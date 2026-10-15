from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from campanha import run_sql

CORTE = pd.Timestamp(run_sql.DATA_DE_CORTE)
CORTE_SQL = f"TIMESTAMP '{CORTE}'"


def perfil_de(parquet: Path) -> pd.DataFrame:
    return run_sql.construir_perfil(run_sql.conectar(parquet))


def sobrescrever_com_consulta(parquet: Path, tabela: str, consulta: str) -> None:
    arquivo = parquet / f"{tabela}.parquet"
    provisorio = parquet / f"{tabela}.provisorio.parquet"
    origem = f"'{arquivo.as_posix()}'"
    duckdb.execute(
        f"COPY ({consulta.format(tabela=origem)}) TO '{provisorio.as_posix()}' (FORMAT parquet)"
    )
    provisorio.replace(arquivo)


def test_amostra_tem_futuro_plantado(amostra_base: Path) -> None:
    compras = pd.read_parquet(amostra_base / "purchases.parquet")
    clientes = pd.read_parquet(amostra_base / "clients.parquet")
    assert (compras["transaction_datetime"] >= CORTE).sum() > 100
    assert (compras["transaction_datetime"] == CORTE).any()
    assert (clientes["first_redeem_date"] >= CORTE).sum() > 10


def test_apagar_o_futuro_nao_muda_o_perfil(amostra_copia: Path) -> None:
    antes = perfil_de(amostra_copia)
    sobrescrever_com_consulta(
        amostra_copia,
        "purchases",
        f"SELECT * FROM {{tabela}} WHERE transaction_datetime < {CORTE_SQL}",
    )
    assert_frame_equal(antes, perfil_de(amostra_copia))


def test_mexer_no_futuro_nao_muda_o_perfil(amostra_copia: Path) -> None:
    antes = perfil_de(amostra_copia)
    sobrescrever_com_consulta(
        amostra_copia,
        "purchases",
        f"""
        SELECT * REPLACE (
            CASE WHEN transaction_datetime >= {CORTE_SQL} THEN purchase_sum * 1000
                 ELSE purchase_sum END AS purchase_sum,
            CASE WHEN transaction_datetime >= {CORTE_SQL} THEN 'loja_nova'
                 ELSE store_id END AS store_id
        )
        FROM {{tabela}}
        """,
    )
    sobrescrever_com_consulta(
        amostra_copia,
        "clients",
        f"""
        SELECT * REPLACE (
            CASE WHEN first_redeem_date >= {CORTE_SQL} THEN {CORTE_SQL} + INTERVAL 40 DAY
                 ELSE first_redeem_date END AS first_redeem_date
        )
        FROM {{tabela}}
        """,
    )
    assert_frame_equal(antes, perfil_de(amostra_copia))


def test_resgate_depois_do_corte_conta_como_nao_resgatou(amostra_base: Path) -> None:
    perfil = perfil_de(amostra_base).set_index("client_id")
    clientes = pd.read_parquet(amostra_base / "clients.parquet").set_index("client_id")
    resgatou_no_futuro = clientes.index[clientes["first_redeem_date"] >= CORTE]
    no_experimento = resgatou_no_futuro.intersection(perfil.index)
    assert len(no_experimento) > 0
    assert (perfil.loc[no_experimento, "ja_resgatou"] == 0).all()


def test_perfil_sai_identico_em_duas_execucoes(amostra_base: Path) -> None:
    assert_frame_equal(perfil_de(amostra_base), perfil_de(amostra_base), check_exact=True)


def test_uma_linha_por_cliente_do_experimento(amostra_base: Path) -> None:
    perfil = perfil_de(amostra_base)
    experimento = pd.read_parquet(amostra_base / "uplift_train.parquet")
    assert perfil["client_id"].is_unique
    assert set(perfil["client_id"]) == set(experimento["client_id"])


@pytest.mark.parametrize(
    "arquivo", sorted((run_sql.SQL / "10_perfil_cliente").glob("*.sql")), ids=lambda f: f.name
)
def test_todo_sql_que_le_compras_filtra_pelo_corte(arquivo: Path) -> None:
    texto = arquivo.read_text(encoding="utf-8")
    if re.search(r"\bFROM\s+purchases\b", texto, re.IGNORECASE):
        assert "getvariable('data_de_corte')" in texto.lower()
