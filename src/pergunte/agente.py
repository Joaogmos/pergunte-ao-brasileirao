"""O agente: um grafo de estados (LangGraph) com quatro nos.

    pergunta
       |
       v
    [modelo] --pediu ferramenta--> [ferramentas] --(volta com os resultados)--> [modelo]
       |                                 |
       | respondeu em texto              | chamou fora_do_escopo
       v                                 v
    [verificador] --reprovou 2x--> [recusa] --> FIM
       |      \\
       |       reprovou 1x: devolve o rascunho ao [modelo] com o motivo
       v
      FIM

Invariante que o grafo garante, qualquer que seja o LLM: a resposta final ou
(a) passou no verificador -- usou ferramenta neste turno e todo numero tem fonte --
ou (b) e a mensagem fixa de recusa. O modelo nunca responde "de cabeca".
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import ValidationError

from pergunte import config
from pergunte.ferramentas import FORA_DO_ESCOPO, MOTIVOS_RECUSA, criar_ferramentas
from pergunte.llm import criar_llm
from pergunte.servico import Servico, obter_servico
from pergunte.verificador import verificar

VERIFICADOR = "verificador"  # `name` das mensagens de correcao, para separar das perguntas reais

PROMPT_SISTEMA = """Você é o assistente do "Pergunte ao Brasileirão". Você responde perguntas sobre a \
Série A do Campeonato Brasileiro de {temporada} usando SOMENTE as ferramentas disponíveis.

Dados disponíveis até {dados_ate}. Clubes da Série A de {temporada}: {clubes}.

Regras:
1. Toda resposta começa por uma chamada de ferramenta. Nunca responda de memória.
2. Todo número da resposta precisa estar no resultado de uma ferramenta. Copie o número como veio. \
Não some, não subtraia, não arredonde de outro jeito e não estime.
3. Se nenhuma ferramenta de dados responde a pergunta, chame fora_do_escopo.
4. Se a ferramenta devolver "erro", explique o erro ao usuário em uma frase, sem inventar dados.
5. Em um jogo, mandante é quem joga em casa. Se o usuário não disser quem joga em casa, \
considere o primeiro clube citado como mandante e avise isso na resposta.
6. Probabilidades vêm de um modelo estatístico: são estimativas, não certezas. Não dê conselho de aposta.
7. Responda em português, em até 4 frases, citando os números que sustentam a resposta. Escreva \
decimais com vírgula (30,6%). Para pontos projetados, cite o valor esperado antes do intervalo."""

MSG_SEM_FERRAMENTA = (
    "Sua resposta não usou nenhuma ferramenta nesta pergunta. Chame a ferramenta de dados adequada "
    "ou, se a pergunta não puder ser respondida com os dados, chame fora_do_escopo."
)
MSG_SEM_FONTE = (
    "Sua resposta contém números que não estão nos resultados das ferramentas: {numeros}. "
    "Reescreva a resposta sem as frases que usam esses números. Use apenas números copiados dos "
    "resultados, sem contar nem somar nada por conta própria."
)
MSG_NAO_VERIFICAVEL = "Não consegui montar uma resposta em que todos os números viessem dos dados."
MSG_LIMITE = "Precisei de consultas demais para essa pergunta e parei antes de responder."
MSG_AJUDA = (
    "Posso responder sobre a Série A de {temporada}: probabilidades de um jogo, projeção de um clube "
    "(título, Libertadores, rebaixamento), classificação atual e histórico de confrontos desde {inicio}."
)


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # conversa inteira (persistida pelo checkpointer)
    fatos: list[dict]  # resultados de ferramenta da conversa: a "fonte" dos numeros
    chamadas: list[dict]  # ferramentas chamadas NESTE turno
    chamadas_llm: int
    correcoes: int
    tokens_entrada: int
    tokens_saida: int
    motivo_recusa: str | None
    primeiro_rascunho: dict | None  # o que o verificador achou do 1o rascunho (metrica do eval)
    tipo: str


@dataclass
class Resposta:
    texto: str
    tipo: Literal["resposta", "sem_dados", "recusa"]
    chamadas: list[dict] = field(default_factory=list)
    aprovada_de_primeira: bool = True
    motivo_reprovacao: str | None = None
    numeros_sem_fonte: list[str] = field(default_factory=list)
    correcoes: int = 0
    chamadas_llm: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_s: float = 0.0
    custo_usd: float | None = None
    modelo: str = ""

    def como_dict(self) -> dict:
        return asdict(self)


def _texto(mensagem: AnyMessage) -> str:
    """Conteudo em texto. Alguns provedores devolvem lista de blocos em vez de string."""
    c = mensagem.content
    if isinstance(c, str):
        return c.strip()
    return "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text").strip()


def janela(mensagens: list[AnyMessage], max_turnos: int) -> list[AnyMessage]:
    """As mensagens dos ultimos `max_turnos` turnos. Um turno comeca numa pergunta do usuario.

    O corte e sempre no inicio de um turno: cortar no meio deixaria um resultado de ferramenta
    sem o pedido que o originou, e os provedores rejeitam essa sequencia.
    """
    inicios = [i for i, m in enumerate(mensagens) if isinstance(m, HumanMessage) and m.name != VERIFICADOR]
    if len(inicios) <= max_turnos:
        return mensagens
    return mensagens[inicios[-max_turnos]:]


def construir_grafo(llm: BaseChatModel, servico: Servico, checkpointer=None, usar_verificador: bool = True):
    ferramentas = {f.name: f for f in criar_ferramentas(servico)}
    llm_com_ferramentas = llm.bind_tools(list(ferramentas.values()))
    sistema = SystemMessage(PROMPT_SISTEMA.format(
        temporada=servico.temporada, dados_ate=f"{servico.dados_ate:%d/%m/%Y}", clubes=", ".join(servico.clubes()),
    ))

    # o que o prompt de sistema ja informa ao modelo tambem conta como fonte
    contexto = {"temporada": servico.temporada, "dados_ate": f"{servico.dados_ate:%d/%m/%Y}",
                "inicio_da_base": servico.primeira_temporada}

    # ------------------------------------------------------------------ nos

    def no_modelo(estado: Estado) -> dict:
        resposta = llm_com_ferramentas.invoke([sistema, *janela(estado["messages"], config.MAX_TURNOS_NO_CONTEXTO)])
        uso = getattr(resposta, "usage_metadata", None) or {}
        return {
            "messages": [resposta],
            "chamadas_llm": estado.get("chamadas_llm", 0) + 1,
            "tokens_entrada": estado.get("tokens_entrada", 0) + uso.get("input_tokens", 0),
            "tokens_saida": estado.get("tokens_saida", 0) + uso.get("output_tokens", 0),
        }

    def no_ferramentas(estado: Estado) -> dict:
        """Executa o que o modelo pediu. O modelo so ESCOLHE; quem roda codigo somos nos."""
        mensagens, chamadas, fatos, motivo = [], [], [], None
        for pedido in estado["messages"][-1].tool_calls:
            nome, args = pedido["name"], pedido["args"]
            if nome not in ferramentas:
                resultado = {"erro": "ferramenta_inexistente", "mensagem": f"Nao existe a ferramenta '{nome}'."}
            else:
                try:
                    resultado = ferramentas[nome].invoke(args)
                except ValidationError as e:  # argumento faltando ou de tipo errado
                    resultado = {"erro": "argumentos_invalidos", "mensagem": str(e.errors()[0]["msg"])}
            if nome == FORA_DO_ESCOPO and isinstance(resultado, str):
                motivo = resultado
            ok = not (isinstance(resultado, dict) and "erro" in resultado)
            chamadas.append({"nome": nome, "args": args, "resultado": resultado, "ok": ok})
            if nome != FORA_DO_ESCOPO:  # erro tambem e fonte: a mensagem de erro e texto nosso
                fatos.append(resultado)
            mensagens.append(ToolMessage(json.dumps(resultado, ensure_ascii=False), tool_call_id=pedido["id"],
                                         name=nome))
        return {
            "messages": mensagens,
            "chamadas": estado.get("chamadas", []) + chamadas,
            "fatos": estado.get("fatos", []) + fatos,
            "motivo_recusa": motivo,
        }

    def no_verificador(estado: Estado) -> dict:
        rascunho = _texto(estado["messages"][-1])
        perguntas = [_texto(m) for m in estado["messages"]
                     if isinstance(m, HumanMessage) and m.name != VERIFICADOR]
        chamadas = estado.get("chamadas", [])
        if not chamadas or not rascunho:
            motivo, sem_fonte, correcao = "sem_ferramenta", [], MSG_SEM_FERRAMENTA
        else:
            v = verificar(rascunho, [contexto, *estado.get("fatos", [])], perguntas)
            motivo = None if v.aprovada or not usar_verificador else "numero_sem_fonte"
            sem_fonte = v.sem_fonte
            correcao = MSG_SEM_FONTE.format(numeros=", ".join(v.sem_fonte))

        saida: dict = {}
        if estado.get("correcoes", 0) == 0:  # registra so o veredito do PRIMEIRO rascunho
            saida["primeiro_rascunho"] = {"motivo": motivo, "sem_fonte": sem_fonte}
        if motivo is None:
            so_erros = all(not c["ok"] for c in chamadas)
            return {**saida, "tipo": "sem_dados" if so_erros else "resposta"}
        if estado.get("correcoes", 0) < config.MAX_CORRECOES:
            return {**saida, "tipo": "corrigir", "correcoes": estado.get("correcoes", 0) + 1,
                    "messages": [HumanMessage(correcao, name=VERIFICADOR)]}
        fixo = MOTIVOS_RECUSA["outro"] if motivo == "sem_ferramenta" else MSG_NAO_VERIFICAVEL
        return {**saida, "tipo": "recusar", "motivo_recusa": fixo}

    def no_recusa(estado: Estado) -> dict:
        """Mensagem FIXA: nada do que o modelo escreveu chega ao usuario por aqui."""
        motivo = estado.get("motivo_recusa") or MSG_LIMITE
        ajuda = MSG_AJUDA.format(temporada=servico.temporada, inicio=servico.primeira_temporada)
        return {"messages": [AIMessage(f"{motivo} {ajuda}")], "tipo": "recusa"}

    # ------------------------------------------------------------------ arestas

    def depois_do_modelo(estado: Estado) -> str:
        if not estado["messages"][-1].tool_calls:
            return "verificador"
        if estado["chamadas_llm"] >= config.MAX_CHAMADAS_LLM:
            return "recusa"
        return "ferramentas"

    def depois_das_ferramentas(estado: Estado) -> str:
        return "recusa" if estado.get("motivo_recusa") else "modelo"

    def depois_do_verificador(estado: Estado) -> str:
        return {"corrigir": "modelo", "recusar": "recusa"}.get(estado["tipo"], END)

    grafo = StateGraph(Estado)
    grafo.add_node("modelo", no_modelo)
    grafo.add_node("ferramentas", no_ferramentas)
    grafo.add_node("verificador", no_verificador)
    grafo.add_node("recusa", no_recusa)
    grafo.add_edge(START, "modelo")
    grafo.add_conditional_edges("modelo", depois_do_modelo, ["ferramentas", "verificador", "recusa"])
    grafo.add_conditional_edges("ferramentas", depois_das_ferramentas, ["modelo", "recusa"])
    grafo.add_conditional_edges("verificador", depois_do_verificador, ["modelo", "recusa", END])
    grafo.add_edge("recusa", END)
    return grafo.compile(checkpointer=checkpointer)


class Agente:
    """Fachada usada pela API, pelo painel e pelo eval."""

    def __init__(self, modelo: str = config.MODELO_PADRAO, llm: BaseChatModel | None = None,
                 servico: Servico | None = None, usar_verificador: bool = True):
        self.modelo = modelo
        self.servico = servico or obter_servico()
        # O checkpointer guarda o estado por conversa (thread_id): e a memoria entre turnos.
        self.grafo = construir_grafo(llm or criar_llm(modelo), self.servico, InMemorySaver(), usar_verificador)

    def perguntar(self, pergunta: str, conversa_id: str | None = None) -> Resposta:
        inicio = time.perf_counter()
        turno = {  # zera os contadores do turno; `messages` e `fatos` continuam da conversa
            "messages": [HumanMessage(pergunta)], "chamadas": [], "chamadas_llm": 0, "correcoes": 0,
            "tokens_entrada": 0, "tokens_saida": 0, "motivo_recusa": None, "primeiro_rascunho": None, "tipo": "",
        }
        final = self.grafo.invoke(turno, {"configurable": {"thread_id": conversa_id or str(uuid.uuid4())},
                                          "recursion_limit": 30})
        rascunho = final.get("primeiro_rascunho") or {}
        resposta = Resposta(
            texto=_texto(final["messages"][-1]),
            tipo=final["tipo"],
            chamadas=final.get("chamadas", []),
            aprovada_de_primeira=rascunho.get("motivo") is None,
            motivo_reprovacao=rascunho.get("motivo"),
            numeros_sem_fonte=rascunho.get("sem_fonte", []),
            correcoes=final.get("correcoes", 0),
            chamadas_llm=final["chamadas_llm"],
            tokens_entrada=final["tokens_entrada"],
            tokens_saida=final["tokens_saida"],
            latencia_s=round(time.perf_counter() - inicio, 2),
            custo_usd=config.custo_usd(self.modelo, final["tokens_entrada"], final["tokens_saida"]),
            modelo=self.modelo,
        )
        if config.ARQUIVO_DE_TRACE:
            _registrar(config.ARQUIVO_DE_TRACE, pergunta, conversa_id, resposta)
        return resposta


def _registrar(arquivo: str, pergunta: str, conversa_id: str | None, resposta: Resposta) -> None:
    """Uma linha JSON por pergunta: o minimo para auditar depois o que o agente respondeu e por que."""
    linha = {"quando": datetime.now(UTC).isoformat(timespec="seconds"), "conversa_id": conversa_id,
             "pergunta": pergunta, **resposta.como_dict()}
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
