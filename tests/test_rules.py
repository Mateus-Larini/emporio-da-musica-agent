from __future__ import annotations

from datetime import date

import pytest

from emporio_agent.data.repository import Order, Product, Promotion
from emporio_agent.rules import (
    installment_options,
    max_installments,
    mixed_payment_allowed,
    price_quote,
    return_assessment,
    shipping_info,
)


def product(price: float) -> Product:
    return Product(1, "Teste", 5, "Violões", price, None, 1, "active")


def promo(percent: float, active: bool = True) -> Promotion:
    return Promotion(1, 1, percent, "Oferta", active)


def order(status: str, order_date: str, delivery: str | None) -> Order:
    return Order(1, 1, order_date, status, 100.0, "pix", None, delivery, None)


# --- preço ---------------------------------------------------------------------


def test_pix_discount_without_promotion():
    q = price_quote(product(1000.0), None)
    assert q.list_price == 1000.0
    assert q.promo_price is None
    assert q.pix_price == 950.0 and q.pix_discount_applied
    assert q.card_price == 1000.0


def test_pix_does_not_stack_with_promotion():
    q = price_quote(product(2199.0), promo(10))
    assert q.promo_price == 1979.1
    assert q.pix_price == 1979.1 and not q.pix_discount_applied
    assert q.card_price == 1979.1


def test_inactive_promotion_is_ignored():
    q = price_quote(product(100.0), promo(50, active=False))
    assert q.promo_price is None and q.pix_price == 95.0


# --- parcelamento -------------------------------------------------------------


@pytest.mark.parametrize(
    "total, expected_max",
    [
        (40.0, 1),  # abaixo de R$ 50: só à vista
        (100.0, 2),  # 3x = 33,33 < 50
        (150.0, 3),
        (240.0, 3),  # 4x = 60 < 80
        (320.0, 4),
        (480.0, 6),
        (560.0, 6),  # 7x = 80 < 100; 6x = 93,33 >= 80
        (700.0, 7),
        (1200.0, 12),
        (2199.0, 12),
    ],
)
def test_max_installments(total: float, expected_max: int):
    assert max_installments(total) == expected_max


def test_installment_amounts():
    options = installment_options(1200.0)
    assert options[0].installments == 1 and options[0].amount == 1200.0
    assert options[-1].installments == 12 and options[-1].amount == 100.0
    assert all(o.amount >= 100 for o in options if o.installments >= 7)


def test_mixed_payment_threshold():
    assert not mixed_payment_allowed(2000.0)
    assert mixed_payment_allowed(2000.01)


# --- frete ------------------------------------------------------------------------


def test_shipping_metro_region():
    assert shipping_info(499.9, "Campo Grande").fee == 35.0
    assert shipping_info(500.0, "campo grande").fee == 35.0  # "acima de 500" é estrito
    s = shipping_info(500.01, "Campo Grande")
    assert s.free and s.fee == 0.0 and s.region == "metropolitana"


def test_shipping_other_cities_needs_quote():
    s = shipping_info(5000.0, "Dourados")
    assert s.region == "outras" and s.fee is None and not s.free
    assert shipping_info(100.0, None).region == "outras"


# --- prazos ---------------------------------------------------------------------


def test_return_windows_for_delivered_order():
    o = order("delivered", "2026-03-01", "2026-03-10")
    a = return_assessment(o, today=date(2026, 3, 15))
    by_name = {w.name: w for w in a.windows}
    assert a.received_on == date(2026, 3, 10)
    assert by_name["arrependimento"].open and by_name["arrependimento"].days_left == 2
    assert by_name["troca por defeito"].open  # 30 dias desde 01/03
    assert by_name["garantia legal"].deadline == date(2026, 6, 8)


def test_return_windows_closed():
    o = order("delivered", "2025-10-15", "2025-10-25")
    a = return_assessment(o, today=date(2026, 3, 15))
    assert not any(w.open for w in a.windows)


def test_not_delivered_or_cancelled_has_no_windows():
    assert (
        return_assessment(order("shipped", "2026-02-15", "2026-02-28"), date(2026, 3, 1)).windows
        == ()
    )
    assert (
        "cancelado"
        in return_assessment(order("cancelled", "2026-01-28", None), date(2026, 3, 1)).note
    )
