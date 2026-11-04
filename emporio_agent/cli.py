"""CLI de atendimento: chat no terminal com sessão persistida.

Uso:
  emporio                          chat interativo (sessão "cli")
  emporio --session 5567999990000  retoma/cria a sessão com esse id
  emporio --new                    apaga a sessão antes de começar
  emporio --pergunta "..."         modo não interativo (pode repetir a flag)
  emporio --rastro                 mostra as ferramentas chamadas (desenvolvedor)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from emporio_agent.agent import Agent, AgentReply, provider_error_text
from emporio_agent.config import model_names, provider, reference_now
from emporio_agent.memory import SessionStore

console = Console()


def build_agent() -> Agent:
    """Separado para os testes trocarem o modelo por um simulado."""
    return Agent()


def _print_trace(reply: AgentReply) -> None:
    if not reply.tool_calls:
        return
    lines = []
    for call in reply.tool_calls:
        args = json.dumps(call.args, ensure_ascii=False)
        lines.append(f"[dim]-> {call.name}({args})[/dim]")
    console.print("\n".join(lines))


def _print_model(reply: AgentReply) -> None:
    if reply.model:
        console.print(f"[dim]modelo: {reply.model}[/dim]")


def _print_reply(reply: AgentReply, show_trace: bool) -> None:
    if show_trace:
        _print_trace(reply)
        _print_model(reply)
    console.print(Panel(Markdown(reply.text), title="Empório da Música", border_style="cyan"))


def answer(agent: Agent, store: SessionStore, session_id: str, text: str) -> AgentReply:
    history = store.load(session_id)
    reply = agent.reply(history, text)
    store.append(session_id, reply.new_messages)
    return reply


def safe_answer(agent: Agent, store: SessionStore, session_id: str, text: str) -> AgentReply:
    """Como `answer`, mas uma falha do provedor (cota, rede) vira uma mensagem
    amigável em vez de derrubar o chat. Nada é salvo na sessão nesse caso."""
    try:
        return answer(agent, store, session_id, text)
    except Exception as exc:  # noqa: BLE001 - qualquer erro do provedor
        return AgentReply(text=provider_error_text(exc))


def run_interactive(agent: Agent, store: SessionStore, session_id: str, show_trace: bool) -> None:
    history = store.load(session_id)
    console.print(
        Panel(
            f"Sessão [bold]{session_id}[/bold] com {len(history)} mensagens salvas. "
            f"Provedor {provider()} / modelos {' > '.join(model_names())}. "
            f"Data de referência {reference_now():%d/%m/%Y}.\n"
            "Comandos: /sair, /limpar (apaga a sessão), /rastro (liga/desliga ferramentas).",
            title="Atendimento Empório da Música",
            border_style="green",
        )
    )
    while True:
        try:
            text = console.input("[bold yellow]Você:[/bold yellow] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nAté mais!")
            return
        if not text:
            continue
        if text.lower() in ("/sair", "/exit", "/quit"):
            console.print("Até mais!")
            return
        if text.lower() == "/limpar":
            store.delete(session_id)
            console.print("[dim]Sessão apagada.[/dim]")
            continue
        if text.lower() == "/rastro":
            show_trace = not show_trace
            console.print(
                f"[dim]Rastro de ferramentas: {'ligado' if show_trace else 'desligado'}[/dim]"
            )
            continue
        with console.status("[dim]consultando...[/dim]"):
            reply = safe_answer(agent, store, session_id, text)
        _print_reply(reply, show_trace)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emporio", description=__doc__.split("\n\n")[0])
    parser.add_argument("--session", default="cli", help="id da sessão (padrão: cli)")
    parser.add_argument("--new", action="store_true", help="apaga a sessão antes de começar")
    parser.add_argument(
        "--pergunta", action="append", metavar="TEXTO", help="modo não interativo; repetível"
    )
    parser.add_argument(
        "--rastro",
        action="store_true",
        help="mostra as ferramentas chamadas e o modelo usado (visão de desenvolvedor)",
    )
    args = parser.parse_args(argv)

    store = SessionStore()
    if args.new:
        store.delete(args.session)

    agent = build_agent()
    show_trace = args.rastro

    if args.pergunta:
        for text in args.pergunta:
            console.print(f"[bold yellow]Você:[/bold yellow] {text}")
            reply = safe_answer(agent, store, args.session, text)
            _print_reply(reply, show_trace)
        return 0

    run_interactive(agent, store, args.session, show_trace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
