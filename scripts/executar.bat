@echo off
rem Executa o robo uma vez, a partir de qualquer pasta. Aceita --sem-coleta e --abrir.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m santos_rpa robo %*
exit /b %ERRORLEVEL%
