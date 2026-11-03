from __future__ import annotations

from emporio_agent.data.repository import Repository


def test_search_violoes_until_1000(repo: Repository):
    results = repo.search_products(query="violão", max_price=1000, in_stock_only=True, limit=50)
    assert results, "deveria haver violões até R$ 1000"
    # Termo de categoria prioriza violões; ukulele cuja descrição cita "violão" vem depois
    assert all(p.category_name == "Violões" for p in results[:10])
    assert all(p.price_brl <= 1000 and p.available for p in results)
    # Giannini GF-3D (id 96) custa 799,90 mas está sem estoque
    assert all(p.product_id != 96 for p in results)


def test_search_by_category_filter_matches_plural_and_accents(repo: Repository):
    assert repo.find_category("guitarra").name == "Guitarras"
    assert repo.find_category("Violoes").name == "Violões"
    assert repo.find_category("ukulele").name == "Ukuleles"
    assert repo.find_category("teclado").name == "Teclados e Pianos"
    assert repo.find_category("pedais") is None


def test_find_product_by_name(repo: Repository):
    p = repo.find_product_by_name("Takamine GD20")
    assert p is not None and p.product_id == 95 and p.price_brl == 2199
    assert repo.find_product_by_name("stratocaster").product_id == 145
    assert repo.find_product_by_name("xyz inexistente") is None


def test_search_price_ordering_and_limit(repo: Repository):
    results = repo.search_products(category="ukulele", limit=3)
    assert len(results) == 3
    assert [p.price_brl for p in results] == sorted(p.price_brl for p in results)


def test_similar_products_excludes_unavailable_and_self(repo: Repository):
    out_of_stock = repo.get_product(96)
    assert not out_of_stock.available
    alternatives = repo.similar_products(out_of_stock)
    assert alternatives and all(a.available and a.product_id != 96 for a in alternatives)
    assert all(a.category_id == out_of_stock.category_id for a in alternatives)


def test_promotions(repo: Repository):
    active = repo.list_active_promotions()
    assert {promo.product_id for promo, _ in active} == {127, 121, 90, 94}
    assert repo.active_promotion(102) is None  # Black Friday inativa
    assert repo.active_promotion(94).discount_percent == 8


def test_find_customer_by_phone_formats(repo: Repository):
    for phone in ("(67) 99812-3456", "67998123456", "99812-3456", "+55 67 99812 3456"):
        found = repo.find_customers(phone=phone)
        assert [c.customer_id for c in found] == [1], phone


def test_find_customer_by_email_and_name(repo: Repository):
    assert repo.find_customers(email="LUCAS.MENDES@jmail.com")[0].customer_id == 1
    by_name = repo.find_customers(name="ana carolina")
    assert any(c.customer_id == 2 for c in by_name)
    assert repo.find_customers() == []


def test_order_with_items(repo: Repository):
    order = repo.get_order(1)
    assert order.status == "delivered" and order.customer_id == 3
    assert order.tracking_code == "BRAB1234567BR"
    assert [i.product_name for i in order.items] == ["Martin D-28 Dreadnought Natural"]
    assert repo.get_order(999) is None


def test_orders_for_customer_sorted_desc(repo: Repository):
    orders = repo.orders_for_customer(3)
    assert [o.order_id for o in orders] == [19, 1]
