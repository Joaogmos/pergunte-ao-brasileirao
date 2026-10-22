"""Do texto do usuario ("Galo", "São Paulo", "atletico mg") para o nome canonico da base.

O LLM repassa o nome do clube como o usuario escreveu. Resolver isso em codigo, e
nao no prompt, deixa o comportamento testavel: apelido conhecido resolve, nome
ambiguo ("Atletico") devolve as opcoes e nome desconhecido devolve erro. O agente
nunca "chuta" um clube.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

# nome canonico (como esta na base) -> nome para exibir
EXIBICAO = {
    "America-MG": "América-MG", "Athletico-PR": "Athletico-PR", "Atletico-GO": "Atlético-GO",
    "Atletico-MG": "Atlético-MG", "Avai": "Avaí", "Bahia": "Bahia", "Botafogo": "Botafogo",
    "Bragantino": "Bragantino", "CSA": "CSA", "Ceara": "Ceará", "Chapecoense": "Chapecoense",
    "Corinthians": "Corinthians", "Coritiba": "Coritiba", "Criciuma": "Criciúma", "Cruzeiro": "Cruzeiro",
    "Cuiaba": "Cuiabá", "Figueirense": "Figueirense", "Flamengo": "Flamengo", "Fluminense": "Fluminense",
    "Fortaleza": "Fortaleza", "Goias": "Goiás", "Gremio": "Grêmio", "Internacional": "Internacional",
    "Joinville": "Joinville", "Juventude": "Juventude", "Mirassol": "Mirassol", "Nautico": "Náutico",
    "Palmeiras": "Palmeiras", "Parana": "Paraná", "Ponte Preta": "Ponte Preta", "Portuguesa": "Portuguesa",
    "Remo": "Remo", "Santa Cruz": "Santa Cruz", "Santos": "Santos", "Sao Paulo": "São Paulo",
    "Sport": "Sport", "Vasco": "Vasco", "Vitoria": "Vitória",
}

APELIDOS = {
    "Atletico-MG": ["atletico mineiro", "galo", "cam", "atletico de minas"],
    "Athletico-PR": ["athletico", "athletico paranaense", "atletico paranaense", "atletico pr", "furacao", "cap"],
    "Atletico-GO": ["atletico goianiense", "dragao"],
    "America-MG": ["america mineiro", "america", "coelho"],
    "Bragantino": ["red bull bragantino", "rb bragantino", "massa bruta"],
    "Flamengo": ["mengao", "mengo", "fla"],
    "Palmeiras": ["verdao", "alviverde"],
    "Corinthians": ["timao", "coringao"],
    "Santos": ["peixe", "santos fc", "alvinegro praiano"],
    "Sao Paulo": ["spfc", "sao paulo fc", "tricolor paulista"],
    "Vasco": ["vasco da gama", "vascao"],
    "Fluminense": ["flu", "fluzao", "tricolor carioca"],
    "Botafogo": ["fogao", "glorioso"],
    "Internacional": ["inter", "colorado"],
    "Gremio": ["imortal", "tricolor gaucho"],
    "Cruzeiro": ["raposa"],
    "Coritiba": ["coxa"],
    "Chapecoense": ["chape"],
    "Vitoria": ["leao da barra"],
    "Bahia": ["esquadrao"],
    "Sport": ["sport recife", "leao da ilha"],
    "Ceara": ["vozao"],
    "Fortaleza": ["leao do pici"],
    "Cuiaba": ["dourado"],
    "Juventude": ["juve"],
    "Criciuma": ["tigre"],
    "Nautico": ["timbu"],
    "Ponte Preta": ["macaca", "ponte"],
    "Portuguesa": ["lusa"],
    "Remo": ["leao azul"],
}

# termos que servem a mais de um clube: melhor perguntar do que escolher
AMBIGUOS = {
    "atletico": ["Atletico-MG", "Athletico-PR", "Atletico-GO"],
    "tricolor": ["Sao Paulo", "Fluminense", "Gremio", "Bahia"],
    "leao": ["Sport", "Fortaleza", "Vitoria", "Remo"],
    "alvinegro": ["Santos", "Botafogo", "Corinthians", "Atletico-MG"],
}


class ClubeNaoEncontrado(ValueError):
    def __init__(self, texto: str, sugestoes: list[str], ambiguo: bool = False):
        self.texto = texto
        self.sugestoes = sugestoes
        self.ambiguo = ambiguo
        super().__init__(texto)


def normalizar(texto: str) -> str:
    """minusculas, sem acento, sem pontuacao: 'São Paulo F.C.' -> 'sao paulo f c'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).strip()


_INDICE: dict[str, str] = {normalizar(c): c for c in EXIBICAO}
for _clube, _nomes in APELIDOS.items():
    for _nome in _nomes:
        _INDICE[_nome] = _clube


def resolver(texto: str) -> str:
    """Devolve o nome canonico ou levanta ClubeNaoEncontrado com sugestoes."""
    chave = normalizar(texto)
    if chave in _INDICE:
        return _INDICE[chave]
    if chave in AMBIGUOS:
        raise ClubeNaoEncontrado(texto, AMBIGUOS[chave], ambiguo=True)
    # erro de digitacao ("palmeras", "curitiba"): so aceita se houver UM candidato proximo
    proximos = difflib.get_close_matches(chave, list(_INDICE), n=3, cutoff=0.8)
    candidatos = sorted({_INDICE[p] for p in proximos})
    if len(candidatos) == 1:
        return candidatos[0]
    raise ClubeNaoEncontrado(texto, candidatos)


def exibir(canonico: str) -> str:
    return EXIBICAO.get(canonico, canonico)
