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


# ---------------------------------------------------------------------------
# Biblioteca de acoes para animacao (Etapa 2)
# ---------------------------------------------------------------------------
#
# Cada acao descreve o arco do movimento quadro a quadro. Os textos entram no
# prompt como descricao de POSE — a identidade do personagem vem sempre da
# imagem de referencia, nunca do texto.

ACTIONS: dict[str, dict] = {
    "Ataque com arma": {
        "emoji": "⚔️",
        "resumo": "Golpe descendente com a arma em mãos.",
        "poses": [
            "de guarda, arma recuada ao lado do corpo, joelhos levemente flexionados",
            "arma erguida acima da cabeca, tronco girado para tras acumulando forca",
            "inicio do golpe descendente, braco se esticando para frente",
            "momento do impacto, arma a frente na altura do alvo, corpo projetado para frente",
            "arma completando o arco para baixo, corpo inclinado a frente",
            "retornando a posicao de guarda inicial",
        ],
    },
    "Defesa / bloqueio": {
        "emoji": "🛡️",
        "resumo": "Levanta a guarda e absorve o impacto.",
        "poses": [
            "em pe, relaxado, guarda baixa",
            "comecando a erguer o braco e o escudo a frente do corpo",
            "escudo erguido cobrindo o tronco, corpo agachado atras da protecao",
            "recebendo o impacto: corpo empurrado para tras, pes firmes, escudo tremendo",
            "recuperando a postura, escudo ainda erguido",
        ],
    },
    "Avanço rápido / investida": {
        "emoji": "💨",
        "resumo": "Arranca para frente em corrida ou investida.",
        "poses": [
            "posicao de largada, corpo inclinado a frente, uma perna recuada",
            "impulso inicial, perna de tras empurrando o chao, tronco bem inclinado",
            "no ar em pleno avanco, pernas afastadas em passada longa, braços recuados",
            "aterrissando a frente, perna dianteira absorvendo o impacto",
            "corrida em velocidade maxima, braços cortando o ar",
        ],
    },
    "Caminhada": {
        "emoji": "🚶",
        "resumo": "Ciclo de caminhada lateral, para locomoção no mapa.",
        "poses": [
            "passo com a perna direita a frente, braco esquerdo a frente",
            "pernas se cruzando, corpo no ponto mais alto do ciclo",
            "passo com a perna esquerda a frente, braco direito a frente",
            "pernas se cruzando novamente, completando o ciclo",
        ],
    },
    "Parado (idle)": {
        "emoji": "🧍",
        "resumo": "Respiração leve para o personagem não ficar estático.",
        "poses": [
            "em pe, postura neutra, peito normal",
            "peito levemente expandido inspirando, ombros um pouco mais altos",
            "peito no ponto maximo da inspiracao, cabeca minimamente erguida",
            "expirando, ombros descendo de volta a postura neutra",
        ],
    },
    "Conjurar magia": {
        "emoji": "✨",
        "resumo": "Canaliza e lança um feitiço.",
        "poses": [
            "em pe, começando a erguer as maos, olhar concentrado",
            "maos erguidas a frente do peito, energia se formando entre elas",
            "energia concentrada e brilhante, corpo tensionado, cabelo e vestes agitados",
            "liberando o feitico: bracos esticados a frente, corpo projetado",
            "apos o disparo, bracos ainda estendidos, corpo relaxando",
        ],
    },
    "Recebendo dano": {
        "emoji": "💥",
        "resumo": "Reação a um golpe recebido.",
        "poses": [
            "em pe, postura normal",
            "cabeca e tronco jogados para tras pelo impacto, bracos abertos",
            "cambaleando para tras, um pe recuando para nao cair",
            "recuperando o equilibrio, voltando a postura de guarda",
        ],
    },
    "Queda / morte": {
        "emoji": "☠️",
        "resumo": "Personagem é derrotado e cai.",
        "poses": [
            "em pe, corpo comecando a ceder, ombros caidos",
            "joelhos dobrando, tronco inclinando a frente",
            "caindo de joelhos, bracos pendendo",
            "corpo tombando de lado em direcao ao chao",
            "deitado no chao, imovel",
        ],
    },
}


def action_options() -> list[str]:
    """Nomes das acoes prefixados com emoji, para o seletor da interface."""
    return [f"{dados['emoji']} {nome}" for nome, dados in ACTIONS.items()]


def strip_action_emoji(label: str) -> str:
    for nome in ACTIONS:
        if label.endswith(nome):
            return nome
    return label


def poses_for_action(action_name: str, n_frames: int, custom_action: str = "") -> list[str]:
    """
    Devolve `n_frames` descricoes de pose distribuidas ao longo do movimento.

    Se o usuario descreveu uma acao propria, gera descricoes genericas de arco
    de movimento (inicio -> meio -> fim) com base no texto dele.
    """
    if custom_action.strip():
        base = custom_action.strip()
        if n_frames == 1:
            return [base]
        etapas = []
        for i in range(n_frames):
            fracao = i / (n_frames - 1)
            if fracao == 0:
                etapas.append(f"inicio do movimento: {base}")
            elif fracao < 0.5:
                etapas.append(f"movimento em andamento ({int(fracao*100)}% concluido): {base}")
            elif fracao == 0.5:
                etapas.append(f"ponto central e mais intenso do movimento: {base}")
            elif fracao < 1:
                etapas.append(f"movimento se completando ({int(fracao*100)}%): {base}")
            else:
                etapas.append(f"final do movimento, retornando ao repouso: {base}")
        return etapas

    poses = ACTIONS.get(action_name, {}).get("poses", ["em pe, postura neutra"])
    if n_frames >= len(poses):
        return poses[:n_frames] if n_frames <= len(poses) else poses + [poses[-1]] * (n_frames - len(poses))
    # Amostra uniforme ao longo do arco (mantem inicio e fim)
    passo = (len(poses) - 1) / (n_frames - 1) if n_frames > 1 else 0
    return [poses[round(i * passo)] for i in range(n_frames)]


def build_prompt(filter_name: str, extra_instructions: str = "", custom_style: str = "") -> str:
    """Monta o prompt final a partir do filtro escolhido (ou estilo livre)."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    extra = ""
    if extra_instructions.strip():
        extra = f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
    return PROMPT_TEMPLATE.format(style=style, extra=extra)


# ---------------------------------------------------------------------------
# Biblioteca de acoes para animacao (Etapa 2)
# ---------------------------------------------------------------------------
#
# Cada acao descreve o arco do movimento quadro a quadro. Os textos entram no
# prompt como descricao de POSE — a identidade do personagem vem sempre da
# imagem de referencia, nunca do texto.

ACTIONS: dict[str, dict] = {
    "Ataque com arma": {
        "emoji": "⚔️",
        "resumo": "Golpe descendente com a arma em mãos.",
        "poses": [
            "de guarda, arma recuada ao lado do corpo, joelhos levemente flexionados",
            "arma erguida acima da cabeca, tronco girado para tras acumulando forca",
            "inicio do golpe descendente, braco se esticando para frente",
            "momento do impacto, arma a frente na altura do alvo, corpo projetado para frente",
            "arma completando o arco para baixo, corpo inclinado a frente",
            "retornando a posicao de guarda inicial",
        ],
    },
    "Defesa / bloqueio": {
        "emoji": "🛡️",
        "resumo": "Levanta a guarda e absorve o impacto.",
        "poses": [
            "em pe, relaxado, guarda baixa",
            "comecando a erguer o braco e o escudo a frente do corpo",
            "escudo erguido cobrindo o tronco, corpo agachado atras da protecao",
            "recebendo o impacto: corpo empurrado para tras, pes firmes, escudo tremendo",
            "recuperando a postura, escudo ainda erguido",
        ],
    },
    "Avanço rápido / investida": {
        "emoji": "💨",
        "resumo": "Arranca para frente em corrida ou investida.",
        "poses": [
            "posicao de largada, corpo inclinado a frente, uma perna recuada",
            "impulso inicial, perna de tras empurrando o chao, tronco bem inclinado",
            "no ar em pleno avanco, pernas afastadas em passada longa, braços recuados",
            "aterrissando a frente, perna dianteira absorvendo o impacto",
            "corrida em velocidade maxima, braços cortando o ar",
        ],
    },
    "Caminhada": {
        "emoji": "🚶",
        "resumo": "Ciclo de caminhada lateral, para locomoção no mapa.",
        "poses": [
            "passo com a perna direita a frente, braco esquerdo a frente",
            "pernas se cruzando, corpo no ponto mais alto do ciclo",
            "passo com a perna esquerda a frente, braco direito a frente",
            "pernas se cruzando novamente, completando o ciclo",
        ],
    },
    "Parado (idle)": {
        "emoji": "🧍",
        "resumo": "Respiração leve para o personagem não ficar estático.",
        "poses": [
            "em pe, postura neutra, peito normal",
            "peito levemente expandido inspirando, ombros um pouco mais altos",
            "peito no ponto maximo da inspiracao, cabeca minimamente erguida",
            "expirando, ombros descendo de volta a postura neutra",
        ],
    },
    "Conjurar magia": {
        "emoji": "✨",
        "resumo": "Canaliza e lança um feitiço.",
        "poses": [
            "em pe, começando a erguer as maos, olhar concentrado",
            "maos erguidas a frente do peito, energia se formando entre elas",
            "energia concentrada e brilhante, corpo tensionado, cabelo e vestes agitados",
            "liberando o feitico: bracos esticados a frente, corpo projetado",
            "apos o disparo, bracos ainda estendidos, corpo relaxando",
        ],
    },
    "Recebendo dano": {
        "emoji": "💥",
        "resumo": "Reação a um golpe recebido.",
        "poses": [
            "em pe, postura normal",
            "cabeca e tronco jogados para tras pelo impacto, bracos abertos",
            "cambaleando para tras, um pe recuando para nao cair",
            "recuperando o equilibrio, voltando a postura de guarda",
        ],
    },
    "Queda / morte": {
        "emoji": "☠️",
        "resumo": "Personagem é derrotado e cai.",
        "poses": [
            "em pe, corpo comecando a ceder, ombros caidos",
            "joelhos dobrando, tronco inclinando a frente",
            "caindo de joelhos, bracos pendendo",
            "corpo tombando de lado em direcao ao chao",
            "deitado no chao, imovel",
        ],
    },
}


def action_options() -> list[str]:
    """Nomes das acoes prefixados com emoji, para o seletor da interface."""
    return [f"{dados['emoji']} {nome}" for nome, dados in ACTIONS.items()]


def strip_action_emoji(label: str) -> str:
    for nome in ACTIONS:
        if label.endswith(nome):
            return nome
    return label


def poses_for_action(action_name: str, n_frames: int, custom_action: str = "") -> list[str]:
    """
    Devolve `n_frames` descricoes de pose distribuidas ao longo do movimento.

    Se o usuario descreveu uma acao propria, gera descricoes genericas de arco
    de movimento (inicio -> meio -> fim) com base no texto dele.
    """
    if custom_action.strip():
        base = custom_action.strip()
        if n_frames == 1:
            return [base]
        etapas = []
        for i in range(n_frames):
            fracao = i / (n_frames - 1)
            if fracao == 0:
                etapas.append(f"inicio do movimento: {base}")
            elif fracao < 0.5:
                etapas.append(f"movimento em andamento ({int(fracao*100)}% concluido): {base}")
            elif fracao == 0.5:
                etapas.append(f"ponto central e mais intenso do movimento: {base}")
            elif fracao < 1:
                etapas.append(f"movimento se completando ({int(fracao*100)}%): {base}")
            else:
                etapas.append(f"final do movimento, retornando ao repouso: {base}")
        return etapas

    poses = ACTIONS.get(action_name, {}).get("poses", ["em pe, postura neutra"])
    if n_frames >= len(poses):
        return poses[:n_frames] if n_frames <= len(poses) else poses + [poses[-1]] * (n_frames - len(poses))
    # Amostra uniforme ao longo do arco (mantem inicio e fim)
    passo = (len(poses) - 1) / (n_frames - 1) if n_frames > 1 else 0
    return [poses[round(i * passo)] for i in range(n_frames)]


def build_prompt(filter_name: str, extra_instructions: str = "", custom_style: str = "") -> str:
    """Monta o prompt final a partir do filtro escolhido (ou estilo livre)."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    extra = ""
    if extra_instructions.strip():
        extra = f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
    return PROMPT_TEMPLATE.format(style=style, extra=extra)


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
) -> tuple[Image.Image, str]:
    """
    Pipeline Img2Img (Etapa 1): envia (imagem base + prompt) e devolve a
    imagem gerada — um personagem unico, reestilizado.

    Parametros:
      base_image          sprite original ja preparado (ver prepare_for_gemini)
      filter_name         nome de um filtro de FILTERS
      extra_instructions  texto livre do usuario ("adicione uma capa", etc.)
      custom_style        descricao de estilo customizada (substitui o filtro)
      creativity          0.0 a 1.0 -> mapeado para a temperature do modelo;
                          valores altos geram resultados mais distintos do
                          original (bom para evitar copia direta)
      api_key             sobrescreve a variavel de ambiente, se informado

    Retorna (imagem_gerada, prompt_utilizado).

    Para animar o personagem gerado, veja generate_action_sheet() e
    generate_action_frames() (Etapa 2).
    """
    from google.genai import types

    client = _get_client(api_key)

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
            # Chave recusada nao melhora com nova tentativa: avisa na hora.
            _raise_if_auth_error(exc)
            last_error = exc
        time.sleep(2 ** attempt)

    raise RuntimeError(f"Falha ao gerar imagem apos {max_retries} tentativas: {last_error}")


# ---------------------------------------------------------------------------
# Resultado de um quadro gerado
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


# ---------------------------------------------------------------------------
# Etapa 2 — Animar um personagem JA gerado
# ---------------------------------------------------------------------------
#
# Aqui o personagem gerado na Etapa 1 e' a UNICA referencia visual, e a pose
# vem de texto. Isso elimina a causa da inconsistencia do modo anterior: nao
# ha uma segunda imagem, com outro estilo, competindo pela aparencia final.

SHEET_PROMPT_TEMPLATE = (
    "A imagem fornecida mostra UM personagem de jogo 2D. Ele e' a referencia "
    "definitiva e imutavel de aparencia. "
    "Gere UMA UNICA imagem contendo uma TIRA HORIZONTAL de exatamente "
    "{n_frames} quadros de animacao desse MESMO personagem executando a acao: "
    "{acao}. "
    "As poses, na ordem da esquerda para a direita, devem ser: {poses}. "
    "REGRAS OBRIGATORIAS: "
    "(1) CONSISTENCIA ABSOLUTA: em todos os {n_frames} quadros o personagem "
    "deve ter exatamente as mesmas cores, a mesma armadura e roupas, o mesmo "
    "cabelo, a mesma arma e os mesmos detalhes da imagem de referencia. Nada "
    "de design pode mudar entre os quadros — apenas a pose. "
    "(2) LAYOUT: os {n_frames} quadros lado a lado em uma unica linha, "
    "igualmente espacados, separados por espaco branco vazio, sem molduras, "
    "sem numeros e sem qualquer texto. "
    "(3) ALINHAMENTO: todos os quadros na MESMA escala, com o personagem do "
    "mesmo tamanho e os pes na MESMA altura em todos eles, para que a "
    "animacao nao trema. "
    "(4) O fundo de toda a imagem deve ser branco solido puro (#FFFFFF). "
    "(5) Mantenha o mesmo estilo artistico e a mesma perspectiva da imagem de "
    "referencia. "
    "{extra}"
)

POSE_PROMPT_TEMPLATE = (
    "A imagem fornecida mostra UM personagem de jogo 2D. Ele e' a referencia "
    "definitiva e imutavel de aparencia. "
    "Gere um novo sprite unico do MESMO personagem, sem alterar nada do seu "
    "design, agora nesta pose: {pose}. "
    "Contexto do movimento: {acao} (quadro {i} de {n_frames}). "
    "REGRAS OBRIGATORIAS: "
    "(1) CONSISTENCIA ABSOLUTA: copie exatamente as cores, a armadura, as "
    "roupas, o cabelo, a arma e todos os detalhes da imagem de referencia. "
    "NAO redesenhe nem reinterprete o personagem — apenas mude a pose. "
    "(2) Mantenha a MESMA escala, o mesmo enquadramento e a mesma altura dos "
    "pes da imagem de referencia, para que os quadros se alinhem na animacao. "
    "(3) Mantenha o mesmo estilo artistico e a mesma perspectiva. "
    "(4) O fundo deve ser branco solido puro (#FFFFFF), sem sombras "
    "projetadas, sem cenario, sem molduras e sem texto. "
    "{extra}"
)


def generate_action_sheet(
    character_image: Image.Image,
    action_name: str,
    n_frames: int = 4,
    custom_action: str = "",
    extra_instructions: str = "",
    api_key: str | None = None,
    max_retries: int = 3,
) -> tuple[Image.Image, str]:
    """
    Gera TODOS os quadros de uma acao em UMA unica chamada, como uma tira.

    E' o metodo mais consistente que existe para este caso: como tudo sai de
    uma unica geracao, o personagem nao tem como divergir de si mesmo entre os
    quadros. Depois a tira e' fatiada em quadros individuais.

    Retorna (imagem_da_tira, prompt_utilizado).
    """
    from google.genai import types

    client = _get_client(api_key)
    acao = custom_action.strip() or ACTIONS.get(action_name, {}).get(
        "resumo", action_name
    )
    poses = poses_for_action(action_name, n_frames, custom_action)
    poses_texto = "; ".join(f"quadro {i + 1}: {p}" for i, p in enumerate(poses))
    extra = (
        f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
        if extra_instructions.strip()
        else ""
    )
    prompt = SHEET_PROMPT_TEMPLATE.format(
        n_frames=n_frames, acao=acao, poses=poses_texto, extra=extra
    )

    config = types.GenerateContentConfig(
        temperature=0.35,  # baixa: fidelidade ao personagem acima de tudo
        response_modalities=["TEXT", "IMAGE"],
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=[prompt, character_image],
                config=config,
            )
            image = _extract_image(response)
            if image is not None:
                return image, prompt
            last_error = RuntimeError(
                "O modelo respondeu sem imagem (possivel bloqueio de "
                "seguranca). Tente outra acao ou menos quadros."
            )
        except Exception as exc:
            _raise_if_auth_error(exc)
            last_error = exc
        time.sleep(2 ** attempt)

    raise RuntimeError(f"Falha ao gerar a tira de animacao: {last_error}")


def generate_action_frames(
    character_image: Image.Image,
    action_name: str,
    n_frames: int = 4,
    custom_action: str = "",
    extra_instructions: str = "",
    api_key: str | None = None,
    pause_between: float = 1.0,
    progress_callback=None,
) -> list[FrameResult]:
    """
    Gera os quadros da acao um a um (uma chamada por quadro).

    Da mais controle sobre cada pose, mas cada chamada pode desviar um pouco
    do personagem. Use quando a tira unica sair com quadros mal separados.
    """
    acao = custom_action.strip() or ACTIONS.get(action_name, {}).get(
        "resumo", action_name
    )
    poses = poses_for_action(action_name, n_frames, custom_action)
    extra = (
        f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
        if extra_instructions.strip()
        else ""
    )

    resultados: list[FrameResult] = []
    for i, pose in enumerate(poses):
        if progress_callback:
            progress_callback(i, n_frames, f"Gerando quadro {i + 1} de {n_frames}...")
        prompt = POSE_PROMPT_TEMPLATE.format(
            pose=pose, acao=acao, i=i + 1, n_frames=n_frames, extra=extra
        )
        try:
            if i and pause_between:
                time.sleep(pause_between)
            image = _single_image_call(prompt, character_image, api_key, temperature=0.3)
            resultados.append(FrameResult(i, image))
        except Exception as exc:
            resultados.append(FrameResult(i, None, error=str(exc)))
    if progress_callback:
        progress_callback(n_frames, n_frames, "Concluido.")
    return resultados


def _single_image_call(
    prompt: str,
    image: Image.Image,
    api_key: str | None,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> Image.Image:
    """Uma chamada Img2Img simples, com retry e erro de autenticacao imediato."""
    from google.genai import types

    client = _get_client(api_key)
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_modalities=["TEXT", "IMAGE"],
    )
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=IMAGE_MODEL, contents=[prompt, image], config=config
            )
            result = _extract_image(response)
            if result is not None:
                return result
            last_error = RuntimeError("o modelo respondeu sem imagem")
        except Exception as exc:
            _raise_if_auth_error(exc)
            last_error = exc
        time.sleep(2 ** attempt)
    raise RuntimeError(f"apos {max_retries} tentativas: {last_error}")


def _raise_if_auth_error(exc: Exception) -> None:
    """Chave recusada nao melhora com retry: interrompe na hora."""
    texto = str(exc).upper()
    if any(
        marca in texto
        for marca in (
            "API_KEY_INVALID", "API KEY NOT VALID", "PERMISSION_DENIED",
            "UNAUTHENTICATED", "401", "403",
        )
    ):
        raise RuntimeError(
            "A chave da API foi recusada pelo Google. Confira se voce copiou a "
            "chave inteira de https://aistudio.google.com/apikey e se a cota da "
            f"conta esta ativa. (resposta do servidor: {exc})"
        ) from exc


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
