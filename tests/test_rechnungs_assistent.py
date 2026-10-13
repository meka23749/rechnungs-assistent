"""Tests: Regel-Extraktion und KI-Extraktion (mit Attrappe)."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402

from app.extraktion import extrahiere, extrahiere_mit_regeln, maskieren, pdf_zu_text  # noqa: E402

BEISPIELE = Path(__file__).resolve().parent.parent / "beispielrechnungen"


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
