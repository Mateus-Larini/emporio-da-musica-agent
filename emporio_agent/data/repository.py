"""Consultas tipadas sobre o SQLite. Esta é a única porta de acesso aos dados:
o modelo nunca escreve SQL, só chama estas funções com argumentos validados."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from emporio_agent.config import DB_PATH
from emporio_agent.data.loader import ensure_database
from emporio_agent.data.text import normalize, tokens


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str | None


@dataclass(frozen=True)
class Product:
    product_id: int
    name: str
    category_id: int
    category_name: str
    price_brl: float
    description: str | None
    stock_quantity: int
    status: str  # active | discontinued | coming_soon
    specs: dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: float
    description: str | None
    is_active: bool


@dataclass(frozen=True)
class Customer:
    customer_id: int
    name: str
    phone: str | None
    email: str | None
    city: str | None


@dataclass(frozen=True)
class OrderItem:
    product_id: int
    product_name: str
    quantity: int
    unit_price_brl: float


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    order_date: str
    status: str  # pending | confirmed | shipped | delivered | cancelled
    total_brl: float
    payment_method: str | None
    tracking_code: str | None
    estimated_delivery: str | None
    notes: str | None
    items: tuple[OrderItem, ...] = ()


class Repository:
    def __init__(self, db_path: Path = DB_PATH):
        ensure_database(db_path)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    # ---- categorias -------------------------------------------------------

    def list_categories(self) -> list[Category]:
        rows = self._conn.execute("SELECT * FROM categories ORDER BY category_id").fetchall()
        return [Category(r["category_id"], r["name"], r["description"]) for r in rows]

    def find_category(self, name: str) -> Category | None:
        wanted = tokens(name)
        for cat in self.list_categories():
            cat_tokens = tokens(cat.name)
            if all(any(ct.startswith(w) for ct in cat_tokens) for w in wanted):
                return cat
        return None

    # ---- produtos ---------------------------------------------------------

    _PRODUCT_SQL = """
        SELECT p.*, c.name AS category_name
        FROM products p JOIN categories c ON c.category_id = p.category_id
    """

    def _row_to_product(self, r: sqlite3.Row) -> Product:
        return Product(
            product_id=r["product_id"],
            name=r["name"],
            category_id=r["category_id"],
            category_name=r["category_name"],
            price_brl=r["price_brl"],
            description=r["description"],
            stock_quantity=r["stock_quantity"],
            status=r["status"],
            specs=json.loads(r["specs"]) if r["specs"] else {},
        )

    def get_product(self, product_id: int) -> Product | None:
        r = self._conn.execute(
            self._PRODUCT_SQL + " WHERE p.product_id = ?", (product_id,)
        ).fetchone()
        return self._row_to_product(r) if r else None

    def search_products(
        self,
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        in_stock_only: bool = False,
        limit: int = 10,
    ) -> list[Product]:
        """Busca por texto livre e/ou filtros. Ranking: quantidade de termos do
        texto encontrados no produto (nome pesa mais), depois preço crescente."""
        where: list[str] = []
        params: list[object] = []

        if category:
            cat = self.find_category(category)
            if cat is None:
                return []
            where.append("p.category_id = ?")
            params.append(cat.category_id)
        if min_price is not None:
            where.append("p.price_brl >= ?")
            params.append(min_price)
        if max_price is not None:
            where.append("p.price_brl <= ?")
            params.append(max_price)
        if in_stock_only:
            where.append("p.status = 'active' AND p.stock_quantity > 0")

        sql = self._PRODUCT_SQL
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self._conn.execute(sql, params).fetchall()

        terms = tokens(query) if query else []
        # Termos da busca que nomeiam uma categoria ("violão", "guitarra") dão
        # bônus aos produtos dessa categoria, acima de menções na descrição.
        category_bonus = {
            cat.category_id: 3
            for cat in self.list_categories()
            if any(t in terms for t in tokens(cat.name) if len(t) > 3)
        }
        scored: list[tuple[float, Product]] = []
        for r in rows:
            if terms:
                name_norm = " ".join(tokens(r["name"]))
                in_name = sum(1 for t in terms if t in name_norm)
                in_text = sum(1 for t in terms if t in r["search_text"])
                if in_text == 0:
                    continue
                score = in_name * 2 + in_text + category_bonus.get(r["category_id"], 0)
            else:
                score = 0
            scored.append((score, self._row_to_product(r)))

        scored.sort(key=lambda s: (-s[0], s[1].price_brl))
        return [p for _, p in scored[:limit]]

    def find_product_by_name(self, name: str) -> Product | None:
        """Melhor correspondência para um nome citado pelo cliente (ex.: "Takamine GD20").

        1) todos os termos no nome; 2) melhor resultado da busca textual;
        3) similaridade de caracteres, para erros de digitação ("Takamini GD-20").
        """
        terms = tokens(name)
        if not terms:
            return None
        candidates = self.search_products(query=name, limit=5)
        for p in candidates:
            name_norm = " ".join(tokens(p.name))
            if all(t in name_norm for t in terms):
                return p
        if candidates:
            return candidates[0]
        return self._fuzzy_product(" ".join(terms))

    def _fuzzy_product(self, query_norm: str, threshold: float = 0.6) -> Product | None:
        rows = self._conn.execute(self._PRODUCT_SQL).fetchall()
        best: tuple[float, sqlite3.Row] | None = None
        for r in rows:
            name_norm = " ".join(tokens(r["name"]))
            # compara contra o prefixo do nome com o mesmo tamanho da busca,
            # para "takamini gd 20" casar com "takamine gd20 dreadnought natural"
            ratio = SequenceMatcher(None, query_norm, name_norm[: len(query_norm) + 4]).ratio()
            if ratio >= threshold and (best is None or ratio > best[0]):
                best = (ratio, r)
        return self._row_to_product(best[1]) if best else None

    def similar_products(self, product: Product, limit: int = 3) -> list[Product]:
        """Alternativas disponíveis da mesma categoria, mais próximas em preço."""
        rows = self._conn.execute(
            self._PRODUCT_SQL
            + """ WHERE p.category_id = ? AND p.product_id != ?
                  AND p.status = 'active' AND p.stock_quantity > 0
                  ORDER BY ABS(p.price_brl - ?) LIMIT ?""",
            (product.category_id, product.product_id, product.price_brl, limit),
        ).fetchall()
        return [self._row_to_product(r) for r in rows]

    # ---- promoções --------------------------------------------------------

    def active_promotion(self, product_id: int) -> Promotion | None:
        r = self._conn.execute(
            """SELECT * FROM promotions WHERE product_id = ? AND is_active = 1
               ORDER BY discount_percent DESC LIMIT 1""",
            (product_id,),
        ).fetchone()
        return self._row_to_promotion(r) if r else None

    def list_active_promotions(self) -> list[tuple[Promotion, Product]]:
        rows = self._conn.execute(
            "SELECT * FROM promotions WHERE is_active = 1 ORDER BY discount_percent DESC"
        ).fetchall()
        result = []
        for r in rows:
            product = self.get_product(r["product_id"])
            if product is not None:
                result.append((self._row_to_promotion(r), product))
        return result

    @staticmethod
    def _row_to_promotion(r: sqlite3.Row) -> Promotion:
        return Promotion(
            promotion_id=r["promotion_id"],
            product_id=r["product_id"],
            discount_percent=r["discount_percent"],
            description=r["description"],
            is_active=bool(r["is_active"]),
        )

    # ---- clientes ---------------------------------------------------------

    def find_customers(
        self, phone: str | None = None, email: str | None = None, name: str | None = None
    ) -> list[Customer]:
        """Localiza clientes por telefone (só dígitos), e-mail (exato) ou nome (parcial)."""
        where: list[str] = []
        params: list[object] = []
        if phone:
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) < 8:
                return []  # curto demais para identificar alguém com segurança
            # Aceita com ou sem DDD/código do país: compara os 8 dígitos finais.
            where.append("phone_digits LIKE ?")
            params.append(f"%{digits[-8:]}")
        if email:
            where.append("email_norm = ?")
            params.append(email.strip().lower())
        if name:
            for t in normalize(name).split():
                where.append("LOWER(name) LIKE ?")
                params.append(f"%{t}%")
        if not where:
            return []
        rows = self._conn.execute(
            "SELECT * FROM customers WHERE " + " AND ".join(where) + " ORDER BY customer_id",
            params,
        ).fetchall()
        return [
            Customer(r["customer_id"], r["name"], r["phone"], r["email"], r["city"]) for r in rows
        ]

    def get_customer(self, customer_id: int) -> Customer | None:
        r = self._conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        return (
            Customer(r["customer_id"], r["name"], r["phone"], r["email"], r["city"]) if r else None
        )

    # ---- pedidos ----------------------------------------------------------

    def get_order(self, order_id: int) -> Order | None:
        r = self._conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return self._row_to_order(r) if r else None

    def orders_for_customer(self, customer_id: int) -> list[Order]:
        rows = self._conn.execute(
            "SELECT * FROM orders WHERE customer_id = ? ORDER BY order_date DESC", (customer_id,)
        ).fetchall()
        return [self._row_to_order(r) for r in rows]

    def _row_to_order(self, r: sqlite3.Row) -> Order:
        item_rows = self._conn.execute(
            """SELECT i.product_id, i.quantity, p.name, p.price_brl
               FROM order_items i JOIN products p ON p.product_id = i.product_id
               WHERE i.order_id = ?""",
            (r["order_id"],),
        ).fetchall()
        items = tuple(
            OrderItem(i["product_id"], i["name"], i["quantity"], i["price_brl"]) for i in item_rows
        )
        return Order(
            order_id=r["order_id"],
            customer_id=r["customer_id"],
            order_date=r["order_date"],
            status=r["status"],
            total_brl=r["total_brl"],
            payment_method=r["payment_method"],
            tracking_code=r["tracking_code"],
            estimated_delivery=r["estimated_delivery"],
            notes=r["notes"],
            items=items,
        )
