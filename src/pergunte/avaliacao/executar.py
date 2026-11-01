"""Roda os casos de evals/casos.json contra um modelo e grava o resultado completo.

    python -m pergunte.avaliacao.executar --modelo ollama:qwen2.5:7b
    python -m pergunte.avaliacao.executar --modelo ollama:llama3.2:3b --sem-verificador

O arquivo gravado (evals/resultados/<modelo>.json) guarda, para cada caso, a
resposta, as chamadas de ferramenta e as metricas. Com isso o CI consegue
RE-JULGAR a execucao sem precisar de um LLM (tests/test_eval_gravado.py).
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import statistics
import time
from datetime import UTC, datetime

from pergunte import config
from pergunte.agente import Agente
from pergunte.avaliacao.juiz import julgar
from pergunte.servico import obter_servico
from pergunte.verificador import verificar


def carregar_casos() -> list[dict]:
    return json.loads(config.CASOS.read_text(encoding="utf-8"))


def _taxa(valores: list[bool]) -> float | None:
    return round(sum(valores) / len(valores), 4) if valores else None


def _percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(p * (len(ordenados) - 1)))]


def resumir(itens: list[dict]) -> dict:
    """Agrega os casos julgados. Usado na execucao ao vivo e no re-julgamento do CI."""
    por_categoria: dict[str, list[bool]] = {}
    for i in itens:
        por_categoria.setdefault(i["categoria"], []).append(i["julgamento"]["passou"])
    respondidos = [i for i in itens if i["espera"] == "resposta"]
    reprovados_1a = [i for i in itens if not i["resposta"]["aprovada_de_primeira"]]
    latencias = [i["resposta"]["latencia_s"] for i in itens]
    custos = [i["resposta"]["custo_usd"] for i in itens if i["resposta"]["custo_usd"] is not None]
    return {
        "casos": len(itens),
        "acerto": _taxa([i["julgamento"]["passou"] for i in itens]),
        "acerto_por_categoria": {c: _taxa(v) for c, v in sorted(por_categoria.items())},
        "ferramenta_correta": _taxa([i["julgamento"]["ferramenta"] for i in respondidos]),
        "numero_correto": _taxa([i["julgamento"]["numero"] for i in respondidos if "numero" in i["julgamento"]]),
        "recusa_correta": _taxa([i["julgamento"]["tipo"] for i in itens if i["espera"] != "resposta"]),
        # o guardrail em numeros: quantos rascunhos ele barrou e o que aconteceu depois
        "rascunhos_reprovados": len(reprovados_1a),
        "reprovados_por_numero_sem_fonte": sum(i["resposta"]["motivo_reprovacao"] == "numero_sem_fonte"
                                               for i in reprovados_1a),
        "reprovados_por_falta_de_ferramenta": sum(i["resposta"]["motivo_reprovacao"] == "sem_ferramenta"
                                                  for i in reprovados_1a),
        "reprovados_que_viraram_acerto": sum(i["julgamento"]["passou"] for i in reprovados_1a),
        "respostas_finais_com_numero_sem_fonte": sum(
            i["resposta"]["tipo"] == "resposta" and bool(i["resposta"].get("sem_fonte_no_final")) for i in itens),
        "chamadas_llm_media": round(statistics.mean(i["resposta"]["chamadas_llm"] for i in itens), 2),
        "tokens_entrada_media": round(statistics.mean(i["resposta"]["tokens_entrada"] for i in itens)),
        "tokens_saida_media": round(statistics.mean(i["resposta"]["tokens_saida"] for i in itens)),
        "latencia_mediana_s": round(statistics.median(latencias), 2),
        "latencia_p95_s": round(_percentil(latencias, 0.95), 2),
        "custo_medio_usd": round(statistics.mean(custos), 6) if custos else None,
    }


def resumir_por_conjunto(itens: list[dict]) -> dict:
    """dev = casos usados para ajustar prompt e ferramentas; teste = casos nunca usados para ajustar."""
    saida = {}
    for nome in ("dev", "teste"):
        parte = [i for i in itens if i["conjunto"] == nome]
        if parte:
            saida[nome] = resumir(parte)
    return {**saida, "todos": resumir(itens)}


def executar(modelo: str, usar_verificador: bool = True, conjunto: str = "todos",
             limite: int | None = None) -> dict:
    servico = obter_servico()
    agente = Agente(modelo=modelo, servico=servico, usar_verificador=usar_verificador)
    agente.perguntar("Quem é o líder?")  # aquece: carrega o modelo na memoria antes de medir latencia
    contexto = {"temporada": servico.temporada, "dados_ate": f"{servico.dados_ate:%d/%m/%Y}",
                "inicio_da_base": servico.primeira_temporada}

    itens = []
    casos = [c for c in carregar_casos() if conjunto in ("todos", c["conjunto"])]
    for caso in casos[:limite]:
        r = agente.perguntar(caso["pergunta"])
        resposta = r.como_dict()
        fatos = [contexto, *[c["resultado"] for c in r.chamadas]]
        resposta["sem_fonte_no_final"] = verificar(r.texto, fatos, [caso["pergunta"]]).sem_fonte
        julgamento = julgar(caso, r.texto, r.tipo, r.chamadas, servico)
        itens.append({"id": caso["id"], "categoria": caso["categoria"], "conjunto": caso["conjunto"],
                      "espera": caso["espera"], "pergunta": caso["pergunta"], "resposta": resposta,
                      "julgamento": julgamento})
        marca = "ok  " if julgamento["passou"] else "ERRO"
        print(f"{marca} {caso['id']:<12} {r.latencia_s:>5.1f}s  {r.texto[:90]!r}")

    return {
        "modelo": modelo,
        "verificador": usar_verificador,
        "executado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "maquina": platform.platform(),
        "dados_ate": f"{servico.dados_ate:%Y-%m-%d}",
        "resumo": resumir_por_conjunto(itens),
        "itens": itens,
    }


def nome_do_arquivo(modelo: str, usar_verificador: bool) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", modelo.lower()).strip("-")
    return f"{base}{'' if usar_verificador else '-sem-verificador'}.json"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Eval do agente")
    parser.add_argument("--modelo", default=config.MODELO_PADRAO)
    parser.add_argument("--sem-verificador", action="store_true", help="desliga o guardrail (ablacao)")
    parser.add_argument("--conjunto", choices=["dev", "teste", "todos"], default="todos")
    parser.add_argument("--limite", type=int, default=None, help="roda so os N primeiros casos")
    args = parser.parse_args(argv)

    inicio = time.perf_counter()
    resultado = executar(args.modelo, not args.sem_verificador, args.conjunto, args.limite)
    resultado["duracao_total_s"] = round(time.perf_counter() - inicio, 1)
    print(json.dumps(resultado["resumo"], indent=2, ensure_ascii=False))
    if args.limite is None and args.conjunto == "todos":  # execucao parcial nao sobrescreve o resultado versionado
        config.RESULTADOS.mkdir(parents=True, exist_ok=True)
        destino = config.RESULTADOS / nome_do_arquivo(args.modelo, not args.sem_verificador)
        destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"gravado em {destino}")


if __name__ == "__main__":
    main()
