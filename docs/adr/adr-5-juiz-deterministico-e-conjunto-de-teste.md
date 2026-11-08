# ADR-5: Eval com juiz deterministico, gabarito calculado e conjunto de teste separado

**Status:** aceito
**Data:** 2026-10-30

## Contexto

Para saber se uma mudanca de prompt melhorou ou piorou o agente e preciso medir. A
resposta certa aqui quase sempre e um numero que sai de uma funcao Python.

## Decisao

- **Juiz em codigo** (`avaliacao/juiz.py`), com quatro checagens: tipo (respondeu ou
  recusou quando devia), ferramenta (nome e argumentos, com apelido de clube
  canonicalizado), numero (o valor do gabarito aparece na resposta) e texto (clube,
  placar ou data).
- **Gabarito calculado na hora**: o caso guarda a chamada esperada e o campo
  (`prob_rebaixamento_pct`), nao o valor. O juiz chama o servico e compara.
- **Dois conjuntos.** 30 casos `dev`, usados para ajustar prompt e ferramentas, e 20
  casos `teste`, escritos antes dos ajustes e nunca usados para ajustar. O numero
  reportado e o do teste.

## Consequencias

O eval roda em 90 segundos e da o mesmo resultado em duas execucoes (temperatura 0 e
semente fixa).

O conjunto de teste se pagou. No dev o `qwen2.5:7b` chegou a 30/30 depois de duas
rodadas de ajuste; no teste, 18/20. Os 100% eram em parte ajuste aos casos.

Li as falhas da primeira rodada uma a uma, e duas eram do juiz, nao do agente: ele nao
aceitava "24 de maio de 2026" como a data 24/05/2026, e o caso de injecao exigia
recusa quando responder com o dado real tambem e correto. Corrigi o juiz e registrei
aqui. Mexer no juiz depois de ver o resultado e arriscado, e por isso cada mudanca
dessas tem um teste proprio em `tests/test_juiz_e_eval.py`.

Limites: 50 casos e pouco (um caso vale 5 pontos percentuais no teste), todos foram
escritos por mim, e o juiz nao mede clareza nem tom da resposta.

## Alternativas consideradas

- **LLM-as-judge:** necessario quando a resposta certa e texto livre. Aqui trocaria uma
  comparacao exata por um julgamento que tambem erra e que custa tokens.
- **Comparar o texto com uma resposta de referencia:** quebra com qualquer parafrase.
- **Valores fixos no arquivo de casos:** ficam errados na proxima rodada do campeonato.