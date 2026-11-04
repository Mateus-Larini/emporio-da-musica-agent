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

# Provedores suportados e modelo padrão de cada um.
# Ordem de tentativa por provedor. Se o primeiro falhar por cota, indisponibilidade
# ou nome inválido, o agente passa ao seguinte. No Groq cada modelo tem cota
# diária própria, então a cadeia estende o uso gratuito.
DEFAULT_MODELS = {
    "anthropic": ["claude-haiku-5-5"],
    "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
    "google": ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
}


def provider() -> str:
    """ "anthropic", "groq" ou "google". Sem EMPORIO_PROVIDER, deduz pela chave presente."""
    explicit = os.environ.get("EMPORIO_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GOOGLE_API_KEY"):
        return "google"
    return "anthropic"


def model_names() -> list[str]:
    """Modelos a tentar, em ordem.

    EMPORIO_MODEL define o principal; EMPORIO_MODEL_FALLBACKS (separados por
    vírgula) os seguintes. Sem as variáveis, usa a cadeia padrão do provedor.
    """
    primary = os.environ.get("EMPORIO_MODEL", "").strip()
    fallbacks = [m.strip() for m in os.environ.get("EMPORIO_MODEL_FALLBACKS", "").split(",")]
    fallbacks = [m for m in fallbacks if m]
    if primary or fallbacks:
        chain = ([primary] if primary else []) + fallbacks
    else:
        chain = list(DEFAULT_MODELS.get(provider(), []))
    seen: list[str] = []
    for name in chain:
        if name not in seen:
            seen.append(name)
    return seen


def model_name() -> str:
    """Modelo principal (primeiro da cadeia)."""
    names = model_names()
    return names[0] if names else ""


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
