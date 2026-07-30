"""
Modulo D — Interface do usuario (Streamlit).

O fluxo tem DUAS etapas, e essa separacao e' proposital:

  ETAPA 1 — Criar o personagem
    1. Usuario descreve o personagem ("Preciso de um Cavaleiro com lanca").
    2. O app busca no indice local do Spriters Resource (construindo o indice
       na primeira execucao) e mostra os sheets candidatos.
    3. O sheet escolhido e' baixado, o fundo e' removido e o usuario decide
       entre usar a imagem inteira ou um quadro especifico.
    4. O sprite vai para o Gemini (Img2Img) com o filtro escolhido e volta UM
       personagem reestilizado.

  ETAPA 2 — Animar o personagem gerado
    5. O personagem da Etapa 1 (ou um sprite enviado) e' a UNICA referencia
       visual; as poses vem de texto (ataque, defesa, avanco, caminhada...).
       Isso e' o que garante consistencia: sem uma segunda imagem de outro
       estilo competindo, o personagem nao muda entre os quadros.
    6. Preferencialmente todos os quadros saem de UMA chamada, como uma tira
       horizontal, depois fatiada — uma geracao unica nao diverge de si mesma.
    7. Saida: previa em GIF, folha de sprites com o tamanho da celula e ZIP
       com os quadros individuais.

Rodar com:  streamlit run app.py
"""

from __future__ import annotations

import io
import traceback
import zipfile
from pathlib import Path

import streamlit as st
from PIL import Image

import pollinations_ai
import scraper
import sprite_tools
from gemini_transform import (
    ACTIONS,
    DEFAULT_INTENSITY,
    FILTER_UI,
    FILTERS,
    GeminiNotConfigured,
    action_options,
    intensity_info,
    filter_options,
    generate_action_frames,
    generate_action_sheet,
    strip_action_emoji,
    strip_emoji,
    transform_sprite,
)

st.set_page_config(page_title="RO Sprite Forge", page_icon="🗡️", layout="wide")

OUTPUT_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# Funcoes auxiliares com cache (evita repetir scraping e downloads)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def cached_index(force: bool = False):
    entries = scraper.build_index(force=force)
    return [scraper.asdict(e) for e in entries]


@st.cache_data(show_spinner=False)
def cached_download(entry_dict: dict) -> str:
    entry = scraper.SheetEntry(**entry_dict)
    return str(scraper.download_sheet(entry))


def image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Barra lateral: configuracao
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Configurações")

# IMPORTANTE: o Streamlit apaga o valor de um campo assim que ele deixa de ser
# exibido na tela. Como o campo da chave fica oculto depois de preenchido, a
# chave era perdida no clique seguinte. A solucao e' copiar o valor digitado
# para esta entrada propria de sessao, que o Streamlit nunca descarta.
KEY_STORE = "gemini_api_key_persistente"
KEY_WIDGETS = ("api_key_sidebar", "api_key_main")

if st.session_state.pop("_esquecer_chave", False):
    st.session_state[KEY_STORE] = ""
    for widget_key in KEY_WIDGETS:
        st.session_state.pop(widget_key, None)

st.session_state.setdefault(KEY_STORE, "")


def remember_api_key(widget_key: str) -> None:
    """Copia o que foi digitado num campo para a memoria persistente."""
    value = (st.session_state.get(widget_key) or "").strip()
    if value:
        st.session_state[KEY_STORE] = value


def detect_stored_key() -> str:
    """
    Procura a chave da API nas fontes automaticas, em ordem:
      1. st.secrets  -> usado no Streamlit Community Cloud
      2. variaveis de ambiente / arquivo .env -> usado na execucao local
    """
    try:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            if name in st.secrets:
                value = str(st.secrets[name]).strip()
                if value and not value.startswith("cole-sua-chave"):
                    return value
    except Exception:
        pass  # nenhum secrets.toml configurado (normal na execucao local)

    import os

    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value and not value.startswith("cole-sua-chave"):
            return value
    return ""


stored_key = detect_stored_key()

st.sidebar.text_input(
    "Chave da API Gemini",
    type="password",
    help="Cole aqui a sua chave. Crie uma grátis em "
    "https://aistudio.google.com/apikey",
    key="api_key_sidebar",
    on_change=remember_api_key,
    args=("api_key_sidebar",),
)
remember_api_key("api_key_sidebar")

typed_key = st.session_state[KEY_STORE]
api_key = typed_key or stored_key

if api_key:
    origem = "digitada" if typed_key else "configurada no servidor"
    st.sidebar.success(f"🔑 Chave {origem} — pronto para gerar!")
else:
    st.sidebar.warning("🔑 Nenhuma chave da API configurada.")

if st.sidebar.button("🔄 Reconstruir índice do site"):
    cached_index.clear()
    with st.spinner("Mapeando o Spriters Resource novamente..."):
        try:
            cached_index(force=True)
            st.sidebar.success("Índice atualizado!")
        except Exception as exc:
            st.sidebar.error(f"Falha ao reindexar: {exc}")

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚖️ Os sprites originais de Ragnarok Online pertencem à Gravity Co., Ltd. "
    "Use as gerações como estudo/inspiração e não como cópia comercial."
)

# ---------------------------------------------------------------------------
# Area principal
# ---------------------------------------------------------------------------

st.title("🗡️ RO Sprite Forge")
st.caption(
    "Busca sprites de Ragnarok Online no Spriters Resource e os reimagina "
    "com o Gemini (Image-to-Image), mantendo pose e silhueta."
)

# No celular a barra lateral fica escondida atras do menu ☰, por isso o campo
# da chave tambem aparece aqui. Ele e' SEMPRE renderizado (apenas recolhido
# quando ja existe chave): se deixasse de aparecer, o Streamlit descartaria o
# valor digitado no clique seguinte.
def campo_da_chave() -> None:
    st.text_input(
        "Chave da API Gemini",
        type="password",
        key="api_key_main",
        placeholder="AIzaSy...",
        label_visibility="collapsed",
        on_change=remember_api_key,
        args=("api_key_main",),
    )
    st.caption(
        "Crie uma chave grátis em **https://aistudio.google.com/apikey** "
        "(login com conta Google → *Create API key*). A chave fica apenas "
        "nesta sessão do navegador e não é salva em nenhum lugar."
    )


# --- Motor de IA -----------------------------------------------------------
MOTOR_GEMINI = "✨ Gemini — melhor qualidade (chave grátis com cota diária)"
MOTOR_POLLINATIONS = "🆓 Pollinations.ai — 100% grátis, sem chave (experimental)"

motor = st.radio(
    "🤖 Motor de IA",
    [MOTOR_GEMINI, MOTOR_POLLINATIONS],
    key="motor_ia",
    help="O Gemini dá os melhores resultados (a chave do aistudio.google.com "
    "é gratuita, com cota diária). O Pollinations é um serviço comunitário "
    "gratuito e sem cadastro — útil quando a cota do Gemini acabar, mas pode "
    "ficar lento ou fora do ar em horários de pico.",
)
usando_pollinations = motor == MOTOR_POLLINATIONS

if usando_pollinations:
    st.info(
        "🆓 **Modo Pollinations**: nenhuma chave é necessária. Atenção: para "
        "processar, seu sprite é enviado temporariamente ao serviço de "
        "hospedagem tmpfiles.org (apagado em ~60 min) e ao Pollinations.ai. "
        "Se a geração falhar por sobrecarga, tente de novo ou volte ao Gemini."
    )

if api_key:
    with st.expander("🔑 Chave da API configurada ✅ — toque para alterar", expanded=False):
        campo_da_chave()
        if st.button("🗑️ Esquecer a chave desta sessão"):
            st.session_state["_esquecer_chave"] = True
            st.rerun()
elif usando_pollinations:
    with st.expander("🔑 Chave do Gemini (não é necessária no modo Pollinations)"):
        campo_da_chave()
else:
    with st.container(border=True):
        st.markdown("#### 🔑 Primeiro, cole a sua chave da API do Gemini")
        campo_da_chave()

remember_api_key("api_key_main")
api_key = st.session_state[KEY_STORE] or stored_key

# Pronto para gerar: Pollinations dispensa chave; Gemini exige.
pode_gerar = usando_pollinations or bool(api_key)

def seletor_de_sprite(sheet: Image.Image, nome: str, prefixo: str) -> dict:
    """
    Interface compartilhada pelas duas abas da Etapa 1: o usuario escolhe se
    envia a imagem inteira (o Gemini le todas as poses e devolve UM
    personagem) ou um quadro isolado.

    A animacao nao acontece aqui — ela e' a Etapa 2, que parte do personagem
    ja gerado. Ver a secao "Etapa 2" mais abaixo.
    """
    escolha: dict = {"base": None, "label": nome}

    modo = st.radio(
        "Como você quer trabalhar?",
        ["🖼️ Imagem inteira (recomendado)", "🧩 Um quadro só"],
        key=f"{prefixo}_modo",
        help="Com a imagem inteira, a IA vê todas as poses do arquivo e "
        "devolve um personagem só — que você depois anima na Etapa 2.",
    )

    if modo.startswith("🖼️"):
        escolha["base"] = sheet
        st.image(sheet, caption=f"{nome} (fundo removido)")
        return escolha

    with st.spinner("Fatiando a imagem em quadros..."):
        frames = sprite_tools.slice_frames(sheet)

    if not frames:
        st.warning("Não consegui isolar quadros nesta imagem — usando ela inteira.")
        escolha["base"] = sheet
        return escolha

    st.success(f"🧩 {len(frames)} quadros detectados.")
    mapa = sprite_tools.annotate_frames(sheet, frames)
    st.image(mapa, caption="Mapa dos quadros — use estes números para escolher", use_container_width=True)

    idx = st.number_input(
        "Número do quadro (veja a numeração acima)",
        0, len(frames) - 1, 0, key=f"{prefixo}_um_idx",
    )
    escolha["base"] = frames[int(idx)].image
    escolha["label"] = f"{nome} — quadro {int(idx)}"
    st.image(escolha["base"], caption=escolha["label"], width=180)
    return escolha


tab_search, tab_upload = st.tabs(["🔎 Buscar no Spriters Resource", "📁 Enviar meu próprio sprite"])

base_sprite: Image.Image | None = None
original_label = ""
selecao: dict = {}

# --- Aba 1: busca no site ---------------------------------------------------

with tab_search:
    query = st.text_input(
        "O que você procura?",
        placeholder='Ex.: "Preciso de um Cavaleiro com lança", "Algoz", "Priest"...',
    )

    if query:
        try:
            with st.spinner("Consultando índice do Spriters Resource... (a primeira vez pode demorar ~1 min)"):
                index = cached_index()
            results = scraper.search_sheets(query, [scraper.SheetEntry(**d) for d in index])
        except Exception as exc:
            st.error(
                f"Não consegui acessar o Spriters Resource: {exc}\n\n"
                "💡 O site usa proteção Cloudflare. Verifique se o Playwright está "
                "instalado (`playwright install chromium`) ou use a aba "
                "**Enviar meu próprio sprite**."
            )
            results = []

        if query and not results:
            st.warning("Nenhum sprite encontrado. Tente outro termo (em português ou inglês).")

        if results:
            options = {f"{e.name}  ({e.section})" if e.section else e.name: e for e in results}
            chosen_label = st.selectbox(
                f"✅ {len(results)} resultado(s) — escolha o spritesheet:",
                list(options.keys()),
            )
            chosen = options[chosen_label]
            st.markdown(f"🔗 Página original: [{chosen.url}]({chosen.url})")

            try:
                with st.spinner(f"Baixando spritesheet de **{chosen.name}**..."):
                    sheet_path = cached_download(scraper.asdict(chosen))
                sheet_img = Image.open(sheet_path)
                clean_sheet = sprite_tools.remove_background(sheet_img)

                selecao = seletor_de_sprite(clean_sheet, chosen.name, "busca")
                base_sprite = selecao.get("base")
                original_label = selecao.get("label", chosen.name)
            except Exception as exc:
                st.error(f"Erro ao baixar/processar o sheet: {exc}")
                with st.expander("Detalhes técnicos"):
                    st.code(traceback.format_exc())

# --- Aba 2: upload manual (fallback para quando o site bloquear) ------------

with tab_upload:
    uploaded = st.file_uploader(
        "Envie um spritesheet ou sprite avulso (PNG/GIF/BMP)",
        type=["png", "gif", "bmp", "webp"],
    )
    if uploaded is not None:
        img = Image.open(uploaded)
        clean = sprite_tools.remove_background(img)
        selecao = seletor_de_sprite(clean, uploaded.name, "upload")
        base_sprite = selecao.get("base")
        original_label = selecao.get("label", uploaded.name)

# ---------------------------------------------------------------------------
# Transformacao com o Gemini
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("🎨 Escolha o filtro / estilo visual")

filter_label = st.selectbox(
    "Filtro pré-definido",
    filter_options(),
    label_visibility="collapsed",
)
filter_name = strip_emoji(filter_label)

emoji, resumo = FILTER_UI.get(filter_name, ("🎨", ""))
st.caption(f"**{emoji} {filter_name}** — {resumo}")
with st.expander("🔍 Ver a descrição completa que será enviada à IA"):
    st.write(FILTERS[filter_name])

with st.expander("🖌️ Ou descreva um estilo personalizado (substitui o filtro acima)"):
    custom_style = st.text_area(
        "Estilo personalizado",
        placeholder="Ex.: estilo aquarela medieval com tons pastéis e detalhes em ouro...",
        label_visibility="collapsed",
    )
if custom_style.strip():
    st.info(f"🖌️ Usando estilo personalizado: _{custom_style.strip()}_")

extra = st.text_input(
    "✏️ Instruções extras para a IA (opcional)",
    placeholder="Ex.: adicione uma capa esvoaçante, deixe a armadura dourada...",
)

# --- Grau de alteracao (1 a 10) --------------------------------------------
st.markdown("##### 🎚️ Quanto o sprite deve ser alterado?")
intensidade = st.slider(
    "Grau de alteração",
    1, 10, DEFAULT_INTENSITY,
    label_visibility="collapsed",
    help="1 = quase nenhuma alteração (mesmo sprite, só tratamento de cor). "
    "10 = personagem completamente diferente, mantendo só a postura.",
)
nivel = intensity_info(intensidade)
st.caption(f"**{intensidade}/10 — {nivel['rotulo']}:** {nivel['descricao']}")
st.progress(intensidade / 10)

if intensidade <= 2:
    st.warning(
        "⚠️ Nesse grau o resultado fica muito próximo do sprite original da "
        "Gravity — bom para testar o estilo, mas evite usar comercialmente."
    )
with st.expander("📋 Ver a regra exata enviada à IA neste grau"):
    st.write(nivel["regra"])

if base_sprite is None:
    st.info("👆 Busque um sprite ou envie um arquivo para habilitar a transformação.")
else:
    if not pode_gerar:
        st.warning(
            "🔑 Cole a sua chave da API do Gemini no campo acima (ou no menu ☰ → "
            "Configurações) — ou troque o Motor de IA para o Pollinations, que "
            "não precisa de chave."
        )
    nome_motor = "Pollinations" if usando_pollinations else "Gemini"
    if st.button(
        f"✨ Transformar sprite com {nome_motor}",
        type="primary",
        use_container_width=True,
        disabled=not pode_gerar,
    ):
        prepared = sprite_tools.prepare_for_gemini(base_sprite)
        try:
            demora = "~30-120 s" if usando_pollinations else "~10-30 s"
            with st.spinner(f"O {nome_motor} está reimaginando seu sprite... ({demora})"):
                if usando_pollinations:
                    result, used_prompt = pollinations_ai.transform_sprite(
                        prepared,
                        filter_name=filter_name,
                        extra_instructions=extra,
                        custom_style=custom_style,
                        intensity=intensidade,
                    )
                else:
                    result, used_prompt = transform_sprite(
                        prepared,
                        filter_name=filter_name,
                        extra_instructions=extra,
                        custom_style=custom_style,
                        intensity=intensidade,
                        api_key=api_key or None,
                    )
            final = sprite_tools.remove_background(result)
            st.session_state["result"] = final
            st.session_state["result_prompt"] = used_prompt
            st.session_state["result_label"] = original_label
            # Fica guardado para a Etapa 2 poder anima-lo
            st.session_state["personagem_gerado"] = final
        except GeminiNotConfigured as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro na geração: {exc}")
            with st.expander("Detalhes técnicos"):
                st.code(traceback.format_exc())

    if "result" in st.session_state and st.session_state.get("result_label") == original_label:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("🕹️ Original")
            st.image(base_sprite, use_container_width=True)
        with col_b:
            st.subheader(f"✨ Transformado — {custom_style.strip() or filter_name}")
            st.image(st.session_state["result"], use_container_width=True)

        png = image_to_png_bytes(st.session_state["result"])
        st.download_button(
            "⬇️ Baixar sprite final (PNG transparente)",
            data=png,
            file_name="sprite_transformado.png",
            mime="image/png",
            use_container_width=True,
        )
        with st.expander("📜 Prompt utilizado na geração"):
            st.write(st.session_state["result_prompt"])

        st.info(
            "👇 Gostou do personagem? Desça até a **Etapa 2** para criar as "
            "animações de movimento (ataque, defesa, avanço...) a partir dele."
        )


# ===========================================================================
# ETAPA 2 — Animar o personagem gerado
# ===========================================================================
#
# Aqui o personagem gerado na Etapa 1 e' a UNICA referencia visual: as poses
# vem de texto. E' o que garante consistencia, ja que nao existe uma segunda
# imagem (com outro estilo) competindo pela aparencia final.

st.markdown("---")
st.header("🎬 Etapa 2 — Criar animações do personagem")
st.caption(
    "Use o personagem gerado acima (ou envie um sprite pronto) para criar "
    "sequências de movimento: ataque, defesa, avanço rápido, caminhada e mais."
)

personagem: Image.Image | None = None
origem_personagem = ""

fonte = st.radio(
    "Qual personagem você quer animar?",
    ["✨ O personagem gerado na Etapa 1", "📤 Enviar um sprite já pronto"],
    key="fonte_personagem",
)

if fonte.startswith("✨"):
    if "personagem_gerado" in st.session_state:
        personagem = st.session_state["personagem_gerado"]
        origem_personagem = "etapa1"
        st.image(personagem, caption="Personagem que será animado", width=170)
    else:
        st.info(
            "Nenhum personagem gerado ainda. Faça a Etapa 1 acima, ou escolha "
            "**Enviar um sprite já pronto**."
        )
else:
    enviado_anim = st.file_uploader(
        "Envie o sprite do personagem (PNG com um personagem só)",
        type=["png", "gif", "bmp", "webp"],
        key="upload_personagem",
    )
    if enviado_anim is not None:
        personagem = sprite_tools.remove_background(Image.open(enviado_anim))
        origem_personagem = f"upload:{enviado_anim.name}"
        st.image(personagem, caption=f"Personagem: {enviado_anim.name}", width=170)

if personagem is not None:
    col_acao, col_qtd = st.columns([2, 1])
    with col_acao:
        acao_label = st.selectbox(
            "🎭 Movimento / ação",
            action_options(),
            help="16 padrões clássicos de animação de jogos 2D, organizados em "
            "locomoção, combate e reação. Escolha o ataque compatível com a "
            "arma do personagem (corte, estocada, tiro, arco...).",
        )
        acao_nome = strip_action_emoji(acao_label)
        st.caption(ACTIONS[acao_nome]["resumo"])
    poses_ideais = len(ACTIONS[acao_nome]["poses"])
    with col_qtd:
        n_quadros = st.slider(
            "Quadros", 2, 8, poses_ideais,
            help="A coreografia completa deste movimento tem "
            f"{poses_ideais} poses — esse é o valor recomendado. Menos quadros "
            "= o app escolhe os instantes-chave; mais = repete o final.",
        )
    if n_quadros != poses_ideais:
        st.caption(
            f"💡 A coreografia de **{acao_nome}** foi desenhada com "
            f"**{poses_ideais} quadros** — use esse valor para o movimento completo."
        )

    with st.expander("🎞️ Ver a coreografia quadro a quadro deste movimento"):
        for pi, pose_txt in enumerate(ACTIONS[acao_nome]["poses"], 1):
            st.markdown(f"**{pi}.** {pose_txt}")

    with st.expander("🎯 Ou descreva um movimento próprio"):
        acao_custom = st.text_area(
            "Movimento personalizado",
            placeholder="Ex.: saltando e girando a espada acima da cabeça...",
            label_visibility="collapsed",
        )
    if acao_custom.strip():
        st.info(f"🎯 Movimento personalizado: _{acao_custom.strip()}_")

    st.caption(
        "🔒 Na Etapa 2 a fidelidade é sempre **máxima**: a IA recebe a ordem de "
        "copiar o personagem detalhe por detalhe (cores, arma, armadura, "
        "cabelo, acessórios) e mudar **apenas a pose**. Aqui não existe grau de "
        "alteração — quem define o visual é a Etapa 1."
    )

    metodo = st.radio(
        "Como gerar os quadros?",
        [
            "🧷 Tira única — 1 chamada à API (mais consistente, recomendado)",
            f"🔢 Quadro a quadro — {n_quadros} chamadas (mais controle)",
        ],
        key="metodo_anim",
        help="Na tira única, todos os quadros saem de uma só geração, então o "
        "personagem não tem como mudar entre eles. É o método mais confiável.",
    )
    extra_anim = st.text_input(
        "✏️ Instruções extras para a animação (opcional)",
        placeholder="Ex.: exagere o movimento da capa, mantenha o escudo visível...",
        key="extra_anim",
    )

    if not pode_gerar:
        st.warning(
            "🔑 Configure a chave da API acima — ou troque o Motor de IA para "
            "o Pollinations, que não precisa de chave."
        )

    if st.button(
        f"🎬 Gerar animação de {n_quadros} quadros",
        type="primary",
        use_container_width=True,
        disabled=not pode_gerar,
        key="btn_anim",
    ):
        base_personagem = sprite_tools.prepare_for_gemini(personagem, target_size=640)
        assinatura = f"{origem_personagem}|{acao_nome}|{acao_custom}|{n_quadros}|{metodo}"
        try:
            if metodo.startswith("🧷"):
                demora = "~1-3 min" if usando_pollinations else "~15-45 s"
                with st.spinner(
                    f"Gerando a tira com {n_quadros} poses em uma única chamada... ({demora})"
                ):
                    if usando_pollinations:
                        tira, prompt_anim = pollinations_ai.generate_action_sheet(
                            base_personagem,
                            action_name=acao_nome,
                            n_frames=n_quadros,
                            custom_action=acao_custom,
                            extra_instructions=extra_anim,
                        )
                    else:
                        tira, prompt_anim = generate_action_sheet(
                            base_personagem,
                            action_name=acao_nome,
                            n_frames=n_quadros,
                            custom_action=acao_custom,
                            extra_instructions=extra_anim,
                            api_key=api_key or None,
                        )
                quadros = sprite_tools.split_strip(tira, n_quadros)
                falhas_anim: list[tuple[int, str]] = []
                st.session_state["anim_tira"] = sprite_tools.remove_background(tira)
            else:
                barra = st.progress(0.0, text="Iniciando...")

                def atualizar(feitos: int, total: int, mensagem: str) -> None:
                    barra.progress(feitos / total, text=f"{mensagem} ({feitos}/{total})")

                if usando_pollinations:
                    resultados = pollinations_ai.generate_action_frames(
                        base_personagem,
                        action_name=acao_nome,
                        n_frames=n_quadros,
                        custom_action=acao_custom,
                        extra_instructions=extra_anim,
                        progress_callback=atualizar,
                    )
                else:
                    resultados = generate_action_frames(
                        base_personagem,
                        action_name=acao_nome,
                        n_frames=n_quadros,
                        custom_action=acao_custom,
                        extra_instructions=extra_anim,
                        api_key=api_key or None,
                        progress_callback=atualizar,
                    )
                barra.empty()
                quadros = [
                    sprite_tools.remove_background(r.image) for r in resultados if r.ok
                ]
                falhas_anim = [(r.index, r.error) for r in resultados if not r.ok]
                prompt_anim = "Geração quadro a quadro (um prompt por pose)."
                st.session_state.pop("anim_tira", None)

            st.session_state["anim_quadros"] = quadros
            st.session_state["anim_falhas"] = falhas_anim
            st.session_state["anim_prompt"] = prompt_anim
            st.session_state["anim_assinatura"] = assinatura
            st.session_state["anim_titulo"] = acao_custom.strip() or acao_nome
        except GeminiNotConfigured as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro ao gerar a animação: {exc}")
            with st.expander("Detalhes técnicos"):
                st.code(traceback.format_exc())

    # ---------------- Resultado da animacao ----------------
    quadros_anim = st.session_state.get("anim_quadros") or []
    if quadros_anim:
        titulo = st.session_state.get("anim_titulo", "animação")
        st.success(f"✅ {len(quadros_anim)} quadros gerados — **{titulo}**")

        falhas_anim = st.session_state.get("anim_falhas") or []
        if falhas_anim:
            with st.expander(f"⚠️ {len(falhas_anim)} quadro(s) falharam"):
                for i, err in falhas_anim:
                    st.write(f"**Quadro {i}:** {err}")

        if "anim_tira" in st.session_state:
            st.markdown("##### 🧷 Tira gerada pela IA (antes do fatiamento)")
            st.image(st.session_state["anim_tira"], use_container_width=True)

        col_gif, col_frames = st.columns([1, 2])
        with col_gif:
            st.markdown("##### ▶️ Prévia animada")
            velocidade = st.slider("ms por quadro", 60, 400, 140, 20, key="gif_ms")
            try:
                gif = sprite_tools.build_gif(quadros_anim, ms_per_frame=velocidade)
                st.image(gif, caption=f"{titulo} ({len(quadros_anim)} quadros)")
            except Exception as exc:
                gif = None
                st.warning(f"Não consegui montar a prévia animada: {exc}")
        with col_frames:
            st.markdown("##### 🧩 Quadros")
            cols_q = st.columns(min(len(quadros_anim), 4))
            for i, q in enumerate(quadros_anim):
                with cols_q[i % len(cols_q)]:
                    st.image(q, caption=f"#{i}", width=110)

        colunas_grade = st.slider(
            "Colunas na folha de sprites",
            1, 8, min(len(quadros_anim), 4), key="cols_anim",
        )
        folha = sprite_tools.build_grid_sheet(quadros_anim, columns=colunas_grade)
        linhas = (len(quadros_anim) + colunas_grade - 1) // colunas_grade
        celula = (folha.width // colunas_grade, folha.height // linhas)
        st.markdown("##### 🧾 Folha de sprites (grade uniforme)")
        st.image(folha, use_container_width=True)
        st.caption(
            f"Tamanho da célula: **{celula[0]}×{celula[1]} px** — informe esse "
            "valor ao importar a folha no seu motor de jogo."
        )

        nome_arquivo = "".join(
            c if c.isalnum() else "_" for c in titulo.lower()
        )[:30] or "animacao"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, q in enumerate(quadros_anim):
                zf.writestr(f"quadros/frame_{i:02d}.png", image_to_png_bytes(q))
            zf.writestr("spritesheet.png", image_to_png_bytes(folha))
            if gif:
                zf.writestr("previa.gif", gif)
            zf.writestr(
                "LEIA-ME.txt",
                (
                    "Animacao gerada com RO Sprite Forge\r\n"
                    f"Movimento: {titulo}\r\n"
                    f"Quadros: {len(quadros_anim)}\r\n"
                    f"spritesheet.png -> grade de {colunas_grade} coluna(s), "
                    f"celula {celula[0]}x{celula[1]} px\r\n"
                    "quadros/ -> cada pose em PNG separado, fundo transparente\r\n"
                    "previa.gif -> animacao para conferir o movimento\r\n"
                ).encode("utf-8"),
            )

        st.download_button(
            "⬇️ Baixar animação (.zip: quadros + folha + GIF)",
            data=zip_buffer.getvalue(),
            file_name=f"animacao_{nome_arquivo}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            key="dl_anim_zip",
        )
        col_z1, col_z2 = st.columns(2)
        with col_z1:
            st.download_button(
                "⬇️ Só a folha de sprites (PNG)",
                data=image_to_png_bytes(folha),
                file_name=f"spritesheet_{nome_arquivo}.png",
                mime="image/png",
                use_container_width=True,
                key="dl_anim_folha",
            )
        with col_z2:
            if gif:
                st.download_button(
                    "⬇️ Só o GIF animado",
                    data=gif,
                    file_name=f"{nome_arquivo}.gif",
                    mime="image/gif",
                    use_container_width=True,
                    key="dl_anim_gif",
                )

        st.caption(
            "💡 Dica: para um jogo completo, gere uma animação por ação "
            "(ataque, defesa, caminhada...) sempre a partir do **mesmo** "
            "personagem da Etapa 1 — assim todas ficam consistentes entre si."
        )
