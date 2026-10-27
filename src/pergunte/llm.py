"""Fabrica do modelo de linguagem. O resto do codigo so conhece a interface do LangChain.

Formato: "provedor:nome", por exemplo "ollama:qwen2.5:7b" ou "anthropic:claude-haiku-5-5".
Trocar de modelo e trocar uma variavel de ambiente (PERGUNTE_MODELO), o que permite
rodar o MESMO eval em modelos diferentes e comparar qualidade x tokens x latencia.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from pergunte import config


def criar_llm(modelo: str = config.MODELO_PADRAO) -> BaseChatModel:
    provedor, _, nome = modelo.partition(":")
    if provedor == "ollama":
        from langchain_ollama import ChatOllama

        # temperature=0 e seed fixa: o eval precisa dar o mesmo resultado em duas execucoes.
        return ChatOllama(model=nome, base_url=config.OLLAMA_URL, temperature=0, seed=config.SEMENTE,
                          num_ctx=8192)
    if provedor == "anthropic":
        from langchain_anthropic import ChatAnthropic  # extra opcional: pip install -e ".[anthropic]"

        return ChatAnthropic(model=nome, max_tokens=1024)
    raise ValueError(f"Provedor desconhecido em '{modelo}'. Use 'ollama:<nome>' ou 'anthropic:<nome>'.")
