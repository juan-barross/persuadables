from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from persuadables import agente, decisao


class ClienteRoteirizado:
    def __init__(self, respostas: list) -> None:
        self.respostas = iter(respostas)
        self.pedidos: list[dict] = []
        self.messages = self

    def create(self, **pedido) -> SimpleNamespace:
        self.pedidos.append(pedido)
        return next(self.respostas)


def resposta(stop_reason: str, *blocos) -> SimpleNamespace:
    uso = SimpleNamespace(input_tokens=100, output_tokens=20)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocos), usage=uso)


def texto(conteudo: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=conteudo)


def chamada(nome: str, entrada: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id="t1", name=nome, input=entrada)


def test_extrai_o_numero_da_ultima_linha() -> None:
    assert agente.extrair_valor("Explicação.\nRESPOSTA: -1234.5") == -1234.5
    assert agente.extrair_valor("sem número") is None


def test_lucro_e_a_mesma_conta_do_simulador() -> None:
    curvas = pd.read_csv(agente.REPORTS / "50_decisao" / "curvas.csv")
    premissas = json.loads((agente.REPORTS / "50_decisao" / "premissas.json").read_text("utf-8"))
    ponto = curvas[(curvas["estrategia"] == "uplift") & (curvas["fracao"] == 0.3)]
    valor = decisao.Premissas(4.0, 0.25).valor_por_comprador(premissas["ticket_base"])
    esperado = decisao.financeiro(ponto, premissas["n_base"], valor, 4.0)["lucro"].iloc[0]
    assert agente.lucro("uplift", 0.3, 4.0, 0.25)["lucro"] == pytest.approx(esperado, abs=0.01)


def test_lucro_recusa_fracao_fora_da_grade() -> None:
    assert "erro" in agente.lucro("uplift", 0.33, 3.0, 0.2)


def test_consultar_le_as_tabelas_e_so_aceita_select() -> None:
    linhas = json.loads(agente.consultar("SELECT modelo FROM modelos WHERE conjunto = 'teste'"))
    assert {linha["modelo"] for linha in linhas} >= {"propensão", "S-learner"}
    assert agente.consultar("DROP TABLE modelos").startswith("erro")
    assert agente.consultar("SELECT 1; SELECT 2").startswith("erro")


def test_ferramentas_descrevem_as_colunas_e_sao_estritas() -> None:
    consultar, lucro = agente.ferramentas()
    assert "curvas(estrategia, fracao, incrementais, inf, sup)" in consultar["description"]
    assert consultar["strict"] and lucro["strict"]


def test_pergunta_executa_a_ferramenta_e_devolve_o_valor() -> None:
    entrada = {"estrategia": "uplift", "fracao": 0.15, "custo_por_contato": 3.0, "margem": 0.2}
    cliente = ClienteRoteirizado(
        [
            resposta("tool_use", chamada("lucro", entrada)),
            resposta("end_turn", texto("Lucro de cerca de 160 mil.\nRESPOSTA: 159782.5")),
        ]
    )
    r = agente.perguntar("Qual o lucro?", cliente)
    assert r.valor == 159782.5 and (r.tokens_entrada, r.tokens_saida) == (200, 40)
    resultado = cliente.pedidos[1]["messages"][2]["content"][0]
    assert resultado["type"] == "tool_result" and '"lucro"' in resultado["content"]


def test_gabarito_tem_dez_perguntas_com_resposta_numerica() -> None:
    perguntas = agente.gabarito()
    assert len(perguntas) == 10
    assert all(pd.notna(esperado) for _, esperado in perguntas)


def test_acerto_tolera_um_por_cento() -> None:
    assert agente.acertou(100.9, 100) and not agente.acertou(102, 100)
    assert not agente.acertou(None, 100)


def test_avaliacao_conta_acertos_e_grava_relatorio(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    shutil.copytree(agente.REPORTS, reports)
    gabarito = agente.gabarito(reports)
    cliente = ClienteRoteirizado(
        [resposta("end_turn", texto(f"RESPOSTA: {esperado}")) for _, esperado in gabarito[:-1]]
        + [resposta("end_turn", texto("não sei"))]
    )
    avaliacao = agente.avaliar(cliente, reports)
    assert avaliacao["acertou"].sum() == len(gabarito) - 1
    assert "**9 de 10 acertos**" in (reports / "agente.md").read_text(encoding="utf-8")


def test_custo_e_zero_em_modelo_gratuito_e_preco_do_opus_nos_demais() -> None:
    assert agente.custo_em_dolares("nvidia/nemotron-3-ultra-550b-a55b:free", 10**6, 10**6) == 0
    assert agente.custo_em_dolares("anthropic/claude-opus-5.5", 10**6, 10**6) == 24
