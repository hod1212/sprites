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

REM --- 1. Verifica se o Python esta instalado -------------------------
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ======================================================
    echo   ATENCAO: Python nao foi encontrado no seu computador.
    echo ======================================================
    echo.
    echo Siga estes passos:
    echo   1. Uma pagina vai abrir no seu navegador.
    echo   2. Clique no botao amarelo "Download Python".
    echo   3. Abra o instalador baixado.
    echo   4. IMPORTANTE: marque a caixa "Add Python to PATH"
    echo      antes de clicar em "Install Now".
    echo   5. Depois de instalar, feche esta janela e clique
    echo      de novo neste mesmo arquivo (instalar_e_abrir_WINDOWS.bat).
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b
)

REM --- 2. Cria o ambiente isolado (so' na primeira vez) ---------------
if not exist ".venv" (
    echo.
    echo [1/3] Preparando o ambiente do aplicativo pela primeira vez...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

REM --- 3. Instala as dependencias (so' demora na primeira vez) --------
echo.
echo [2/3] Verificando componentes necessarios...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

REM Instala o navegador do scraper apenas se ainda nao existir
if not exist "%USERPROFILE%\AppData\Local\ms-playwright" (
    echo Instalando o navegador auxiliar ^(1a vez apenas^)...
    python -m playwright install chromium
)

REM --- 4. Abre o aplicativo --------------------------------------------
echo.
echo [3/3] Abrindo o RO Sprite Forge no seu navegador...
echo.
echo ======================================================
echo   NAO FECHE ESTA JANELA enquanto estiver usando o app.
echo   Para encerrar, feche esta janela ou aperte Ctrl+C.
echo ======================================================
echo.

streamlit run app.py

pause
