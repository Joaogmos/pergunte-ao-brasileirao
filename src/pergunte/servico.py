"""Camada de dominio: tudo que o agente pode saber sobre o Brasileirao sai daqui.

Carrega o snapshot de partidas, ajusta o Dixon-Coles uma vez e roda a simulacao
de Monte Carlo do resto da temporada. Cada metodo devolve um dict pronto para
virar JSON, com os numeros JA no formato em que devem aparecer na resposta
(percentual com 1 casa). O LLM copia, nao calcula (ADR-3).

O modelo estatistico e importado do pacote `brasileirao` (outro repositorio).
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from brasileirao.dados import ler_bruto, limpar, validar
from brasileirao.modelos.dixon_coles import DixonColes
from brasileirao.simulacao import jogos_restantes, simular, zonas
from brasileirao.tabela import classificacao

from pergunte import config
from pergunte.clubes import ClubeNaoEncontrado, exibir, resolver

CRITERIOS = {"titulo": "titulo", "top6": "top6", "rebaixamento": "rebaixamento"}


class ErroDominio(Exception):
    """Pergunta valida na forma, mas sem resposta nos dados. Vira {"erro": ...} na ferramenta."""

    def __init__(self, codigo: str, mensagem: str, **extra):
        self.codigo = codigo
        self.mensagem = mensagem
        self.extra = extra
        super().__init__(mensagem)

    def como_dict(self) -> dict:
        return {"erro": self.codigo, "mensagem": self.mensagem, **self.extra}


def _pct(p: float) -> float:
    return round(float(p) * 100, 1)


class Servico:
    def __init__(self, caminho: Path = config.DADOS, n_simulacoes: int = config.N_SIMULACOES):
        dados = limpar(ler_bruto(caminho))
        validar(dados)
        self.partidas = dados.partidas
        self.temporada = int(self.partidas["temporada"].max())
        self.jogados = self.partidas[self.partidas["temporada"] == self.temporada]
        self.dados_ate = self.jogados["data"].max()
        self.primeira_temporada = int(self.partidas["temporada"].min())
        self.clubes_atuais = sorted(set(self.jogados["mandante"]) | set(self.jogados["visitante"]))

        self.modelo = DixonColes(xi=config.DC_XI, reg=config.DC_REG).ajustar(self.partidas)
        self.tabela = classificacao(self.jogados).set_index("clube")
        self.restantes = jogos_restantes(self.jogados)
        self.n_simulacoes = n_simulacoes
        sim = simular(self.modelo, self.jogados, self.restantes, n=n_simulacoes, semente=config.SEMENTE)
        self.posicoes = sim["posicoes"]
        self.resumo = sim["resumo"]
        self.zonas = zonas(self.posicoes)

    # ------------------------------------------------------------------ apoio

    def _clube(self, texto: str) -> str:
        try:
            return resolver(texto)
        except ClubeNaoEncontrado as e:
            sugestoes = [exibir(s) for s in e.sugestoes]
            if e.ambiguo:
                raise ErroDominio("clube_ambiguo", f"'{texto}' pode ser mais de um clube. Pergunte qual.",
                                  opcoes=sugestoes) from e
            raise ErroDominio("clube_desconhecido", f"Nao ha clube '{texto}' na base da Serie A.",
                              parecidos=sugestoes) from e

    def _clube_atual(self, texto: str) -> str:
        clube = self._clube(texto)
        if clube not in self.clubes_atuais:
            raise ErroDominio(
                "fora_da_serie_a",
                f"{exibir(clube)} nao disputa a Serie A de {self.temporada}; "
                "previsoes e projecoes so existem para os 20 clubes da temporada atual.",
            )
        return clube

    def _contexto(self) -> dict:
        return {"temporada": self.temporada, "dados_ate": f"{self.dados_ate:%d/%m/%Y}"}

    # ------------------------------------------------------------------ consultas

    def clubes(self) -> list[str]:
        return [exibir(c) for c in self.clubes_atuais]

    def probabilidade_jogo(self, mandante: str, visitante: str) -> dict:
        casa, fora = self._clube_atual(mandante), self._clube_atual(visitante)
        if casa == fora:
            raise ErroDominio("mesmo_clube", "Mandante e visitante sao o mesmo clube.")
        jogo = pd.DataFrame({"mandante": [casa], "visitante": [fora]})
        lam, mu = self.modelo.taxas(jogo)
        placares = self.modelo.matriz_placares(lam, mu)[0]
        p_casa, p_empate, p_fora = self.modelo.prever(jogo)[0]
        gc, gf = np.unravel_index(placares.argmax(), placares.shape)

        saida = {
            "mandante": exibir(casa),
            "visitante": exibir(fora),
            "prob_vitoria_mandante_pct": _pct(p_casa),
            "prob_empate_pct": _pct(p_empate),
            "prob_vitoria_visitante_pct": _pct(p_fora),
            "gols_esperados_mandante": round(float(lam[0]), 2),
            "gols_esperados_visitante": round(float(mu[0]), 2),
            "placar_mais_provavel": f"{gc}x{gf}",
            "prob_placar_mais_provavel_pct": _pct(placares[gc, gf]),
            **self._contexto(),
        }
        feito = self.jogados[(self.jogados["mandante"] == casa) & (self.jogados["visitante"] == fora)]
        if len(feito):
            j = feito.iloc[0]
            saida["aviso"] = (f"Este jogo ja foi disputado em {j['data']:%d/%m/%Y}: "
                              f"{exibir(casa)} {j['gols_mandante']}x{j['gols_visitante']} {exibir(fora)}. "
                              "As probabilidades acima sao o que o modelo diria hoje.")
        return saida

    def projecao_clube(self, clube: str) -> dict:
        c = self._clube_atual(clube)
        t, r, z = self.tabela.loc[c], self.resumo.loc[c], self.zonas.loc[c]
        return {
            "clube": exibir(c),
            "posicao_atual": int(t["posicao"]),
            "pontos_atuais": int(t["pontos"]),
            "jogos_disputados": int(t["jogos"]),
            "pontos_esperados_no_fim": round(float(r["pontos_esperados"]), 1),
            "faixa_provavel_de_pontos": f"de {int(r['pontos_p05'])} a {int(r['pontos_p95'])} "
                                        "(intervalo de 90% das simulacoes)",
            "posicao_final_mais_provavel": int(self.posicoes.loc[c].idxmax()),
            "prob_titulo_pct": _pct(z["titulo"]),
            "prob_top6_pct": _pct(z["top6"]),
            "prob_rebaixamento_pct": _pct(z["rebaixamento"]),
            "simulacoes": self.n_simulacoes,
            **self._contexto(),
        }

    def ranking_projecao(self, criterio: str, limite: int = 5) -> dict:
        if criterio not in CRITERIOS:
            raise ErroDominio("criterio_invalido", "Use 'titulo', 'top6' ou 'rebaixamento'.")
        ordenado = self.zonas[CRITERIOS[criterio]].sort_values(ascending=False, kind="stable")
        limite = max(1, min(int(limite), len(ordenado)))
        return {
            "criterio": criterio,
            "ranking": [
                {"clube": exibir(c), "prob_pct": _pct(p), "pontos_atuais": int(self.tabela.loc[c, "pontos"])}
                for c, p in ordenado.head(limite).items()
            ],
            "simulacoes": self.n_simulacoes,
            **self._contexto(),
        }

    def classificacao_atual(self, limite: int = 20) -> dict:
        limite = max(1, min(int(limite), len(self.tabela)))
        linhas = self.tabela.reset_index().head(limite)
        return {
            "tabela": [
                {"posicao": int(x["posicao"]), "clube": exibir(x["clube"]), "pontos": int(x["pontos"]),
                 "jogos": int(x["jogos"]), "vitorias": int(x["vitorias"]), "empates": int(x["empates"]),
                 "derrotas": int(x["derrotas"]), "saldo": int(x["saldo"])}
                for _, x in linhas.iterrows()
            ],
            "zona_de_rebaixamento": [exibir(c) for c in self.tabela.index[-4:]],
            **self._contexto(),
        }

    def historico_confronto(self, clube_a: str, clube_b: str, ultimos: int = 5) -> dict:
        a, b = self._clube(clube_a), self._clube(clube_b)
        if a == b:
            raise ErroDominio("mesmo_clube", "Os dois clubes sao o mesmo.")
        p = self.partidas
        jogos = p[((p["mandante"] == a) & (p["visitante"] == b)) | ((p["mandante"] == b) & (p["visitante"] == a))]
        if jogos.empty:
            raise ErroDominio("sem_confrontos", f"{exibir(a)} e {exibir(b)} nao se enfrentaram na Serie A "
                              f"entre {self.primeira_temporada} e {self.temporada}.")
        gols_a = np.where(jogos["mandante"] == a, jogos["gols_mandante"], jogos["gols_visitante"])
        gols_b = np.where(jogos["mandante"] == b, jogos["gols_mandante"], jogos["gols_visitante"])
        recentes = jogos.sort_values("data", ascending=False).head(max(1, min(int(ultimos), 10)))
        return {
            "clube_a": exibir(a),
            "clube_b": exibir(b),
            "periodo": f"Serie A de {self.primeira_temporada} a {self.temporada}",
            "jogos": int(len(jogos)),
            "vitorias_clube_a": int((gols_a > gols_b).sum()),
            "empates": int((gols_a == gols_b).sum()),
            "vitorias_clube_b": int((gols_a < gols_b).sum()),
            "gols_clube_a": int(gols_a.sum()),
            "gols_clube_b": int(gols_b.sum()),
            "jogos_mais_recentes": [
                {"data": f"{j['data']:%d/%m/%Y}",
                 "placar": f"{exibir(j['mandante'])} {j['gols_mandante']}x{j['gols_visitante']} "
                           f"{exibir(j['visitante'])}"}
                for _, j in recentes.iterrows()
            ],
        }


def conferir_manifesto(caminho: Path = config.DADOS) -> bool:
    """O CSV e exatamente o snapshot registrado? (mesmo SHA-256 do repositorio do modelo)"""
    esperado = json.loads(config.MANIFESTO.read_text(encoding="utf-8"))["sha256"]
    return hashlib.sha256(caminho.read_bytes()).hexdigest() == esperado


@lru_cache(maxsize=1)
def obter_servico() -> Servico:
    return Servico()
