# ADR-6: O modelo padrao e aberto e roda local; o provedor e trocavel

**Status:** aceito
**Data:** 2026-10-26

## Contexto

Desenvolver um agente e rodar o eval dezenas de vezes. Com API paga, cada rodada custa
dinheiro e depende de chave; e o resultado nao e reproduzivel por quem clonar o
repositorio sem conta no provedor.

## Decisao

- Padrao: `qwen2.5:7b` via Ollama, numa GPU de 8 GB.
- O modelo e uma string `provedor:nome` em `PERGUNTE_MODELO`. `llm.py` e o unico lugar
  que conhece provedores (Ollama e, como extra opcional, Anthropic).
- Temperatura 0 e semente fixa, para o eval repetir.
- O eval grava tokens de entrada e saida, chamadas ao modelo e latencia por pergunta.
  Custo em dolar so e calculado para modelo com preco em `config.PRECOS_USD_POR_MTOK`.

## Consequencias

Rodei o mesmo eval em dois modelos abertos. No teste: `qwen2.5:7b` 18/20 e
`llama3.2:3b` 5/20, com o menor respondendo em metade do tempo (0,76 s contra 1,62 s
de mediana). O modelo de 3B chama a ferramenta certa em 72% dos casos, mas le o
resultado errado. Para esta tarefa ele nao serve, mesmo sendo mais rapido.

Cada pergunta consome em media 3.008 tokens de entrada e 80 de saida. A entrada domina
porque o schema das 6 ferramentas e o prompt de sistema (cerca de 1.300 tokens) sao
reenviados em cada uma das 1,9 chamadas. E onde cache de prompt daria retorno.

O caminho Anthropic esta implementado e nao foi exercitado no eval: nao ha numero
dele no README.

Achado de percurso: com a ferramenta chamada `projecao_clube`, o Ollama devolvia
resposta vazia, sem texto e sem chamada, embora o modelo gerasse 26 tokens. Renomear
para `projetar_clube` resolveu. Nao investiguei a causa no parser do Ollama. O grafo
ja tratava o caso (resposta vazia e reprovada e termina em recusa), entao a falha era
segura, mas silenciosa: so apareceu porque havia um caso de eval para ela.

## Alternativas consideradas

- **So API paga:** melhor qualidade provavel, mas eval com custo e sem reproducao local.
- **Abstrair provedores com LiteLLM:** uma dependencia a mais para dois provedores.