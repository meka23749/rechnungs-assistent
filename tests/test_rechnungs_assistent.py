"""Tests: Prüfregeln, Regel-Extraktion, KI-Extraktion (mit Attrappe) und API."""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

os.environ["DB_PFAD"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.extraktion import (Rechnung, extrahiere, extrahiere_mit_regeln, maskieren,  # noqa: E402
                            pdf_zu_text)
from app.main import app  # noqa: E402
from app.pruefung import gesamtstatus, iban_gueltig, pruefe  # noqa: E402

BEISPIELE = Path(__file__).resolve().parent.parent / "beispielrechnungen"


def gute_rechnung(**aenderungen) -> Rechnung:
    daten = dict(lieferant="Test GmbH", rechnungsnummer="R-1", rechnungsdatum="2026-10-01",
                 netto=100.0, mwst_satz=19.0, mwst_betrag=19.0, brutto=119.0,
                 iban="DE89 3704 0044 0532 0130 00")
    daten.update(aenderungen)
    return Rechnung(**daten)


# ------------------------------------------------------------ Prüfregeln

def test_korrekte_rechnung_ist_ok():
    assert gesamtstatus(pruefe(gute_rechnung(), heute=date(2026, 10, 11))) == "ok"


def test_rechenfehler_wird_erkannt():
    punkte = pruefe(gute_rechnung(brutto=129.0), heute=date(2026, 10, 11))
    assert gesamtstatus(punkte) == "fehler"
    assert any(p.regel == "Summe" and "10,00 €" in p.meldung for p in punkte)


def test_rundungsdifferenz_wird_toleriert():
    assert gesamtstatus(pruefe(gute_rechnung(brutto=119.01), heute=date(2026, 10, 11))) == "ok"


def test_ungewoehnlicher_steuersatz_ist_warnung():
    r = gute_rechnung(mwst_satz=16.0, mwst_betrag=16.0, brutto=116.0)
    assert gesamtstatus(pruefe(r, heute=date(2026, 10, 11))) == "pruefen"


def test_fehlende_pflichtfelder():
    punkte = pruefe(gute_rechnung(rechnungsnummer=None, netto=None), heute=date(2026, 10, 11))
    assert "Rechnungsnummer" in punkte[0].meldung and "Nettobetrag" in punkte[0].meldung


def test_duplikat_ist_fehler():
    assert gesamtstatus(pruefe(gute_rechnung(), duplikat_von="alt.pdf", heute=date(2026, 10, 11))) == "fehler"


def test_zukunftsdatum_ist_warnung():
    assert gesamtstatus(pruefe(gute_rechnung(rechnungsdatum="2027-01-01"), heute=date(2026, 10, 11))) == "pruefen"


@pytest.mark.parametrize("iban,gueltig", [
    ("DE89 3704 0044 0532 0130 00", True),
    ("DE89370400440532013000", True),
    ("DE89370400440532013001", False),   # letzte Ziffer falsch
    ("DE98370400440532013000", False),   # Zahlendreher in der Prüfziffer
    ("DE8937040044053201300", False),    # eine Stelle zu kurz
])
def test_iban_pruefziffer(iban, gueltig):
    assert iban_gueltig(iban) is gueltig


# ------------------------------------------------------------ Extraktion

ERWARTET = {
    "01_nordwind_buerobedarf.pdf": ("Nordwind Bürobedarf GmbH", "RE-2026-1047", 1388.02),
    "02_elbtal_it_service.pdf": ("Elbtal IT-Service KG", "ET-48213", 2797.69),
    "03_alster_catering.pdf": ("Alster Catering GmbH", "AC-2026-311", 438.17),
    "04_hanse_druck_medien.pdf": ("Hanse Druck & Medien GmbH", "HD-7741", 822.77),
    "06_kieler_software.pdf": ("Kieler Software Lizenzen GmbH", "KSL-2026-0918", 1142.40),
    "07_nordlicht_reinigung.pdf": ("Nordlicht Gebäudereinigung GmbH", "NL-0926-118", 1213.80),
}


@pytest.mark.parametrize("datei,erwartet", ERWARTET.items())
def test_regeln_lesen_musterrechnungen(datei, erwartet):
    r = extrahiere_mit_regeln(pdf_zu_text((BEISPIELE / datei).read_bytes()))
    assert (r.lieferant, r.rechnungsnummer, r.brutto) == erwartet


def test_maskierung_entfernt_iban_und_email():
    text = "IBAN: DE89 3704 0044 0532 0130 00\nKontakt: buchhaltung@firma.example"
    maskiert = maskieren(text)
    assert "3704" not in maskiert and "@" not in maskiert


class AttrappenClient:
    """Ersetzt die Claude-API im Test und merkt sich, was gesendet wurde."""

    def __init__(self, antwort: dict):
        self.antwort = antwort
        self.gesendet = None
        self.messages = self

    def create(self, **kwargs):
        self.gesendet = kwargs
        block = SimpleNamespace(type="text", text=json.dumps(self.antwort))
        return SimpleNamespace(stop_reason="end_turn", content=[block])


def test_ki_extraktion_mit_attrappe():
    text = pdf_zu_text((BEISPIELE / "01_nordwind_buerobedarf.pdf").read_bytes())
    client = AttrappenClient({"lieferant": "Nordwind Bürobedarf GmbH", "rechnungsnummer": "RE-2026-1047",
                              "rechnungsdatum": "2026-10-02", "netto": 1166.4, "mwst_satz": 19,
                              "mwst_betrag": 221.62, "brutto": 1388.02, "waehrung": "eur"})
    ergebnis = extrahiere(text, "ki", client=client)
    assert ergebnis.quelle == "ki"
    assert ergebnis.rechnung.brutto == 1388.02 and ergebnis.rechnung.waehrung == "EUR"
    assert ergebnis.rechnung.iban == "DE43000123450000004711"  # lokal erkannt
    gesendeter_text = client.gesendet["messages"][0]["content"]
    assert "DE43" not in gesendeter_text and "[IBAN entfernt]" in gesendeter_text
    assert client.gesendet["output_config"]["format"]["type"] == "json_schema"


def test_ki_fehler_faellt_auf_regeln_zurueck():
    class KaputterClient:
        messages = SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(ConnectionError("offline")))

    text = pdf_zu_text((BEISPIELE / "02_elbtal_it_service.pdf").read_bytes())
    ergebnis = extrahiere(text, "ki", client=KaputterClient())
    assert ergebnis.quelle == "regeln" and "ConnectionError" in ergebnis.hinweis
    assert ergebnis.rechnung.rechnungsnummer == "ET-48213"


# ------------------------------------------------------------ API

def test_kompletter_ablauf_ueber_die_api():
    with TestClient(app) as client:
        client.delete("/api/rechnungen")
        antwort = client.post("/api/beispiele", data={"modus": "regeln"}).json()
        status = {r["dateiname"]: r["status"] for r in antwort["rechnungen"]}
        assert status == {
            "01_nordwind_buerobedarf.pdf": "ok",
            "02_elbtal_it_service.pdf": "ok",
            "03_alster_catering.pdf": "pruefen",
            "04_hanse_druck_medien.pdf": "fehler",
            "05_nordwind_buerobedarf_kopie.pdf": "fehler",
            "06_kieler_software.pdf": "fehler",
            "07_nordlicht_reinigung.pdf": "ok",
        }

        # Fehlerhafte Rechnung kann nicht freigegeben werden
        druck = next(r for r in antwort["rechnungen"] if r["dateiname"].startswith("04"))
        assert client.post(f"/api/rechnungen/{druck['id']}/freigabe", json={"freigegeben": True}).status_code == 409

        # Mensch korrigiert den Bruttobetrag -> Regeln laufen erneut -> ok
        korrektur = {k: druck[k] for k in ["lieferant", "rechnungsnummer", "rechnungsdatum", "netto",
                                           "mwst_satz", "mwst_betrag", "iban"]}
        korrektur["brutto"] = 812.77
        neu = client.put(f"/api/rechnungen/{druck['id']}", json=korrektur).json()
        assert neu["status"] == "ok"
        assert client.post(f"/api/rechnungen/{druck['id']}/freigabe", json={"freigegeben": True}).json()["freigegeben"]

        # Keine PDF -> Fehlermeldung statt Absturz
        falsch = client.post("/api/rechnungen", files={"dateien": ("notiz.pdf", b"kein pdf", "application/pdf")}).json()
        assert falsch["fehler"] and not falsch["rechnungen"]
