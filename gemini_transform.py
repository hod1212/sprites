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

# ---------------------------------------------------------------------------
# Intensidade da alteracao (escala 1 a 10)
# ---------------------------------------------------------------------------
#
# So mexer na `temperature` nao controla QUANTO o desenho muda — ela controla
# a aleatoriedade da geracao. O que realmente define o grau de alteracao e' a
# INSTRUCAO. Por isso cada nivel tem seu proprio texto de regra, e a
# temperatura acompanha em segundo plano.

INTENSITY_LEVELS: dict[int, dict] = {
    1: {
        "rotulo": "Praticamente idêntico",
        "descricao": "Só um leve tratamento de cor. O sprite continua o mesmo.",
        "regra": (
            "PRESERVE o design original quase por completo. Mantenha exatamente "
            "as mesmas roupas, a mesma armadura, a mesma arma, o mesmo cabelo e "
            "os mesmos acessorios. Faca APENAS um leve ajuste de paleta e de "
            "acabamento na direcao do estilo indicado — como se fosse uma "
            "correcao de cor sutil. O resultado deve ser reconhecido de imediato "
            "como o MESMO personagem da imagem original."
        ),
        "temperatura": 0.15,
    },
    2: {
        "rotulo": "Retoque leve",
        "descricao": "Mesmo personagem, com acabamento e sombreamento melhores.",
        "regra": (
            "PRESERVE o design original. Mantenha as mesmas pecas de roupa, "
            "armadura, arma e cabelo, sem trocar nenhuma delas. Refine o "
            "sombreamento, o contraste e pequenos detalhes de textura na direcao "
            "do estilo indicado. O personagem deve continuar claramente o mesmo."
        ),
        "temperatura": 0.25,
    },
    3: {
        "rotulo": "Ajuste sutil",
        "descricao": "Mesmas peças de equipamento, cores puxadas para o estilo.",
        "regra": (
            "Mantenha o design original claramente reconhecivel: as mesmas pecas "
            "de equipamento e a mesma arma. Ajuste as cores, os materiais e o "
            "sombreamento na direcao do estilo indicado, sem substituir nenhuma "
            "peca por outra diferente."
        ),
        "temperatura": 0.35,
    },
    4: {
        "rotulo": "Reestilização branda",
        "descricao": "Mesmo equipamento, materiais e ornamentos repaginados.",
        "regra": (
            "Mantenha o tipo de cada peca de equipamento (mesma categoria de "
            "armadura, mesmo tipo de arma) e a identidade geral do personagem. "
            "Repagine os materiais, as cores e os ornamentos no estilo indicado. "
            "Alguem que conheca o sprite original deve reconhece-lo na hora."
        ),
        "temperatura": 0.45,
    },
    5: {
        "rotulo": "Equilibrado",
        "descricao": "Silhueta e tipo de equipamento preservados, visual novo.",
        "regra": (
            "Mantenha a silhueta e o tipo de equipamento (se usa armadura "
            "pesada, continua com armadura pesada; se usa manto, continua com "
            "manto). Reimagine materiais, cores, texturas e detalhes no estilo "
            "indicado. O resultado deve parecer uma versao alternativa do mesmo "
            "personagem."
        ),
        "temperatura": 0.6,
    },
    6: {
        "rotulo": "Reimaginação moderada",
        "descricao": "Mesma classe e silhueta, roupas e cores redesenhadas.",
        "regra": (
            "Mantenha a pose, as proporcoes, a silhueta e a classe do "
            "personagem. Redesenhe as roupas, a armadura, as cores e os detalhes "
            "no estilo indicado. O resultado deve ser um personagem novo, mas da "
            "mesma classe e com a mesma presenca visual."
        ),
        "temperatura": 0.7,
    },
    7: {
        "rotulo": "Reimaginação forte",
        "descricao": "Só pose e proporções se mantêm; o resto é novo.",
        "regra": (
            "Mantenha estritamente a MESMA pose, as proporcoes e a silhueta "
            "geral. Reimagine COMPLETAMENTE as roupas, a armadura, as cores e os "
            "detalhes no estilo indicado. O design final deve ser claramente "
            "diferente do original em identidade visual, ainda que reconhecivel "
            "como a mesma pose e classe."
        ),
        "temperatura": 0.8,
    },
    8: {
        "rotulo": "Personagem novo",
        "descricao": "Outro personagem, na mesma pose e silhueta.",
        "regra": (
            "Mantenha apenas a pose, as proporcoes e a silhueta. Crie um "
            "personagem NOVO e inedito no estilo indicado: outro equipamento, "
            "outra paleta, outra identidade visual. Nao deve ser possivel dizer "
            "que e' o mesmo personagem — apenas que esta na mesma pose."
        ),
        "temperatura": 0.9,
    },
    9: {
        "rotulo": "Reinvenção",
        "descricao": "Design totalmente novo; a pose serve só de esqueleto.",
        "regra": (
            "Use a imagem apenas como esqueleto de pose. Crie um personagem "
            "completamente novo no estilo indicado, com equipamento, silhueta de "
            "detalhes, paleta e identidade totalmente proprios. Preserve somente "
            "a postura corporal e o enquadramento."
        ),
        "temperatura": 1.0,
    },
    10: {
        "rotulo": "Completamente diferente",
        "descricao": "Personagem inédito; mantém apenas a postura corporal.",
        "regra": (
            "Use a imagem APENAS como referencia de postura corporal e "
            "enquadramento. Crie um personagem totalmente inedito e original no "
            "estilo indicado, sem qualquer relacao visual com o original alem da "
            "posicao do corpo. Seja ousado e criativo no design."
        ),
        "temperatura": 1.15,
    },
}

DEFAULT_INTENSITY = 7


def intensity_info(intensity: int) -> dict:
    """Devolve rotulo, descricao, regra e temperatura de um nivel 1..10."""
    nivel = max(1, min(10, int(intensity)))
    return INTENSITY_LEVELS[nivel]


PROMPT_TEMPLATE = (
    "A partir do sprite de personagem 2D fornecido na imagem, gere um sprite "
    "2D no estilo indicado. "
    "GRAU DE ALTERACAO SOLICITADO: {intensidade} de 10 ({rotulo}). "
    "{regra_intensidade} "
    "ESTILO VISUAL ALVO: {style}. "
    "REGRAS FIXAS (valem em qualquer grau de alteracao): "
    "(1) Mantenha estritamente a MESMA pose, proporcoes, anatomia e silhueta "
    "do sprite original — nao mude a posicao de bracos, pernas, cabeca ou "
    "arma. "
    "(2) O fundo deve ser 100% branco solido puro (#FFFFFF), sem sombras "
    "projetadas, sem cenario, sem molduras e sem texto. "
    "(3) Nao altere a perspectiva nem o enquadramento: o personagem deve "
    "ocupar a mesma area da imagem que o sprite original. "
    "(4) Entregue um unico personagem, de corpo inteiro, centralizado. "
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
    # ---------------- LOCOMOCAO ----------------
    "Parado (idle)": {
        "emoji": "🧍",
        "resumo": "Respiração leve em posição de prontidão — o loop básico de qualquer jogo.",
        "poses": [
            "postura de prontidao: pes afastados na largura dos ombros, joelhos levemente "
            "flexionados, arma segurada em posicao de descanso, ombros relaxados, peito neutro",
            "inspirando: peito expande sutilmente, ombros sobem 1-2 pixels, cabeca ergue "
            "minimamente, arma acompanha a leve subida do corpo",
            "pico da inspiracao: peito no maximo, ombros no ponto mais alto, corpo levemente "
            "mais alongado que na pose 1",
            "expirando: ombros e peito descem de volta, corpo retorna exatamente a postura "
            "da primeira pose para fechar o loop",
        ],
    },
    "Andar": {
        "emoji": "🚶",
        "resumo": "Ciclo de caminhada completo, pronto para loop.",
        "poses": [
            "contato: perna direita estendida a frente com calcanhar tocando o chao, perna "
            "esquerda atras com dedos empurrando, braco esquerdo balanca a frente e o direito "
            "atras (oposicao), tronco ereto",
            "passagem: pernas se cruzam sob o corpo, joelho esquerdo levantado passando a "
            "frente, corpo no ponto mais ALTO do ciclo, bracos alinhados ao corpo",
            "contato espelhado: perna esquerda estendida a frente tocando o chao, perna "
            "direita atras empurrando, braco direito a frente e esquerdo atras",
            "passagem espelhada: joelho direito levantado passando a frente, corpo alto "
            "novamente, fechando o loop de volta a primeira pose",
        ],
    },
    "Correr": {
        "emoji": "🏃",
        "resumo": "Corrida com tronco inclinado e passada larga.",
        "poses": [
            "impulso: tronco inclinado ~20 graus a frente, perna direita empurrando o chao "
            "atras, joelho esquerdo erguendo a frente, bracos flexionados 90 graus em oposicao",
            "suspensao: AMBOS os pes fora do chao, passada larga no ar, perna esquerda "
            "estendida a frente e direita dobrada atras, bracos em oposicao maxima",
            "aterrissagem: pe esquerdo toca o chao sob o corpo, joelho absorvendo, perna "
            "direita vindo por tras, tronco ainda inclinado",
            "impulso espelhado: perna esquerda empurra atras, joelho direito erguendo a "
            "frente, bracos trocados",
            "suspensao espelhada: ambos os pes no ar, perna direita estendida a frente e "
            "esquerda dobrada atras",
            "aterrissagem espelhada: pe direito toca o chao sob o corpo, fechando o loop",
        ],
    },
    "Pular": {
        "emoji": "🦘",
        "resumo": "Salto vertical completo: impulso, subida, ápice e aterrissagem.",
        "poses": [
            "antecipacao: agachado profundo, joelhos bem dobrados, tronco inclinado a frente, "
            "bracos recuados atras do corpo prontos para lancar",
            "lancamento: pernas estendendo com forca, corpo esticando para cima, bracos "
            "lancados para o alto, dedos dos pes deixando o chao",
            "apice: corpo totalmente no ar, pernas levemente dobradas sob o corpo, bracos "
            "acima da cabeca, ponto mais alto do salto",
            "queda: corpo descendo, pernas estendendo em direcao ao chao, bracos abaixando "
            "para equilibrar",
            "aterrissagem: pes tocando o chao, joelhos dobrando fundo para absorver o "
            "impacto, tronco inclinado a frente, bracos a frente equilibrando",
        ],
    },
    "Investida / dash": {
        "emoji": "💨",
        "resumo": "Arranque explosivo para frente, com linhas de velocidade.",
        "poses": [
            "preparacao: corpo abaixado em posicao de largada, uma perna recuada, tronco "
            "inclinado a frente, punhos fechados",
            "explosao: perna de tras empurra com forca total, corpo disparando a frente "
            "quase horizontal, bracos cortando o ar",
            "velocidade maxima: corpo lancado a frente em passada longa no ar, cabelo e "
            "roupas esvoacando para tras, leves linhas de velocidade atras do personagem",
            "chegada: perna dianteira crava no chao freando, corpo ainda inclinado pela "
            "inercia, poeira leve nos pes",
            "recuperacao: corpo se erguendo de volta a postura de prontidao",
        ],
    },
    "Esquiva / rolamento": {
        "emoji": "🤸",
        "resumo": "Rolamento defensivo no chão, saindo em posição de guarda.",
        "poses": [
            "reacao: corpo abaixando rapido, joelhos dobrando, tronco encolhendo, bracos "
            "recolhendo junto ao peito",
            "entrada no rolamento: corpo mergulhando a frente, cabeca escondida, costas "
            "curvadas formando uma bola",
            "meio do rolamento: corpo totalmente enrolado em bola rolando no chao, pernas "
            "recolhidas sobre o corpo",
            "saida do rolamento: pes voltando a tocar o chao, corpo desenrolando, tronco "
            "se erguendo",
            "guarda: agachado em posicao de prontidao, arma de volta a posicao de defesa, "
            "pronto para agir",
        ],
    },
    # ---------------- COMBATE ----------------
    "Ataque de corte (arma branca)": {
        "emoji": "⚔️",
        "resumo": "Golpe de espada/machado em arco — só para armas de corte.",
        "poses": [
            "guarda: pes afastados, joelhos flexionados, arma branca segurada firme na "
            "diagonal a frente do corpo",
            "preparacao: arma erguida acima e atras do ombro, tronco girado para tras "
            "acumulando torque, peso na perna de tras",
            "inicio do corte: arma iniciando o arco descendente, tronco comecando a girar "
            "para frente, peso transferindo para a perna da frente",
            "impacto: arma cruzando a frente do corpo na diagonal, braco totalmente "
            "estendido, tronco girado para frente, leve rastro do movimento da lamina",
            "acompanhamento: arma completando o arco do lado oposto do corpo, tronco "
            "totalmente girado, peso na perna da frente",
            "recuperacao: arma voltando a posicao de guarda inicial",
        ],
    },
    "Estocada (lança/adaga)": {
        "emoji": "🗡️",
        "resumo": "Golpe perfurante em linha reta — lança, rapieira ou adaga.",
        "poses": [
            "guarda: corpo de perfil, arma apontada a frente na altura do peito, perna "
            "dianteira leve, peso na perna de tras",
            "recuo: arma puxada para tras junto ao corpo, cotovelo dobrado, corpo "
            "comprimindo como uma mola, peso todo na perna de tras",
            "avanco: perna dianteira dando um passo largo a frente, arma disparando em "
            "linha reta, braco estendendo",
            "extensao maxima: braco e arma totalmente estendidos a frente na horizontal, "
            "corpo alongado em linha, perna de tras esticada",
            "retorno: arma recolhendo, corpo voltando a posicao de guarda",
        ],
    },
    "Ataque desarmado (soco/chute)": {
        "emoji": "👊",
        "resumo": "Combo corpo a corpo sem arma.",
        "poses": [
            "guarda de luta: punhos erguidos na altura do rosto, joelhos flexionados, "
            "corpo levemente de perfil",
            "preparacao: quadril e ombro girando para tras, punho direito recuado junto "
            "a cintura",
            "soco: punho direito disparado a frente com o braco estendido, quadril girado "
            "para frente, peso na perna dianteira",
            "acompanhamento: braco recolhendo enquanto o corpo gira, joelho esquerdo "
            "comecando a subir para o chute",
            "chute: perna esquerda estendida em chute frontal na altura do tronco, bracos "
            "equilibrando, tronco levemente recuado",
        ],
    },
    "Tiro (arma de fogo)": {
        "emoji": "🔫",
        "resumo": "Mirar e atirar com pistola ou rifle, com recuo realista.",
        "poses": [
            "pronto-baixo: arma de fogo segurada com as duas maos apontada para o chao a "
            "frente, pes afastados, joelhos levemente flexionados",
            "mirando: arma erguida na linha dos olhos, coronha firme no ombro (ou bracos "
            "estendidos se for pistola), bochecha proxima da arma, corpo levemente de perfil",
            "disparo: clarao de tiro na boca do cano, arma empurrada para tras pelo recuo, "
            "ombros absorvendo, leve fumaca",
            "recuperacao do recuo: arma voltando a linha de mira, corpo reassentando, "
            "fumaca se dissipando",
            "pronto-baixo final: arma abaixada de volta a posicao inicial de prontidao",
        ],
    },
    "Disparo de arco": {
        "emoji": "🏹",
        "resumo": "Sacar, tensionar e soltar a flecha.",
        "poses": [
            "prontidao: arco segurado abaixado, flecha ja encaixada na corda, corpo de "
            "perfil para o alvo",
            "erguendo: arco subindo para a linha dos olhos, braco do arco estendendo, mao "
            "da corda comecando a puxar",
            "tensao maxima: corda puxada ate a bochecha, cotovelo alto atras, arco "
            "totalmente flexionado, corpo firme ancorado",
            "disparo: corda solta vibrando, flecha saindo em linha reta, mao da corda "
            "aberta atras da cabeca, arco inclinando levemente a frente",
            "descanso: arco abaixando de volta, corpo relaxando a tensao",
        ],
    },
    "Conjurar magia": {
        "emoji": "✨",
        "resumo": "Canalizar energia e lançar o feitiço.",
        "poses": [
            "concentracao: maos comecando a se erguer a frente do peito, olhar fixo, pes "
            "firmes no chao",
            "canalizacao: maos em concha a frente do peito com uma pequena esfera de "
            "energia brilhando entre elas, cabelo e vestes comecando a flutuar",
            "carga maxima: esfera de energia grande e intensa, bracos tremendo de tensao, "
            "cabelo e vestes flutuando com forca, leve brilho iluminando o personagem",
            "lancamento: bracos estendidos com forca a frente, energia disparada, corpo "
            "projetado a frente, vestes chicoteando para tras",
            "exaustao: bracos abaixando lentamente, ultimas particulas de energia se "
            "dissipando, postura relaxando",
        ],
    },
    "Defesa / bloqueio": {
        "emoji": "🛡️",
        "resumo": "Levantar a guarda e aguentar o impacto.",
        "poses": [
            "alerta: corpo em prontidao, escudo (ou arma em posicao defensiva cruzada a "
            "frente) comecando a subir",
            "guarda fechada: escudo ou arma cobrindo o tronco e o rosto, corpo agachado "
            "atras da protecao, pes bem plantados",
            "impacto: corpo empurrado alguns pixels para tras, joelhos dobrando fundo, "
            "escudo/arma tremendo com pequenas faiscas do golpe, pes arrastando",
            "resistindo: corpo firmando de volta a posicao, empurrando contra a pressao",
            "recuperacao: guarda abrindo, corpo voltando a prontidao",
        ],
    },
    # ---------------- REACAO ----------------
    "Recebendo dano": {
        "emoji": "💥",
        "resumo": "Reação ao golpe sofrido, com recuo.",
        "poses": [
            "impacto: cabeca e tronco chicoteados para tras, olhos fechados com forca, "
            "bracos abertos soltos, arma quase escapando da mao",
            "recuo: corpo cambaleando um passo para tras, um pe arrastando, tronco ainda "
            "arqueado",
            "quase caindo: joelho baixando perto do chao, mao buscando apoio, corpo no "
            "limite do equilibrio",
            "recuperacao: corpo se reerguendo com esforco, arma reassumida, voltando a "
            "guarda com expressao de dor",
        ],
    },
    "Queda / morte": {
        "emoji": "☠️",
        "resumo": "Derrota: o personagem desaba até ficar imóvel.",
        "poses": [
            "golpe final: corpo arqueado para tras, bracos abertos, arma escapando da mao",
            "cedendo: joelhos dobrando, tronco despencando a frente, ombros caidos",
            "de joelhos: caido de joelhos no chao, bracos pendendo sem forca, cabeca baixa",
            "tombando: corpo desabando de lado em direcao ao chao",
            "imovel: deitado no chao de lado, olhos fechados, arma caida ao lado",
        ],
    },
    "Vitória / comemoração": {
        "emoji": "🏆",
        "resumo": "Celebração após vencer — clássico de fim de batalha.",
        "poses": [
            "alivio: postura relaxando apos o combate, ombros baixando, leve sorriso",
            "impulso de alegria: joelhos dobrando para saltar, bracos recuando",
            "salto comemorativo: pequeno pulo com o punho (ou a arma) erguido ao alto, "
            "expressao radiante",
            "pose de vitoria: aterrissado com o punho ou arma erguida ao ceu, peito "
            "estufado, postura triunfante",
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


def build_prompt(
    filter_name: str,
    extra_instructions: str = "",
    custom_style: str = "",
    intensity: int = DEFAULT_INTENSITY,
) -> str:
    """Monta o prompt final: estilo escolhido + grau de alteracao (1 a 10)."""
    style = custom_style.strip() or FILTERS.get(filter_name, filter_name)
    extra = ""
    if extra_instructions.strip():
        extra = f"Instrucoes adicionais do usuario: {extra_instructions.strip()}."
    nivel = intensity_info(intensity)
    return PROMPT_TEMPLATE.format(
        style=style,
        extra=extra,
        intensidade=max(1, min(10, int(intensity))),
        rotulo=nivel["rotulo"],
        regra_intensidade=nivel["regra"],
    )


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
    intensity: int = DEFAULT_INTENSITY,
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
      intensity           1 a 10 — quanto o sprite deve ser alterado. 1 mantem
                          o desenho praticamente igual (so tratamento de cor);
                          10 cria um personagem completamente novo, mantendo
                          apenas a postura. Controla tanto a INSTRUCAO enviada
                          ao modelo quanto a temperatura (ver INTENSITY_LEVELS)
      api_key             sobrescreve a variavel de ambiente, se informado

    Retorna (imagem_gerada, prompt_utilizado).

    Para animar o personagem gerado, veja generate_action_sheet() e
    generate_action_frames() (Etapa 2).
    """
    from google.genai import types

    client = _get_client(api_key)

    prompt = build_prompt(filter_name, extra_instructions, custom_style, intensity)
    temperature = intensity_info(intensity)["temperatura"]
    # Imagem antes do texto: ancora melhor a geracao na referencia visual.
    contents = [base_image, prompt]

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

# Bloco de fidelidade reaproveitado nos dois metodos. E' deliberadamente
# exaustivo e repetitivo: modelos de imagem tendem a "reinterpretar" o
# personagem, e enumerar item por item o que deve ser copiado — junto de uma
# lista explicita de proibicoes — e' o que segura o desenho no lugar.
FIDELITY_RULES = (
    "FIDELIDADE AO PERSONAGEM — esta e' a regra mais importante de todas: "
    "trate a imagem de referencia como uma FOLHA DE MODELO oficial que deve ser "
    "copiada fielmente. O personagem gerado precisa ser o MESMO em cada detalhe: "
    "a mesma cor exata de cada peca de roupa e de armadura; o mesmo formato de "
    "capacete, chapeu ou penteado; a mesma cor de cabelo; a mesma arma (mesmo "
    "tipo, mesmo tamanho, mesma cor, mesmo formato de lamina ou ponta); os "
    "mesmos acessorios (capa, manto, cinto, ombreiras, luvas, botas); a mesma "
    "paleta de cores; o mesmo tom de pele; as mesmas proporcoes corporais; e o "
    "mesmo estilo de traco e de sombreamento. "
    "E' PROIBIDO: trocar a arma por outra; mudar a cor de qualquer peca; "
    "acrescentar elementos que nao existem na referencia; remover elementos que "
    "existem nela; alterar as proporcoes do corpo; mudar o estilo artistico; "
    "trocar o personagem por outro parecido. "
    "A UNICA coisa que pode mudar e' a POSE do corpo. Se houver duvida sobre "
    "algum detalhe, copie exatamente o que esta na imagem de referencia."
)

SHEET_PROMPT_TEMPLATE = (
    "A imagem fornecida mostra UM personagem de jogo 2D. Ele e' a referencia "
    "definitiva e imutavel de aparencia. "
    "Gere UMA UNICA imagem contendo uma TIRA HORIZONTAL de exatamente "
    "{n_frames} quadros de animacao desse MESMO personagem executando a acao: "
    "{acao}. "
    "As poses, na ordem da esquerda para a direita, devem ser: {poses}. "
    "{fidelidade} "
    "REGRAS DE MOVIMENTO: "
    "(1) MOVIMENTO CONTINUO: os quadros sao instantes CONSECUTIVOS e "
    "igualmente espacados no tempo de UM UNICO movimento fluido, na ordem "
    "temporal exata descrita acima. A mudanca entre um quadro e o seguinte "
    "deve ser pequena e progressiva — como fotogramas de um filme. Nenhum "
    "quadro pode fugir da sequencia nem repetir outro. "
    "(2) ARMA DO PERSONAGEM: execute a acao com a arma e o equipamento que o "
    "personagem JA possui na imagem de referencia, adaptando a empunhadura de "
    "forma natural. NUNCA troque a arma por outra nem acrescente equipamentos. "
    "Se a descricao das poses citar um item que o personagem nao tem, adapte o "
    "gesto ao que ele realmente carrega. "
    "REGRAS DE LAYOUT: "
    "(3) Os {n_frames} quadros lado a lado em uma unica linha, igualmente "
    "espacados, separados por espaco branco vazio, sem molduras, sem numeros e "
    "sem qualquer texto. "
    "(4) ALINHAMENTO: todos os quadros na MESMA escala, com o personagem do "
    "mesmo tamanho e os pes na MESMA altura em todos eles, para que a animacao "
    "nao trema. "
    "(5) Em TODOS os {n_frames} quadros o personagem deve ser identico ao da "
    "referencia — nenhum detalhe de design pode variar de um quadro para o "
    "outro. "
    "(6) O fundo de toda a imagem deve ser branco solido puro (#FFFFFF). "
    "(7) Mantenha o mesmo estilo artistico e a mesma perspectiva da referencia. "
    "{extra}"
)

POSE_PROMPT_TEMPLATE = (
    "A imagem fornecida mostra UM personagem de jogo 2D. Ele e' a referencia "
    "definitiva e imutavel de aparencia. "
    "Sua tarefa e' REPOSICIONAR esse personagem — nao redesenha-lo. Gere um "
    "unico sprite do MESMO personagem, com o design exatamente igual, agora "
    "nesta pose: {pose}. "
    "Contexto do movimento: {acao} (quadro {i} de {n_frames} — a pose deve "
    "ser exatamente este instante do movimento, coerente com o quadro "
    "anterior e o seguinte da sequencia). "
    "{fidelidade} "
    "REGRAS ADICIONAIS: "
    "(1) ARMA DO PERSONAGEM: execute o gesto com a arma e o equipamento que o "
    "personagem JA possui na referencia, adaptando a empunhadura de forma "
    "natural. Se a descricao da pose citar um item que ele nao tem, adapte o "
    "gesto ao que ele realmente carrega — nunca troque nem invente equipamento. "
    "(2) Mantenha a MESMA escala, o mesmo enquadramento e a mesma altura dos "
    "pes da imagem de referencia, para que os quadros se alinhem na animacao. "
    "(3) Mantenha o mesmo estilo artistico e a mesma perspectiva. "
    "(4) O fundo deve ser branco solido puro (#FFFFFF), sem sombras "
    "projetadas, sem cenario, sem molduras e sem texto. "
    "{extra}"
)

# Temperatura minima nos dois metodos: aqui nao queremos criatividade nenhuma,
# so fidelidade ao personagem de referencia.
ANIMATION_TEMPERATURE = 0.12


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
        n_frames=n_frames,
        acao=acao,
        poses=poses_texto,
        fidelidade=FIDELITY_RULES,
        extra=extra,
    )

    config = types.GenerateContentConfig(
        temperature=ANIMATION_TEMPERATURE,  # minima: fidelidade acima de tudo
        response_modalities=["TEXT", "IMAGE"],
    )

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=IMAGE_MODEL,
                # Imagem primeiro: ancora a geracao na referencia visual.
                contents=[character_image, prompt],
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
            pose=pose,
            acao=acao,
            i=i + 1,
            n_frames=n_frames,
            fidelidade=FIDELITY_RULES,
            extra=extra,
        )
        try:
            if i and pause_between:
                time.sleep(pause_between)
            image = _single_image_call(
                prompt, character_image, api_key, temperature=ANIMATION_TEMPERATURE
            )
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
    temperature: float = ANIMATION_TEMPERATURE,
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
                # Imagem primeiro: ancora a geracao na referencia visual.
                model=IMAGE_MODEL, contents=[image, prompt], config=config
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
