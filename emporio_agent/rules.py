"""Regras de negócio do manual de políticas (versão 2.1, junho/2025), em código.

Tudo que envolve aritmética ou prazo fica aqui, determinístico e testável. O modelo
de linguagem só explica o resultado; ele nunca calcula desconto, parcela ou prazo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from emporio_agent.data.repository import Order, Product, Promotion

# --- Seção 3: formas de pagamento -------------------------------------------

PIX_DISCOUNT_PERCENT = 5.0
MAX_INSTALLMENTS = 12
# (parcelas até N, parcela mínima em R$)
INSTALLMENT_TIERS = ((3, 50.0), (6, 80.0), (12, 100.0))
MIXED_PAYMENT_MIN_TOTAL = 2000.0

# --- Seção 4: trocas e devoluções --------------------------------------------

WITHDRAWAL_DAYS = 7  # arrependimento (compra online), dias corridos após recebimento
PREFERENCE_EXCHANGE_DAYS = 7  # troca por cor/modelo, dias após recebimento
DEFECT_EXCHANGE_DAYS = 30  # defeito de fabricação, dias corridos após a compra
LEGAL_WARRANTY_DAYS = 90  # garantia legal (CDC), após recebimento

# --- Seção 5: frete ------------------------------------------------------------

METRO_FREE_SHIPPING_MIN = 500.0
METRO_SHIPPING_FEE = 35.0
METRO_CITIES = {"campo grande"}

# Rótulos em português para status vindos do CSV.
ORDER_STATUS_LABELS = {
    "pending": "pendente (aguardando confirmação de pagamento)",
    "confirmed": "confirmado (em separação)",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PRODUCT_STATUS_LABELS = {
    "active": "ativo",
    "discontinued": "descontinuado",
    "coming_soon": "em breve (ainda não disponível para venda)",
}


def money(value: float) -> float:
    return round(value + 1e-9, 2)


# --- Preço -----------------------------------------------------------------------


@dataclass(frozen=True)
class PriceQuote:
    list_price: float
    promo_percent: float | None
    promo_description: str | None
    promo_price: float | None
    pix_price: float
    pix_discount_applied: bool

    @property
    def best_cash_price(self) -> float:
        """Menor preço à vista. PIX (5%) só se não houver promoção (6.2)."""
        return self.pix_price

    @property
    def card_price(self) -> float:
        """Preço no cartão/boleto: promocional se houver, senão o de tabela."""
        return self.promo_price if self.promo_price is not None else self.list_price


def price_quote(product: Product, promotion: Promotion | None) -> PriceQuote:
    list_price = money(product.price_brl)
    if promotion is not None and promotion.is_active:
        promo_price = money(list_price * (1 - promotion.discount_percent / 100))
        # 6.2 Cumulatividade: PIX não se aplica sobre preço promocional.
        return PriceQuote(
            list_price=list_price,
            promo_percent=promotion.discount_percent,
            promo_description=promotion.description,
            promo_price=promo_price,
            pix_price=promo_price,
            pix_discount_applied=False,
        )
    return PriceQuote(
        list_price=list_price,
        promo_percent=None,
        promo_description=None,
        promo_price=None,
        pix_price=money(list_price * (1 - PIX_DISCOUNT_PERCENT / 100)),
        pix_discount_applied=True,
    )


# --- Parcelamento ----------------------------------------------------------------


@dataclass(frozen=True)
class InstallmentOption:
    installments: int
    amount: float


def installment_options(total: float) -> list[InstallmentOption]:
    """Parcelas sem juros permitidas pela seção 3.1 para um valor."""
    options = []
    for n in range(1, MAX_INSTALLMENTS + 1):
        minimum = next(m for limit, m in INSTALLMENT_TIERS if n <= limit)
        amount = total / n
        if n == 1 or amount >= minimum:
            options.append(InstallmentOption(n, money(amount)))
    return options


def max_installments(total: float) -> int:
    return installment_options(total)[-1].installments


def mixed_payment_allowed(total: float) -> bool:
    return total > MIXED_PAYMENT_MIN_TOTAL


# --- Frete -----------------------------------------------------------------------


@dataclass(frozen=True)
class ShippingInfo:
    region: str  # "metropolitana" | "outras"
    fee: float | None  # None quando depende de cotação
    free: bool
    deadline: str
    note: str


def shipping_info(total: float, city: str | None) -> ShippingInfo:
    if city and city.strip().lower() in METRO_CITIES:
        free = total > METRO_FREE_SHIPPING_MIN
        return ShippingInfo(
            region="metropolitana",
            fee=0.0 if free else METRO_SHIPPING_FEE,
            free=free,
            deadline="1 a 3 dias úteis",
            note=(
                "Entrega por motoboy próprio; o cliente é contactado por telefone antes. "
                f"Frete grátis acima de R$ {METRO_FREE_SHIPPING_MIN:.2f}, "
                f"senão taxa fixa de R$ {METRO_SHIPPING_FEE:.2f}."
            ),
        )
    return ShippingInfo(
        region="outras",
        fee=None,
        free=False,
        deadline="PAC 5 a 12 dias úteis; SEDEX 2 a 5; Jadlog 3 a 8",
        note=(
            "Valor calculado por CEP, peso e dimensões (Correios ou Jadlog), com seguro "
            "incluído. Instrumentos de grande porte podem exigir cotação individual."
        ),
    )


# --- Prazos de troca/devolução -------------------------------------------------


@dataclass(frozen=True)
class ReturnWindow:
    name: str
    deadline: date
    days_left: int
    open: bool
    basis: str


@dataclass(frozen=True)
class ReturnAssessment:
    order_status: str
    received_on: date | None
    reference_date: date
    windows: tuple[ReturnWindow, ...]
    note: str


def _parse(d: str | None) -> date | None:
    return date.fromisoformat(d) if d else None


def return_assessment(order: Order, today: date) -> ReturnAssessment:
    """Avalia os prazos da seção 4 e 8 para um pedido na data de referência.

    Suposição documentada: o dataset não tem data de recebimento. Para pedidos
    entregues usamos `estimated_delivery` como data de recebimento.
    """
    purchased = _parse(order.order_date)
    received = _parse(order.estimated_delivery) if order.status == "delivered" else None

    if order.status == "cancelled":
        return ReturnAssessment(
            order.status, None, today, (), "Pedido cancelado; não há o que devolver."
        )
    if order.status != "delivered" or received is None or purchased is None:
        return ReturnAssessment(
            order.status,
            None,
            today,
            (),
            "Pedido ainda não entregue. Devolução/troca só após o recebimento; "
            "para cancelar antes do envio, a equipe da loja deve ser acionada.",
        )

    def window(name: str, start: date, days: int, basis: str) -> ReturnWindow:
        deadline = start + timedelta(days=days)
        left = (deadline - today).days
        return ReturnWindow(name, deadline, left, left >= 0, basis)

    windows = (
        window("arrependimento", received, WITHDRAWAL_DAYS, "7 dias corridos após o recebimento"),
        window(
            "troca por preferência", received, PREFERENCE_EXCHANGE_DAYS, "7 dias após o recebimento"
        ),
        window(
            "troca por defeito", purchased, DEFECT_EXCHANGE_DAYS, "30 dias corridos após a compra"
        ),
        window("garantia legal", received, LEGAL_WARRANTY_DAYS, "90 dias após o recebimento"),
    )
    return ReturnAssessment(
        order.status,
        received,
        today,
        windows,
        "Data de recebimento assumida como a previsão de entrega registrada no pedido.",
    )
