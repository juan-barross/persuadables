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
TOPO_AVALIADO = 0.3
GRUPO_COMPARADO = 0.2
DECIS = 10
FORA_DO_MODELO = ("client_id", "treatment_flg", "target")
VARIAVEIS_DO_PERFIL = (
    "gasto_total ticket_medio n_transacoes dias_desde_ultima gasto_30d intervalo_medio_dias "
    "ja_resgatou prop_transacoes_com_resgate lojas_distintas idade"
).split()
HIPERPARAMETROS = {
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
CORES = {
    "propensão": graficos.AZUL,
    "S-learner": graficos.LARANJA,
    "T-learner": graficos.VERDE_AGUA,
    "X-learner": graficos.AMARELO,
    "class transformation": graficos.MAGENTA,
}


def classificador() -> LGBMClassifier:
    return LGBMClassifier(**HIPERPARAMETROS)


class Propensao:
    def __init__(self) -> None:
        self.modelo = classificador()

    def fit(self, x: pd.DataFrame, comprou: pd.Series, tratado: pd.Series) -> Propensao:
        self.modelo.fit(x, comprou)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.modelo.predict_proba(x)[:, 1]


class XLearner:
    def __init__(self) -> None:
        self.compra_sem_campanha, self.compra_com_campanha = classificador(), classificador()
        self.efeito_no_controle = LGBMRegressor(**HIPERPARAMETROS)
        self.efeito_nos_tratados = LGBMRegressor(**HIPERPARAMETROS)

    def fit(self, x: pd.DataFrame, comprou: pd.Series, tratado: pd.Series) -> XLearner:
        tratado, comprou = np.asarray(tratado).astype(bool), np.asarray(comprou)
        x_t, x_c, y_t, y_c = x[tratado], x[~tratado], comprou[tratado], comprou[~tratado]
        self.compra_sem_campanha.fit(x_c, y_c)
        self.compra_com_campanha.fit(x_t, y_t)
        self.efeito_nos_tratados.fit(x_t, y_t - self.compra_sem_campanha.predict_proba(x_t)[:, 1])
        self.efeito_no_controle.fit(x_c, self.compra_com_campanha.predict_proba(x_c)[:, 1] - y_c)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return 0.5 * self.efeito_no_controle.predict(x) + 0.5 * self.efeito_nos_tratados.predict(x)


def modelos() -> dict:
    return {
        "propensão": Propensao(),
        "S-learner": SoloModel(classificador()),
        "T-learner": TwoModels(classificador(), classificador(), method="vanilla"),
        "X-learner": XLearner(),
        "class transformation": ClassTransformation(classificador()),
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


def rodar(perfil: pd.DataFrame, reports: Path, dados: Path) -> ResultadoUplift:
    divisao = dividir(perfil)
    conjuntos = {"validação": divisao.validacao, "teste": divisao.teste}
    variaveis = [coluna for coluna in perfil.columns if coluna not in FORA_DO_MODELO]
    scores = {conjunto: {} for conjunto in conjuntos}
    for nome, modelo in modelos().items():
        modelo.fit(
            divisao.treino[variaveis], divisao.treino["target"], divisao.treino["treatment_flg"]
        )
        for conjunto, dados_do_conjunto in conjuntos.items():
            scores[conjunto][nome] = modelo.predict(dados_do_conjunto[variaveis])

    metricas = pd.DataFrame(
        {"modelo": nome, "conjunto": conjunto}
        | avaliar(conjuntos[conjunto], scores[conjunto][nome])
        for nome in scores["teste"]
        for conjunto in conjuntos
    )
    resultado = ResultadoUplift(melhor_na_validacao(metricas), metricas, divisao)
    salvar(resultado, scores["teste"], reports, dados)
    return resultado


def melhor_na_validacao(metricas: pd.DataFrame) -> str:
    validacao = metricas[
        (metricas["conjunto"] == "validação") & (metricas["modelo"] != "propensão")
    ]
    return validacao.sort_values("auuc", ascending=False).iloc[0]["modelo"]


def avaliar(dados: pd.DataFrame, score: np.ndarray) -> dict:
    comprou, tratado = dados["target"].to_numpy(), dados["treatment_flg"].to_numpy()
    clientes, incrementais = qini_curve(comprou, score, tratado)
    no_topo = np.interp(TOPO_AVALIADO * len(comprou), clientes, incrementais)

    def uplift_no_topo(fracao: float) -> float:
        return uplift_at_k(comprou, score, tratado, strategy="overall", k=fracao) * EM_PP

    return {
        "auuc": uplift_auc_score(comprou, score, tratado),
        "qini_auc": qini_auc_score(comprou, score, tratado),
        "uplift_top10_pp": uplift_no_topo(0.1),
        "uplift_top30_pp": uplift_no_topo(TOPO_AVALIADO),
        "captura_top30": no_topo / incrementais[-1] if incrementais[-1] else np.nan,
    }


def efeito_observado(clientes: pd.DataFrame) -> dict:
    tratados = clientes.loc[clientes["treatment_flg"] == 1, "target"]
    controle = clientes.loc[clientes["treatment_flg"] == 0, "target"]
    efeito = stats.diferenca_proporcoes(
        tratados.sum(), len(tratados), controle.sum(), len(controle)
    )
    return {
        "n": len(clientes),
        "taxa_t": tratados.mean(),
        "taxa_c": controle.mean(),
        "uplift_pp": efeito.diferenca * EM_PP,
        "ic_inf_pp": efeito.ic_inf * EM_PP,
        "ic_sup_pp": efeito.ic_sup * EM_PP,
    }


def uplift_por_decil(teste: pd.DataFrame, score: np.ndarray) -> pd.DataFrame:
    posto = pd.Series(-score).rank(method="first")
    decil = pd.qcut(posto, DECIS, labels=range(1, DECIS + 1)).astype(int).to_numpy()
    return pd.DataFrame(
        {"faixa": numero} | efeito_observado(clientes) for numero, clientes in teste.groupby(decil)
    )


def quem_e_influenciado(teste: pd.DataFrame, score: np.ndarray) -> pd.DataFrame:
    ordem = np.argsort(-score)
    tamanho = int(len(score) * GRUPO_COMPARADO)
    grupos = {
        "20% maior uplift": teste.iloc[ordem[:tamanho]],
        "20% menor uplift": teste.iloc[ordem[-tamanho:]],
        "todos": teste,
    }
    return pd.DataFrame(
        {"grupo": nome}
        | efeito_observado(clientes)
        | clientes[VARIAVEIS_DO_PERFIL].median().to_dict()
        for nome, clientes in grupos.items()
    )


def salvar(resultado: ResultadoUplift, scores: dict, reports: Path, dados: Path) -> None:
    teste, escolhido = resultado.divisao.teste, resultado.escolhido
    teste[["client_id", "treatment_flg", "target"]].assign(**scores).to_parquet(
        dados / "scores_teste.parquet", index=False
    )
    influenciados = quem_e_influenciado(teste, scores[escolhido])
    por_decil = {nome: uplift_por_decil(teste, scores[nome]) for nome in (escolhido, "propensão")}

    destino = reports / "40_uplift"
    relatorio.salvar_csv(resultado.metricas, destino / "metricas.csv")
    relatorio.salvar_csv(influenciados, destino / "quem_e_influenciado.csv")
    for nome, decis in por_decil.items():
        relatorio.salvar_csv(decis, destino / f"uplift_por_decil_{nome.replace(' ', '_')}.csv")
    (destino / "modelo_escolhido.txt").write_text(escolhido + "\n", encoding="utf-8")

    grafico_qini(teste, scores, reports / "figuras" / "curva_qini.png")
    grupos = influenciados.set_index("grupo")
    no_teste = resultado.metricas_no_teste
    texto = relatorio.preencher(
        "uplift",
        semente=SEMENTE,
        n_treino=len(resultado.divisao.treino),
        n_validacao=len(resultado.divisao.validacao),
        n_teste=len(teste),
        escolhido=escolhido,
        tabela_metricas=relatorio.tabela(no_teste.reset_index(), casas=4),
        efeito_medio_pp=efeito_observado(teste)["uplift_pp"],
        top30_escolhido_pp=no_teste.loc[escolhido, "uplift_top30_pp"],
        top30_propensao_pp=no_teste.loc["propensão", "uplift_top30_pp"],
        linhas_por_decil=linhas_por_decil(por_decil[escolhido], por_decil["propensão"]),
        tabela_influenciados=relatorio.tabela(influenciados, casas=2),
        topo=grupos.loc["20% maior uplift"],
        base=grupos.loc["20% menor uplift"],
    )
    (reports / "uplift.md").write_text(texto, encoding="utf-8")


def linhas_por_decil(do_escolhido: pd.DataFrame, da_propensao: pd.DataFrame) -> str:
    return "\n".join(
        f"| {a.faixa} | {a.uplift_pp:+.1f} [{a.ic_inf_pp:.1f}; {a.ic_sup_pp:.1f}] | "
        f"{b.uplift_pp:+.1f} [{b.ic_inf_pp:.1f}; {b.ic_sup_pp:.1f}] | {b.taxa_c:.0%} |"
        for a, b in zip(do_escolhido.itertuples(), da_propensao.itertuples(), strict=True)
    )


def curva_qini(dados: pd.DataFrame, score: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    comprou, tratado = dados["target"].to_numpy(), dados["treatment_flg"].to_numpy()
    clientes, incrementais = qini_curve(comprou, score, tratado)
    fracoes = np.linspace(0, 1, 101)
    return fracoes, np.interp(fracoes * len(dados), np.r_[0, clientes], np.r_[0, incrementais])


def grafico_qini(teste: pd.DataFrame, scores: dict, destino: Path) -> None:
    fig = graficos.nova_figura(8, 5.2)
    ax = fig.subplots()
    graficos.estilizar(ax)
    curvas = {nome: curva_qini(teste, score) for nome, score in scores.items()}
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
    ax.legend(frameon=False, fontsize=9, loc="lower right", title="modelo", title_fontsize=9)
    graficos.titular(
        fig,
        "Modelos de uplift acham os compradores incrementais; propensão não",
        f"Curva Qini no conjunto de teste ({len(teste):,} clientes)".replace(",", "."),
    )
    graficos.salvar(fig, destino)
