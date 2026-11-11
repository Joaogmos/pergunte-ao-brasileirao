"""Gera evals/RESULTADOS.md a partir dos arquivos gravados em evals/resultados/.

    python -m pergunte.avaliacao.relatorio

As tabelas do README sao copiadas deste arquivo: nenhum numero e digitado a mao.
"""

from __future__ import annotations

import json

from pergunte import config

DESTINO = config.RAIZ / "evals" / "RESULTADOS.md"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x * 100:.0f}%".replace(".", ",")


def _fracao(resumo: dict) -> str:
    return f"{round(resumo['acerto'] * resumo['casos'])}/{resumo['casos']} ({_pct(resumo['acerto'])})"


def _virgula(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def gerar() -> str:
    execucoes = [json.loads(a.read_text(encoding="utf-8")) for a in sorted(config.RESULTADOS.glob("*.json"))]
    execucoes.sort(key=lambda e: (-e["resumo"]["teste"]["acerto"], not e["verificador"]))

    linhas = [
        "# Resultados do eval",
        "",
        "Gerado por `python -m pergunte.avaliacao.relatorio` a partir de `evals/resultados/*.json`.",
        "`dev` sao os 30 casos usados para ajustar prompt e ferramentas; `teste` sao 20 casos escritos",
        "antes dos ajustes e nunca usados para ajustar. O numero que vale e o do teste.",
        "",
        "## Qualidade",
        "",
        "| Modelo | Verificador | Teste | Dev | Ferramenta certa | Numero certo | Recusa certa |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in execucoes:
        r = e["resumo"]
        linhas.append(
            f"| `{e['modelo']}` | {'ligado' if e['verificador'] else 'desligado'} | {_fracao(r['teste'])} "
            f"| {_fracao(r['dev'])} | {_pct(r['todos']['ferramenta_correta'])} "
            f"| {_pct(r['todos']['numero_correto'])} | {_pct(r['todos']['recusa_correta'])} |"
        )

    linhas += [
        "",
        "Ferramenta, numero e recusa sao medidos nos 50 casos (dev + teste).",
        "",
        "## Custo e latencia (50 casos)",
        "",
        "| Modelo | Verificador | Chamadas ao LLM | Tokens entrada | Tokens saida | Latencia mediana | Latencia p95 |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in execucoes:
        t = e["resumo"]["todos"]
        linhas.append(
            f"| `{e['modelo']}` | {'ligado' if e['verificador'] else 'desligado'} | {_virgula(t['chamadas_llm_media'])} "
            f"| {t['tokens_entrada_media']} | {t['tokens_saida_media']} | {_virgula(t['latencia_mediana_s'])} s "
            f"| {_virgula(t['latencia_p95_s'])} s |"
        )

    linhas += [
        "",
        "Medias por pergunta. Modelos locais (Ollama) nao tem preco por token; a maquina esta em cada JSON.",
        "",
        "## O que o verificador fez (50 casos)",
        "",
        "| Modelo | Verificador | Rascunhos reprovados | Por numero sem fonte | Por falta de ferramenta "
        "| Viraram acerto | Respostas finais com numero sem fonte |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in execucoes:
        t = e["resumo"]["todos"]
        linhas.append(
            f"| `{e['modelo']}` | {'ligado' if e['verificador'] else 'desligado'} | {t['rascunhos_reprovados']} "
            f"| {t['reprovados_por_numero_sem_fonte']} | {t['reprovados_por_falta_de_ferramenta']} "
            f"| {t['reprovados_que_viraram_acerto']} | {t['respostas_finais_com_numero_sem_fonte']} |"
        )

    linhas += ["", "## Casos que falharam", ""]
    for e in execucoes:
        falhas = [i for i in e["itens"] if not i["julgamento"]["passou"]]
        titulo = f"`{e['modelo']}`" + ("" if e["verificador"] else " (verificador desligado)")
        linhas.append(f"**{titulo}: {len(falhas)} falha(s)**")
        linhas.append("")
        for i in falhas[:12]:
            motivo = ", ".join(k for k, v in i["julgamento"].items() if k != "passou" and not v)
            texto = i["resposta"]["texto"].replace("\n", " ")[:140]
            linhas.append(f"- `{i['id']}` ({motivo}): {i['pergunta']} -> \"{texto}\"")
        if len(falhas) > 12:
            linhas.append(f"- ... e mais {len(falhas) - 12} (ver o JSON)")
        linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    texto = gerar()
    DESTINO.write_text(texto, encoding="utf-8", newline="\n")
    print(texto)


if __name__ == "__main__":
    main()
