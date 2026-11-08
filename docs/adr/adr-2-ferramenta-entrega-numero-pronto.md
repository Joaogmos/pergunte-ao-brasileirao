# ADR-2: A ferramenta entrega o numero pronto; o LLM copia, nao calcula

**Status:** aceito
**Data:** 2026-10-23

## Contexto

LLM erra conta e erra conversao. Se a ferramenta devolve `0.3609` e a resposta precisa
dizer "36,1%", o modelo tem de multiplicar por 100 e arredondar, e cada passo desses e
uma chance de errar que nenhum teste pega com facilidade.

## Decisao

- Cada metodo de `servico.py` devolve o numero no formato em que ele deve aparecer na
  resposta: percentual com 1 casa (`prob_rebaixamento_pct: 36.1`), gols com 2 casas,
  data como `dd/mm/aaaa`, placar como `1x0`.
- Nomes de clube passam por `clubes.resolver` em codigo: apelido conhecido resolve,
  nome ambiguo ("Atletico") devolve as opcoes, nome desconhecido devolve erro.
- Erro de dominio nao vira excecao: vira `{"erro": codigo, "mensagem": ...}`, que o
  modelo le e explica.
- As ferramentas tem o minimo de parametros. `classificacao_atual` nao recebe nada.

## Consequencias

Conferir a resposta vira comparar numeros, o que permite o verificador do ADR-3 e o
juiz do ADR-5. O prompt pode dizer "copie o numero como veio".

O ultimo item veio do eval. Com um parametro `limite` na classificacao, o modelo pedia
`limite=1` para a pergunta "quantos pontos o Palmeiras tem?", recebia so o lider e
respondia que o Palmeiras nao estava na tabela. Tirar o parametro resolveu; a
ferramenta devolve sempre os 20 clubes, o que custa mais tokens de entrada.

O modelo perde liberdade: nao consegue responder "qual a chance de o Santos nao
perder?" somando duas probabilidades, porque a soma nao esta em nenhum resultado e o
verificador reprova. Seria preciso a ferramenta devolver esse campo.

## Alternativas consideradas

- **Devolver probabilidade crua (0 a 1) e deixar o modelo formatar:** mais flexivel e
  mais sujeito a erro, sem jeito simples de conferir.
- **Resolver nome de clube no prompt** (lista de apelidos): nao e testavel, e modelo
  pequeno escolhe um clube parecido em vez de admitir que nao conhece.