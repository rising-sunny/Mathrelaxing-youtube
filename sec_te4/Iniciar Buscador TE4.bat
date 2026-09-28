@echo off
rem Abre el Buscador TE4. La primera vez prepara un entorno de Python con lo necesario.
rem Requisito: Python 3.10 o superior (python.org, marcando "Add python.exe to PATH").
cd /d "%~dp0"
if not exist ".venv\listo.txt" (
    echo Preparando el Buscador TE4 por primera vez, esto toma unos minutos...
    py -3 -m venv .venv >nul 2>&1 || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
        echo marcando "Add python.exe to PATH", y vuelve a abrir este archivo.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
    if errorlevel 1 (
        echo.
        echo No se pudieron instalar las dependencias. Revisa la conexion a internet y vuelve a intentar.
        pause
        exit /b 1
    )
    echo ok> ".venv\listo.txt"
)
start "" ".venv\Scripts\pythonw.exe" buscador_te4.py
