@echo off
chcp 65001 >nul
title RO Sprite Forge - Instalador
color 0A

echo ======================================================
echo   RO SPRITE FORGE - Instalador para Windows
echo ======================================================
echo.
echo Este arquivo vai preparar tudo automaticamente na
echo primeira vez (pode demorar alguns minutos) e depois
echo abrir o aplicativo no seu navegador.
echo.
echo Da proxima vez que voce clicar neste mesmo arquivo,
echo ele vai abrir o app direto, sem reinstalar nada.
echo.
pause

REM --- 1. Verifica se o Python esta instalado ---------------------------
REM O instalador oficial do Python cria o comando "py" (Python Launcher)
REM mesmo quando "python" nao fica disponivel no PATH. Por isso testamos
REM os dois, nesta ordem.
set "PYCMD="

where py >nul 2>nul
if %errorlevel% equ 0 set "PYCMD=py -3"

if not defined PYCMD (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PYCMD=python"
)

if not defined PYCMD (
    echo.
    echo ======================================================
    echo   ATENCAO: Python nao foi encontrado no seu computador.
    echo ======================================================
    echo.
    echo Siga estes passos:
    echo   1. Uma pagina vai abrir no seu navegador.
    echo   2. Clique no botao amarelo "Download Python".
    echo   3. Abra o instalador baixado.
    echo   4. IMPORTANTE: marque a caixa "Add python.exe to PATH"
    echo      na PRIMEIRA tela do instalador, antes de clicar em
    echo      "Install Now".
    echo   5. Depois de instalar, fechar TODAS as janelas abertas
    echo      deste instalador e clicar de novo neste mesmo arquivo
    echo      ^(instalar_e_abrir_WINDOWS.bat^).
    echo.
    echo Se voce acha que ja instalou o Python e esta mensagem
    echo apareceu mesmo assim, o motivo mais comum e' que a caixa
    echo "Add python.exe to PATH" nao foi marcada durante a
    echo instalacao. Reinstale marcando essa opcao.
    echo.
    start https://www.python.org/downloads/
    echo ======================================================
    echo   Pressione uma tecla para FECHAR esta janela.
    echo ======================================================
    pause >nul
    exit /b 1
)

echo.
echo Python encontrado ^(comando: %PYCMD%^). Continuando...
echo.

REM --- 2. Cria o ambiente isolado (so' na primeira vez) -----------------
if not exist ".venv" (
    echo [1/3] Preparando o ambiente do aplicativo pela primeira vez...
    echo       ^(isso demora 1-2 minutos^)
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo ======================================================
        echo   ERRO ao criar o ambiente do aplicativo.
        echo ======================================================
        echo.
        echo Isso pode acontecer se o antivirus bloqueou o processo,
        echo ou se o Python instalado esta corrompido. Tente:
        echo   1. Desativar o antivirus temporariamente e tentar de novo.
        echo   2. Reinstalar o Python em https://www.python.org/downloads/
        echo.
        echo Pressione uma tecla para FECHAR esta janela.
        pause >nul
        exit /b 1
    )
)

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ======================================================
    echo   ERRO: a pasta .venv existe mas parece incompleta.
    echo ======================================================
    echo.
    echo Apague a pasta ".venv" que esta ao lado deste arquivo e
    echo clique de novo neste instalador para recriar do zero.
    echo.
    echo Pressione uma tecla para FECHAR esta janela.
    pause >nul
    exit /b 1
)

call .venv\Scripts\activate.bat

REM --- 3. Instala as dependencias (so' demora na primeira vez) ----------
echo.
echo [2/3] Instalando componentes necessarios...
echo       ^(pode demorar varios minutos na primeira vez - normal^)
echo.
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ======================================================
    echo   ERRO ao instalar os componentes do aplicativo.
    echo ======================================================
    echo.
    echo Verifique sua conexao com a internet e tente novamente
    echo clicando de novo neste arquivo.
    echo.
    echo Pressione uma tecla para FECHAR esta janela.
    pause >nul
    exit /b 1
)

REM Instala o navegador do scraper apenas se ainda nao existir
if not exist "%USERPROFILE%\AppData\Local\ms-playwright" (
    echo.
    echo Instalando o navegador auxiliar de busca ^(1a vez apenas^)...
    python -m playwright install chromium
)

REM Evita a pergunta de e-mail que o Streamlit faz na 1a execucao, que
REM travaria o terminal esperando resposta sem explicar isso na tela.
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    (
        echo [general]
        echo email = ""
    ) > "%USERPROFILE%\.streamlit\credentials.toml"
)

REM --- 4. Abre o aplicativo ----------------------------------------------
echo.
echo [3/3] Abrindo o RO Sprite Forge no seu navegador...
echo.
echo ======================================================
echo   NAO FECHE ESTA JANELA enquanto estiver usando o app.
echo   Para encerrar, feche esta janela ou aperte Ctrl+C.
echo ======================================================
echo.

streamlit run app.py

echo.
echo O aplicativo foi encerrado.
pause
