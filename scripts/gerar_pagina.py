"""Gera site/index.html — a página pública do Argos — a partir do que o build produziu.

Lê o banco (views de acesso, matriz, catálogo, fila de retenção), o manifest e o
run_results do dbt e o target/incidentes.json. Nada na página é digitado à mão:
se a política mudar, a página muda junto no próximo build.
"""
import hashlib
import html
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
DB = os.environ.get("ARGOS_DB", str(RAIZ / "argos.duckdb"))
SEGREDO = os.environ.get("ARGOS_SEGREDO", "segredo-local-de-desenvolvimento")
REPO = "https://github.com/GabiGattiRodrigues/argos"

PAPEIS = [  # (papel, rótulo pt, rótulo en)
    ("analista_bi", "Analista de BI", "BI analyst"),
    ("cientista_dados", "Cientista de dados", "Data scientist"),
    ("compliance_pld", "Compliance / PLD", "Compliance / AML"),
    ("crm_marketing", "CRM / marketing", "CRM / marketing"),
]
TRAT_EN = {"claro": "clear", "mascarar": "mask", "pseudonimizar": "pseudonymize", "faixa": "band", "remover": "remove"}


def e(x) -> str:
    return html.escape("" if x is None else str(x))


def bi(pt: str, en: str, tag: str = "span", cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-pt="{e(pt)}" data-en="{e(en)}">{pt}</{tag}>'


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    q = lambda s, *p: con.execute(s, list(p)).fetchall()

    catalogo = q("select modelo, coluna, tipo_dado, classificacao, dado_pessoal, finalidade, base_legal, descricao "
                 "from governanca.gov_catalogo_colunas order by modelo, coluna")
    matriz = {(p, t): tr for p, t, _, tr in q("select papel, tipo_dado, classificacao, tratamento from governanca.gov_matriz_acesso")}
    tipos = q("select distinct tipo_dado, classificacao from governanca.gov_matriz_acesso")
    ordem_cls = {"restrito": 0, "confidencial": 1, "interno": 2, "publico": 3}
    tipos.sort(key=lambda r: (ordem_cls.get(r[1], 9), r[0]))
    retencao = dict(q("select acao, count(*) from governanca.gov_fila_retencao group by 1"))
    n_clientes = q("select count(*) from gold.dim_cliente")[0][0]
    n_crm = q("select count(*) from gold.mart_crm_contatos")[0][0]
    n_trans = q("select count(*) from gold.fct_transacoes")[0][0]

    # ---- o mesmo cliente, quatro olhares -------------------------------------------------------
    alvo = q("select id_cliente from gold.mart_crm_contatos order by id_cliente limit 1")[0][0]
    pseudo = "p_" + hashlib.sha256((SEGREDO + alvo).encode()).hexdigest()[:16]
    gold_cols = [r[0] for r in q("select column_name from information_schema.columns where table_schema='gold' "
                                 "and table_name='dim_cliente' order by ordinal_position")]
    tipo_col = {c: t for m, c, t, *_ in catalogo if m == "dim_cliente"}
    vistas = {}
    for papel, *_ in PAPEIS:
        if papel == "crm_marketing":
            rel, chave = "acesso_crm_marketing.mart_crm_contatos", alvo
        else:
            rel = f"acesso_{papel}.dim_cliente"
            chave = alvo if matriz.get((papel, "id_cliente")) == "claro" else pseudo
        cur = con.execute(f"select * from {rel} where id_cliente = ?", [chave])
        nomes = [d[0] for d in cur.description]
        vistas[papel] = dict(zip(nomes, cur.fetchone()))

    def celula(papel, col):
        v = vistas[papel]
        tipo = tipo_col[col]
        tr = matriz.get((papel, tipo), "remover")
        if papel == "crm_marketing" and col not in v:
            return f'<td class="t-off">{bi("fora da finalidade", "out of purpose")}</td>'
        if tr == "remover":
            return f'<td class="t-off">{bi("removido", "removed")}</td>'
        val = v.get(col, v.get(col + "_faixa"))
        if isinstance(val, float):
            val = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<td class="t-{tr}"><code>{e(val)}</code><small>{bi(tr, TRAT_EN[tr])}</small></td>'

    linhas_olhar = "".join(
        f"<tr><th><code>{e(c)}</code><small>{e(tipo_col[c])}</small></th>" + "".join(celula(p, c) for p, *_ in PAPEIS) + "</tr>"
        for c in gold_cols)

    # ---- matriz de acesso ---------------------------------------------------------------------
    linhas_matriz = "".join(
        f'<tr><th><code>{e(t)}</code></th><td><span class="cls cls-{e(cl)}">{e(cl)}</span></td>'
        + "".join(f'<td class="t-{matriz[(p, t)]}">{bi(matriz[(p, t)], TRAT_EN[matriz[(p, t)]])}</td>' for p, *_ in PAPEIS)
        + "</tr>" for t, cl in tipos)

    # ---- testes, incidentes ---------------------------------------------------------------------
    rr = json.loads((RAIZ / "target" / "run_results.json").read_text(encoding="utf-8"))
    testes = [r for r in rr["results"] if r["unique_id"].startswith("test.")]
    ok = sum(r["status"] == "pass" for r in testes)
    manifest = json.loads((RAIZ / "target" / "manifest.json").read_text(encoding="utf-8"))
    contratos = sum(1 for n in manifest["nodes"].values()
                    if n["resource_type"] == "model" and n["config"].get("contract", {}).get("enforced"))
    inc_path = RAIZ / "target" / "incidentes.json"
    incidentes = json.loads(inc_path.read_text(encoding="utf-8")) if inc_path.exists() else []
    inc_en = {
        "schema": ("The producer renamed the valor column", "transacoes.csv arrives with valor_transacao instead of valor.",
                   "bronze_transacoes contract (before any table is rebuilt)"),
        "unidade": ("The producer switched to cents", "valor is still a double with the same name, but R$ 59.58 becomes 5958.",
                    "contract quality test: daily average ticket between R$ 20 and R$ 1,000"),
        "classificacao": ("A column arrived without a classification", "dim_cliente.ocupacao loses its tipo_dado in the YAML.",
                          "access view generation (compile time)"),
    }
    cards_inc = ""
    for i in incidentes:
        t_en, m_en, o_en = inc_en.get(i["id"], (i["titulo"], i["o_que_mudou"], i["onde"]))
        n = i.get("pulados")
        pul = (f'<p class="muted">{bi(f"{n} etapas a jusante não rodaram com o dado quebrado.", f"{n} downstream steps did not run on broken data.")}</p>'
               if n else "")
        cards_inc += f'''<article class="inc {'ok' if i['barrado'] else 'bad'}">
  <span class="badge">{bi('barrado' if i['barrado'] else 'passou', 'blocked' if i['barrado'] else 'got through')}</span>
  {bi(i['titulo'], t_en, 'h3')}
  {bi(i['o_que_mudou'], m_en, 'p')}
  <p class="onde"><b>{bi('Onde parou', 'Where it stopped')}:</b> {bi(i['onde'], o_en)}</p>
  <pre>{e(i['evidencia'])}</pre>{pul}
</article>'''

    # ---- catálogo -------------------------------------------------------------------------------
    linhas_cat = "".join(
        f'<tr><td><code>{e(m)}</code></td><td><code>{e(c)}</code></td><td>{e(t)}</td>'
        f'<td><span class="cls cls-{e(cl)}">{e(cl)}</span></td><td>{"sim" if dp else "não"}</td><td>{e(d)}</td></tr>'
        for m, c, t, cl, dp, fin, bl, d in catalogo)
    n_cols = len(catalogo)
    n_pessoais = sum(1 for r in catalogo if r[4])
    gerado = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    pagina = TEMPLATE
    for k, v in {
        "LINHAS_OLHAR": linhas_olhar, "LINHAS_MATRIZ": linhas_matriz, "CARDS_INC": cards_inc, "LINHAS_CAT": linhas_cat,
        "N_COLS": str(n_cols), "N_PESSOAIS": str(n_pessoais), "N_TESTES": str(len(testes)), "N_OK": str(ok),
        "N_CONTRATOS": str(contratos), "N_INC": str(sum(i["barrado"] for i in incidentes)), "N_INC_TOTAL": str(len(incidentes)),
        "N_CLIENTES": f"{n_clientes:,}".replace(",", "."), "N_CRM": f"{n_crm:,}".replace(",", "."),
        "N_TRANS": f"{n_trans:,}".replace(",", "."), "ALVO": alvo,
        "RET_ANON": str(retencao.get("anonimizar", 0)), "RET_MKT": str(retencao.get("excluir da base de marketing", 0)),
        "GERADO": gerado, "REPO": REPO,
        "TH_PAPEIS": "".join(f"<th>{bi(pt, en)}</th>" for _, pt, en in PAPEIS),
    }.items():
        pagina = pagina.replace("{{" + k + "}}", v)
    (RAIZ / "site").mkdir(exist_ok=True)
    (RAIZ / "site" / "index.html").write_text(pagina, encoding="utf-8")
    for img in ("icone.jpg", "mercurio-e-argos.jpg"):
        shutil.copyfile(RAIZ / "scripts" / img, RAIZ / "site" / img)
    print(f"site/index.html gerado — {n_cols} colunas, {len(testes)} testes, {len(incidentes)} incidentes")


TEMPLATE = (Path(__file__).with_name("pagina_template.html")).read_text(encoding="utf-8")

if __name__ == "__main__":
    main()
