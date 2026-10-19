from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic
import duckdb
import pandas as pd

from persuadables import decisao, relatorio

OPENROUTER = os.environ.get("OPENROUTER_API_KEY")
MODELO = os.environ.get(
    "PERSUADABLES_MODELO", "anthropic/claude-opus-5.5" if OPENROUTER else "claude-opus-5-5"
)
REPORTS = Path(__file__).resolve().parents[2] / "reports"
MAX_VOLTAS = 8
MAX_LINHAS = 50
TOLERANCIA = 0.01
DOLARES_POR_MILHAO = {"entrada": 4.0, "saida": 20.0}

TABELAS = {
    "efeito": "20_placar_experimento/03_efeito.csv",
    "segmentos": "20_placar_experimento/05_segmentos_bh.csv",
    "cuped": "20_placar_experimento/04_cuped.csv",
    "modelos": "40_uplift/metricas.csv",
    "influenciados": "40_uplift/quem_e_influenciado.csv",
    "curvas": "50_decisao/curvas.csv",
}

SISTEMA = (
    "Você é analista de CRM e responde perguntas do gerente sobre um teste de campanha da X5 "
    "com 200 mil clientes sorteados. Use as ferramentas: `consultar` lê as tabelas de "
    "resultado e `lucro` calcula compradores e lucro de um orçamento. Valores em rublos, "
    "efeitos em pontos percentuais. Termine sempre com uma linha 'RESPOSTA: <número>', sem "
    "separador de milhar e com ponto como separador decimal."
)


@dataclass(frozen=True)
class Resposta:
    texto: str
    valor: float | None
    tokens_entrada: int
    tokens_saida: int


def ferramentas(reports: Path = REPORTS) -> list[dict]:
    tabelas = "; ".join(
        f"{nome}({', '.join(pd.read_csv(reports / arquivo, nrows=0).columns)})"
        for nome, arquivo in TABELAS.items()
    )
    return [
        {
            "name": "consultar",
            "description": f"Executa um SELECT (DuckDB) nas tabelas: {tabelas}.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
        {
            "name": "lucro",
            "description": "Compradores incrementais e lucro de mandar a campanha para uma "
            "fração da base, ordenada por uma estratégia. Frações de 0.05 a 1.0, de 0.05 em 0.05.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "estrategia": {"type": "string", "enum": ["aleatório", "propensão", "uplift"]},
                    "fracao": {"type": "number"},
                    "custo_por_contato": {"type": "number"},
                    "margem": {"type": "number"},
                },
                "required": ["estrategia", "fracao", "custo_por_contato", "margem"],
                "additionalProperties": False,
            },
        },
    ]


def consultar(sql: str, reports: Path = REPORTS) -> str:
    comando = sql.strip().rstrip(";")
    if not re.match(r"(SELECT|WITH)\b", comando, re.IGNORECASE) or ";" in comando:
        return "erro: só um SELECT por vez"
    with duckdb.connect() as con:
        for nome, arquivo in TABELAS.items():
            con.execute(f"CREATE VIEW {nome} AS SELECT * FROM '{(reports / arquivo).as_posix()}'")
        try:
            linhas = con.execute(comando).df().head(MAX_LINHAS)
        except duckdb.Error as erro:
            return f"erro: {erro}"
    return linhas.to_json(orient="records", force_ascii=False)


def lucro(
    estrategia: str, fracao: float, custo_por_contato: float, margem: float, reports: Path = REPORTS
) -> dict:
    curvas = pd.read_csv(reports / "50_decisao" / "curvas.csv")
    premissas = json.loads((reports / "50_decisao" / "premissas.json").read_text(encoding="utf-8"))
    no_orcamento = (curvas["estrategia"] == estrategia) & (
        curvas["fracao"].round(2) == round(fracao, 2)
    )
    if not no_orcamento.any():
        return {"erro": "fração fora da grade de 0.05 a 1.0"}
    valor = decisao.Premissas(custo_por_contato, margem).valor_por_comprador(
        premissas["ticket_base"]
    )
    linha = decisao.financeiro(curvas[no_orcamento], premissas["n_base"], valor, custo_por_contato)
    colunas = ["contatos", "incrementais", "inf", "sup", "custo", "lucro", "lucro_inf", "lucro_sup"]
    return {coluna: round(float(linha[coluna].iloc[0]), 2) for coluna in colunas}


def executar(nome: str, entrada: dict, reports: Path = REPORTS) -> str:
    if nome == "consultar":
        return consultar(entrada["sql"], reports)
    return json.dumps(lucro(**entrada, reports=reports), ensure_ascii=False)


def extrair_valor(texto: str) -> float | None:
    achado = re.search(r"RESPOSTA:\s*(-?\d+(?:\.\d+)?)", texto)
    return float(achado.group(1)) if achado else None


def cliente_padrao() -> anthropic.Anthropic:
    if OPENROUTER:
        return anthropic.Anthropic(base_url="https://openrouter.ai/api", auth_token=OPENROUTER)
    return anthropic.Anthropic()


def perguntar(pergunta: str, cliente=None, reports: Path = REPORTS) -> Resposta:
    cliente = cliente or cliente_padrao()
    mensagens = [{"role": "user", "content": pergunta}]
    entrada = saida = 0
    for _ in range(MAX_VOLTAS):
        r = cliente.messages.create(
            model=MODELO,
            max_tokens=4096,
            system=SISTEMA,
            tools=ferramentas(reports),
            messages=mensagens,
            output_config={"effort": "low"},
        )
        entrada, saida = entrada + r.usage.input_tokens, saida + r.usage.output_tokens
        if r.stop_reason != "tool_use":
            texto = "".join(bloco.text for bloco in r.content if bloco.type == "text")
            return Resposta(texto, extrair_valor(texto), entrada, saida)
        mensagens.append({"role": "assistant", "content": r.content})
        resultados = [
            {
                "type": "tool_result",
                "tool_use_id": bloco.id,
                "content": executar(bloco.name, bloco.input, reports),
            }
            for bloco in r.content
            if bloco.type == "tool_use"
        ]
        mensagens.append({"role": "user", "content": resultados})
    return Resposta("", None, entrada, saida)


def gabarito(reports: Path = REPORTS) -> list[tuple[str, float]]:
    tabela = {nome: pd.read_csv(reports / arquivo) for nome, arquivo in TABELAS.items()}
    efeito = tabela["efeito"].iloc[0]
    segmentos = tabela["segmentos"].set_index(["segmento", "nivel"])["efeito_pp"]
    modelos = tabela["modelos"].query("conjunto == 'teste'").set_index("modelo")
    influenciados = tabela["influenciados"].set_index("grupo")
    curvas = tabela["curvas"].set_index(["estrategia", "fracao"])
    lucro_a_6 = {f: lucro("uplift", f, 6.0, 0.2, reports)["lucro"] for f in decisao.FRACOES}
    return [
        (
            "Qual foi o efeito médio da campanha na taxa de compra, em pontos percentuais?",
            efeito["efeito_pp"],
        ),
        (
            "Quantos compradores a mais a campanha gerou entre os clientes tratados?",
            efeito["compras_incrementais"],
        ),
        (
            "Qual o efeito da campanha, em p.p., no decil de clientes que menos gastavam antes?",
            segmentos[("decil_gasto", "D01")],
        ),
        ("Qual a AUUC do S-learner no conjunto de teste?", modelos.loc["S-learner", "auuc"]),
        (
            "Qual a mediana de idade dos 20% de clientes com maior uplift previsto?",
            influenciados.loc["20% maior uplift", "idade"],
        ),
        (
            "Quantos compradores a mais teremos mandando por uplift para 20% da base?",
            curvas.loc[("uplift", 0.2), "incrementais"],
        ),
        (
            "Qual o lucro incremental de mandar por uplift para 15% da base, com contato a 3 "
            "rublos e margem de 20%?",
            lucro("uplift", 0.15, 3.0, 0.2, reports)["lucro"],
        ),
        (
            "Com contato a 5 rublos e margem de 25%, qual o lucro de mandar por propensão para "
            "30% da base?",
            lucro("propensão", 0.3, 5.0, 0.25, reports)["lucro"],
        ),
        (
            "Qual o lucro de mandar a campanha para a base inteira com contato a 6 rublos e "
            "margem de 20%?",
            lucro("uplift", 1.0, 6.0, 0.2, reports)["lucro"],
        ),
        (
            "Com contato a 6 rublos e margem de 20%, qual porcentagem da base devemos contatar "
            "por uplift para ter o maior lucro? Responda em %.",
            max(lucro_a_6, key=lucro_a_6.get) * 100,
        ),
    ]


def acertou(resposta: float | None, esperado: float) -> bool:
    return resposta is not None and abs(resposta - esperado) <= TOLERANCIA * max(abs(esperado), 1)


def avaliar(cliente=None, reports: Path = REPORTS) -> pd.DataFrame:
    cliente = cliente or cliente_padrao()
    linhas = []
    for pergunta, esperado in gabarito(reports):
        r = perguntar(pergunta, cliente, reports)
        linhas.append(
            {
                "pergunta": pergunta,
                "esperado": round(float(esperado), 4),
                "resposta": r.valor,
                "acertou": acertou(r.valor, esperado),
                "tokens_entrada": r.tokens_entrada,
                "tokens_saida": r.tokens_saida,
            }
        )
    avaliacao = pd.DataFrame(linhas)
    relatorio.salvar_csv(avaliacao, reports / "60_agente" / "avaliacao.csv")
    custo = (
        avaliacao["tokens_entrada"].sum() * DOLARES_POR_MILHAO["entrada"]
        + avaliacao["tokens_saida"].sum() * DOLARES_POR_MILHAO["saida"]
    ) / 1e6
    texto = relatorio.preencher(
        "agente",
        modelo=MODELO,
        acertos=int(avaliacao["acertou"].sum()),
        total=len(avaliacao),
        tolerancia=TOLERANCIA,
        tokens=int(avaliacao[["tokens_entrada", "tokens_saida"]].to_numpy().sum()),
        custo=custo,
        tabela=relatorio.tabela(
            avaliacao.drop(columns=["tokens_entrada", "tokens_saida"]), casas=2
        ),
    )
    (reports / "agente.md").write_text(texto, encoding="utf-8")
    return avaliacao
