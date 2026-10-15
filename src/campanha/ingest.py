from __future__ import annotations

import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import duckdb

DATA = Path("data")
RAW = DATA / "raw"
PARQUET = DATA / "parquet"
BLOCO_DE_DOWNLOAD = 8 * 2**20

ESPELHO_X5 = "https://sklift.s3.eu-west-2.amazonaws.com"
ESPELHO_CRITEO = "https://github.com/jszymon/uplift_sklearn_data/releases/download/Criteo"


@dataclass(frozen=True)
class Fonte:
    tabela: str
    url: str
    base: str

    @property
    def arquivo(self) -> Path:
        return RAW / self.url.rsplit("/", 1)[-1]

    @property
    def parquet(self) -> Path:
        return PARQUET / f"{self.tabela}.parquet"


FONTES = [
    Fonte("clients", f"{ESPELHO_X5}/clients.csv.gz", "x5"),
    Fonte("uplift_train", f"{ESPELHO_X5}/uplift_train.csv.gz", "x5"),
    Fonte("purchases", f"{ESPELHO_X5}/purchases.csv.gz", "x5"),
    Fonte("criteo", f"{ESPELHO_CRITEO}/criteo-research-uplift-v2.1.csv.gz", "criteo"),
]


def fontes(base: str | None = None) -> list[Fonte]:
    return [fonte for fonte in FONTES if base is None or fonte.base == base]


def baixar(fonte: Fonte, forcar: bool = False) -> Path:
    if fonte.arquivo.exists() and not forcar:
        return fonte.arquivo
    RAW.mkdir(parents=True, exist_ok=True)
    incompleto = fonte.arquivo.with_suffix(fonte.arquivo.suffix + ".part")
    with urllib.request.urlopen(fonte.url, timeout=60) as resposta, incompleto.open("wb") as saida:
        tamanho_esperado = int(resposta.headers.get("Content-Length", 0))
        shutil.copyfileobj(resposta, saida, length=BLOCO_DE_DOWNLOAD)
    tamanho_baixado = incompleto.stat().st_size
    if tamanho_esperado and tamanho_baixado != tamanho_esperado:
        raise OSError(f"{fonte.arquivo.name}: baixei {tamanho_baixado} de {tamanho_esperado} bytes")
    incompleto.replace(fonte.arquivo)
    return fonte.arquivo


def converter(fonte: Fonte, forcar: bool = False) -> Path:
    if fonte.parquet.exists() and not forcar:
        return fonte.parquet
    PARQUET.mkdir(parents=True, exist_ok=True)
    incompleto = fonte.parquet.with_suffix(".parquet.tmp")
    csv = f"read_csv('{fonte.arquivo.as_posix()}', header = true, sample_size = -1)"
    with duckdb.connect() as con:
        con.execute(
            f"COPY (SELECT * FROM {csv}) "
            f"TO '{incompleto.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"
        )
    incompleto.replace(fonte.parquet)
    return fonte.parquet
