from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import typer
from rich.console import Console

from persuadables import agente, ingest, relatorio, run_sql
from persuadables import amostra as amostra_sintetica
from persuadables import decisao as decisao_de_orcamento
from persuadables import escala as prova_de_escala
from persuadables import placar as placar_do_experimento
from persuadables import uplift as modelos_de_uplift

AMOSTRA = Path("data/amostra")

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
pastas = {"parquet": ingest.PARQUET, "reports": Path("reports")}


@app.callback()
def principal(amostra: bool = typer.Option(False, help="Usa a amostra sintética.")) -> None:
    if amostra:
        pastas.update(parquet=AMOSTRA / "parquet", reports=AMOSTRA / "reports")
    pastas["reports"].mkdir(parents=True, exist_ok=True)


@app.command(help="Baixa os CSVs da X5 e da Criteo e converte para Parquet.")
def baixar(base: str = typer.Option(None, help="x5 ou criteo; vazio baixa as duas.")) -> None:
    for fonte in ingest.fontes(base):
        ingest.baixar(fonte)
        ingest.converter(fonte)
        console.print(f"{fonte.tabela:<14} {fonte.parquet.stat().st_size / 2**20:8.0f} MB")


@app.command(help="Gera a amostra sintética, sem rede.")
def amostra() -> None:
    console.print(f"amostra em {amostra_sintetica.gerar(AMOSTRA / 'parquet').as_posix()}")


@app.command(help="Audita as tabelas da X5 e grava reports/auditoria.md.")
def auditar() -> None:
    resultados = run_sql.rodar_pasta(conexao(), "00_auditoria", pastas["reports"])
    introducao = (
        f"Gerado por `persuadables auditar` sobre `{pastas['parquet'].as_posix()}`. "
        f"Data de corte: {run_sql.DATA_DE_CORTE}."
    )
    texto = relatorio.de_consultas("Auditoria dos dados da X5", resultados, introducao)
    (pastas["reports"] / "auditoria.md").write_text(texto, encoding="utf-8")
    for r in resultados:
        console.print(f"{r.nome:<20} {r.segundos:6.1f} s")


@app.command(help="Monta o perfil do cliente em SQL e grava perfil_cliente.parquet.")
def perfil() -> None:
    df = run_sql.construir_perfil(conexao(), pastas["reports"])
    df.to_parquet(pastas["parquet"] / "perfil_cliente.parquet", index=False)
    console.print(f"perfil_cliente: {len(df):,} clientes, {len(df.columns) - 3} variáveis")


@app.command(help="Lê o experimento: sorteio, efeito, CUPED, poder e segmentos.")
def placar() -> None:
    r = placar_do_experimento.rodar(conexao(), pastas["reports"])
    console.print(
        f"efeito {r['efeito_pp']:+.2f} p.p. [{r['ic_inf_pp']:.2f}; {r['ic_sup_pp']:.2f}], "
        f"SRM p = {r['p_srm']:.3f}, CUPED reduz a variância em {r['cuped_reducao_variancia']:.1%}"
    )


@app.command(help="Treina propensão e modelos de uplift e compara por Qini e AUUC.")
def uplift() -> None:
    perfil_cliente = pd.read_parquet(pastas["parquet"] / "perfil_cliente.parquet")
    r = modelos_de_uplift.rodar(perfil_cliente, pastas["reports"], pastas["parquet"])
    for nome, linha in r.metricas_no_teste.iterrows():
        console.print(f"{nome:<22} AUUC {linha.auuc:.4f}  top30 {linha.uplift_top30_pp:+.2f} p.p.")
    console.print(f"escolhido: {r.escolhido}")


@app.command(help="Compara orçamentos por estratégia e grava reports/decisao.md.")
def decisao(
    custo: float = typer.Option(3.0, help="Custo por contato, em rublos."),
    margem: float = typer.Option(0.20, help="Margem bruta sobre o ticket."),
) -> None:
    premissas = decisao_de_orcamento.Premissas(custo_por_contato=custo, margem=margem)
    r = decisao_de_orcamento.rodar(pastas["parquet"], pastas["reports"], premissas)
    console.print(
        f"melhor: uplift para {r.melhor_fracao:.0%} da base, lucro {r.melhor_lucro:,.0f} "
        f"contra {r.lucro_mandando_para_todos:,.0f} mandando para todos"
    )


@app.command(help="Roda o placar em SQL nos 14 mi de linhas da Criteo, com tempo e memória.")
def escala() -> None:
    if not (pastas["parquet"] / "criteo.parquet").exists():
        console.print("sem criteo.parquet: prova de escala pulada")
        return
    r = prova_de_escala.rodar(conexao(), pastas["reports"], pastas["parquet"])
    console.print(f"{r.linhas:,} linhas: {r.segundos:.1f} s, pico {r.pico_memoria_mb:,.0f} MB")


@app.command(help="Responde uma pergunta do CRM com o agente (precisa de chave de API).")
def perguntar(pergunta: str) -> None:
    resposta = agente.perguntar(pergunta)
    console.print(resposta.texto)
    console.print(f"[dim]{resposta.tokens_entrada + resposta.tokens_saida:,} tokens[/dim]")


@app.command(name="avaliar-agente", help="Mede o agente contra respostas conhecidas.")
def avaliar_agente() -> None:
    avaliacao = agente.avaliar()
    console.print(f"{avaliacao['acertou'].sum()} de {len(avaliacao)} acertos (reports/agente.md)")


@app.command(help="Roda o pipeline inteiro, dos dados à prova de escala.")
def tudo() -> None:
    na_amostra = pastas["parquet"] != ingest.PARQUET
    passos = {
        "dados": amostra if na_amostra else lambda: baixar(base=None),
        "auditoria": auditar,
        "perfil": perfil,
        "placar": placar,
        "uplift": uplift,
        "decisão": lambda: decisao(custo=3.0, margem=0.20),
        "escala": escala,
    }
    for nome, passo in passos.items():
        console.rule(nome)
        passo()


def conexao() -> duckdb.DuckDBPyConnection:
    return run_sql.conectar(pastas["parquet"])


if __name__ == "__main__":
    app()
