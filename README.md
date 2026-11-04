# Empório da Música — Agente de Atendimento

Protótipo de atendente virtual para a Empório da Música, loja fictícia de instrumentos
musicais de Campo Grande/MS, construído para o desafio técnico de AI Engineer da Artefact.

O agente conversa em português no tom da loja, consulta o catálogo, os pedidos e as
promoções em um banco local, aplica as regras do manual de políticas (trocas, garantia,
frete, pagamento) e recusa com educação o que foge do escopo.

```
Cliente: Me arrependi da minha compra, posso devolver meu pedido?
Agente:  Para eu verificar, preciso do número do pedido e do telefone ou e-mail cadastrado.

Cliente: Pedido 7, telefone (67) 9****-0123
Agente:  Letícia, seu pedido 7 foi entregue em 17/02/2026. O prazo de arrependimento
         (7 dias após o recebimento) terminou em 24/02/2026, então não cabe mais
         devolução por arrependimento. Se o violão apresentar defeito de fabricação,
         a garantia legal de 90 dias vale até 18/05/2026. [...]
```

Antes de responder, o agente consultou o pedido e só o exibiu porque o telefone
conferia com o cadastro. Mais conversas em [`examples/`](examples/), cada uma com uma
seção "Bastidores" mostrando o que foi consultado. Resultado da avaliação automática em
[`evals/results.md`](evals/results.md).

---

## Como rodar

**Requisitos:** [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho) e uma
chave de API. A opção gratuita, sem cartão, é o [Groq](https://console.groq.com/keys).
A Anthropic (Claude) também é suportada.

```bash
git clone https://github.com/Mateus-Larini/emporio-da-musica-agent.git
cd emporio-da-musica-agent
uv sync                      # cria o ambiente e instala as dependências
cp .env.example .env         # edite e coloque sua chave (GROQ_API_KEY ou ANTHROPIC_API_KEY)
```

| O que | Comando |
|---|---|
| Chat no terminal | `uv run emporio` |
| Chat no navegador | `uv run streamlit run app.py` e abra http://localhost:8501 |
| Pergunta única, sem interação | `uv run emporio --pergunta "Quanto custa o Takamine GD20?"` |
| Ver as ferramentas chamadas (visão de desenvolvedor) | `uv run emporio --rastro` |
| Testes (sem chamar API) | `uv run pytest` |
| Avaliação contra o modelo | `uv run python -m evals` |
| Regenerar as conversas de exemplo | `uv run python examples/generate.py` |

O banco SQLite (`data/emporio.db`) é criado a partir dos CSVs na primeira execução.
Para recriar: `uv run python -m emporio_agent.data.loader`.

Variáveis do `.env` (todas documentadas em [`.env.example`](.env.example)):

| Variável | Para quê |
|---|---|
| `EMPORIO_PROVIDER` | `groq` ou `anthropic`. Se omitida, usa o provedor cuja chave existir. |
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | chave do provedor |
| `EMPORIO_MODEL`, `EMPORIO_MODEL_FALLBACKS` | modelo principal e lista de reservas (ver "Modelo e provedor") |
| `EMPORIO_REFERENCE_DATE` | data "de hoje" para cálculo de prazos (ver "Suposições") |

---

## Arquitetura

```
 cliente ──► CLI (emporio) ou Streamlit (app.py)
                │
                ▼
         Agent.reply(histórico, mensagem)          emporio_agent/agent.py
                │  system prompt (persona + regras) emporio_agent/prompts.py
                │  loop: modelo ─► tool call ─► resultado ─► modelo ... ─► texto
                ▼
         ┌─────────────────── ferramentas (emporio_agent/tools.py) ───────────────────┐
         │ buscar_produtos  detalhar_produto  listar_promocoes  consultar_pedido       │
         │ pedidos_do_cliente  simular_pagamento_e_frete  info_loja  consultar_politicas│
         └──────┬──────────────────────┬─────────────────────────────┬─────────────────┘
                ▼                      ▼                             ▼
      Repository (SQLite)       rules.py (regras do manual      policies.py (PDF em
      data/*.csv ─► emporio.db  em código: PIX, parcelas,       seções + busca lexical)
                                frete, prazos de devolução)
                │
                ▼
      sessions/<id>.json  (histórico por conversa, emporio_agent/memory.py)
```

**Fluxo de uma mensagem.** O histórico da sessão é carregado do JSON; o prompt de sistema
(persona, regras de conduta, data de referência) é montado; o modelo recebe tudo mais a
lista de ferramentas. Se ele pedir uma ferramenta, o código executa e devolve o JSON; o
ciclo repete até o modelo escrever a resposta final (limite de 6 rodadas). As mensagens
novas são anexadas ao JSON da sessão.

| Módulo | Responsabilidade |
|---|---|
| `emporio_agent/data/loader.py` | CSVs → SQLite, com validação de integridade e troca atômica do arquivo |
| `emporio_agent/data/repository.py` | consultas tipadas: busca tolerante a acento/plural/erro de digitação, clientes, pedidos, promoções |
| `emporio_agent/rules.py` | regras do manual em código: PIX 5% sem cumular, faixas de parcelamento, frete, janelas de devolução/garantia |
| `emporio_agent/policies.py` | PDF do manual fatiado por seção numerada; busca por termos e sinônimos |
| `emporio_agent/store.py` | dados fixos da loja (endereço, telefones, horários) e "aberta agora?" |
| `emporio_agent/tools.py` | as 8 ferramentas com schemas Pydantic; única porta do modelo para os dados |
| `emporio_agent/prompts.py` | persona e regras de conduta |
| `emporio_agent/agent.py` | loop de tool use, cadeia de fallback de modelos, rastro das chamadas |
| `emporio_agent/memory.py` | persistência do histórico por sessão |
| `emporio_agent/cli.py`, `app.py` | interfaces |
| `evals/` | casos de avaliação e runner |
| `tests/` | 84 testes, nenhum chama API |

---

## Decisões técnicas

### Abordagem: ferramentas tipadas + políticas por seção (híbrido)

Os dados da loja são **tabulares** (produtos, pedidos, promoções) e as perguntas sobre
eles são **filtros** ("violões até R$ 1000", "status do pedido 7"), não buscas
semânticas. Para isso, o modelo recebe funções com argumentos validados e o código
executa a consulta. O modelo nunca escreve SQL: isso elimina consultas inventadas,
mantém a leitura restrita e torna cada resposta auditável (a UI mostra a chamada e o
JSON devolvido).

Toda **aritmética e prazo** fica em `rules.py`, determinístico e testado. O manual diz
que informação errada de preço configura propaganda enganosa; um modelo de linguagem
calculando desconto e parcela erraria uma hora ou outra.

O **manual de políticas** é texto, e aí sim faz sentido recuperar trechos: o PDF é
fatiado nas seções numeradas e a ferramenta `consultar_politicas` devolve as 3 mais
relevantes. A busca é lexical (termos normalizados mais um mapa de sinônimos do
vocabulário do cliente, como "arrependi" → seção 4.1). Para um documento de 8 páginas
com seções bem demarcadas isso é suficiente, não depende de serviço de embeddings e é
fácil de inspecionar. Embeddings entrariam se o manual crescesse para dezenas de páginas.

Alternativas consideradas:

- **RAG sobre os CSVs**: chunks de linhas de tabela recuperados por similaridade não
  respeitam filtro de preço nem estoque; descartado.
- **Agente de SQL livre** (o modelo escreve as consultas): mais flexível, porém frágil e
  difícil de restringir; um dos repositórios públicos deste mesmo desafio relata ter
  precisado ajustar o prompt para o modelo descobrir os JOINs. Descartado para um
  domínio com 6 tabelas e perguntas previsíveis.
- **LangGraph**: o fluxo aqui é um único loop de ferramentas sem ramificações nem
  estado complexo; um grafo adicionaria abstração sem benefício. O LangChain entra só
  como camada de modelo e de definição de ferramentas, e o loop (cerca de 60 linhas)
  está escrito em `agent.py` para ser lido e testado.

### Modelo e provedor

Padrão: **Groq**, gratuito e sem cartão, com `openai/gpt-oss-120b` como modelo
principal. A escolha foi pragmática: o avaliador consegue rodar sem custo, e o modelo
lida bem com chamada de ferramentas em português.

O limite diário da cota gratuita apareceu durante os testes. A resposta foi uma
**cadeia de fallback**: se o modelo ativo falha por cota, indisponibilidade ou erro de
servidor, o agente passa ao seguinte (`openai/gpt-oss-20b`, depois `qwen/qwen3.8-27b`),
cada um com cota própria. Erros de requisição inválida não disparam fallback, porque
repetir em outro modelo não resolveria. A cadeia é configurável no `.env`.

O Groq tem dois limites: por minuto e por dia. Quando o erro informa uma espera curta
(limite por minuto), o agente aguarda esses segundos e repete no mesmo modelo, que
responde melhor que os reservas; só desce na cadeia quando a espera seria longa (cota
do dia). Os scripts em lote (avaliação e exemplos) ainda aceitam esperar a cota
reencher entre chamadas (`--wait` em minutos), porque rodam dezenas de conversas
seguidas.

**Claude** (Anthropic) é suportado trocando o provedor no `.env`; o padrão nesse caso é
`claude-haiku-5-5`, com esforço de raciocínio baixo, suficiente para escolher ferramentas
e redigir uma mensagem de WhatsApp. Modelo local via Ollama foi descartado por exigir
GPU para ficar utilizável.

### Estratégia de prompt

Um único prompt de sistema (`prompts.py`) com: a persona do manual ("amigo que entende de
música", informal mas profissional), a data e hora de referência, as regras de ouro
(nunca afirmar preço, estoque ou prazo sem consultar; pedir identificação antes de
mostrar pedido; PIX não cumula com promoção; preço promocional sempre com o original e
o percentual), o escopo (só instrumentos, sem acessórios, sem assuntos fora da loja) e o
que o agente **não** consegue fazer (reservar, vender, cancelar, enviar fotos, avisar
quando chegar). Grande parte dessas linhas nasceu de testes manuais em que o modelo
inventou um site, prometeu fotos ou ofereceu "indicar lojas parceiras" que não existem
nos materiais.

As ferramentas também carregam instruções no JSON que devolvem (ex.: "não recalcule
totais de pedidos já feitos", "não repita a mesma chamada após erro"), porque o modelo
lê o resultado no momento em que precisa da orientação.

### Interface

CLI e Streamlit, ambos sobre a mesma classe `Agent`. A CLI tem modo não interativo,
usado para gerar as conversas de exemplo de forma reproduzível. O Streamlit mostra, em
cada resposta, as ferramentas consultadas com argumentos e retorno. Uma API HTTP
(FastAPI) e um frontend em React foram considerados e deixados de fora: o enunciado
coloca a interface como secundária, e o tempo foi investido na avaliação do agente.

### Persistência do histórico

Um arquivo JSON por sessão em `sessions/` (mensagens serializadas pelo LangChain,
incluindo as chamadas de ferramenta). O modelo não tem memória: a cada turno o
histórico inteiro é reenviado. Para um protótipo com poucos usuários, arquivos são
simples e inspecionáveis; em produção seria uma tabela no banco.

### Tratamento dos dados

Os 6 CSVs vão para um SQLite local em uma carga validada (chaves estrangeiras
conferidas; falha aborta sem deixar banco pela metade). Na carga, cada produto ganha
uma coluna de busca normalizada (sem acento, sem plural) e os clientes ganham telefone
só com dígitos e e-mail em minúsculas, para a identificação tolerar formatos diferentes.
Nomes de produto com erro de digitação caem em um fallback de similaridade de caracteres.

---

## Suposições e contradições encontradas nos materiais

O enunciado pede para assumir interpretações razoáveis e documentá-las.

| Ponto | O que os materiais dizem | O que foi adotado |
|---|---|---|
| Data "de hoje" | Os pedidos vão até março de 2026 | `EMPORIO_REFERENCE_DATE=2026-03-25` por padrão no `.env.example`, para que prazos de devolução e garantia façam sentido. Sem a variável, usa a data real. |
| Data de recebimento | Os pedidos não têm `delivered_at` | Para pedidos entregues, a previsão de entrega é tratada como data de recebimento. |
| Troca por preferência | "em até 7 dias", sem dizer a partir de quando | Contados do recebimento, como o arrependimento. |
| Frete em exatamente R$ 500 | "grátis acima de 500" e "taxa abaixo de 500" | R$ 500,00 paga a taxa (regra estrita). |
| Parcelamento | Tabela diz "parcela mínima R$ 100"; seção 3.1 detalha faixas (50 / 80 / 100) | Seguida a seção 3.1, mais específica. |
| WhatsApp | Seção 1.2: (67) 3341-4444 "Telefone / WhatsApp"; seção 7: WhatsApp (67) 3321-4500 | 3341-4444 como fixo, 3321-4500 como WhatsApp de atendimento (a seção 7 é a específica do canal). |
| E-mail | Aparece com e sem acento ("empóriodamusica") | Sem acento, o único tecnicamente válido. |
| Tamanho do catálogo | Manual: "mais de 300 instrumentos"; CSV: 65 | Os dados prevalecem. Categorias de sopro e cordas orquestrais existem no CSV mas estão vazias; o agente informa que não há itens no momento, sem prometer avisar. |
| Black Friday | Manual promete 15% a 30% em novembro; no CSV a promoção está inativa | Os dados prevalecem (regra 7.3 do manual: nunca prometer desconto não vigente). |
| Pedidos históricos | Alguns violam as regras (PIX sem os 5%, parcelas abaixo do mínimo, total diferente da soma dos itens, item "em breve") | O agente relata pedidos como estão no sistema e não recalcula nada. |
| "Lojas parceiras" | O manual manda sugerir, mas não lista nenhuma | O agente sugere procurar loja especializada, sem citar nomes. |

---

## Qualidade

- **Testes** (`uv run pytest`): 84 testes cobrindo carga e integridade dos dados, busca,
  regras de preço/parcela/frete/prazos, recuperação de políticas, as 8 ferramentas
  (inclusive a recusa por identificação errada), o loop do agente com modelo simulado,
  a cadeia de fallback, a persistência e a CLI. Nenhum chama API.
- **CI** (`.github/workflows/ci.yml`): ruff e pytest em todo pull request.
- **Avaliação com modelo real** (`uv run python -m evals`): 25 casos em
  [`evals/cases.yaml`](evals/cases.yaml), cada um com a ferramenta esperada e trechos
  que a resposta deve ou não conter (preço correto, código de rastreio, ausência de
  promessas como "reservar" ou "nosso site"). Última execução completa: **22 de 25
  casos aprovados (88%)**, relatório com transcrições em
  [`evals/results.md`](evals/results.md). Das três falhas, uma era do próprio caso
  (aceitava "fechado" mas não "fechada"), uma de formatação ("5 %" em vez de "5%") e
  uma de completude (ao negar o arrependimento, o agente não citou a garantia legal
  ainda aberta). As três foram corrigidas em seguida (normalização de "5 %" coberta
  por teste unitário, caso ampliado, regra de prompt para citar os prazos ainda
  abertos); a reexecução desses casos com o modelo real ficou limitada pela cota
  gratuita do dia.
- **Conversas de exemplo** (`examples/`): 5 roteiros gerados pela CLI e revisados, com
  as ferramentas chamadas em cada turno.

---

## Limitações conhecidas e próximos passos

- **Busca de políticas lexical.** Perguntas com vocabulário muito distante do manual
  podem não achar a seção; com mais tempo, embeddings com reranking e um conjunto de
  perguntas de validação maior.
- **Identificação do cliente fraca.** Telefone ou e-mail bastam para ver um pedido. É o
  que os dados permitem; em produção, o número do WhatsApp já viria autenticado do canal.
- **Sem escrita.** O agente só informa; reclamações, reservas e cancelamentos são
  encaminhados à equipe. O próximo passo natural é uma ferramenta de "registrar
  atendimento" com aprovação humana.
- **Avaliação por trechos.** Os 25 casos verificam presença/ausência de texto e a
  ferramenta chamada, não a qualidade da redação. Um juiz automático (LLM) por critério
  seria o passo seguinte.
- **Histórico em arquivos** e sem resumo: conversas muito longas crescem o contexto.
- **Cota gratuita.** O fallback entre modelos mitiga, mas o Groq gratuito limita tokens
  por dia; para uso contínuo, plano pago ou Claude.
- **Interface.** Streamlit atende a demonstração; um produto pediria API (FastAPI) e um
  canal real (WhatsApp Business), com o histórico em banco.
- **Dados.** O CSV não traz imagens, data de entrega real nem indicação de "venda final"
  (seção 4.4 do manual); o agente responde sem esses dados.

---

## Uso de assistentes de IA

Este projeto foi desenvolvido em par com o **Claude Code** (Anthropic), no terminal,
com o modelo Claude Fable 5.1. O fluxo:

1. **Contexto e plano.** O assistente leu o enunciado, o manual e os CSVs, levantou as
   pegadinhas (contradições do manual, pedidos fora das regras, datas) e propôs a
   arquitetura. Fiz uma pesquisa de mercado com ele sobre abordagens (RAG vs. tool
   calling, frameworks) e sobre entregas públicas deste mesmo desafio, para decidir
   onde investir.
2. **Decisões minhas, execução dele.** Escolhi o provedor (Groq pela gratuidade),
   recusei React e FastAPI para focar no agente, fixei a data de referência, e pedi
   mudanças de tom e formato (sem emojis, sem travessões, saudação por horário,
   fechamento contextual, vocabulário sem gírias). O assistente implementou, testou e
   abriu os commits.
3. **Gitflow com pull requests.** Quatro branches (`feature/data-layer`,
   `feature/agent-core`, `feature/cli-ui`, `feature/docs-examples`), cada uma com
   commits pequenos e PR para `develop` com CI; release final para `main`. Os merges e
   PRs foram feitos por mim no GitHub.
4. **Teste manual guiando o prompt.** Conversei com o agente pela CLI e pela web e
   reportei cada resposta ruim (oferta de "reservar", fotos "pelo site", "lojas
   parceiras", violão como substituto de violoncelo). Cada caso virou uma regra no
   prompt, um teste ao vivo e, no fim, um caso no conjunto de avaliação.
5. **Bugs encontrados no uso real.** O erro de SQLite entre threads só apareceu na
   interface web; foi corrigido com conexão por thread e ganhou teste de regressão.

Os commits trazem a coautoria do assistente. Os comentários de código foram escritos
para quem lê o projeto, não como registro das sessões.

---

## Estrutura do repositório

```
.
├── app.py                    # interface Streamlit
├── data/                     # CSVs e PDF do manual (fornecidos); emporio.db é gerado
├── emporio_agent/            # pacote do agente (ver tabela em "Arquitetura")
├── evals/                    # casos de avaliação, runner e relatório
├── examples/                 # conversas de exemplo
├── tests/                    # testes automatizados
├── .env.example              # variáveis de ambiente documentadas
├── .github/workflows/ci.yml  # lint e testes em PRs
└── pyproject.toml            # dependências (uv)
```
