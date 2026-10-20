"""Caminhos, hiperparametros e configuracao por variavel de ambiente."""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = Path(os.environ.get("PERGUNTE_DADOS", RAIZ / "data" / "BRA.csv"))
MANIFESTO = DADOS.with_name("MANIFEST.json")
CASOS = RAIZ / "evals" / "casos.json"
RESULTADOS = RAIZ / "evals" / "resultados"

# Hiperparametros do Dixon-Coles escolhidos na validacao (2014-2016) do projeto
# brasileirao-em-numeros. Nao sao re-tunados aqui: este projeto so CONSOME o modelo.
DC_XI = 0.003
DC_REG = 8.0
N_SIMULACOES = 20000
SEMENTE = 2026

# Modelo de linguagem no formato "provedor:nome". Padrao: modelo aberto local (custo zero).
MODELO_PADRAO = os.environ.get("PERGUNTE_MODELO", "ollama:qwen2.5:7b")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Limites do agente
MAX_CHAMADAS_LLM = 6  # por pergunta; evita loop de ferramenta
MAX_CORRECOES = 1  # quantas vezes o verificador devolve o rascunho antes de recusar

# Preco em USD por milhao de tokens (entrada, saida). Modelo local nao tem preco:
# o custo dele e a maquina, e por isso o relatorio mostra tokens e latencia.
PRECOS_USD_POR_MTOK: dict[str, tuple[float, float]] = {
    "anthropic:claude-haiku-5-5": (0.10, 0.50),
    "anthropic:claude-sonnet-5-5": (2.00, 10.00),
}


def custo_usd(modelo: str, tokens_entrada: int, tokens_saida: int) -> float | None:
    preco = PRECOS_USD_POR_MTOK.get(modelo)
    if preco is None:
        return None
    return (tokens_entrada * preco[0] + tokens_saida * preco[1]) / 1_000_000
