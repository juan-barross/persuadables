"""Executa os .sql de uma pasta em ordem sobre o DuckDB.

Cada arquivo pode ter vários comandos. Se o último devolve linhas, o resultado
vira um CSV em reports/ e entra no relatório em Markdown da pasta.
"""

from __future__ import annotations

import numbers
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

SQL = Path(__file__).resolve().parents[2] / "sql"
# Último dia com compra é 2019-03-18; a comunicação começa no dia seguinte (docs/adr/0001).
DATA_DE_CORTE = "2019-03-19"

TABELAS_X5 = ("clients", "uplift_train", "purchases")


@dataclass
class Resultado:
    nome: str
    df: pd.DataFrame | None
    segundos: float


def conectar(parquet: Path, banco: Path | str = ":memory:") -> duckdb.DuckDBPyConnection:
    """Abre o banco e cria views sobre os Parquet que existirem na pasta."""
    con = duckdb.connect(str(banco))
    con.execute("SET enable_progress_bar = false")
    for tabela in (*TABELAS_X5, "perfil_cliente", "criteo"):
        arquivo = parquet / f"{tabela}.parquet"
        if arquivo.exists():
            con.execute(f"CREATE OR REPLACE VIEW {tabela} AS SELECT * FROM '{arquivo.as_posix()}'")
    con.execute(f"SET VARIABLE data_de_corte = TIMESTAMP '{DATA_DE_CORTE}'")
    return con


def rodar_arquivo(con: duckdb.DuckDBPyConnection, arquivo: Path) -> Resultado:
    t0 = time.perf_counter()
    res = con.execute(arquivo.read_text(encoding="utf-8"))
    df = res.df() if res.description else None
    return Resultado(arquivo.stem, df, time.perf_counter() - t0)


def rodar_pasta(
    con: duckdb.DuckDBPyConnection, pasta: str, saida: Path | None = None
) -> list[Resultado]:
    resultados = [rodar_arquivo(con, f) for f in sorted((SQL / pasta).glob("*.sql"))]
    if saida is not None:
        destino = saida / pasta
        destino.mkdir(parents=True, exist_ok=True)
        for r in resultados:
            if r.df is not None:
                r.df.to_csv(destino / f"{r.nome}.csv", index=False)
    return resultados


def construir_perfil(con: duckdb.DuckDBPyConnection, saida: Path | None = None) -> pd.DataFrame:
    """Roda sql/10_perfil_cliente e devolve perfil_cliente ordenado por cliente."""
    con.execute("DROP VIEW IF EXISTS perfil_cliente")
    rodar_pasta(con, "10_perfil_cliente", saida)
    return con.sql("SELECT * FROM perfil_cliente ORDER BY client_id").df()


def tabela_md(df: pd.DataFrame, casas: int = 4) -> str:
    """Tabela Markdown sem depender do tabulate."""

    def fmt(v: object) -> str:
        if isinstance(v, bool):
            return str(v)
        if isinstance(v, numbers.Integral):
            return f"{v:,}"
        if isinstance(v, numbers.Real):
            return f"{v:,.{casas}f}".rstrip("0").rstrip(".") if v == v else ""
        return "" if v is None or v is pd.NaT else str(v)

    linhas = ["| " + " | ".join(map(str, df.columns)) + " |"]
    linhas.append("|" + "|".join("---" for _ in df.columns) + "|")
    linhas += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(linhas)


def relatorio_md(titulo: str, resultados: list[Resultado], intro: str = "") -> str:
    partes = [f"# {titulo}", ""]
    if intro:
        partes += [intro, ""]
    for r in resultados:
        if r.df is None:
            continue
        partes += [f"## {r.nome}", "", tabela_md(r.df), ""]
    return "\n".join(partes)
