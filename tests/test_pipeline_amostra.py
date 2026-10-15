from __future__ import annotations

import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from persuadables import decisao, placar, run_sql, uplift


@dataclass
class Pipeline:
    dados: Path
    reports: Path
    perfil: pd.DataFrame
    placar: dict
    uplift: uplift.ResultadoUplift


@pytest.fixture(scope="module")
def pipeline(amostra_base: Path, tmp_path_factory: pytest.TempPathFactory) -> Pipeline:
    raiz = tmp_path_factory.mktemp("pipeline")
    dados, reports = raiz / "parquet", raiz / "reports"
    shutil.copytree(amostra_base, dados)
    reports.mkdir()
    perfil = run_sql.construir_perfil(run_sql.conectar(dados), reports)
    perfil.to_parquet(dados / "perfil_cliente.parquet", index=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultado_do_placar = placar.rodar(run_sql.conectar(dados), reports)
        resultado_do_uplift = uplift.rodar(perfil, reports, dados)
        decisao.rodar(dados, reports)
    return Pipeline(dados, reports, perfil, resultado_do_placar, resultado_do_uplift)


def test_relatorios_gerados(pipeline: Pipeline) -> None:
    for nome in ("placar.md", "uplift.md", "decisao.md"):
        assert (pipeline.reports / nome).stat().st_size > 1000
    for figura in ("efeito_por_segmento", "curva_qini", "orcamento_vs_incrementais"):
        assert (pipeline.reports / "figuras" / f"{figura}.png").exists()


def test_placar_conta_todos_os_clientes(pipeline: Pipeline) -> None:
    resumo = pipeline.placar
    assert resumo["n_t"] + resumo["n_c"] == len(pipeline.perfil)
    assert resumo["p_srm"] > 0.001


def test_balanco_dentro_do_acaso(pipeline: Pipeline) -> None:
    resumo = pipeline.placar
    erro_padrao_do_smd = (2 / min(resumo["n_t"], resumo["n_c"])) ** 0.5
    assert resumo["max_abs_smd"] < 4 * erro_padrao_do_smd


def test_efeito_plantado_aparece_nos_inativos(pipeline: Pipeline) -> None:
    segmentos = pd.read_csv(pipeline.reports / "20_placar_experimento" / "05_segmentos_bh.csv")
    recencia = segmentos[segmentos["segmento"] == "recencia_14d"].set_index("nivel")["efeito_pp"]
    assert recencia["sem comprar há mais de 14 dias"] > recencia["comprou nos últimos 14 dias"] + 5


def test_scores_cobrem_o_teste_sem_perder_linhas(pipeline: Pipeline) -> None:
    scores = pd.read_parquet(pipeline.dados / "scores_teste.parquet")
    divisao = pipeline.uplift.divisao
    clientes_divididos = len(divisao.treino) + len(divisao.validacao) + len(divisao.teste)
    assert clientes_divididos == len(pipeline.perfil)
    assert len(scores) == len(divisao.teste)
    assert scores["client_id"].is_unique
    assert scores.drop(columns=["client_id"]).notna().all().all()


def test_decisao_fecha_igual_quando_manda_para_todos(pipeline: Pipeline) -> None:
    curvas = pd.read_csv(pipeline.reports / "50_decisao" / "curvas.csv")
    assert set(curvas["estrategia"]) == {"aleatório", "propensão", "uplift"}
    mandando_para_todos = curvas[curvas["fracao"] == 1.0]["incrementais"]
    assert mandando_para_todos.max() - mandando_para_todos.min() == pytest.approx(0, abs=1e-6)


def test_bootstrap_por_pesos_igual_a_repetir_as_linhas() -> None:
    rng = np.random.default_rng(0)
    n = 500
    comprou = (rng.random(n) < 0.6).astype(float)
    tratado = (rng.random(n) < 0.5).astype(float)
    pesos = rng.multinomial(n, np.full(n, 1 / n)).astype(float)
    linhas_repetidas = np.repeat(np.arange(n), pesos.astype(int))

    por_pesos = decisao.incrementais_por_fracao(comprou, tratado, pesos, n)
    repetindo = decisao.incrementais_por_fracao(
        comprou[linhas_repetidas], tratado[linhas_repetidas], np.ones(n), n
    )
    assert por_pesos == pytest.approx(repetindo)
