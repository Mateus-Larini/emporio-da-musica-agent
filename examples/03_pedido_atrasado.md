# Pedido enviado com previsão vencida

**Cenário:** Cliente identificada pelo e-mail pergunta por um pedido que consta como enviado com previsão de entrega já passada. O agente relata o status como está no sistema, informa o rastreio e encaminha à equipe.

_Gerado em 04/11/2026 com groq / openai/gpt-oss-120b; data de referência do agente 25/03/2026. Telefones e e-mails mascarados._

---

**Cliente:** Meu pedido 8 ainda não chegou, meu email é an***@coldmail.com

**Agente:** Ana Carolina, seu pedido 8 está com status “enviado” e o código de rastreio é BRJL5544332BR. A previsão de entrega era 28/02/2026, que já passou. Você pode acompanhar o trajeto pelo site dos Correios e, se ainda não receber, entre em contato com a equipe pelo WhatsApp ***4500 para que possamos acionar a transportadora. Precisa de ajuda para abrir a solicitação?

**Cliente:** Como faço pra rastrear?

**Agente:** Acesse o site dos Correios (www.correios.com.br), clique em “Rastreamento” e digite o código BRJL5544332BR. O sistema mostrará a localização atual e a data prevista de entrega. Caso o status não avance ou o prazo já tenha passado, avise a gente pelo WhatsApp ***4500 para que possamos abrir a solicitação junto à transportadora. Precisa de mais alguma orientação?

---

## Bastidores: o que o agente consultou

O cliente não vê esta parte. Cada linha é um turno da conversa e as ferramentas que o agente chamou antes de responder.

1. consultar_pedido(email='an***@coldmail.com', numero_pedido=8)
2. nenhuma consulta
