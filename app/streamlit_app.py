from __future__ import annotations

import json
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


def com_milhar(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def grafico_de_lucro(por_orcamento: pd.DataFrame, fracao: float) -> alt.LayerChart:
    base = alt.Chart(por_orcamento).encode(
        alt.X("fracao:Q", title="% da base que recebe", axis=alt.Axis(format="%")),
        alt.Color(
            "estrategia:N",
            title="estratégia",
            scale=alt.Scale(domain=list(CORES), range=list(CORES.values())),
        ),
    )
    faixas = (
        base.mark_area(opacity=0.15)
        .encode(alt.Y("lucro_inf:Q"), alt.Y2("lucro_sup:Q"))
        .transform_filter("datum.estrategia != 'aleatório'")
    )
    linhas = base.mark_line(strokeWidth=2).encode(
        alt.Y("lucro:Q", title="lucro incremental (₽)"),
        tooltip=[
            "estrategia",
            alt.Tooltip("fracao", format=".0%"),
            alt.Tooltip("lucro", format=",.0f"),
        ],
    )
    orcamento = alt.Chart(pd.DataFrame({"x": [fracao]})).mark_rule(strokeDash=[4, 3]).encode(x="x")
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=CORES["aleatório"]).encode(y="y")
    return (faixas + linhas + zero + orcamento).properties(height=380)


def main() -> None:
    st.set_page_config(page_title="Quem deve receber a campanha?", layout="wide")
    curvas = pd.read_csv(DECISAO / "curvas.csv")
    premissas = json.loads((DECISAO / "premissas.json").read_text(encoding="utf-8"))
    st.title("Quem deve receber a campanha?")
    st.caption(
        "X5 RetailHero: experimento randomizado com 200 mil clientes. As curvas vêm do conjunto "
        "de teste dos modelos; valores em rublos. Código e método no README do repositório."
    )

    with st.sidebar:
        st.header("Premissas")
        custo = st.slider("Custo por contato (₽)", 0.0, 15.0, premissas["custo_por_contato"], 0.5)
        ticket = st.slider(
            "Ticket de uma compra (₽)", 100, 1500, round(premissas["ticket_base"]), 10
        )
        margem = st.slider("Margem bruta", 0.05, 0.50, premissas["margem"], 0.01)
        compras = st.slider("Compras por comprador incremental", 1.0, 4.0, 1.0, 0.5)
        st.header("Orçamento")
        fracao = st.select_slider(
            "% da base que recebe",
            options=sorted(curvas["fracao"].unique()),
            value=0.3,
            format_func=lambda f: f"{f:.0%}",
        )

    valor = ticket * margem * compras
    por_orcamento = financeiro(curvas, premissas["n_base"], valor, custo)
    no_orcamento = por_orcamento[por_orcamento["fracao"] == fracao].set_index("estrategia")
    uplift = por_orcamento[por_orcamento["estrategia"] == "uplift"]
    melhor, escolhido = uplift.loc[uplift["lucro"].idxmax()], no_orcamento.loc["uplift"]
    vantagem = escolhido["incrementais"] - no_orcamento.loc["propensão", "incrementais"]

    indicadores = [
        (
            f"Compradores a mais, uplift em {fracao:.0%}",
            com_milhar(escolhido["incrementais"]),
            f"{vantagem:+,.0f} vs propensão".replace(",", "."),
        ),
        (
            f"Lucro, uplift em {fracao:.0%}",
            f"₽ {com_milhar(escolhido['lucro'])}",
            f"IC [{com_milhar(escolhido['lucro_inf'])}; {com_milhar(escolhido['lucro_sup'])}]",
        ),
        ("Lucro, mandar para todos", f"₽ {com_milhar(uplift.iloc[-1]['lucro'])}", None),
        ("Melhor fração por uplift", f"{melhor['fracao']:.0%}", f"₽ {com_milhar(melhor['lucro'])}"),
    ]
    for coluna, (rotulo, valor_exibido, detalhe) in zip(st.columns(4), indicadores, strict=True):
        coluna.metric(rotulo, valor_exibido, detalhe, delta_color="off")

    st.subheader("Lucro incremental por orçamento")
    st.altair_chart(grafico_de_lucro(por_orcamento, fracao), use_container_width=True)
    st.subheader(f"Detalhe em {fracao:.0%} da base")
    detalhe = no_orcamento[list(COLUNAS_DO_DETALHE)].rename(columns=COLUNAS_DO_DETALHE)
    st.dataframe(detalhe.style.format(com_milhar), use_container_width=True)
    st.caption(
        f"Valor de um comprador incremental com estas premissas: ₽ {valor:,.1f}. "
        "O aleatório é a reta do efeito médio do experimento. Faixas: IC 95% por bootstrap."
    )


main()
