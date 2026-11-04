from __future__ import annotations

from evals import CASES_PATH, check_turn, load_cases


def test_cases_file_is_well_formed():
    cases, forbidden = load_cases(CASES_PATH)
    assert len(cases) >= 20 and forbidden
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "ids repetidos"
    allowed = {
        "user",
        "expect_tools",
        "expect_no_tools",
        "must_contain",
        "must_contain_any",
        "must_contain_any_2",
        "must_not_contain",
    }
    for case in cases:
        assert case["turns"], case["id"]
        for turn in case["turns"]:
            assert set(turn) <= allowed, (case["id"], set(turn) - allowed)


def test_check_turn_rules():
    spec = {
        "expect_tools": ["detalhar_produto", "buscar_produtos"],
        "must_contain": ["2.089,05"],
        "must_contain_any": ["pix", "à vista"],
        "must_not_contain": ["site"],
    }
    ok = check_turn(spec, "Sai por R$ 2.089,05 no PIX.", ["detalhar_produto"], ["reservar"])
    assert ok == []

    bad = check_turn(spec, "Posso reservar no nosso site.", [], ["reservar"])
    assert any("esperava chamar" in f for f in bad)
    assert any("faltou '2.089,05'" in f for f in bad)
    assert any("faltou algum de" in f for f in bad)
    assert any("não devia conter 'site'" in f for f in bad)
    assert any("não devia conter 'reservar'" in f for f in bad)

    no_tools = check_turn({"expect_no_tools": True}, "ok", ["info_loja"], [])
    assert no_tools and "não devia chamar" in no_tools[0]
