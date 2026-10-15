from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as st

ALPHA = 0.05


@dataclass(frozen=True)
class Efeito:
    diferenca: float
    erro_padrao: float
    ic_inf: float
    ic_sup: float
    p_valor: float

    @property
    def largura(self) -> float:
        return self.ic_sup - self.ic_inf


@dataclass(frozen=True)
class Cuped:
    theta: float
    correlacao: float
    efeito_bruto: Efeito
    efeito_ajustado: Efeito

    @property
    def reducao_variancia(self) -> float:
        return 1 - (self.efeito_ajustado.erro_padrao / self.efeito_bruto.erro_padrao) ** 2

    @property
    def reducao_largura_ic(self) -> float:
        return 1 - self.efeito_ajustado.largura / self.efeito_bruto.largura


def z_critico(alpha: float = ALPHA) -> float:
    return float(st.norm.ppf(1 - alpha / 2))


def efeito_de(diferenca: float, erro_padrao: float, alpha: float = ALPHA) -> Efeito:
    z = z_critico(alpha)
    p_valor = 2 * st.norm.sf(abs(diferenca / erro_padrao)) if erro_padrao > 0 else float("nan")
    return Efeito(
        diferenca=diferenca,
        erro_padrao=erro_padrao,
        ic_inf=diferenca - z * erro_padrao,
        ic_sup=diferenca + z * erro_padrao,
        p_valor=float(p_valor),
    )


def srm(n_tratamento: int, n_controle: int, prop_esperada: float = 0.5) -> tuple[float, float]:
    n = n_tratamento + n_controle
    esperado = [n * prop_esperada, n * (1 - prop_esperada)]
    qui2, p_valor = st.chisquare([n_tratamento, n_controle], esperado)
    return float(qui2), float(p_valor)


def diferenca_proporcoes(
    compras_t: int, n_t: int, compras_c: int, n_c: int, alpha: float = ALPHA
) -> Efeito:
    taxa_t, taxa_c = compras_t / n_t, compras_c / n_c
    erro_padrao = np.sqrt(taxa_t * (1 - taxa_t) / n_t + taxa_c * (1 - taxa_c) / n_c)
    return efeito_de(taxa_t - taxa_c, float(erro_padrao), alpha)


def diferenca_medias(y: np.ndarray, tratado: np.ndarray, alpha: float = ALPHA) -> Efeito:
    y = np.asarray(y, float)
    tratado = np.asarray(tratado).astype(bool)
    y_t, y_c = y[tratado], y[~tratado]
    erro_padrao = np.sqrt(y_t.var(ddof=1) / len(y_t) + y_c.var(ddof=1) / len(y_c))
    return efeito_de(float(y_t.mean() - y_c.mean()), float(erro_padrao), alpha)


def bootstrap_diferenca(
    y: np.ndarray, tratado: np.ndarray, reps: int = 2000, alpha: float = ALPHA, semente: int = 42
) -> tuple[float, float]:
    y = np.asarray(y, float)
    tratado = np.asarray(tratado).astype(bool)
    rng = np.random.default_rng(semente)
    diferencas = _medias_reamostradas(y[tratado], reps, rng) - _medias_reamostradas(
        y[~tratado], reps, rng
    )
    return float(np.quantile(diferencas, alpha / 2)), float(np.quantile(diferencas, 1 - alpha / 2))


def _medias_reamostradas(y: np.ndarray, reps: int, rng: np.random.Generator) -> np.ndarray:
    if np.isin(y, (0.0, 1.0)).all():
        return rng.binomial(len(y), y.mean(), reps) / len(y)
    return np.array([rng.choice(y, len(y)).mean() for _ in range(reps)])


def cuped(y: np.ndarray, x: np.ndarray, tratado: np.ndarray, alpha: float = ALPHA) -> Cuped:
    y, x = np.asarray(y, float), np.asarray(x, float)
    theta = float(np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1))
    y_ajustado = y - theta * (x - x.mean())
    return Cuped(
        theta=theta,
        correlacao=float(np.corrcoef(y, x)[0, 1]),
        efeito_bruto=diferenca_medias(y, tratado, alpha),
        efeito_ajustado=diferenca_medias(y_ajustado, tratado, alpha),
    )


def efeito_minimo_detectavel(
    taxa_base: float, n_t: int, n_c: int, alpha: float = ALPHA, poder: float = 0.8
) -> float:
    z = z_critico(alpha) + st.norm.ppf(poder)
    return float(z * np.sqrt(taxa_base * (1 - taxa_base) * (1 / n_t + 1 / n_c)))


def benjamini_hochberg(p_valores: np.ndarray) -> np.ndarray:
    p = np.asarray(p_valores, float)
    n = len(p)
    ordem = np.argsort(p)
    ajustado = p[ordem] * n / np.arange(1, n + 1)
    ajustado = np.minimum.accumulate(ajustado[::-1])[::-1]
    q_valores = np.empty(n)
    q_valores[ordem] = np.minimum(ajustado, 1.0)
    return q_valores
