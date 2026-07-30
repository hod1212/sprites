"""
Modulo C — Integracao com a API do Google Gemini (Image-to-Image).

Usa a biblioteca oficial `google-genai` com o modelo de geracao/edicao de
imagens do Gemini ("gemini-2.5-flash-image", tambem conhecido como
Nano Banana), que aceita prompts multimodais: imagem base + instrucao de
texto. E' exatamente o pipeline Img2Img pedido: o sprite original entra como
referencia visual e o texto instrui a reestilizacao mantendo pose/silhueta.

A chave de API e' lida da variavel de ambiente GEMINI_API_KEY (ou do arquivo
.env na raiz do projeto). Crie a sua gratis em https://aistudio.google.com/apikey
"""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from PIL import Image

load_dotenv()  # carrega GEMINI_API_KEY do arquivo .env, se existir

# Modelo de edicao de imagem. Se o Google lancar um sucessor, basta trocar aqui.
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

# ---------------------------------------------------------------------------
# Filtros / estilos pre-definidos
# ---------------------------------------------------------------------------

FILTERS: dict[str, str] = {
    "Dark Fantasy": (
        "dark fantasy sombrio: armaduras negras com detalhes gastos, couro "
        "escuro, metal fosco com arranhoes, paleta dessaturada de cinzas, "
        "roxos profundos e vermelho sangue, leve nevoa e iluminacao dramatica "
        "de baixo contraste"
    ),
    "Sci-Fi / Cyberpunk": (
        "cyberpunk futurista: trajes tecnologicos com placas de armadura "
        "sintetica, luzes de neon ciano e magenta embutidas, visores "
        "holograficos, cabos e circuitos aparentes, paleta escura com "
        "acentos neon vibrantes"
    ),
    "Cel Shading": (
        "cel shading estilo anime moderno: contornos pretos limpos e "
        "uniformes, blocos de cor chapados com no maximo dois niveis de "
        "sombra bem definidos, cores saturadas e luminosas, visual de "
        "desenho animado de alta producao"
    ),
    "Pixel Art HD": (
        "pixel art de alta definicao (estilo hi-bit moderno): resolucao de "
        "pixels maior que o original, dithering sutil, paleta rica e "
        "harmonica, sombreamento detalhado pixel a pixel, acabamento "
        "refinado como jogos indie premiados"
    ),
    "Gothic": (
        "gotico vitoriano: vestes longas escuras com rendas e brocados, "
        "detalhes em prata envelhecida, cruzes e filigranas ornamentais, "
        "paleta de pretos, bordos e cinza-perola, atmosfera melancolica"
    ),
    "Steampunk": (
        "steampunk: engrenagens de latao, tubos de cobre e vapor, couro "
        "envelhecido com fivelas, oculos de aviador, paleta de marrons, "
        "bronze e verde-petroleo"
    ),
    "Aquarela": (
        "pintura em aquarela: bordas suaves com sangramento de tinta, "
        "texturas de papel, cores translucidas em camadas, contorno fino a "
        "nanquim, estilo de ilustracao de livro de fantasia"
    ),
    "Pixel Art Retrô 16-bit": (
        "pixel art retro autentica de console 16-bit (era SNES/Mega Drive): "
        "paleta reduzida e limitada, pixels grandes e visiveis, sombreamento "
        "em poucos tons chapados, contorno escuro definido, sem anti-aliasing, "
        "estetica de JRPG classico dos anos 90"
    ),
    "Realismo Pintado": (
        "ilustracao realista pintada a oleo digital: materiais com textura "
        "convincente (metal escovado, couro trabalhado, tecido com dobras "
        "reais), volumetria e iluminacao coerente, pinceladas visiveis, "
        "acabamento de arte conceitual de RPG premium"
    ),
    "Chibi Kawaii": (
        "estilo chibi fofo japones: proporcoes exageradas com cabeca grande e "
        "corpo pequeno, tracos arredondados e macios, cores pastel vibrantes, "
        "olhos grandes e expressivos, visual adoravel de mascote"
    ),
    "Elemental Fogo": (
        "tematica elemental de fogo e magma: armadura incandescente com veios "
        "de lava brilhante, brasas e fagulhas suspensas, tecidos que parecem "
        "chama viva, paleta de laranjas, vermelhos e amarelos incandescentes "
        "sobre metal escurecido pelo calor"
    ),
    "Elemental Gelo": (
        "tematica elemental de gelo: armadura cristalina translucida com "
        "arestas de gelo, mantos brancos com detalhes prateados, cristais "
        "geometricos e vapor frio, paleta de ciano, branco e azul profundo "
        "com brilho glacial"
    ),
    "Sacro / Divino": (
        "estetica sacra e divina: armadura dourada polida com gravacoes "
        "sagradas, panos brancos imaculados, halos e ornamentos angelicais, "
        "luz radiante suave, paleta de dourado, marfim e azul celeste"
    ),
}

# Emoji + explicacao curta para a interface (ordem de exibicao no seletor).
FILTER_UI: dict[str, tuple[str, str]] = {
    "Dark Fantasy": ("🌑", "Sombrio e pesado — armaduras negras, paleta dessaturada, ar de RPG brutal."),
    "Sci-Fi / Cyberpunk": ("🤖", "Futurista — placas sintéticas, neon ciano/magenta e circuitos à vista."),
    "Cel Shading": ("🎬", "Anime moderno — contornos limpos e cores chapadas de animação."),
    "Pixel Art HD": ("🧩", "Pixel art refinada — mais detalhe e paleta rica, estilo indie premiado."),
    "Pixel Art Retrô 16-bit": ("🕹️", "Nostálgico — pixels grandes e paleta limitada de SNES/Mega Drive."),
    "Gothic": ("🕯️", "Gótico vitoriano — rendas, prata envelhecida e melancolia."),
    "Steampunk": ("⚙️", "Engrenagens de latão, vapor, couro e óculos de aviador."),
    "Aquarela": ("🎨", "Pintura suave — tinta que sangra no papel, ar de livro ilustrado."),
    "Realismo Pintado": ("🖼️", "Arte conceitual — materiais realistas e pinceladas visíveis."),
    "Chibi Kawaii": ("🧸", "Fofo — cabeça grande, traços redondos e cores pastel."),
    "Elemental Fogo": ("🔥", "Incandescente — veios de lava, brasas e metal aquecido."),
    "Elemental Gelo": ("❄️", "Glacial — cristais translúcidos, prata e azul profundo."),
    "Sacro / Divino": ("✨", "Divino — ouro polido, panos brancos e luz radiante."),
}


def filter_options() -> list[str]:
    """Nomes dos filtros na ordem de exibicao, prefixados com emoji."""
    return [f"{FILTER_UI.get(name, ('🎨',''))[0]} {name}" for name in FILTER_UI if name in FILTERS]


def strip_emoji(label: str) -> str:
    """Converte o rotulo exibido ('🌑 Dark Fantasy') no nome real do filtro."""
    for name in FILTERS:
        if label.endswith(name):
            return name
    return label

PROMPT_TEMPLATE = (
    "A partir do sprite de personagem 2D fornecido na imagem, gere um NOVO "
    "sprite estilizado e inedito. REGRAS OBRIGATORIAS: "
    "(1) Mantenha estritamente a MESMA pose, proporcoes, anatomia e silhueta "
    "do sprite original — nao mude a posicao de bracos, pernas, cabeca ou "
    "arma. "
    "(2) Reimagine completamente as roupas, armaduras, cores e detalhes no "
    "seguinte estilo: {style}. "
    "(3) O design final deve ser claramente DIFERENTE do original em "
    "identidade visual (outro personagem, inspirado mas nao copiado), porem "
    "reconhecivel como a mesma pose e classe. "
    "(4) O fundo deve ser 100% branco solido puro (#FFFFFF), sem sombras "
    "projetadas, sem cenario, sem molduras e sem texto. "
    "(5) Nao altere a perspectiva nem o enquadramento: o personagem deve "
    "ocupar a mesma area da imagem que o sprite original. "
    "{extra}"
)


# Prompt usado nos quadros seguintes de uma animacao: recebe DUAS imagens —
# o personagem ja estilizado (referencia de identidade) e o quadro original
# (referencia de pose). E' o que garante que a animacao mostre o MESMO
# personagem se movendo, e nao um personagem diferente por quadro.
ANIM_PROMPT_TEMPLATE = (
    "Voce recebeu duas imagens. "
    "A IMAGEM 1 e' a folha de identidade do personagem: define exatamente "
    "quem ele e' — roupas, armadura, cores, cabelo, arma e todos os detalhes "
    "de design. A IMAGEM 2 e' um quadro de animacao do sprite original e "
    "define apenas a POSE. "
    "Gere um unico sprite novo que seja O MESMO PERSONAGEM da IMAGEM 1 "
    "executando exatamente a POSE da IMAGEM 2. REGRAS OBRIGATORIAS: "
    "(1) CONSISTENCIA ABSOLUTA de personagem: copie fielmente da IMAGEM 1 as "
    "mesmas cores, o mesmo formato de armadura e roupas, o mesmo cabelo, a "
    "mesma arma e os mesmos detalhes. NAO invente nem altere nenhum elemento "
    "do design — esta e' a regra mais importante, pois os quadros serao usados "
    "em sequencia como animacao. "
    "(2) Copie da IMAGEM 2 apenas a pose: posicao de bracos, pernas, tronco, "
    "cabeca, direcao em que o personagem olha e angulo da arma. "
    "(3) Mantenha a mesma escala, proporcoes e enquadramento da IMAGEM 1, para "
    "que os quadros se alinhem perfeitamente na animacao. "
    "(4) O estilo visual continua sendo: {style}. "
    "(5) O fundo deve ser 100% branco solido puro (#FFFFFF), sem sombras "
    "projetadas, sem cenario, sem molduras e sem texto. "
    "{extra}"
)


def build_prompt(filter_name: str, extra_instructions: str = "", custom_style: str = "") -> str:
    """Monta o prompt final a partir do filtro escolhido (ou estilo livre)."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    extra = ""
    if extra_instructions.strip():
        extra = f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
    return PROMPT_TEMPLATE.format(style=style, extra=extra)


def build_animation_prompt(
    filter_name: str, extra_instructions: str = "", custom_style: str = ""
) -> str:
    """Prompt dos quadros seguintes, com referencia de personagem + de pose."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    extra = ""
    if extra_instructions.strip():
        extra = f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
    return ANIM_PROMPT_TEMPLATE.format(style=style, extra=extra)


# ---------------------------------------------------------------------------
# Chamada a API
# ---------------------------------------------------------------------------

class GeminiNotConfigured(RuntimeError):
    pass


def _get_client(api_key: str | None = None):
    from google import genai

    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise GeminiNotConfigured(
            "Chave da API nao encontrada. Defina GEMINI_API_KEY no arquivo "
            ".env ou informe a chave na barra lateral do aplicativo. "
            "Crie uma chave gratis em https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=key)


def transform_sprite(
    base_image: Image.Image,
    filter_name: str,
    extra_instructions: str = "",
    custom_style: str = "",
    creativity: float = 0.7,
    api_key: str | None = None,
    max_retries: int = 3,
    reference_image: Image.Image | None = None,
) -> tuple[Image.Image, str]:
    """
    Pipeline Img2Img: envia (imagem base + prompt) e devolve a imagem gerada.

    Parametros:
      base_image          sprite original ja preparado (ver prepare_for_gemini)
      filter_name         nome de um filtro de FILTERS
      extra_instructions  texto livre do usuario ("adicione uma capa", etc.)
      custom_style        descricao de estilo customizada (substitui o filtro)
      creativity          0.0 a 1.0 -> mapeado para a temperature do modelo;
                          valores altos geram resultados mais distintos do
                          original (bom para evitar copia direta)
      api_key             sobrescreve a variavel de ambiente, se informado
      reference_image     quando informado, ativa o modo animacao: o sprite ja
                          estilizado entra como referencia de IDENTIDADE do
                          personagem e `base_image` passa a definir apenas a
                          POSE — e' o que mantem o mesmo personagem em todos os
                          quadros de um ciclo de animacao

    Retorna (imagem_gerada, prompt_utilizado).
    """
    from google.genai import types

    client = _get_client(api_key)

    modo_animacao = reference_image is not None
    if modo_animacao:
        prompt = build_animation_prompt(filter_name, extra_instructions, custom_style)
        # Temperatura baixa e fixa: nos quadros seguintes queremos fidelidade
        # ao personagem, nao criatividade (que quebraria a consistencia).
        temperature = 0.25
        contents = [
            "IMAGEM 1 — referencia de identidade do personagem:",
            reference_image,
            "IMAGEM 2 — quadro original que define apenas a pose:",
            base_image,
            prompt,
        ]
    else:
        prompt = build_prompt(filter_name, extra_instructions, custom_style)
        # temperature 0.55..1.15: nunca tao baixa a ponto de "clonar" o original
        temperature = 0.55 + 0.6 * max(0.0, min(1.0, creativity))
        contents = [prompt, base_image]

    config = types.GenerateContentConfig(
        temperature=temperature,
        response_modalities=["TEXT", "IMAGE"],
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=contents,
                config=config,
            )
            image = _extract_image(response)
            if image is not None:
                return image, prompt
            last_error = RuntimeError(
                "O modelo respondeu sem imagem (possivel bloqueio de "
                "seguranca). Tente outro filtro ou outro quadro do sprite."
            )
        except Exception as exc:  # erros de rede/quota -> retry com backoff
            # Chave invalida ou sem permissao nao melhora com nova tentativa:
            # avisa na hora, em vez de insistir por quase um minuto.
            texto = str(exc).upper()
            if any(
                marca in texto
                for marca in (
                    "API_KEY_INVALID", "API KEY NOT VALID", "PERMISSION_DENIED",
                    "UNAUTHENTICATED", "401", "403",
                )
            ):
                raise RuntimeError(
                    "A chave da API foi recusada pelo Google. Confira se voce "
                    "copiou a chave inteira de https://aistudio.google.com/apikey "
                    "e se o faturamento/cota da conta esta ativo. "
                    f"(resposta do servidor: {exc})"
                ) from exc
            last_error = exc
        time.sleep(2 ** attempt)

    raise RuntimeError(f"Falha ao gerar imagem apos {max_retries} tentativas: {last_error}")


# ---------------------------------------------------------------------------
# Modo animacao: varios quadros com o MESMO personagem
# ---------------------------------------------------------------------------

@dataclass
class FrameResult:
    """Resultado da transformacao de um quadro da animacao."""

    index: int                      # posicao do quadro na lista enviada
    image: Image.Image | None       # sprite gerado (None se falhou)
    error: str = ""                 # motivo da falha, quando houver

    @property
    def ok(self) -> bool:
        return self.image is not None


def transform_animation_frames(
    frames: list[Image.Image],
    filter_name: str,
    extra_instructions: str = "",
    custom_style: str = "",
    creativity: float = 0.7,
    api_key: str | None = None,
    reference_index: int = 0,
    pause_between: float = 1.0,
    progress_callback=None,
) -> tuple[list[FrameResult], Image.Image | None]:
    """
    Transforma varios quadros mantendo o MESMO personagem em todos.

    Estrategia (a mesma usada para consistencia de personagem em producao):
      1. O quadro `reference_index` e' transformado normalmente e define o
         design do personagem (roupas, cores, arma...).
      2. Cada quadro seguinte e' gerado com DUAS imagens: o personagem ja
         estilizado (identidade) + o quadro original (pose). Assim a sequencia
         mostra o mesmo personagem se movendo, e nao personagens diferentes.

    Um quadro que falhar nao interrompe os demais: ele volta com `error`
    preenchido, e os quadros bem-sucedidos continuam utilizaveis.

    `progress_callback(concluidos, total, mensagem)` permite atualizar a
    barra de progresso da interface.

    Retorna (lista de FrameResult na ordem original, imagem de referencia).
    """
    if not frames:
        return [], None

    reference_index = max(0, min(reference_index, len(frames) - 1))
    total = len(frames)
    results: list[FrameResult | None] = [None] * total

    def relatar(feitos: int, mensagem: str) -> None:
        if progress_callback:
            progress_callback(feitos, total, mensagem)

    # --- Passo 1: o quadro de referencia define o personagem ---------------
    relatar(0, f"Criando o design do personagem (quadro {reference_index + 1})...")
    reference_image, _ = transform_sprite(
        frames[reference_index],
        filter_name=filter_name,
        extra_instructions=extra_instructions,
        custom_style=custom_style,
        creativity=creativity,
        api_key=api_key,
    )
    results[reference_index] = FrameResult(reference_index, reference_image)
    relatar(1, "Design do personagem definido. Gerando as demais poses...")

    # --- Passo 2: demais quadros herdam a identidade do personagem --------
    feitos = 1
    for i, frame in enumerate(frames):
        if i == reference_index:
            continue
        try:
            if pause_between:
                time.sleep(pause_between)  # respeita o limite de requisicoes
            image, _ = transform_sprite(
                frame,
                filter_name=filter_name,
                extra_instructions=extra_instructions,
                custom_style=custom_style,
                creativity=creativity,
                api_key=api_key,
                reference_image=reference_image,
            )
            results[i] = FrameResult(i, image)
        except Exception as exc:
            results[i] = FrameResult(i, None, error=str(exc))
        feitos += 1
        relatar(feitos, f"Quadro {feitos} de {total} processado.")

    return [r for r in results if r is not None], reference_image


def _extract_image(response) -> Image.Image | None:
    """Percorre as partes da resposta multimodal e devolve a primeira imagem."""
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                return Image.open(io.BytesIO(inline.data)).convert("RGBA")
    return None


if __name__ == "__main__":
    # Teste rapido via terminal:  python gemini_transform.py caminho/sprite.png
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else None
    if not src:
        print("Uso: python gemini_transform.py <sprite.png> [nome-do-filtro]")
        raise SystemExit(1)
    style = sys.argv[2] if len(sys.argv) > 2 else "Dark Fantasy"

    from sprite_tools import prepare_for_gemini, remove_background

    original = Image.open(src)
    prepared = prepare_for_gemini(remove_background(original))
    result, used_prompt = transform_sprite(prepared, style)
    out = "output/resultado.png"
    os.makedirs("output", exist_ok=True)
    remove_background(result).save(out)
    print(f"[OK] Sprite transformado salvo em {out}\nPrompt: {used_prompt}")
