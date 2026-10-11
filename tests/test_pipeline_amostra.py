"""Pipeline inteiro sobre a amostra sintética: perfil, placar, uplift e decisão.

Não confere os números da X5 (a CI não tem a base), mas garante que cada passo roda,
que nenhuma linha some no caminho e que o efeito plantado aparece onde foi plantado.
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import pandas as pd
import pytest

from campanha import decisao, placar, run_sql, uplift


@pytest.fixture(scope="module")
def pipeline(amostra_base: Path, tmp_path_factory: pytest.TempPathFactory) -> dict:
    raiz = tmp_path_factory.mktemp("pipeline")
    dados, reports = raiz / "parquet", raiz / "reports"
    shutil.copytree(amostra_base, dados)
    reports.mkdir()
    con = run_sql.conectar(dados)
    perfil = run_sql.construir_perfil(con, reports)
    perfil.to_parquet(dados / "perfil_cliente.parquet", index=False)
    con = run_sql.conectar(dados)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r_placar = placar.rodar(con, reports)
        r_uplift = uplift.rodar(perfil, reports, dados)
        r_decisao = decisao.rodar(dados, reports)
    return {
        "dados": dados,
        "reports": reports,
        "perfil": perfil,
        "placar": r_placar,
        "uplift": r_uplift,
        "decisao": r_decisao,
    }


def test_relatorios_gerados(pipeline: dict) -> None:
    for nome in ("placar.md", "uplift.md", "decisao.md"):
        assert (pipeline["reports"] / nome).stat().st_size > 1000
    for fig in ("efeito_por_segmento", "curva_qini", "orcamento_vs_incrementais"):
        assert (pipeline["reports"] / "figuras" / f"{fig}.png").exists()


def test_placar_conta_todos_os_clientes(pipeline: dict) -> None:
    r = pipeline["placar"]
    assert r["n_t"] + r["n_c"] == len(pipeline["perfil"])
    assert r["p_srm"] > 0.001  # o sorteio da amostra é honesto
    # Com sorteio honesto, o erro padrão do SMD é ~ sqrt(2 / n por braço). O 0,1 usual vale
    # para bases grandes; na amostra pequena, o maior de 36 SMDs fica abaixo de 4 erros padrão.
    erro_padrao = (2 / min(r["n_t"], r["n_c"])) ** 0.5
    assert r["max_abs_smd"] < 4 * erro_padrao


def test_efeito_plantado_aparece_nos_inativos(pipeline: dict) -> None:
    """A amostra planta +15 p.p. só em quem parou de comprar há mais de 30 dias."""
    seg = pd.read_csv(pipeline["reports"] / "20_placar_experimento" / "05_segmentos_bh.csv")
    rec = seg[seg.segmento == "recencia_14d"].set_index("nivel")["efeito_pp"]
    assert rec["sem comprar há mais de 14 dias"] > rec["comprou nos últimos 14 dias"] + 5


def test_scores_cobrem_o_teste_sem_perder_linhas(pipeline: dict) -> None:
    scores = pd.read_parquet(pipeline["dados"] / "scores_teste.parquet")
    n_tr, n_va, n_te = pipeline["uplift"]["n"]
    assert n_tr + n_va + n_te == len(pipeline["perfil"])
    assert len(scores) == n_te
    assert scores["client_id"].is_unique
    assert scores.drop(columns=["client_id"]).notna().all().all()


def test_decisao_tem_tres_estrategias_e_fecha_em_mandar_para_todos(pipeline: dict) -> None:
    curvas = pd.read_csv(pipeline["reports"] / "50_decisao" / "curvas.csv")
    assert set(curvas.estrategia) == {"aleatório", "propensão", "uplift"}
    em_100 = curvas[curvas.fracao == 1.0].set_index("estrategia")["incrementais"]
    # Mandando para todos, a ordem não importa: as três estratégias dão o mesmo número
    assert em_100.max() - em_100.min() == pytest.approx(0, abs=1e-6)
