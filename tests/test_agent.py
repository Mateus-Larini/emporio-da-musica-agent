from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from emporio_agent.agent import FALLBACK_TEXT, Agent
from emporio_agent.data.repository import Repository
from emporio_agent.memory import SessionStore

NOW = datetime(2026, 3, 25, 10, 30)


class ScriptedModel:
    """Modelo falso: devolve respostas pré-definidas e grava o que recebeu."""

    def __init__(self, replies: list[AIMessage]):
        self.replies = list(replies)
        self.calls: list[list] = []
        self.tools = None

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        self.calls.append(list(messages))
        if self.replies:
            return self.replies.pop(0)
        return AIMessage(content="")


def tool_call(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}]
    )


def test_agent_runs_tool_then_answers(repo: Repository):
    model = ScriptedModel(
        [
            tool_call("detalhar_produto", {"produto": "Takamine GD20"}),
            AIMessage(content="O Takamine GD20 sai por R$ 2.199,00, ou R$ 2.089,05 no PIX."),
        ]
    )
    agent = Agent(model=model, repo=repo, now_fn=lambda: NOW)
    reply = agent.reply([], "Quanto custa o Takamine GD20?")

    assert "2.199" in reply.text
    assert [t.name for t in reply.tool_calls] == ["detalhar_produto"]
    assert '"id": 95' in reply.tool_calls[0].result
    kinds = [type(m).__name__ for m in reply.new_messages]
    assert kinds == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage"]
    # system prompt vai na frente e carrega a data de referência e a saudação da hora
    assert model.calls[0][0].content.startswith("Você é o atendente virtual")
    assert "25/03/2026" in model.calls[0][0].content
    assert 'Cumprimente com "Bom dia!"' in model.calls[0][0].content
    assert len(model.tools) == 8


def test_agent_handles_unknown_tool_and_empty_reply(repo: Repository):
    model = ScriptedModel([tool_call("nao_existe", {}), AIMessage(content="")])
    agent = Agent(model=model, repo=repo, now_fn=lambda: NOW)
    reply = agent.reply([], "oi")
    assert "ferramenta desconhecida" in reply.tool_calls[0].result
    assert reply.text == FALLBACK_TEXT


def test_agent_stops_after_max_rounds(repo: Repository):
    loop = [tool_call("info_loja", {}, f"c{i}") for i in range(3)]
    model = ScriptedModel(loop + [AIMessage(content="Fechando com o que tenho.")])
    agent = Agent(model=model, repo=repo, now_fn=lambda: NOW, max_tool_rounds=2)
    reply = agent.reply([], "horário?")
    assert reply.text == "Fechando com o que tenho."
    assert len(reply.tool_calls) == 3  # max_tool_rounds + 1 chamadas, depois corte
    # a chamada final recebe um pedido explícito de resposta, sem novas ferramentas
    assert isinstance(model.calls[-1][-1], HumanMessage)
    assert "Responda agora" in model.calls[-1][-1].content


def test_session_store_roundtrip(tmp_path: Path):
    store = SessionStore(tmp_path)
    msgs = [
        HumanMessage(content="oi"),
        tool_call("info_loja", {}),
        ToolMessage(content="{}", tool_call_id="c1"),
        AIMessage(content="Olá!"),
    ]
    store.append("5567999990000", msgs)
    loaded = store.load("5567999990000")
    assert [type(m).__name__ for m in loaded] == [type(m).__name__ for m in msgs]
    assert loaded[1].tool_calls[0]["name"] == "info_loja"
    assert store.list_sessions() == ["5567999990000"]
    store.delete("5567999990000")
    assert store.load("5567999990000") == []


def test_greeting_follows_reference_hour():
    from emporio_agent.prompts import greeting

    assert greeting(datetime(2026, 3, 25, 8, 0)) == "Bom dia"
    assert greeting(datetime(2026, 3, 25, 14, 0)) == "Boa tarde"
    assert greeting(datetime(2026, 3, 25, 19, 30)) == "Boa noite"


class FailingModel:
    """Modelo falso que sempre falha com o erro informado."""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        raise self.exc


class RateLimited(Exception):
    status_code = 429


class BadRequest(Exception):
    status_code = 400


def test_agent_falls_back_to_next_model_on_rate_limit(repo: Repository):
    broken = FailingModel(RateLimited("429 rate limit"))
    good = ScriptedModel([AIMessage(content="Respondi pelo segundo modelo.")])
    agent = Agent(models=[broken, good], repo=repo, now_fn=lambda: NOW)
    reply = agent.reply([], "oi")
    assert reply.text == "Respondi pelo segundo modelo."
    assert broken.calls == 1
    # o segundo passa a ser o ativo: a próxima mensagem não bate mais no quebrado
    good.replies.append(AIMessage(content="De novo pelo segundo."))
    agent.reply([], "oi de novo")
    assert broken.calls == 1


def test_agent_does_not_fall_back_on_client_error(repo: Repository):
    broken = FailingModel(BadRequest("400 bad request"))
    good = ScriptedModel([AIMessage(content="nunca")])
    agent = Agent(models=[broken, good], repo=repo, now_fn=lambda: NOW)
    with pytest.raises(BadRequest):
        agent.reply([], "oi")


def test_model_names_from_env(monkeypatch: pytest.MonkeyPatch):
    from emporio_agent.config import model_names

    monkeypatch.setenv("EMPORIO_PROVIDER", "groq")
    monkeypatch.delenv("EMPORIO_MODEL", raising=False)
    monkeypatch.delenv("EMPORIO_MODEL_FALLBACKS", raising=False)
    assert model_names()[0] == "openai/gpt-oss-120b" and len(model_names()) == 3
    monkeypatch.setenv("EMPORIO_MODEL", "a")
    monkeypatch.setenv("EMPORIO_MODEL_FALLBACKS", "b, c,a")
    assert model_names() == ["a", "b", "c"]
