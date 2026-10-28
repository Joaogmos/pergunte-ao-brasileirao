import pytest

from pergunte.clubes import ClubeNaoEncontrado, resolver
from pergunte.servico import ErroDominio, conferir_manifesto


@pytest.mark.parametrize(("texto", "esperado"), [
    ("São Paulo", "Sao Paulo"),
    ("GRÊMIO", "Gremio"),
    ("Galo", "Atletico-MG"),
    ("atlético mineiro", "Atletico-MG"),
    ("Furacão", "Athletico-PR"),
    ("Peixe", "Santos"),
    ("Red Bull Bragantino", "Bragantino"),
    ("palmeras", "Palmeiras"),  # erro de digitacao com um unico candidato proximo
])
def test_resolver_entende_acento_apelido_e_erro_de_digitacao(texto, esperado):
    assert resolver(texto) == esperado


def test_nome_ambiguo_devolve_as_opcoes_em_vez_de_escolher():
    with pytest.raises(ClubeNaoEncontrado) as e:
        resolver("Atlético")
    assert e.value.ambiguo
    assert {"Atletico-MG", "Athletico-PR"} <= set(e.value.sugestoes)


def test_clube_desconhecido_nao_vira_um_clube_parecido():
    with pytest.raises(ClubeNaoEncontrado):
        resolver("Real Madrid")


def test_snapshot_e_o_mesmo_do_repositorio_do_modelo():
    assert conferir_manifesto()


def test_probabilidades_de_um_jogo_somam_100(servico):
    r = servico.probabilidade_jogo("Santos", "Palmeiras")
    soma = r["prob_vitoria_mandante_pct"] + r["prob_empate_pct"] + r["prob_vitoria_visitante_pct"]
    assert soma == pytest.approx(100, abs=0.2)  # cada parcela e arredondada para 1 casa
    assert r["mandante"] == "Santos" and r["dados_ate"] == "13/10/2026"


def test_mando_de_campo_muda_a_probabilidade(servico):
    em_casa = servico.probabilidade_jogo("Santos", "Palmeiras")["prob_vitoria_mandante_pct"]
    fora = servico.probabilidade_jogo("Palmeiras", "Santos")["prob_vitoria_visitante_pct"]
    assert em_casa > fora


def test_projecao_repete_os_numeros_do_projeto_original(servico):
    # brasileirao-em-numeros/reports/projecao.json: Santos 8o, 42 pts em 30 jogos
    r = servico.projecao_clube("peixe")
    assert (r["clube"], r["posicao_atual"], r["pontos_atuais"], r["jogos_disputados"]) == ("Santos", 8, 42, 30)
    assert 0 <= r["prob_rebaixamento_pct"] <= 1


def test_clube_fora_da_serie_a_atual_nao_tem_projecao(servico):
    with pytest.raises(ErroDominio) as e:
        servico.projecao_clube("Fortaleza")
    assert e.value.codigo == "fora_da_serie_a"


def test_clube_inexistente_e_ambiguo_viram_erros_distintos(servico):
    with pytest.raises(ErroDominio) as desconhecido:
        servico.probabilidade_jogo("Real Madrid", "Santos")
    with pytest.raises(ErroDominio) as ambiguo:
        servico.projecao_clube("Atlético")
    assert desconhecido.value.codigo == "clube_desconhecido"
    assert ambiguo.value.codigo == "clube_ambiguo" and "Atlético-MG" in ambiguo.value.extra["opcoes"]


def test_historico_e_o_mesmo_visto_dos_dois_lados(servico):
    ab = servico.historico_confronto("Santos", "Corinthians")
    ba = servico.historico_confronto("Corinthians", "Santos")
    assert ab["jogos"] == ba["jogos"] == ab["vitorias_clube_a"] + ab["empates"] + ab["vitorias_clube_b"]
    assert (ab["vitorias_clube_a"], ab["gols_clube_a"]) == (ba["vitorias_clube_b"], ba["gols_clube_b"])


def test_historico_vale_para_clube_que_ja_saiu_da_serie_a(servico):
    assert servico.historico_confronto("Fortaleza", "Ceará")["jogos"] > 0


def test_ranking_vem_ordenado_e_respeita_o_limite(servico):
    r = servico.ranking_projecao("rebaixamento", limite=3)["ranking"]
    probs = [x["prob_pct"] for x in r]
    assert len(r) == 3 and probs == sorted(probs, reverse=True)
    with pytest.raises(ErroDominio):
        servico.ranking_projecao("artilharia")


def test_classificacao_tem_20_clubes_e_zona_com_os_4_ultimos(servico):
    r = servico.classificacao_atual()
    assert [x["posicao"] for x in r["tabela"]] == list(range(1, 21))
    assert r["zona_de_rebaixamento"] == [x["clube"] for x in r["tabela"][-4:]]
