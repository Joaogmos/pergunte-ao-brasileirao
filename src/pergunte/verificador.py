"""Guardrail deterministico: todo numero da resposta tem de ter vindo de uma ferramenta.

O prompt PEDE ao modelo para nao inventar numero. Este modulo CONFERE. Ele extrai
os numeros do texto da resposta e procura cada um nos resultados das ferramentas
(ou na propria pergunta do usuario). Numero sem fonte reprova o rascunho.

Sem LLM aqui de proposito: e uma funcao pura, barata, testavel e que nao alucina.

Limites conhecidos (documentados no README):
- numero escrito por extenso ("dois gols") nao e conferido;
- confere a ORIGEM do numero, nao se ele foi atribuido ao clube certo;
- conta feita pelo modelo (somar duas probabilidades) reprova, mesmo se certa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")
_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+")
# "top 6", "G-4", "Z4": nomes de zona da tabela, nao dados.
_ZONAS = re.compile(r"\b(?:top|g|z)[\s-]?\d{1,2}\b", re.IGNORECASE)


@dataclass(frozen=True)
class Numero:
    valor: float
    casas: int  # casas decimais como escrito: "52,3" -> 1
    texto: str


@dataclass
class Verificacao:
    aprovada: bool
    sem_fonte: list[str] = field(default_factory=list)


def extrair_numeros(texto: str) -> list[Numero]:
    """Le numeros no formato brasileiro (52,3 / 20.000) e tambem 52.3 e '20 mil'."""
    texto = _ZONAS.sub(" ", texto)
    achados = []
    for m in _NUMERO.finditer(texto):
        bruto = m.group().rstrip(".,")
        if "," in bruto:  # virgula decimal; ponto so pode ser milhar
            inteiro, _, decimal = bruto.replace(".", "").partition(",")
            valor, casas = float(f"{inteiro}.{decimal}"), len(decimal)
        elif _MILHAR.fullmatch(bruto):
            valor, casas = float(bruto.replace(".", "")), 0
        elif bruto.count(".") == 1:  # ponto decimal (o modelo as vezes escreve assim)
            valor, casas = float(bruto), len(bruto.split(".")[1])
        elif "." in bruto:  # "13.10.2026": trata como partes separadas
            achados.extend(Numero(float(p), 0, p) for p in bruto.split("."))
            continue
        else:
            valor, casas = float(bruto), 0
        if re.match(r"\s*mil\b", texto[m.end():], re.IGNORECASE):
            valor, casas = valor * 1000, 0
        achados.append(Numero(valor, casas, bruto))
    return achados


def numeros_dos_fatos(obj) -> list[float]:
    """Todo numero que aparece num resultado de ferramenta: folhas numericas e dentro de textos."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, int | float):
        return [float(obj)]
    if isinstance(obj, str):
        return [n.valor for n in extrair_numeros(obj)]
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in numeros_dos_fatos(x)]
    if isinstance(obj, list | tuple):
        return [v for x in obj for v in numeros_dos_fatos(x)]
    return []


def _tem_fonte(n: Numero, fontes: list[float]) -> bool:
    # "52%" confere com 52,3 (arredondou); "52,3%" so confere com 52,3.
    tolerancia = 0.5 * 10 ** (-n.casas) + 1e-9
    return any(abs(f - n.valor) <= tolerancia for f in fontes)


def verificar(resposta: str, fatos: list, perguntas: list[str]) -> Verificacao:
    fontes = numeros_dos_fatos(fatos) + [n.valor for p in perguntas for n in extrair_numeros(p)]
    sem_fonte = [n.texto for n in extrair_numeros(resposta) if not _tem_fonte(n, fontes)]
    return Verificacao(aprovada=not sem_fonte, sem_fonte=sem_fonte)
