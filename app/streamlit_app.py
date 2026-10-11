"""Simulador de orçamento da campanha.

Lê só as curvas pré-calculadas em reports/50_decisao/ (versionadas no git), então roda sem
os dados da X5. Toda a conta de dinheiro é linear sobre os compradores incrementais:
lucro = incrementais × ticket × margem × compras - contatos × custo.

    uv run --extra app streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PASTA = Path(__file__).resolve().parents[1] / "reports" / "50_decisao"
CORES = {"uplift": "#eb6834", "propensão": "#2a78d6", "aleatório": "#52514e"}

st.set_page_config(page_title="Quem deve receber a campanha?", layout="wide")


@st.cache_data
def carregar() -> tuple[pd.DataFrame, dict]:
    curvas = pd.read_csv(PASTA / "curvas.csv")
    premissas = json.loads((PASTA / "premissas.json").read_text(encoding="utf-8"))
    return curvas, premissas


def br(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


curvas, base = carregar()
n_base = int(base["n_base"])

st.title("Quem deve receber a campanha?")
st.caption(
    "X5 RetailHero: experimento randomizado com 200 mil clientes. As curvas vêm do conjunto "
    "de teste dos modelos; valores em rublos. Código e método no README do repositório."
)

with st.sidebar:
    st.header("Premissas")
    custo = st.slider("Custo por contato (₽)", 0.0, 15.0, float(base["custo_por_contato"]), 0.5)
    ticket = st.slider("Ticket de uma compra (₽)", 100, 1500, int(round(base["ticket_base"])), 10)
    margem = st.slider("Margem bruta", 0.05, 0.50, float(base["margem"]), 0.01, format="%.2f")
    compras = st.slider("Compras por comprador incremental", 1.0, 4.0, 1.0, 0.5)
    st.header("Orçamento")
    fracao = st.select_slider(
        "% da base que recebe",
        options=sorted(curvas["fracao"].unique()),
        value=0.3,
        format_func=lambda f: f"{f:.0%}",
    )

valor = ticket * margem * compras
d = curvas.copy()
d["contatos"] = d["fracao"] * n_base
d["custo"] = d["contatos"] * custo
d["lucro"] = d["incrementais"] * valor - d["custo"]
d["lucro_inf"] = d["inf"] * valor - d["custo"]
d["lucro_sup"] = d["sup"] * valor - d["custo"]

escolha = d[d.fracao == fracao].set_index("estrategia")
up = d[d.estrategia == "uplift"]
todos = up[up.fracao == 1.0].iloc[0]
melhor = up.loc[up.lucro.idxmax()]

c1, c2, c3, c4 = st.columns(4)
dif = escolha.loc["uplift", "incrementais"] - escolha.loc["propensão", "incrementais"]
c1.metric(
    f"Compradores a mais, uplift em {fracao:.0%}",
    br(escolha.loc["uplift", "incrementais"]),
    f"{'+' if dif >= 0 else '-'}{br(abs(dif))} vs propensão",
)
c2.metric(
    f"Lucro, uplift em {fracao:.0%}",
    f"₽ {br(escolha.loc['uplift', 'lucro'])}",
    f"IC [{br(escolha.loc['uplift', 'lucro_inf'])}; {br(escolha.loc['uplift', 'lucro_sup'])}]",
    delta_color="off",
)
c3.metric("Lucro, mandar para todos", f"₽ {br(todos['lucro'])}")
c4.metric(
    "Melhor fração por uplift",
    f"{melhor['fracao']:.0%}",
    f"₽ {br(melhor['lucro'])}",
    delta_color="off",
)

st.subheader("Lucro incremental por orçamento")
escala = alt.Scale(domain=list(CORES), range=list(CORES.values()))
eixo_x = alt.X("fracao:Q", title="% da base que recebe", axis=alt.Axis(format="%"))
faixa = (
    alt.Chart(d[d.estrategia != "aleatório"])
    .mark_area(opacity=0.15)
    .encode(
        eixo_x, alt.Y("lucro_inf:Q"), alt.Y2("lucro_sup:Q"), alt.Color("estrategia:N", scale=escala)
    )
)
linhas = (
    alt.Chart(d)
    .mark_line(strokeWidth=2)
    .encode(
        eixo_x,
        alt.Y("lucro:Q", title="lucro incremental (₽)"),
        alt.Color("estrategia:N", scale=escala, title="estratégia"),
        tooltip=[
            alt.Tooltip("estrategia:N", title="estratégia"),
            alt.Tooltip("fracao:Q", title="% da base", format=".0%"),
            alt.Tooltip("incrementais:Q", title="compradores a mais", format=",.0f"),
            alt.Tooltip("lucro:Q", title="lucro (₽)", format=",.0f"),
        ],
    )
)
zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#52514e").encode(y="y:Q")
marca = alt.Chart(pd.DataFrame({"x": [fracao]})).mark_rule(strokeDash=[4, 3]).encode(x="x:Q")
st.altair_chart((faixa + linhas + zero + marca).properties(height=380), use_container_width=True)

st.subheader(f"Detalhe em {fracao:.0%} da base")
tabela = escolha[["contatos", "incrementais", "inf", "sup", "custo", "lucro"]].rename(
    columns={
        "incrementais": "compradores a mais",
        "inf": "IC inf.",
        "sup": "IC sup.",
        "custo": "custo (₽)",
        "lucro": "lucro (₽)",
    }
)
st.dataframe(tabela.style.format(br), use_container_width=True)

st.caption(
    f"Valor de um comprador incremental com estas premissas: ₽ {valor:,.1f}. "
    "O aleatório é a reta do efeito médio do experimento. Faixas: IC 95% por bootstrap."
)
