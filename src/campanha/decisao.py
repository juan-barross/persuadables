"""Da métrica para a decisão: quantas compras a mais e quanto retorno por orçamento.

Para cada fração da base contatada, compara mandar aleatório, por propensão e por uplift.
As compras incrementais vêm do conjunto de teste (que nenhum modelo viu), escaladas para a
base do experimento, com IC por bootstrap. O dinheiro entra por premissas explícitas
(Premissas) e o simulador só refaz a conta linear em cima das curvas pré-calculadas.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from campanha import run_sql  # noqa: E402

SUPERFICIE, TEXTO, TEXTO_2, GRADE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
CORES = {"propensão": "#2a78d6", "uplift": "#eb6834", "aleatório": TEXTO_2}
FRACOES = np.round(np.linspace(0.05, 1.0, 20), 2)


@dataclass(frozen=True)
class Premissas:
    """Tudo em rublos, porque a X5 é russa. Ajustáveis no simulador."""

    custo_por_contato: float = 3.0  # SMS em massa; sem cupom
    margem: float = 0.20  # margem bruta de varejo alimentar
    compras_por_comprador: float = 1.0  # conservador: o incremental compra uma vez
    ticket: float | None = None  # se None, usa o ticket médio histórico da base

    def valor_por_comprador(self, ticket_base: float) -> float:
        return (self.ticket or ticket_base) * self.margem * self.compras_por_comprador


def curva(y: np.ndarray, t: np.ndarray, score: np.ndarray, n_base: int) -> np.ndarray:
    """Compradores incrementais na base inteira ao contatar o top-k% do score, para cada
    k em FRACOES. Dentro do top-k: (taxa tratados - taxa controle) × clientes contatados."""
    ordem = np.argsort(-score, kind="stable")
    y, t = y[ordem], t[ordem].astype(bool)
    cum_nt, cum_yt = np.cumsum(t), np.cumsum(y * t)
    cum_nc, cum_yc = np.cumsum(~t), np.cumsum(y * ~t)
    corte = np.maximum((FRACOES * len(y)).astype(int) - 1, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        efeito = cum_yt[corte] / cum_nt[corte] - cum_yc[corte] / cum_nc[corte]
    return efeito * FRACOES * n_base


def curvas_com_ic(
    teste: pd.DataFrame,
    scores: dict[str, np.ndarray],
    n_base: int,
    reps: int = 500,
    semente: int = 42,
) -> pd.DataFrame:
    """Curva pontual e IC 95% por bootstrap (reamostra clientes do teste dentro de cada braço)."""
    rng = np.random.default_rng(semente)
    y = teste["target"].to_numpy()
    t = teste["treatment_flg"].to_numpy()
    idx_t, idx_c = np.flatnonzero(t == 1), np.flatnonzero(t == 0)
    pontual = {nome: curva(y, t, s, n_base) for nome, s in scores.items()}
    boot = {nome: np.empty((reps, len(FRACOES))) for nome in scores}
    for b in range(reps):
        idx = np.r_[rng.choice(idx_t, len(idx_t)), rng.choice(idx_c, len(idx_c))]
        for nome, s in scores.items():
            boot[nome][b] = curva(y[idx], t[idx], s[idx], n_base)
    linhas = []
    for nome in scores:
        inf, sup = np.nanquantile(boot[nome], [0.025, 0.975], axis=0)
        for f, p, a, b in zip(FRACOES, pontual[nome], inf, sup, strict=True):
            linhas.append({"estrategia": nome, "fracao": f, "incrementais": p, "inf": a, "sup": b})
    return pd.DataFrame(linhas)


def financeiro(curvas: pd.DataFrame, n_base: int, valor: float, custo: float) -> pd.DataFrame:
    d = curvas.copy()
    d["contatos"] = d["fracao"] * n_base
    d["custo"] = d["contatos"] * custo
    d["receita_incremental"] = d["incrementais"] * valor
    d["lucro"] = d["receita_incremental"] - d["custo"]
    d["lucro_inf"] = d["inf"] * valor - d["custo"]
    d["lucro_sup"] = d["sup"] * valor - d["custo"]
    d["retorno_por_rublo"] = d["receita_incremental"] / d["custo"]
    return d


def grafico(curvas: pd.DataFrame, destino: Path, n_base: int) -> None:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    for nome in ("aleatório", "propensão", "uplift"):
        d = curvas[curvas.estrategia == nome]
        x = d["fracao"] * 100
        estilo = (0, (4, 3)) if nome == "aleatório" else "-"
        if nome != "aleatório":
            ax.fill_between(x, d["inf"], d["sup"], color=CORES[nome], alpha=0.14, lw=0)
        ax.plot(x, d["incrementais"], color=CORES[nome], lw=2, ls=estilo)
        i = len(d) // 4
        ax.annotate(
            nome,
            (x.iloc[i], d["incrementais"].iloc[i]),
            xytext=(4, 6),
            textcoords="offset points",
            color=TEXTO,
            fontsize=9,
        )
    ax.set_xlabel("% da base que recebe a campanha (orçamento)", color=TEXTO_2)
    ax.set_ylabel(f"compradores incrementais (base de {n_base:,})".replace(",", "."), color=TEXTO_2)
    ax.tick_params(colors=TEXTO_2, labelsize=9)
    ax.grid(color=GRADE, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    fig.suptitle(
        "Com o mesmo orçamento, mandar por uplift traz mais compradores",
        x=0.02,
        ha="left",
        color=TEXTO,
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.02,
        0.9,
        "Faixas: IC 95% por bootstrap no conjunto de teste. Tracejado: envio aleatório. "
        "100% = mandar para todos.",
        color=TEXTO_2,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def rodar(dados: Path, reports: Path, premissas: Premissas | None = None) -> dict:
    premissas = premissas or Premissas()
    scores = pd.read_parquet(dados / "scores_teste.parquet")
    perfil = pd.read_parquet(dados / "perfil_cliente.parquet", columns=["ticket_medio"])
    escolhido = (reports / "40_uplift" / "modelo_escolhido.txt").read_text().strip()
    n_base = len(perfil)
    ticket_base = float(perfil["ticket_medio"].mean())
    valor = premissas.valor_por_comprador(ticket_base)

    rng = np.random.default_rng(7)
    estrategias = {
        "aleatório": rng.random(len(scores)),
        "propensão": scores["propensão"].to_numpy(),
        "uplift": scores[escolhido].to_numpy(),
    }
    curvas = curvas_com_ic(scores, estrategias, n_base)
    # O aleatório tem valor esperado linear: fração × efeito médio. A ordem sorteada acima
    # serve só para a faixa de incerteza; o ponto central usa a reta.
    alea = curvas.estrategia == "aleatório"
    no_fim = curvas.loc[alea & (curvas.fracao == 1.0)].iloc[0]
    for col in ("incrementais", "inf", "sup"):
        curvas.loc[alea, col] = curvas.loc[alea, "fracao"] * float(no_fim[col])

    fin = financeiro(curvas, n_base, valor, premissas.custo_por_contato)
    destino = reports / "50_decisao"
    destino.mkdir(parents=True, exist_ok=True)
    curvas.to_csv(destino / "curvas.csv", index=False)
    fin.to_csv(destino / "financeiro.csv", index=False)
    meta = asdict(premissas) | {
        "ticket_base": ticket_base,
        "valor_por_comprador": valor,
        "n_base": n_base,
        "modelo_uplift": escolhido,
    }
    pd.Series(meta).to_json(destino / "premissas.json", force_ascii=False, indent=2)
    grafico(curvas, reports / "figuras" / "orcamento_vs_incrementais.png", n_base)

    r = resumo(fin, meta)
    (reports / "decisao.md").write_text(relatorio(fin, meta, r), encoding="utf-8")
    return r


def resumo(fin: pd.DataFrame, meta: dict) -> dict:
    up = fin[fin.estrategia == "uplift"]
    todos = up[up.fracao == 1.0].iloc[0]
    melhor = up.loc[up["lucro"].idxmax()]
    k30 = {
        e: fin[(fin.estrategia == e) & (fin.fracao == 0.3)].iloc[0]
        for e in ("aleatório", "propensão", "uplift")
    }
    # Menor fração que já entrega metade dos compradores incrementais de mandar para todos
    metade = up[up["incrementais"] >= todos["incrementais"] / 2]
    return {
        "todos": todos,
        "melhor": melhor,
        "k30": k30,
        "fracao_metade": float(metade["fracao"].min()),
        "valor_por_comprador": meta["valor_por_comprador"],
    }


def sensibilidade(fin: pd.DataFrame, meta: dict) -> pd.DataFrame:
    linhas = []
    base = fin[["estrategia", "fracao", "incrementais", "inf", "sup"]]
    for custo in (1.0, 3.0, 6.0, 10.0):
        for margem in (0.15, 0.20, 0.30):
            p = Premissas(custo_por_contato=custo, margem=margem)
            f = financeiro(base, meta["n_base"], p.valor_por_comprador(meta["ticket_base"]), custo)
            up = f[f.estrategia == "uplift"]
            best = up.loc[up["lucro"].idxmax()]
            linhas.append(
                {
                    "custo_por_contato": custo,
                    "margem": margem,
                    "melhor_fracao": best["fracao"],
                    "lucro_melhor": best["lucro"],
                    "lucro_mandar_para_todos": up[up.fracao == 1.0].iloc[0]["lucro"],
                }
            )
    return pd.DataFrame(linhas)


def relatorio(fin: pd.DataFrame, meta: dict, r: dict) -> str:
    t, m, k = r["todos"], r["melhor"], r["k30"]
    sens = sensibilidade(fin, meta)
    colunas = ["estrategia", "fracao", "incrementais", "inf", "sup", "custo", "lucro"]
    tab = fin[fin.fracao.isin([0.1, 0.2, 0.3, 0.5, 0.7, 1.0])][colunas].sort_values(
        ["fracao", "estrategia"]
    )
    return f"""# Da métrica para a decisão

Gerado por `campanha decisao`. Curvas estimadas no conjunto de teste e escaladas para a
base do experimento ({meta["n_base"]:,} clientes). Modelo de uplift: `{meta["modelo_uplift"]}`.

## Premissas (em rublos)

| premissa | valor | de onde vem |
|---|---:|---|
| custo por contato | {meta["custo_por_contato"]:.2f} | SMS em massa, sem cupom (ajustável no simulador) |
| ticket médio | {meta["ticket_base"]:.0f} | média de `ticket_medio` no perfil, antes do corte |
| margem bruta | {meta["margem"]:.0%} | típica de varejo alimentar |
| compras por comprador incremental | {meta["compras_por_comprador"]:.0f} | conservador: o desfecho só diz se comprou |
| **valor de um comprador incremental** | **{meta["valor_por_comprador"]:.1f}** | ticket × margem × compras |

## Resultado

- **Mandar para todos:** {t["incrementais"]:,.0f} compradores a mais
  (IC [{t["inf"]:,.0f}; {t["sup"]:,.0f}]), custo de {t["custo"]:,.0f} e lucro incremental
  de {t["lucro"]:,.0f}.
- **Metade do resultado com uma fração do custo:** mandando por uplift, {r["fracao_metade"]:.0%}
  da base já trazem metade dos compradores incrementais de mandar para todos.
- **Com 30% do orçamento:** uplift traz {k["uplift"]["incrementais"]:,.0f}
  (IC [{k["uplift"]["inf"]:,.0f}; {k["uplift"]["sup"]:,.0f}]), propensão
  {k["propensão"]["incrementais"]:,.0f} e aleatório {k["aleatório"]["incrementais"]:,.0f}.
- **Melhor ponto com estas premissas:** mandar por uplift para {m["fracao"]:.0%} da base,
  lucro de {m["lucro"]:,.0f} (IC [{m["lucro_inf"]:,.0f}; {m["lucro_sup"]:,.0f}]) contra
  {t["lucro"]:,.0f} mandando para todos.

![orçamento contra compradores incrementais](figuras/orcamento_vs_incrementais.png)

## Tabela por orçamento

{run_sql.tabela_md(tab, casas=2)}

## Sensibilidade às premissas

Melhor fração da base para mandar por uplift e lucro, variando custo por contato e margem:

{run_sql.tabela_md(sens, casas=2)}
"""
