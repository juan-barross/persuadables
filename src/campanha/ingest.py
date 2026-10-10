"""Baixa os CSVs da X5 RetailHero e da Criteo e converte para Parquet.

Os arquivos são os mesmos que `sklift.datasets.fetch_x5` e `fetch_criteo` usam,
mas baixados direto em streaming: carregar 45 milhões de compras no pandas
trava o notebook, então a conversão para Parquet é feita pelo DuckDB.
"""

from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import duckdb

DATA = Path("data")
RAW = DATA / "raw"
PARQUET = DATA / "parquet"


@dataclass(frozen=True)
class Fonte:
    tabela: str
    url: str
    base: str  # x5 ou criteo

    @property
    def arquivo(self) -> Path:
        return RAW / self.url.rsplit("/", 1)[-1]

    @property
    def parquet(self) -> Path:
        return PARQUET / f"{self.tabela}.parquet"


FONTES = [
    Fonte("clients", "https://sklift.s3.eu-west-2.amazonaws.com/clients.csv.gz", "x5"),
    Fonte("uplift_train", "https://sklift.s3.eu-west-2.amazonaws.com/uplift_train.csv.gz", "x5"),
    Fonte("purchases", "https://sklift.s3.eu-west-2.amazonaws.com/purchases.csv.gz", "x5"),
    # O bucket que o sklift usa (criteo-bucket) e o go.criteo.net davam 404 em out/2026.
    # Este é o espelho da v2.1 que a libuplift usa; conferimos MD5 e linhas.
    Fonte(
        "criteo",
        "https://github.com/jszymon/uplift_sklearn_data/releases/download/Criteo/"
        "criteo-research-uplift-v2.1.csv.gz",
        "criteo",
    ),
]


def fontes(base: str | None = None) -> list[Fonte]:
    return [f for f in FONTES if base is None or f.base == base]


def baixar(fonte: Fonte, forcar: bool = False) -> Path:
    """Baixa em streaming para um .part e só renomeia no fim, para um download
    interrompido não passar por arquivo completo."""
    if fonte.arquivo.exists() and not forcar:
        return fonte.arquivo
    RAW.mkdir(parents=True, exist_ok=True)
    parcial = fonte.arquivo.with_suffix(fonte.arquivo.suffix + ".part")
    with urllib.request.urlopen(fonte.url, timeout=60) as resp, parcial.open("wb") as out:
        esperado = int(resp.headers.get("Content-Length", 0))
        shutil.copyfileobj(resp, out, length=8 * 1024 * 1024)
    if esperado and parcial.stat().st_size != esperado:
        raise OSError(f"{fonte.arquivo.name}: baixei {parcial.stat().st_size} de {esperado} bytes")
    parcial.replace(fonte.arquivo)
    return fonte.arquivo


def converter(fonte: Fonte, forcar: bool = False) -> Path:
    """CSV.gz -> Parquet (zstd) via DuckDB, sem passar pela memória do pandas."""
    if fonte.parquet.exists() and not forcar:
        return fonte.parquet
    PARQUET.mkdir(parents=True, exist_ok=True)
    tmp = fonte.parquet.with_suffix(".parquet.tmp")
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (SELECT * FROM read_csv('{fonte.arquivo.as_posix()}', header = true,
                                     sample_size = -1))
        TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    con.close()
    tmp.replace(fonte.parquet)
    return fonte.parquet
