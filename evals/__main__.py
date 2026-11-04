"""Roda os casos de evals/cases.yaml contra o modelo configurado.

    uv run python -m evals                 roda tudo e grava evals/results.md
    uv run python -m evals --only pedido_  só casos cujo id contém o texto
    uv run python -m evals --no-report     não grava o relatório

Cada caso começa com histórico vazio. Usa o mesmo Agent da CLI e da UI.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from emporio_agent.agent import Agent
from emporio_agent.config import model_names, provider, reference_now
from evals import CASES_PATH, CaseResult, TurnResult, check_turn, load_cases

REPORT_PATH = Path(__file__).with_name("results.md")
console = Console()


def run_case(agent: Agent, case: dict, forbidden: list[str]) -> CaseResult:
    history = []
    turns: list[TurnResult] = []
    for spec in case["turns"]:
        try:
            reply = agent.reply(history, spec["user"])
        except Exception as exc:  # noqa: BLE001 - falha do provedor conta como erro do caso
            return CaseResult(
                case["id"], case.get("group", ""), turns, error=f"{type(exc).__name__}: {exc}"
            )
        history += reply.new_messages
        tools = [t.name for t in reply.tool_calls]
        turns.append(
            TurnResult(
                user=spec["user"],
                reply=reply.text,
                tools=tools,
                model=reply.model,
                failures=check_turn(spec, reply.text, tools, forbidden),
            )
        )
    return CaseResult(case["id"], case.get("group", ""), turns)


def write_report(results: list[CaseResult], path: Path) -> None:
    passed = sum(r.passed for r in results)
    by_group: Counter[str] = Counter()
    total_group: Counter[str] = Counter()
    for r in results:
        total_group[r.group] += 1
        by_group[r.group] += int(r.passed)
    models = sorted({t.model for r in results for t in r.turns if t.model})

    lines = [
        "# Resultado da avaliação",
        "",
        f"- Data da execução: {datetime.now():%d/%m/%Y %H:%M}",
        f"- Provedor: {provider()} | cadeia de modelos: {' > '.join(model_names())}",
        f"- Modelo(s) que responderam: {', '.join(models) or '-'}",
        f"- Data de referência do agente: {reference_now():%d/%m/%Y}",
        f"- Casos: {len(results)} | aprovados: {passed} | taxa: {passed / len(results):.0%}",
        "",
        "## Por grupo",
        "",
        "| Grupo | Aprovados | Total |",
        "|---|---|---|",
    ]
    for group in sorted(total_group):
        lines.append(f"| {group} | {by_group[group]} | {total_group[group]} |")
    lines += [
        "",
        "## Por caso",
        "",
        "| Caso | Resultado | Ferramentas | Falhas |",
        "|---|---|---|---|",
    ]
    for r in results:
        status = "ok" if r.passed else "FALHOU"
        tools = ", ".join(t for turn in r.turns for t in turn.tools) or "-"
        failures = r.error or "; ".join(f for turn in r.turns for f in turn.failures) or "-"
        lines.append(f"| {r.case_id} | {status} | {tools} | {failures} |")
    lines += ["", "## Transcrições", ""]
    for r in results:
        lines.append(f"### {r.case_id} ({'ok' if r.passed else 'FALHOU'})")
        lines.append("")
        for turn in r.turns:
            lines.append(f"**Cliente:** {turn.user}")
            lines.append("")
            if turn.tools:
                lines.append(f"_ferramentas: {', '.join(turn.tools)}_")
                lines.append("")
            lines.append("**Agente:** " + turn.reply.replace("\n", "  \n"))
            lines.append("")
            for failure in turn.failures:
                lines.append(f"- falha: {failure}")
            if turn.failures:
                lines.append("")
        if r.error:
            lines.append(f"- erro: {r.error}")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", default="", help="roda só casos cujo id contém este texto")
    parser.add_argument("--no-report", action="store_true", help="não grava evals/results.md")
    args = parser.parse_args(argv)

    cases, forbidden = load_cases(CASES_PATH)
    if args.only:
        cases = [c for c in cases if args.only in c["id"]]
    if not cases:
        console.print("[red]nenhum caso selecionado[/red]")
        return 2

    agent = Agent()
    results: list[CaseResult] = []
    table = Table(title="Avaliação do agente", show_lines=False)
    table.add_column("caso")
    table.add_column("resultado")
    table.add_column("detalhe")

    for case in cases:
        with console.status(f"[dim]{case['id']}[/dim]"):
            result = run_case(agent, case, forbidden)
        results.append(result)
        detail = result.error or "; ".join(f for t in result.turns for f in t.failures)
        table.add_row(
            case["id"],
            "[green]ok[/green]" if result.passed else "[red]FALHOU[/red]",
            detail[:110],
        )

    console.print(table)
    passed = sum(r.passed for r in results)
    console.print(
        f"\n[bold]{passed}/{len(results)} casos aprovados ({passed / len(results):.0%})[/bold]"
    )
    if not args.no_report:
        write_report(results, REPORT_PATH)
        console.print(f"[dim]relatório em {REPORT_PATH}[/dim]")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
