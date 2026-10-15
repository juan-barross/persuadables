from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from persuadables import graficos, relatorio

FRACOES = np.round(np.linspace(0.05, 1.0, 20), 2)
FRACOES_NA_TABELA = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
CORES = {
    "aleatório": graficos.TEXTO_SECUNDARIO,
    "propensão": graficos.AZUL,
    "uplift": graficos.LARANJA,
}
CUSTOS_TESTADOS = (1.0, 3.0, 6.0, 10.0)
MARGENS_TESTADAS = (0.15, 0.20, 0.30)


@dataclass(frozen=True)
class Premissas:
    custo_por_contato: float = 3.0
    margem: float = 0.20
    compras_por_comprador: float = 1.0
    ticket: float | None = None

    def valor_por_comprador(self, ticket_da_base: float) -> float:
        return (self.ticket or ticket_da_base) * self.margem * self.compras_por_comprador


@dataclass(frozen=True)
class ResultadoDecisao:
    melhor_fracao: float
    melhor_lucro: float
    lucro_mandando_para_todos: float


def rodar(dados: Path, reports: Path, premissas: Premissas | None = None) -> ResultadoDecisao:
    premissas = premissas or Premissas()
    teste = pd.read_parquet(dados / "scores_teste.parquet")
    ticket_medio = pd.read_parquet(dados / "perfil_cliente.parquet", columns=["ticket_medio"])
    modelo_uplift = (reports / "40_uplift" / "modelo_escolhido.txt").read_text().strip()
    n_base = len(ticket_medio)
    ticket_da_base = float(ticket_medio["ticket_medio"].mean())
    valor = premissas.valor_por_comprador(ticket_da_base)

    scores = {
        "aleatório": np.random.default_rng(7).random(len(teste)),
        "propensão": teste["propensão"].to_numpy(),
        "uplift": teste[modelo_uplift].to_numpy(),
    }
    curvas = com_aleatorio_esperado(curvas_com_ic(teste, scores, n_base))
    por_orcamento = financeiro(curvas, n_base, valor, premissas.custo_por_contato)

    contexto = asdict(premissas) | {
        "ticket_base": ticket_da_base,
        "valor_por_comprador": valor,
        "n_base": n_base,
        "modelo_uplift": modelo_uplift,
    }
    destino = reports / "50_decisao"
    relatorio.salvar_csv(curvas, destino / "curvas.csv")
    relatorio.salvar_csv(por_orcamento, destino / "financeiro.csv")
    (destino / "premissas.json").write_text(
        json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    grafico(curvas, n_base, reports / "figuras" / "orcamento_vs_incrementais.png")
    (reports / "decisao.md").write_text(
        texto_do_relatorio(por_orcamento, contexto), encoding="utf-8"
    )

    uplift = por_orcamento[por_orcamento["estrategia"] == "uplift"]
    melhor = uplift.loc[uplift["lucro"].idxmax()]
    return ResultadoDecisao(
        melhor_fracao=float(melhor["fracao"]),
        melhor_lucro=float(melhor["lucro"]),
        lucro_mandando_para_todos=float(uplift.iloc[-1]["lucro"]),
    )


def incrementais_por_fracao(
    comprou: np.ndarray, tratado: np.ndarray, pesos: np.ndarray, n_base: int
) -> np.ndarray:
    clientes_ate_aqui = np.cumsum(pesos)
    tratados_ate_aqui = np.cumsum(pesos * tratado)
    compras_ate_aqui = np.cumsum(pesos * comprou)
    compras_tratados_ate_aqui = np.cumsum(pesos * comprou * tratado)

    contatados = np.maximum((FRACOES * clientes_ate_aqui[-1]).astype(int), 1)
    ultimo = np.searchsorted(clientes_ate_aqui, contatados)
    sobra_do_ultimo = clientes_ate_aqui[ultimo] - contatados

    tratados = tratados_ate_aqui[ultimo] - sobra_do_ultimo * tratado[ultimo]
    compras = compras_ate_aqui[ultimo] - sobra_do_ultimo * comprou[ultimo]
    compras_t = (
        compras_tratados_ate_aqui[ultimo] - sobra_do_ultimo * comprou[ultimo] * tratado[ultimo]
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        efeito = compras_t / tratados - (compras - compras_t) / (contatados - tratados)
    return efeito * FRACOES * n_base


def curvas_com_ic(
    teste: pd.DataFrame,
    scores: dict[str, np.ndarray],
    n_base: int,
    reps: int = 500,
    semente: int = 42,
) -> pd.DataFrame:
    comprou = teste["target"].to_numpy(float)
    tratado = teste["treatment_flg"].to_numpy(float)
    ordens = {nome: np.argsort(-score, kind="stable") for nome, score in scores.items()}
    ordenados = {nome: (comprou[ordem], tratado[ordem]) for nome, ordem in ordens.items()}

    bootstrap = {nome: np.empty((reps, len(FRACOES))) for nome in scores}
    for rep, pesos in enumerate(_pesos_do_bootstrap(tratado.astype(bool), reps, semente)):
        for nome, ordem in ordens.items():
            bootstrap[nome][rep] = incrementais_por_fracao(*ordenados[nome], pesos[ordem], n_base)

    linhas = []
    for nome, (y, t) in ordenados.items():
        inf, sup = np.nanquantile(bootstrap[nome], [0.025, 0.975], axis=0)
        pontual = incrementais_por_fracao(y, t, np.ones(len(y)), n_base)
        linhas.append(
            pd.DataFrame(
                {
                    "estrategia": nome,
                    "fracao": FRACOES,
                    "incrementais": pontual,
                    "inf": inf,
                    "sup": sup,
                }
            )
        )
    return pd.concat(linhas, ignore_index=True)


def _pesos_do_bootstrap(tratado: np.ndarray, reps: int, semente: int) -> Iterator[np.ndarray]:
    rng = np.random.default_rng(semente)
    indices_t, indices_c = np.flatnonzero(tratado), np.flatnonzero(~tratado)
    for _ in range(reps):
        sorteados = np.r_[
            rng.choice(indices_t, len(indices_t)), rng.choice(indices_c, len(indices_c))
        ]
        yield np.bincount(sorteados, minlength=len(tratado)).astype(float)


def com_aleatorio_esperado(curvas: pd.DataFrame) -> pd.DataFrame:
    curvas = curvas.copy()
    aleatorio = curvas["estrategia"] == "aleatório"
    mandando_para_todos = curvas.loc[aleatorio & (curvas["fracao"] == 1.0)].iloc[0]
    for coluna in ("incrementais", "inf", "sup"):
        curvas.loc[aleatorio, coluna] = (
            curvas.loc[aleatorio, "fracao"] * mandando_para_todos[coluna]
        )
    return curvas


def financeiro(curvas: pd.DataFrame, n_base: int, valor: float, custo: float) -> pd.DataFrame:
    contatos = curvas["fracao"] * n_base
    gasto = contatos * custo
    receita = curvas["incrementais"] * valor
    return curvas.assign(
        contatos=contatos,
        custo=gasto,
        receita_incremental=receita,
        lucro=receita - gasto,
        lucro_inf=curvas["inf"] * valor - gasto,
        lucro_sup=curvas["sup"] * valor - gasto,
        retorno_por_rublo=receita / gasto,
    )


def sensibilidade(curvas: pd.DataFrame, contexto: dict) -> pd.DataFrame:
    linhas = []
    for custo in CUSTOS_TESTADOS:
        for margem in MARGENS_TESTADAS:
            valor = Premissas(custo, margem).valor_por_comprador(contexto["ticket_base"])
            por_orcamento = financeiro(curvas, contexto["n_base"], valor, custo)
            uplift = por_orcamento[por_orcamento["estrategia"] == "uplift"]
            melhor = uplift.loc[uplift["lucro"].idxmax()]
            linhas.append(
                {
                    "custo_por_contato": custo,
                    "margem": margem,
                    "melhor_fracao": melhor["fracao"],
                    "lucro_melhor": melhor["lucro"],
                    "lucro_mandar_para_todos": uplift.iloc[-1]["lucro"],
                }
            )
    return pd.DataFrame(linhas)


def texto_do_relatorio(por_orcamento: pd.DataFrame, contexto: dict) -> str:
    def ponto(estrategia: str, fracao: float) -> pd.Series:
        escolhido = (por_orcamento["estrategia"] == estrategia) & (
            por_orcamento["fracao"] == fracao
        )
        return por_orcamento[escolhido].iloc[0]

    uplift = por_orcamento[por_orcamento["estrategia"] == "uplift"]
    todos = ponto("uplift", 1.0)
    metade = uplift[uplift["incrementais"] >= todos["incrementais"] / 2]
    colunas = ["estrategia", "fracao", "incrementais", "inf", "sup", "custo", "lucro"]
    na_tabela = por_orcamento[por_orcamento["fracao"].isin(FRACOES_NA_TABELA)]
    curvas = por_orcamento[["estrategia", "fracao", "incrementais", "inf", "sup"]]
    return relatorio.preencher(
        "decisao",
        **contexto,
        todos=todos,
        melhor=uplift.loc[uplift["lucro"].idxmax()],
        fracao_metade=float(metade["fracao"].min()),
        com_30_uplift=ponto("uplift", 0.3),
        com_30_propensao=ponto("propensão", 0.3),
        com_30_aleatorio=ponto("aleatório", 0.3),
        tabela_orcamento=relatorio.tabela(
            na_tabela[colunas].sort_values(["fracao", "estrategia"]), casas=2
        ),
        tabela_sensibilidade=relatorio.tabela(sensibilidade(curvas, contexto), casas=2),
    )


def grafico(curvas: pd.DataFrame, n_base: int, destino: Path) -> None:
    fig = graficos.nova_figura(8, 5)
    ax = fig.subplots()
    graficos.estilizar(ax)
    for nome, cor in CORES.items():
        estrategia = curvas[curvas["estrategia"] == nome]
        x = estrategia["fracao"] * 100
        if nome == "aleatório":
            ax.plot(x, estrategia["incrementais"], color=cor, lw=2, ls=graficos.TRACEJADO)
        else:
            ax.fill_between(x, estrategia["inf"], estrategia["sup"], color=cor, alpha=0.14, lw=0)
            ax.plot(x, estrategia["incrementais"], color=cor, lw=2)
        rotulo = len(estrategia) // 4
        ax.annotate(
            nome,
            (x.iloc[rotulo], estrategia["incrementais"].iloc[rotulo]),
            xytext=(4, 6),
            textcoords="offset points",
            color=graficos.TEXTO,
            fontsize=9,
        )
    graficos.rotular_eixos(
        ax,
        "% da base que recebe a campanha (orçamento)",
        f"compradores incrementais (base de {n_base:,})".replace(",", "."),
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    graficos.titular(
        fig,
        "Com o mesmo orçamento, mandar por uplift traz mais compradores",
        "Faixas: IC 95% por bootstrap no conjunto de teste. Tracejado: envio aleatório. "
        "100% = mandar para todos.",
        espaco_topo=0.89,
    )
    graficos.salvar(fig, destino)
