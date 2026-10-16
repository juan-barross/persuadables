from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from persuadables import cli, decisao, graficos, ingest, placar, relatorio, run_sql, stats, uplift


def clientes_ficticios(taxa_t: float, taxa_c: float, n: int = 1000) -> pd.DataFrame:
    tratado = np.repeat([1, 0], n // 2)
    comprou = np.r_[np.arange(n // 2) < taxa_t * n / 2, np.arange(n // 2) < taxa_c * n / 2]
    return pd.DataFrame({"treatment_flg": tratado, "target": comprou.astype(int)})


def test_tabela_formata_milhar_decimais_e_vazios() -> None:
    df = pd.DataFrame({"n": [1234567], "taxa": [0.12345], "faltando": [np.nan], "nome": ["a"]})
    assert relatorio.tabela(df, casas=2).splitlines()[2] == "| 1,234,567 | 0.12 |  | a |"


def test_salvar_csv_guarda_seis_digitos(tmp_path: Path) -> None:
    relatorio.salvar_csv(pd.DataFrame({"x": [1 / 3]}), tmp_path / "pasta" / "a.csv")
    assert (tmp_path / "pasta" / "a.csv").read_text().splitlines() == ["x", "0.333333"]


def test_relatorio_de_consultas_pula_quem_nao_devolve_linhas() -> None:
    resultados = [
        run_sql.Resultado("cria_tabela", None, 0.1),
        run_sql.Resultado("conta", pd.DataFrame({"n": [3]}), 0.1),
    ]
    texto = relatorio.de_consultas("Título", resultados, "introdução")
    assert "## conta" in texto and "cria_tabela" not in texto


def test_rodar_pasta_executa_em_ordem_e_salva_um_csv_por_arquivo(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "sql" / "teste").mkdir(parents=True)
    (tmp_path / "sql" / "teste" / "02_le.sql").write_text("SELECT a + 1 AS b FROM t")
    (tmp_path / "sql" / "teste" / "01_cria.sql").write_text("CREATE TABLE t AS SELECT 1 AS a")
    monkeypatch.setattr(run_sql, "SQL", tmp_path / "sql")
    resultados = run_sql.rodar_pasta(run_sql.conectar(tmp_path), "teste", tmp_path / "saida")
    assert [r.nome for r in resultados] == ["01_cria", "02_le"]
    assert resultados[0].df.iloc[0, 0] == 1
    assert resultados[1].df["b"].item() == 2
    assert sorted(p.name for p in (tmp_path / "saida" / "teste").iterdir()) == [
        "01_cria.csv",
        "02_le.csv",
    ]


def test_fontes_filtra_por_base() -> None:
    assert [f.tabela for f in ingest.fontes("x5")] == ["clients", "uplift_train", "purchases"]
    assert [f.tabela for f in ingest.fontes("criteo")] == ["criteo"]
    assert len(ingest.fontes()) == 4


def test_converter_csv_gz_para_parquet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ingest, "RAW", tmp_path / "raw")
    monkeypatch.setattr(ingest, "PARQUET", tmp_path / "parquet")
    fonte = ingest.Fonte("clientes", "https://exemplo/clientes.csv.gz", "teste")
    fonte.arquivo.parent.mkdir()
    with gzip.open(fonte.arquivo, "wt") as arquivo:
        arquivo.write("client_id,age\nc1,30\nc2,41\n")
    convertido = pd.read_parquet(ingest.converter(fonte))
    assert convertido.to_dict("list") == {"client_id": ["c1", "c2"], "age": [30, 41]}


def test_salvar_grafico_gera_png(tmp_path: Path) -> None:
    fig = graficos.nova_figura(2, 2)
    graficos.estilizar(fig.subplots())
    graficos.salvar(fig, tmp_path / "figuras" / "teste.png")
    assert (tmp_path / "figuras" / "teste.png").read_bytes()[:4] == b"\x89PNG"


def test_efeito_de_sem_erro_padrao_nao_tem_p_valor() -> None:
    efeito = stats.efeito_de(0.0, 0.0)
    assert np.isnan(efeito.p_valor) and efeito.largura == 0


def test_bootstrap_de_desfecho_continuo_cobre_a_diferenca() -> None:
    rng = np.random.default_rng(1)
    tratado = rng.integers(0, 2, 2000)
    y = rng.normal(10, 2, 2000) + 0.5 * tratado
    inferior, superior = stats.bootstrap_diferenca(y, tratado, reps=300)
    assert inferior < 0.5 < superior


def test_efeito_observado_em_pontos_percentuais() -> None:
    efeito = uplift.efeito_observado(clientes_ficticios(0.6, 0.5))
    assert efeito["taxa_t"] == 0.6 and efeito["taxa_c"] == 0.5
    assert efeito["uplift_pp"] == pytest.approx(10)
    assert efeito["ic_inf_pp"] < 10 < efeito["ic_sup_pp"]


def test_uplift_por_decil_divide_em_dez_faixas_iguais() -> None:
    clientes = clientes_ficticios(0.6, 0.5)
    decis = uplift.uplift_por_decil(clientes, np.random.default_rng(0).random(len(clientes)))
    assert decis["faixa"].tolist() == list(range(1, 11))
    assert (decis["n"] == 100).all()


def test_dividir_mantem_proporcoes_e_estratos() -> None:
    perfil = clientes_ficticios(0.6, 0.5, n=2000).assign(client_id=range(2000))
    divisao = uplift.dividir(perfil)
    assert [len(divisao.treino), len(divisao.validacao), len(divisao.teste)] == [1200, 400, 400]
    for parte in (divisao.treino, divisao.validacao, divisao.teste):
        assert parte["treatment_flg"].mean() == pytest.approx(0.5, abs=0.01)


def test_escolha_do_modelo_ignora_propensao() -> None:
    metricas = pd.DataFrame(
        {
            "modelo": ["propensão", "S-learner", "T-learner"],
            "conjunto": "validação",
            "auuc": [0.9, 0.1, 0.2],
        }
    )
    assert uplift.melhor_na_validacao(metricas) == "T-learner"


def test_segmentos_com_bh_marca_so_os_fortes() -> None:
    segmentos = pd.DataFrame({"z": [10.0, 0.1], "efeito_pp": [5.0, 0.1], "ep_pp": [0.5, 1.0]})
    marcados = placar.segmentos_com_bh(segmentos)
    assert marcados["significativo_bh_5pct"].tolist() == [True, False]
    assert marcados["ic_inf_pp"].iloc[0] == pytest.approx(5 - 1.959964 * 0.5)


def test_diferenca_entre_niveis_em_pp() -> None:
    segmentos = pd.DataFrame(
        {"segmento": "decil", "nivel": ["D01", "D10"], "efeito_pp": [7.0, 1.0], "ep_pp": [3.0, 4.0]}
    )
    efeito = placar.diferenca_entre_niveis(segmentos, "decil", "D01", "D10")
    assert efeito.diferenca == 6 and efeito.erro_padrao == 5


def test_sem_efeito_nao_ha_compradores_incrementais() -> None:
    clientes = clientes_ficticios(0.5, 0.5)
    incrementais = decisao.incrementais_por_fracao(
        clientes["target"].to_numpy(float),
        clientes["treatment_flg"].to_numpy(float),
        np.ones(len(clientes)),
        n_base=1000,
    )
    assert incrementais[-1] == pytest.approx(0)


def test_pesos_do_bootstrap_somam_o_tamanho_da_base_em_cada_braco() -> None:
    tratado = np.repeat([True, False], [30, 70])
    for pesos in decisao.pesos_do_bootstrap(tratado, reps=5):
        assert pesos[tratado].sum() == 30 and pesos[~tratado].sum() == 70


def test_aleatorio_esperado_e_uma_reta() -> None:
    curvas = pd.DataFrame(
        {
            "estrategia": "aleatório",
            "fracao": decisao.FRACOES,
            "incrementais": np.random.default_rng(0).random(20),
            "inf": 0.0,
            "sup": 0.0,
        }
    )
    reta = decisao.com_aleatorio_esperado(curvas)
    no_fim = reta["incrementais"].iloc[-1]
    assert np.allclose(reta["incrementais"], decisao.FRACOES * no_fim)


def test_financeiro_calcula_lucro() -> None:
    curvas = pd.DataFrame({"fracao": [0.5], "incrementais": [100.0], "inf": [50.0], "sup": [150.0]})
    linha = decisao.financeiro(curvas, n_base=1000, valor=10.0, custo=2.0).iloc[0]
    assert (linha["custo"], linha["lucro"], linha["lucro_inf"]) == (1000, 0, -500)


def test_premissas_usam_ticket_da_base_quando_nao_informado() -> None:
    assert decisao.Premissas(margem=0.2).valor_por_comprador(500) == 100
    assert decisao.Premissas(margem=0.2, ticket=100).valor_por_comprador(500) == 20


def test_sensibilidade_testa_doze_cenarios() -> None:
    curvas = pd.DataFrame(
        {
            "estrategia": "uplift",
            "fracao": decisao.FRACOES,
            "incrementais": decisao.FRACOES * 1000,
            "inf": 0.0,
            "sup": 0.0,
        }
    )
    cenarios = decisao.sensibilidade(curvas, {"ticket_base": 500, "n_base": 10_000})
    assert len(cenarios) == len(decisao.CUSTOS_TESTADOS) * len(decisao.MARGENS_TESTADAS)


def test_cli_lista_os_comandos() -> None:
    ajuda = CliRunner().invoke(cli.app, ["--help"]).output
    for comando in ("baixar", "auditar", "perfil", "placar", "uplift", "decisao", "escala", "tudo"):
        assert comando in ajuda


def test_cli_gera_amostra(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultado = CliRunner().invoke(cli.app, ["--amostra", "amostra"])
    assert resultado.exit_code == 0
    assert (tmp_path / "data" / "amostra" / "parquet" / "purchases.parquet").exists()
