from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CORTE = pd.Timestamp("2019-03-19")
INICIO = pd.Timestamp("2018-11-21")
DIAS_DE_HISTORICO = (CORTE - INICIO).days

FRACAO_NO_EXPERIMENTO = 0.6
FRACAO_QUE_PAROU_DE_COMPRAR = 0.25
FRACAO_QUE_JA_RESGATOU = 0.7
TAXA_DE_COMPRA_BASE = 0.55
QUEDA_NOS_INATIVOS = 0.10
EFEITO_PLANTADO_NOS_INATIVOS = 0.15
VALOR_DAS_COMPRAS_FUTURAS = 50_000.0
IDADES_IMPOSSIVEIS = [150, -1, 3, 999, 120]

COLUNAS_DE_PURCHASES = (
    "client_id transaction_id transaction_datetime regular_points_received "
    "express_points_received regular_points_spent express_points_spent purchase_sum store_id "
    "product_id product_quantity trn_sum_from_iss trn_sum_from_red"
).split()


def gerar(destino: Path, n_clientes: int = 3000, semente: int = 7) -> Path:
    rng = np.random.default_rng(semente)
    ids = np.array([f"c{i:05d}" for i in range(n_clientes)])

    transacoes_passadas = _transacoes_antes_do_corte(rng, ids)
    ultima_compra = transacoes_passadas.groupby("client_id")["transaction_datetime"].max()
    transacoes = pd.concat(
        [transacoes_passadas, _transacoes_plantadas(rng, ids)], ignore_index=True
    )

    destino.mkdir(parents=True, exist_ok=True)
    _clientes(rng, ids).to_parquet(destino / "clients.parquet", index=False)
    _experimento(rng, ids, ultima_compra).to_parquet(destino / "uplift_train.parquet", index=False)
    _itens(rng, transacoes).to_parquet(destino / "purchases.parquet", index=False)
    return destino


def _clientes(rng: np.random.Generator, ids: np.ndarray) -> pd.DataFrame:
    n = len(ids)
    emissao = INICIO - pd.to_timedelta(rng.integers(30, 900, n), unit="D")
    resgate = pd.Series(emissao + pd.to_timedelta(rng.integers(1, 700, n), unit="D"))
    resgate = resgate.where(rng.random(n) < FRACAO_QUE_JA_RESGATOU)
    resgate.iloc[5:61] = CORTE + pd.Timedelta(days=3)
    idade = rng.integers(18, 80, n)
    idade[: len(IDADES_IMPOSSIVEIS)] = IDADES_IMPOSSIVEIS
    return pd.DataFrame(
        {
            "client_id": ids,
            "first_issue_date": emissao,
            "first_redeem_date": resgate,
            "age": idade,
            "gender": rng.choice(["F", "M", "U"], n),
        }
    )


def _transacoes_antes_do_corte(rng: np.random.Generator, ids: np.ndarray) -> pd.DataFrame:
    n = len(ids)
    por_cliente = rng.poisson(12, n) + 1
    parou_de_comprar = rng.random(n) < FRACAO_QUE_PAROU_DE_COMPRAR
    dias_parado = np.where(parou_de_comprar, rng.integers(31, 90, n), 0)

    cliente = np.repeat(np.arange(n), por_cliente)
    primeira_do_cliente = np.repeat(np.cumsum(por_cliente) - por_cliente, por_cliente)
    sequencia = np.arange(len(cliente)) - primeira_do_cliente
    ultimo_dia_com_compra = DIAS_DE_HISTORICO - dias_parado[cliente]
    dia = np.floor(rng.random(len(cliente)) * ultimo_dia_com_compra)
    segundo = rng.integers(0, 86_400, len(cliente))

    return pd.DataFrame(
        {
            "client_id": ids[cliente],
            "transaction_id": [
                f"t{c:05d}_{s:03d}" for c, s in zip(cliente, sequencia, strict=True)
            ],
            "transaction_datetime": INICIO
            + pd.to_timedelta(dia, unit="D")
            + pd.to_timedelta(segundo, unit="s"),
            "purchase_sum": np.round(rng.gamma(2.0, 180.0, len(cliente)), 2),
        }
    )


def _transacoes_plantadas(rng: np.random.Generator, ids: np.ndarray) -> pd.DataFrame:
    com_compra_futura = ids[::10]
    n = len(com_compra_futura)
    futuras = pd.DataFrame(
        {
            "client_id": com_compra_futura,
            "transaction_id": [f"futuro{i:05d}" for i in range(n)],
            "transaction_datetime": CORTE
            + pd.to_timedelta(rng.integers(0, 20, n), unit="D")
            + pd.to_timedelta(rng.integers(0, 23, n), unit="h"),
            "purchase_sum": VALOR_DAS_COMPRAS_FUTURAS,
        }
    )
    casos_de_borda = pd.DataFrame(
        {
            "client_id": [ids[1], ids[2], ids[3]],
            "transaction_id": ["futuro_no_corte", "colisao", "colisao"],
            "transaction_datetime": [
                CORTE,
                CORTE - pd.Timedelta(days=5),
                CORTE - pd.Timedelta(days=9),
            ],
            "purchase_sum": [77_777.0, 412.5, 233.9],
        }
    )
    return pd.concat([futuras, casos_de_borda], ignore_index=True)


def _itens(rng: np.random.Generator, transacoes: pd.DataFrame) -> pd.DataFrame:
    n = len(transacoes)
    itens_por_transacao = rng.integers(1, 6, n)
    por_transacao = transacoes.assign(
        regular_points_received=np.round(transacoes["purchase_sum"] * 0.01, 1),
        express_points_received=0.0,
        regular_points_spent=-rng.choice([0.0, 0.0, 0.0, 20.0, 50.0], n),
        express_points_spent=0.0,
        store_id=[f"s{loja:03d}" for loja in rng.integers(0, 40, n)],
        trn_sum_from_iss=np.round(transacoes["purchase_sum"] / itens_por_transacao, 2),
    )
    itens = por_transacao.loc[np.repeat(np.arange(n), itens_por_transacao)].reset_index(drop=True)
    return itens.assign(
        product_id=[f"p{produto:04d}" for produto in rng.integers(0, 500, len(itens))],
        product_quantity=rng.choice([0.0, 1.0, 1.0, 2.0], len(itens)),
        trn_sum_from_red=np.nan,
    )[COLUNAS_DE_PURCHASES]


def _experimento(
    rng: np.random.Generator, ids: np.ndarray, ultima_compra: pd.Series
) -> pd.DataFrame:
    participantes = ids[: int(len(ids) * FRACAO_NO_EXPERIMENTO)]
    tratado = rng.integers(0, 2, len(participantes))
    dias_sem_comprar = (CORTE - ultima_compra.loc[participantes]).dt.days.to_numpy()
    inativo = dias_sem_comprar > 30
    chance_de_comprar = (
        TAXA_DE_COMPRA_BASE
        - QUEDA_NOS_INATIVOS * inativo
        + EFEITO_PLANTADO_NOS_INATIVOS * tratado * inativo
    )
    return pd.DataFrame(
        {
            "client_id": participantes,
            "treatment_flg": tratado,
            "target": (rng.random(len(participantes)) < chance_de_comprar).astype(int),
        }
    )
