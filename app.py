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
import zipfile
from pathlib import Path

import streamlit as st
from PIL import Image

import scraper
import sprite_tools
from gemini_transform import (
    FILTER_UI,
    FILTERS,
    GeminiNotConfigured,
    filter_options,
    strip_emoji,
    transform_animation_frames,
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


if api_key:
    with st.expander("🔑 Chave da API configurada ✅ — toque para alterar", expanded=False):
        campo_da_chave()
        if st.button("🗑️ Esquecer a chave desta sessão"):
            st.session_state["_esquecer_chave"] = True
            st.rerun()
else:
    with st.container(border=True):
        st.markdown("#### 🔑 Primeiro, cole a sua chave da API do Gemini")
        campo_da_chave()

remember_api_key("api_key_main")
api_key = st.session_state[KEY_STORE] or stored_key

MAX_QUADROS_ANIMACAO = 24


def seletor_de_sprite(sheet: Image.Image, nome: str, prefixo: str) -> dict:
    """
    Interface compartilhada pelas duas abas: deixa o usuario escolher entre
    trabalhar com a imagem inteira, um quadro isolado ou vários quadros para
    montar uma animação.

    Devolve um dicionario com o que a etapa de transformacao precisa.
    """
    escolha: dict = {
        "base": None,          # sprite unico (modos 1 e 2)
        "frames": [],          # lista de sprites (modo animacao)
        "placements": [],      # bboxes originais, para remontar o sheet
        "sheet_size": sheet.size,
        "label": nome,
        "animacao": False,
    }

    modo = st.radio(
        "Como você quer trabalhar?",
        [
            "🖼️ Imagem inteira",
            "🧩 Um quadro só",
            "🎬 Animação — vários quadros (para usar em jogo)",
        ],
        key=f"{prefixo}_modo",
    )

    if modo == "🖼️ Imagem inteira":
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

    # Mapa numerado: uma imagem so, legivel no celular (miniaturas em colunas
    # empilham e ficam gigantes em telas estreitas).
    mapa = sprite_tools.annotate_frames(sheet, frames)
    st.image(mapa, caption="Mapa dos quadros — use estes números para escolher", use_container_width=True)

    if modo == "🧩 Um quadro só":
        idx = st.number_input(
            "Número do quadro (veja a numeração acima)",
            0, len(frames) - 1, 0, key=f"{prefixo}_um_idx",
        )
        escolha["base"] = frames[int(idx)].image
        escolha["label"] = f"{nome} — quadro {int(idx)}"
        st.image(escolha["base"], caption=escolha["label"], width=180)
        return escolha

    # ------------------ Modo animacao ------------------
    st.markdown("##### 🎬 Escolha os quadros da animação")
    st.caption(
        "Selecione os quadros de um mesmo movimento (ex.: o ciclo de caminhada "
        "em uma direção). O primeiro quadro define o design do personagem e os "
        "demais o repetem em outras poses."
    )

    modo_selecao = st.radio(
        "Seleção dos quadros",
        ["Intervalo (mais rápido)", "Escolher um por um"],
        horizontal=True,
        key=f"{prefixo}_selmodo",
    )

    if modo_selecao == "Intervalo (mais rápido)":
        inicio, fim = st.slider(
            "Do quadro ... até o quadro",
            0, len(frames) - 1, (0, min(len(frames) - 1, 5)),
            key=f"{prefixo}_range",
        )
        indices = list(range(inicio, fim + 1))
    else:
        indices = st.multiselect(
            "Quadros (pela numeração das miniaturas)",
            list(range(len(frames))),
            default=list(range(min(len(frames), 6))),
            key=f"{prefixo}_multi",
        )

    indices = sorted(set(indices))
    if not indices:
        st.info("Selecione ao menos dois quadros para gerar uma animação.")
        return escolha

    if len(indices) > MAX_QUADROS_ANIMACAO:
        st.warning(
            f"Você selecionou {len(indices)} quadros. Para evitar estourar a "
            f"cota da API, vou processar os primeiros {MAX_QUADROS_ANIMACAO}."
        )
        indices = indices[:MAX_QUADROS_ANIMACAO]

    ref_idx = st.selectbox(
        "Quadro que define o design do personagem",
        indices,
        index=0,
        help="Escolha o quadro em que o personagem aparece mais nítido e de "
        "corpo inteiro — em geral o de frente, parado.",
        key=f"{prefixo}_ref",
    )

    escolha["frames"] = [frames[i].image for i in indices]
    escolha["placements"] = [frames[i].bbox for i in indices]
    escolha["ref_pos"] = indices.index(ref_idx)
    escolha["label"] = f"{nome} — {len(indices)} quadros"
    escolha["animacao"] = True

    st.info(
        f"🎬 **{len(indices)} quadros** selecionados → serão feitas "
        f"{len(indices)} chamadas à API (≈{len(indices) * 12}s no total)."
    )
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

quadros_animacao = selecao.get("frames") or []
modo_animacao = bool(selecao.get("animacao")) and len(quadros_animacao) >= 2

# ---------------------------------------------------------------------------
# Caminho A — Animacao: varios quadros com o MESMO personagem
# ---------------------------------------------------------------------------

if modo_animacao:
    if not api_key:
        st.warning(
            "🔑 Cole a sua chave da API do Gemini no campo acima (ou no menu ☰ → "
            "Configurações) para habilitar a geração."
        )
    if st.button(
        f"🎬 Gerar animação ({len(quadros_animacao)} quadros)",
        type="primary",
        use_container_width=True,
        disabled=not api_key,
    ):
        preparados = [sprite_tools.prepare_for_gemini(q) for q in quadros_animacao]
        barra = st.progress(0.0, text="Iniciando...")

        def atualizar(feitos: int, total: int, mensagem: str) -> None:
            barra.progress(feitos / total, text=f"{mensagem} ({feitos}/{total})")

        try:
            resultados, referencia = transform_animation_frames(
                preparados,
                filter_name=filter_name,
                extra_instructions=extra,
                custom_style=custom_style,
                creativity=creativity,
                api_key=api_key or None,
                reference_index=selecao.get("ref_pos", 0),
                progress_callback=atualizar,
            )
            barra.empty()
            st.session_state["anim"] = [
                (r.index, sprite_tools.remove_background(r.image) if r.ok else None, r.error)
                for r in resultados
            ]
            st.session_state["anim_label"] = original_label
            st.session_state["anim_placements"] = selecao.get("placements", [])
            st.session_state["anim_sheet_size"] = selecao.get("sheet_size")
        except GeminiNotConfigured as exc:
            barra.empty()
            st.error(str(exc))
        except Exception as exc:
            barra.empty()
            st.error(f"Erro na geração da animação: {exc}")
            with st.expander("Detalhes técnicos"):
                st.code(traceback.format_exc())

    if st.session_state.get("anim_label") == original_label and st.session_state.get("anim"):
        anim = st.session_state["anim"]
        gerados = [(i, img) for i, img, _ in anim if img is not None]
        falhas = [(i, err) for i, img, err in anim if img is None]

        st.success(f"✅ {len(gerados)} de {len(anim)} quadros gerados com o mesmo personagem.")
        if falhas:
            with st.expander(f"⚠️ {len(falhas)} quadro(s) falharam — ver motivos"):
                for i, err in falhas:
                    st.write(f"**Quadro {i}:** {err}")

        st.markdown("##### 🎬 Comparação quadro a quadro")
        for i, novo in gerados:
            col_o, col_n = st.columns(2)
            with col_o:
                st.image(quadros_animacao[i], caption=f"Original #{i}", width=140)
            with col_n:
                st.image(novo, caption=f"Gerado #{i}", width=140)

        # --- Montagem dos arquivos prontos para o jogo ---------------------
        sprites = [img for _, img in gerados]
        colunas_grade = st.slider(
            "Colunas na folha de sprites em grade",
            1, 12, min(len(sprites), 6),
            help="Quantos quadros por linha na folha uniforme. Motores de jogo "
            "importam esse formato informando o tamanho da célula.",
        )
        folha_grade = sprite_tools.build_grid_sheet(sprites, columns=colunas_grade)
        st.markdown("##### 🧾 Folha de sprites gerada (grade uniforme)")
        st.image(folha_grade, use_container_width=True)
        celula = (
            folha_grade.width // colunas_grade,
            folha_grade.height // ((len(sprites) + colunas_grade - 1) // colunas_grade),
        )
        st.caption(
            f"Tamanho da célula: **{celula[0]}×{celula[1]} px** — use esse valor "
            "ao importar a folha no seu motor de jogo (Unity, Godot, GameMaker)."
        )

        # Folha com o mesmo layout do arquivo original (encaixe direto)
        folha_original = None
        placements = st.session_state.get("anim_placements") or []
        sheet_size = st.session_state.get("anim_sheet_size")
        if sheet_size and len(placements) == len(anim):
            pares = [(placements[i], img) for i, img in gerados]
            folha_original = sprite_tools.rebuild_sheet_like_original(sheet_size, pares)

        # --- ZIP com tudo -------------------------------------------------
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for pos, (i, img) in enumerate(gerados):
                zf.writestr(f"quadros/frame_{pos:02d}_orig{i}.png", image_to_png_bytes(img))
            zf.writestr("spritesheet_grade.png", image_to_png_bytes(folha_grade))
            if folha_original is not None:
                zf.writestr("spritesheet_layout_original.png", image_to_png_bytes(folha_original))
            zf.writestr(
                "LEIA-ME.txt",
                (
                    "Sprites gerados com RO Sprite Forge\r\n"
                    f"Estilo: {custom_style.strip() or filter_name}\r\n"
                    f"Quadros: {len(sprites)}\r\n"
                    f"spritesheet_grade.png -> grade uniforme, celula "
                    f"{celula[0]}x{celula[1]} px, {colunas_grade} colunas\r\n"
                    "spritesheet_layout_original.png -> mesmo layout do arquivo "
                    "enviado, para substituicao direta\r\n"
                    "quadros/ -> cada pose em PNG separado, fundo transparente\r\n"
                ).encode("utf-8"),
            )

        st.download_button(
            "⬇️ Baixar animação completa (.zip: quadros + folhas de sprite)",
            data=zip_buffer.getvalue(),
            file_name="animacao_sprites.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "⬇️ Só a folha em grade (PNG)",
                data=image_to_png_bytes(folha_grade),
                file_name="spritesheet_grade.png",
                mime="image/png",
                use_container_width=True,
            )
        with col_d2:
            if folha_original is not None:
                st.download_button(
                    "⬇️ Folha no layout original (PNG)",
                    data=image_to_png_bytes(folha_original),
                    file_name="spritesheet_layout_original.png",
                    mime="image/png",
                    use_container_width=True,
                )

# ---------------------------------------------------------------------------
# Caminho B — sprite unico
# ---------------------------------------------------------------------------

elif base_sprite is None:
    st.info("👆 Busque um sprite ou envie um arquivo para habilitar a transformação.")
else:
    if not api_key:
        st.warning(
            "🔑 Cole a sua chave da API do Gemini no campo acima (ou no menu ☰ → "
            "Configurações) para habilitar a geração."
        )
    if st.button(
        "✨ Transformar sprite com Gemini",
        type="primary",
        use_container_width=True,
        disabled=not api_key,
    ):
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
