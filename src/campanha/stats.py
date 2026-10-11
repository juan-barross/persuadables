"""Estatística do placar: sorteio, efeito com IC, bootstrap, CUPED, poder e BH.

Funções puras sobre contagens ou arrays, para serem testadas contra statsmodels/scipy.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as st


@dataclass(frozen=True)
class Efeito:
    diferenca: float  # tratamento - controle, em proporção (0,01 = 1 p.p.)
    erro_padrao: float
    ic_inf: float
    ic_sup: float
    p_valor: float

    @property
    def largura(self) -> float:
        return self.ic_sup - self.ic_inf


def z_critico(alpha: float = 0.05) -> float:
    return float(st.norm.ppf(1 - alpha / 2))


def srm(n_tratamento: int, n_controle: int, prop_esperada: float = 0.5) -> tuple[float, float]:
    """Qui-quadrado do sorteio (Sample Ratio Mismatch). Devolve (estatística, p)."""
    n = n_tratamento + n_controle
    esperado = [n * prop_esperada, n * (1 - prop_esperada)]
    qui2, p = st.chisquare([n_tratamento, n_controle], esperado)
    return float(qui2), float(p)


def diferenca_proporcoes(x_t: int, n_t: int, x_c: int, n_c: int, alpha: float = 0.05) -> Efeito:
    """Diferença de proporções com IC de Wald (variâncias separadas) e teste z."""
    p_t, p_c = x_t / n_t, x_c / n_c
    ep = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    return _efeito(p_t - p_c, float(ep), alpha)


def diferenca_medias(y: np.ndarray, t: np.ndarray, alpha: float = 0.05) -> Efeito:
    """Diferença de médias com variâncias separadas; serve para o desfecho ajustado do CUPED."""
    y, t = np.asarray(y, float), np.asarray(t).astype(bool)
    a, b = y[t], y[~t]
    ep = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return _efeito(float(a.mean() - b.mean()), float(ep), alpha)


def _efeito(dif: float, ep: float, alpha: float) -> Efeito:
    z = z_critico(alpha)
    p = 2 * st.norm.sf(abs(dif / ep)) if ep > 0 else float("nan")
    return Efeito(dif, ep, dif - z * ep, dif + z * ep, float(p))


def bootstrap_diferenca(
    y: np.ndarray, t: np.ndarray, reps: int = 2000, alpha: float = 0.05, semente: int = 42
) -> tuple[float, float]:
    """IC percentil por bootstrap, reamostrando cada braço separadamente.

    Para desfecho binário basta sortear o número de compras de uma binomial com a taxa
    observada, o que equivale a reamostrar as linhas e é muito mais rápido.
    """
    y, t = np.asarray(y, float), np.asarray(t).astype(bool)
    rng = np.random.default_rng(semente)
    a, b = y[t], y[~t]
    if set(np.unique(y)) <= {0.0, 1.0}:
        da = rng.binomial(len(a), a.mean(), reps) / len(a)
        db = rng.binomial(len(b), b.mean(), reps) / len(b)
    else:
        da = np.array([rng.choice(a, len(a)).mean() for _ in range(reps)])
        db = np.array([rng.choice(b, len(b)).mean() for _ in range(reps)])
    dif = da - db
    return float(np.quantile(dif, alpha / 2)), float(np.quantile(dif, 1 - alpha / 2))


@dataclass(frozen=True)
class Cuped:
    theta: float
    correlacao: float
    efeito_bruto: Efeito
    efeito_ajustado: Efeito

    @property
    def reducao_variancia(self) -> float:
        """1 - Var(ajustado)/Var(bruto) do estimador; em teoria igual a ρ²."""
        return 1 - (self.efeito_ajustado.erro_padrao / self.efeito_bruto.erro_padrao) ** 2

    @property
    def reducao_largura_ic(self) -> float:
        return 1 - self.efeito_ajustado.largura / self.efeito_bruto.largura


def cuped(y: np.ndarray, x: np.ndarray, t: np.ndarray, alpha: float = 0.05) -> Cuped:
    """CUPED com uma covariável pré-período.

    y_ajustado = y - θ (x - média(x)), com θ = cov(y, x) / var(x) estimado juntando os
    dois braços. Como x é anterior ao sorteio, a média de x é igual nos braços em
    expectativa e o efeito continua não viesado; só a variância cai, por um fator ρ².
    """
    y, x = np.asarray(y, float), np.asarray(x, float)
    theta = float(np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1))
    ajustado = y - theta * (x - x.mean())
    return Cuped(
        theta=theta,
        correlacao=float(np.corrcoef(y, x)[0, 1]),
        efeito_bruto=diferenca_medias(y, t, alpha),
        efeito_ajustado=diferenca_medias(ajustado, t, alpha),
    )


def efeito_minimo_detectavel(
    p_base: float, n_t: int, n_c: int, alpha: float = 0.05, poder: float = 0.8
) -> float:
    """Menor diferença absoluta detectável (MDE) para duas proporções, teste bicaudal."""
    z = z_critico(alpha) + st.norm.ppf(poder)
    return float(z * np.sqrt(p_base * (1 - p_base) * (1 / n_t + 1 / n_c)))


def benjamini_hochberg(p_valores: np.ndarray) -> np.ndarray:
    """q-valores de Benjamini-Hochberg (controle da taxa de falsas descobertas)."""
    p = np.asarray(p_valores, float)
    n = len(p)
    ordem = np.argsort(p)
    ajustado = p[ordem] * n / np.arange(1, n + 1)
    ajustado = np.minimum.accumulate(ajustado[::-1])[::-1]
    q = np.empty(n)
    q[ordem] = np.minimum(ajustado, 1.0)
    return q
