#!/bin/bash
# RO Sprite Forge - Instalador para Mac
# Clique duas vezes neste arquivo para instalar (1a vez) e abrir o app.

cd "$(dirname "$0")"

echo "======================================================"
echo "  RO SPRITE FORGE - Instalador para Mac"
echo "======================================================"
echo ""
echo "Este arquivo vai preparar tudo automaticamente na"
echo "primeira vez (pode demorar alguns minutos) e depois"
echo "abrir o aplicativo no seu navegador."
echo ""
echo "Da proxima vez que voce clicar neste mesmo arquivo,"
echo "ele vai abrir o app direto, sem reinstalar nada."
echo ""
read -p "Pressione ENTER para continuar..."

# --- 1. Verifica se o Python esta instalado -----------------------------
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "======================================================"
    echo "  ATENCAO: Python nao foi encontrado no seu Mac."
    echo "======================================================"
    echo ""
    echo "Siga estes passos:"
    echo "  1. Uma pagina vai abrir no seu navegador."
    echo "  2. Clique no botao amarelo 'Download Python'."
    echo "  3. Abra o arquivo .pkg baixado e siga a instalacao"
    echo "     (pode deixar tudo no padrao, so clicar em Continuar)."
    echo "  4. Depois de instalar, feche esta janela e clique"
    echo "     de novo neste mesmo arquivo (instalar_e_abrir_MAC.command)."
    echo ""
    open "https://www.python.org/downloads/"
    read -p "Pressione ENTER para fechar..."
    exit 1
fi

# --- 2. Cria o ambiente isolado (so' na primeira vez) -------------------
if [ ! -d ".venv" ]; then
    echo ""
    echo "[1/3] Preparando o ambiente do aplicativo pela primeira vez..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# --- 3. Instala as dependencias (so' demora na primeira vez) ------------
echo ""
echo "[2/3] Verificando componentes necessarios..."
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet -r requirements.txt

# Instala o navegador do scraper apenas se ainda nao existir
if [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
    echo "Instalando o navegador auxiliar (1a vez apenas)..."
    python3 -m playwright install chromium
fi

# --- 4. Abre o aplicativo -------------------------------------------------
echo ""
echo "[3/3] Abrindo o RO Sprite Forge no seu navegador..."
echo ""
echo "======================================================"
echo "  NAO FECHE ESTA JANELA enquanto estiver usando o app."
echo "  Para encerrar, feche esta janela ou aperte Ctrl+C."
echo "======================================================"
echo ""

streamlit run app.py
