# Decisoes de arquitetura (ADRs)

Cada decisao que muda o comportamento do agente ou o numero do eval tem um registro
curto: contexto, decisao, consequencias (com o trade-off) e alternativas descartadas.

| ADR | Decisao |
|---|---|
| [ADR-1](adr-1-modelo-como-dependencia-travada.md) | O modelo estatistico e uma dependencia travada em commit, com o mesmo snapshot de dados |
| [ADR-2](adr-2-ferramenta-entrega-numero-pronto.md) | A ferramenta entrega o numero pronto; o LLM copia, nao calcula |
| [ADR-3](adr-3-verificador-deterministico.md) | Um verificador em codigo confere a origem de cada numero da resposta |
| [ADR-4](adr-4-grafo-explicito-em-langgraph.md) | O agente e um grafo explicito em LangGraph, nao um agente pronto |
| [ADR-5](adr-5-juiz-deterministico-e-conjunto-de-teste.md) | Eval com juiz deterministico, gabarito calculado e conjunto de teste separado |
| [ADR-6](adr-6-modelo-aberto-local-como-padrao.md) | O modelo padrao e aberto e roda local; o provedor e trocavel |
| [ADR-7](adr-7-eval-gravado-no-ci.md) | O CI re-julga o eval gravado em vez de chamar um LLM |