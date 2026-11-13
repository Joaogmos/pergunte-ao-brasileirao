# ADR-4: O agente e um grafo explicito em LangGraph, nao um agente pronto

**Status:** aceito
**Data:** 2026-10-26

## Contexto

O laco basico de um agente e curto: chama o modelo, executa as ferramentas que ele
pediu, devolve os resultados, repete ate vir texto. Aqui ha tres desvios desse laco:
o verificador pode devolver o rascunho ao modelo, `fora_do_escopo` encerra sem nova
chamada, e ha um teto de chamadas por pergunta.

## Decisao

Um `StateGraph` com quatro nos (`modelo`, `ferramentas`, `verificador`, `recusa`) e
arestas condicionais escritas a mao em `agente.py`. O no de ferramentas e proprio, em
vez do `ToolNode` pronto, porque ele tambem guarda os resultados como "fatos" para o
verificador e trata ferramenta inexistente e argumento invalido como erro legivel.
A memoria entre turnos e o checkpointer do LangGraph, com um `thread_id` por conversa.

## Consequencias

Cada caminho do grafo tem um teste com um LLM roteirizado (`tests/test_agente.py`):
caminho feliz, correcao aceita, recusa apos duas reprovacoes, resposta de memoria
barrada, erro de ferramenta, limite de chamadas, memoria por conversa.

O estado mistura dois ciclos de vida: `messages` e `fatos` duram a conversa;
`chamadas`, contadores e veredito sao zerados a cada pergunta em `Agente.perguntar`.
Isso esta num lugar so, mas e facil de esquecer ao adicionar um campo.

O checkpointer e em memoria: reiniciar a API apaga as conversas. O que vai para o modelo
e uma janela das ultimas 6 perguntas da conversa (`janela` em `agente.py`), cortada
sempre no inicio de um turno para nao separar o resultado de uma ferramenta do pedido
que o gerou. Os resultados de ferramenta antigos continuam valendo como fonte para o
verificador. Para producao faltam um checkpointer em banco (Postgres) e um resumo do
que a janela corta.

## Alternativas consideradas

- **`create_react_agent` pronto:** menos codigo, mas o verificador e a recusa fixa
  teriam de entrar por ganchos, e o fluxo deixaria de estar visivel num arquivo.
- **Laco `while` na mao, sem framework:** funciona para um turno. Perde o checkpointer
  e a visualizacao do grafo, e eu reescreveria parte do LangGraph.