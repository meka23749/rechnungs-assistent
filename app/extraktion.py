"""Rechnungsdaten aus PDF-Rechnungen auslesen.

Regeln (reguläre Ausdrücke): läuft offline, versteht bekannte Layouts.
"""

from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from datetime import datetime

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


# ---------------------------------------------------------------- Hilfsfunktionen

BETRAG = r"(-?\d{1,3}(?:\.\d{3})+,\d{2}|-?\d+,\d{2})"
IBAN_MUSTER = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
RECHTSFORM = re.compile(r"\b(GmbH & Co\. KG|GmbH|mbH|AG|KG|OHG|GbR|UG|e\. ?K\.)\b")


def deutsche_zahl(text: str) -> float:
    """'1.234,56' -> 1234.56"""
    return float(text.replace(".", "").replace(",", "."))


def datum_iso(text: str) -> str | None:
    """'02.10.2026' oder '2026-10-02' -> '2026-10-02'"""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def finde_iban(text: str) -> str | None:
    for zeile in text.splitlines():
        if "IBAN" not in zeile.upper():
            continue
        treffer = IBAN_MUSTER.search(zeile.split("IBAN", 1)[1])
        if treffer:
            return treffer.group(0).replace(" ", "")
    return None


# ---------------------------------------------------------------- Regel-Extraktion

def _suche(muster: list[str], text: str) -> str | None:
    for m in muster:
        treffer = re.search(m, text, re.IGNORECASE | re.MULTILINE)
        if treffer:
            return treffer.group(1).strip()
    return None


def _lieferant(text: str) -> str | None:
    """Erste Zeile mit Rechtsform (GmbH, KG ...) = Absender der Rechnung."""
    for zeile in text.splitlines():
        if "MUSTER" in zeile.upper():
            continue
        if RECHTSFORM.search(zeile):
            teil = next(t for t in re.split(r"\s+·\s+|,\s+", zeile) if RECHTSFORM.search(t))
            return teil.strip()
    return None


def _mwst(text: str) -> tuple[float | None, float | None]:
    """Sucht eine Zeile wie 'zzgl. 19 % MwSt.: 234,56 €' oder 'USt 19 % 446,69 EUR'."""
    for zeile in text.splitlines():
        if not re.search(r"MwSt|USt|Umsatzsteuer|Mehrwertsteuer", zeile, re.IGNORECASE):
            continue
        satz = re.search(r"(\d{1,2}(?:,\d+)?)\s*%", zeile)
        betraege = re.findall(BETRAG, zeile)
        if satz and betraege:
            return deutsche_zahl(satz.group(1)), deutsche_zahl(betraege[-1])
    return None, None


def extrahiere_mit_regeln(text: str) -> Rechnung:
    nummer = _suche([
        r"Rechnungs-?\s*(?:nummer|nr\.?)\s*:?\s*([A-Z0-9][A-Z0-9\-/]+)",
        r"Re\.?-?\s*Nr\.?\s*:?\s*([A-Z0-9][A-Z0-9\-/]+)",
    ], text)
    datum = _suche([
        r"Rechnungsdatum\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})",
        r"^\s*Datum\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})",
    ], text)
    netto = _suche([
        rf"(?:Nettobetrag|Summe\s+netto|Zwischensumme)\s*:?\s*(?:EUR\s*)?{BETRAG}",
    ], text)
    brutto = _suche([
        rf"(?:Gesamtbetrag|Rechnungsbetrag|Bruttobetrag|Gesamtsumme|Endbetrag|Zu zahlen)\s*:?\s*(?:EUR\s*)?{BETRAG}",
    ], text)
    satz, steuer = _mwst(text)
    return Rechnung(
        lieferant=_lieferant(text),
        rechnungsnummer=nummer,
        rechnungsdatum=datum_iso(datum) if datum else None,
        netto=deutsche_zahl(netto) if netto else None,
        mwst_satz=satz,
        mwst_betrag=steuer,
        brutto=deutsche_zahl(brutto) if brutto else None,
        iban=finde_iban(text),
    )
