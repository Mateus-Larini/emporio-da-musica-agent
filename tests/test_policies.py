from __future__ import annotations

import pytest

from emporio_agent.policies import load_sections, search_sections


def test_sections_are_parsed_from_pdf():
    sections = load_sections()
    numbers = [s.number for s in sections]
    for expected in (
        "1",
        "1.2",
        "2",
        "3",
        "3.1",
        "4.1",
        "4.2",
        "4.4",
        "5.1",
        "5.3",
        "6.2",
        "7.1",
        "8.1",
        "9",
    ):
        assert expected in numbers, expected
    by_number = {s.number: s for s in sections}
    assert by_number["2"].title == "Horário de Funcionamento"
    assert "7 (sete) dias" in by_number["4.1"].text
    assert "Página" not in by_number["5.3"].text


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Me arrependi da compra, posso devolver?", "4.1"),
        ("Qual o horário de vocês no sábado?", "2"),
        ("Vocês aceitam PIX? Tem desconto?", "3"),
        ("Quantas vezes posso parcelar?", "3.1"),
        ("Como rastreio meu pedido?", "5.3"),
        ("Quanto é o frete pra Campo Grande?", "5.1"),
        ("Meu violão veio com defeito", "4.2"),
        ("Qual a garantia?", "8.1"),
        ("Vocês vendem cordas?", "7.1"),
        ("Quero excluir meus dados", "9"),
        ("Onde fica a loja?", "1.2"),
    ],
)
def test_retrieval_hits_expected_section(question: str, expected: str):
    top = [s.number for s in search_sections(question, k=3)]
    assert expected in top, f"{question!r} -> {top}"
