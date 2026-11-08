# ADR-7: O CI re-julga o eval gravado em vez de chamar um LLM

**Status:** aceito
**Data:** 2026-11-05

## Contexto

O eval precisa de um LLM. O runner gratuito do GitHub Actions nao tem GPU: um modelo
de 7B em CPU levaria dezenas de minutos por execucao, e usar API paga no CI exigiria
um segredo e gastaria a cada push.

## Decisao

- `executar.py` grava em `evals/resultados/<modelo>.json` tudo o que o juiz precisa:
  texto da resposta, tipo e chamadas de ferramenta de cada caso.
- No CI, `tests/test_juiz_e_eval.py` re-julga esses arquivos com o juiz e os dados
  atuais e exige: mesmo veredito caso a caso, mesmo resumo, mesma lista de casos, e
  nota do modelo padrao acima de `evals/limiares.json` (dev 95%, teste 85%).
- Um passo separado confere que `evals/RESULTADOS.md` e o que o gerador produz.

## Consequencias

Sem gastar token, o CI pega: mudanca no juiz que altere algum veredito, mudanca nos
dados ou nas ferramentas que invalide o gabarito, caso novo sem resultado gravado, e
tabela do README desatualizada.

O que o CI NAO pega: mudanca de prompt ou de descricao de ferramenta. O arquivo
gravado continua com as respostas antigas e o teste continua verde. A regra e manual:
mexeu em `agente.py` ou `ferramentas.py`, roda o eval ao vivo e versiona o JSON novo.
E a principal lacuna do desenho.

## Alternativas consideradas

- **Rodar o eval ao vivo no CI com modelo pequeno em CPU:** o unico que caberia no
  tempo (3B) acerta 25% do teste. Mediria outra coisa.
- **API paga no CI, so em PR que toque prompt:** e a evolucao certa, com um limite de
  gasto. Fecha a lacuna acima.