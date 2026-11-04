"""Loop do agente: modelo decide ferramentas, código executa, modelo responde.

Padrão ReAct via tool use nativo. O loop é escrito aqui (cerca de 60 linhas) em vez
de usar um executor pronto, para que cada passo seja visível e testável: quais
ferramentas foram chamadas, com quais argumentos e o que devolveram.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from emporio_agent.config import model_names, provider, reference_now
from emporio_agent.data.repository import Repository
from emporio_agent.prompts import system_prompt
from emporio_agent.tools import build_tools

MAX_TOOL_ROUNDS = 6
FALLBACK_TEXT = (
    "Desculpa, não consegui concluir sua solicitação agora. Pode repetir ou chamar a "
    "equipe no WhatsApp (67) 3321-4500?"
)


@dataclass
class ToolTrace:
    name: str
    args: dict[str, Any]
    result: str


@dataclass
class AgentReply:
    text: str
    tool_calls: list[ToolTrace] = field(default_factory=list)
    new_messages: list[BaseMessage] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


def provider_error_text(exc: Exception) -> str:
    """Mensagem para o usuário quando o provedor do modelo falha."""
    message = str(exc)
    if "429" in message or "rate_limit" in message.lower():
        return (
            "O serviço do modelo atingiu o limite de uso por enquanto. Tente de novo em "
            "alguns minutos ou troque o modelo em EMPORIO_MODEL no arquivo .env."
        )
    if "401" in message or "api key" in message.lower() or "api_key" in message.lower():
        return "Chave da API ausente ou inválida. Confira o arquivo .env (veja .env.example)."
    return f"Não consegui falar com o modelo agora ({type(exc).__name__}). Tente novamente."


def build_model(name: str) -> BaseChatModel:
    """Instancia um modelo do provedor configurado (.env)."""
    if provider() == "groq":
        from langchain_groq import ChatGroq

        # 1000 tokens de saída bastam para uma mensagem de WhatsApp e respeitam o
        # limite por minuto da cota gratuita do Groq em todos os modelos da cadeia.
        return ChatGroq(model=name, max_tokens=1000, temperature=0.3, max_retries=2)

    from langchain_anthropic import ChatAnthropic

    # Haiku 5.5: thinking fica ligado por padrão; "low" é suficiente para
    # escolher ferramentas e redigir uma mensagem de WhatsApp.
    return ChatAnthropic(model=name, max_tokens=2048, effort="low", max_retries=2)


def default_models() -> list[BaseChatModel]:
    return [build_model(name) for name in model_names()]


# Limite por minuto do Groq: o erro 429 diz "Please try again in 1.234s" (ou "1m2s").
# Esperas até este teto valem a pena antes de descer na cadeia de modelos; acima dele
# (cota diária, que leva horas) é melhor trocar de modelo na hora.
SHORT_WAIT_LIMIT = 30.0
_RETRY_AFTER_RE = re.compile(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)(ms|s)", re.IGNORECASE)


def retry_after_seconds(exc: Exception) -> float | None:
    """Tempo de espera sugerido pelo provedor em um 429, se a mensagem trouxer um."""
    match = _RETRY_AFTER_RE.search(str(exc))
    if not match:
        return None
    minutes, value, unit = match.groups()
    seconds = float(value) / (1000 if unit == "ms" else 1)
    return seconds + 60 * int(minutes or 0)


def is_fallback_error(exc: Exception) -> bool:
    """Erros em que vale tentar o próximo modelo da cadeia: cota esgotada,
    modelo inexistente/indisponível, falha do servidor ou de rede."""
    status = getattr(exc, "status_code", None)
    if status in (404, 429) or (isinstance(status, int) and status >= 500):
        return True
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("rate limit", "rate_limit", "429", "404", "not found", "overloaded")
    ) or type(exc).__name__ in ("APIConnectionError", "APITimeoutError")


class Agent:
    def __init__(
        self,
        model: BaseChatModel | None = None,
        models: list[BaseChatModel] | None = None,
        repo: Repository | None = None,
        tools: list[BaseTool] | None = None,
        now_fn: Callable[[], datetime] = reference_now,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ):
        self.repo = repo or Repository()
        self.now_fn = now_fn
        self.tools = tools or build_tools(self.repo, now_fn)
        self.tool_map = {t.name: t for t in self.tools}
        if model is not None:
            models = [model]
        elif models is None:
            models = default_models()
        if not models:
            raise ValueError("Nenhum modelo configurado. Veja .env.example.")
        # Pares (modelo sem ferramentas, modelo com ferramentas), na ordem de tentativa.
        self.models = [(m, m.bind_tools(self.tools)) for m in models]
        self.active_index = 0
        self.max_tool_rounds = max_tool_rounds
        self.sleep = time.sleep  # injetável nos testes

    def reply(self, history: list[BaseMessage], user_text: str) -> AgentReply:
        """Responde `user_text` dado o histórico (sem system message).

        Devolve o texto final e as mensagens novas (humana, IA, ferramentas) para
        o chamador anexar ao histórico persistido.
        """
        new_messages: list[BaseMessage] = [HumanMessage(content=user_text)]
        traces: list[ToolTrace] = []
        usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        system = SystemMessage(content=system_prompt(self.now_fn()))

        ai: AIMessage | None = None
        for _ in range(self.max_tool_rounds + 1):
            ai = self._invoke([system, *history, *new_messages], with_tools=True)
            new_messages.append(ai)
            self._accumulate_usage(usage, ai)
            if not ai.tool_calls:
                break
            for call in ai.tool_calls:
                result = self._run_tool(call["name"], call["args"])
                traces.append(ToolTrace(call["name"], call["args"], result))
                new_messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        else:
            # Estourou o número de rodadas: pede uma resposta final sem ferramentas.
            ai = self._invoke(
                [
                    system,
                    *history,
                    *new_messages,
                    HumanMessage(content="Responda agora ao cliente com o que já tem."),
                ],
                with_tools=False,
            )
            new_messages.append(ai)
            self._accumulate_usage(usage, ai)

        text = _tidy_text((ai.text or "").strip()) if ai is not None else ""
        return AgentReply(
            text=text or FALLBACK_TEXT,
            tool_calls=traces,
            new_messages=new_messages,
            usage=usage,
            model=self.model_name,
        )

    @property
    def model_name(self) -> str:
        """Nome do modelo que respondeu por último (para a UI e os logs)."""
        base = self.models[self.active_index][0]
        return getattr(base, "model", None) or getattr(base, "model_name", None) or "?"

    def _invoke(self, messages: list[BaseMessage], with_tools: bool) -> AIMessage:
        """Chama o modelo ativo; em erro de cota/indisponibilidade passa ao próximo
        da cadeia e mantém esse como ativo para as chamadas seguintes."""
        last_error: Exception | None = None
        for index in range(self.active_index, len(self.models)):
            base, bound = self.models[index]
            model = bound if with_tools else base
            try:
                ai = model.invoke(messages)
            except Exception as exc:  # noqa: BLE001 - decidimos abaixo se é caso de fallback
                if not is_fallback_error(exc):
                    raise
                wait = retry_after_seconds(exc)
                if wait is not None and wait <= SHORT_WAIT_LIMIT:
                    # Limite por minuto: uma espera curta preserva o modelo principal,
                    # que responde melhor que os reservas.
                    self.sleep(wait + 0.5)
                    try:
                        ai = model.invoke(messages)
                    except Exception as retry_exc:  # noqa: BLE001
                        if not is_fallback_error(retry_exc):
                            raise
                        exc = retry_exc
                    else:
                        self.active_index = index
                        return ai
                if index == len(self.models) - 1:
                    raise exc
                last_error = exc
                continue
            self.active_index = index
            return ai
        raise last_error if last_error else RuntimeError("nenhum modelo disponível")

    def _run_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self.tool_map.get(name)
        if tool is None:
            return f'{{"erro": "ferramenta desconhecida: {name}"}}'
        try:
            return str(tool.invoke(args))
        except Exception as exc:  # noqa: BLE001 - o erro volta ao modelo, não derruba o chat
            return json.dumps(
                {
                    "erro": f"falha ao executar {name}: {exc}",
                    "instrucao": "Não repita a mesma chamada. Informe ao cliente que houve "
                    "um problema técnico momentâneo e ofereça o WhatsApp da equipe.",
                },
                ensure_ascii=False,
            )

    @staticmethod
    def _accumulate_usage(usage: dict[str, int], ai: AIMessage) -> None:
        meta = ai.usage_metadata or {}
        usage["input_tokens"] += int(meta.get("input_tokens", 0) or 0)
        usage["output_tokens"] += int(meta.get("output_tokens", 0) or 0)


_PERCENT_RE = re.compile(r"(\d)\s+%")


def _tidy_text(text: str) -> str:
    """Pequenos acertos tipográficos que o modelo não segue de forma estável.

    Hífens tipográficos (U+2010, U+2011) viram o hífen comum: alguns modelos
    escrevem "e‑mail" com o hífen inseparável, que aparece como um traço diferente
    em terminais e no Streamlit. Percentuais ficam sem espaço ("5%", não "5 %"),
    como se escreve em português."""
    text = text.replace("\u2010", "-").replace("\u2011", "-")
    return _PERCENT_RE.sub(r"\1%", text)


# Scripts em lote (avaliação, exemplos) rodam dezenas de conversas seguidas e
# esbarram na cota diária gratuita. Quando o provedor não diz quanto esperar,
# usamos este intervalo entre tentativas.
DEFAULT_QUOTA_WAIT = 600.0


def reply_when_quota_allows(
    agent: Agent,
    history: list[BaseMessage],
    user_text: str,
    max_wait: float,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> AgentReply:
    """Como `agent.reply`, mas quando toda a cadeia de modelos está sem cota espera o
    tempo que o provedor pede (ou DEFAULT_QUOTA_WAIT) e tenta de novo, até somar
    `max_wait` segundos. Outros erros sobem na hora."""
    waited = 0.0
    while True:
        try:
            return agent.reply(history, user_text)
        except Exception as exc:  # noqa: BLE001 - só esperamos em erro de cota
            if not is_fallback_error(exc):
                raise
            wait = retry_after_seconds(exc) or DEFAULT_QUOTA_WAIT
            wait += 5.0  # margem para o relógio do provedor
            if waited + wait > max_wait:
                raise
            log(f"sem cota ({agent.model_name}); aguardando {wait:.0f}s")
            sleep(wait)
            waited += wait
            # Durante a espera todos os modelos reencheram; a nova tentativa começa
            # do principal em vez de ficar presa no último que falhou.
            agent.active_index = 0
