"""Simula três incidentes reais e registra o que o pipeline fez com cada um.

1. schema   — o produtor renomeia a coluna `valor` sem avisar.
2. unidade  — o produtor passa a mandar `valor` em centavos, com o mesmo nome e tipo.
3. coluna sem classificação — alguém adiciona uma coluna à gold sem declarar o tipo de dado.

Para cada um, roda o dbt e guarda em target/incidentes.json se o problema foi barrado,
em que etapa e com qual mensagem. No fim, restaura a base e o YAML originais.
Uso: python scripts/simular_incidentes.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GOLD_YML = RAIZ / "models" / "gold" / "_gold.yml"


# No Windows o padrão é cp1252: força UTF-8 no dbt (os YAML têm acento) e na leitura da saída.
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def dbt(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["dbt", *args, "--profiles-dir", "."], cwd=RAIZ, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=ENV)


def gerar(incidente: str | None = None) -> None:
    cmd = [sys.executable, "scripts/gerar_dados.py"] + (["--incidente", incidente] if incidente else [])
    subprocess.run(cmd, cwd=RAIZ, check=True, capture_output=True, env=ENV)


def limpar(saida: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", saida)


def trecho(saida: str, padrao: str, linhas: int = 8) -> str:
    s = limpar(saida).splitlines()
    for i, l in enumerate(s):
        if re.search(padrao, l):
            return "\n".join(x.split("  ", 1)[-1] if re.match(r"^\d\d:\d\d:\d\d", x) else x for x in s[i:i + linhas]).strip()
    return ""


def main() -> None:
    resultados = []
    saidas = {}

    # base limpa para o que não é afetado pelos incidentes (cartões, clientes, MCC)
    gerar(None)
    dbt("seed")
    dbt("run", "-s", "bronze_clientes", "bronze_cartoes", "silver_clientes", "silver_cartoes")

    # 1. quebra de esquema
    gerar("schema")
    r = dbt("build", "-s", "bronze_transacoes+")
    out = limpar(r.stdout)
    saidas["schema"] = out
    resultados.append({
        "id": "schema",
        "titulo": "O produtor renomeou a coluna valor",
        "o_que_mudou": "transacoes.csv chega com valor_transacao no lugar de valor.",
        "barrado": r.returncode != 0 and "enforced contract" in out,
        "onde": "contrato do bronze_transacoes (antes de qualquer tabela ser recriada)",
        "evidencia": trecho(out, r"column_name\s+\|", 4),
        "pulados": len(re.findall(r"\bSKIP\b", out)),
    })

    # 2. mudança silenciosa de unidade
    gerar("unidade")
    r = dbt("build", "-s", "bronze_transacoes+")
    out = limpar(r.stdout)
    saidas["unidade"] = out
    m = re.search(r"FAIL (\d+) argos_ticket_medio", out)
    resultados.append({
        "id": "unidade",
        "titulo": "O produtor passou a mandar centavos",
        "o_que_mudou": "valor continua double e com o mesmo nome, mas R$ 59,58 vira 5958.",
        "barrado": r.returncode != 0 and m is not None,
        "onde": "teste de qualidade do contrato: ticket médio diário entre R$ 20 e R$ 1.000",
        "evidencia": f"{m.group(1)} dias com ticket médio fora da faixa" if m else "",
        "pulados": len(re.findall(r"\bSKIP\b", out)),
    })

    # 3. coluna nova sem classificação
    gerar(None)
    original = GOLD_YML.read_text(encoding="utf-8")
    try:
        GOLD_YML.write_text(original.replace(
            '        data_type: varchar\n        config: {meta: {tipo_dado: ocupacao}}',
            '        data_type: varchar', 1), encoding="utf-8")
        r = dbt("compile", "-s", "path:models/acesso")
        out = limpar(r.stdout)
        saidas["classificacao"] = out
        resultados.append({
            "id": "classificacao",
            "titulo": "Uma coluna chegou sem classificação",
            "o_que_mudou": "dim_cliente.ocupacao perde o tipo_dado no YAML.",
            "barrado": r.returncode != 0 and "não tem tipo_dado" in out,
            "onde": "geração das views de acesso (compilação)",
            "evidencia": next((l.strip() for l in out.splitlines() if "não tem tipo_dado" in l), ""),
            "pulados": None,
        })
    finally:
        GOLD_YML.write_text(original, encoding="utf-8")

    (RAIZ / "target").mkdir(exist_ok=True)
    (RAIZ / "target" / "incidentes.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    for x in resultados:
        print(("BARRADO " if x["barrado"] else "PASSOU  ") + x["titulo"])
        if not x["barrado"]:
            fim = "\n".join(saidas.get(x["id"], "").strip().splitlines()[-12:])
            print("   --- últimas linhas do dbt ---\n   " + fim.replace("\n", "\n   "))
    if not all(x["barrado"] for x in resultados):
        sys.exit("Algum incidente passou pelo pipeline sem ser barrado.")


if __name__ == "__main__":
    main()
