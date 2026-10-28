"""Testes do grafo com um LLM roteirizado. Cada teste e um caminho do diagrama em agente.py."""

from langchain_core.messages import HumanMessage, ToolMessage

from pergunte import config
from pergunte.agente import MSG_NAO_VERIFICAVEL, VERIFICADOR
from pergunte.ferramentas import MOTIVOS_RECUSA
from tests.conftest import dizer, pedir


def test_caminho_feliz_chama_a_ferramenta_e_responde_com_o_numero_dela(criar_agente, servico):
    risco = servico.projecao_clube("Corinthians")["prob_rebaixamento_pct"]
    agente, _ = criar_agente(pedir("projetar_clube", clube="Corinthians"),
                             dizer(f"O Corinthians tem {risco}% de risco de queda."))
    r = agente.perguntar("O Corinthians vai cair?")

    assert r.tipo == "resposta" and r.aprovada_de_primeira
    assert [(c["nome"], c["ok"]) for c in r.chamadas] == [("projetar_clube", True)]
    assert (r.chamadas_llm, r.tokens_entrada, r.tokens_saida) == (2, 220, 30)


def test_o_resultado_da_ferramenta_volta_para_o_modelo_como_mensagem(criar_agente):
    agente, llm = criar_agente(pedir("classificacao_atual"), dizer("O líder é o Flamengo."))
    agente.perguntar("Quem lidera?")
    segunda_chamada = llm.vistos[1]
    assert isinstance(segunda_chamada[-1], ToolMessage) and "Flamengo" in segunda_chamada[-1].content


def test_numero_inventado_e_devolvido_ao_modelo_e_a_correcao_e_aceita(criar_agente, servico):
    risco = servico.projecao_clube("Santos")["prob_rebaixamento_pct"]
    agente, llm = criar_agente(pedir("projetar_clube", clube="Santos"),
                               dizer("O Santos tem 35% de risco de cair."),  # 35 nao veio da ferramenta
                               dizer(f"O Santos tem {risco}% de risco de cair."))
    r = agente.perguntar("O Santos cai?")

    assert r.tipo == "resposta" and str(risco).replace(".", ",") in r.texto.replace(".", ",")
    assert not r.aprovada_de_primeira and r.motivo_reprovacao == "numero_sem_fonte"
    assert r.numeros_sem_fonte == ["35"] and r.correcoes == 1
    correcao = llm.vistos[2][-1]
    assert isinstance(correcao, HumanMessage) and correcao.name == VERIFICADOR and "35" in correcao.content


def test_modelo_que_insiste_no_numero_inventado_termina_em_recusa_fixa(criar_agente):
    agente, _ = criar_agente(pedir("projetar_clube", clube="Santos"),
                             dizer("O Santos tem 35% de risco de cair."),
                             dizer("Como eu disse, 35% de risco."))
    r = agente.perguntar("O Santos cai?")

    assert r.tipo == "recusa" and r.texto.startswith(MSG_NAO_VERIFICAVEL)
    assert "35" not in r.texto  # nada do que o modelo escreveu chega ao usuario


def test_resposta_de_memoria_sem_ferramenta_e_barrada(criar_agente):
    agente, _ = criar_agente(dizer("O técnico do Santos é o Fulano."),
                             pedir("fora_do_escopo", motivo="jogadores_ou_tecnicos"))
    r = agente.perguntar("Quem é o técnico do Santos?")

    assert r.tipo == "recusa" and r.motivo_reprovacao == "sem_ferramenta"
    assert r.texto.startswith(MOTIVOS_RECUSA["jogadores_ou_tecnicos"]) and "Fulano" not in r.texto


def test_fora_do_escopo_encerra_sem_nova_chamada_ao_modelo(criar_agente):
    agente, llm = criar_agente(pedir("fora_do_escopo", motivo="outra_competicao"))
    r = agente.perguntar("Quem ganhou a Copa do Brasil?")
    assert r.tipo == "recusa" and r.chamadas_llm == 1 and llm.roteiro == []


def test_erro_da_ferramenta_vira_resposta_sem_dados(criar_agente):
    agente, _ = criar_agente(pedir("probabilidade_jogo", mandante="Fortaleza", visitante="Ceará"),
                             dizer("O Fortaleza não disputa a Série A de 2026."))
    r = agente.perguntar("Fortaleza ganha do Ceará?")
    assert r.tipo == "sem_dados" and r.chamadas[0]["resultado"]["erro"] == "fora_da_serie_a"


def test_ferramenta_inexistente_e_argumento_invalido_nao_derrubam_o_grafo(criar_agente):
    agente, llm = criar_agente(pedir("escalacao_do_time", clube="Santos"),
                               pedir("ranking_projecao", criterio="artilharia"),
                               pedir("fora_do_escopo", motivo="outro"))
    r = agente.perguntar("Qual a escalação?")
    erros = [c["resultado"]["erro"] for c in r.chamadas[:2]]
    assert erros == ["ferramenta_inexistente", "argumentos_invalidos"] and r.tipo == "recusa"


def test_limite_de_chamadas_interrompe_loop_de_ferramentas(criar_agente):
    agente, llm = criar_agente(*[pedir("classificacao_atual") for _ in range(config.MAX_CHAMADAS_LLM + 3)])
    r = agente.perguntar("Quem lidera?")
    assert r.tipo == "recusa" and r.chamadas_llm == config.MAX_CHAMADAS_LLM
    assert len(llm.roteiro) == 3  # parou de chamar o modelo


def test_mesma_conversa_lembra_do_turno_anterior_e_conversas_diferentes_nao(criar_agente):
    agente, llm = criar_agente(pedir("classificacao_atual"), dizer("O líder é o Flamengo."),
                               pedir("classificacao_atual"), dizer("O vice é o Palmeiras."),
                               pedir("classificacao_atual"), dizer("O líder é o Flamengo."))
    agente.perguntar("Quem lidera?", conversa_id="a")
    r2 = agente.perguntar("E o vice?", conversa_id="a")
    agente.perguntar("Quem lidera?", conversa_id="b")

    perguntas = lambda mensagens: [m.content for m in mensagens if isinstance(m, HumanMessage)]  # noqa: E731
    assert perguntas(llm.vistos[2]) == ["Quem lidera?", "E o vice?"]
    assert perguntas(llm.vistos[4]) == ["Quem lidera?"]
    assert len(r2.chamadas) == 1  # contadores sao por turno, nao por conversa
