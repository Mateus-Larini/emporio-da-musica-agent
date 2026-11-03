"""Carrega os CSVs da loja em um banco SQLite local.

O banco é um artefato derivado: pode ser apagado e reconstruído a qualquer momento
a partir dos CSVs em data/. Executar `python -m emporio_agent.data.loader` recria.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from emporio_agent.config import CSV_FILES, DB_PATH
from emporio_agent.data.text import tokens

SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE products (
    product_id     INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    category_id    INTEGER NOT NULL REFERENCES categories(category_id),
    price_brl      REAL NOT NULL,
    description    TEXT,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL,
    specs          TEXT,            -- JSON
    created_at     TEXT,
    search_text    TEXT NOT NULL    -- nome + categoria + descrição normalizados
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    city        TEXT,
    phone_digits TEXT,              -- só dígitos, para busca
    email_norm   TEXT               -- minúsculo, para busca
);

CREATE TABLE orders (
    order_id           INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date         TEXT NOT NULL,
    status             TEXT NOT NULL,
    total_brl          REAL NOT NULL,
    payment_method     TEXT,
    tracking_code      TEXT,
    estimated_delivery TEXT,
    notes              TEXT
);

CREATE TABLE order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity   INTEGER NOT NULL
);

CREATE TABLE promotions (
    promotion_id     INTEGER PRIMARY KEY,
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent REAL NOT NULL,
    description      TEXT,
    is_active        INTEGER NOT NULL
);

CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_promotions_product ON promotions(product_id, is_active);
"""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def build_database(db_path: Path = DB_PATH, csv_files: dict[str, Path] = CSV_FILES) -> Path:
    """(Re)cria o banco a partir dos CSVs. Escreve em arquivo temporário e troca
    atomicamente, para nunca deixar um banco pela metade."""
    tmp_path = db_path.with_suffix(".tmp.db")
    tmp_path.unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(SCHEMA)
        _load_categories(conn, _read_csv(csv_files["categories"]))
        _load_products(conn, _read_csv(csv_files["products"]))
        _load_customers(conn, _read_csv(csv_files["customers"]))
        _load_orders(conn, _read_csv(csv_files["orders"]))
        _load_order_items(conn, _read_csv(csv_files["order_items"]))
        _load_promotions(conn, _read_csv(csv_files["promotions"]))
        _validate(conn)
        conn.commit()
    finally:
        conn.close()

    tmp_path.replace(db_path)
    return db_path


def _load_categories(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    conn.executemany(
        "INSERT INTO categories VALUES (?, ?, ?)",
        [
            (int(r["category_id"]), r["name"].strip(), _blank_to_none(r["description"]))
            for r in rows
        ],
    )


def _load_products(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    categories = dict(conn.execute("SELECT category_id, name FROM categories"))
    data = []
    for r in rows:
        category_id = int(r["category_id"])
        specs_raw = _blank_to_none(r.get("specs"))
        specs = json.dumps(json.loads(specs_raw), ensure_ascii=False) if specs_raw else None
        search_text = " ".join(
            tokens(f"{r['name']} {categories.get(category_id, '')} {r.get('description', '')}")
        )
        data.append(
            (
                int(r["product_id"]),
                r["name"].strip(),
                category_id,
                float(r["price_brl"]),
                _blank_to_none(r.get("description")),
                int(r["stock_quantity"] or 0),
                r["status"].strip().lower(),
                specs,
                _blank_to_none(r.get("created_at")),
                search_text,
            )
        )
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)", data)


def _load_customers(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    data = []
    for r in rows:
        phone = _blank_to_none(r.get("phone"))
        email = _blank_to_none(r.get("email"))
        data.append(
            (
                int(r["customer_id"]),
                r["name"].strip(),
                phone,
                email,
                _blank_to_none(r.get("city")),
                "".join(ch for ch in phone if ch.isdigit()) if phone else None,
                email.lower() if email else None,
            )
        )
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", data)


def _load_orders(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                int(r["order_id"]),
                int(r["customer_id"]),
                r["order_date"].strip(),
                r["status"].strip().lower(),
                float(r["total_brl"]),
                _blank_to_none(r.get("payment_method")),
                _blank_to_none(r.get("tracking_code")),
                _blank_to_none(r.get("estimated_delivery")),
                _blank_to_none(r.get("notes")),
            )
            for r in rows
        ],
    )


def _load_order_items(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    conn.executemany(
        "INSERT INTO order_items VALUES (?,?,?)",
        [(int(r["order_id"]), int(r["product_id"]), int(r["quantity"])) for r in rows],
    )


def _load_promotions(conn: sqlite3.Connection, rows: list[dict[str, str]]) -> None:
    conn.executemany(
        "INSERT INTO promotions VALUES (?,?,?,?,?)",
        [
            (
                int(r["promotion_id"]),
                int(r["product_id"]),
                float(r["discount_percent"]),
                _blank_to_none(r.get("description")),
                1 if r["is_active"].strip() in ("1", "true", "True") else 0,
            )
            for r in rows
        ],
    )


def _validate(conn: sqlite3.Connection) -> None:
    """Checagens de integridade referencial. Falha alto em vez de carregar lixo."""
    checks = {
        "produto com categoria inexistente": """
            SELECT COUNT(*) FROM products p
            LEFT JOIN categories c ON c.category_id = p.category_id
            WHERE c.category_id IS NULL""",
        "pedido com cliente inexistente": """
            SELECT COUNT(*) FROM orders o
            LEFT JOIN customers c ON c.customer_id = o.customer_id
            WHERE c.customer_id IS NULL""",
        "item com pedido inexistente": """
            SELECT COUNT(*) FROM order_items i
            LEFT JOIN orders o ON o.order_id = i.order_id
            WHERE o.order_id IS NULL""",
        "item com produto inexistente": """
            SELECT COUNT(*) FROM order_items i
            LEFT JOIN products p ON p.product_id = i.product_id
            WHERE p.product_id IS NULL""",
        "promoção com produto inexistente": """
            SELECT COUNT(*) FROM promotions pr
            LEFT JOIN products p ON p.product_id = pr.product_id
            WHERE p.product_id IS NULL""",
    }
    problems = [name for name, sql in checks.items() if conn.execute(sql).fetchone()[0]]
    if problems:
        raise ValueError("Dados inconsistentes: " + "; ".join(problems))


def ensure_database(db_path: Path = DB_PATH) -> Path:
    """Garante que o banco existe (constrói na primeira execução)."""
    if not db_path.exists():
        build_database(db_path)
    return db_path


if __name__ == "__main__":
    path = build_database()
    conn = sqlite3.connect(path)
    for table in ("categories", "products", "customers", "orders", "order_items", "promotions"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table:12s} {count:4d} linhas")
    conn.close()
    print(f"Banco criado em {path}")
