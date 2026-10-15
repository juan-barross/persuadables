from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from matplotlib.axes import Axes
from scipy import stats as st

from persuadables import graficos, relatorio, run_sql, stats

EM_PP = 100
Q_SIGNIFICATIVO = 0.05

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

PAINEIS_DO_GRAFICO = (
    ("decil_gasto", "Decil de gasto antes da campanha (D01 = gasta menos)"),
    ("quartil_recencia", "Quartil de recência (Q1 = comprou mais recentemente)"),
    ("decil_ticket", "Decil de ticket médio (D01 = ticket menor)"),
)

QUARTIL_MAIS_ANTIGO = "Q4 (1 = mais recente)"
QUARTIL_MAIS_RECENTE = "Q1 (1 = mais recente)"
COLUNAS_DA_TABELA = [
    "segmento",
    "nivel",
    "n_t",
    "n_c",
    "efeito_pp",
    "ic_inf_pp",
    "ic_sup_pp",
    "q_bh",
]


def rodar(con: duckdb.DuckDBPyConnection, reports: Path) -> dict:
    consultas = {r.nome: r.df for r in run_sql.rodar_pasta(con, "20_placar_experimento", reports)}
    colunas = ", ".join(["treatment_flg", "target", *COVARIAVEIS_CUPED])
    perfil = con.sql(f"SELECT {colunas} FROM perfil_cliente").df()

    segmentos = segmentos_com_bh(consultas["05_segmentos"])
    relatorio.salvar_csv(segmentos, reports / "20_placar_experimento" / "05_segmentos_bh.csv")

    resumo = (
        resumo_do_efeito(consultas, perfil)
        | resumo_do_cuped(consultas["04_cuped"].iloc[0], perfil)
        | resumo_dos_segmentos(segmentos)
    )
    grafico_segmentos(
        segmentos, resumo["efeito_pp"], reports / "figuras" / "efeito_por_segmento.png"
    )

    texto = relatorio.preencher(
        "placar",
        **resumo,
        tabela_segmentos=relatorio.tabela(segmentos[COLUNAS_DA_TABELA], casas=3),
    )
    (reports / "placar.md").write_text(texto, encoding="utf-8")
    return resumo


def resumo_do_efeito(consultas: dict[str, pd.DataFrame], perfil: pd.DataFrame) -> dict:
    sorteio = consultas["01_sorteio"].iloc[0]
    efeito = consultas["03_efeito"].iloc[0]
    n_t, n_c = int(efeito["n_t"]), int(efeito["n_c"])
    _, p_srm = stats.srm(int(sorteio["n_tratamento"]), int(sorteio["n_controle"]))
    boot_inf, boot_sup = stats.bootstrap_diferenca(
        perfil["target"], perfil["treatment_flg"], reps=5000
    )
    mde = stats.efeito_minimo_detectavel(efeito["taxa_c"], n_t, n_c)
    por_braco_num_decil = (n_t + n_c) // 20
    mde_decil = stats.efeito_minimo_detectavel(
        efeito["taxa_c"], por_braco_num_decil, por_braco_num_decil
    )
    return {
        "n_t": n_t,
        "n_c": n_c,
        "prop_tratamento": n_t / (n_t + n_c),
        "p_srm": p_srm,
        "n_variaveis_balanco": len(consultas["02_balanco"]),
        "max_abs_smd": float(consultas["02_balanco"]["smd"].abs().max()),
        "taxa_t": float(efeito["taxa_t"]),
        "taxa_c": float(efeito["taxa_c"]),
        "efeito_pp": float(efeito["efeito_pp"]),
        "ic_inf_pp": float(efeito["ic_inf_pp"]),
        "ic_sup_pp": float(efeito["ic_sup_pp"]),
        "boot_inf_pp": boot_inf * EM_PP,
        "boot_sup_pp": boot_sup * EM_PP,
        "p_valor": float(2 * st.norm.sf(abs(efeito["z"]))),
        "efeito_relativo_pct": float(efeito["efeito_relativo_pct"]),
        "compras_incrementais": float(efeito["compras_incrementais"]),
        "compraria_sem_campanha": float(efeito["taxa_c"] / efeito["taxa_t"]),
        "mde_pp": mde * EM_PP,
        "mde_decil_pp": mde_decil * EM_PP,
        "efeito_em_mdes": float(efeito["efeito_pp"]) / (mde * EM_PP),
    }


def resumo_do_cuped(melhor_covariavel_sql: pd.Series, perfil: pd.DataFrame) -> dict:
    bruto, ajustado = cuped_por_regressao(perfil)
    reducao_variancia = 1 - (ajustado.erro_padrao / bruto.erro_padrao) ** 2
    return {
        "cuped_sql_covariavel": melhor_covariavel_sql["covariavel"],
        "cuped_sql_rho2": melhor_covariavel_sql["rho2"],
        "cuped_sql_reducao_variancia": melhor_covariavel_sql["reducao_variancia"],
        "cuped_sql_reducao_ic": melhor_covariavel_sql["reducao_largura_ic"],
        "cuped_sql_efeito_pp": melhor_covariavel_sql["efeito_cuped_pp"],
        "cuped_sql_ic_inf_pp": melhor_covariavel_sql["ic_inf_cuped_pp"],
        "cuped_sql_ic_sup_pp": melhor_covariavel_sql["ic_sup_cuped_pp"],
        "n_covariaveis": len(COVARIAVEIS_CUPED),
        "cuped_reg_reducao_variancia": reducao_variancia,
        "cuped_reg_reducao_ic": 1 - ajustado.largura / bruto.largura,
        "cuped_reg_efeito_pp": ajustado.diferenca * EM_PP,
        "cuped_reg_ic_inf_pp": ajustado.ic_inf * EM_PP,
        "cuped_reg_ic_sup_pp": ajustado.ic_sup * EM_PP,
        "clientes_extras_equivalentes": 1 / (1 - reducao_variancia) - 1,
    }


def cuped_por_regressao(perfil: pd.DataFrame) -> tuple[stats.Efeito, stats.Efeito]:
    covariaveis = perfil[COVARIAVEIS_CUPED].astype(float)
    covariaveis = covariaveis.fillna(covariaveis.mean())
    covariaveis -= covariaveis.mean()
    tratado = perfil["treatment_flg"].astype(float)
    comprou = perfil["target"].astype(float)

    so_tratamento = sm.add_constant(tratado)
    com_covariaveis = sm.add_constant(pd.concat([tratado, covariaveis], axis=1))
    bruto = sm.OLS(comprou, so_tratamento).fit(cov_type="HC1")
    ajustado = sm.OLS(comprou, com_covariaveis).fit(cov_type="HC1")
    return _efeito_do_tratamento(bruto), _efeito_do_tratamento(ajustado)


def _efeito_do_tratamento(regressao) -> stats.Efeito:
    return stats.efeito_de(
        float(regressao.params["treatment_flg"]), float(regressao.bse["treatment_flg"])
    )


def segmentos_com_bh(segmentos: pd.DataFrame) -> pd.DataFrame:
    z = stats.z_critico()
    p_valor = 2 * st.norm.sf(segmentos["z"].abs())
    q_bh = stats.benjamini_hochberg(p_valor)
    return segmentos.assign(
        p_valor=p_valor,
        q_bh=q_bh,
        ic_inf_pp=segmentos["efeito_pp"] - z * segmentos["ep_pp"],
        ic_sup_pp=segmentos["efeito_pp"] + z * segmentos["ep_pp"],
        significativo_bh_5pct=q_bh < Q_SIGNIFICATIVO,
    )


def resumo_dos_segmentos(segmentos: pd.DataFrame) -> dict:
    gasto = diferenca_entre_niveis(segmentos, "decil_gasto", "D01", "D10")
    recencia = diferenca_entre_niveis(
        segmentos, "quartil_recencia", QUARTIL_MAIS_ANTIGO, QUARTIL_MAIS_RECENTE
    )
    ticket = segmentos[segmentos["segmento"] == "decil_ticket"].set_index("nivel")["efeito_pp"]
    return {
        "segmentos_significativos": int(segmentos["significativo_bh_5pct"].sum()),
        "segmentos_total": len(segmentos),
        **_em_pp("gasto", gasto),
        **_em_pp("recencia", recencia),
        "ticket_min_pp": float(ticket.min()),
        "ticket_min_nivel": ticket.idxmin(),
        "ticket_max_pp": float(ticket.max()),
        "ticket_max_nivel": ticket.idxmax(),
    }


def diferenca_entre_niveis(
    segmentos: pd.DataFrame, segmento: str, nivel_a: str, nivel_b: str
) -> stats.Efeito:
    niveis = segmentos[segmentos["segmento"] == segmento].set_index("nivel")
    diferenca = niveis.loc[nivel_a, "efeito_pp"] - niveis.loc[nivel_b, "efeito_pp"]
    erro_padrao = np.hypot(niveis.loc[nivel_a, "ep_pp"], niveis.loc[nivel_b, "ep_pp"])
    return stats.efeito_de(float(diferenca) / EM_PP, float(erro_padrao) / EM_PP)


def _em_pp(prefixo: str, efeito: stats.Efeito) -> dict:
    return {
        f"{prefixo}_dif_pp": efeito.diferenca * EM_PP,
        f"{prefixo}_ic_inf_pp": efeito.ic_inf * EM_PP,
        f"{prefixo}_ic_sup_pp": efeito.ic_sup * EM_PP,
        f"{prefixo}_p": efeito.p_valor,
    }


def grafico_segmentos(segmentos: pd.DataFrame, efeito_medio_pp: float, destino: Path) -> None:
    paineis = [
        (titulo, segmentos[segmentos["segmento"] == nome].sort_values("nivel", ascending=False))
        for nome, titulo in PAINEIS_DO_GRAFICO
    ]
    fig = graficos.nova_figura(8, 9.5)
    eixos = fig.subplots(
        len(paineis), 1, gridspec_kw={"height_ratios": [len(niveis) for _, niveis in paineis]}
    )
    for ax, (titulo, niveis) in zip(eixos, paineis, strict=True):
        _desenhar_intervalos(ax, titulo, niveis, efeito_medio_pp)
    eixos[-1].set_xlabel(
        "Efeito da campanha na taxa de compra (p.p.), com IC 95%",
        color=graficos.TEXTO_SECUNDARIO,
    )

    n_clientes = int(paineis[0][1][["n_t", "n_c"]].to_numpy().sum())
    graficos.titular(
        fig,
        "A campanha rende mais em quem gasta menos e comprou há mais tempo",
        f"Linha tracejada: efeito médio de {efeito_medio_pp:+.1f} p.p. "
        f"Linha sólida: efeito zero. {n_clientes:,} clientes.".replace(",", "."),
        espaco_topo=0.94,
    )
    graficos.salvar(fig, destino)


def _desenhar_intervalos(
    ax: Axes, titulo: str, niveis: pd.DataFrame, efeito_medio_pp: float
) -> None:
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
    ax.set_yticks(posicoes, niveis["nivel"].str.split(" ").str[0])
    ax.set_title(titulo, loc="left", color=graficos.TEXTO, fontsize=10.5, pad=6)
    ax.set_xlim(-1.5, 10)
