"""Painel de demonstracao: conversa a esquerda, "sumula" da resposta a direita.

    streamlit run app/streamlit_app.py

A sumula e a trilha de auditoria da ultima resposta, no formato de uma sumula de
jogo: que ferramentas o agente chamou, com que argumentos, o que o verificador
decidiu e quanto custou (chamadas ao modelo, tokens, tempo).
"""

from __future__ import annotations

import html
import json
import uuid

import streamlit as st

from pergunte import config
from pergunte.agente import Agente

st.set_page_config(page_title="Pergunte ao Brasileirão", page_icon="⚽", layout="wide")

# Paleta: cal do gramado (fundo), verde de vestiario (tinta de destaque), amarelo e
# vermelho de cartao para os vereditos. Tipos: Barlow Condensed (placa de estadio)
# nos titulos, IBM Plex Sans no texto e Plex Mono em tudo que e dado.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
:root { --cal:#F6F7F1; --tinta:#14201B; --verde:#0F3D2E; --linha:#CBD2C8; --mudo:#5C6B63;
        --amarelo:#F2C230; --vermelho:#C8372D; --papel:#FFFFFF; }
html, body, .stApp, .stMarkdown, p, textarea { font-family:'IBM Plex Sans', sans-serif; color:var(--tinta); }
.stApp { background:var(--cal); }
.block-container { padding-top:2.2rem; max-width:1240px; }
h1.titulo { font-family:'Barlow Condensed', sans-serif; font-weight:700; font-size:3.1rem; line-height:.95;
            letter-spacing:.01em; text-transform:uppercase; color:var(--verde); margin:0 0 .35rem; }
p.sub { color:var(--mudo); font-size:1rem; margin:0 0 1.4rem; max-width:46rem; }
[data-testid="stChatMessage"] { background:var(--papel); border:1px solid var(--linha); border-radius:6px; }
[data-testid="stChatMessageAvatarUser"] { background:var(--tinta); }
[data-testid="stChatMessageAvatarAssistant"] { background:var(--verde); }
[data-testid="stBottom"] > div, [data-testid="stHeader"] { background:var(--cal); }
.stButton > button { font-family:'IBM Plex Sans', sans-serif; border:1px solid var(--linha); border-radius:4px;
                     background:var(--papel); color:var(--tinta); text-align:left; width:100%; }
.stButton > button:hover { border-color:var(--verde); color:var(--verde); }
.stButton > button:focus-visible { outline:2px solid var(--verde); outline-offset:2px; }

.sumula { background:var(--papel); border:1px solid var(--tinta); border-radius:3px; padding:1.1rem 1.2rem 1rem;
          position:relative; }
.sumula .cab { display:flex; justify-content:space-between; align-items:baseline;
               border-bottom:2px solid var(--tinta); padding-bottom:.45rem; margin-bottom:.8rem; }
.sumula .cab b { font-family:'Barlow Condensed', sans-serif; font-size:1.55rem; font-weight:600;
                 letter-spacing:.06em; text-transform:uppercase; }
.sumula .cab span, .sumula .rotulo { font-family:'IBM Plex Mono', monospace; font-size:.72rem; color:var(--mudo);
                 text-transform:uppercase; letter-spacing:.05em; }
.sumula .rotulo { margin:.9rem 0 .3rem; display:block; }
.lance { display:grid; grid-template-columns:1.6rem 1fr auto; gap:.5rem; align-items:baseline;
         padding:.42rem 0; border-bottom:1px dashed var(--linha); font-family:'IBM Plex Mono', monospace; font-size:.8rem; }
.lance .n { color:var(--mudo); }
.lance .args { color:var(--mudo); display:block; overflow-wrap:anywhere; }
.lance .ok { color:var(--verde); font-weight:500; }
.lance .erro { color:var(--vermelho); font-weight:500; }
.carimbo { display:inline-block; font-family:'Barlow Condensed', sans-serif; font-weight:700; font-size:1.25rem;
           letter-spacing:.12em; text-transform:uppercase; padding:.1rem .7rem; border:3px solid; border-radius:4px;
           transform:rotate(-3deg); margin:.5rem 0 .2rem; }
.carimbo.conferido { color:var(--verde); border-color:var(--verde); }
.carimbo.corrigido { color:#8A6A00; border-color:var(--amarelo); background:#FFF9E0; }
.carimbo.recusado { color:var(--vermelho); border-color:var(--vermelho); }
.sumula p.nota { font-size:.85rem; color:var(--tinta); margin:.3rem 0 0; }
.placar { display:grid; grid-template-columns:repeat(4, 1fr); gap:.4rem; margin-top:.4rem; }
.placar div { border:1px solid var(--linha); border-radius:3px; padding:.4rem .5rem; }
.placar b { display:block; font-family:'IBM Plex Mono', monospace; font-weight:500; font-size:1.02rem; }
.placar span { display:block; font-size:.68rem; line-height:1.3; color:var(--mudo); text-transform:uppercase;
               letter-spacing:.04em; }
.vazia { border:1px dashed var(--linha); border-radius:3px; padding:1.4rem 1.2rem; color:var(--mudo); font-size:.92rem; }
@media (max-width: 760px) { h1.titulo { font-size:2.3rem; } .placar { grid-template-columns:repeat(2, 1fr); } }
</style>
"""

EXEMPLOS = [
    "O Santos corre risco de cair?",
    "Qual a chance de o Flamengo vencer o Palmeiras em casa?",
    "Quem é o favorito ao título?",
    "Como é o retrospecto entre Grêmio e Internacional?",
    "Quem é o artilheiro do campeonato?",
]

VEREDITOS = {
    "conferido": ("conferido", "Todos os números da resposta estão nos resultados das ferramentas."),
    "corrigido": ("corrigido", "O primeiro rascunho foi devolvido ao modelo; a versão corrigida passou."),
    "sem_dados": ("conferido", "A ferramenta não tinha o dado. A resposta explica o motivo, sem números novos."),
    "recusa": ("recusado", "Pergunta fora dos dados, ou rascunho reprovado duas vezes. Resposta fixa."),
}


@st.cache_resource(show_spinner="Ajustando o modelo estatístico e simulando a temporada…")
def obter_agente() -> Agente:
    return Agente()


def veredito(r: dict) -> str:
    if r["tipo"] == "recusa":
        return "recusa"
    if r["tipo"] == "sem_dados":
        return "sem_dados"
    return "conferido" if r["aprovada_de_primeira"] else "corrigido"


def sumula_html(pergunta: str, r: dict) -> str:
    lances = []
    for i, c in enumerate(r["chamadas"], start=1):
        args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in c["args"].items()) or "sem argumentos"
        situacao = '<span class="ok">ok</span>' if c["ok"] else '<span class="erro">erro</span>'
        lances.append(f'<div class="lance"><span class="n">{i}</span><span>{html.escape(c["nome"])}'
                      f'<span class="args">{html.escape(args)}</span></span>{situacao}</div>')
    if not lances:
        lances.append('<div class="lance"><span class="n">–</span><span>nenhuma ferramenta de dados</span>'
                      '<span></span></div>')

    chave = veredito(r)
    classe, nota = VEREDITOS[chave]
    rotulo = {"conferido": "Conferido", "corrigido": "Corrigido", "sem_dados": "Sem dados", "recusa": "Recusado"}[chave]
    if r["numeros_sem_fonte"]:
        nota += f' Números sem fonte no rascunho: {html.escape(", ".join(r["numeros_sem_fonte"]))}.'
    custo = "modelo local" if r["custo_usd"] is None else f'US$ {r["custo_usd"]:.5f}'
    return f"""
<div class="sumula">
  <div class="cab"><b>Súmula</b><span>{html.escape(r["modelo"])}</span></div>
  <span class="rotulo">Pergunta</span>
  <p class="nota">{html.escape(pergunta)}</p>
  <span class="rotulo">Ferramentas chamadas</span>
  {"".join(lances)}
  <span class="rotulo">Verificador</span>
  <div class="carimbo {classe}">{rotulo}</div>
  <p class="nota">{nota}</p>
  <span class="rotulo">Custo desta resposta</span>
  <div class="placar">
    <div><b>{r["chamadas_llm"]}</b><span>chamadas ao modelo</span></div>
    <div><b>{r["tokens_entrada"]}</b><span>tokens de entrada</span></div>
    <div><b>{r["tokens_saida"]}</b><span>tokens de saída</span></div>
    <div><b>{r["latencia_s"]:.1f} s</b><span>tempo · {custo}</span></div>
  </div>
</div>"""


st.markdown(CSS, unsafe_allow_html=True)
st.session_state.setdefault("turnos", [])
st.session_state.setdefault("conversa_id", str(uuid.uuid4()))

agente = obter_agente()
servico = agente.servico

st.markdown('<h1 class="titulo">Pergunte ao Brasileirão</h1>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub">Série A de {servico.temporada}, com dados até {servico.dados_ate:%d/%m/%Y}. '
    "Cada número da resposta sai de um modelo estatístico e é conferido antes de chegar aqui. "
    "O que os dados não cobrem, o agente recusa.</p>",
    unsafe_allow_html=True,
)

conversa, lateral = st.columns([3, 2], gap="large")
pergunta = st.chat_input("Pergunte sobre um jogo, um clube ou a tabela")

with conversa:
    if not st.session_state.turnos and not pergunta:
        st.caption("Comece por uma destas:")
        for exemplo in EXEMPLOS:
            if st.button(exemplo, key=exemplo):
                pergunta = exemplo
    for turno in st.session_state.turnos:
        st.chat_message("user").write(turno["pergunta"])
        st.chat_message("assistant").write(turno["resposta"]["texto"])
    if pergunta:
        st.chat_message("user").write(pergunta)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Consultando os dados…"):
                    resposta = agente.perguntar(pergunta, st.session_state.conversa_id).como_dict()
            except Exception as erro:  # modelo local desligado, modelo nao baixado...
                st.error(f"O modelo de linguagem ({config.MODELO_PADRAO}) não respondeu. "
                         f"Confira se o Ollama está rodando e tente de novo. Detalhe: {str(erro)[:160]}")
                st.stop()
            st.write(resposta["texto"])
        st.session_state.turnos.append({"pergunta": pergunta, "resposta": resposta})

with lateral:
    if st.session_state.turnos:
        ultimo = st.session_state.turnos[-1]
        st.markdown(sumula_html(ultimo["pergunta"], ultimo["resposta"]), unsafe_allow_html=True)
        with st.expander("Ver o que cada ferramenta devolveu"):
            for c in ultimo["resposta"]["chamadas"]:
                st.caption(c["nome"])
                st.json(c["resultado"], expanded=False)
        if st.button("Começar nova conversa"):
            st.session_state.turnos = []
            st.session_state.conversa_id = str(uuid.uuid4())
            st.rerun()
    else:
        st.markdown('<div class="vazia">A súmula da resposta aparece aqui: ferramentas chamadas, '
                    "veredito do verificador, tokens e tempo.</div>", unsafe_allow_html=True)
