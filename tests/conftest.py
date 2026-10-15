from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from campanha import amostra


@pytest.fixture(scope="session")
def amostra_base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return amostra.gerar(tmp_path_factory.mktemp("amostra"), n_clientes=2000)


@pytest.fixture
def amostra_copia(amostra_base: Path, tmp_path: Path) -> Path:
    destino = tmp_path / "parquet"
    shutil.copytree(amostra_base, destino)
    return destino
