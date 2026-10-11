"""Modelos de uplift contra um modelo de propensão, avaliados com Qini e AUUC.

Propensão prevê quem compra; uplift prevê em quem a campanha MUDA a compra. Os dois só
coincidem se quem compra muito também for quem mais reage, e o placar já mostrou que é o
contrário (o efeito é maior em quem gasta menos).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from lightgbm import LGBMClassifier, LGBMRegressor  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklift.metrics import qini_auc_score, qini_curve, uplift_at_k, uplift_auc_score  # noqa: E402
from sklift.models import ClassTransformation, SoloModel, TwoModels  # noqa: E402

from campanha import run_sql, stats  # noqa: E402

SEMENTE = 42
FORA = ["client_id", "treatment_flg", "target"]

# Paleta de referência (skill dataviz), slots categóricos em ordem fixa.
CORES = {
    "propensão": "#2a78d6",
    "S-learner": "#eb6834",
    "T-learner": "#1baf7a",
    "X-learner": "#eda100",
    "class transformation": "#e87ba4",
}
SUPERFICIE, TEXTO, TEXTO_2, GRADE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

EXPLICAR = [
    "gasto_total",
    "ticket_medio",
    "n_transacoes",
    "dias_desde_ultima",
    "gasto_30d",
    "intervalo_medio_dias",
    "ja_resgatou",
    "prop_transacoes_com_resgate",
    "lojas_distintas",
    "idade",
]


def _lgbm(**extra) -> dict:
    return dict(
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=31,
        min_child_samples=200,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        random_state=SEMENTE,
        verbose=-1,
        **extra,
    )


class Propensao:
    """O erro comum: ordenar clientes pela chance de comprar, ignorando o tratamento."""

    def __init__(self) -> None:
        self.modelo = LGBMClassifier(**_lgbm())

    def fit(self, x, y, t):
        self.modelo.fit(x, y)
        return self

    def predict(self, x):
        return self.modelo.predict_proba(x)[:, 1]


class XLearner:
    """X-learner (Künzel et al., 2019) com propensão conhecida de 0,5 (sorteio)."""

    def __init__(self) -> None:
        self.m0 = LGBMClassifier(**_lgbm())
        self.m1 = LGBMClassifier(**_lgbm())
        self.tau0 = LGBMRegressor(**_lgbm())
        self.tau1 = LGBMRegressor(**_lgbm())

    def fit(self, x, y, t):
        t = np.asarray(t).astype(bool)
        y = np.asarray(y)
        self.m0.fit(x[~t], y[~t])
        self.m1.fit(x[t], y[t])
        d1 = y[t] - self.m0.predict_proba(x[t])[:, 1]
        d0 = self.m1.predict_proba(x[~t])[:, 1] - y[~t]
        self.tau1.fit(x[t], d1)
        self.tau0.fit(x[~t], d0)
        return self

    def predict(self, x):
        return 0.5 * self.tau0.predict(x) + 0.5 * self.tau1.predict(x)


def modelos() -> dict:
    return {
        "propensão": Propensao(),
        "S-learner": SoloModel(LGBMClassifier(**_lgbm())),
        "T-learner": TwoModels(
            LGBMClassifier(**_lgbm()), LGBMClassifier(**_lgbm()), method="vanilla"
        ),
        "X-learner": XLearner(),
        "class transformation": ClassTransformation(LGBMClassifier(**_lgbm())),
    }


@dataclass
class Divisao:
    treino: pd.DataFrame
    validacao: pd.DataFrame
    teste: pd.DataFrame


def dividir(perfil: pd.DataFrame, semente: int = SEMENTE) -> Divisao:
    """60/20/20 estratificado por tratamento × desfecho."""
    estrato = perfil["treatment_flg"] * 2 + perfil["target"]
    treino, resto = train_test_split(perfil, test_size=0.4, stratify=estrato, random_state=semente)
    validacao, teste = train_test_split(
        resto, test_size=0.5, stratify=estrato.loc[resto.index], random_state=semente
    )
    return Divisao(treino, validacao, teste)


def variaveis(perfil: pd.DataFrame) -> list[str]:
    return [c for c in perfil.columns if c not in FORA]


def avaliar(y, u, t) -> dict:
    y, u, t = np.asarray(y), np.asarray(u), np.asarray(t)
    x_q, y_q = qini_curve(y, u, t)
    total = y_q[-1]
    cap = np.interp(0.3 * len(y), x_q, y_q) / total if total else np.nan
    return {
        "auuc": uplift_auc_score(y, u, t),
        "qini_auc": qini_auc_score(y, u, t),
        "uplift_top10_pp": uplift_at_k(y, u, t, strategy="overall", k=0.1) * 100,
        "uplift_top30_pp": uplift_at_k(y, u, t, strategy="overall", k=0.3) * 100,
        "captura_top30": cap,
    }


def curva_qini(y, u, t, pontos: int = 101) -> tuple[np.ndarray, np.ndarray]:
    """Compras incrementais acumuladas por fração da base contatada (grade fixa)."""
    x_q, y_q = qini_curve(np.asarray(y), np.asarray(u), np.asarray(t))
    grade = np.linspace(0, 1, pontos)
    return grade, np.interp(grade * len(y), np.r_[0, x_q], np.r_[0, y_q])


def uplift_observado(teste: pd.DataFrame, score: np.ndarray, faixas: int = 10) -> pd.DataFrame:
    """Taxa de compra de tratados e controle por decil do score (1 = maior score)."""
    d = teste[["treatment_flg", "target"]].copy()
    # Decil pelo posto e não pelo valor: um score com empates (ou constante, quando a base é
    # pequena demais para o LightGBM dividir) ainda gera dez faixas do mesmo tamanho.
    posto = pd.Series(-score).rank(method="first")
    d["faixa"] = pd.qcut(posto, faixas, labels=range(1, faixas + 1)).astype(int).to_numpy()
    linhas = []
    for f, g in d.groupby("faixa"):
        t, c = g[g.treatment_flg == 1], g[g.treatment_flg == 0]
        e = stats.diferenca_proporcoes(t.target.sum(), len(t), c.target.sum(), len(c))
        linhas.append(
            {
                "faixa": f,
                "n": len(g),
                "taxa_t": t.target.mean(),
                "taxa_c": c.target.mean(),
                "uplift_pp": e.diferenca * 100,
                "ic_inf_pp": e.ic_inf * 100,
                "ic_sup_pp": e.ic_sup * 100,
            }
        )
    return pd.DataFrame(linhas)


def quem_e_influenciado(teste: pd.DataFrame, score: np.ndarray, frac: float = 0.2) -> pd.DataFrame:
    """Perfil mediano dos 20% com maior uplift previsto contra os 20% com menor."""
    ordem = np.argsort(-score)
    k = int(len(score) * frac)
    topo, base = teste.iloc[ordem[:k]], teste.iloc[ordem[-k:]]
    linhas = []
    for nome, g in (("20% maior uplift", topo), ("20% menor uplift", base), ("todos", teste)):
        t, c = g[g.treatment_flg == 1], g[g.treatment_flg == 0]
        e = stats.diferenca_proporcoes(t.target.sum(), len(t), c.target.sum(), len(c))
        linha = {"grupo": nome, "n": len(g), "taxa_controle": c.target.mean()}
        linha |= {"uplift_observado_pp": e.diferenca * 100}
        linha |= {"ic_inf_pp": e.ic_inf * 100, "ic_sup_pp": e.ic_sup * 100}
        linha |= {v: g[v].median() for v in EXPLICAR}
        linhas.append(linha)
    return pd.DataFrame(linhas)


def grafico_qini(curvas: dict, total_aleatorio: float, n_teste: int, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5.2), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    ax.plot([0, 100], [0, total_aleatorio], color=TEXTO_2, lw=1.2, ls=(0, (4, 3)))
    ax.annotate(
        "envio aleatório",
        xy=(30, total_aleatorio * 0.30),
        xytext=(36, total_aleatorio * 0.12),
        color=TEXTO_2,
        fontsize=8.5,
        arrowprops={"arrowstyle": "-", "color": TEXTO_2, "lw": 0.8},
    )
    for nome, (x, y) in curvas.items():
        ax.plot(x * 100, y, color=CORES[nome], lw=2, label=nome)
    ax.set_xlabel("% dos clientes que recebem a campanha (ordenados pelo modelo)", color=TEXTO_2)
    ax.set_ylabel("compradores incrementais (conjunto de teste)", color=TEXTO_2)
    ax.tick_params(colors=TEXTO_2, labelsize=9)
    ax.grid(color=GRADE, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    leg = ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=TEXTO)
    leg.set_title("modelo", prop={"size": 9})
    fig.suptitle(
        "Modelos de uplift acham os compradores incrementais; propensão não",
        x=0.02,
        ha="left",
        color=TEXTO,
        fontsize=11.5,
        fontweight="bold",
    )
    fig.text(
        0.02,
        0.905,
        f"Curva Qini no conjunto de teste ({n_teste:,} clientes)".replace(",", "."),
        color=TEXTO_2,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def rodar(perfil: pd.DataFrame, reports: Path, dados: Path) -> dict:
    div = dividir(perfil)
    cols = variaveis(perfil)
    resultados, scores_val, scores_teste, curvas = [], {}, {}, {}
    for nome, m in modelos().items():
        m.fit(div.treino[cols], div.treino["target"], div.treino["treatment_flg"])
        for conjunto, d, guarda in (
            ("validação", div.validacao, scores_val),
            ("teste", div.teste, scores_teste),
        ):
            u = m.predict(d[cols])
            guarda[nome] = u
            resultados.append(
                {"modelo": nome, "conjunto": conjunto} | avaliar(d.target, u, d.treatment_flg)
            )
        curvas[nome] = curva_qini(div.teste.target, scores_teste[nome], div.teste.treatment_flg)

    tabela = pd.DataFrame(resultados)
    val = tabela[(tabela.conjunto == "validação") & (tabela.modelo != "propensão")]
    escolhido = val.sort_values("auuc", ascending=False).iloc[0]["modelo"]

    teste = div.teste.reset_index(drop=True)
    pontuado = teste[["client_id", "treatment_flg", "target"]].copy()
    for nome, u in scores_teste.items():
        pontuado[nome] = u
    pontuado.attrs["escolhido"] = escolhido
    pontuado.to_parquet(dados / "scores_teste.parquet", index=False)

    quem = quem_e_influenciado(teste, scores_teste[escolhido])
    decis = {nome: uplift_observado(teste, scores_teste[nome]) for nome in (escolhido, "propensão")}
    destino = reports / "40_uplift"
    destino.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(destino / "metricas.csv", index=False)
    quem.to_csv(destino / "quem_e_influenciado.csv", index=False)
    for nome, d in decis.items():
        d.to_csv(destino / f"uplift_por_decil_{nome.replace(' ', '_')}.csv", index=False)
    (destino / "modelo_escolhido.txt").write_text(escolhido + "\n", encoding="utf-8")

    t1, t0 = teste[teste.treatment_flg == 1], teste[teste.treatment_flg == 0]
    ate = stats.diferenca_proporcoes(t1.target.sum(), len(t1), t0.target.sum(), len(t0))
    total_aleatorio = curvas[escolhido][1][-1]
    grafico_qini(curvas, total_aleatorio, len(teste), reports / "figuras" / "curva_qini.png")
    r = {
        "escolhido": escolhido,
        "tabela": tabela,
        "quem": quem,
        "decis": decis,
        "n": (len(div.treino), len(div.validacao), len(div.teste)),
        "ate_teste_pp": ate.diferenca * 100,
    }
    (reports / "uplift.md").write_text(relatorio(r), encoding="utf-8")
    return r


def relatorio(r: dict) -> str:
    tab = r["tabela"]
    teste = (
        tab[tab.conjunto == "teste"].drop(columns="conjunto").sort_values("auuc", ascending=False)
    )
    esc = teste.set_index("modelo").loc[r["escolhido"]]
    prop = teste.set_index("modelo").loc["propensão"]
    quem = r["quem"].set_index("grupo")
    q_top, q_base = quem.loc["20% maior uplift"], quem.loc["20% menor uplift"]
    dec_esc = r["decis"][r["escolhido"]]
    dec_prop = r["decis"]["propensão"]
    n_tr, n_va, n_te = r["n"]
    linhas_decil = "\n".join(
        f"| {a.faixa} | {a.uplift_pp:+.1f} [{a.ic_inf_pp:.1f}; {a.ic_sup_pp:.1f}] | "
        f"{b.uplift_pp:+.1f} [{b.ic_inf_pp:.1f}; {b.ic_sup_pp:.1f}] | {b.taxa_c:.0%} |"
        for a, b in zip(dec_esc.itertuples(), dec_prop.itertuples(), strict=True)
    )
    return f"""# Modelos de uplift

Gerado por `campanha uplift`. Divisão estratificada por tratamento × desfecho, semente
{SEMENTE}: treino {n_tr:,}, validação {n_va:,}, teste {n_te:,}. Todos os modelos usam
LightGBM com os mesmos hiperparâmetros e as variáveis do perfil em SQL. O modelo escolhido
é o de maior AUUC na **validação** (`{r["escolhido"]}`); os números abaixo são do
**teste**, que nenhum modelo viu.

## Placar dos modelos (teste)

{run_sql.tabela_md(teste, casas=4)}

- `auuc` e `qini_auc`: área sob a curva de uplift e sob a curva Qini, normalizadas pelo
  sklift (quanto maior, melhor; 0 = aleatório).
- `uplift_top30_pp`: diferença de taxa de compra entre tratados e controle dentro dos
  30% de maior score. Efeito médio no teste: {r["ate_teste_pp"]:.2f} p.p.
- `captura_top30`: fração das compras incrementais da base inteira que já está nos 30%
  de maior score.

**Leitura:** o `{r["escolhido"]}` encontra nos 30% de maior score um efeito de
{esc["uplift_top30_pp"]:.1f} p.p., contra {prop["uplift_top30_pp"]:.1f} p.p. nos 30% que a
propensão escolhe.

![curva Qini](figuras/curva_qini.png)

## Uplift observado por decil de score (teste)

Decil 1 = maior score. Se o modelo funciona, o uplift observado cai do decil 1 ao 10.

| decil | uplift `{r["escolhido"]}` (p.p.) | uplift propensão (p.p.) | taxa do controle, propensão |
|---|---:|---:|---:|
{linhas_decil}

## Quem é influenciado

Mediana das variáveis do perfil nos 20% com maior uplift previsto pelo `{r["escolhido"]}`
contra os 20% com menor, no teste (valores em rublos):

{run_sql.tabela_md(r["quem"], casas=2)}

Nos 20% de maior uplift a campanha mudou a compra em {q_top["uplift_observado_pp"]:+.1f} p.p.
(IC [{q_top["ic_inf_pp"]:.1f}; {q_top["ic_sup_pp"]:.1f}]); nos 20% de menor, em
{q_base["uplift_observado_pp"]:+.1f} p.p. (IC [{q_base["ic_inf_pp"]:.1f}; {q_base["ic_sup_pp"]:.1f}]).
Mediana dos mais influenciados contra os menos: {q_top["n_transacoes"]:.0f} contra
{q_base["n_transacoes"]:.0f} transações, {q_top["gasto_total"]:,.0f} contra
{q_base["gasto_total"]:,.0f} rublos gastos no período, {q_top["dias_desde_ultima"]:.1f} contra
{q_base["dias_desde_ultima"]:.1f} dias desde a última compra, idade de {q_top["idade"]:.0f}
contra {q_base["idade"]:.0f} anos. Sem a campanha,
{q_top["taxa_controle"]:.0%} deles comprariam, contra {q_base["taxa_controle"]:.0%} no grupo
de menor uplift.
"""
