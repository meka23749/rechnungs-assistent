"""Automatische Prüfregeln für ausgelesene Rechnungen.

Die KI liest aus, die Regeln prüfen: Jede Zahl wird nachgerechnet, bevor ein
Mensch die Rechnung freigibt.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date

from .extraktion import Rechnung

TOLERANZ = 0.02  # Rundungsdifferenz in Euro
UEBLICHE_STEUERSAETZE = {19.0, 7.0, 0.0}


@dataclass
class Pruefpunkt:
    regel: str
    status: str  # "ok" | "warnung" | "fehler"
    meldung: str

    def als_dict(self) -> dict:
        return asdict(self)


def euro(betrag: float) -> str:
    """1234.5 -> '1.234,50 €'"""
    text = f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def iban_gueltig(iban: str) -> bool:
    """Prüfziffer nach ISO 13616 (Modulo 97)."""
    s = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    if s.startswith("DE") and len(s) != 22:
        return False
    umgestellt = s[4:] + s[:4]
    zahl = "".join(str(int(zeichen, 36)) for zeichen in umgestellt)
    return int(zahl) % 97 == 1


def pruefe(r: Rechnung, duplikat_von: str | None = None, heute: date | None = None) -> list[Pruefpunkt]:
    heute = heute or date.today()
    punkte: list[Pruefpunkt] = []

    # 1. Pflichtfelder
    pflicht = {"lieferant": "Lieferant", "rechnungsnummer": "Rechnungsnummer",
               "rechnungsdatum": "Rechnungsdatum", "netto": "Nettobetrag", "brutto": "Bruttobetrag"}
    fehlend = [name for feld, name in pflicht.items() if getattr(r, feld) in (None, "")]
    if fehlend:
        punkte.append(Pruefpunkt("Pflichtfelder", "fehler", "Nicht gefunden: " + ", ".join(fehlend)))
    else:
        punkte.append(Pruefpunkt("Pflichtfelder", "ok", "Alle Pflichtfelder vorhanden"))

    # 2. Netto + MwSt = Brutto
    if None not in (r.netto, r.mwst_betrag, r.brutto):
        summe = round(r.netto + r.mwst_betrag, 2)
        differenz = round(r.brutto - summe, 2)
        if abs(differenz) <= TOLERANZ:
            punkte.append(Pruefpunkt("Summe", "ok", f"Netto + MwSt = {euro(summe)} stimmt mit dem Bruttobetrag überein"))
        else:
            punkte.append(Pruefpunkt("Summe", "fehler",
                f"Netto + MwSt = {euro(summe)}, auf der Rechnung stehen {euro(r.brutto)} "
                f"(Differenz {euro(differenz)})"))

    # 3. Steuerbetrag = Netto × Steuersatz
    if None not in (r.netto, r.mwst_satz, r.mwst_betrag):
        erwartet = round(r.netto * r.mwst_satz / 100, 2)
        if abs(erwartet - r.mwst_betrag) <= TOLERANZ:
            punkte.append(Pruefpunkt("Steuerbetrag", "ok", f"{r.mwst_satz:g} % von {euro(r.netto)} = {euro(erwartet)}"))
        else:
            punkte.append(Pruefpunkt("Steuerbetrag", "fehler",
                f"{r.mwst_satz:g} % von {euro(r.netto)} ergibt {euro(erwartet)}, berechnet wurden {euro(r.mwst_betrag)}"))

    # 4. Steuersatz plausibel
    if r.mwst_satz is not None and float(r.mwst_satz) not in UEBLICHE_STEUERSAETZE:
        punkte.append(Pruefpunkt("Steuersatz", "warnung",
            f"Ungewöhnlicher Steuersatz {r.mwst_satz:g} % (üblich: 19 % oder 7 %)"))

    # 5. Rechnungsdatum
    if r.rechnungsdatum:
        try:
            datum = date.fromisoformat(r.rechnungsdatum)
            if datum > heute:
                punkte.append(Pruefpunkt("Datum", "warnung", "Rechnungsdatum liegt in der Zukunft"))
            else:
                punkte.append(Pruefpunkt("Datum", "ok", f"Rechnungsdatum {datum:%d.%m.%Y}"))
        except ValueError:
            punkte.append(Pruefpunkt("Datum", "fehler", f"Ungültiges Datum: {r.rechnungsdatum}"))

    # 6. Bankverbindung
    if not r.iban:
        punkte.append(Pruefpunkt("IBAN", "warnung", "Keine IBAN gefunden, Zahlungsweg manuell prüfen"))
    elif iban_gueltig(r.iban):
        punkte.append(Pruefpunkt("IBAN", "ok", "IBAN-Prüfziffer gültig"))
    else:
        punkte.append(Pruefpunkt("IBAN", "fehler",
            "IBAN-Prüfziffer ungültig: Tippfehler oder geänderte Bankdaten. Vor der Zahlung beim Lieferanten telefonisch bestätigen"))

    # 7. Doppelte Rechnung
    if duplikat_von:
        punkte.append(Pruefpunkt("Duplikat", "fehler", f"Rechnungsnummer bereits erfasst ({duplikat_von})"))
    elif r.rechnungsnummer:
        punkte.append(Pruefpunkt("Duplikat", "ok", "Keine doppelte Rechnungsnummer"))

    return punkte


def pruefe_stammdaten(r: Rechnung, lieferant: dict | None) -> Pruefpunkt:
    """Vergleicht die IBAN der Rechnung mit der in den Stammdaten hinterlegten Bankverbindung."""
    if lieferant is None:
        return Pruefpunkt("Stammdaten", "warnung",
                          "Neuer Lieferant, nicht in den Stammdaten. Bankverbindung vor der ersten Zahlung telefonisch bestätigen")
    rechnung_iban = r.iban.replace(" ", "").upper() if r.iban else None
    if not rechnung_iban:
        return Pruefpunkt("Stammdaten", "ok", "Keine IBAN auf der Rechnung")
    if not lieferant.get("iban"):
        return Pruefpunkt("Stammdaten", "warnung", "Keine IBAN in den Stammdaten")
    if rechnung_iban == lieferant["iban"]:
        return Pruefpunkt("Stammdaten", "ok", "IBAN entspricht den Stammdaten")
    return Pruefpunkt("Stammdaten", "fehler",
                      f"IBAN weicht von den Stammdaten ab (hinterlegt: ...{lieferant['iban'][-4:]}). "
                      "Betrugsverdacht: Bankdaten nur nach Rückruf unter der bekannten Telefonnummer ändern")


def gesamtstatus(punkte: list[Pruefpunkt]) -> str:
    """'fehler' schlägt 'pruefen' schlägt 'ok'."""
    stati = {p.status for p in punkte}
    if "fehler" in stati:
        return "fehler"
    if "warnung" in stati:
        return "pruefen"
    return "ok"
