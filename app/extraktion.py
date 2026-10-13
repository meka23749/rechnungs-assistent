"""Rechnungsdaten aus PDF-Rechnungen auslesen.

Schritt 1: Text aus dem PDF lesen, lokal mit pdfplumber.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass

import pdfplumber


@dataclass
class Rechnung:
    lieferant: str | None = None
    rechnungsnummer: str | None = None
    rechnungsdatum: str | None = None  # ISO-Format JJJJ-MM-TT
    netto: float | None = None
    mwst_satz: float | None = None  # in Prozent, z. B. 19
    mwst_betrag: float | None = None
    brutto: float | None = None
    iban: str | None = None
    waehrung: str = "EUR"

    def als_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- PDF -> Text

def pdf_zu_text(daten: bytes) -> str:
    """Liest den Text aller Seiten. Gescannte Rechnungen (Bilder) bräuchten OCR."""
    with pdfplumber.open(io.BytesIO(daten)) as pdf:
        return "\n".join((seite.extract_text() or "") for seite in pdf.pages)
