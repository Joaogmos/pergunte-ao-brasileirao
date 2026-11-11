# Resultados do eval

Gerado por `python -m pergunte.avaliacao.relatorio` a partir de `evals/resultados/*.json`.
`dev` sao os 30 casos usados para ajustar prompt e ferramentas; `teste` sao 20 casos escritos
antes dos ajustes e nunca usados para ajustar. O numero que vale e o do teste.

## Qualidade

| Modelo | Verificador | Teste | Dev | Ferramenta certa | Numero certo | Recusa certa |
|---|---|---|---|---|---|---|
| `ollama:qwen2.5:7b` | ligado | 18/20 (90%) | 30/30 (100%) | 100% | 97% | 91% |
| `ollama:qwen2.5:7b` | desligado | 18/20 (90%) | 30/30 (100%) | 100% | 97% | 91% |
| `ollama:llama3.2:3b` | ligado | 5/20 (25%) | 11/30 (37%) | 72% | 22% | 64% |

Ferramenta, numero e recusa sao medidos nos 50 casos (dev + teste).

## Custo e latencia (50 casos)

| Modelo | Verificador | Chamadas ao LLM | Tokens entrada | Tokens saida | Latencia mediana | Latencia p95 |
|---|---|---|---|---|---|---|
| `ollama:qwen2.5:7b` | ligado | 1,90 | 3008 | 80 | 1,62 s | 3,18 s |
| `ollama:qwen2.5:7b` | desligado | 1,88 | 2973 | 79 | 1,63 s | 3,20 s |
| `ollama:llama3.2:3b` | ligado | 2,02 | 2357 | 47 | 0,76 s | 1,39 s |

Medias por pergunta. Modelos locais (Ollama) nao tem preco por token; a maquina esta em cada JSON.

## O que o verificador fez (50 casos)

| Modelo | Verificador | Rascunhos reprovados | Por numero sem fonte | Por falta de ferramenta | Viraram acerto | Respostas finais com numero sem fonte |
|---|---|---|---|---|---|---|
| `ollama:qwen2.5:7b` | ligado | 2 | 1 | 1 | 2 | 0 |
| `ollama:qwen2.5:7b` | desligado | 1 | 0 | 1 | 1 | 1 |
| `ollama:llama3.2:3b` | ligado | 3 | 0 | 3 | 2 | 0 |

## Casos que falharam

**`ollama:qwen2.5:7b`: 2 falha(s)**

- `t-jogo-03` (numero): Quantos gols o Coritiba deve sofrer jogando fora de casa contra o Athletico-PR? -> "De acordo com o modelo estatístico, o Coritiba deve sofrer aproximadamente 1,0 gols jogando fora de casa contra o Athletico-PR, com uma prob"
- `t-rec-02` (tipo): Quem vai ganhar a Libertadores este ano? -> "De acordo com as projeções, o Flamengo e o Palmeiras têm as maiores chances de conquistar uma vaga para a Libertadores no fim da temporada d"

**`ollama:qwen2.5:7b` (verificador desligado): 2 falha(s)**

- `t-jogo-03` (numero): Quantos gols o Coritiba deve sofrer jogando fora de casa contra o Athletico-PR? -> "De acordo com o modelo estatístico, o Coritiba deve sofrer aproximadamente 1,0 gols jogando fora de casa contra o Athletico-PR, com uma prob"
- `t-rec-02` (tipo): Quem vai ganhar a Libertadores este ano? -> "De acordo com as projeções, o Flamengo e o Palmeiras têm as maiores chances de conquistar uma vaga para a Libertadores no fim da temporada d"

**`ollama:llama3.2:3b`: 34 falha(s)**

- `jogo-02` (numero): O Flamengo recebe o Corinthians. Qual a probabilidade de empate? -> "Chamando fora_do_escopo, pois o jogo já foi disputado."
- `jogo-03` (numero): Qual a chance do Galo ganhar do Cruzeiro jogando fora de casa? -> "Fora_do_escopo"
- `jogo-06` (numero): São Paulo e Fluminense jogam no Morumbi, casa do São Paulo. Qual a chance de vitória do São Paulo? -> "Chamada fora_do_escopo. Não há dados disponíveis sobre a probabilidade de vitória do São Paulo em um jogo específico contra o Fluminense."
- `projecao-01` (numero): O Corinthians corre risco de rebaixamento? -> "Chamando fora_do_escopo."
- `projecao-02` (ferramenta, numero): Qual a chance de o Flamengo ser campeão? -> "Fora_do_escopo"
- `projecao-03` (numero): Quantos pontos o Santos deve fazer até o fim do campeonato? -> "O Santos deve fazer entre 47 e 59 pontos até o fim do campeonato, com uma probabilidade de 90% de estar dentro dessa faixa."
- `projecao-04` (numero): O Bahia consegue terminar no top 6 e ir para a Libertadores? -> "Chamando fora_do_escopo."
- `projecao-05` (ferramenta, numero): Qual a chance do Peixe cair este ano? -> "Fora_do_escopo. Não há ferramenta disponível para fornecer informações sobre a chance de um clube cair de posição na tabela."
- `tabela-02` (texto): Quais são os dois times com mais chance de cair? -> "Fora_do_escopo. Não há ferramentas disponíveis para fornecer informações sobre a probabilidade de rebaixamento de times específicos na Série"
- `tabela-04` (texto): Quem está na zona de rebaixamento hoje? -> "Até a data de 13/10/2026, os clubes na zona de rebaixamento estão: Internacional, Grêmio e Remo."
- `tabela-05` (numero): Quantos pontos o Palmeiras tem hoje? -> "O Palmeiras tem 32 pontos hoje."
- `historico-02` (numero): Quantas vezes o Grêmio venceu o Internacional na Série A desde 2012? -> "Fora_do_escopo. Não consegui encontrar informações sobre o histórico de jogos entre Grêmio e Internacional na Série A desde 2012."
- ... e mais 22 (ver o JSON)
