"""Normalização de texto para busca tolerante a acentos e plural."""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, sem pontuação, espaços únicos."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def stem(token: str) -> str:
    """Stemmer mínimo para português: reduz plurais comuns.

    violoes -> violao, guitarras -> guitarra, baixos -> baixo, ukuleles -> ukulele.
    """
    if len(token) <= 3:
        return token
    if token.endswith("oes"):
        return token[:-3] + "ao"
    if token.endswith("aes"):
        return token[:-3] + "ao"
    if token.endswith("ais"):
        return token[:-3] + "al"
    if token.endswith("s"):
        return token[:-1]
    return token


def tokens(text: str) -> list[str]:
    return [stem(t) for t in normalize(text).split()]
