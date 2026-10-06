"""Gera a base sintética do Argos: clientes, cartões e transações de uma fintech fictícia.

Todos os dados são inventados (Faker pt_BR + numpy, semente fixa). Os CPFs têm dígito
verificador válido para que as regras de mascaramento sejam testadas em formato real,
mas não correspondem a ninguém. Os números de cartão usam o prefixo de teste 400000,
que não é emitido para cartões reais.

Uso:
    python scripts/gerar_dados.py              # base normal
    python scripts/gerar_dados.py --incidente schema    # produtor renomeia a coluna valor
    python scripts/gerar_dados.py --incidente unidade   # produtor passa a mandar valor em centavos
"""
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEMENTE = 42
DATA_REF = date(2026, 9, 30)          # data de referência fixa: a base é reprodutível
N_CLIENTES = 5_000
SAIDA = Path(__file__).resolve().parents[1] / "data" / "raw"

rng = np.random.default_rng(SEMENTE)
fake = Faker("pt_BR")
Faker.seed(SEMENTE)

UFS = ["SP"] * 40 + ["RJ"] * 12 + ["MG"] * 10 + ["RS"] * 6 + ["PR"] * 6 + ["BA"] * 6 + \
      ["SC"] * 4 + ["PE"] * 4 + ["CE"] * 4 + ["GO"] * 4 + ["DF"] * 4
MCCS = {  # mcc: (descrição, ticket médio em R$)
    "5411": ("Supermercados", 180), "5812": ("Restaurantes", 75), "5814": ("Fast food", 38),
    "5541": ("Postos de combustível", 160), "5912": ("Farmácias", 85), "4121": ("Transporte por app", 28),
    "5311": ("Lojas de departamento", 240), "5732": ("Eletrônicos", 900), "4899": ("Streaming e assinaturas", 45),
    "7995": ("Apostas", 120), "6051": ("Quase-dinheiro / cripto", 1500), "4829": ("Transferência de dinheiro", 700),
}


def dv_cpf(base: str) -> str:
    for n in (9, 10):
        soma = sum(int(d) * p for d, p in zip(base, range(n + 1, 1, -1)))
        r = (soma * 10) % 11
        base += str(0 if r == 10 else r)
    return base


def cpf() -> str:
    b = dv_cpf("".join(str(d) for d in rng.integers(0, 10, 9)))
    return f"{b[:3]}.{b[3:6]}.{b[6:9]}-{b[9:]}"


def luhn(pan15: str) -> str:
    total = 0
    for i, d in enumerate(reversed(pan15)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return pan15 + str((10 - total % 10) % 10)


def gerar_clientes() -> pd.DataFrame:
    linhas = []
    for i in range(1, N_CLIENTES + 1):
        cadastro = DATA_REF - timedelta(days=int(rng.integers(30, 365 * 18)))
        nasc = DATA_REF - timedelta(days=int(rng.integers(18 * 365, 80 * 365)))
        encerrado = rng.random() < 0.18
        encerramento = None
        if encerrado:
            dias_ate_hoje = (DATA_REF - cadastro).days
            encerramento = cadastro + timedelta(days=int(rng.integers(30, max(31, dias_ate_hoje))))
        consent = rng.random() < 0.62
        revogacao = None
        if consent and rng.random() < 0.15:
            revogacao = cadastro + timedelta(days=int(rng.integers(1, max(2, (DATA_REF - cadastro).days))))
        nome = fake.name()
        uf = UFS[int(rng.integers(0, len(UFS)))]
        linhas.append({
            "id_cliente": f"C{i:06d}",
            "nome_completo": nome,
            "cpf": cpf(),
            "email": fake.unique.email(),
            "telefone": fake.cellphone_number(),
            "data_nascimento": nasc.isoformat(),
            "renda_mensal": round(float(rng.lognormal(8.2, 0.7)), 2),
            "endereco": fake.street_address(),
            "cep": fake.postcode(),
            "cidade": fake.city(),
            "uf": uf,
            "ocupacao": fake.job(),
            "pep": bool(rng.random() < 0.004),                # pessoa exposta politicamente
            "consentimento_marketing": bool(consent),
            "data_revogacao_consentimento": revogacao.isoformat() if revogacao else None,
            "data_cadastro": cadastro.isoformat(),
            "data_encerramento": encerramento.isoformat() if encerramento else None,
        })
    return pd.DataFrame(linhas)


def gerar_cartoes(clientes: pd.DataFrame) -> pd.DataFrame:
    linhas, n = [], 0
    for _, c in clientes.iterrows():
        for _ in range(1 + int(rng.random() < 0.3)):
            n += 1
            emissao = min(DATA_REF, date.fromisoformat(c.data_cadastro) + timedelta(days=int(rng.integers(0, 60))))
            status = "cancelado" if pd.notna(c.data_encerramento) else ("bloqueado" if rng.random() < 0.03 else "ativo")
            linhas.append({
                "id_cartao": f"K{n:07d}",
                "id_cliente": c.id_cliente,
                "numero_cartao": luhn("400000" + "".join(str(d) for d in rng.integers(0, 10, 9))),
                "bandeira": rng.choice(["Visa", "Mastercard", "Elo"], p=[.45, .4, .15]),
                "produto": rng.choice(["Básico", "Gold", "Platinum"], p=[.6, .3, .1]),
                "limite": float(rng.choice([500, 1000, 2000, 3500, 5000, 8000, 15000])),
                "data_emissao": emissao.isoformat(),
                "status": status,
            })
    return pd.DataFrame(linhas)


def gerar_transacoes(cartoes: pd.DataFrame, clientes: pd.DataFrame) -> pd.DataFrame:
    inicio = DATA_REF - timedelta(days=364)
    ativos = cartoes[cartoes.status != "cancelado"].reset_index(drop=True)
    mccs = list(MCCS)
    pesos = np.array([18, 14, 12, 9, 8, 12, 6, 2, 10, 4, 1, 4], dtype=float)
    pesos /= pesos.sum()
    partes = []
    # alguns cartões com comportamento atípico, para alimentar regras de PLD a jusante
    suspeitos = set(rng.choice(ativos.id_cartao, size=25, replace=False))
    for _, k in ativos.iterrows():
        n = int(rng.poisson(28))
        if n == 0:
            continue
        dias = rng.integers(0, 365, n)
        segs = rng.integers(6 * 3600, 23 * 3600, n)
        m = rng.choice(mccs, size=n, p=pesos)
        tickets = np.array([MCCS[x][1] for x in m])
        valores = np.round(rng.lognormal(np.log(tickets), 0.6), 2)
        if k.id_cartao in suspeitos:
            extra = int(rng.integers(8, 20))
            dia = int(rng.integers(300, 365))
            dias = np.concatenate([dias, np.full(extra, dia)])
            segs = np.concatenate([segs, rng.integers(0, 4 * 3600, extra)])
            m = np.concatenate([m, rng.choice(["6051", "4829", "7995"], size=extra)])
            valores = np.concatenate([valores, np.round(rng.uniform(4000, 9900, extra), 2)])
        partes.append(pd.DataFrame({
            "id_cartao": k.id_cartao, "dia": dias, "seg": segs, "mcc": m, "valor": valores,
        }))
    t = pd.concat(partes, ignore_index=True)
    t["data_hora"] = [
        (datetime.combine(inicio, datetime.min.time()) + timedelta(days=int(d), seconds=int(s))).isoformat(sep=" ")
        for d, s in zip(t.dia, t.seg)
    ]
    t = t.sort_values("data_hora").reset_index(drop=True)
    t.insert(0, "id_transacao", [f"T{i:08d}" for i in range(1, len(t) + 1)])
    t["estabelecimento"] = [f"{MCCS[x][0]} {fake.last_name()}" for x in t.mcc]
    t["canal"] = rng.choice(["presencial", "online", "carteira_digital"], size=len(t), p=[.45, .4, .15])
    t["status"] = rng.choice(["aprovada", "negada", "estornada"], size=len(t), p=[.93, .05, .02])
    return t[["id_transacao", "id_cartao", "data_hora", "valor", "mcc", "estabelecimento", "canal", "status"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidente", choices=["schema", "unidade"])
    args = ap.parse_args()

    SAIDA.mkdir(parents=True, exist_ok=True)
    clientes = gerar_clientes()
    cartoes = gerar_cartoes(clientes)
    transacoes = gerar_transacoes(cartoes, clientes)

    if args.incidente == "schema":      # o time do app renomeou a coluna sem avisar
        transacoes = transacoes.rename(columns={"valor": "valor_transacao"})
    elif args.incidente == "unidade":   # mesmo nome, outra unidade: agora vem em centavos
        transacoes["valor"] = (transacoes["valor"] * 100).round(0)

    clientes.to_csv(SAIDA / "clientes.csv", index=False)
    cartoes.to_csv(SAIDA / "cartoes.csv", index=False)
    transacoes.to_csv(SAIDA / "transacoes.csv", index=False)
    print(f"clientes={len(clientes):,} cartoes={len(cartoes):,} transacoes={len(transacoes):,}"
          + (f"  [incidente: {args.incidente}]" if args.incidente else ""))


if __name__ == "__main__":
    main()
