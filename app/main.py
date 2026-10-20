"""Rechnungs-Assistent: Web-API und Oberfläche.

Start:  python -m uvicorn app.main:app --port 8000
Danach: http://localhost:8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

BASIS = Path(__file__).resolve().parent.parent


def lade_env(pfad: Path) -> None:
    """Liest KEY=WERT aus .env. API-Schlüssel gehören nie in den Quellcode."""
    if not pfad.exists():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            schluessel, wert = zeile.split("=", 1)
            os.environ.setdefault(schluessel.strip(), wert.strip().strip('"').strip("'"))


lade_env(BASIS / ".env")

from . import datenbank  # noqa: E402  (nach .env, damit DB_PFAD greift)
from .export import erstelle_excel  # noqa: E402
from .extraktion import Rechnung, extrahiere, ki_verfuegbar, modell, pdf_zu_text  # noqa: E402
from .pruefung import gesamtstatus, pruefe  # noqa: E402

MAX_GROESSE = 10 * 1024 * 1024  # 10 MB pro Datei
BEISPIELE = BASIS / "beispielrechnungen"
STAMMDATEN = BASIS / "stammdaten" / "lieferanten.csv"


@asynccontextmanager
async def lifespan(_: FastAPI):
    datenbank.initialisieren()
    datenbank.stammdaten_laden(STAMMDATEN)
    yield


app = FastAPI(title="Rechnungs-Assistent", lifespan=lifespan)


def verarbeite(dateiname: str, inhalt: bytes, modus: str) -> dict:
    """PDF -> Text -> Extraktion -> Prüfung -> Speichern."""
    if not inhalt.startswith(b"%PDF"):
        raise HTTPException(400, f"{dateiname}: keine PDF-Datei")
    if len(inhalt) > MAX_GROESSE:
        raise HTTPException(413, f"{dateiname}: größer als 10 MB")

    text = pdf_zu_text(inhalt)
    if not text.strip():
        raise HTTPException(422, f"{dateiname}: kein Text gefunden (gescanntes Dokument? OCR nötig)")

    ergebnis = extrahiere(text, modus)
    r = ergebnis.rechnung
    punkte = pruefe(r, datenbank.finde_duplikat(r.lieferant, r.rechnungsnummer))
    return datenbank.speichern(
        dateiname, r.als_dict(), ergebnis.quelle, ergebnis.hinweis, ergebnis.dauer_ms,
        gesamtstatus(punkte), [p.als_dict() for p in punkte],
    )


@app.get("/")
def startseite():
    return FileResponse(BASIS / "app" / "static" / "index.html")


@app.get("/api/status")
def status():
    return {"ki_verfuegbar": ki_verfuegbar(), "modell": modell()}


@app.get("/api/rechnungen")
def liste():
    return datenbank.alle()


@app.post("/api/rechnungen")
async def hochladen(dateien: list[UploadFile] = File(...), modus: str = Form("auto")):
    ergebnisse, fehler = [], []
    for datei in dateien:
        try:
            ergebnisse.append(verarbeite(datei.filename or "rechnung.pdf", await datei.read(), modus))
        except HTTPException as e:
            fehler.append(e.detail)
    return {"rechnungen": ergebnisse, "fehler": fehler}


@app.post("/api/beispiele")
def beispiele(modus: str = Form("auto")):
    """Demo-Abkürzung: alle Musterrechnungen aus dem Ordner verarbeiten."""
    dateien = sorted(BEISPIELE.glob("*.pdf"))
    if not dateien:
        raise HTTPException(404, "Keine Musterrechnungen gefunden. Erst scripts/beispielrechnungen_erzeugen.py ausführen")
    return {"rechnungen": [verarbeite(d.name, d.read_bytes(), modus) for d in dateien], "fehler": []}


class Korrektur(BaseModel):
    lieferant: str | None = None
    rechnungsnummer: str | None = None
    rechnungsdatum: str | None = None
    netto: float | None = None
    mwst_satz: float | None = None
    mwst_betrag: float | None = None
    brutto: float | None = None
    iban: str | None = None
    waehrung: str = "EUR"


@app.put("/api/rechnungen/{rechnung_id}")
def korrigieren(rechnung_id: int, korrektur: Korrektur):
    """Mensch korrigiert ein Feld -> alle Regeln laufen erneut."""
    if not datenbank.hole(rechnung_id):
        raise HTTPException(404, "Rechnung nicht gefunden")
    daten = korrektur.model_dump()
    if daten["iban"]:
        daten["iban"] = daten["iban"].replace(" ", "").upper()
    r = Rechnung(**daten)
    punkte = pruefe(r, datenbank.finde_duplikat(r.lieferant, r.rechnungsnummer, ausser_id=rechnung_id))
    return datenbank.aktualisieren(rechnung_id, r.als_dict(), gesamtstatus(punkte), [p.als_dict() for p in punkte])


class Freigabe(BaseModel):
    freigegeben: bool


@app.post("/api/rechnungen/{rechnung_id}/freigabe")
def freigeben(rechnung_id: int, freigabe: Freigabe):
    rechnung = datenbank.hole(rechnung_id)
    if not rechnung:
        raise HTTPException(404, "Rechnung nicht gefunden")
    if freigabe.freigegeben and rechnung["status"] == "fehler":
        raise HTTPException(409, "Rechnungen mit Fehlern können nicht freigegeben werden. Bitte zuerst korrigieren")
    return datenbank.setze_freigabe(rechnung_id, freigabe.freigegeben)


@app.delete("/api/rechnungen")
def zuruecksetzen():
    datenbank.alle_loeschen()
    return {"ok": True}


@app.get("/api/export.xlsx")
def excel():
    inhalt = erstelle_excel(datenbank.alle())
    name = f"rechnungen_{datetime.now():%Y-%m-%d}.xlsx"
    return Response(
        inhalt,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
