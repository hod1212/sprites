"""
Provedor alternativo: Pollinations.ai (modelo FLUX Kontext).

IMPORTANTE — correcao de uma informacao anterior: o Pollinations NAO e'
totalmente "sem chave". Segundo a documentacao oficial
(github.com/pollinations/pollinations/blob/master/APIDOCS.md), existem tres
niveis de acesso:

  - Anonimo (sem chave): funciona sem cadastro, mas e' limitado a ~1
    requisicao a cada 15s e as imagens SAEM COM MARCA D'AGUA (o parametro
    "nologo" e' documentado como "needs account" — ou seja, so' funciona de
    verdade com uma chave/conta).
  - "Seed" (cadastro gratuito em auth.pollinations.ai): ~1 requisicao a cada
    5s e SEM marca d'agua.
  - "Flower/Nectar" (pago): limites maiores, para uso intenso.

Ou seja: da' para usar sem nenhuma chave (e por isso o motor continua
disponivel de graca nesta ferramenta), mas o resultado real sem chave inclui
marca d'agua e um limite de velocidade maior. Quem tiver uma chave/token do
Pollinations pode informa-la no app para remover a marca d'agua e acelerar as
geracoes — o campo e' opcional.

Funcionamento tecnico:
  - A API e' um simples GET: image.pollinations.ai/prompt/<texto>?image=<url>
  - A imagem de entrada precisa estar acessivel por URL publica. Como o sprite
    do usuario e' local, subimos o PNG para o tmpfiles.org, um hospedeiro
    temporario anonimo que APAGA o arquivo em ~60 minutos.
  - Por ser comunitario, pode ficar lento (30-120s) ou fora do ar em horarios
    de pico. Nesses casos, o app orienta a tentar de novo ou voltar ao Gemini.
  - O FLUX Kontext responde melhor a instrucoes curtas em ingles; os prompts
    daqui sao versoes condensadas em ingles dos prompts do Gemini, com as
    descricoes de estilo/pose embutidas.
  - A documentacao oficial nao detalha o formato exato de autenticacao para o
    endpoint de IMAGEM (so' exemplifica para o endpoint de texto). Por isso,
    quando uma chave e' informada, ela e' enviada de duas formas ao mesmo
    tempo — como parametro "token" na URL e como cabecalho "Authorization:
    Bearer" — para maximizar a chance de ser reconhecida.

Nenhuma dependencia nova: usa apenas `requests` e `Pillow`.
"""

from __future__ import annotations

import io
import random
import time
import urllib.parse

import requests
from PIL import Image

from gemini_transform import (
    ACTIONS,
    FILTERS,
    FrameResult,
    intensity_info,
    poses_for_action,
)
from redact import redact

IMAGE_ENDPOINT = "https://image.pollinations.ai/prompt/"
UPLOAD_ENDPOINT = "https://tmpfiles.org/api/v1/upload"
MODEL = "kontext"
REFERRER = "ro-sprite-forge"          # identifica o app (melhora o rate limit)
REQUEST_TIMEOUT = 180                  # geracoes podem demorar em hora de pico

# Regras de intensidade condensadas em ingles (mesma escala 1-10 do Gemini).
_INTENSITY_EN: dict[int, str] = {
    1: "Keep the character's design EXACTLY as-is; only apply a subtle color grade toward the style.",
    2: "Keep the same outfit, weapon and hair; only refine shading and finish toward the style.",
    3: "Keep every equipment piece recognizable; shift colors and materials toward the style.",
    4: "Keep each equipment type and the character's identity; restyle materials, colors and ornaments.",
    5: "Keep the silhouette and equipment type; reimagine materials, colors and details in the style.",
    6: "Keep pose, proportions, silhouette and class; redesign clothing, armor and colors in the style.",
    7: "Keep only the pose, proportions and overall silhouette; completely reimagine outfit, armor and colors.",
    8: "Keep only the pose and silhouette; create a NEW original character in the style.",
    9: "Use the image only as a pose skeleton; invent a completely new character design in the style.",
    10: "Use the image only as a body-posture reference; create a totally original, unrelated character in the style.",
}


class PollinationsError(RuntimeError):
    """Erro amigavel do provedor gratuito, com orientacao de contorno."""


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _upload_temp(img: Image.Image) -> str:
    """
    Sobe o sprite para o tmpfiles.org e devolve a URL direta do arquivo.
    O arquivo e' apagado automaticamente pelo servico em ~60 minutos.
    """
    try:
        resp = requests.post(
            UPLOAD_ENDPOINT,
            files={"file": ("sprite.png", _png_bytes(img), "image/png")},
            timeout=60,
        )
        resp.raise_for_status()
        page_url = resp.json()["data"]["url"]
    except Exception as exc:
        raise PollinationsError(
            "Nao consegui preparar a imagem para o Pollinations (o hospedeiro "
            "temporario tmpfiles.org nao respondeu). Tente novamente em "
            "instantes ou volte ao motor Gemini."
        ) from exc
    # https://tmpfiles.org/123/sprite.png -> https://tmpfiles.org/dl/123/sprite.png
    return page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)


def _generate(
    prompt: str,
    reference: Image.Image,
    width: int,
    height: int,
    api_key: str | None = None,
    max_retries: int = 2,
) -> Image.Image:
    """Uma chamada de edicao de imagem ao Pollinations, com retry."""
    ref_url = _upload_temp(reference)
    params = {
        "model": MODEL,
        "image": ref_url,
        "width": width,
        "height": height,
        "nologo": "true",     # so' remove a marca d'agua de fato com chave
        "private": "true",    # nao publicar no feed publico do servico
        "enhance": "false",   # NAO reescrever o prompt (mudaria as regras)
        "referrer": REFERRER,
        "seed": random.randint(0, 2**31 - 1),
    }
    headers = {}
    if api_key:
        # A documentacao oficial nao especifica o formato exato para o
        # endpoint de imagem, entao enviamos dos dois jeitos usados pelo
        # restante da API do Pollinations (token na URL + Bearer no cabecalho).
        params["token"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    url = IMAGE_ENDPOINT + urllib.parse.quote(prompt[:1800], safe="")

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200 and resp.headers.get(
                "content-type", ""
            ).startswith("image/"):
                return Image.open(io.BytesIO(resp.content)).convert("RGBA")
            if resp.status_code in (401, 403):
                raise PollinationsError(
                    "O Pollinations recusou a chave informada (HTTP "
                    f"{resp.status_code}). Confira se ela foi copiada "
                    "corretamente em auth.pollinations.ai, ou remova o "
                    "campo para usar o modo anônimo (com marca d'água)."
                )
            last_error = RuntimeError(
                f"resposta inesperada (HTTP {resp.status_code})"
            )
        except requests.RequestException as exc:
            last_error = exc
        # Nao dorme depois da ultima tentativa: so' atrasaria o erro final.
        if attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))

    # IMPORTANTE: a chave vai na querystring, e as excecoes do `requests`
    # costumam trazer a URL inteira. Sem esta limpeza, a chave do usuario
    # apareceria na tela do app.
    detalhe = redact(str(last_error), api_key)
    raise PollinationsError(
        "O Pollinations nao respondeu (servico comunitario — fica "
        "sobrecarregado em horarios de pico, e o modo sem chave tem limite "
        "de 1 requisicao a cada ~15s). Tente novamente em 1-2 minutos, "
        f"informe uma chave, ou volte ao motor Gemini. Detalhe tecnico: {detalhe}"
    )


# ---------------------------------------------------------------------------
# Etapa 1 — Reestilizar o personagem
# ---------------------------------------------------------------------------

def transform_sprite(
    base_image: Image.Image,
    filter_name: str,
    extra_instructions: str = "",
    custom_style: str = "",
    intensity: int = 7,
    api_key: str | None = None,
) -> tuple[Image.Image, str]:
    """Equivalente de gemini_transform.transform_sprite(), via Pollinations."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    nivel = max(1, min(10, int(intensity)))
    extra = (
        f" Additional user request: {extra_instructions.strip()}."
        if extra_instructions.strip()
        else ""
    )
    prompt = (
        f"Restyle this 2D game character sprite. Target visual style: {style}. "
        f"Change intensity {nivel}/10 ({intensity_info(nivel)['rotulo']}): "
        f"{_INTENSITY_EN[nivel]} "
        "Strict rules: keep the exact same pose, body proportions and framing; "
        "single full-body character, centered; pure solid white background "
        "(#FFFFFF), no shadows, no scenery, no frames, no text."
        f"{extra}"
    )
    w, h = base_image.size
    result = _generate(prompt, base_image, width=w, height=h, api_key=api_key)
    return result, prompt


# ---------------------------------------------------------------------------
# Etapa 2 — Animar o personagem (fidelidade maxima)
# ---------------------------------------------------------------------------

_FIDELITY_EN = (
    "CRITICAL: this is the SAME character as the reference image — copy the "
    "design faithfully: identical colors of every clothing and armor piece, "
    "identical helmet/hair, identical weapon (same type, size, color), "
    "identical accessories, palette, skin tone, body proportions and art "
    "style. Do NOT swap the weapon, change colors, add or remove elements. "
    "ONLY the body pose changes."
)


def generate_action_sheet(
    character_image: Image.Image,
    action_name: str,
    n_frames: int = 4,
    custom_action: str = "",
    extra_instructions: str = "",
    api_key: str | None = None,
) -> tuple[Image.Image, str]:
    """Equivalente de gemini_transform.generate_action_sheet(), via Pollinations."""
    acao = custom_action.strip() or ACTIONS.get(action_name, {}).get(
        "resumo", action_name
    )
    poses = poses_for_action(action_name, n_frames, custom_action)
    poses_texto = "; ".join(f"frame {i + 1}: {p}" for i, p in enumerate(poses))
    extra = (
        f" Additional user request: {extra_instructions.strip()}."
        if extra_instructions.strip()
        else ""
    )
    prompt = (
        f"Create ONE image: a horizontal sprite-sheet strip with exactly "
        f"{n_frames} animation frames of this same 2D game character "
        f"performing: {acao}. Poses left to right: {poses_texto}. "
        f"{_FIDELITY_EN} "
        "Motion rules: the frames are CONSECUTIVE, evenly-spaced moments of "
        "ONE continuous motion, in exact temporal order — small, progressive "
        "changes between neighboring frames, like film frames. Perform the "
        "action with the weapon the character already holds, adapting the "
        "grip naturally; if a pose mentions an item the character lacks, "
        "adapt the gesture to what they actually carry. "
        "Layout: frames side by side in a single row, equal spacing and equal "
        "scale, feet at the same height in every frame, separated by empty "
        "white space; no borders, no numbers, no text; pure white background "
        "(#FFFFFF)."
        f"{extra}"
    )
    w, h = character_image.size
    # Tira horizontal: largura proporcional ao numero de quadros
    out_w = min(2048, max(768, h * n_frames))
    result = _generate(prompt, character_image, width=out_w, height=h, api_key=api_key)
    return result, prompt


def generate_action_frames(
    character_image: Image.Image,
    action_name: str,
    n_frames: int = 4,
    custom_action: str = "",
    extra_instructions: str = "",
    api_key: str | None = None,
    pause_between: float = 2.0,
    progress_callback=None,
) -> list[FrameResult]:
    """Equivalente de gemini_transform.generate_action_frames(), via Pollinations."""
    acao = custom_action.strip() or ACTIONS.get(action_name, {}).get(
        "resumo", action_name
    )
    poses = poses_for_action(action_name, n_frames, custom_action)
    extra = (
        f" Additional user request: {extra_instructions.strip()}."
        if extra_instructions.strip()
        else ""
    )
    w, h = character_image.size

    resultados: list[FrameResult] = []
    for i, pose in enumerate(poses):
        if progress_callback:
            progress_callback(i, n_frames, f"Gerando quadro {i + 1} de {n_frames}...")
        prompt = (
            "Repose this exact 2D game character — do not redesign it. New "
            f"pose: {pose}. Movement context: {acao} (frame {i + 1} of "
            f"{n_frames} — this exact moment of the motion, consistent with "
            f"the previous and next frames). {_FIDELITY_EN} Perform the "
            "gesture with the weapon the character already holds, adapting "
            "the grip naturally. Keep the same scale, framing and feet "
            "height as the reference; pure white background (#FFFFFF), no "
            "shadows, no scenery, no text."
            f"{extra}"
        )
        try:
            if i and pause_between:
                time.sleep(pause_between)  # respeita o limite de requisicoes
            image = _generate(prompt, character_image, width=w, height=h, api_key=api_key)
            resultados.append(FrameResult(i, image))
        except Exception as exc:
            # O erro por quadro tambem e' exibido na interface: limpa segredos.
            resultados.append(FrameResult(i, None, error=redact(str(exc), api_key)))
    if progress_callback:
        progress_callback(n_frames, n_frames, "Concluido.")
    return resultados
