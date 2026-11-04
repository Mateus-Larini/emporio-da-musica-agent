# Catálogo, preços e promoção

**Cenário:** Cliente explorando violões com teto de preço, pedindo preço de um modelo específico (com erro de digitação) e perguntando sobre promoção. Mostra a busca com filtro, o preço no PIX e a regra de apresentar preço promocional junto do original e do percentual.

_Gerado em 03/11/2026 com groq / qwen/qwen3.8-27b; data de referência do agente 25/03/2026. Telefones e e-mails mascarados._

---

**Cliente:** Oi! Quais violões vocês têm até R$ 1000?

**Agente:** Boa noite! Temos algumas opções de violão até R$ 1.000:  
  
Tagima Memphis AC-39 Nylon Natural: R$ 429,90 (R$ 408,41 no PIX)  
Rozini RC-104 Nylon Estudante: R$ 459,90 (R$ 436,91 no PIX)  
Shelby SN-100 Folk Aço Preto: R$ 549,00 (R$ 521,55 no PIX)  
  
Quer saber mais detalhes de algum desses modelos?

**Cliente:** quanto ta o takamini gd 20?

**Agente:** O Takamine GD20 Dreadnought Natural está por R$ 2.199,00, ou R$ 2.089,05 no PIX. Dá pra parcelar em até 12x sem juros de R$ 183,25.  
  
Quer ver as condições de frete pra sua cidade?

**Cliente:** E o Taylor 110e, está em promoção?

**Agente:** Sim, o Taylor 110e Dreadnought Natural está em promoção: de R$ 5.999,00 por R$ 5.519,08 (8% off). Como já está com desconto, o PIX não aplica desconto extra. Dá pra parcelar em até 12x sem juros de R$ 459,92.  
  
Quer saber mais sobre as especificações dele?

**Cliente:** Pagando no pix o Taylor fica mais barato ainda?

**Agente:** Não, nesse caso não. Como o Taylor 110e já está com 8% de desconto, o desconto de 5% do PIX não se aplica sobre o preço promocional. Então no PIX ele fica pelo mesmo valor: R$ 5.519,08.  
  
Quer que eu simule o parcelamento em 12x?

---

## Bastidores: o que o agente consultou

O cliente não vê esta parte. Cada linha é um turno da conversa e as ferramentas que o agente chamou antes de responder.

1. buscar_produtos(apenas_disponiveis=True, categoria='violão', limite=3, preco_max=1000)
2. detalhar_produto(produto='Takamine GD 20')
3. detalhar_produto(produto='Taylor 110e')
4. nenhuma consulta
