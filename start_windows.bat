@echo off
setlocal
REM Rechnungs-Assistent starten (Windows). Doppelklick genuegt.
REM Prueft bei jedem Start, ob die Pakete installiert sind, und holt fehlende nach.
cd /d "%~dp0"
set "VPY=.venv\Scripts\python.exe"

if exist "%VPY%" goto pakete_pruefen
echo Erster Start: virtuelle Umgebung wird eingerichtet ...
REM Bevorzugt Python 3.12 oder 3.13 ueber den Python-Launcher, sonst das Standard-Python
py -3.12 -m venv .venv >nul 2>&1
if not exist "%VPY%" py -3.13 -m venv .venv >nul 2>&1
if not exist "%VPY%" python -m venv .venv
if not exist "%VPY%" goto fehler_python

:pakete_pruefen
"%VPY%" -c "import fastapi, uvicorn, pdfplumber, openpyxl, anthropic, reportlab" >nul 2>&1
if not errorlevel 1 goto starten
echo Pakete werden installiert, das dauert 2 bis 5 Minuten ...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto fehler_pakete
"%VPY%" -c "import fastapi, uvicorn, pdfplumber, openpyxl, anthropic, reportlab" >nul 2>&1
if errorlevel 1 goto fehler_pakete

:starten
if not exist beispielrechnungen\01_nordwind_buerobedarf.pdf "%VPY%" scripts\beispielrechnungen_erzeugen.py
echo.
echo Rechnungs-Assistent startet auf http://localhost:8000 - Beenden mit Strg+C
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000'"
"%VPY%" -m uvicorn app.main:app --port 8000
pause
exit /b 0

:fehler_python
echo.
echo Python wurde nicht gefunden. Bitte Python 3.12 von python.org installieren
echo und dabei "Add python.exe to PATH" anhaken. Danach diese Datei erneut starten.
pause
exit /b 1

:fehler_pakete
echo.
echo Die Installation der Pakete ist fehlgeschlagen. Verwendete Python-Version:
"%VPY%" --version
echo Haeufigste Ursache: eine sehr neue Python-Version, fuer die noch nicht alle Pakete bereitstehen.
echo Loesung: Python 3.12 von python.org installieren, den Ordner .venv loeschen
echo und diese Datei erneut starten.
pause
exit /b 1
