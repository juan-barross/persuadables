"""Linha de comando: `uv run campanha <passo>`."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from campanha import amostra as amostra_mod
from campanha import ingest, run_sql

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@dataclass
class Contexto:
    parquet: Path = ingest.PARQUET
    reports: Path = Path("reports")


ctx = Contexto()


@app.callback()
def principal(
    amostra: bool = typer.Option(
        False, help="usa a amostra sintética em data/amostra/ e grava em data/amostra/reports/"
    ),
) -> None:
    if amostra:
        ctx.parquet = Path("data/amostra/parquet")
        ctx.reports = Path("data/amostra/reports")
    ctx.reports.mkdir(parents=True, exist_ok=True)


@app.command()
def baixar(
    base: str = typer.Option(None, help="x5 ou criteo; vazio baixa as duas"),
    forcar: bool = typer.Option(False, help="baixa e converte de novo"),
) -> None:
    """Baixa os CSVs e converte para Parquet em data/parquet/."""
    for fonte in ingest.fontes(base):
        t0 = time.perf_counter()
        ingest.baixar(fonte, forcar)
        ingest.converter(fonte, forcar)
        mb = fonte.parquet.stat().st_size / 2**20
        console.print(f"{fonte.tabela:<14} {mb:8.0f} MB  {time.perf_counter() - t0:6.0f} s")


@app.command()
def amostra() -> None:
    """Gera a amostra sintética em data/amostra/parquet (sem rede)."""
    destino = amostra_mod.gerar(Path("data/amostra/parquet"))
    console.print(f"amostra gravada em {destino.as_posix()}")


@app.command()
def auditar() -> None:
    """Roda sql/00_auditoria e grava reports/auditoria.md."""
    con = run_sql.conectar(ctx.parquet)
    resultados = run_sql.rodar_pasta(con, "00_auditoria", ctx.reports)
    texto = run_sql.relatorio_md(
        "Auditoria dos dados da X5",
        resultados,
        f"Gerado por `campanha auditar` sobre `{ctx.parquet.as_posix()}`. "
        f"Data de corte: {run_sql.DATA_DE_CORTE}.",
    )
    (ctx.reports / "auditoria.md").write_text(texto, encoding="utf-8")
    for r in resultados:
        console.print(f"{r.nome:<20} {r.segundos:6.1f} s")


@app.command()
def perfil() -> None:
    """Roda sql/10_perfil_cliente e grava perfil_cliente.parquet ao lado dos dados."""
    t0 = time.perf_counter()
    con = run_sql.conectar(ctx.parquet)
    df = run_sql.construir_perfil(con, ctx.reports)
    df.to_parquet(ctx.parquet / "perfil_cliente.parquet", index=False)
    resumo = con.sql("SELECT * FROM perfil_cliente LIMIT 0").columns
    console.print(
        f"perfil_cliente: {len(df):,} linhas, {len(resumo) - 3} variáveis, "
        f"{time.perf_counter() - t0:.0f} s"
    )


@app.command()
def placar() -> None:
    """Sorteio, efeito, CUPED, poder e segmentos: grava reports/placar.md."""
    from campanha import placar as placar_mod

    con = run_sql.conectar(ctx.parquet)
    r = placar_mod.rodar(con, ctx.reports)
    console.print(
        f"efeito {r['efeito_pp']:+.2f} p.p. [{r['ic_inf_pp']:.2f}; {r['ic_sup_pp']:.2f}], "
        f"SRM p = {r['p_srm']:.3f}, CUPED reduz a variância em "
        f"{r['cuped_multi']['reducao_variancia']:.1%}"
    )


@app.command()
def uplift() -> None:
    """Propensão, S-, T-, X-learner e class transformation: grava reports/uplift.md."""
    import pandas as pd

    from campanha import uplift as uplift_mod

    t0 = time.perf_counter()
    perfil = pd.read_parquet(ctx.parquet / "perfil_cliente.parquet")
    r = uplift_mod.rodar(perfil, ctx.reports, ctx.parquet)
    teste = r["tabela"][r["tabela"].conjunto == "teste"].set_index("modelo")
    for nome, linha in teste.iterrows():
        console.print(f"{nome:<22} AUUC {linha.auuc:.4f}  top30 {linha.uplift_top30_pp:+.2f} p.p.")
    console.print(f"escolhido: {r['escolhido']} ({time.perf_counter() - t0:.0f} s)")


@app.command()
def decisao(
    custo: float = typer.Option(3.0, help="custo por contato, em rublos"),
    margem: float = typer.Option(0.20, help="margem bruta sobre o ticket"),
) -> None:
    """Orçamento contra compradores incrementais por estratégia: grava reports/decisao.md."""
    from campanha import decisao as decisao_mod

    p = decisao_mod.Premissas(custo_por_contato=custo, margem=margem)
    r = decisao_mod.rodar(ctx.parquet, ctx.reports, p)
    m = r["melhor"]
    console.print(
        f"melhor: uplift para {m['fracao']:.0%} da base, lucro {m['lucro']:,.0f} "
        f"contra {r['todos']['lucro']:,.0f} mandando para todos"
    )


@app.command()
def escala() -> None:
    """Placar em SQL sobre os 14 mi de linhas da Criteo, com tempo e memória."""
    from campanha import escala as escala_mod

    con = run_sql.conectar(ctx.parquet)
    r = escala_mod.rodar(con, ctx.reports, ctx.parquet)
    m = r["medicoes"]
    console.print(
        f"{r['n']:,} linhas: {m['segundos'].sum():.1f} s, "
        f"pico {m['pico_memoria_processo_mb'].max():,.0f} MB"
    )


if __name__ == "__main__":
    app()
