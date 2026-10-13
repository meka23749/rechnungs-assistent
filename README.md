# Rechnungs-Assistent

Ein internes Tool für die Buchhaltung: PDF-Eingangsrechnungen werden per KI ausgelesen, automatisch nachgerechnet, von einem Menschen freigegeben und nach Excel exportiert.

## Das Problem

In vielen Büros werden Lieferantenrechnungen noch von Hand abgetippt. Das kostet Zeit, und typische Fehler fallen oft erst bei der Zahlung auf: Rechenfehler auf der Rechnung, doppelt eingereichte Rechnungen oder eine falsche IBAN.

## Die Lösung

| Schritt | Was passiert |
| --- | --- |
| 1. PDF einlesen | Text wird lokal aus dem PDF gelesen (pdfplumber) |
| 2. Daten auslesen | Claude liefert Lieferant, Nummer, Datum und Beträge als JSON nach festem Schema. Ohne API-Schlüssel oder bei Netzwerkfehlern übernehmen Regeln (reguläre Ausdrücke) |
| 3. Nachrechnen | 7 Prüfregeln: Pflichtfelder, Netto + MwSt = Brutto, Steuerbetrag, Steuersatz, Datum, IBAN-Prüfziffer, Duplikate |
| 4. Freigabe | Ein Mensch korrigiert bei Bedarf und gibt frei. Rechnungen mit Fehlern lassen sich nicht freigeben |
| 5. Export | Excel-Datei mit Rechnungsliste, Summen und vollständigem Prüfprotokoll |

_In Arbeit: Die Schritte werden nacheinander umgesetzt._
