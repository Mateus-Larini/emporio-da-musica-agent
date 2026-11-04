"""Configuração central: caminhos, modelo e data de referência."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
DB_PATH = Path(os.environ.get("EMPORIO_DB_PATH", DATA_DIR / "emporio.db"))
POLICIES_PDF = DATA_DIR / "politicas_da_loja.pdf"
SESSIONS_DIR = Path(os.environ.get("EMPORIO_SESSIONS_DIR", ROOT_DIR / "sessions"))

CSV_FILES = {
    "categories": DATA_DIR / "categories.csv",
    "products": DATA_DIR / "products.csv",
    "customers": DATA_DIR / "customers.csv",
    "orders": DATA_DIR / "orders.csv",
    "order_items": DATA_DIR / "order_items.csv",
    "promotions": DATA_DIR / "promotions.csv",
}

DEFAULT_MODEL = "claude-haiku-5-5"


def model_name() -> str:
    return os.environ.get("EMPORIO_MODEL", DEFAULT_MODEL)


def reference_date() -> date:
    """Data "de hoje" usada para calcular prazos (arrependimento, garantia etc.).

    Os pedidos do dataset vão até março de 2026. Para que os cenários de prazo
    façam sentido independentemente de quando o projeto é executado, a data pode
    ser fixada via EMPORIO_REFERENCE_DATE (YYYY-MM-DD). Sem a variável, usa hoje.
    """
    raw = os.environ.get("EMPORIO_REFERENCE_DATE")
    if raw:
        return date.fromisoformat(raw)
    return date.today()


def reference_now() -> datetime:
    """Data de referência combinada com a hora atual do relógio."""
    return datetime.combine(reference_date(), datetime.now().time())
