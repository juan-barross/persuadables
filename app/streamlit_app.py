from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from persuadables.decisao import CORES, financeiro

DECISAO = Path(__file__).resolve().parents[1] / "reports" / "50_decisao"
COLUNAS_DO_DETALHE = {
    "contatos": "contatos",
    "incrementais": "compradores a mais",
    "inf": "IC inf.",
    "sup": "IC sup.",
    "custo": "custo (₽)",
    "lucro": "lucro (₽)",
}


@dataclass(frozen=True)
class Escolhas:
    custo: float
    ticket: float
    margem: float
    compras: float
    fracao: float

    @property
    def valor_por_comprador(self) -> float:
        return self.ticket * self.margem * self.compras


@st.cache_data
def carregar() -> tuple[pd.DataFrame, dict]:
    curvas = pd.read_csv(DECISAO / "curvas.csv")
    premissas = json.loads((DECISAO / "premissas.json").read_text(encoding="utf-8"))
    return curvas, premissas


def com_milhar(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def barra_lateral(curvas: pd.DataFrame, premissas: dict) -> Escolhas:
    with st.sidebar:
        st.header("Premissas")
        custo = st.slider(
            "Custo por contato (₽)", 0.0, 15.0, float(premissas["custo_por_contato"]), 0.5
        )
        ticket = st.slider(
            "Ticket de uma compra (₽)", 100, 1500, round(premissas["ticket_base"]), 10
        )
        margem = st.slider(
            "Margem bruta", 0.05, 0.50, float(premissas["margem"]), 0.01, format="%.2f"
        )
        compras = st.slider("Compras por comprador incremental", 1.0, 4.0, 1.0, 0.5)
        st.header("Orçamento")
        fracao = st.select_slider(
            "% da base que recebe",
            options=sorted(curvas["fracao"].unique()),
            value=0.3,
            format_func=lambda f: f"{f:.0%}",
        )
    return Escolhas(custo, ticket, margem, compras, fracao)


def indicadores(por_orcamento: pd.DataFrame, fracao: float) -> None:
    no_orcamento = por_orcamento[por_orcamento["fracao"] == fracao].set_index("estrategia")
    uplift = por_orcamento[por_orcamento["estrategia"] == "uplift"]
    mandando_para_todos = uplift[uplift["fracao"] == 1.0].iloc[0]
    melhor = uplift.loc[uplift["lucro"].idxmax()]
    escolhido = no_orcamento.loc["uplift"]
    vantagem = escolhido["incrementais"] - no_orcamento.loc["propensão", "incrementais"]

    compradores, lucro, todos, melhor_fracao = st.columns(4)
    compradores.metric(
        f"Compradores a mais, uplift em {fracao:.0%}",
        com_milhar(escolhido["incrementais"]),
        f"{'+' if vantagem >= 0 else '-'}{com_milhar(abs(vantagem))} vs propensão",
    )
    lucro.metric(
        f"Lucro, uplift em {fracao:.0%}",
        f"₽ {com_milhar(escolhido['lucro'])}",
        f"IC [{com_milhar(escolhido['lucro_inf'])}; {com_milhar(escolhido['lucro_sup'])}]",
        delta_color="off",
    )
    todos.metric("Lucro, mandar para todos", f"₽ {com_milhar(mandando_para_todos['lucro'])}")
    melhor_fracao.metric(
        "Melhor fração por uplift",
        f"{melhor['fracao']:.0%}",
        f"₽ {com_milhar(melhor['lucro'])}",
        delta_color="off",
    )


def grafico_de_lucro(por_orcamento: pd.DataFrame, fracao: float) -> alt.LayerChart:
    cores = alt.Scale(domain=list(CORES), range=list(CORES.values()))
    eixo_x = alt.X("fracao:Q", title="% da base que recebe", axis=alt.Axis(format="%"))
    faixas = (
        alt.Chart(por_orcamento[por_orcamento["estrategia"] != "aleatório"])
        .mark_area(opacity=0.15)
        .encode(
            eixo_x,
            alt.Y("lucro_inf:Q"),
            alt.Y2("lucro_sup:Q"),
            alt.Color("estrategia:N", scale=cores),
        )
    )
    linhas = (
        alt.Chart(por_orcamento)
        .mark_line(strokeWidth=2)
        .encode(
            eixo_x,
            alt.Y("lucro:Q", title="lucro incremental (₽)"),
            alt.Color("estrategia:N", scale=cores, title="estratégia"),
            tooltip=[
                alt.Tooltip("estrategia:N", title="estratégia"),
                alt.Tooltip("fracao:Q", title="% da base", format=".0%"),
                alt.Tooltip("incrementais:Q", title="compradores a mais", format=",.0f"),
                alt.Tooltip("lucro:Q", title="lucro (₽)", format=",.0f"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=CORES["aleatório"]).encode(y="y:Q")
    orcamento = (
        alt.Chart(pd.DataFrame({"x": [fracao]})).mark_rule(strokeDash=[4, 3]).encode(x="x:Q")
    )
    return (faixas + linhas + zero + orcamento).properties(height=380)


def main() -> None:
    st.set_page_config(page_title="Quem deve receber a campanha?", layout="wide")
    curvas, premissas = carregar()
    st.title("Quem deve receber a campanha?")
    st.caption(
        "X5 RetailHero: experimento randomizado com 200 mil clientes. As curvas vêm do conjunto "
        "de teste dos modelos; valores em rublos. Código e método no README do repositório."
    )

    escolhas = barra_lateral(curvas, premissas)
    por_orcamento = financeiro(
        curvas, int(premissas["n_base"]), escolhas.valor_por_comprador, escolhas.custo
    )
    indicadores(por_orcamento, escolhas.fracao)

    st.subheader("Lucro incremental por orçamento")
    st.altair_chart(grafico_de_lucro(por_orcamento, escolhas.fracao), use_container_width=True)

    st.subheader(f"Detalhe em {escolhas.fracao:.0%} da base")
    no_orcamento = por_orcamento[por_orcamento["fracao"] == escolhas.fracao]
    detalhe = no_orcamento.set_index("estrategia")[list(COLUNAS_DO_DETALHE)]
    st.dataframe(
        detalhe.rename(columns=COLUNAS_DO_DETALHE).style.format(com_milhar),
        use_container_width=True,
    )
    st.caption(
        "Valor de um comprador incremental com estas premissas: "
        f"₽ {escolhas.valor_por_comprador:,.1f}. "
        "O aleatório é a reta do efeito médio do experimento. Faixas: IC 95% por bootstrap."
    )


main()
