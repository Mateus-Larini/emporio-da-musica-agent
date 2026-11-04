from __future__ import annotations

import json
from datetime import datetime

import pytest

from emporio_agent.data.repository import Repository
from emporio_agent.tools import build_tools

NOW = datetime(2026, 3, 25, 10, 30)  # quarta-feira, loja aberta


@pytest.fixture(scope="module")
def tools(repo: Repository):
    return {t.name: t for t in build_tools(repo, now_fn=lambda: NOW)}


def call(tools, name: str, **kwargs) -> dict:
    return json.loads(tools[name].invoke(kwargs))


def test_tool_names(tools):
    assert set(tools) == {
        "buscar_produtos",
        "detalhar_produto",
        "listar_promocoes",
        "consultar_pedido",
        "pedidos_do_cliente",
        "consultar_politicas",
        "simular_pagamento_e_frete",
        "info_loja",
    }


def test_buscar_violoes_ate_1000(tools):
    out = call(tools, "buscar_produtos", busca="violão", preco_max=1000, limite=20)
    names = [r["nome"] for r in out["resultados"]]
    assert names and all(r["preco_tabela"] <= 1000 for r in out["resultados"])
    assert "Giannini GF-3D Dreadnought Sunburst" not in names  # sem estoque
    assert all(r["preco_pix"] < r["preco_tabela"] for r in out["resultados"] if "promocao" not in r)


def test_buscar_sem_resultado_da_dica(tools):
    out = call(tools, "buscar_produtos", categoria="Cordas Orquestrais")
    assert out["resultados"] == [] and "Categorias" in out["dica"]


def test_detalhar_takamine_gd20(tools):
    out = call(tools, "detalhar_produto", produto="Takamine GD20")
    assert out["id"] == 95
    assert out["preco_tabela"] == 2199 and out["preco_pix"] == 2089.05
    assert out["parcelamento_maximo_sem_juros"] == 12
    assert out["especificacoes"]["strings"] == "aço" or out["especificacoes"]
    assert out["disponibilidade"].startswith("disponível")


def test_detalhar_produto_em_promocao_mostra_original_e_percentual(tools):
    out = call(tools, "detalhar_produto", produto="Taylor 110e")
    assert out["promocao"]["desconto_percentual"] == 8
    assert out["promocao"]["preco_promocional"] == 5519.08
    assert out["preco_pix"] == 5519.08  # PIX não cumula
    assert out["preco_tabela"] == 5999


def test_detalhar_indisponivel_traz_alternativas(tools):
    out = call(tools, "detalhar_produto", produto="96")
    assert out["disponibilidade"] == "temporariamente sem estoque"
    assert out["alternativas_disponiveis"]


def test_detalhar_inexistente(tools):
    assert "erro" in call(tools, "detalhar_produto", produto="xpto zzz")


def test_listar_promocoes(tools):
    out = call(tools, "listar_promocoes")
    assert out["total"] == 4
    assert all("promocao" in p and p["preco_tabela"] for p in out["promocoes_ativas"])


def test_consultar_pedido_exige_identificacao(tools):
    assert "Identificação" in call(tools, "consultar_pedido", numero_pedido=7)["erro"]


def test_consultar_pedido_dados_errados_nao_revela(tools):
    out = call(tools, "consultar_pedido", numero_pedido=7, telefone="(67) 99812-3456")
    assert "não conferem" in out["erro"] and "itens" not in out


def test_consultar_pedido_ok_com_janelas(tools, repo: Repository):
    customer = repo.get_customer(14)
    out = call(tools, "consultar_pedido", numero_pedido=7, telefone=customer.phone)
    assert out["status"] == "entregue" and out["codigo_rastreio"] == "BRKR1122334BR"
    janelas = {j["tipo"]: j for j in out["prazos_troca_devolucao"]["janelas"]}
    assert not janelas["arrependimento"]["dentro_do_prazo"]  # entregue em 17/02, hoje 25/03
    assert janelas["garantia legal"]["dentro_do_prazo"]


def test_pedido_enviado_atrasado_tem_alerta(tools, repo: Repository):
    customer = repo.get_customer(2)
    out = call(tools, "consultar_pedido", numero_pedido=8, email=customer.email)
    assert out["status"] == "enviado" and "alerta" in out


def test_pedidos_do_cliente(tools, repo: Repository):
    customer = repo.get_customer(3)
    out = call(tools, "pedidos_do_cliente", telefone=customer.phone)
    assert [p["numero_pedido"] for p in out["clientes"][0]["pedidos"]] == [19, 1]
    assert "erro" in call(tools, "pedidos_do_cliente", telefone="0000")


def test_consultar_politicas_texto(tools):
    text = tools["consultar_politicas"].invoke({"pergunta": "posso devolver?"})
    assert "4.1" in text and "arrependimento" in text.lower()


def test_simular_pagamento_e_frete(tools):
    out = call(tools, "simular_pagamento_e_frete", valor_total=1000, cidade="Campo Grande")
    assert out["pix"]["valor"] == 950.0
    assert out["parcelamento_sem_juros"][-1] == "10x de R$ 100.00"
    assert out["frete"]["gratis"] and out["frete"]["valor"] == 0.0
    promo = call(tools, "simular_pagamento_e_frete", valor_total=400, produto_em_promocao=True)
    assert promo["pix"]["valor"] == 400 and promo["frete"]["regiao"] == "outras"


def test_info_loja(tools):
    out = call(tools, "info_loja")
    assert out["endereco"].startswith("Rua 14 de Maio")
    assert out["agora"]["loja_aberta_agora"] is True and out["agora"]["dia_da_semana"] == "quarta"


def test_buscar_mostra_indisponiveis_que_casam_com_a_busca(tools):
    out = call(tools, "buscar_produtos", busca="Giannini GF-3D Sunburst")
    names = [r["nome"] for r in out["resultados"]]
    assert "Giannini GF-3D Dreadnought Sunburst" not in names
    unavailable = {u["nome"]: u["situacao"] for u in out["indisponiveis_no_momento"]}
    assert unavailable["Giannini GF-3D Dreadnought Sunburst"] == "temporariamente sem estoque"


def test_janelas_trazem_condicoes_proprias(tools, repo: Repository):
    customer = repo.get_customer(14)
    out = call(tools, "consultar_pedido", numero_pedido=7, telefone=customer.phone)
    janelas = {j["tipo"]: j for j in out["prazos_troca_devolucao"]["janelas"]}
    assert "compras online" in janelas["arrependimento"]["condicoes"]
    assert "defeito de fabricação" in janelas["troca por defeito"]["condicoes"]


def test_telefone_truncado_pede_numero_completo(tools):
    out = call(tools, "consultar_pedido", numero_pedido=7, telefone="67")
    assert "incompleto" in out["erro"] and "itens" not in out
    out = call(tools, "pedidos_do_cliente", telefone="(67)")
    assert "incompleto" in out["erro"]


def test_privacy_masking():
    from emporio_agent.privacy import describe_call, mask_text

    assert describe_call(
        "consultar_pedido", {"numero_pedido": 7, "telefone": "(67) 99789-0123"}
    ) == ("consultar_pedido(numero_pedido=7, telefone='***0123')")
    masked = mask_text("pedido 7, tel (67) 99123-7788, email lucas.mendes@jmail.com")
    assert "99123" not in masked and "lucas.mendes" not in masked
    assert "***7788" in masked and "lu***@jmail.com" in masked
