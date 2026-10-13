@echo off
REM Rechnungs-Assistent starten (Windows). Doppelklick genuegt.
cd /d "%~dp0"
if not exist .venv (
  echo Erster Start: virtuelle Umgebung wird eingerichtet ...
  python -m venv .venv || (echo Python nicht gefunden. Bitte Python 3.11+ von python.org installieren. & pause & exit /b 1)
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)
if not exist beispielrechnungen\01_nordwind_buerobedarf.pdf python scripts\beispielrechnungen_erzeugen.py
echo.
echo Rechnungs-Assistent laeuft auf http://localhost:8000  (Beenden: Strg+C)
start "" http://localhost:8000
python -m uvicorn app.main:app --port 8000
pause
