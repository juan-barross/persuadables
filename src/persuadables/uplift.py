from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.model_selection import train_test_split
from sklift.metrics import qini_auc_score, qini_curve, uplift_at_k, uplift_auc_score
from sklift.models import ClassTransformation, SoloModel, TwoModels

from persuadables import graficos, relatorio, stats

SEMENTE = 42
EM_PP = 100
COLUNAS_FORA_DO_MODELO = ("client_id", "treatment_flg", "target")
TOPO_AVALIADO = 0.3
GRUPO_COMPARADO = 0.2
DECIS = 10

CORES = {
    "propensão": graficos.AZUL,
    "S-learner": graficos.LARANJA,
    "T-learner": graficos.VERDE_AGUA,
    "X-learner": graficos.AMARELO,
    "class transformation": graficos.MAGENTA,
}

VARIAVEIS_DO_PERFIL = [
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


def hiperparametros() -> dict:
    return {
        "n_estimators": 300,
        "learning_rate": 0.03,
        "num_leaves": 31,
        "min_child_samples": 200,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "random_state": SEMENTE,
        "verbose": -1,
    }


class Propensao:
    def __init__(self) -> None:
        self.modelo = LGBMClassifier(**hiperparametros())

    def fit(self, x: pd.DataFrame, comprou: pd.Series, tratado: pd.Series) -> Propensao:
        self.modelo.fit(x, comprou)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.modelo.predict_proba(x)[:, 1]


class XLearner:
    def __init__(self) -> None:
        self.compra_sem_campanha = LGBMClassifier(**hiperparametros())
        self.compra_com_campanha = LGBMClassifier(**hiperparametros())
        self.efeito_estimado_no_controle = LGBMRegressor(**hiperparametros())
        self.efeito_estimado_nos_tratados = LGBMRegressor(**hiperparametros())

    def fit(self, x: pd.DataFrame, comprou: pd.Series, tratado: pd.Series) -> XLearner:
        tratado = np.asarray(tratado).astype(bool)
        comprou = np.asarray(comprou)
        x_t, x_c = x[tratado], x[~tratado]
        self.compra_sem_campanha.fit(x_c, comprou[~tratado])
        self.compra_com_campanha.fit(x_t, comprou[tratado])
        efeito_nos_tratados = comprou[tratado] - self.compra_sem_campanha.predict_proba(x_t)[:, 1]
        efeito_no_controle = self.compra_com_campanha.predict_proba(x_c)[:, 1] - comprou[~tratado]
        self.efeito_estimado_nos_tratados.fit(x_t, efeito_nos_tratados)
        self.efeito_estimado_no_controle.fit(x_c, efeito_no_controle)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        no_controle = self.efeito_estimado_no_controle.predict(x)
        nos_tratados = self.efeito_estimado_nos_tratados.predict(x)
        return 0.5 * no_controle + 0.5 * nos_tratados


def modelos() -> dict:
    return {
        "propensão": Propensao(),
        "S-learner": SoloModel(LGBMClassifier(**hiperparametros())),
        "T-learner": TwoModels(
            LGBMClassifier(**hiperparametros()),
            LGBMClassifier(**hiperparametros()),
            method="vanilla",
        ),
        "X-learner": XLearner(),
        "class transformation": ClassTransformation(LGBMClassifier(**hiperparametros())),
    }


@dataclass
class Divisao:
    treino: pd.DataFrame
    validacao: pd.DataFrame
    teste: pd.DataFrame


@dataclass
class ResultadoUplift:
    escolhido: str
    metricas: pd.DataFrame
    divisao: Divisao

    @property
    def metricas_no_teste(self) -> pd.DataFrame:
        no_teste = self.metricas[self.metricas["conjunto"] == "teste"].drop(columns="conjunto")
        return no_teste.sort_values("auuc", ascending=False).set_index("modelo")


def dividir(perfil: pd.DataFrame) -> Divisao:
    estrato = perfil["treatment_flg"] * 2 + perfil["target"]
    treino, resto = train_test_split(perfil, test_size=0.4, stratify=estrato, random_state=SEMENTE)
    validacao, teste = train_test_split(
        resto, test_size=0.5, stratify=estrato.loc[resto.index], random_state=SEMENTE
    )
    return Divisao(treino, validacao, teste.reset_index(drop=True))


def variaveis_do_modelo(perfil: pd.DataFrame) -> list[str]:
    return [coluna for coluna in perfil.columns if coluna not in COLUNAS_FORA_DO_MODELO]


def rodar(perfil: pd.DataFrame, reports: Path, dados: Path) -> ResultadoUplift:
    divisao = dividir(perfil)
    scores_validacao, scores_teste = treinar_e_pontuar(divisao, variaveis_do_modelo(perfil))
    metricas = tabela_de_metricas(divisao, scores_validacao, scores_teste)
    resultado = ResultadoUplift(melhor_na_validacao(metricas), metricas, divisao)
    escolhido, teste = resultado.escolhido, divisao.teste

    salvar_scores(teste, scores_teste, dados / "scores_teste.parquet")
    influenciados = quem_e_influenciado(teste, scores_teste[escolhido])
    por_decil = {
        nome: uplift_por_decil(teste, scores_teste[nome]) for nome in (escolhido, "propensão")
    }

    destino = reports / "40_uplift"
    relatorio.salvar_csv(metricas, destino / "metricas.csv")
    relatorio.salvar_csv(influenciados, destino / "quem_e_influenciado.csv")
    for nome, decis in por_decil.items():
        relatorio.salvar_csv(decis, destino / f"uplift_por_decil_{nome.replace(' ', '_')}.csv")
    (destino / "modelo_escolhido.txt").write_text(escolhido + "\n", encoding="utf-8")

    curvas = {nome: curva_qini(teste, score) for nome, score in scores_teste.items()}
    grafico_qini(curvas, len(teste), reports / "figuras" / "curva_qini.png")
    texto = texto_do_relatorio(resultado, influenciados, por_decil)
    (reports / "uplift.md").write_text(texto, encoding="utf-8")
    return resultado


def treinar_e_pontuar(divisao: Divisao, variaveis: list[str]) -> tuple[dict, dict]:
    scores_validacao, scores_teste = {}, {}
    treino = divisao.treino
    for nome, modelo in modelos().items():
        modelo.fit(treino[variaveis], treino["target"], treino["treatment_flg"])
        scores_validacao[nome] = modelo.predict(divisao.validacao[variaveis])
        scores_teste[nome] = modelo.predict(divisao.teste[variaveis])
    return scores_validacao, scores_teste


def tabela_de_metricas(
    divisao: Divisao, scores_validacao: dict, scores_teste: dict
) -> pd.DataFrame:
    linhas = []
    for nome in scores_teste:
        for conjunto, dados, scores in (
            ("validação", divisao.validacao, scores_validacao),
            ("teste", divisao.teste, scores_teste),
        ):
            linhas.append({"modelo": nome, "conjunto": conjunto} | avaliar(dados, scores[nome]))
    return pd.DataFrame(linhas)


def melhor_na_validacao(metricas: pd.DataFrame) -> str:
    validacao = metricas[metricas["conjunto"] == "validação"]
    candidatos = validacao[validacao["modelo"] != "propensão"]
    return candidatos.sort_values("auuc", ascending=False).iloc[0]["modelo"]


def avaliar(dados: pd.DataFrame, score: np.ndarray) -> dict:
    comprou, tratado = dados["target"].to_numpy(), dados["treatment_flg"].to_numpy()
    clientes, incrementais = qini_curve(comprou, score, tratado)
    no_topo = np.interp(TOPO_AVALIADO * len(comprou), clientes, incrementais)
    no_total = incrementais[-1]
    return {
        "auuc": uplift_auc_score(comprou, score, tratado),
        "qini_auc": qini_auc_score(comprou, score, tratado),
        "uplift_top10_pp": _uplift_no_topo(comprou, score, tratado, 0.1),
        "uplift_top30_pp": _uplift_no_topo(comprou, score, tratado, TOPO_AVALIADO),
        "captura_top30": no_topo / no_total if no_total else np.nan,
    }


def _uplift_no_topo(comprou, score, tratado, fracao: float) -> float:
    return uplift_at_k(comprou, score, tratado, strategy="overall", k=fracao) * EM_PP


def curva_qini(dados: pd.DataFrame, score: np.ndarray, pontos: int = 101) -> tuple:
    comprou, tratado = dados["target"].to_numpy(), dados["treatment_flg"].to_numpy()
    clientes, incrementais = qini_curve(comprou, score, tratado)
    fracoes = np.linspace(0, 1, pontos)
    return fracoes, np.interp(fracoes * len(dados), np.r_[0, clientes], np.r_[0, incrementais])


def salvar_scores(teste: pd.DataFrame, scores: dict, caminho: Path) -> None:
    pontuado = teste[["client_id", "treatment_flg", "target"]].assign(**scores)
    pontuado.to_parquet(caminho, index=False)


def uplift_por_decil(teste: pd.DataFrame, score: np.ndarray) -> pd.DataFrame:
    posto = pd.Series(-score).rank(method="first")
    decil = pd.qcut(posto, DECIS, labels=range(1, DECIS + 1)).astype(int).to_numpy()
    linhas = []
    for numero, clientes in teste[["treatment_flg", "target"]].groupby(decil):
        efeito = _efeito_observado(clientes)
        linhas.append(
            {
                "faixa": numero,
                "n": len(clientes),
                "taxa_t": clientes.loc[clientes["treatment_flg"] == 1, "target"].mean(),
                "taxa_c": clientes.loc[clientes["treatment_flg"] == 0, "target"].mean(),
                "uplift_pp": efeito.diferenca * EM_PP,
                "ic_inf_pp": efeito.ic_inf * EM_PP,
                "ic_sup_pp": efeito.ic_sup * EM_PP,
            }
        )
    return pd.DataFrame(linhas)


def quem_e_influenciado(teste: pd.DataFrame, score: np.ndarray) -> pd.DataFrame:
    ordem = np.argsort(-score)
    tamanho = int(len(score) * GRUPO_COMPARADO)
    grupos = {
        "20% maior uplift": teste.iloc[ordem[:tamanho]],
        "20% menor uplift": teste.iloc[ordem[-tamanho:]],
        "todos": teste,
    }
    linhas = []
    for nome, clientes in grupos.items():
        efeito = _efeito_observado(clientes)
        linhas.append(
            {
                "grupo": nome,
                "n": len(clientes),
                "taxa_controle": clientes.loc[clientes["treatment_flg"] == 0, "target"].mean(),
                "uplift_observado_pp": efeito.diferenca * EM_PP,
                "ic_inf_pp": efeito.ic_inf * EM_PP,
                "ic_sup_pp": efeito.ic_sup * EM_PP,
            }
            | clientes[VARIAVEIS_DO_PERFIL].median().to_dict()
        )
    return pd.DataFrame(linhas)


def _efeito_observado(clientes: pd.DataFrame) -> stats.Efeito:
    tratados = clientes[clientes["treatment_flg"] == 1]
    controle = clientes[clientes["treatment_flg"] == 0]
    return stats.diferenca_proporcoes(
        tratados["target"].sum(), len(tratados), controle["target"].sum(), len(controle)
    )


def grafico_qini(curvas: dict, n_teste: int, destino: Path) -> None:
    fig = graficos.nova_figura(8, 5.2)
    ax = fig.subplots()
    graficos.estilizar(ax)
    total = next(iter(curvas.values()))[1][-1]
    ax.plot([0, 100], [0, total], color=graficos.TEXTO_SECUNDARIO, lw=1.2, ls=graficos.TRACEJADO)
    ax.annotate(
        "envio aleatório",
        xy=(30, total * 0.30),
        xytext=(36, total * 0.12),
        color=graficos.TEXTO_SECUNDARIO,
        fontsize=8.5,
        arrowprops={"arrowstyle": "-", "color": graficos.TEXTO_SECUNDARIO, "lw": 0.8},
    )
    for nome, (fracoes, incrementais) in curvas.items():
        ax.plot(fracoes * 100, incrementais, color=CORES[nome], lw=2, label=nome)
    graficos.rotular_eixos(
        ax,
        "% dos clientes que recebem a campanha (ordenados pelo modelo)",
        "compradores incrementais (conjunto de teste)",
    )
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    legenda = ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=graficos.TEXTO)
    legenda.set_title("modelo", prop={"size": 9})
    graficos.titular(
        fig,
        "Modelos de uplift acham os compradores incrementais; propensão não",
        f"Curva Qini no conjunto de teste ({n_teste:,} clientes)".replace(",", "."),
    )
    graficos.salvar(fig, destino)


def texto_do_relatorio(
    resultado: ResultadoUplift, influenciados: pd.DataFrame, por_decil: dict[str, pd.DataFrame]
) -> str:
    no_teste = resultado.metricas_no_teste
    escolhido = resultado.escolhido
    teste = resultado.divisao.teste
    grupos = influenciados.set_index("grupo")
    return relatorio.preencher(
        "uplift",
        semente=SEMENTE,
        n_treino=len(resultado.divisao.treino),
        n_validacao=len(resultado.divisao.validacao),
        n_teste=len(teste),
        escolhido=escolhido,
        tabela_metricas=relatorio.tabela(no_teste.reset_index(), casas=4),
        efeito_medio_pp=_efeito_observado(teste).diferenca * EM_PP,
        top30_escolhido_pp=no_teste.loc[escolhido, "uplift_top30_pp"],
        top30_propensao_pp=no_teste.loc["propensão", "uplift_top30_pp"],
        linhas_por_decil=_linhas_por_decil(por_decil[escolhido], por_decil["propensão"]),
        tabela_influenciados=relatorio.tabela(influenciados, casas=2),
        topo=grupos.loc["20% maior uplift"],
        base=grupos.loc["20% menor uplift"],
    )


def _linhas_por_decil(do_escolhido: pd.DataFrame, da_propensao: pd.DataFrame) -> str:
    return "\n".join(
        f"| {a.faixa} | {a.uplift_pp:+.1f} [{a.ic_inf_pp:.1f}; {a.ic_sup_pp:.1f}] | "
        f"{b.uplift_pp:+.1f} [{b.ic_inf_pp:.1f}; {b.ic_sup_pp:.1f}] | {b.taxa_c:.0%} |"
        for a, b in zip(do_escolhido.itertuples(), da_propensao.itertuples(), strict=True)
    )
