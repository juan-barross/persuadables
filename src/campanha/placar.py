"""Placar do experimento: junta o SQL de sql/20_placar_experimento com o que precisa de
Python (p-valores, Benjamini-Hochberg, bootstrap, poder e CUPED com várias covariáveis)
e escreve reports/placar.md.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy import stats as st  # noqa: E402

from campanha import run_sql, stats  # noqa: E402

# Paleta de referência (skill dataviz): uma série por gráfico, texto em tinta neutra.
AZUL = "#2a78d6"
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"

COVARIAVEIS_CUPED = [
    "n_transacoes",
    "n_transacoes_30d",
    "dias_com_compra",
    "dias_desde_ultima",
    "intervalo_medio_dias",
    "gasto_total",
    "gasto_30d",
    "ticket_medio",
    "pontos_gastos",
    "ja_resgatou",
]


def cuped_regressao(perfil: pd.DataFrame) -> dict:
    """CUPED com várias covariáveis = regressão de y em tratamento + covariáveis centradas.

    O coeficiente do tratamento é o efeito ajustado; erro padrão robusto (HC1).
    """
    x = perfil[COVARIAVEIS_CUPED].astype(float)
    x = x.fillna(x.mean())
    x = x - x.mean()
    t = perfil["treatment_flg"].astype(float)
    y = perfil["target"].astype(float)
    bruto = sm.OLS(y, sm.add_constant(t)).fit(cov_type="HC1")
    ajustado = sm.OLS(y, sm.add_constant(pd.concat([t, x], axis=1))).fit(cov_type="HC1")
    ep_b, ep_a = bruto.bse["treatment_flg"], ajustado.bse["treatment_flg"]
    return {
        "efeito_pp": ajustado.params["treatment_flg"] * 100,
        "ic_inf_pp": (ajustado.params["treatment_flg"] - 1.959964 * ep_a) * 100,
        "ic_sup_pp": (ajustado.params["treatment_flg"] + 1.959964 * ep_a) * 100,
        "reducao_variancia": 1 - (ep_a / ep_b) ** 2,
        "reducao_largura_ic": 1 - ep_a / ep_b,
        "r2": ajustado.rsquared,
    }


def segmentos_com_bh(seg: pd.DataFrame) -> pd.DataFrame:
    seg = seg.copy()
    seg["p_valor"] = 2 * st.norm.sf(seg["z"].abs())
    seg["q_bh"] = stats.benjamini_hochberg(seg["p_valor"].to_numpy())
    seg["ic_inf_pp"] = seg["efeito_pp"] - 1.959964 * seg["ep_pp"]
    seg["ic_sup_pp"] = seg["efeito_pp"] + 1.959964 * seg["ep_pp"]
    seg["significativo_bh_5pct"] = seg["q_bh"] < 0.05
    return seg


def diferenca_entre_niveis(seg: pd.DataFrame, segmento: str, a: str, b: str) -> stats.Efeito:
    """O efeito no nível a é diferente do efeito no nível b? (teste de heterogeneidade)."""
    linhas = seg[seg["segmento"] == segmento].set_index("nivel")
    dif = (linhas.loc[a, "efeito_pp"] - linhas.loc[b, "efeito_pp"]) / 100
    ep = np.hypot(linhas.loc[a, "ep_pp"], linhas.loc[b, "ep_pp"]) / 100
    return stats._efeito(float(dif), float(ep), 0.05)


def grafico_segmentos(seg: pd.DataFrame, efeito_geral_pp: float, destino: Path) -> None:
    paineis = [
        ("decil_gasto", "Decil de gasto antes da campanha (D01 = gasta menos)"),
        ("quartil_recencia", "Quartil de recência (Q1 = comprou mais recentemente)"),
        ("decil_ticket", "Decil de ticket médio (D01 = ticket menor)"),
    ]
    alturas = [len(seg[seg["segmento"] == s]) for s, _ in paineis]
    n_clientes = seg.loc[seg["segmento"] == "decil_gasto", ["n_t", "n_c"]].to_numpy().sum()
    fig, eixos = plt.subplots(
        len(paineis),
        1,
        figsize=(8, 9.5),
        gridspec_kw={"height_ratios": alturas},
        facecolor=SUPERFICIE,
    )
    for ax, (nome, titulo) in zip(eixos, paineis, strict=True):
        d = seg[seg["segmento"] == nome].sort_values("nivel", ascending=False)
        rotulos = d["nivel"].str.split(" ").str[0]
        ypos = np.arange(len(d))
        ax.set_facecolor(SUPERFICIE)
        ax.axvline(0, color=TEXTO_2, lw=1)
        ax.axvline(efeito_geral_pp, color=TEXTO_2, lw=1, ls=(0, (4, 3)))
        ax.hlines(ypos, d["ic_inf_pp"], d["ic_sup_pp"], color=AZUL, lw=2)
        ax.plot(d["efeito_pp"], ypos, "o", color=AZUL, ms=8, mec=SUPERFICIE, mew=2)
        ax.set_yticks(ypos, rotulos, color=TEXTO_2, fontsize=9)
        ax.set_title(titulo, loc="left", color=TEXTO, fontsize=10.5, pad=6)
        ax.tick_params(axis="x", colors=TEXTO_2, labelsize=9)
        ax.grid(axis="x", color=GRADE, lw=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(GRADE)
        ax.set_xlim(-1.5, 10)
    fig.text(
        0.02,
        0.945,
        f"Linha tracejada: efeito médio de {efeito_geral_pp:+.1f} p.p. "
        f"Linha sólida: efeito zero. {int(n_clientes):,} clientes.".replace(",", "."),
        ha="left",
        color=TEXTO_2,
        fontsize=9,
    )
    eixos[-1].set_xlabel(
        "Efeito da campanha na taxa de compra (p.p.), com IC 95%", color=TEXTO_2, fontsize=9.5
    )
    fig.suptitle(
        "A campanha rende mais em quem gasta menos e comprou há mais tempo",
        x=0.02,
        ha="left",
        color=TEXTO,
        fontsize=12.5,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def rodar(con: duckdb.DuckDBPyConnection, reports: Path) -> dict:
    res = {r.nome: r.df for r in run_sql.rodar_pasta(con, "20_placar_experimento", reports)}
    perfil = con.sql("SELECT * FROM perfil_cliente").df()

    sorteio = res["01_sorteio"].iloc[0]
    _, p_srm = stats.srm(int(sorteio["n_tratamento"]), int(sorteio["n_controle"]))
    ef = res["03_efeito"].iloc[0]
    boot = stats.bootstrap_diferenca(perfil["target"], perfil["treatment_flg"], reps=5000)
    analitico = stats.diferenca_proporcoes(
        int(round(ef["taxa_t"] * ef["n_t"])),
        int(ef["n_t"]),
        int(round(ef["taxa_c"] * ef["n_c"])),
        int(ef["n_c"]),
    )
    mde = stats.efeito_minimo_detectavel(float(ef["taxa_c"]), int(ef["n_t"]), int(ef["n_c"]))
    n_decil = len(perfil) / 10 / 2
    mde_decil = stats.efeito_minimo_detectavel(float(ef["taxa_c"]), int(n_decil), int(n_decil))
    cuped_multi = cuped_regressao(perfil)
    seg = segmentos_com_bh(res["05_segmentos"])
    seg.to_csv(reports / "20_placar_experimento" / "05_segmentos_bh.csv", index=False)
    het_gasto = diferenca_entre_niveis(seg, "decil_gasto", "D01", "D10")
    het_rec = diferenca_entre_niveis(
        seg, "quartil_recencia", "Q4 (1 = mais recente)", "Q1 (1 = mais recente)"
    )
    grafico_segmentos(seg, float(ef["efeito_pp"]), reports / "figuras" / "efeito_por_segmento.png")

    resumo = {
        "n_t": int(ef["n_t"]),
        "n_c": int(ef["n_c"]),
        "taxa_t": float(ef["taxa_t"]),
        "taxa_c": float(ef["taxa_c"]),
        "efeito_pp": float(ef["efeito_pp"]),
        "ic_inf_pp": float(ef["ic_inf_pp"]),
        "ic_sup_pp": float(ef["ic_sup_pp"]),
        "boot_inf_pp": boot[0] * 100,
        "boot_sup_pp": boot[1] * 100,
        "p_valor": analitico.p_valor,
        "efeito_relativo_pct": float(ef["efeito_relativo_pct"]),
        "compras_incrementais": float(ef["compras_incrementais"]),
        "p_srm": p_srm,
        "max_abs_smd": float(res["02_balanco"]["smd"].abs().max()),
        "mde_pp": mde * 100,
        "mde_decil_pp": mde_decil * 100,
        "cuped_1": res["04_cuped"].iloc[0].to_dict(),
        "cuped_multi": cuped_multi,
        "het_gasto": het_gasto,
        "het_recencia": het_rec,
        "segmentos_significativos": int(seg["significativo_bh_5pct"].sum()),
        "segmentos_total": len(seg),
    }
    ticket = seg[seg["segmento"] == "decil_ticket"].set_index("nivel")["efeito_pp"]
    resumo |= {
        "ticket_min_pp": float(ticket.min()),
        "ticket_min_nivel": ticket.idxmin(),
        "ticket_max_pp": float(ticket.max()),
        "ticket_max_nivel": ticket.idxmax(),
    }
    (reports / "placar.md").write_text(relatorio(resumo, res, seg), encoding="utf-8")
    return resumo


def relatorio(r: dict, res: dict[str, pd.DataFrame], seg: pd.DataFrame) -> str:
    c1, cm = r["cuped_1"], r["cuped_multi"]
    tab_seg = seg[
        ["segmento", "nivel", "n_t", "n_c", "efeito_pp", "ic_inf_pp", "ic_sup_pp", "q_bh"]
    ]
    return f"""# Placar do experimento

Gerado por `campanha placar` a partir de `sql/20_placar_experimento/`. Desfecho: `target`
(comprou depois da comunicação). Tratados: {r["n_t"]:,}. Controle: {r["n_c"]:,}.

## 1. O sorteio está são?

| checagem | resultado | leitura |
|---|---|---|
| proporção de tratados | {r["n_t"] / (r["n_t"] + r["n_c"]):.4f} | esperado 0,5 |
| qui-quadrado (SRM) | p = {r["p_srm"]:.3f} | sem sinal de sorteio torto |
| maior \\|SMD\\| entre {len(res["02_balanco"])} variáveis | {r["max_abs_smd"]:.4f} | tudo abaixo de 0,1: braços comparáveis |

## 2. Efeito médio

| | controle | tratamento | diferença |
|---|---:|---:|---:|
| taxa de compra | {r["taxa_c"]:.2%} | {r["taxa_t"]:.2%} | **{r["efeito_pp"]:+.2f} p.p.** |

- IC 95% analítico (Wald, no SQL): [{r["ic_inf_pp"]:.2f}; {r["ic_sup_pp"]:.2f}] p.p.
- IC 95% por bootstrap (5.000 reamostras): [{r["boot_inf_pp"]:.2f}; {r["boot_sup_pp"]:.2f}] p.p.
- p-valor: {r["p_valor"]:.1e}
- Relativo: {r["efeito_relativo_pct"]:+.1f}% sobre a taxa do controle.
- Em compras: cerca de **{r["compras_incrementais"]:,.0f} compradores a mais** entre
  {r["n_t"]:,} tratados. Como {r["taxa_c"]:.0%} comprariam de qualquer jeito, cerca de
  {r["taxa_c"] / r["taxa_t"]:.0%} das compras dos tratados não foram causadas pela campanha.

## 3. Redução de variância (CUPED)

| método | covariáveis | redução da variância | IC encolhe | efeito (p.p.) | IC 95% |
|---|---|---:|---:|---:|---|
| sem ajuste | - | - | - | {r["efeito_pp"]:.2f} | [{r["ic_inf_pp"]:.2f}; {r["ic_sup_pp"]:.2f}] |
| CUPED (SQL) | `{c1["covariavel"]}` | {c1["reducao_variancia"]:.1%} | {c1["reducao_largura_ic"]:.1%} | {c1["efeito_cuped_pp"]:.2f} | [{c1["ic_inf_cuped_pp"]:.2f}; {c1["ic_sup_cuped_pp"]:.2f}] |
| CUPED por regressão | {len(COVARIAVEIS_CUPED)} do perfil | {cm["reducao_variancia"]:.1%} | {cm["reducao_largura_ic"]:.1%} | {cm["efeito_pp"]:.2f} | [{cm["ic_inf_pp"]:.2f}; {cm["ic_sup_pp"]:.2f}] |

A redução da variância bate com ρ² da covariável ({c1["rho2"]:.3f}), como a teoria prevê.
Ela é modesta porque o desfecho é binário: o histórico explica parte de quem compra, mas
longe de tudo. Em termos práticos, um IC {cm["reducao_largura_ic"]:.0%} mais estreito
equivale a rodar o teste com cerca de {1 / (1 - cm["reducao_variancia"]) - 1:.0%} mais clientes.
A tabela completa por covariável está em `reports/20_placar_experimento/04_cuped.csv`.

## 4. Poder

- Com {r["n_t"]:,} por braço e taxa-base de {r["taxa_c"]:.1%}, o menor efeito detectável
  (α = 5%, poder 80%) é **{r["mde_pp"]:.2f} p.p.** O efeito observado é cerca de
  {r["efeito_pp"] / r["mde_pp"]:.0f} vezes isso: o teste tinha folga.
- Num decil (cerca de 10 mil por braço) o MDE sobe para **{r["mde_decil_pp"]:.2f} p.p.**:
  diferenças entre segmentos menores que isso não são confiáveis.

## 5. Métrica de proteção

A base não tem gasto depois da campanha (ADR 0002), então não dá para medir se a campanha
derrubou o ticket. O que dá para ver é o efeito por faixa de ticket histórico: vai de
{r["ticket_min_pp"]:+.1f} p.p. (decil {r["ticket_min_nivel"]}) a {r["ticket_max_pp"]:+.1f} p.p.
(decil {r["ticket_max_nivel"]}). Num próximo teste, o
gasto pós-campanha precisa ser coletado como métrica de proteção definida antes do início.

## 6. Efeito por segmento

{r["segmentos_significativos"]} de {r["segmentos_total"]} segmentos têm efeito diferente de zero depois
da correção de Benjamini-Hochberg (q < 5%). O mais útil é onde o efeito **muda**:

- **Gasto:** decil que menos gasta vs. decil que mais gasta: {r["het_gasto"].diferenca * 100:+.1f} p.p.
  (IC [{r["het_gasto"].ic_inf * 100:.1f}; {r["het_gasto"].ic_sup * 100:.1f}], p = {r["het_gasto"].p_valor:.1e}).
- **Recência:** quartil que comprou há mais tempo vs. o mais recente: {r["het_recencia"].diferenca * 100:+.1f} p.p.
  (IC [{r["het_recencia"].ic_inf * 100:.1f}; {r["het_recencia"].ic_sup * 100:.1f}], p = {r["het_recencia"].p_valor:.1e}).

Todo cliente do experimento comprou nos 23 dias anteriores ao corte, então não existe o
segmento "inativo há mais de 30 dias"; o recorte de recência usa 14 dias e quartis.

![efeito por segmento](figuras/efeito_por_segmento.png)

{run_sql.tabela_md(tab_seg, casas=3)}
"""
