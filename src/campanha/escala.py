"""Prova de escala: o placar em SQL rodando sobre os 14 milhões de linhas da Criteo.

Mede o tempo de cada consulta e o pico de memória do processo (DuckDB roda dentro dele),
lendo direto do Parquet, sem carregar a tabela em memória.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import duckdb
import pandas as pd
import psutil

from campanha import run_sql


def pico_memoria_mb() -> float:
    info = psutil.Process().memory_info()
    pico = getattr(info, "peak_wset", None)  # Windows
    if pico is None:
        import resource  # Linux: ru_maxrss em KB

        pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return pico / 2**20


def rodar(con: duckdb.DuckDBPyConnection, reports: Path, parquet: Path) -> dict:
    n = con.sql("SELECT COUNT(*) FROM criteo").fetchone()[0]
    medicoes, resultados = [], {}
    rss_inicial = psutil.Process().memory_info().rss / 2**20
    for arquivo in sorted((run_sql.SQL / "30_escala_criteo").glob("*.sql")):
        r = run_sql.rodar_arquivo(con, arquivo)
        resultados[r.nome] = r.df
        medicoes.append(
            {
                "consulta": r.nome,
                "segundos": r.segundos,
                "linhas_por_segundo_mi": n / r.segundos / 1e6,
                "pico_memoria_processo_mb": pico_memoria_mb(),
            }
        )
    medicoes = pd.DataFrame(medicoes)
    destino = reports / "30_escala_criteo"
    destino.mkdir(parents=True, exist_ok=True)
    medicoes.to_csv(destino / "medicoes.csv", index=False)
    for nome, df in resultados.items():
        df.to_csv(destino / f"{nome}.csv", index=False)

    maquina = {
        "sistema": f"{platform.system()} {platform.release()}",
        "cpu_logicas": os.cpu_count(),
        "ram_total_gb": psutil.virtual_memory().total / 2**30,
        "duckdb": duckdb.__version__,
        "threads_duckdb": con.sql("SELECT current_setting('threads')").fetchone()[0],
        "parquet_mb": (parquet / "criteo.parquet").stat().st_size / 2**20,
        "rss_inicial_mb": rss_inicial,
    }
    r = {"n": n, "medicoes": medicoes, "resultados": resultados, "maquina": maquina}
    (reports / "escala_criteo.md").write_text(relatorio(r), encoding="utf-8")
    return r


def relatorio(r: dict) -> str:
    m, res = r["maquina"], r["resultados"]
    s = res["01_sorteio"].iloc[0]
    ef = res["03_efeito"].set_index("desfecho")
    c = res["04_cuped"].iloc[0]
    total = r["medicoes"]["segundos"].sum()
    pico = r["medicoes"]["pico_memoria_processo_mb"].max()
    return f"""# Prova de escala: o placar na Criteo

Gerado por `campanha escala`. As mesmas consultas do placar da X5 (sorteio, balanço com
`UNPIVOT`, efeito com IC e CUPED), reescritas para a Criteo Uplift v2.1 em
`sql/30_escala_criteo/`.

## Tempo e memória

**{r["n"]:,} linhas, {total:.1f} s no total, pico de memória do processo de {pico:,.0f} MB**,
lendo direto de um Parquet de {m["parquet_mb"]:.0f} MB.

{run_sql.tabela_md(r["medicoes"], casas=2)}

Máquina: {m["sistema"]}, {m["cpu_logicas"]} CPUs lógicas, {m["ram_total_gb"]:.0f} GB de RAM,
DuckDB {m["duckdb"]} com {m["threads_duckdb"]} threads. O pico é do processo Python inteiro
(inclui pandas e o próprio DuckDB) e é cumulativo: cada linha mostra o maior valor até ali.

## O que o placar diz

- **Sorteio:** {s["prop_tratamento"]:.4%} de tratados, contra 85% esperados
  (χ² = {s["qui2_vs_85pct"]:.2f}). A exposição ao anúncio é {s["exposicao_tratados"]:.2%} nos
  tratados e {s["exposicao_controle"]:.2%} no controle: por isso o tratamento é `treatment`, e
  não `exposure`, que depende do usuário.
- **Balanço:** maior |SMD| entre as 12 variáveis = {res["02_balanco"]["smd"].abs().max():.4f}.
- **Visita:** {ef.loc["visit", "taxa_c"]:.2%} no controle, efeito de
  {ef.loc["visit", "efeito_pp"]:+.3f} p.p. (IC [{ef.loc["visit", "ic_inf_pp"]:.3f};
  {ef.loc["visit", "ic_sup_pp"]:.3f}]), {ef.loc["visit", "efeito_relativo_pct"]:+.1f}% relativo.
- **Conversão:** {ef.loc["conversion", "taxa_c"]:.3%} no controle, efeito de
  {ef.loc["conversion", "efeito_pp"]:+.4f} p.p. (IC [{ef.loc["conversion", "ic_inf_pp"]:.4f};
  {ef.loc["conversion", "ic_sup_pp"]:.4f}]), {ef.loc["conversion", "efeito_relativo_pct"]:+.1f}% relativo.
- **CUPED em visita:** a melhor covariável (`{c["covariavel"]}`) reduz a variância em
  {c["reducao_variancia"]:.1%} e o IC em {c["reducao_largura_ic"]:.1%}.

{run_sql.tabela_md(res["03_efeito"], casas=4)}
"""
