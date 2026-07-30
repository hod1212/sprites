#!/bin/bash
# RO Sprite Forge - Instalador para Mac
# Clique duas vezes neste arquivo para instalar (1a vez) e abrir o app.

cd "$(dirname "$0")" || exit 1

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
    echo "======================================================"
    echo "  Pressione ENTER para FECHAR esta janela."
    echo "======================================================"
    read -p ""
    exit 1
fi

echo ""
echo "Python encontrado. Continuando..."
echo ""

# --- 2. Cria o ambiente isolado (so' na primeira vez) -------------------
if [ ! -d ".venv" ]; then
    echo "[1/3] Preparando o ambiente do aplicativo pela primeira vez..."
    echo "      (isso demora 1-2 minutos)"
    if ! python3 -m venv .venv; then
        echo ""
        echo "======================================================"
        echo "  ERRO ao criar o ambiente do aplicativo."
        echo "======================================================"
        echo ""
        echo "Tente reinstalar o Python em https://www.python.org/downloads/"
        echo "e rode este arquivo novamente."
        echo ""
        read -p "Pressione ENTER para FECHAR esta janela..."
        exit 1
    fi
fi

if [ ! -f ".venv/bin/activate" ]; then
    echo ""
    echo "======================================================"
    echo "  ERRO: a pasta .venv existe mas parece incompleta."
    echo "======================================================"
    echo ""
    echo "Apague a pasta '.venv' que esta ao lado deste arquivo e"
    echo "clique de novo neste instalador para recriar do zero."
    echo ""
    read -p "Pressione ENTER para FECHAR esta janela..."
    exit 1
fi

source .venv/bin/activate

# --- 3. Instala as dependencias (so' demora na primeira vez) ------------
echo ""
echo "[2/3] Instalando componentes necessarios..."
echo "      (pode demorar varios minutos na primeira vez - normal)"
echo ""
python3 -m pip install --upgrade pip > /dev/null
if ! python3 -m pip install -r requirements.txt; then
    echo ""
    echo "======================================================"
    echo "  ERRO ao instalar os componentes do aplicativo."
    echo "======================================================"
    echo ""
    echo "Verifique sua conexao com a internet e tente novamente"
    echo "clicando de novo neste arquivo."
    echo ""
    read -p "Pressione ENTER para FECHAR esta janela..."
    exit 1
fi

# Instala o navegador do scraper apenas se ainda nao existir
if [ ! -d "$HOME/Library/Caches/ms-playwright" ]; then
    echo ""
    echo "Instalando o navegador auxiliar de busca (1a vez apenas)..."
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

echo ""
echo "O aplicativo foi encerrado."
read -p "Pressione ENTER para fechar..."
