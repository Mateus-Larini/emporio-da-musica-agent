"""Avaliação do agente contra casos com resultado esperado (evals/cases.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CASES_PATH = Path(__file__).with_name("cases.yaml")


@dataclass
class TurnResult:
    user: str
    reply: str
    tools: list[str]
    model: str
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass
class CaseResult:
    case_id: str
    group: str
    turns: list[TurnResult]
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(t.passed for t in self.turns)


def load_cases(path: Path = CASES_PATH) -> tuple[list[dict[str, Any]], list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["cases"], data.get("forbidden_everywhere", [])


def check_turn(
    spec: dict[str, Any], reply: str, tools: list[str], forbidden: list[str]
) -> list[str]:
    """Compara uma resposta com as expectativas do turno. Devolve a lista de falhas."""
    text = reply.lower()
    failures: list[str] = []

    expected_tools = spec.get("expect_tools")
    if expected_tools and not any(t in tools for t in expected_tools):
        failures.append(f"esperava chamar {expected_tools}, chamou {tools or 'nada'}")
    if spec.get("expect_no_tools") and tools:
        failures.append(f"não devia chamar ferramentas, chamou {tools}")

    for needle in spec.get("must_contain", []):
        if needle.lower() not in text:
            failures.append(f"faltou '{needle}'")

    for key in ("must_contain_any", "must_contain_any_2"):
        options = spec.get(key, [])
        if options and not any(o.lower() in text for o in options):
            failures.append(f"faltou algum de {options}")

    for needle in list(spec.get("must_not_contain", [])) + list(forbidden):
        if needle.lower() in text:
            failures.append(f"não devia conter '{needle}'")

    return failures
