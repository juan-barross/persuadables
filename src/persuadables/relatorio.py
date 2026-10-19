from __future__ import annotations

import numbers
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from persuadables.run_sql import Resultado

MODELOS = Path(__file__).parent / "relatorios"
DIGITOS_SIGNIFICATIVOS = "%.6g"


def salvar_csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False, float_format=DIGITOS_SIGNIFICATIVOS)


def preencher(modelo: str, /, **valores: object) -> str:
    texto = (MODELOS / f"{modelo}.md").read_text(encoding="utf-8")
    return texto.format(**valores)


def tabela(df: pd.DataFrame, casas: int = 4) -> str:
    cabecalho = "| " + " | ".join(map(str, df.columns)) + " |"
    separador = "|" + "|".join("---" for _ in df.columns) + "|"
    linhas = [
        "| " + " | ".join(_formatar(valor, casas) for valor in linha) + " |"
        for linha in df.itertuples(index=False)
    ]
    return "\n".join([cabecalho, separador, *linhas])


def de_consultas(titulo: str, resultados: list[Resultado], introducao: str) -> str:
    partes = [f"# {titulo}", "", introducao, ""]
    for r in resultados:
        if r.df is not None:
            partes += [f"## {r.nome}", "", tabela(r.df), ""]
    return "\n".join(partes)


def _formatar(valor: object, casas: int) -> str:
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, numbers.Integral):
        return f"{valor:,}"
    if isinstance(valor, numbers.Real):
        if valor != valor:
            return ""
        return f"{valor:,.{casas}f}".rstrip("0").rstrip(".")
    if valor is None or valor is pd.NaT:
        return ""
    return str(valor)
