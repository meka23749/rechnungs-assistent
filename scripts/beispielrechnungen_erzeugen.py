"""Erzeugt fiktive Musterrechnungen für die Demo.

Alle Firmen, Adressen und Bankdaten sind frei erfunden. Jede Rechnung trägt
deutlich den Vermerk MUSTERRECHNUNG. Die Bankleitzahlen beginnen mit 0 und
existieren daher in Deutschland nicht.

Aufruf:  python scripts/beispielrechnungen_erzeugen.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ZIEL = Path(__file__).resolve().parent.parent / "beispielrechnungen"
EMPFAENGER = ["Beispiel Handels GmbH", "Einkauf / Buchhaltung", "Industriestraße 5", "22844 Norderstedt"]


def iban(blz: str, konto: str) -> str:
    """Deutsche IBAN mit korrekter Prüfziffer (fiktive BLZ)."""
    bban = blz + konto.zfill(10)
    zahl = int(bban + "131400")  # 'DE' -> 13 14, Prüfziffer 00
    pruefziffer = 98 - zahl % 97
    roh = f"DE{pruefziffer:02d}{bban}"
    return " ".join(roh[i:i + 4] for i in range(0, len(roh), 4))


def betrag(wert: Decimal) -> str:
    text = f"{wert:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def runden(wert: Decimal) -> Decimal:
    return wert.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Muster:
    datei: str
    firma: str
    adresse: str
    nummer: str
    datum: str
    positionen: list[tuple[str, int, str]]  # Beschreibung, Menge, Einzelpreis
    steuersatz: int = 19
    layout: str = "A"
    iban: str | None = None
    brutto_aufschlag: Decimal = Decimal("0")  # absichtlicher Rechenfehler
    vermerk: str | None = None
    zahlungstext: str = "Bitte überweisen Sie den Betrag innerhalb von 14 Tagen ohne Abzug."
    extra: dict = field(default_factory=dict)


def zeichne(m: Muster) -> None:
    pfad = ZIEL / m.datei
    c = canvas.Canvas(str(pfad), pagesize=A4)
    c.setTitle(f"Musterrechnung {m.nummer} (fiktiv)")
    breite, hoehe = A4
    links, rechts = 20 * mm, breite - 20 * mm
    tinte = HexColor("#1B2A41")
    grau = HexColor("#5B6B7F")

    # Vermerk oben
    c.setFillColor(HexColor("#FDECEA"))
    c.rect(0, hoehe - 11 * mm, breite, 11 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#B3261E"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(links, hoehe - 7 * mm, "MUSTERRECHNUNG - fiktive Testdaten für eine Software-Demo")

    # Absender
    y = hoehe - 28 * mm
    c.setFillColor(tinte)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(links, y, m.firma)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(grau)
    c.drawString(links, y - 6 * mm, m.adresse)

    # Empfänger
    y -= 22 * mm
    c.setFillColor(tinte)
    c.setFont("Helvetica", 10.5)
    for zeile in EMPFAENGER:
        c.drawString(links, y, zeile)
        y -= 5 * mm

    # Kopfdaten
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 15)
    c.drawString(links, y, "Rechnung" if m.layout == "A" else "RECHNUNG")
    if m.vermerk:
        c.setFillColor(HexColor("#B3261E"))
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(rechts, y, m.vermerk)
        c.setFillColor(tinte)
    y -= 9 * mm
    c.setFont("Helvetica", 10)
    if m.layout == "A":
        kopf = [("Rechnungsnummer:", m.nummer), ("Rechnungsdatum:", m.datum), ("Kundennummer:", "K-20931")]
    else:
        kopf = [("Re.-Nr.", m.nummer), ("Datum", m.datum), ("Kunden-Nr.", "40-1187")]
    for etikett, wert in kopf:
        c.drawString(links, y, etikett)
        c.drawString(links + 38 * mm, y, wert)
        y -= 5.5 * mm

    # Positionen
    y -= 6 * mm
    spalten = [links, links + 12 * mm, links + 100 * mm, links + 128 * mm, rechts]
    titel = (["Pos.", "Beschreibung", "Menge", "Einzelpreis", "Gesamt"] if m.layout == "A"
             else ["Pos.", "Artikel / Leistung", "Anzahl", "Preis", "Betrag"])
    c.setFont("Helvetica-Bold", 9.5)
    for i, t in enumerate(titel):
        (c.drawRightString if i == 4 else c.drawString)(spalten[i], y, t)
    c.setStrokeColor(HexColor("#C9D6E3"))
    c.line(links, y - 2 * mm, rechts, y - 2 * mm)
    y -= 7.5 * mm

    waehrung = "€" if m.layout == "A" else "EUR"
    netto = Decimal("0")
    c.setFont("Helvetica", 9.5)
    for nr, (text, menge, preis) in enumerate(m.positionen, start=1):
        einzel = Decimal(preis)
        gesamt = einzel * menge
        netto += gesamt
        c.drawString(spalten[0], y, str(nr))
        c.drawString(spalten[1], y, text)
        c.drawString(spalten[2], y, str(menge))
        c.drawString(spalten[3], y, f"{betrag(einzel)} {waehrung}")
        c.drawRightString(spalten[4], y, f"{betrag(gesamt)} {waehrung}")
        y -= 6 * mm
    c.line(links, y + 2 * mm, rechts, y + 2 * mm)

    steuer = runden(netto * m.steuersatz / 100)
    brutto = netto + steuer + m.brutto_aufschlag

    # Summen
    y -= 6 * mm
    x_etikett = links + 100 * mm
    if m.layout == "A":
        summen = [("Nettobetrag:", netto), (f"zzgl. {m.steuersatz} % MwSt.:", steuer), ("Gesamtbetrag:", brutto)]
    else:
        summen = [("Summe netto", netto), (f"USt {m.steuersatz} %", steuer), ("Rechnungsbetrag", brutto)]
    for i, (etikett, wert) in enumerate(summen):
        c.setFont("Helvetica-Bold" if i == 2 else "Helvetica", 10)
        c.drawString(x_etikett, y, etikett)
        c.drawRightString(rechts, y, f"{betrag(wert)} {waehrung}")
        y -= 6 * mm

    # Zahlung
    y -= 10 * mm
    c.setFont("Helvetica", 9.5)
    c.drawString(links, y, m.zahlungstext)
    y -= 5.5 * mm
    if m.iban:
        c.drawString(links, y, f"Bankverbindung: Musterbank Nord, IBAN: {m.iban}, BIC: MUSTDEXXXXX")
        y -= 5.5 * mm

    # Fußzeile
    c.setFont("Helvetica", 7.5)
    c.setFillColor(grau)
    c.drawString(links, 18 * mm, f"{m.firma}, {m.adresse.split(' · ')[0]}, USt-IdNr.: DE000000000 (fiktiv)")
    c.drawString(links, 14 * mm, "Alle Firmen, Personen, Adressen und Bankdaten auf diesem Dokument sind frei erfunden.")
    c.save()


def main() -> None:
    ZIEL.mkdir(exist_ok=True)
    for alt in ZIEL.glob("*.pdf"):
        alt.unlink()

    nordwind = dict(
        firma="Nordwind Bürobedarf GmbH",
        adresse="Musterweg 12 · 22846 Norderstedt · Tel. 040 0000000 · rechnung@nordwind-buero.example",
        nummer="RE-2026-1047", datum="02.10.2026",
        positionen=[("Kopierpapier A4, 500 Blatt", 40, "4.95"), ("Tonerkartusche schwarz", 6, "54.90"),
                    ("Ordner A4, breit", 60, "2.35"), ("Bürostuhl, ergonomisch", 2, "249.00")],
        iban=iban("00012345", "4711"),
    )
    kiel_iban_korrekt = iban("00067890", "815")
    # Zahlendreher in der IBAN: zwei Ziffern vertauscht -> Prüfziffer passt nicht mehr
    kiel_iban_falsch = kiel_iban_korrekt[:-2] + kiel_iban_korrekt[-1] + kiel_iban_korrekt[-2]

    muster = [
        Muster("01_nordwind_buerobedarf.pdf", **nordwind),
        Muster("02_elbtal_it_service.pdf", "Elbtal IT-Service KG",
               "Am Deich 3 · 21029 Hamburg · service@elbtal-it.example",
               "ET-48213", "25.09.2026",
               [("Notebook 14 Zoll, 16 GB RAM", 2, "899.00"), ("Dockingstation USB-C", 2, "149.00"),
                ("Einrichtung und Datenübernahme (Std.)", 3, "85.00")],
               layout="B", iban=iban("00054321", "220077")),
        Muster("03_alster_catering.pdf", "Alster Catering GmbH",
               "Seeufer 8 · 22085 Hamburg · Tel. 040 0000001",
               "AC-2026-311", "29.09.2026",
               [("Lunchpaket, vegetarisch", 25, "12.90"), ("Obstkorb, groß", 3, "29.00")],
               steuersatz=7, zahlungstext="Der Betrag wird vereinbarungsgemäß per SEPA-Lastschrift eingezogen."),
        Muster("04_hanse_druck_medien.pdf", "Hanse Druck & Medien GmbH",
               "Papierstraße 21 · 23552 Lübeck · auftrag@hanse-druck.example",
               "HD-7741", "30.09.2026",
               [("Visitenkarten, 500 Stück", 4, "39.00"), ("Flyer DIN A5, 2.000 Stück", 1, "289.00"),
                ("Roll-up-Banner 85 x 200 cm", 2, "119.00")],
               layout="B", iban=iban("00098765", "31337"), brutto_aufschlag=Decimal("10.00")),
        Muster("05_nordwind_buerobedarf_kopie.pdf", **nordwind, vermerk="KOPIE"),
        Muster("06_kieler_software.pdf", "Kieler Software Lizenzen GmbH",
               "Hafenblick 5 · 24103 Kiel · lizenzen@kieler-software.example",
               "KSL-2026-0918", "01.10.2026",
               [("Lizenz Projektsoftware, 12 Monate", 10, "96.00")],
               iban=kiel_iban_falsch),
        Muster("07_nordlicht_reinigung.pdf", "Nordlicht Gebäudereinigung GmbH",
               "Lindenallee 40 · 22850 Norderstedt · Tel. 040 0000002",
               "NL-0926-118", "30.09.2026",
               [("Unterhaltsreinigung Büro, September", 1, "780.00"), ("Fensterreinigung", 1, "240.00")],
               layout="B", iban=iban("00011223", "990011")),
        # Typischer Betrugsversuch: bekannter Lieferant, gültige, aber neue IBAN
        Muster("08_elbtal_it_service_neue_bank.pdf", "Elbtal IT-Service KG",
               "Am Deich 3 · 21029 Hamburg · service@elbtal-it.example",
               "ET-48377", "08.10.2026",
               [("Wartungsvertrag IT, Oktober", 1, "450.00"), ("Lizenz Virenschutz, 10 Geräte", 1, "189.00")],
               layout="B", iban=iban("00077777", "556677"),
               zahlungstext="Bitte beachten Sie unsere NEUE Bankverbindung. Zahlung innerhalb von 7 Tagen."),
    ]
    for m in muster:
        zeichne(m)
        print("erzeugt:", m.datei)


if __name__ == "__main__":
    main()
