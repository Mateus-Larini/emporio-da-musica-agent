"""Manual de políticas: extração do PDF por seção e busca lexical.

O manual tem 8 páginas e seções numeradas (1, 1.1, 1.2, 2, ...). Cada seção vira
um "chunk" com título e texto. A busca é lexical (sobreposição de termos
normalizados + mapa de sinônimos para o vocabulário do cliente). Para um documento
desse tamanho isso é suficiente, auditável e não exige serviço de embeddings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

from emporio_agent.config import POLICIES_PDF
from emporio_agent.data.text import tokens

HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d)?)\.?\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{2,80})$")
NOISE_PREFIXES = ("Página ", "Empório da Música Manual de Políticas")


@dataclass(frozen=True)
class Section:
    number: str
    title: str
    text: str

    @property
    def heading(self) -> str:
        return f"{self.number} {self.title}"


# Termos (já normalizados/stemizados) que o cliente usa -> seções relevantes.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "devolver": ("4.1",),
    "devolucao": ("4.1",),
    "arrependimento": ("4.1",),
    "arrependi": ("4.1",),
    "reembolso": ("4.1",),
    "cancelar": ("4.1",),
    "troca": ("4", "4.2", "4.3", "4.4"),
    "trocar": ("4", "4.2", "4.3", "4.4"),
    "defeito": ("4.2", "8.1"),
    "quebrou": ("4.2", "8.3"),
    "garantia": ("8", "8.1", "8.2", "8.3"),
    "frete": ("5", "5.1", "5.2"),
    "entrega": ("5", "5.1", "5.2"),
    "entregar": ("5.1", "5.2"),
    "envio": ("5.2", "5.3"),
    "enviar": ("5.2",),
    "prazo": ("5.1", "5.2"),
    "rastreio": ("5.3",),
    "rastreamento": ("5.3",),
    "rastrear": ("5.3",),
    "correio": ("5.2", "5.3"),
    "sedex": ("5.2",),
    "pagamento": ("3", "3.1"),
    "pagar": ("3", "3.1"),
    "pix": ("3", "6.2"),
    "parcela": ("3.1",),
    "parcelar": ("3.1",),
    "parcelamento": ("3.1",),
    "cartao": ("3", "3.1"),
    "credito": ("3", "3.1"),
    "boleto": ("3",),
    "juro": ("3", "3.1"),
    "desconto": ("3", "6", "6.2"),
    "horario": ("2",),
    "hora": ("2",),
    "aberto": ("2",),
    "abre": ("2",),
    "fecha": ("2",),
    "fechado": ("2",),
    "funcionamento": ("2",),
    "domingo": ("2",),
    "sabado": ("2",),
    "feriado": ("2",),
    "endereco": ("1.2",),
    "onde": ("1.2",),
    "fica": ("1.2",),
    "telefone": ("1.2", "7"),
    "whatsapp": ("1.2", "7"),
    "email": ("1.2",),
    "contato": ("1.2", "7"),
    "cnpj": ("1.2",),
    "promocao": ("6", "6.1", "6.2"),
    "oferta": ("6", "6.2"),
    "black": ("6.1",),
    "friday": ("6.1",),
    "aniversario": ("6.1",),
    "privacidade": ("9",),
    "lgpd": ("9",),
    "dado": ("9",),
    "excluir": ("9",),
    "reclamacao": ("7.3",),
    "reclamar": ("7.3",),
    "estoque": ("7.3", "6.2"),
    "esgotado": ("7.3", "6.2"),
    "descontinuado": ("7.3",),
    "acessorio": ("1", "7.1"),
    "corda": ("1", "7.1"),
    "pedal": ("1", "7.1"),
    "amplificador": ("1", "7.1"),
    "cabo": ("1", "7.1"),
    "palheta": ("1", "7.1"),
    "case": ("1", "7.1"),
    "boquilha": ("4.4",),
    "personalizado": ("4.4",),
    "setup": ("4.4",),
    "loja": ("1",),
    "sobre": ("1", "1.1"),
    "missao": ("1.1",),
}


def extract_text(pdf_path: Path = POLICIES_PDF) -> str:
    reader = PdfReader(pdf_path)
    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    return "\n".join(pages)


def _clean_lines(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        line = " ".join(line.split())
        if not line or line.startswith(NOISE_PREFIXES):
            continue
        lines.append(line)
    return lines


def parse_sections(raw: str) -> list[Section]:
    """Divide o texto em seções a partir dos títulos numerados."""
    sections: list[Section] = []
    current: tuple[str, str] | None = None
    body: list[str] = []

    def flush() -> None:
        if current is not None:
            sections.append(Section(current[0], current[1], "\n".join(body).strip()))

    for line in _clean_lines(raw):
        match = HEADING_RE.match(line)
        if match:
            flush()
            current = (match.group(1), match.group(2).strip())
            body = []
        elif current is not None:
            body.append(line)
    flush()
    return sections


@lru_cache(maxsize=1)
def load_sections(pdf_path: Path = POLICIES_PDF) -> tuple[Section, ...]:
    return tuple(parse_sections(extract_text(pdf_path)))


def search_sections(question: str, k: int = 3) -> list[Section]:
    """Seções mais relevantes para a pergunta, por sinônimos + sobreposição de termos."""
    terms = tokens(question)
    if not terms:
        return []
    sections = load_sections()
    scored: list[tuple[float, int, Section]] = []
    for index, section in enumerate(sections):
        synonym_hits = sum(3 for t in terms if section.number in SYNONYMS.get(t, ()))
        section_terms = set(tokens(section.heading + " " + section.text))
        title_terms = set(tokens(section.title))
        overlap = sum(1 for t in terms if len(t) > 2 and t in section_terms)
        title_overlap = sum(2 for t in terms if len(t) > 2 and t in title_terms)
        score = synonym_hits + overlap + title_overlap
        if score > 0:
            scored.append((score, index, section))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [s for _, _, s in scored[:k]]


def format_sections(sections: list[Section]) -> str:
    if not sections:
        return "Nenhuma seção do manual corresponde à pergunta."
    return "\n\n".join(f"### {s.heading}\n{s.text}" for s in sections)
