"""API HTTP (FastAPI).

Dois grupos de rotas:
- /dados/...   as mesmas consultas que o agente usa como ferramentas, sem LLM no caminho.
               Deterministicas, rapidas e de graca: quem ja sabe o que quer nao paga token.
- /perguntar   linguagem natural -> agente -> resposta + trilha de auditoria (quais
               ferramentas rodaram, com que argumentos, e o que o verificador achou).

    uvicorn pergunte.api:app --reload      # documentacao interativa em /docs
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from pergunte import __version__, config
from pergunte.agente import Agente
from pergunte.servico import ErroDominio, Servico, obter_servico

app = FastAPI(
    title="Pergunte ao Brasileirao",
    version=__version__,
    description="Agente LLM com tool calling sobre um modelo Dixon-Coles da Serie A.",
)


@lru_cache(maxsize=1)
def obter_agente() -> Agente:
    return Agente()


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=2, max_length=500, examples=["O Santos corre risco de cair?"])
    conversa_id: str | None = Field(default=None, max_length=64,
                                    description="Repita o mesmo id para manter o contexto entre perguntas.")


class Chamada(BaseModel):
    nome: str
    args: dict
    resultado: dict | str
    ok: bool


class RespostaAgente(BaseModel):
    texto: str
    tipo: Literal["resposta", "sem_dados", "recusa"]
    chamadas: list[Chamada]
    aprovada_de_primeira: bool
    motivo_reprovacao: str | None
    numeros_sem_fonte: list[str]
    correcoes: int
    chamadas_llm: int
    tokens_entrada: int
    tokens_saida: int
    latencia_s: float
    custo_usd: float | None
    modelo: str


def _consultar(funcao, *args):
    """ErroDominio -> HTTP 404/422 com o mesmo corpo que o agente recebe."""
    try:
        return funcao(*args)
    except ErroDominio as e:
        status = 404 if e.codigo in {"clube_desconhecido", "fora_da_serie_a", "sem_confrontos"} else 422
        raise HTTPException(status_code=status, detail=e.como_dict()) from e


@app.get("/saude")
def saude(servico: Servico = Depends(obter_servico)) -> dict:
    return {"status": "ok", "temporada": servico.temporada, "dados_ate": f"{servico.dados_ate:%d/%m/%Y}",
            "partidas": len(servico.partidas), "modelo_llm": config.MODELO_PADRAO}


@app.get("/dados/clubes")
def clubes(servico: Servico = Depends(obter_servico)) -> list[str]:
    return servico.clubes()


@app.get("/dados/jogo")
def jogo(mandante: str, visitante: str, servico: Servico = Depends(obter_servico)) -> dict:
    return _consultar(servico.probabilidade_jogo, mandante, visitante)


@app.get("/dados/clubes/{clube}/projecao")
def projecao(clube: str, servico: Servico = Depends(obter_servico)) -> dict:
    return _consultar(servico.projecao_clube, clube)


@app.get("/dados/ranking")
def ranking(criterio: Literal["titulo", "top6", "rebaixamento"], limite: int = Query(5, ge=1, le=20),
            servico: Servico = Depends(obter_servico)) -> dict:
    return _consultar(servico.ranking_projecao, criterio, limite)


@app.get("/dados/classificacao")
def tabela(limite: int = Query(20, ge=1, le=20), servico: Servico = Depends(obter_servico)) -> dict:
    return _consultar(servico.classificacao_atual, limite)


@app.get("/dados/confronto")
def confronto(clube_a: str, clube_b: str, servico: Servico = Depends(obter_servico)) -> dict:
    return _consultar(servico.historico_confronto, clube_a, clube_b)


@app.post("/perguntar", response_model=RespostaAgente)
def perguntar(corpo: Pergunta, agente: Agente = Depends(obter_agente)) -> dict:
    try:
        return agente.perguntar(corpo.pergunta, corpo.conversa_id).como_dict()
    except Exception as e:  # LLM fora do ar, modelo nao baixado, timeout...
        raise HTTPException(status_code=503, detail={"erro": "llm_indisponivel", "mensagem": str(e)[:300]}) from e
