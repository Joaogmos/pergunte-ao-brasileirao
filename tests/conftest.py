"""Fixtures compartilhadas.

`LLMRoteirizado` e um modelo de mentira: devolve, em ordem, as mensagens que o
teste escreveu. Com ele da para testar o GRAFO (roteamento, verificador, recusa,
memoria) de forma deterministica, sem GPU, sem rede e sem custo -- e para simular
de proposito um modelo que alucina.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from pergunte.agente import Agente
from pergunte.servico import Servico


class LLMRoteirizado(BaseChatModel):
    roteiro: list[Any]
    vistos: list[Any] = []

    @property
    def _llm_type(self) -> str:
        return "roteirizado"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.vistos.append(list(messages))
        mensagem = self.roteiro.pop(0)
        return ChatResult(generations=[ChatGeneration(message=mensagem)])


def pedir(nome: str, **args) -> AIMessage:
    """Mensagem do modelo pedindo UMA ferramenta."""
    return AIMessage("", tool_calls=[{"name": nome, "args": args, "id": f"id-{nome}-{len(args)}"}],
                     usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110})


def dizer(texto: str) -> AIMessage:
    return AIMessage(texto, usage_metadata={"input_tokens": 120, "output_tokens": 20, "total_tokens": 140})


@pytest.fixture(scope="session")
def servico() -> Servico:
    return Servico(n_simulacoes=2000)  # menos simulacoes: os testes nao dependem da 3a casa decimal


@pytest.fixture
def criar_agente(servico):
    def _criar(*roteiro) -> tuple[Agente, LLMRoteirizado]:
        llm = LLMRoteirizado(roteiro=list(roteiro), vistos=[])
        return Agente(modelo="teste:roteirizado", llm=llm, servico=servico), llm

    return _criar
