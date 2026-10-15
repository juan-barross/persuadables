from __future__ import annotations

from pathlib import Path

from matplotlib.axes import Axes
from matplotlib.figure import Figure

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRADE = "#e4e3df"

AZUL = "#2a78d6"
LARANJA = "#eb6834"
VERDE_AGUA = "#1baf7a"
AMARELO = "#eda100"
MAGENTA = "#e87ba4"

TRACEJADO = (0, (4, 3))


def nova_figura(largura: float, altura: float) -> Figure:
    return Figure(figsize=(largura, altura), facecolor=SUPERFICIE)


def estilizar(ax: Axes, grade: str = "both") -> None:
    ax.set_facecolor(SUPERFICIE)
    ax.tick_params(colors=TEXTO_SECUNDARIO, labelsize=9)
    ax.grid(axis=grade, color=GRADE, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)


def rotular_eixos(ax: Axes, x: str, y: str = "") -> None:
    ax.set_xlabel(x, color=TEXTO_SECUNDARIO)
    ax.set_ylabel(y, color=TEXTO_SECUNDARIO)


def titular(fig: Figure, titulo: str, subtitulo: str, espaco_topo: float = 0.9) -> None:
    fig.suptitle(titulo, x=0.02, ha="left", color=TEXTO, fontsize=12, fontweight="bold")
    fig.text(0.02, espaco_topo + 0.005, subtitulo, color=TEXTO_SECUNDARIO, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, espaco_topo - 0.01))


def salvar(fig: Figure, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
