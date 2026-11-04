"""Mascaramento de dados pessoais em textos destinados a documentos públicos
(conversas de exemplo, relatórios de avaliação).

Os dados do dataset são fictícios, mas telefone e e-mail de cliente não devem
circular em transcrições publicadas, seguindo a seção 9 do manual (LGPD).
"""

from __future__ import annotations

import re

SENSITIVE_ARGS = {"telefone", "email"}
PHONE_RE = re.compile(r"\(?\d{2}\)?\s?9?\d{4}-?\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def mask_value(value: object) -> str:
    """'(67) 99789-0123' -> '***0123'; 'ana@x.com' -> 'an***@x.com'."""
    text = str(value)
    if "@" in text:
        user, _, domain = text.partition("@")
        return f"{user[:2]}***@{domain}"
    digits = [c for c in text if c.isdigit()]
    return f"***{''.join(digits[-4:])}" if len(digits) >= 4 else "***"


def mask_text(text: str) -> str:
    """Mascara telefones e e-mails dentro de texto livre."""
    text = EMAIL_RE.sub(lambda m: mask_value(m.group(0)), text)
    return PHONE_RE.sub(lambda m: mask_value(m.group(0)), text)


def describe_call(name: str, args: dict) -> str:
    """Representação legível de uma chamada de ferramenta, com dados pessoais mascarados."""
    shown = ", ".join(
        f"{k}={mask_value(v) if k in SENSITIVE_ARGS else v!r}"
        for k, v in args.items()
        if v not in (None, "")
    )
    return f"{name}({shown})"
