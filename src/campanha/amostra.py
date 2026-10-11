"""Amostra sintética com o mesmo esquema da X5 e anomalias plantadas.

Serve para a CI (a licença da X5 não é clara, então não redistribuímos o dado) e para
o teste de vazamento: na base real não existe compra depois do corte, então o teste
só prova alguma coisa se houver compras futuras plantadas para o perfil ignorar.

O efeito da campanha é plantado só nos clientes inativos há mais de 30 dias, para o
placar e os modelos de uplift terem algo a encontrar.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CORTE = pd.Timestamp("2019-03-19")
INICIO = pd.Timestamp("2018-11-21")


def gerar(destino: Path, n_clientes: int = 3000, semente: int = 7) -> Path:
    rng = np.random.default_rng(semente)
    destino.mkdir(parents=True, exist_ok=True)
    ids = [f"c{i:05d}" for i in range(n_clientes)]

    emissao = INICIO - pd.to_timedelta(rng.integers(30, 900, n_clientes), unit="D")
    resgate = emissao + pd.to_timedelta(rng.integers(1, 700, n_clientes), unit="D")
    resgate = pd.Series(resgate).where(rng.random(n_clientes) < 0.7)  # 30% nunca resgatou
    idade = rng.integers(18, 80, n_clientes)
    idade[:5] = [150, -1, 3, 999, 120]  # idades impossíveis
    clients = pd.DataFrame(
        {
            "client_id": ids,
            "first_issue_date": emissao,
            "first_redeem_date": resgate,
            "age": idade,
            "gender": rng.choice(["F", "M", "U"], n_clientes),
        }
    )
    # Resgates depois do corte: o perfil precisa tratá-los como "ainda não resgatou".
    clients.loc[5:60, "first_redeem_date"] = CORTE + pd.Timedelta(days=3)

    linhas = []
    dias = (CORTE - INICIO).days
    ultima = {}
    for i, cid in enumerate(ids):
        n_trn = int(rng.poisson(12)) + 1
        # 25% dos clientes param de comprar 30 a 90 dias antes do corte
        fim = dias - (int(rng.integers(31, 90)) if rng.random() < 0.25 else 0)
        for t in range(n_trn):
            quando = INICIO + pd.Timedelta(
                days=int(rng.integers(0, max(fim, 1))), seconds=int(rng.integers(0, 86400))
            )
            quando = min(quando, CORTE - pd.Timedelta(seconds=1))
            ultima[cid] = max(ultima.get(cid, quando), quando)
            linhas += _itens(rng, cid, f"t{i:05d}_{t:03d}", quando)

    # Compras na data de corte ou depois, com valores enormes: se o perfil usar
    # qualquer uma delas, as variáveis mudam e o teste de vazamento pega.
    for i, cid in enumerate(ids[::10]):
        quando = CORTE + pd.Timedelta(days=int(rng.integers(0, 20)), hours=int(rng.integers(0, 23)))
        linhas += _itens(rng, cid, f"futuro{i:05d}", quando, valor=50_000.0)
    # Uma compra exatamente na data de corte (limite do <)
    linhas += _itens(rng, ids[1], "futuro_no_corte", CORTE, valor=77_777.0)
    # Colisão de transaction_id entre dois clientes, como na X5
    linhas += _itens(rng, ids[2], "colisao", CORTE - pd.Timedelta(days=5))
    linhas += _itens(rng, ids[3], "colisao", CORTE - pd.Timedelta(days=9))

    purchases = pd.DataFrame(linhas)

    exp = pd.DataFrame({"client_id": ids[: int(n_clientes * 0.6)]})
    exp["treatment_flg"] = rng.integers(0, 2, len(exp))
    inativo = exp["client_id"].map(lambda c: (CORTE - ultima[c]).days > 30).to_numpy()
    p = 0.55 + 0.15 * exp["treatment_flg"].to_numpy() * inativo - 0.10 * inativo
    exp["target"] = (rng.random(len(exp)) < p).astype(int)

    clients.to_parquet(destino / "clients.parquet", index=False)
    exp.to_parquet(destino / "uplift_train.parquet", index=False)
    purchases.to_parquet(destino / "purchases.parquet", index=False)
    return destino


def _itens(rng, cid: str, trn: str, quando: pd.Timestamp, valor: float | None = None) -> list:
    n_itens = int(rng.integers(1, 6))
    total = valor if valor is not None else float(round(rng.gamma(2.0, 180.0), 2))
    recebidos = round(total * 0.01, 1)
    gastos = -float(rng.choice([0, 0, 0, 20, 50]))
    loja = f"s{int(rng.integers(0, 40)):03d}"
    return [
        {
            "client_id": cid,
            "transaction_id": trn,
            "transaction_datetime": quando,
            "regular_points_received": recebidos,
            "express_points_received": 0.0,
            "regular_points_spent": gastos,
            "express_points_spent": 0.0,
            "purchase_sum": total,  # valor da transação, repetido em cada item como na X5
            "store_id": loja,
            "product_id": f"p{int(rng.integers(0, 500)):04d}",
            "product_quantity": float(rng.choice([0.0, 1.0, 1.0, 2.0])),  # 0 = por peso
            "trn_sum_from_iss": round(total / n_itens, 2),
            "trn_sum_from_red": np.nan,
        }
        for _ in range(n_itens)
    ]
