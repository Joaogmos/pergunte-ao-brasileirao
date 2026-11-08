# ADR-3: Um verificador em codigo confere a origem de cada numero da resposta

**Status:** aceito
**Data:** 2026-10-24

## Contexto

O requisito do projeto e "nao inventar numero". Pedir isso no prompt nao garante nada:
e uma instrucao, e o modelo pode ignorar. Era preciso algo que conferisse.

## Decisao

`verificador.py` e uma funcao pura. Ela extrai os numeros do rascunho (formato
brasileiro, `20 mil`, datas, placares), e procura cada um nos resultados das
ferramentas da conversa ou na pergunta do usuario. No grafo:

- rascunho sem nenhuma chamada de ferramenta no turno e reprovado;
- rascunho com numero sem fonte e reprovado e volta ao modelo com a lista dos numeros;
- na segunda reprovacao o usuario recebe uma mensagem fixa de recusa. Nada do texto
  do modelo passa.

Arredondar e aceito ("36%" confere com 36,1); trocar o numero nao ("36,5%" nao confere).

## Consequencias

Medido nos 50 casos com `qwen2.5:7b`: o verificador reprovou 2 rascunhos (1 por numero
sem fonte, 1 por falta de ferramenta) e os 2 terminaram em resposta correta. Com o
verificador desligado, a mesma pergunta sobre o Vasco saiu com "20% de chance de
terminar entre os seis primeiros", quando a ferramenta dizia 0,2%. Sao poucos casos:
neste eval o modelo quase sempre copia certo, e o verificador e uma rede para o resto.
Ele custa uma chamada a mais ao modelo so quando reprova.

O que ele NAO pega, e o eval mostra:

- **Atribuicao.** Confere de onde o numero veio, nao a quem ele pertence. O
  `llama3.2:3b` respondeu "O Palmeiras tem 32 pontos" (sao 63). O 32 esta na tabela, e
  de outro clube, e passou.
- **Texto sem numero.** "O artilheiro e o Flamengo" nao tem numero para conferir.
- **Numero por extenso** ("dois gols") e conta certa feita pelo modelo (que reprova).
- **Numero vindo da pergunta.** O que o usuario escreveu conta como fonte, para o
  modelo poder repetir "em 2023". Um usuario pode plantar um numero assim; ha um caso
  de eval para isso.

## Alternativas consideradas

- **Um segundo LLM como revisor:** custa uma chamada em toda resposta e pode errar do
  mesmo jeito que o primeiro. Faz sentido para atribuicao, que a regex nao alcanca; e a
  evolucao natural.
- **Saida estruturada** (o modelo devolve referencias aos campos e o codigo monta a
  frase): garante origem e atribuicao, mas a resposta vira um template. E o caminho se
  o requisito for erro zero.
- **So o prompt:** foi o que a ablacao mediu.