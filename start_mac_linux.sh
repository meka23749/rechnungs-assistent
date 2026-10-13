#!/usr/bin/env bash
# Rechnungs-Assistent starten (macOS/Linux). Prueft bei jedem Start die Pakete.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
PY=.venv/bin/python
if ! "$PY" -c "import fastapi, uvicorn, pdfplumber, openpyxl, anthropic, reportlab" 2>/dev/null; then
  echo "Pakete werden installiert ..."
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r requirements.txt
fi
[ -f beispielrechnungen/01_nordwind_buerobedarf.pdf ] || "$PY" scripts/beispielrechnungen_erzeugen.py
echo "Rechnungs-Assistent startet auf http://localhost:8000 (Beenden: Ctrl+C)"
"$PY" -m uvicorn app.main:app --port 8000
