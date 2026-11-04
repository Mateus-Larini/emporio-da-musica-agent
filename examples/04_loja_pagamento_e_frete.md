# Informações da loja, pagamento e frete

**Cenário:** Perguntas sobre horário, endereço, parcelamento e frete. Mostra o agente usando os dados fixos da loja, a simulação determinística de parcelas e a regra de frete da região metropolitana.

_Gerado em 04/11/2026 com groq / qwen/qwen3.8-27b; data de referência do agente 25/03/2026. Telefones e e-mails mascarados._

---

**Cliente:** Vocês abrem no sábado? E onde fica a loja?

**Agente:** Sim, abrimos no sábado das 09:00 às 13:00. Estamos na Rua 14 de Maio, 3200, Centro, Campo Grande, MS, CEP 79202-333. Precisa de mais alguma informação?

**Cliente:** Uma compra de 1200 reais, em quantas vezes consigo parcelar sem juros?

**Agente:** Consegue parcelar em até 12x sem juros, de R$ 100,00 cada. No PIX sai por R$ 1.140,00, com 5% de desconto. Quer que eu simule o frete para a sua cidade?

**Cliente:** Moro em Campo Grande, quanto fica o frete de um ukulele de 400 reais?

**Agente:** Para Campo Grande, o frete de um ukulele de R$ 400,00 é R$ 35,00, com entrega em 1 a 3 dias úteis por motoboy. Acima de R$ 500,00 o frete é grátis. Quer ver opções de ukulele nesse valor?

---

## Bastidores: o que o agente consultou

O cliente não vê esta parte. Cada linha é um turno da conversa e as ferramentas que o agente chamou antes de responder.

1. info_loja()
2. simular_pagamento_e_frete(produto_em_promocao=False, valor_total=1200)
3. simular_pagamento_e_frete(cidade='Campo Grande', produto_em_promocao=False, valor_total=400)
