from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from emporio_agent.config import CSV_FILES
from emporio_agent.data.loader import build_database
from emporio_agent.data.text import normalize, stem, tokens


def test_counts_match_csvs(db_path: Path):
    conn = sqlite3.connect(db_path)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("categories", "products", "customers", "orders", "order_items", "promotions")
    }
    conn.close()
    assert counts == {
        "categories": 9,
        "products": 65,
        "customers": 50,
        "orders": 20,
        "order_items": 22,
        "promotions": 25,
    }


def test_specs_are_valid_json_and_search_text_normalized(db_path: Path):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT specs, search_text FROM products WHERE product_id = 81").fetchone()
    conn.close()
    assert '"strings": "nylon"' in row[0]
    assert "violao" in row[1] and "classico" in row[1]


def test_build_is_atomic_on_bad_data(tmp_path: Path):
    bad_items = tmp_path / "order_items.csv"
    bad_items.write_text("order_id,quantity,product_id\n1,1,99999\n", encoding="utf-8")
    files = dict(CSV_FILES, order_items=bad_items)
    target = tmp_path / "emporio.db"
    with pytest.raises(ValueError, match="item com produto inexistente"):
        build_database(target, files)
    assert not target.exists()


def test_normalize_and_stem():
    assert normalize("Violões Clássicos, Ñ!") == "violoes classicos n"
    assert stem("violoes") == "violao"
    assert stem("guitarras") == "guitarra"
    assert stem("baixos") == "baixo"
    assert tokens("Violões até R$1000") == ["violao", "ate", "r", "1000"]
