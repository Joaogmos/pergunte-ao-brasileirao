# ADR-1: O modelo estatistico e uma dependencia travada em commit

**Status:** aceito
**Data:** 2026-10-20

## Contexto

As probabilidades vem do Dixon-Coles e da simulacao de Monte Carlo que ja existem no
repositorio `brasileirao-em-numeros`, validados la contra as odds do mercado. Este
projeto nao treina nem valida modelo estatistico: ele coloca uma interface em
linguagem natural na frente de um modelo que ja existe.

## Decisao

- Importar o pacote `brasileirao` direto do GitHub, travado no hash do commit
  (`pyproject.toml`), em vez de copiar o codigo para ca.
- Versionar aqui o mesmo `BRA.csv` com o mesmo `MANIFEST.json`. Um teste confere o
  SHA-256, e outro confere que a projecao do Santos repete o que o repositorio de
  origem publicou (8o lugar, 42 pontos em 30 jogos).
- Hiperparametros (`xi = 0.003`, `reg = 8`) vem da validacao feita la. Nao sao
  re-tunados aqui.

## Consequencias

Os numeros que o agente cita sao reproduziveis: mesmo commit do modelo, mesmo arquivo
de dados, mesma semente, mesmas 20 mil simulacoes. O gabarito do eval e calculado
chamando o mesmo servico, entao atualizar os dados nao quebra os casos.

O custo e um acoplamento: `pip install` precisa de `git` e de acesso ao GitHub (o
Dockerfile instala o git por isso), e mudar o modelo exige trocar o hash aqui.

## Alternativas consideradas

- **Copiar os modulos para este repositorio:** dois lugares para corrigir o mesmo bug.
- **Chamar o outro projeto por HTTP:** um servico a mais para subir sem ganho nenhum,
  porque o ajuste leva 15 ms e a simulacao 0,2 s.
- **Depender de `main` sem travar:** um commit la mudaria os numeros daqui sem aviso.