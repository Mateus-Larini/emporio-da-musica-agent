# Catálogo, preços e promoção

**Cenário:** Cliente explorando violões com teto de preço, pedindo preço de um modelo específico (com erro de digitação) e perguntando sobre promoção. Mostra a busca com filtro, o preço no PIX e a regra de apresentar preço promocional junto do original e do percentual.

_Gerado em 04/11/2026 com groq / openai/gpt-oss-120b; data de referência do agente 25/03/2026. Telefones e e-mails mascarados._

---

**Cliente:** Oi! Quais violões vocês têm até R$ 1000?

**Agente:** Bom dia! Seguem opções de violões até R$ 1.000:  
  
Tagima Memphis AC-39 Nylon Natural: R$ 429,90 (R$ 408,41 no PIX)    
Rozini RC-104 Nylon Estudante: R$ 459,90 (R$ 436,91 no PIX)    
Shelby SN-100 Folk Aço Preto: R$ 549,00 (R$ 521,55 no PIX)    
  
Algum desses te interessou?

**Cliente:** quanto ta o takamini gd 20?

**Agente:** Takamine GD20 Dreadnought Natural: R$ 2.199,00 (R$ 2.089,05 no PIX).    
  
Quer saber as condições de parcelamento ou outra opção?

**Cliente:** E o Taylor 110e, está em promoção?

**Agente:** Taylor 110e Dreadnought Natural: de R$ 5.999,00 por R$ 5.519,08 (8% off).    
  
Deseja ver as opções de parcelamento ou outro modelo?

**Cliente:** Pagando no pix o Taylor fica mais barato ainda?

**Agente:** No caso do Taylor 110e, o preço promocional já está aplicado (de R$ 5.999,00 por R$ 5.519,08). O desconto de 5 % do PIX não se soma a ele, então o valor no PIX continua R$ 5.519,08.    
  
Quer saber como funciona o parcelamento ou prefere outro modelo?

---

## Bastidores: o que o agente consultou

O cliente não vê esta parte. Cada linha é um turno da conversa e as ferramentas que o agente chamou antes de responder.

1. buscar_produtos(apenas_disponiveis=True, categoria='Violão', limite=3, preco_max=1000)
2. detalhar_produto(produto='Takamine GD20')
3. buscar_produtos(apenas_disponiveis=True, busca='Taylor 110e', limite=5)
4. nenhuma consulta
