@echo off
REM Moto Monitor - duplo clique para iniciar no Windows
cd /d "%~dp0"
if not exist .venv (
    echo Criando ambiente Python...
    python -m venv .venv || (echo Instale o Python 3.10+ em python.org e marque "Add to PATH". & pause & exit /b 1)
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt
)
.venv\Scripts\python -m motomonitor %*
pause
