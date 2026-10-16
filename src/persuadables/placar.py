from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as st

from persuadables import graficos, relatorio, run_sql, stats

EM_PP = 100
COVARIAVEIS_CUPED = (
    "n_transacoes n_transacoes_30d dias_com_compra dias_desde_ultima intervalo_medio_dias "
    "gasto_total gasto_30d ticket_medio pontos_gastos ja_resgatou"
).split()
PAINEIS = {
    "decil_gasto": "Decil de gasto antes da campanha (D01 = gasta menos)",
    "quartil_recencia": "Quartil de recência (Q1 = comprou mais recentemente)",
    "decil_ticket": "Decil de ticket médio (D01 = ticket menor)",
}
COLUNAS_DA_TABELA = "segmento nivel n_t n_c efeito_pp ic_inf_pp ic_sup_pp q_bh".split()


def rodar(con: duckdb.DuckDBPyConnection, reports: Path) -> dict:
    sql = {r.nome: r.df for r in run_sql.rodar_pasta(con, "20_placar_experimento", reports)}
    colunas = ", ".join(["treatment_flg", "target", *COVARIAVEIS_CUPED])
    perfil = con.sql(f"SELECT {colunas} FROM perfil_cliente").df()
    segmentos = segmentos_com_bh(sql["05_segmentos"])
    relatorio.salvar_csv(segmentos, reports / "20_placar_experimento" / "05_segmentos_bh.csv")

    resumo = resumir(sql, perfil, segmentos)
    grafico_segmentos(
        segmentos, resumo["efeito_pp"], reports / "figuras" / "efeito_por_segmento.png"
    )
    texto = relatorio.preencher(
        "placar",
        **resumo,
        efeito=sql["03_efeito"].iloc[0],
        cuped_sql=sql["04_cuped"].iloc[0],
        tabela_segmentos=relatorio.tabela(segmentos[COLUNAS_DA_TABELA], casas=3),
    )
    (reports / "placar.md").write_text(texto, encoding="utf-8")
    return resumo


def resumir(sql: dict[str, pd.DataFrame], perfil: pd.DataFrame, segmentos: pd.DataFrame) -> dict:
    efeito = sql["03_efeito"].iloc[0]
    n_t, n_c = int(efeito["n_t"]), int(efeito["n_c"])
    boot_inf, boot_sup = stats.bootstrap_diferenca(perfil["target"], perfil["treatment_flg"], 5000)
    mde_pp = stats.efeito_minimo_detectavel(efeito["taxa_c"], n_t, n_c) * EM_PP
    por_braco_num_decil = (n_t + n_c) // 20
    mde_decil = stats.efeito_minimo_detectavel(
        efeito["taxa_c"], por_braco_num_decil, por_braco_num_decil
    )
    bruto, cuped = cuped_por_regressao(perfil)
    reducao_variancia = 1 - (cuped.erro_padrao / bruto.erro_padrao) ** 2
    ticket = segmentos[segmentos["segmento"] == "decil_ticket"].set_index("nivel")["efeito_pp"]
    return {
        "n_t": n_t,
        "n_c": n_c,
        "prop_tratamento": n_t / (n_t + n_c),
        "p_srm": stats.srm(n_t, n_c)[1],
        "n_variaveis_balanco": len(sql["02_balanco"]),
        "max_abs_smd": sql["02_balanco"]["smd"].abs().max(),
        "efeito_pp": efeito["efeito_pp"],
        "ic_inf_pp": efeito["ic_inf_pp"],
        "ic_sup_pp": efeito["ic_sup_pp"],
        "boot_inf_pp": boot_inf * EM_PP,
        "boot_sup_pp": boot_sup * EM_PP,
        "p_valor": 2 * st.norm.sf(abs(efeito["z"])),
        "compraria_sem_campanha": efeito["taxa_c"] / efeito["taxa_t"],
        "mde_pp": mde_pp,
        "mde_decil_pp": mde_decil * EM_PP,
        "efeito_em_mdes": efeito["efeito_pp"] / mde_pp,
        "n_covariaveis": len(COVARIAVEIS_CUPED),
        "cuped": cuped,
        "cuped_reducao_variancia": reducao_variancia,
        "cuped_reducao_ic": 1 - cuped.largura / bruto.largura,
        "clientes_extras_equivalentes": 1 / (1 - reducao_variancia) - 1,
        "ticket_min_pp": ticket.min(),
        "ticket_min_nivel": ticket.idxmin(),
        "ticket_max_pp": ticket.max(),
        "ticket_max_nivel": ticket.idxmax(),
        "segmentos_significativos": int(segmentos["significativo_bh_5pct"].sum()),
        "segmentos_total": len(segmentos),
        "gasto": diferenca_entre_niveis(segmentos, "decil_gasto", "D01", "D10"),
        "recencia": diferenca_entre_niveis(
            segmentos, "quartil_recencia", "Q4 (1 = mais recente)", "Q1 (1 = mais recente)"
        ),
    }


def cuped_por_regressao(perfil: pd.DataFrame) -> tuple[stats.Efeito, stats.Efeito]:
    covariaveis = perfil[COVARIAVEIS_CUPED].astype(float)
    covariaveis = covariaveis.fillna(covariaveis.mean()) - covariaveis.mean()
    tratado = perfil["treatment_flg"].astype(float)

    def efeito_do_tratamento(*explicativas: pd.Series | pd.DataFrame) -> stats.Efeito:
        x = sm.add_constant(pd.concat(explicativas, axis=1))
        regressao = sm.OLS(perfil["target"].astype(float), x).fit(cov_type="HC1")
        return stats.efeito_de(
            regressao.params["treatment_flg"] * EM_PP, regressao.bse["treatment_flg"] * EM_PP
        )

    return efeito_do_tratamento(tratado), efeito_do_tratamento(tratado, covariaveis)


def segmentos_com_bh(segmentos: pd.DataFrame) -> pd.DataFrame:
    z = stats.z_critico()
    p_valor = 2 * st.norm.sf(segmentos["z"].abs())
    q_bh = stats.benjamini_hochberg(p_valor)
    return segmentos.assign(
        p_valor=p_valor,
        q_bh=q_bh,
        ic_inf_pp=segmentos["efeito_pp"] - z * segmentos["ep_pp"],
        ic_sup_pp=segmentos["efeito_pp"] + z * segmentos["ep_pp"],
        significativo_bh_5pct=q_bh < stats.ALPHA,
    )


def diferenca_entre_niveis(
    segmentos: pd.DataFrame, segmento: str, nivel_a: str, nivel_b: str
) -> stats.Efeito:
    niveis = segmentos[segmentos["segmento"] == segmento].set_index("nivel")
    a, b = niveis.loc[nivel_a], niveis.loc[nivel_b]
    return stats.efeito_de(a["efeito_pp"] - b["efeito_pp"], float(np.hypot(a["ep_pp"], b["ep_pp"])))


def grafico_segmentos(segmentos: pd.DataFrame, efeito_medio_pp: float, destino: Path) -> None:
    paineis = {
        titulo: segmentos[segmentos["segmento"] == nome].sort_values("nivel", ascending=False)
        for nome, titulo in PAINEIS.items()
    }
    fig = graficos.nova_figura(8, 9.5)
    alturas = [len(niveis) for niveis in paineis.values()]
    eixos = fig.subplots(len(paineis), 1, gridspec_kw={"height_ratios": alturas})
    for ax, (titulo, niveis) in zip(eixos, paineis.items(), strict=True):
        posicoes = np.arange(len(niveis))
        graficos.estilizar(ax, grade="x")
        ax.axvline(0, color=graficos.TEXTO_SECUNDARIO, lw=1)
        ax.axvline(efeito_medio_pp, color=graficos.TEXTO_SECUNDARIO, lw=1, ls=graficos.TRACEJADO)
        ax.hlines(posicoes, niveis["ic_inf_pp"], niveis["ic_sup_pp"], color=graficos.AZUL, lw=2)
        ax.plot(
            niveis["efeito_pp"],
            posicoes,
            "o",
            color=graficos.AZUL,
            ms=8,
            mec=graficos.SUPERFICIE,
            mew=2,
        )
        ax.set_yticks(posicoes, niveis["nivel"].str.split().str[0])
        ax.set_title(titulo, loc="left", color=graficos.TEXTO, fontsize=10.5, pad=6)
        ax.set_xlim(-1.5, 10)
    graficos.rotular_eixos(eixos[-1], "Efeito da campanha na taxa de compra (p.p.), com IC 95%")
    n_clientes = int(paineis[PAINEIS["decil_gasto"]][["n_t", "n_c"]].to_numpy().sum())
    graficos.titular(
        fig,
        "A campanha rende mais em quem gasta menos e comprou há mais tempo",
        f"Linha tracejada: efeito médio de {efeito_medio_pp:+.1f} p.p. "
        f"Linha sólida: efeito zero. {n_clientes:,} clientes.".replace(",", "."),
        espaco_topo=0.94,
    )
    graficos.salvar(fig, destino)
