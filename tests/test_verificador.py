import pytest

from pergunte.verificador import extrair_numeros, numeros_dos_fatos, verificar

FATOS = [{"clube": "Santos", "prob_rebaixamento_pct": 0.1, "prob_top6_pct": 7.1, "pontos_atuais": 42,
          "simulacoes": 20000, "dados_ate": "13/10/2026", "placar_mais_provavel": "1x0"}]


@pytest.mark.parametrize(("texto", "valores"), [
    ("chance de 52,3%", [52.3]),
    ("chance de 52.3%", [52.3]),  # o modelo as vezes usa ponto decimal
    ("20.000 simulações", [20000]),
    ("20 mil simulações", [20000]),
    ("placar de 2x1", [2, 1]),
    ("em 13/10/2026", [13, 10, 2026]),
    ("42 pontos.", [42]),  # ponto final nao e separador decimal
])
def test_extrai_numeros_no_formato_brasileiro(texto, valores):
    assert [n.valor for n in extrair_numeros(texto)] == valores


def test_nome_de_zona_da_tabela_nao_conta_como_numero():
    assert extrair_numeros("vaga no top 6, longe do Z4 e do G-4") == []


def test_fatos_incluem_numeros_dentro_de_textos():
    assert {13, 10, 2026, 1, 0, 42, 7.1} <= set(numeros_dos_fatos(FATOS))


def test_resposta_com_numeros_da_ferramenta_passa():
    v = verificar("O Santos tem 42 pontos e 7,1% de chance de top 6 (20 mil simulações).", FATOS, [])
    assert v.aprovada


def test_arredondar_passa_mas_trocar_o_numero_nao():
    assert verificar("cerca de 7% de chance", FATOS, []).aprovada  # 7,1 escrito sem casa decimal
    v = verificar("7,5% de chance", FATOS, [])  # com 1 casa, tem de bater na casa
    assert not v.aprovada and v.sem_fonte == ["7,5"]


def test_numero_inventado_e_apontado():
    v = verificar("O Santos tem 42 pontos e 35% de chance de título.", FATOS, [])
    assert not v.aprovada and v.sem_fonte == ["35"]


def test_numero_que_o_usuario_citou_pode_ser_repetido():
    assert verificar("Em 2023 não tenho esse dado.", FATOS, ["E em 2023?"]).aprovada
    assert not verificar("Em 2023 não tenho esse dado.", FATOS, ["E antes?"]).aprovada


def test_resposta_sem_numero_passa():
    assert verificar("O Santos está em situação tranquila.", FATOS, []).aprovada
