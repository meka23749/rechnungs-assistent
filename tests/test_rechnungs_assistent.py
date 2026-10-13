"""Tests: Regel-Extraktion der Musterrechnungen."""

from pathlib import Path

import pytest

from app.extraktion import extrahiere_mit_regeln, pdf_zu_text

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
