"""Linha de comando: `uv run campanha <passo>`."""

from __future__ import annotations

import time

import typer
from rich.console import Console

from campanha import ingest

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


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


if __name__ == "__main__":
    app()
