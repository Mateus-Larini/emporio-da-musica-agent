# Resultado da avaliação

- Data da execução: 04/11/2026 14:28
- Provedor: groq | cadeia de modelos: openai/gpt-oss-120b > openai/gpt-oss-20b > qwen/qwen3.8-27b
- Modelo(s) que responderam: openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b
- Data de referência do agente: 25/03/2026
- Casos: 25 | aprovados: 22 | taxa: 88%

## Por grupo

| Grupo | Aprovados | Total |
|---|---|---|
| catálogo | 3 | 3 |
| escopo | 4 | 4 |
| estoque | 1 | 1 |
| loja | 2 | 3 |
| pedidos | 5 | 6 |
| políticas | 3 | 4 |
| preço | 2 | 2 |
| promoções | 2 | 2 |

## Por caso

| Caso | Resultado | Ferramentas | Falhas |
|---|---|---|---|
| catalogo_violoes_ate_1000 | ok | buscar_produtos | - |
| catalogo_ukulele_vago | ok | buscar_produtos | - |
| catalogo_guitarra_rock_8mil | ok | buscar_produtos | - |
| preco_takamine_pix | ok | detalhar_produto | - |
| preco_nome_com_erro_de_digitacao | ok | detalhar_produto | - |
| promocao_mostra_original_e_percentual | ok | detalhar_produto | - |
| promocao_expirada_black_friday | ok | listar_promocoes, detalhar_produto | - |
| estoque_produto_sem_estoque | ok | detalhar_produto | - |
| loja_endereco | ok | info_loja | - |
| loja_horario_sabado | ok | info_loja | - |
| loja_domingo_fechado | FALHOU | info_loja | faltou algum de ['fechado', 'fechados', 'fechamos', 'não abrimos', 'não funcionamos'] |
| pagamento_pix_desconto | FALHOU | - | faltou '5%' |
| pagamento_parcelamento_1200 | ok | simular_pagamento_e_frete | - |
| frete_campo_grande_abaixo_500 | ok | simular_pagamento_e_frete | - |
| garantia_legal | ok | consultar_politicas | - |
| pedido_exige_identificacao | ok | - | - |
| pedido_telefone_errado_nao_revela | ok | consultar_pedido | - |
| pedido_telefone_correto | ok | consultar_pedido | - |
| pedido_arrependimento_prazo_expirado | FALHOU | consultar_pedido | faltou algum de ['18/05', 'garantia'] |
| pedido_enviado_atrasado | ok | consultar_pedido | - |
| pedidos_do_cliente_por_telefone | ok | pedidos_do_cliente | - |
| escopo_acessorio | ok | - | - |
| escopo_categoria_vazia_violoncelo | ok | - | - |
| escopo_fotos | ok | detalhar_produto | - |
| escopo_fora_da_loja | ok | - | - |

## Transcrições

### catalogo_violoes_ate_1000 (ok)

**Cliente:** Quais violões vocês têm até R$ 1000?

_ferramentas: buscar_produtos_

**Agente:** Temos boas opções de violões até R$ 1.000:  
  
Tagima Memphis AC-39 Nylon Natural: R$ 429,90 (R$ 408,41 no PIX)    
Rozini RC-104 Nylon Estudante: R$ 459,90 (R$ 436,91 no PIX)    
Shelby SN-100 Folk Aço Preto: R$ 549,00 (R$ 521,55 no PIX)    
Giannini GF-1R Aço Folk Sunburst: R$ 579,90 (R$ 550,91 no PIX)    
Yamaha C40 Nylon Natural: R$ 599,90 (R$ 569,91 no PIX)    
  
Algum desses modelos chamou sua atenção?

### catalogo_ukulele_vago (ok)

**Cliente:** to começando a tocar e queria um ukulele barato, o que indicam?

_ferramentas: buscar_produtos_

**Agente:** Bom dia! Seguem opções de ukuleles com bom custo-benefício:  
  
Shelby SU-21S Soprano Sunburst: R$ 159,90 (R$ 151,91 no PIX)    
Kalani KAL-300S Soprano Natural: R$ 179,90 (R$ 170,91 no PIX)    
Kala KA-15S Soprano Mogno: R$ 199,90 (R$ 189,91 no PIX)    
Ohana SK-10 Soprano Natural: R$ 249,90 (R$ 237,41 no PIX)    
Kala KA-C Concert Mogno: R$ 349,90 (R$ 332,41 no PIX)    
  
Algum desses modelos chamou sua atenção?

### catalogo_guitarra_rock_8mil (ok)

**Cliente:** tem alguma guitarra boa pra rock até uns 8 mil?

_ferramentas: buscar_produtos_

**Agente:** Aqui vão três opções de guitarra boa para rock dentro do seu orçamento:    
  
Fender Telecaster Player Series: R$ 5.400,00 (R$ 5.130,00 no PIX)    
PRS SE Custom 24: R$ 6.800,00 (R$ 6.460,00 no PIX)    
Ibanez RG550 Genesis Collection: R$ 7.500,00 (R$ 7.125,00 no PIX)    
  
Qual delas chamou mais a sua atenção?

### preco_takamine_pix (ok)

**Cliente:** Quanto custa o Takamine GD20 no pix?

_ferramentas: detalhar_produto_

**Agente:** Takamine GD20 Dreadnought Natural: R$ 2.089,05 no PIX.    
Quer saber as condições de parcelamento?

### preco_nome_com_erro_de_digitacao (ok)

**Cliente:** quanto ta o takamini gd 20?

_ferramentas: detalhar_produto_

**Agente:** O Takamine GD20 Dreadnought Natural está por R$ 2.199,00, ou R$ 2.089,05 no PIX. Dá pra parcelar em até 12x sem juros de R$ 183,25. Tem 5 unidades em estoque. Quer ver as condições de frete pra sua cidade?

### promocao_mostra_original_e_percentual (ok)

**Cliente:** O Taylor 110e está em promoção?

_ferramentas: detalhar_produto_

**Agente:** Sim, o Taylor 110e está com desconto de 8%: de R$ 5.999,00 por R$ 5.519,08. Quer saber mais detalhes ou ver condições de parcelamento?

### promocao_expirada_black_friday (ok)

**Cliente:** Tem Black Friday rolando? Queria o Crafter CE-15 com desconto

_ferramentas: listar_promocoes, detalhar_produto_

**Agente:** Não tem Black Friday no momento, só as promoções ativas no sistema, e o Crafter CE-15 não está entre elas. Ele está por R$ 3.899,00 (R$ 3.704,05 no PIX, 5% off) e dá pra parcelar em até 12x sem juros. Quer que eu simule o parcelamento ou o frete pra sua cidade?

### estoque_produto_sem_estoque (ok)

**Cliente:** O Giannini GF-3D Sunburst tem na loja?

_ferramentas: detalhar_produto_

**Agente:** Giannini GF-3D Dreadnought Sunburst está temporariamente sem estoque.    
Alternativas disponíveis:    
Yamaha C70 Nylon Natural: R$ 849,00 (R$ 806,55 no PIX)    
Tagima Dallas Tuner Aço Natural: R$ 749,00 (R$ 711,55 no PIX)    
Shelby SGD-195E Elétrico Aço Sunburst: R$ 799,00 (R$ 759,05 no PIX)    
  
Quer saber mais detalhes de algum desses modelos?

### loja_endereco (ok)

**Cliente:** Qual o endereço da loja?

_ferramentas: info_loja_

**Agente:** Rua 14 de Maio, 3200, Centro, Campo Grande, MS, CEP 79202-333.    
Precisa de mais alguma informação?

### loja_horario_sabado (ok)

**Cliente:** Vocês abrem no sábado? Até que horas?

_ferramentas: info_loja_

**Agente:** Bom dia! Sim, abrimos aos sábados das 09:00 às 13:00. Precisa de alguma informação sobre instrumentos?

### loja_domingo_fechado (FALHOU)

**Cliente:** Vocês abrem domingo?

_ferramentas: info_loja_

**Agente:** Não, aos domingos a loja fica fechada. Nosso horário é de segunda a sexta das 9h às 18h e sábado das 9h às 13h. Quer saber mais sobre algum instrumento?

- falha: faltou algum de ['fechado', 'fechados', 'fechamos', 'não abrimos', 'não funcionamos']

### pagamento_pix_desconto (FALHOU)

**Cliente:** Pagando no pix tem desconto?

**Agente:** Sim, no pagamento via PIX você recebe 5 % de desconto sobre o preço de tabela, sem acumular com eventuais promoções. Quer saber como fica o valor de algum produto específico?

- falha: faltou '5%'

### pagamento_parcelamento_1200 (ok)

**Cliente:** Uma compra de 1200 reais, em quantas vezes consigo parcelar sem juros?

_ferramentas: simular_pagamento_e_frete_

**Agente:** Dá pra parcelar em até 12x sem juros, de R$ 100,00 por parcela. No PIX sai R$ 1.140,00, com 5% de desconto. Quer que eu simule o frete pra sua cidade também?

### frete_campo_grande_abaixo_500 (ok)

**Cliente:** Moro em Campo Grande, quanto fica o frete de um ukulele de 400 reais?

_ferramentas: simular_pagamento_e_frete_

**Agente:** Frete de R$ 35,00, prazo de 1 a 3 dias úteis.    
Quer saber mais sobre as condições de pagamento?

### garantia_legal (ok)

**Cliente:** Qual a garantia dos instrumentos?

_ferramentas: consultar_politicas_

**Agente:** A garantia legal é de 90 dias a partir da data de compra.    
Além disso, a maioria dos fabricantes oferece garantia própria que varia de 6 meses a 2 anos, conforme o certificado que acompanha cada instrumento.    
  
Algum modelo em particular te interessa?

### pedido_exige_identificacao (ok)

**Cliente:** Qual o status do pedido 7?

**Agente:** Para consultar o pedido 7, preciso do telefone ou e-mail cadastrado na compra. Pode me passar um dos dois?

### pedido_telefone_errado_nao_revela (ok)

**Cliente:** Quero ver o pedido 7, meu telefone é ***7788

_ferramentas: consultar_pedido_

**Agente:** Desculpe, os dados não conferem com o cadastro desse pedido. Pode confirmar o telefone ou o e-mail que você usou na compra?

### pedido_telefone_correto (ok)

**Cliente:** Quero ver o pedido 7, meu telefone é ***0123

_ferramentas: consultar_pedido_

**Agente:** Pedido nº 7: entregue em 17/02/2026, valor R$ 159,90, pagamento em 3x no cartão. Produto: Shelby SU-21S Soprano Sunburst (1 unidade). Código de rastreio: BRKR1122334BR. Precisa de mais alguma informação?

### pedido_arrependimento_prazo_expirado (FALHOU)

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Agente:** Boa tarde! Para verificar a possibilidade de devolução, preciso do número do pedido e do telefone ou e-mail cadastrado. Pode me informar?

**Cliente:** Pedido 7, telefone ***0123

_ferramentas: consultar_pedido_

**Agente:** O prazo de arrependimento de 7 dias corridos após o recebimento já expirou (entregamos em 17/02/2026). Assim, não é possível devolver por arrependimento. Se houver algum defeito de fabricação, podemos analisar a troca ou reembolso. Você percebeu algum problema no instrumento?

- falha: faltou algum de ['18/05', 'garantia']

### pedido_enviado_atrasado (ok)

**Cliente:** Meu pedido 8 não chegou, meu email é an***@coldmail.com

_ferramentas: consultar_pedido_

**Agente:** O pedido 8 foi enviado em 15/02/2026, com previsão de entrega em 28/02/2026, e ainda consta como enviado. Você pode rastrear pelo código BRJL5544332BR e, se não chegar, a equipe pode ajudar. Precisa que eu encaminhe a equipe para resolver?

### pedidos_do_cliente_por_telefone (ok)

**Cliente:** Não lembro o número do meu pedido, meu telefone é ***1098

_ferramentas: pedidos_do_cliente_

**Agente:** Você tem dois pedidos: #19 cancelado e #1 entregue. Qual deles você quer saber mais?

### escopo_acessorio (ok)

**Cliente:** Vocês têm corda de violão?

**Agente:** Aqui na Empório da Música a gente vende só instrumentos musicais, então não temos cordas, palhetas nem acessórios. Pra isso, o ideal é procurar uma loja especializada em acessórios. Posso te ajudar a escolher um violão?

### escopo_categoria_vazia_violoncelo (ok)

**Cliente:** Vocês vendem violoncelo?

**Agente:** Boa tarde! No momento não temos violoncelos no nosso catálogo. Gostaria de saber sobre outro instrumento ou prefere falar com a equipe pelo WhatsApp?

### escopo_fotos (ok)

**Cliente:** Quero o Yamaha C40, tem fotos?

_ferramentas: detalhar_produto_

**Agente:** O Yamaha C40 Nylon Natural tem tampo em Spruce, fundo e laterais em Meranti, braço em nato e cordas de nylon. É ideal para estudantes e iniciantes, com boa projeção sonora. Por aqui não consigo enviar fotos, mas você pode vir à loja para ver pessoalmente ou pedir fotos à equipe pelo WhatsApp ***4500. Gostaria de saber mais detalhes sobre o modelo?

### escopo_fora_da_loja (ok)

**Cliente:** Me ensina a fazer um bolo de cenoura?

**Agente:** Aqui eu só consigo ajudar com a Empório da Música, que é loja de instrumentos. Quer saber de algum violão, guitarra ou outro instrumento?
