"""Teste de fumaca do painel Streamlit, com o LLM trocado por um roteiro."""

from streamlit.testing.v1 import AppTest

from pergunte import config
from tests.conftest import LLMRoteirizado, dizer, pedir


def test_painel_responde_e_mostra_a_sumula(monkeypatch, servico):
    roteiro = LLMRoteirizado(roteiro=[pedir("classificacao_atual"), dizer("O líder é o Flamengo.")], vistos=[])
    monkeypatch.setattr("pergunte.agente.criar_llm", lambda modelo: roteiro)
    monkeypatch.setattr("pergunte.agente.obter_servico", lambda: servico)

    painel = AppTest.from_file(str(config.RAIZ / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not painel.exception
    assert any("súmula da resposta aparece aqui" in m.value for m in painel.markdown)

    painel.chat_input[0].set_value("Quem lidera?").run()
    assert not painel.exception
    assert painel.chat_message[1].markdown[0].value == "O líder é o Flamengo."
    sumula = next(m.value for m in painel.markdown if 'class="sumula"' in m.value)
    assert "classificacao_atual" in sumula and "Conferido" in sumula
