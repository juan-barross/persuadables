from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import typer
from rich.console import Console

from persuadables import amostra as amostra_sintetica
from persuadables import ingest, relatorio, run_sql

AMOSTRA = Path("data/amostra")

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@dataclass
class Pastas:
    parquet: Path = ingest.PARQUET
    reports: Path = Path("reports")

    @property
    def na_amostra(self) -> bool:
        return self.parquet != ingest.PARQUET


pastas = Pastas()


@app.callback()
def principal(
    amostra: bool = typer.Option(False, help="Usa a amostra sintética em data/amostra/."),
) -> None:
    if amostra:
        pastas.parquet = AMOSTRA / "parquet"
        pastas.reports = AMOSTRA / "reports"
    pastas.reports.mkdir(parents=True, exist_ok=True)


@app.command(help="Baixa os CSVs da X5 e da Criteo e converte para Parquet.")
def baixar(
    base: str = typer.Option(None, help="x5 ou criteo; vazio baixa as duas."),
    forcar: bool = typer.Option(False, help="Baixa e converte de novo."),
) -> None:
    for fonte in ingest.fontes(base):
        inicio = time.perf_counter()
        ingest.baixar(fonte, forcar)
        ingest.converter(fonte, forcar)
        megabytes = fonte.parquet.stat().st_size / 2**20
        console.print(f"{fonte.tabela:<14} {megabytes:8.0f} MB  {_desde(inicio):6.0f} s")


@app.command(help="Gera a amostra sintética, sem rede.")
def amostra() -> None:
    destino = amostra_sintetica.gerar(AMOSTRA / "parquet")
    console.print(f"amostra gravada em {destino.as_posix()}")


@app.command(help="Audita as tabelas da X5 e grava reports/auditoria.md.")
def auditar() -> None:
    con = run_sql.conectar(pastas.parquet)
    resultados = run_sql.rodar_pasta(con, "00_auditoria", pastas.reports)
    texto = relatorio.de_consultas(
        "Auditoria dos dados da X5",
        resultados,
        f"Gerado por `persuadables auditar` sobre `{pastas.parquet.as_posix()}`. "
        f"Data de corte: {run_sql.DATA_DE_CORTE}.",
    )
    (pastas.reports / "auditoria.md").write_text(texto, encoding="utf-8")
    for r in resultados:
        console.print(f"{r.nome:<20} {r.segundos:6.1f} s")


@app.command(help="Monta o perfil do cliente em SQL e grava perfil_cliente.parquet.")
def perfil() -> None:
    inicio = time.perf_counter()
    con = run_sql.conectar(pastas.parquet)
    df = run_sql.construir_perfil(con, pastas.reports)
    df.to_parquet(pastas.parquet / "perfil_cliente.parquet", index=False)
    variaveis = len(df.columns) - len(("client_id", "treatment_flg", "target"))
    console.print(
        f"perfil_cliente: {len(df):,} linhas, {variaveis} variáveis, {_desde(inicio):.0f} s"
    )


@app.command(help="Lê o experimento: sorteio, efeito, CUPED, poder e segmentos.")
def placar() -> None:
    from persuadables import placar as placar_do_experimento

    r = placar_do_experimento.rodar(run_sql.conectar(pastas.parquet), pastas.reports)
    console.print(
        f"efeito {r['efeito_pp']:+.2f} p.p. [{r['ic_inf_pp']:.2f}; {r['ic_sup_pp']:.2f}], "
        f"SRM p = {r['p_srm']:.3f}, "
        f"CUPED reduz a variância em {r['cuped_reg_reducao_variancia']:.1%}"
    )


@app.command(help="Treina propensão e modelos de uplift e compara por Qini e AUUC.")
def uplift() -> None:
    from persuadables import uplift as modelos_de_uplift

    inicio = time.perf_counter()
    perfil_cliente = pd.read_parquet(pastas.parquet / "perfil_cliente.parquet")
    r = modelos_de_uplift.rodar(perfil_cliente, pastas.reports, pastas.parquet)
    for nome, linha in r.metricas_no_teste.iterrows():
        console.print(f"{nome:<22} AUUC {linha.auuc:.4f}  top30 {linha.uplift_top30_pp:+.2f} p.p.")
    console.print(f"escolhido: {r.escolhido} ({_desde(inicio):.0f} s)")


@app.command(help="Compara orçamentos por estratégia e grava reports/decisao.md.")
def decisao(
    custo: float = typer.Option(3.0, help="Custo por contato, em rublos."),
    margem: float = typer.Option(0.20, help="Margem bruta sobre o ticket."),
) -> None:
    from persuadables import decisao as decisao_de_orcamento

    premissas = decisao_de_orcamento.Premissas(custo_por_contato=custo, margem=margem)
    r = decisao_de_orcamento.rodar(pastas.parquet, pastas.reports, premissas)
    console.print(
        f"melhor: uplift para {r.melhor_fracao:.0%} da base, lucro {r.melhor_lucro:,.0f} "
        f"contra {r.lucro_mandando_para_todos:,.0f} mandando para todos"
    )


@app.command(help="Roda o placar em SQL nos 14 mi de linhas da Criteo, com tempo e memória.")
def escala() -> None:
    from persuadables import escala as prova_de_escala

    if not (pastas.parquet / "criteo.parquet").exists():
        console.print("sem criteo.parquet: prova de escala pulada")
        return
    r = prova_de_escala.rodar(run_sql.conectar(pastas.parquet), pastas.reports, pastas.parquet)
    console.print(f"{r.linhas:,} linhas: {r.segundos:.1f} s, pico {r.pico_memoria_mb:,.0f} MB")


@app.command(help="Roda o pipeline inteiro, dos dados à prova de escala.")
def tudo() -> None:
    passos = [
        ("dados", amostra if pastas.na_amostra else lambda: baixar(base=None, forcar=False)),
        ("auditoria", auditar),
        ("perfil", perfil),
        ("placar", placar),
        ("uplift", uplift),
        ("decisão", lambda: decisao(custo=3.0, margem=0.20)),
        ("escala", escala),
    ]
    for nome, passo in passos:
        console.rule(nome)
        passo()


def _desde(inicio: float) -> float:
    return time.perf_counter() - inicio


if __name__ == "__main__":
    app()
