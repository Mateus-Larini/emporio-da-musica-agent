"""Gera as conversas de exemplo em examples/*.md a partir de roteiros fixos.

    uv run python examples/generate.py              todos os roteiros
    uv run python examples/generate.py 04 120       só os roteiros com "04" no nome,
                                                    esperando até 120 min por cota

Cada roteiro é uma conversa real com o modelo configurado no .env. A transcrição
mostra só o que o cliente veria; o que o agente consultou em cada turno vai para
uma seção "Bastidores" ao final, para quem avalia o projeto. Telefones e e-mails
são mascarados. Os arquivos são revisados manualmente antes de entrar no repositório.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from emporio_agent.agent import Agent, reply_when_quota_allows
from emporio_agent.config import model_names, provider, reference_now
from emporio_agent.privacy import describe_call, mask_text

OUT_DIR = Path(__file__).parent

SCRIPTS: list[dict] = [
    {
        "file": "01_catalogo_e_precos.md",
        "title": "Catálogo, preços e promoção",
        "scenario": (
            "Cliente explorando violões com teto de preço, pedindo preço de um modelo "
            "específico (com erro de digitação) e perguntando sobre promoção. Mostra a "
            "busca com filtro, o preço no PIX e a regra de apresentar preço promocional "
            "junto do original e do percentual."
        ),
        "turns": [
            "Oi! Quais violões vocês têm até R$ 1000?",
            "quanto ta o takamini gd 20?",
            "E o Taylor 110e, está em promoção?",
            "Pagando no pix o Taylor fica mais barato ainda?",
        ],
    },
    {
        "file": "02_pedido_e_devolucao.md",
        "title": "Consulta de pedido e devolução por arrependimento",
        "scenario": (
            "Situação não trivial: o cliente quer devolver um pedido. O agente exige "
            "identificação antes de consultar (LGPD), recusa um telefone que não confere, "
            "e com o telefone certo aplica os prazos do manual calculados pela data de "
            "referência (25/03/2026): arrependimento de 7 dias expirado, garantia legal "
            "de 90 dias ainda vigente."
        ),
        "turns": [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "É o pedido 7, meu telefone é (67) 99123-7788",
            "Desculpa, o telefone cadastrado é (67) 99789-0123",
            "E se o violão apresentar defeito, ainda tenho garantia?",
        ],
    },
    {
        "file": "03_pedido_atrasado.md",
        "title": "Pedido enviado com previsão vencida",
        "scenario": (
            "Cliente identificada pelo e-mail pergunta por um pedido que consta como "
            "enviado com previsão de entrega já passada. O agente relata o status como "
            "está no sistema, informa o rastreio e encaminha à equipe."
        ),
        "turns": [
            "Meu pedido 8 ainda não chegou, meu email é anacarol.ferreira@coldmail.com",
            "Como faço pra rastrear?",
        ],
    },
    {
        "file": "04_loja_pagamento_e_frete.md",
        "title": "Informações da loja, pagamento e frete",
        "scenario": (
            "Perguntas sobre horário, endereço, parcelamento e frete. Mostra o agente "
            "usando os dados fixos da loja, a simulação determinística de parcelas e a "
            "regra de frete da região metropolitana."
        ),
        "turns": [
            "Vocês abrem no sábado? E onde fica a loja?",
            "Uma compra de 1200 reais, em quantas vezes consigo parcelar sem juros?",
            "Moro em Campo Grande, quanto fica o frete de um ukulele de 400 reais?",
        ],
    },
    {
        "file": "05_limites_do_agente.md",
        "title": "Limites: acessórios, categoria vazia, fotos e fora de escopo",
        "scenario": (
            "O que o agente não faz: não vende acessórios, não inventa estoque de "
            "categorias vazias, não promete enviar fotos nem cita canais inexistentes, e "
            "não responde assuntos fora da loja."
        ),
        "turns": [
            "Vocês têm corda de violão?",
            "E violoncelo, vendem?",
            "Quero o Yamaha C40, tem fotos?",
            "Me ensina a fazer um bolo de cenoura?",
        ],
    },
]


def render(script: dict, turns: list[tuple[str, list[str], str]], model_used: str) -> str:
    lines = [
        f"# {script['title']}",
        "",
        f"**Cenário:** {script['scenario']}",
        "",
        f"_Gerado em {datetime.now():%d/%m/%Y} com {provider()} / {model_used}; "
        f"data de referência do agente {reference_now():%d/%m/%Y}. "
        "Telefones e e-mails mascarados._",
        "",
        "---",
        "",
    ]
    for user, _, reply in turns:
        lines.append(f"**Cliente:** {mask_text(user)}")
        lines.append("")
        lines.append("**Agente:** " + mask_text(reply).replace("\n", "  \n"))
        lines.append("")
    lines += [
        "---",
        "",
        "## Bastidores: o que o agente consultou",
        "",
        "O cliente não vê esta parte. Cada linha é um turno da conversa e as ferramentas "
        "que o agente chamou antes de responder.",
        "",
    ]
    for index, (_, tools, _) in enumerate(turns, start=1):
        lines.append(f"{index}. {', '.join(tools) if tools else 'nenhuma consulta'}")
    lines.append("")
    return "\n".join(lines)


def main(only: str = "", max_wait: float = 0) -> None:
    """`only` filtra roteiros pelo nome do arquivo; `max_wait` (segundos) é quanto
    esperar a cota do provedor reencher antes de desistir de um turno."""
    agent = Agent()
    print(f"provedor {provider()} | modelos {' > '.join(model_names())}")
    for script in SCRIPTS:
        if only not in script["file"]:
            continue
        agent.active_index = 0  # cada conversa tenta o modelo principal primeiro
        history = []
        turns: list[tuple[str, list[str], str]] = []
        model_used = ""
        for user in script["turns"]:
            reply = reply_when_quota_allows(agent, history, user, max_wait)
            history += reply.new_messages
            model_used = reply.model
            calls = [describe_call(t.name, t.args) for t in reply.tool_calls]
            turns.append((user, calls, reply.text))
            print(f"  [{script['file']}] {user[:50]!r} -> {len(reply.text)} chars")
        (OUT_DIR / script["file"]).write_text(render(script, turns, model_used), encoding="utf-8")
    print("conversas geradas em", OUT_DIR)


if __name__ == "__main__":
    # uso: generate.py [trecho-do-nome] [minutos-de-espera-por-cota]
    main(
        only=sys.argv[1] if len(sys.argv) > 1 else "",
        max_wait=60 * float(sys.argv[2]) if len(sys.argv) > 2 else 0,
    )
