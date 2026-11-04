from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
    # system prompt vai na frente e carrega a data de referência
    assert model.calls[0][0].content.startswith("Você é o atendente virtual")
    assert "25/03/2026" in model.calls[0][0].content
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
