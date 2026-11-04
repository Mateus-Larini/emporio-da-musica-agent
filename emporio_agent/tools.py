"""Ferramentas que o modelo pode chamar. Cada uma recebe argumentos validados
(Pydantic), consulta o repositório/regras e devolve JSON em português.

Decisões:
- O modelo nunca recebe acesso a SQL; só a estas funções.
- Consulta de pedido exige telefone ou e-mail que confira com o cliente do pedido
  (seção 9 do manual, LGPD).
- Preço promocional sempre vem acompanhado do preço original e do percentual
  (seção 6.2), e o preço PIX já considera a não-cumulatividade.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from emporio_agent import rules
from emporio_agent.config import reference_now
from emporio_agent.data.repository import Order, Product, Repository
from emporio_agent.policies import format_sections, search_sections
from emporio_agent.store import HOURS_TEXT, STORE, status_now


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _availability(product: Product) -> str:
    if product.status == "discontinued":
        return "descontinuado (não faz mais parte do catálogo)"
    if product.status == "coming_soon":
        return "em breve (ainda não está à venda)"
    if product.stock_quantity <= 0:
        return "temporariamente sem estoque"
    return f"disponível ({product.stock_quantity} em estoque)"


def _product_payload(repo: Repository, product: Product, detailed: bool = False) -> dict:
    promo = repo.active_promotion(product.product_id)
    quote = rules.price_quote(product, promo)
    payload: dict[str, Any] = {
        "id": product.product_id,
        "nome": product.name,
        "categoria": product.category_name,
        "disponibilidade": _availability(product),
        "preco_tabela": quote.list_price,
    }
    if quote.promo_price is not None:
        payload["promocao"] = {
            "nome": quote.promo_description,
            "desconto_percentual": quote.promo_percent,
            "preco_promocional": quote.promo_price,
            "observacao": "Desconto PIX de 5% NÃO se aplica sobre preço promocional.",
        }
    payload["preco_pix"] = quote.pix_price
    payload["preco_cartao_ou_boleto"] = quote.card_price
    payload["parcelamento_maximo_sem_juros"] = rules.max_installments(quote.card_price)
    if detailed:
        payload["descricao"] = product.description
        payload["especificacoes"] = product.specs
        options = rules.installment_options(quote.card_price)
        payload["opcoes_parcelamento"] = [
            f"{o.installments}x de R$ {o.amount:.2f}" for o in options if o.installments > 1
        ]
        if not product.available:
            payload["alternativas_disponiveis"] = [
                _product_payload(repo, alt) for alt in repo.similar_products(product)
            ]
    return payload


def _order_payload(repo: Repository, order: Order, now: datetime) -> dict:
    customer = repo.get_customer(order.customer_id)
    assessment = rules.return_assessment(order, now.date())
    payload: dict[str, Any] = {
        "numero_pedido": order.order_id,
        "cliente": customer.name if customer else None,
        "cidade": customer.city if customer else None,
        "data_pedido": order.order_date,
        "status": rules.ORDER_STATUS_LABELS.get(order.status, order.status),
        "forma_pagamento": order.payment_method,
        "total_pago": order.total_brl,
        "codigo_rastreio": order.tracking_code,
        "previsao_entrega": order.estimated_delivery,
        "observacoes": order.notes,
        "itens": [
            {
                "produto": i.product_name,
                "quantidade": i.quantity,
                "preco_unitario": i.unit_price_brl,
            }
            for i in order.items
        ],
        "aviso": (
            "Relate o pedido exatamente como está no sistema. Não recalcule total, "
            "desconto ou parcelas de pedidos já feitos."
        ),
    }
    if order.status == "shipped" and order.estimated_delivery:
        if datetime.fromisoformat(order.estimated_delivery).date() < now.date():
            payload["alerta"] = (
                "A previsão de entrega já passou e o pedido ainda consta como enviado. "
                "Oriente o cliente a rastrear pelo código e ofereça acionar a equipe."
            )
    payload["prazos_troca_devolucao"] = {
        "data_referencia": assessment.reference_date.isoformat(),
        "data_recebimento_considerada": (
            assessment.received_on.isoformat() if assessment.received_on else None
        ),
        "janelas": [
            {
                "tipo": w.name,
                "base": w.basis,
                "prazo_final": w.deadline.isoformat(),
                "dias_restantes": w.days_left,
                "dentro_do_prazo": w.open,
                "condicoes": w.conditions,
            }
            for w in assessment.windows
        ],
        "observacao": assessment.note,
    }
    return payload


def _identify(repo: Repository, telefone: str | None, email: str | None) -> list[int] | None:
    if not telefone and not email:
        return None
    customers = repo.find_customers(phone=telefone or None, email=email or None)
    return [c.customer_id for c in customers]


# ---- schemas ----------------------------------------------------------------


class BuscarProdutosArgs(BaseModel):
    busca: str | None = Field(
        default=None,
        description="Palavras do que o cliente procura (ex.: 'violão nylon', 'guitarra fender').",
    )
    categoria: str | None = Field(
        default=None,
        description=(
            "Categoria: Guitarras, Baixos, Baterias e Percussão, Teclados e Pianos, Violões, "
            "Instrumentos de Sopro (Madeiras), Instrumentos de Sopro (Metais), "
            "Cordas Orquestrais, Ukuleles."
        ),
    )
    preco_min: float | None = Field(default=None, description="Preço mínimo em reais.")
    preco_max: float | None = Field(default=None, description="Preço máximo em reais.")
    apenas_disponiveis: bool = Field(
        default=True, description="Se True, só produtos ativos e com estoque."
    )
    limite: int = Field(default=8, ge=1, le=20)


class DetalharProdutoArgs(BaseModel):
    produto: str = Field(description="Nome (ou parte do nome) ou id numérico do produto.")


class ConsultarPedidoArgs(BaseModel):
    numero_pedido: int = Field(description="Número do pedido informado pelo cliente.")
    telefone: str | None = Field(default=None, description="Telefone cadastrado do cliente.")
    email: str | None = Field(default=None, description="E-mail cadastrado do cliente.")


class PedidosDoClienteArgs(BaseModel):
    telefone: str | None = Field(default=None, description="Telefone cadastrado do cliente.")
    email: str | None = Field(default=None, description="E-mail cadastrado do cliente.")


class ConsultarPoliticasArgs(BaseModel):
    pergunta: str = Field(
        description="Dúvida do cliente sobre regras: troca, devolução, garantia, frete, "
        "pagamento, horário, promoções, privacidade, escopo da loja."
    )


class SimularPagamentoArgs(BaseModel):
    valor_total: float = Field(gt=0, description="Valor total da compra em reais.")
    cidade: str | None = Field(default=None, description="Cidade de entrega, se informada.")
    produto_em_promocao: bool = Field(
        default=False, description="True se o valor já é promocional (PIX não desconta)."
    )


class SemArgs(BaseModel):
    pass


# ---- fábrica ----------------------------------------------------------------


def build_tools(repo: Repository, now_fn: Callable[[], datetime] = reference_now) -> list[BaseTool]:
    def buscar_produtos(
        busca: str | None = None,
        categoria: str | None = None,
        preco_min: float | None = None,
        preco_max: float | None = None,
        apenas_disponiveis: bool = True,
        limite: int = 8,
    ) -> str:
        products = repo.search_products(
            query=busca,
            category=categoria,
            min_price=preco_min,
            max_price=preco_max,
            in_stock_only=apenas_disponiveis,
            limit=limite,
        )
        if not products:
            categories = [c.name for c in repo.list_categories()]
            payload: dict[str, Any] = {
                "resultados": [],
                "dica": "Nada encontrado com esses filtros. Tente outra palavra ou "
                "categoria. Categorias do catálogo: " + ", ".join(categories),
            }
            if apenas_disponiveis and busca:
                unavailable = [
                    p
                    for p in repo.search_products(
                        query=busca, category=categoria, min_price=preco_min, max_price=preco_max
                    )
                    if not p.available
                ]
                if unavailable:
                    payload["indisponiveis_no_momento"] = [
                        {"id": p.product_id, "nome": p.name, "situacao": _availability(p)}
                        for p in unavailable[:5]
                    ]
            return _json(payload)
        payload: dict[str, Any] = {"resultados": [_product_payload(repo, p) for p in products]}
        if apenas_disponiveis and busca:
            # Produtos que casam com a busca mas não podem ser vendidos agora: o
            # atendente precisa saber que existem para não dizer "não temos".
            shown = {p.product_id for p in products}
            unavailable = [
                p
                for p in repo.search_products(
                    query=busca, category=categoria, min_price=preco_min, max_price=preco_max
                )
                if not p.available and p.product_id not in shown
            ]
            if unavailable:
                payload["indisponiveis_no_momento"] = [
                    {"id": p.product_id, "nome": p.name, "situacao": _availability(p)}
                    for p in unavailable[:5]
                ]
        return _json(payload)

    def detalhar_produto(produto: str) -> str:
        product = None
        if produto.strip().isdigit():
            product = repo.get_product(int(produto))
        if product is None:
            product = repo.find_product_by_name(produto)
        if product is None:
            return _json({"erro": f"Nenhum produto parecido com '{produto}' no catálogo."})
        return _json(_product_payload(repo, product, detailed=True))

    def listar_promocoes() -> str:
        items = []
        for promo, product in repo.list_active_promotions():
            payload = _product_payload(repo, product)
            payload["promocao"]["nome"] = promo.description
            items.append(payload)
        return _json({"promocoes_ativas": items, "total": len(items)})

    def consultar_pedido(
        numero_pedido: int, telefone: str | None = None, email: str | None = None
    ) -> str:
        ids = _identify(repo, telefone, email)
        if ids is None:
            return _json(
                {
                    "erro": "Identificação necessária. Peça ao cliente o telefone ou e-mail "
                    "cadastrado no pedido antes de consultar (proteção de dados, LGPD)."
                }
            )
        order = repo.get_order(numero_pedido)
        if order is None:
            return _json({"erro": f"Pedido {numero_pedido} não encontrado."})
        if order.customer_id not in ids:
            return _json(
                {
                    "erro": "Os dados informados não conferem com o cadastro deste pedido. "
                    "Não exiba detalhes; peça para conferir telefone/e-mail."
                }
            )
        return _json(_order_payload(repo, order, now_fn()))

    def pedidos_do_cliente(telefone: str | None = None, email: str | None = None) -> str:
        ids = _identify(repo, telefone, email)
        if ids is None:
            return _json({"erro": "Informe telefone ou e-mail cadastrado para localizar pedidos."})
        if not ids:
            return _json({"erro": "Nenhum cliente encontrado com esses dados."})
        result = []
        for cid in ids:
            customer = repo.get_customer(cid)
            orders = repo.orders_for_customer(cid)
            result.append(
                {
                    "cliente": customer.name if customer else cid,
                    "pedidos": [
                        {
                            "numero_pedido": o.order_id,
                            "data": o.order_date,
                            "status": rules.ORDER_STATUS_LABELS.get(o.status, o.status),
                            "total": o.total_brl,
                            "itens": [i.product_name for i in o.items],
                        }
                        for o in orders
                    ],
                }
            )
        return _json({"clientes": result})

    def consultar_politicas(pergunta: str) -> str:
        return format_sections(search_sections(pergunta, k=3))

    def simular_pagamento_e_frete(
        valor_total: float, cidade: str | None = None, produto_em_promocao: bool = False
    ) -> str:
        pix = valor_total if produto_em_promocao else rules.money(valor_total * 0.95)
        options = rules.installment_options(valor_total)
        shipping = rules.shipping_info(valor_total, cidade)
        return _json(
            {
                "valor": valor_total,
                "pix": {
                    "valor": pix,
                    "desconto_aplicado": not produto_em_promocao,
                    "regra": "5% sobre o preço de tabela; não cumula com promoção.",
                },
                "parcelamento_sem_juros": [
                    f"{o.installments}x de R$ {o.amount:.2f}" for o in options if o.installments > 1
                ],
                "combinar_formas_de_pagamento": rules.mixed_payment_allowed(valor_total),
                "boleto": "à vista, compensação em até 3 dias úteis",
                "frete": {
                    "regiao": shipping.region,
                    "valor": shipping.fee,
                    "gratis": shipping.free,
                    "prazo": shipping.deadline,
                    "observacao": shipping.note,
                },
            }
        )

    def info_loja() -> str:
        return _json({**STORE, "horarios": HOURS_TEXT, "agora": status_now(now_fn())})

    return [
        StructuredTool.from_function(
            buscar_produtos,
            name="buscar_produtos",
            description="Busca produtos do catálogo por texto, categoria, faixa de preço e "
            "disponibilidade. Use para 'quais violões até X', 'tem guitarra Fender', etc.",
            args_schema=BuscarProdutosArgs,
        ),
        StructuredTool.from_function(
            detalhar_produto,
            name="detalhar_produto",
            description="Detalhes, preço (tabela, PIX, promoção), parcelamento e estoque de um "
            "produto específico. Se estiver indisponível, traz alternativas.",
            args_schema=DetalharProdutoArgs,
        ),
        StructuredTool.from_function(
            listar_promocoes,
            name="listar_promocoes",
            description="Lista as promoções ativas no sistema com preço original e desconto.",
            args_schema=SemArgs,
        ),
        StructuredTool.from_function(
            consultar_pedido,
            name="consultar_pedido",
            description="Status, rastreio, itens e prazos de troca/devolução de um pedido. "
            "Exige número do pedido e telefone ou e-mail do cliente.",
            args_schema=ConsultarPedidoArgs,
        ),
        StructuredTool.from_function(
            pedidos_do_cliente,
            name="pedidos_do_cliente",
            description="Lista os pedidos de um cliente identificado por telefone ou e-mail. "
            "Use quando o cliente não sabe o número do pedido.",
            args_schema=PedidosDoClienteArgs,
        ),
        StructuredTool.from_function(
            consultar_politicas,
            name="consultar_politicas",
            description="Consulta o manual de políticas da loja: trocas, devoluções, garantia, "
            "frete, formas de pagamento, horários, promoções, privacidade e escopo.",
            args_schema=ConsultarPoliticasArgs,
        ),
        StructuredTool.from_function(
            simular_pagamento_e_frete,
            name="simular_pagamento_e_frete",
            description="Calcula preço no PIX, parcelas sem juros e frete para um valor e cidade.",
            args_schema=SimularPagamentoArgs,
        ),
        StructuredTool.from_function(
            info_loja,
            name="info_loja",
            description="Endereço, telefone, WhatsApp, e-mail, horários e se está aberta agora.",
            args_schema=SemArgs,
        ),
    ]
