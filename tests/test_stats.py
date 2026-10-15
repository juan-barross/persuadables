from __future__ import annotations

import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from persuadables import stats


def test_srm_sem_desvio_tem_p_alto() -> None:
    _, p = stats.srm(50_000, 50_000)
    assert p == pytest.approx(1.0)


def test_srm_detecta_sorteio_torto() -> None:
    _, p = stats.srm(50_600, 49_400)
    assert p < 0.001


def test_diferenca_proporcoes_bate_com_a_conta_na_mao() -> None:
    e = stats.diferenca_proporcoes(630, 1000, 600, 1000)
    ep = np.sqrt(0.63 * 0.37 / 1000 + 0.6 * 0.4 / 1000)
    assert e.diferenca == pytest.approx(0.03)
    assert e.erro_padrao == pytest.approx(ep)
    assert e.ic_inf == pytest.approx(0.03 - 1.959964 * ep, rel=1e-5)


def test_bootstrap_concorda_com_o_ic_analitico() -> None:
    rng = np.random.default_rng(0)
    t = rng.integers(0, 2, 40_000)
    y = (rng.random(40_000) < 0.6 + 0.03 * t).astype(int)
    analitico = stats.diferenca_medias(y, t)
    inf, sup = stats.bootstrap_diferenca(y, t, reps=4000)
    assert inf == pytest.approx(analitico.ic_inf, abs=0.002)
    assert sup == pytest.approx(analitico.ic_sup, abs=0.002)


def test_cuped_reduz_variancia_em_rho_quadrado_sem_viesar() -> None:
    rng = np.random.default_rng(1)
    n = 200_000
    x = rng.normal(size=n)
    t = rng.integers(0, 2, n)
    y = 0.6 * x + rng.normal(size=n) + 0.05 * t
    r = stats.cuped(y, x, t)
    assert r.efeito_ajustado.diferenca == pytest.approx(0.05, abs=0.01)
    assert r.reducao_variancia == pytest.approx(r.correlacao**2, abs=0.01)
    assert r.efeito_ajustado.largura < r.efeito_bruto.largura


def test_mde_bate_com_statsmodels() -> None:
    mde = stats.efeito_minimo_detectavel(0.62, 100_000, 100_000)
    tamanho_de_efeito_cohen = NormalIndPower().solve_power(
        effect_size=None, nobs1=100_000, alpha=0.05, power=0.8, ratio=1.0
    )
    assert proportion_effectsize(0.62 + mde, 0.62) == pytest.approx(
        tamanho_de_efeito_cohen, rel=0.02
    )


def test_benjamini_hochberg_bate_com_statsmodels() -> None:
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    esperado = multipletests(p, method="fdr_bh")[1]
    np.testing.assert_allclose(stats.benjamini_hochberg(p), esperado)
