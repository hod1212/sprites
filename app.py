"""
Modulo D — Interface do usuario (Streamlit).

Fluxo completo:
  1. Usuario descreve o personagem ("Preciso de um Cavaleiro com lanca").
  2. O app busca no indice local do Spriters Resource (construindo o indice
     na primeira execucao) e mostra os sheets candidatos.
  3. O sheet escolhido e' baixado, o fundo e' removido e o usuario decide
     entre usar o sheet inteiro ou um quadro/direcao especifica.
  4. O sprite vai para o Gemini (Img2Img) com o filtro de estilo escolhido.
  5. Original e resultado aparecem lado a lado, com botao de download.

Rodar com:  streamlit run app.py
"""

from __future__ import annotations

import io
import traceback
from pathlib import Path

import streamlit as st
from PIL import Image

import scraper
import sprite_tools
from gemini_transform import FILTERS, GeminiNotConfigured, transform_sprite

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

api_key = st.sidebar.text_input(
    "Chave da API Gemini",
    type="password",
    help="Deixe em branco para usar a variável GEMINI_API_KEY do arquivo .env. "
    "Crie uma chave grátis em https://aistudio.google.com/apikey",
)

filter_name = st.sidebar.selectbox("🎨 Filtro / Estilo visual", list(FILTERS.keys()))
custom_style = st.sidebar.text_area(
    "Ou descreva um estilo personalizado",
    placeholder="Ex.: estilo aquarela medieval com tons pastéis...",
    help="Se preenchido, substitui o filtro selecionado acima.",
)
creativity = st.sidebar.slider(
    "🎲 Nível de variação (criatividade)",
    0.0, 1.0, 0.7, 0.05,
    help="Valores altos geram resultados mais diferentes do original — "
    "recomendado para garantir um sprite inédito.",
)

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

tab_search, tab_upload = st.tabs(["🔎 Buscar no Spriters Resource", "📁 Enviar meu próprio sprite"])

base_sprite: Image.Image | None = None
original_label = ""

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

                mode = st.radio(
                    "Como você quer trabalhar?",
                    ["Sheet inteiro", "Quadro / direção específica"],
                    horizontal=True,
                )

                if mode == "Sheet inteiro":
                    base_sprite = clean_sheet
                    original_label = chosen.name
                    st.image(clean_sheet, caption=f"{chosen.name} (fundo removido)")
                else:
                    with st.spinner("Fatiando o sheet em quadros..."):
                        frames = sprite_tools.slice_frames(clean_sheet)
                    if not frames:
                        st.warning("Não consegui isolar quadros — usando o sheet inteiro.")
                        base_sprite = clean_sheet
                        original_label = chosen.name
                    else:
                        st.write(f"🧩 {len(frames)} quadros detectados. Clique para escolher:")
                        n_cols = 8
                        page_size = 40
                        page = 0
                        if len(frames) > page_size:
                            page = st.number_input(
                                "Página de quadros", 0, (len(frames) - 1) // page_size, 0
                            )
                        start = page * page_size
                        visible = frames[start : start + page_size]
                        cols = st.columns(n_cols)
                        for i, frame in enumerate(visible):
                            with cols[i % n_cols]:
                                st.image(frame.image, use_container_width=True)
                                if st.button(f"Quadro {start + i}", key=f"fr{start + i}"):
                                    st.session_state["frame_idx"] = start + i
                        idx = st.session_state.get("frame_idx")
                        if idx is not None and idx < len(frames):
                            base_sprite = frames[idx].image
                            original_label = f"{chosen.name} — quadro {idx}"
                            st.success(f"Quadro {idx} selecionado ({base_sprite.size[0]}×{base_sprite.size[1]} px).")
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
        use_slicing = st.checkbox("Fatiar em quadros individuais")
        if use_slicing:
            frames = sprite_tools.slice_frames(clean)
            if frames:
                idx = st.number_input("Índice do quadro", 0, len(frames) - 1, 0, key="upl_idx")
                base_sprite = frames[int(idx)].image
                original_label = f"{uploaded.name} — quadro {int(idx)}"
                st.image(base_sprite, caption=original_label, width=200)
            else:
                st.warning("Nenhum quadro isolado — usando a imagem inteira.")
                base_sprite = clean
                original_label = uploaded.name
        else:
            base_sprite = clean
            original_label = uploaded.name
            st.image(clean, caption=original_label)

# ---------------------------------------------------------------------------
# Transformacao com o Gemini
# ---------------------------------------------------------------------------

st.markdown("---")
extra = st.text_input(
    "✏️ Instruções extras para a IA (opcional)",
    placeholder="Ex.: adicione uma capa esvoaçante, deixe a armadura dourada...",
)

if base_sprite is None:
    st.info("👆 Busque um sprite ou envie um arquivo para habilitar a transformação.")
else:
    if st.button("✨ Transformar sprite com Gemini", type="primary", use_container_width=True):
        prepared = sprite_tools.prepare_for_gemini(base_sprite)
        try:
            with st.spinner("O Gemini está reimaginando seu sprite... (~10-30 s)"):
                result, used_prompt = transform_sprite(
                    prepared,
                    filter_name=filter_name,
                    extra_instructions=extra,
                    custom_style=custom_style,
                    creativity=creativity,
                    api_key=api_key or None,
                )
            final = sprite_tools.remove_background(result)
            st.session_state["result"] = final
            st.session_state["result_prompt"] = used_prompt
            st.session_state["result_label"] = original_label
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
