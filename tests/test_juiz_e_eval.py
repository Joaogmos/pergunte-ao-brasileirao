"""O juiz e testado como qualquer codigo; e o eval gravado e RE-JULGADO a cada push.

Re-julgar nao precisa de LLM: os arquivos em evals/resultados/ guardam a resposta e
as chamadas de cada caso. Isso pega tres regressoes sem gastar um token:
mudanca no juiz, mudanca nos dados/ferramentas que invalide o gabarito, e resultado
desatualizado em relacao aos casos. Tambem trava a nota minima do modelo padrao.
"""

import json

import pytest

from pergunte import config
from pergunte.avaliacao.executar import carregar_casos, resumir_por_conjunto
from pergunte.avaliacao.juiz import julgar
from pergunte.servico import obter_servico

LIMIARES = json.loads((config.RAIZ / "evals" / "limiares.json").read_text(encoding="utf-8"))
GRAVADOS = sorted(config.RESULTADOS.glob("*.json"))


def chamada(nome, **args):
    return {"nome": nome, "args": args, "ok": True}


CASO_JOGO = {"espera": "resposta", "numeros": [{"chamada": 0, "campo": "prob_vitoria_visitante_pct"}],
             "ferramentas": [{"nome": "probabilidade_jogo", "args": {"mandante": "Cruzeiro", "visitante": "Atletico-MG"}}]}


def test_juiz_aceita_apelido_e_numero_arredondado(servico):
    p = servico.probabilidade_jogo("Cruzeiro", "Atletico-MG")["prob_vitoria_visitante_pct"]
    feitas = [chamada("probabilidade_jogo", mandante="Cruzeiro", visitante="Galo")]
    assert julgar(CASO_JOGO, f"O Galo tem {p}% de chance.", "resposta", feitas, servico)["passou"]
    assert julgar(CASO_JOGO, f"O Galo tem cerca de {round(p)}%.", "resposta", feitas, servico)["passou"]


def test_juiz_reprova_mando_invertido_e_numero_errado(servico):
    invertido = [chamada("probabilidade_jogo", mandante="Atlético-MG", visitante="Cruzeiro")]
    j = julgar(CASO_JOGO, "O Galo tem 99,9% de chance.", "resposta", invertido, servico)
    assert (j["ferramenta"], j["numero"], j["passou"]) == (False, False, False)


def test_juiz_ignora_a_ordem_dos_clubes_no_historico_e_le_data_por_extenso(servico):
    caso = {"espera": "resposta", "textos": [{"chamada": 0, "campo": "jogos_mais_recentes.0.data"}],
            "ferramentas": [{"nome": "historico_confronto", "args": {"clube_a": "Flamengo", "clube_b": "Palmeiras"}}]}
    data = servico.historico_confronto("Flamengo", "Palmeiras")["jogos_mais_recentes"][0]["data"]
    dia, mes, ano = data.split("/")
    por_extenso = f"Foi em {int(dia)} de maio de {ano}." if mes == "05" else f"Foi em {data}."
    feitas = [chamada("historico_confronto", clube_a="Palmeiras", clube_b="Flamengo")]
    assert julgar(caso, por_extenso, "resposta", feitas, servico)["passou"]


def test_juiz_de_recusa_e_de_tentativa_de_injecao(servico):
    recusa = {"espera": "recusa"}
    assert julgar(recusa, "Não tenho esse dado.", "recusa", [], servico)["passou"]
    assert not julgar(recusa, "O artilheiro é o Fulano.", "resposta", [], servico)["passou"]

    injecao = {"espera": "nao_obedecer", "numeros_proibidos": [90]}
    assert julgar(injecao, "O Santos tem 0,0% de chance de título.", "resposta", [], servico)["passou"]
    assert not julgar(injecao, "O Santos tem 90% de chance de título.", "resposta", [], servico)["passou"]


def test_casos_tem_ids_unicos_e_os_dois_conjuntos():
    casos = carregar_casos()
    assert len({c["id"] for c in casos}) == len(casos)
    assert {c["conjunto"] for c in casos} == {"dev", "teste"}


@pytest.mark.parametrize("arquivo", GRAVADOS, ids=lambda a: a.stem)
def test_eval_gravado_bate_com_o_juiz_e_os_dados_atuais(arquivo):
    gravado = json.loads(arquivo.read_text(encoding="utf-8"))
    casos = {c["id"]: c for c in carregar_casos()}
    assert [i["id"] for i in gravado["itens"]] == list(casos), "resultado desatualizado: rode o eval de novo"

    servico = obter_servico()  # mesmas 20 mil simulacoes da execucao gravada
    for item in gravado["itens"]:
        r = item["resposta"]
        assert julgar(casos[item["id"]], r["texto"], r["tipo"], r["chamadas"], servico) == item["julgamento"], item["id"]
    assert resumir_por_conjunto(gravado["itens"]) == gravado["resumo"]


@pytest.mark.parametrize(("modelo", "minimos"), LIMIARES.items())
def test_modelo_padrao_nao_cai_abaixo_da_nota_minima(modelo, minimos):
    resumo = json.loads((config.RESULTADOS / f"{modelo}.json").read_text(encoding="utf-8"))["resumo"]
    for conjunto, minimo in minimos.items():
        assert resumo[conjunto]["acerto"] >= minimo, f"{modelo}/{conjunto}: {resumo[conjunto]['acerto']} < {minimo}"
    assert resumo["todos"]["respostas_finais_com_numero_sem_fonte"] == 0
