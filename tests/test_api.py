import pytest
from fastapi.testclient import TestClient

from pergunte.api import app, obter_agente
from pergunte.servico import obter_servico
from tests.conftest import dizer, pedir


@pytest.fixture
def cliente(servico):
    app.dependency_overrides[obter_servico] = lambda: servico
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_saude_informa_ate_quando_vao_os_dados(cliente):
    r = cliente.get("/saude").json()
    assert r["status"] == "ok" and r["temporada"] == 2026 and r["dados_ate"] == "13/10/2026"


def test_rotas_de_dados_respondem_sem_llm(cliente):
    jogo = cliente.get("/dados/jogo", params={"mandante": "Santos", "visitante": "Palmeiras"})
    assert jogo.status_code == 200 and jogo.json()["mandante"] == "Santos"
    assert cliente.get("/dados/clubes/galo/projecao").json()["clube"] == "Atlético-MG"
    assert len(cliente.get("/dados/ranking", params={"criterio": "titulo", "limite": 3}).json()["ranking"]) == 3
    assert len(cliente.get("/dados/classificacao").json()["tabela"]) == 20
    assert cliente.get("/dados/confronto", params={"clube_a": "Santos", "clube_b": "Corinthians"}).json()["jogos"] > 0


def test_erro_de_dominio_vira_404_ou_422_com_o_codigo(cliente):
    desconhecido = cliente.get("/dados/clubes/Real Madrid/projecao")
    assert desconhecido.status_code == 404 and desconhecido.json()["detail"]["erro"] == "clube_desconhecido"
    ambiguo = cliente.get("/dados/clubes/Atlético/projecao")
    assert ambiguo.status_code == 422 and ambiguo.json()["detail"]["erro"] == "clube_ambiguo"
    assert cliente.get("/dados/ranking", params={"criterio": "artilharia"}).status_code == 422  # validacao do FastAPI


def test_perguntar_devolve_resposta_e_trilha_de_auditoria(cliente, criar_agente):
    agente, _ = criar_agente(pedir("classificacao_atual"), dizer("O líder é o Flamengo."))
    app.dependency_overrides[obter_agente] = lambda: agente
    r = cliente.post("/perguntar", json={"pergunta": "Quem lidera?"})

    corpo = r.json()
    assert r.status_code == 200 and corpo["tipo"] == "resposta" and "Flamengo" in corpo["texto"]
    assert corpo["chamadas"][0]["nome"] == "classificacao_atual" and corpo["custo_usd"] is None


def test_pergunta_vazia_e_rejeitada_e_llm_fora_do_ar_vira_503(cliente, criar_agente):
    agente, _ = criar_agente()  # roteiro vazio: a primeira chamada ao "modelo" estoura
    app.dependency_overrides[obter_agente] = lambda: agente
    assert cliente.post("/perguntar", json={"pergunta": ""}).status_code == 422
    r = cliente.post("/perguntar", json={"pergunta": "Quem lidera?"})
    assert r.status_code == 503 and r.json()["detail"]["erro"] == "llm_indisponivel"
