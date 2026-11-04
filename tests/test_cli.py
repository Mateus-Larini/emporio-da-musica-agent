from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from emporio_agent import cli
from emporio_agent.agent import Agent
from emporio_agent.data.repository import Repository
from emporio_agent.memory import SessionStore
from tests.test_agent import NOW, ScriptedModel, tool_call


@pytest.fixture
def fake_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo: Repository):
    model = ScriptedModel(
        [
            tool_call("info_loja", {}),
            AIMessage(content="Ficamos na Rua 14 de Maio, 3200."),
            AIMessage(content="De nada!"),
        ]
    )
    monkeypatch.setattr(
        cli, "build_agent", lambda: Agent(model=model, repo=repo, now_fn=lambda: NOW)
    )
    monkeypatch.setattr(cli, "SessionStore", lambda: SessionStore(tmp_path))
    return tmp_path


def test_cli_non_interactive_persists_session(fake_cli: Path, capsys: pytest.CaptureFixture):
    code = cli.main(
        ["--session", "teste", "--pergunta", "Onde fica a loja?", "--pergunta", "obrigado"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "info_loja" in out  # rastro da ferramenta
    assert "Rua 14 de Maio" in out and "De nada" in out
    saved = SessionStore(fake_cli).load("teste")
    # turno 1: human, ai(tool_call), tool, ai; turno 2: human, ai
    assert len(saved) == 6


def test_cli_new_flag_clears_session(fake_cli: Path, capsys: pytest.CaptureFixture):
    store = SessionStore(fake_cli)
    store.append("x", [AIMessage(content="lixo antigo")])
    cli.main(["--session", "x", "--new", "--sem-rastro", "--pergunta", "oi"])
    out = capsys.readouterr().out
    assert "info_loja" not in out
    saved = store.load("x")
    assert all(m.content != "lixo antigo" for m in saved)
