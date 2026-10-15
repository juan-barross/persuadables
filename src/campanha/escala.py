from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import psutil

from campanha import relatorio, run_sql

MEGABYTE = 2**20
GIGABYTE = 2**30


@dataclass(frozen=True)
class ResultadoEscala:
    linhas: int
    segundos: float
    pico_memoria_mb: float


def pico_de_memoria_mb() -> float:
    memoria = psutil.Process().memory_info()
    pico_no_windows = getattr(memoria, "peak_wset", None)
    if pico_no_windows is not None:
        return pico_no_windows / MEGABYTE
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / MEGABYTE


def rodar(con: duckdb.DuckDBPyConnection, reports: Path, parquet: Path) -> ResultadoEscala:
    linhas = con.sql("SELECT COUNT(*) FROM criteo").fetchone()[0]
    consultas, medicoes = {}, []
    for arquivo in sorted((run_sql.SQL / "30_escala_criteo").glob("*.sql")):
        r = run_sql.rodar_arquivo(con, arquivo)
        consultas[r.nome] = r.df
        medicoes.append(
            {
                "consulta": r.nome,
                "segundos": r.segundos,
                "linhas_por_segundo_mi": linhas / r.segundos / 1e6,
                "pico_memoria_processo_mb": pico_de_memoria_mb(),
            }
        )
    medicoes = pd.DataFrame(medicoes)

    destino = reports / "30_escala_criteo"
    relatorio.salvar_csv(medicoes, destino / "medicoes.csv")
    for nome, df in consultas.items():
        relatorio.salvar_csv(df, destino / f"{nome}.csv")

    resultado = ResultadoEscala(
        linhas=linhas,
        segundos=float(medicoes["segundos"].sum()),
        pico_memoria_mb=float(medicoes["pico_memoria_processo_mb"].max()),
    )
    texto = texto_do_relatorio(resultado, consultas, medicoes, con, parquet)
    (reports / "escala_criteo.md").write_text(texto, encoding="utf-8")
    return resultado


def texto_do_relatorio(
    resultado: ResultadoEscala,
    consultas: dict[str, pd.DataFrame],
    medicoes: pd.DataFrame,
    con: duckdb.DuckDBPyConnection,
    parquet: Path,
) -> str:
    efeito = consultas["03_efeito"].set_index("desfecho")
    return relatorio.preencher(
        "escala",
        linhas=resultado.linhas,
        segundos=resultado.segundos,
        pico_memoria_mb=resultado.pico_memoria_mb,
        parquet_mb=(parquet / "criteo.parquet").stat().st_size / MEGABYTE,
        tabela_medicoes=relatorio.tabela(medicoes, casas=2),
        sistema=f"{platform.system()} {platform.release()}",
        cpu_logicas=os.cpu_count(),
        ram_total_gb=psutil.virtual_memory().total / GIGABYTE,
        versao_duckdb=duckdb.__version__,
        threads_duckdb=con.sql("SELECT current_setting('threads')").fetchone()[0],
        sorteio=consultas["01_sorteio"].iloc[0],
        max_abs_smd=consultas["02_balanco"]["smd"].abs().max(),
        visita=efeito.loc["visit"],
        conversao=efeito.loc["conversion"],
        cuped=consultas["04_cuped"].iloc[0],
        tabela_efeito=relatorio.tabela(consultas["03_efeito"], casas=4),
    )
