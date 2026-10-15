from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from persuadables import relatorio

SQL = Path(__file__).resolve().parents[2] / "sql"
DATA_DE_CORTE = "2019-03-19"
TABELAS = ("clients", "uplift_train", "purchases", "perfil_cliente", "criteo")
DIRETORIO_TEMPORARIO = Path("data") / "duckdb_tmp"


@dataclass
class Resultado:
    nome: str
    df: pd.DataFrame | None
    segundos: float


def conectar(parquet: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    DIRETORIO_TEMPORARIO.mkdir(parents=True, exist_ok=True)
    con.execute("SET enable_progress_bar = false")
    con.execute(f"SET temp_directory = '{DIRETORIO_TEMPORARIO.resolve().as_posix()}'")
    con.execute(f"SET VARIABLE data_de_corte = TIMESTAMP '{DATA_DE_CORTE}'")
    for tabela in TABELAS:
        arquivo = parquet / f"{tabela}.parquet"
        if arquivo.exists():
            con.execute(f"CREATE OR REPLACE VIEW {tabela} AS SELECT * FROM '{arquivo.as_posix()}'")
    return con


def rodar_arquivo(con: duckdb.DuckDBPyConnection, arquivo: Path) -> Resultado:
    inicio = time.perf_counter()
    resultado = con.execute(arquivo.read_text(encoding="utf-8"))
    df = resultado.df() if resultado.description else None
    return Resultado(arquivo.stem, df, time.perf_counter() - inicio)


def rodar_pasta(
    con: duckdb.DuckDBPyConnection, pasta: str, saida: Path | None = None
) -> list[Resultado]:
    resultados = [rodar_arquivo(con, arquivo) for arquivo in sorted((SQL / pasta).glob("*.sql"))]
    if saida is not None:
        _salvar_csvs(resultados, saida / pasta)
    return resultados


def construir_perfil(con: duckdb.DuckDBPyConnection, saida: Path | None = None) -> pd.DataFrame:
    con.execute("DROP VIEW IF EXISTS perfil_cliente")
    rodar_pasta(con, "10_perfil_cliente", saida)
    return con.sql("SELECT * FROM perfil_cliente ORDER BY client_id").df()


def _salvar_csvs(resultados: list[Resultado], destino: Path) -> None:
    for r in resultados:
        if r.df is not None:
            relatorio.salvar_csv(r.df, destino / f"{r.nome}.csv")
