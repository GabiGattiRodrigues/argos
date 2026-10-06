@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem Windows usa cp1252 por padrao; o dbt precisa ler os YAML (com acento) em UTF-8
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
title Argos

rem ---- acha o Python ----------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [ERRO] Python nao encontrado. Instale o Python 3.11+ em python.org
  echo        e marque "Add python.exe to PATH" na instalacao.
  goto fim
)

rem ---- ambiente (so na primeira vez) ------------------------------------------
rem O arquivo .venv\instalado so e criado quando a instalacao termina sem erro.
rem Se a instalacao anterior foi interrompida, ele recomeca do zero.
if not exist ".venv\instalado" (
  if exist ".venv" rmdir /s /q ".venv"
  echo Criando ambiente virtual...
  %PY% -m venv .venv || goto erro
  call .venv\Scripts\activate.bat
  echo Instalando dependencias - leva uns minutos, o progresso aparece abaixo...
  python -m pip install --upgrade pip --no-cache-dir --disable-pip-version-check || goto erro
  pip install -r requirements.txt --no-cache-dir --disable-pip-version-check || goto erro
  echo ok> ".venv\instalado"
  echo Ambiente pronto.
) else (
  call .venv\Scripts\activate.bat
)

:menu
echo.
echo  ===================== ARGOS =====================
echo   1  Rodar tudo (incidentes + build + pagina)
echo   2  So o build (gera dados + dbt build + pagina)
echo   3  Abrir documentacao e linhagem (dbt docs)
echo   4  Ver o contrato quebrando (incidente de schema)
echo   5  Sair
echo  =================================================
set "op="
set /p op="Escolha: "
if "%op%"=="1" goto tudo
if "%op%"=="2" goto build
if "%op%"=="3" goto docs
if "%op%"=="4" goto incidente
if "%op%"=="5" goto fim
goto menu

:tudo
echo.
echo [1/4] Simulando incidentes (demora uns minutos)...
python scripts\simular_incidentes.py || goto erro

:build
echo.
echo [2/4] Gerando base sintetica...
python scripts\gerar_dados.py || goto erro
echo.
echo [3/4] dbt build (modelos, contratos e testes)...
dbt build --profiles-dir . || goto erro
echo.
echo [4/4] Gerando a pagina...
python scripts\gerar_pagina.py || goto erro
echo.
echo Pronto! Abrindo a pagina...
start "" "%~dp0site\index.html"
goto menu

:docs
echo.
echo Gerando documentacao... (para fechar o servidor, Ctrl+C e depois N)
dbt docs generate --profiles-dir . || goto erro
dbt docs serve --profiles-dir .
goto menu

:incidente
echo.
echo Produtor renomeia a coluna "valor" sem avisar...
python scripts\gerar_dados.py --incidente schema || goto erro
dbt build --profiles-dir . -s bronze_transacoes+
echo.
echo Acima: o contrato barrou: veja a tabelinha "missing in definition / missing in contract".
echo Restaurando a base normal...
python scripts\gerar_dados.py >nul || goto erro
dbt build --profiles-dir . >nul || goto erro
echo Base restaurada.
goto menu

:erro
echo.
echo [ERRO] Algo falhou no passo acima. Tira um print desta tela e me manda.
pause
goto menu

:fim
endlocal
