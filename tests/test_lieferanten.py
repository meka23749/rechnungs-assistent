"""Tests für die Erweiterung "Lieferanten-Stammdaten".

Diese Tests beschreiben, was die Erweiterung können muss. Sie schlagen fehl,
bis die Erweiterung fertig ist (testgetriebene Entwicklung).

Aufruf:  python -m pytest -q tests/test_lieferanten.py
"""

import os
import sqlite3
import tempfile
from pathlib import Path

os.environ.setdefault("DB_PFAD", str(Path(tempfile.mkdtemp()) / "test.db"))
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import datenbank, pruefung  # noqa: E402
from app.extraktion import Rechnung  # noqa: E402
from app.main import app  # noqa: E402

IBAN_A = "DE89370400440532013000"
IBAN_B = "DE02100100100006820101"


@pytest.fixture(scope="module", autouse=True)
def datenbank_bereit():
    datenbank.initialisieren()


def rechnung(iban: str | None) -> Rechnung:
    return Rechnung(lieferant="Beispiel GmbH", rechnungsnummer="R-1", rechnungsdatum="2026-10-01",
                    netto=100.0, mwst_satz=19.0, mwst_betrag=19.0, brutto=119.0, iban=iban)


# ------------------------------------------------------------ Schritt 1: Tabelle und Funktionen

def test_lieferant_anlegen_und_finden():
    datenbank.lieferant_anlegen("Testfirma Anlegen GmbH", "DE89 3704 0044 0532 0130 00")
    gefunden = datenbank.finde_lieferant("  testfirma anlegen gmbh ")
    assert gefunden is not None
    assert gefunden["iban"] == IBAN_A          # ohne Leerzeichen gespeichert
    assert isinstance(gefunden["lieferant_id"], int)


def test_lieferantenname_ist_eindeutig():
    datenbank.lieferant_anlegen("Testfirma Eindeutig GmbH", IBAN_A)
    with pytest.raises(sqlite3.IntegrityError):
        datenbank.lieferant_anlegen("TESTFIRMA EINDEUTIG GMBH", IBAN_B)


def test_unbekannter_lieferant_ergibt_none():
    assert datenbank.finde_lieferant("Gibt Es Nicht GmbH") is None


# ------------------------------------------------------------ Schritt 3: die neue Prüfregel

def test_iban_stimmt_mit_stammdaten_ueberein():
    punkt = pruefung.pruefe_stammdaten(rechnung(IBAN_A), {"lieferant_id": 1, "name": "Beispiel GmbH", "iban": IBAN_A})
    assert punkt.regel == "Stammdaten"
    assert punkt.status == "ok"


def test_abweichende_iban_ist_fehler():
    punkt = pruefung.pruefe_stammdaten(rechnung(IBAN_A), {"lieferant_id": 1, "name": "Beispiel GmbH", "iban": IBAN_B})
    assert punkt.status == "fehler"
    assert "Stammdaten" in punkt.meldung


def test_neuer_lieferant_ist_warnung():
    assert pruefung.pruefe_stammdaten(rechnung(IBAN_A), None).status == "warnung"


def test_rechnung_ohne_iban_bei_bekanntem_lieferanten_ist_ok():
    punkt = pruefung.pruefe_stammdaten(rechnung(None), {"lieferant_id": 1, "name": "Beispiel GmbH", "iban": IBAN_A})
    assert punkt.status == "ok"


# ------------------------------------------------------------ Schritte 2 und 4: Start und Ablauf

def test_stammdaten_werden_geladen_und_bei_jeder_rechnung_geprueft():
    with TestClient(app) as client:
        client.delete("/api/rechnungen")
        assert datenbank.finde_lieferant("Elbtal IT-Service KG") is not None, "lieferanten.csv wurde beim Start nicht geladen"

        rechnungen = client.post("/api/beispiele", data={"modus": "regeln"}).json()["rechnungen"]
        neue_bank = next(r for r in rechnungen if r["dateiname"].startswith("08"))
        assert neue_bank["status"] == "fehler"
        assert any(p["regel"] == "Stammdaten" and p["status"] == "fehler" for p in neue_bank["pruefung"])

        nordwind = next(r for r in rechnungen if r["dateiname"].startswith("01"))
        assert nordwind["status"] == "ok"
        assert nordwind["lieferant_id"] is not None, "Die Rechnung muss per Fremdschlüssel auf den Lieferanten zeigen"


# ------------------------------------------------------------ Schritt 5: Auswertungen per SQL

def test_auswertungen():
    with TestClient(app) as client:
        client.delete("/api/rechnungen")
        client.post("/api/beispiele", data={"modus": "regeln"})
        auswertungen = client.get("/api/auswertungen").json()

    assert len(auswertungen) >= 3
    for a in auswertungen:
        assert {"titel", "sql", "spalten", "zeilen"} <= a.keys()
        assert a["sql"].strip().upper().startswith(("SELECT", "WITH"))

    bank = next(a for a in auswertungen if "Bankverbindung" in a["titel"])
    # Kieler Software (Zahlendreher) und Elbtal (angeblich neue Bank)
    assert len(bank["zeilen"]) == 2
