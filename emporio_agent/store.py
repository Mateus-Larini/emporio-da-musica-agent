"""Dados fixos da loja (seções 1, 2 e 7 do manual) e situação "agora".

O manual traz dois números de WhatsApp (seção 1.2 e seção 7) e o e-mail com e sem
acento. Adotamos: telefone fixo da 1.2, WhatsApp da seção 7 (canal de atendimento),
e-mail sem acento (o único tecnicamente válido).
"""

from __future__ import annotations

from datetime import datetime, time

STORE = {
    "nome": "Empório da Música",
    "slogan": "Sua música começa aqui.",
    "razao_social": "Empório da Música Instrumentos Musicais Ltda.",
    "cnpj": "12.345.678/0001-90",
    "endereco": "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333",
    "telefone": "(67) 3341-4444",
    "whatsapp": "(67) 3321-4500",
    "email": "contato@emporiodamusica.com.br",
    "fundacao": 2008,
    "categorias_vendidas": (
        "guitarras, baixos, violões, baterias, teclados, instrumentos de sopro, "
        "cordas orquestrais e ukuleles"
    ),
    "nao_vende": "acessórios (cordas, palhetas, cabos, cases, pedais, amplificadores)",
}

# weekday(): 0 = segunda ... 6 = domingo
OPENING_HOURS: dict[int, tuple[time, time] | None] = {
    0: (time(9, 0), time(18, 0)),
    1: (time(9, 0), time(18, 0)),
    2: (time(9, 0), time(18, 0)),
    3: (time(9, 0), time(18, 0)),
    4: (time(9, 0), time(18, 0)),
    5: (time(9, 0), time(13, 0)),
    6: None,
}
WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

HOURS_TEXT = (
    "Segunda a sexta: 09:00 às 18:00. Sábado: 09:00 às 13:00. Domingos e feriados: fechado. "
    "WhatsApp segue o mesmo horário, com resposta automática fora do expediente."
)


def next_opening(now: datetime) -> str:
    """Descrição do próximo horário de abertura a partir de `now`."""
    for offset in range(0, 8):
        day = now.weekday() if offset == 0 else (now.weekday() + offset) % 7
        hours = OPENING_HOURS[day]
        if hours is None:
            continue
        opens, _ = hours
        if offset == 0 and now.time() >= opens:
            continue
        label = "hoje" if offset == 0 else ("amanhã" if offset == 1 else WEEKDAY_NAMES[day])
        return f"{label} às {opens.strftime('%H:%M')}"
    return "segunda às 09:00"


def status_now(now: datetime) -> dict[str, str | bool]:
    hours = OPENING_HOURS[now.weekday()]
    is_open = hours is not None and hours[0] <= now.time() < hours[1]
    return {
        "data_hora_referencia": now.strftime("%d/%m/%Y %H:%M"),
        "dia_da_semana": WEEKDAY_NAMES[now.weekday()],
        "loja_aberta_agora": is_open,
        "proxima_abertura": None if is_open else next_opening(now),
    }
