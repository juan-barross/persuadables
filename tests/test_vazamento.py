"""Nenhuma variável do perfil pode usar informação da data de corte em diante.

A ideia do teste: se apagarmos ou mexermos em tudo o que aconteceu a partir do corte,
o perfil tem que sair idêntico. Se mudar uma casa decimal, alguma variável olhou o
futuro.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from campanha import run_sql

CORTE = pd.Timestamp(run_sql.DATA_DE_CORTE)


def perfil(parquet: Path) -> pd.DataFrame:
    con = run_sql.conectar(parquet)
    return run_sql.construir_perfil(con)


def reescrever(parquet: Path, tabela: str, sql: str) -> None:
    """Aplica um SELECT sobre a tabela e grava por cima do Parquet."""
    arquivo = parquet / f"{tabela}.parquet"
    tmp = parquet / f"{tabela}.tmp.parquet"
    origem = f"'{arquivo.as_posix()}'"
    duckdb.execute(f"COPY ({sql.format(t=origem)}) TO '{tmp.as_posix()}' (FORMAT parquet)")
    tmp.replace(arquivo)


def test_amostra_tem_futuro_plantado(amostra_base: Path) -> None:
    """Sem compras depois do corte, os testes abaixo passariam sem provar nada."""
    compras = pd.read_parquet(amostra_base / "purchases.parquet")
    clientes = pd.read_parquet(amostra_base / "clients.parquet")
    assert (compras["transaction_datetime"] >= CORTE).sum() > 100
    assert (compras["transaction_datetime"] == CORTE).any()
    assert (clientes["first_redeem_date"] >= CORTE).sum() > 10


def test_apagar_o_futuro_nao_muda_o_perfil(amostra_copia: Path) -> None:
    antes = perfil(amostra_copia)
    reescrever(
        amostra_copia,
        "purchases",
        "SELECT * FROM {t} WHERE transaction_datetime < TIMESTAMP '" + str(CORTE) + "'",
    )
    assert_frame_equal(antes, perfil(amostra_copia))


def test_mexer_no_futuro_nao_muda_o_perfil(amostra_copia: Path) -> None:
    antes = perfil(amostra_copia)
    corte = f"TIMESTAMP '{CORTE}'"
    reescrever(
        amostra_copia,
        "purchases",
        f"""SELECT * REPLACE (
                CASE WHEN transaction_datetime >= {corte} THEN purchase_sum * 1000
                     ELSE purchase_sum END AS purchase_sum,
                CASE WHEN transaction_datetime >= {corte} THEN 'loja_nova'
                     ELSE store_id END AS store_id)
            FROM {{t}}""",
    )
    reescrever(
        amostra_copia,
        "clients",
        f"""SELECT * REPLACE (
                CASE WHEN first_redeem_date >= {corte} THEN {corte} + INTERVAL 40 DAY
                     ELSE first_redeem_date END AS first_redeem_date)
            FROM {{t}}""",
    )
    assert_frame_equal(antes, perfil(amostra_copia))


def test_resgate_depois_do_corte_conta_como_nao_resgatou(amostra_base: Path) -> None:
    p = perfil(amostra_base).set_index("client_id")
    clientes = pd.read_parquet(amostra_base / "clients.parquet").set_index("client_id")
    futuros = clientes.index[clientes["first_redeem_date"] >= CORTE].intersection(p.index)
    assert len(futuros) > 0
    assert (p.loc[futuros, "ja_resgatou"] == 0).all()


def test_uma_linha_por_cliente_do_experimento(amostra_base: Path) -> None:
    p = perfil(amostra_base)
    exp = pd.read_parquet(amostra_base / "uplift_train.parquet")
    assert p["client_id"].is_unique
    assert set(p["client_id"]) == set(exp["client_id"])


@pytest.mark.parametrize(
    "arquivo", sorted((run_sql.SQL / "10_perfil_cliente").glob("*.sql")), ids=lambda f: f.name
)
def test_todo_sql_que_le_compras_filtra_pelo_corte(arquivo: Path) -> None:
    """Defesa extra: quem lê purchases direto tem que citar a data de corte."""
    texto = arquivo.read_text(encoding="utf-8")
    if re.search(r"\bFROM\s+purchases\b", texto, re.IGNORECASE):
        assert "getvariable('data_de_corte')" in texto
