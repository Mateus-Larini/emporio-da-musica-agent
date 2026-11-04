"""Loop do agente: modelo decide ferramentas, código executa, modelo responde.

Padrão ReAct via tool use nativo. O loop é escrito aqui (cerca de 60 linhas) em vez
de usar um executor pronto, para que cada passo seja visível e testável: quais
ferramentas foram chamadas, com quais argumentos e o que devolveram.
"""

from __future__ import annotations

import json
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

        text = (ai.text or "").strip() if ai is not None else ""
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
            try:
                ai = (bound if with_tools else base).invoke(messages)
            except Exception as exc:  # noqa: BLE001 - decidimos abaixo se é caso de fallback
                if not is_fallback_error(exc) or index == len(self.models) - 1:
                    raise
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
