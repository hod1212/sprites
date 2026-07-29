"""
Modulo B — Processamento de Imagem & Sprite Slicing (Pillow + NumPy).

Responsabilidades:
  1. Detectar e remover o fundo do spritesheet — tanto o "magenta magico"
     (#FF00FF e variacoes) quanto qualquer cor solida de fundo, preservando
     transparencia alpha quando ela ja existe.
  2. Fatiar o sheet em quadros individuais (frames/direcoes) usando projecao
     do canal alpha: colunas vazias separam os sprites horizontalmente e,
     dentro de cada faixa, linhas vazias separam verticalmente.
  3. Preparar o quadro escolhido para envio ao Gemini (recorte justo +
     enquadramento quadrado com margem, o que melhora muito o resultado
     do Image-to-Image).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# Cores de fundo mais comuns em rips de Ragnarok Online
KNOWN_BG_COLORS = [
    (255, 0, 255),    # magenta classico
    (255, 0, 128),    # rosa choque
    (0, 255, 0),      # verde chroma
]
BG_TOLERANCE = 32  # distancia por canal para considerar "mesma cor"


@dataclass
class Frame:
    """Um quadro individual extraido do spritesheet."""

    image: Image.Image           # RGBA, ja com fundo transparente
    bbox: tuple[int, int, int, int]  # (esq, topo, dir, base) no sheet original

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size


# ---------------------------------------------------------------------------
# Remocao de fundo
# ---------------------------------------------------------------------------

def _detect_background_color(rgba: np.ndarray) -> tuple[int, int, int] | None:
    """
    Descobre a cor de fundo olhando os 4 cantos da imagem: se a maioria dos
    cantos tiver a mesma cor opaca, ela e' o fundo. Cores "magicas" conhecidas
    (magenta etc.) tem prioridade.
    """
    h, w = rgba.shape[:2]
    corners = [rgba[0, 0], rgba[0, w - 1], rgba[h - 1, 0], rgba[h - 1, w - 1]]
    corners = [tuple(int(v) for v in c[:3]) for c in corners if c[3] > 0]
    if not corners:
        return None  # cantos ja transparentes

    for known in KNOWN_BG_COLORS:
        for corner in corners:
            if all(abs(corner[i] - known[i]) <= BG_TOLERANCE for i in range(3)):
                return corner

    # Cor solida repetida em pelo menos 3 cantos -> fundo generico
    from collections import Counter

    color, count = Counter(corners).most_common(1)[0]
    if count >= 3:
        return color
    return None


def remove_background(img: Image.Image) -> Image.Image:
    """
    Devolve a imagem em RGBA com o fundo transparente.

    - Se a imagem ja tem transparencia real (alpha variado), so garante RGBA.
    - Caso contrario, detecta a cor de fundo pelos cantos e a torna
      transparente com tolerancia (pega tambem os pixels de borda serrilhada).
    """
    rgba_img = img.convert("RGBA")
    rgba = np.array(rgba_img)

    alpha = rgba[:, :, 3]
    has_real_alpha = bool((alpha < 250).any())

    bg = _detect_background_color(rgba)
    if bg is None:
        return rgba_img if has_real_alpha else rgba_img

    r, g, b = (rgba[:, :, i].astype(int) for i in range(3))
    mask = (
        (abs(r - bg[0]) <= BG_TOLERANCE)
        & (abs(g - bg[1]) <= BG_TOLERANCE)
        & (abs(b - bg[2]) <= BG_TOLERANCE)
    )
    rgba[mask, 3] = 0
    return Image.fromarray(rgba, "RGBA")


# ---------------------------------------------------------------------------
# Fatiamento em quadros
# ---------------------------------------------------------------------------

def _split_ranges(profile: np.ndarray, min_size: int, min_gap: int) -> list[tuple[int, int]]:
    """
    Recebe um perfil 1D (soma de pixels opacos por coluna ou linha) e devolve
    os intervalos [inicio, fim) com conteudo, ignorando vao menores que
    `min_gap` e blocos menores que `min_size`.
    """
    occupied = profile > 0
    ranges: list[tuple[int, int]] = []
    start = None
    gap = 0
    for i, filled in enumerate(occupied):
        if filled:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                end = i - gap + 1
                if end - start >= min_size:
                    ranges.append((start, end))
                start = None
                gap = 0
    if start is not None:
        end = len(occupied)
        while end > start and not occupied[end - 1]:
            end -= 1
        if end - start >= min_size:
            ranges.append((start, end))
    return ranges


def slice_frames(
    sheet: Image.Image,
    min_size: int = 12,
    min_gap: int = 2,
    max_frames: int = 200,
) -> list[Frame]:
    """
    Fatia um spritesheet (ja sem fundo) em quadros individuais.

    Algoritmo: projeta o canal alpha nas colunas para achar faixas verticais
    de conteudo; dentro de cada faixa, projeta nas linhas; o retangulo
    resultante e' refinado para o bounding box exato do sprite.
    """
    rgba = np.array(sheet.convert("RGBA"))
    alpha = (rgba[:, :, 3] > 16).astype(np.uint32)

    frames: list[Frame] = []
    col_profile = alpha.sum(axis=0)
    for x0, x1 in _split_ranges(col_profile, min_size, min_gap):
        strip = alpha[:, x0:x1]
        row_profile = strip.sum(axis=1)
        for y0, y1 in _split_ranges(row_profile, min_size, min_gap):
            block = alpha[y0:y1, x0:x1]
            # Bounding box exato dentro do bloco
            cols = np.where(block.sum(axis=0) > 0)[0]
            rows = np.where(block.sum(axis=1) > 0)[0]
            if cols.size == 0 or rows.size == 0:
                continue
            bx0, bx1 = x0 + int(cols[0]), x0 + int(cols[-1]) + 1
            by0, by1 = y0 + int(rows[0]), y0 + int(rows[-1]) + 1
            crop = sheet.convert("RGBA").crop((bx0, by0, bx1, by1))
            frames.append(Frame(image=crop, bbox=(bx0, by0, bx1, by1)))
            if len(frames) >= max_frames:
                return frames
    return frames


# ---------------------------------------------------------------------------
# Preparacao para o Gemini
# ---------------------------------------------------------------------------

def prepare_for_gemini(
    img: Image.Image,
    target_size: int = 512,
    margin_ratio: float = 0.08,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> Image.Image:
    """
    Prepara o sprite para o Image-to-Image:
      - centraliza em uma tela quadrada com margem,
      - amplia com NEAREST (preserva o visual pixelado, sem borrar),
      - aplica fundo branco solido (o Gemini trabalha melhor com fundo de
        alto contraste do que com alpha; a transparencia e' recuperada
        depois com remove_background()).
    """
    img = img.convert("RGBA")
    w, h = img.size
    side = max(w, h)
    margin = int(side * margin_ratio)
    canvas_side = side + 2 * margin

    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(img, ((canvas_side - w) // 2, (canvas_side - h) // 2), img)

    if canvas_side < target_size:
        scale = max(1, target_size // canvas_side)
        canvas = canvas.resize(
            (canvas_side * scale, canvas_side * scale), Image.NEAREST
        )

    flat = Image.new("RGBA", canvas.size, background)
    flat.paste(canvas, (0, 0), canvas)
    return flat.convert("RGB")


def save_png(img: Image.Image, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path
