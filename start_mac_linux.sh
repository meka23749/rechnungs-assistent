#!/usr/bin/env bash
# Rechnungs-Assistent starten (macOS/Linux)
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi
[ -f beispielrechnungen/01_nordwind_buerobedarf.pdf ] || python scripts/beispielrechnungen_erzeugen.py
echo "Rechnungs-Assistent laeuft auf http://localhost:8000  (Beenden: Ctrl+C)"
python -m uvicorn app.main:app --port 8000
