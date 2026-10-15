from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from persuadables import run_sql, stats


@pytest.fixture(scope="module")
def criteo_falsa(tmp_path_factory: pytest.TempPathFactory) -> tuple[pd.DataFrame, Path]:
    rng = np.random.default_rng(3)
    n = 60_000
    d = pd.DataFrame({f"f{i}": rng.normal(10 + i, 1 + i / 3, n) for i in range(3)})
    d["treatment"] = (rng.random(n) < 0.85).astype(int)
    p = 0.03 + 0.01 * d["treatment"] + 0.01 * (d["f1"] - 11) / 1.3
    d["visit"] = (rng.random(n) < p.clip(0, 1)).astype(int)
    d["conversion"] = d["visit"] * (rng.random(n) < 0.1)
    d["exposure"] = d["treatment"] * (rng.random(n) < 0.04)
    pasta = tmp_path_factory.mktemp("criteo")
    d.to_parquet(pasta / "criteo.parquet", index=False)
    return d, pasta


def rodar(pasta: Path, nome: str) -> pd.DataFrame:
    con = run_sql.conectar(pasta)
    return run_sql.rodar_arquivo(con, run_sql.SQL / "30_escala_criteo" / f"{nome}.sql").df


def test_cuped_por_estatisticas_suficientes_bate_com_python(criteo_falsa) -> None:
    d, pasta = criteo_falsa
    sql = rodar(pasta, "04_cuped").set_index("covariavel")
    for f in ("f0", "f1", "f2"):
        py = stats.cuped(d["visit"], d[f], d["treatment"])
        assert sql.loc[f, "reducao_variancia"] == pytest.approx(py.reducao_variancia, abs=1e-9)
        assert sql.loc[f, "efeito_cuped_pp"] == pytest.approx(
            py.efeito_ajustado.diferenca * 100, abs=1e-9
        )
    unica_que_explica_a_visita = "f1"
    assert sql.index[0] == unica_que_explica_a_visita


def test_efeito_em_visita_bate_com_python(criteo_falsa) -> None:
    d, pasta = criteo_falsa
    sql = rodar(pasta, "03_efeito").set_index("desfecho")
    t, y = d["treatment"], d["visit"]
    py = stats.diferenca_proporcoes(
        y[t == 1].sum(), (t == 1).sum(), y[t == 0].sum(), (t == 0).sum()
    )
    assert sql.loc["visit", "efeito_pp"] == pytest.approx(py.diferenca * 100)
    assert sql.loc["visit", "ic_inf_pp"] == pytest.approx(py.ic_inf * 100, rel=1e-5)


def test_sorteio_usa_treatment_e_nao_exposure(criteo_falsa) -> None:
    d, pasta = criteo_falsa
    s = rodar(pasta, "01_sorteio").iloc[0]
    assert s["prop_tratamento"] == pytest.approx(d["treatment"].mean())
    assert s["exposicao_controle"] == 0
