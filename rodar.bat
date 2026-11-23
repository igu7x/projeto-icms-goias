@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
%PY% --version
if errorlevel 1 (
  echo.
  echo [ERRO] Python nao encontrado. Instale em https://www.python.org/downloads/
  echo e marque a opcao "Add Python to PATH" na instalacao.
  pause
  exit /b
)
echo.
echo === 1/4 Instalando bibliotecas ===
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo.
echo === 2/4 Baixando dados e criando o banco ===
%PY% etl.py
if errorlevel 1 goto erro
echo.
echo === 3/4 Gerando o relatorio PDF ===
%PY% relatorio.py
if errorlevel 1 goto erro
echo.
echo === 4/4 Abrindo o painel no navegador ===
%PY% -m streamlit run app.py
pause
exit /b
:erro
echo.
echo [ERRO] Algo deu errado acima. Tire um print desta janela e mande.
pause
