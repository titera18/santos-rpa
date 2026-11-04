@echo off
rem Executa o robo uma vez. Use este arquivo no Agendador de Tarefas do Windows.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" rpa.py %*
exit /b %ERRORLEVEL%
