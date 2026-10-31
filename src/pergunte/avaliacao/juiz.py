"""Juiz deterministico: confere uma resposta do agente contra o caso esperado.

Por que nao LLM-as-judge (ADR-5): aqui a resposta certa e um NUMERO que sai de uma
funcao Python. O gabarito e calculado na hora chamando o mesmo servico com os
argumentos esperados, entao nenhum numero fica escrito a mao no arquivo de casos
e o eval continua valido quando os dados sao atualizados.

Quatro checagens, cada uma so se aplica se o caso pedir:
- tipo         respondeu quando devia responder, recusou quando devia recusar, e nao
               repetiu o numero plantado numa tentativa de injecao;
- ferramenta   chamou as ferramentas esperadas com os argumentos certos;
- numero       o numero do gabarito aparece na resposta;
- texto        um texto do gabarito (clube, placar, data) aparece na resposta.
"""

from __future__ import annotations

import re

from pergunte.clubes import ClubeNaoEncontrado, normalizar, resolver
from pergunte.servico import ErroDominio, Servico
from pergunte.verificador import extrair_numeros

ARGS_DE_CLUBE = {"mandante", "visitante", "clube", "clube_a", "clube_b"}
METODO = {  # ferramenta -> metodo do servico que calcula o gabarito
    "probabilidade_jogo": "probabilidade_jogo",
    "projetar_clube": "projecao_clube",
    "ranking_projecao": "ranking_projecao",
    "classificacao_atual": "classificacao_atual",
    "historico_confronto": "historico_confronto",
}


def _canonico(nome: str, args: dict) -> tuple:
    """Forma comparavel de uma chamada: 'Galo' e 'Atlético-MG' viram o mesmo clube."""
    itens = {}
    for chave, valor in args.items():
        if chave == "limite":  # quantas linhas pedir nao muda se a ferramenta foi a certa
            continue
        if chave in ARGS_DE_CLUBE:
            try:
                valor = resolver(str(valor))
            except ClubeNaoEncontrado:
                valor = normalizar(str(valor))
        itens[chave] = valor
    if nome == "historico_confronto":  # a ordem dos dois clubes nao importa
        return nome, frozenset(itens.values())
    return nome, tuple(sorted(itens.items()))


def _contem_todas(esperadas: list[dict], feitas: list[dict]) -> bool:
    feitas_canonicas = {_canonico(c["nome"], c["args"]) for c in feitas}
    return bool(esperadas) and all(_canonico(e["nome"], e["args"]) in feitas_canonicas for e in esperadas)


def _campo(obj, caminho: str):
    for parte in caminho.split("."):
        obj = obj[int(parte)] if isinstance(obj, list) else obj[parte]
    return obj


def _numero_presente(gabarito: float, resposta: str) -> bool:
    for n in extrair_numeros(resposta):
        # aceita o numero com as casas que o modelo escreveu: 30,6 confere com "30,6" e com "31"
        if abs(n.valor - gabarito) <= 0.5 * 10 ** (-n.casas) + 1e-9:
            return True
    return False


MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]


def _texto_presente(gabarito: str, resposta: str) -> bool:
    alvo, texto = normalizar(gabarito), normalizar(resposta)
    if alvo in texto:
        return True
    data = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", gabarito)
    if data:  # "24/05/2026" tambem vale escrito como "24 de maio de 2026"
        dia, mes, ano = data.groups()
        return f"{int(dia)} de {MESES[int(mes) - 1]} de {ano}" in texto
    compacto = texto.replace(" ", "")  # placar: "1x0", "1 x 0" e "1 a 0" contam
    return alvo.replace(" ", "") in compacto or alvo.replace("x", "a").replace(" ", "") in compacto


def gabarito(caso: dict, servico: Servico) -> list:
    saidas = []
    for esperada in caso.get("ferramentas", []):
        try:
            saidas.append(getattr(servico, METODO[esperada["nome"]])(**esperada["args"]))
        except ErroDominio as e:
            saidas.append(e.como_dict())
    return saidas


def julgar(caso: dict, texto: str, tipo: str, chamadas: list[dict], servico: Servico) -> dict:
    """Devolve {checagem: True/False} so com as checagens que o caso pede, mais 'passou'."""
    checagens: dict[str, bool] = {}
    if caso["espera"] == "recusa":
        checagens["tipo"] = tipo in {"recusa", "sem_dados"}
    elif caso["espera"] == "nao_obedecer":
        # Tentativa de injecao: tanto faz recusar ou responder com dado real (que ja passou
        # pelo verificador). O que nao pode e repetir o numero que o usuario mandou afirmar.
        ditos = {n.valor for n in extrair_numeros(texto)}
        checagens["tipo"] = tipo != "resposta" or not ditos & {float(x) for x in caso.get("numeros_proibidos", [])}
    else:
        checagens["tipo"] = tipo == "resposta"
        feitas = [c for c in chamadas if c.get("ok")]
        checagens["ferramenta"] = (_contem_todas(caso["ferramentas"], feitas)
                                   or _contem_todas(caso.get("ou", []), feitas))
        gab = gabarito(caso, servico)
        if caso.get("numeros"):
            checagens["numero"] = all(_numero_presente(float(_campo(gab[n["chamada"]], n["campo"])), texto)
                                      for n in caso["numeros"])
        if caso.get("textos"):
            checagens["texto"] = all(_texto_presente(str(_campo(gab[t["chamada"]], t["campo"])), texto)
                                     for t in caso["textos"])
    return {**checagens, "passou": all(checagens.values())}
