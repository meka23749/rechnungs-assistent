"""Speicherung der Rechnungen in SQLite (eine Datei, kein Server nötig)."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PFAD = Path(os.environ.get("DB_PFAD", Path(__file__).resolve().parent.parent / "rechnungen.db"))

FELDER = ["lieferant", "rechnungsnummer", "rechnungsdatum", "netto", "mwst_satz",
          "mwst_betrag", "brutto", "iban", "waehrung"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS rechnungen (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dateiname       TEXT NOT NULL,
    lieferant       TEXT,
    rechnungsnummer TEXT,
    rechnungsdatum  TEXT,
    netto           REAL,
    mwst_satz       REAL,
    mwst_betrag     REAL,
    brutto          REAL,
    iban            TEXT,
    waehrung        TEXT DEFAULT 'EUR',
    quelle          TEXT,
    hinweis         TEXT,
    dauer_ms        INTEGER,
    status          TEXT,
    pruefung        TEXT,
    freigegeben     INTEGER DEFAULT 0,
    erfasst_am      TEXT
)
"""


@contextmanager
def verbindung():
    con = sqlite3.connect(DB_PFAD)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def initialisieren() -> None:
    with verbindung() as con:
        con.execute(SCHEMA)


def _zeile(row: sqlite3.Row) -> dict:
    daten = dict(row)
    daten["pruefung"] = json.loads(daten["pruefung"] or "[]")
    daten["freigegeben"] = bool(daten["freigegeben"])
    return daten


def finde_duplikat(lieferant: str | None, nummer: str | None, ausser_id: int | None = None) -> str | None:
    """Gibt eine Beschreibung der bereits erfassten Rechnung zurück oder None."""
    if not lieferant or not nummer:
        return None
    with verbindung() as con:
        row = con.execute(
            """SELECT id, dateiname, erfasst_am FROM rechnungen
               WHERE lower(trim(lieferant)) = lower(trim(?))
                 AND lower(trim(rechnungsnummer)) = lower(trim(?))
                 AND id != ? ORDER BY id LIMIT 1""",
            (lieferant, nummer, ausser_id or -1),
        ).fetchone()
    if row is None:
        return None
    zeitpunkt = datetime.fromisoformat(row["erfasst_am"]).strftime("%d.%m.%Y %H:%M")
    return f"{row['dateiname']}, erfasst am {zeitpunkt}"


def speichern(dateiname: str, daten: dict, quelle: str, hinweis: str | None,
              dauer_ms: int, status: str, pruefung: list[dict]) -> dict:
    with verbindung() as con:
        cur = con.execute(
            f"""INSERT INTO rechnungen (dateiname, {", ".join(FELDER)}, quelle, hinweis,
                    dauer_ms, status, pruefung, erfasst_am)
                VALUES (?, {", ".join("?" for _ in FELDER)}, ?, ?, ?, ?, ?, ?)""",
            (dateiname, *[daten.get(f) for f in FELDER], quelle, hinweis, dauer_ms,
             status, json.dumps(pruefung, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
        )
        neue_id = cur.lastrowid
    return hole(neue_id)


def aktualisieren(rechnung_id: int, daten: dict, status: str, pruefung: list[dict]) -> dict:
    with verbindung() as con:
        con.execute(
            f"""UPDATE rechnungen SET {", ".join(f"{f} = ?" for f in FELDER)},
                    status = ?, pruefung = ?, freigegeben = 0 WHERE id = ?""",
            (*[daten.get(f) for f in FELDER], status, json.dumps(pruefung, ensure_ascii=False), rechnung_id),
        )
    return hole(rechnung_id)


def setze_freigabe(rechnung_id: int, freigegeben: bool) -> dict:
    with verbindung() as con:
        con.execute("UPDATE rechnungen SET freigegeben = ? WHERE id = ?", (int(freigegeben), rechnung_id))
    return hole(rechnung_id)


def hole(rechnung_id: int) -> dict | None:
    with verbindung() as con:
        row = con.execute("SELECT * FROM rechnungen WHERE id = ?", (rechnung_id,)).fetchone()
    return _zeile(row) if row else None


def alle() -> list[dict]:
    with verbindung() as con:
        rows = con.execute("SELECT * FROM rechnungen ORDER BY id").fetchall()
    return [_zeile(r) for r in rows]


def alle_loeschen() -> None:
    with verbindung() as con:
        con.execute("DELETE FROM rechnungen")
        con.execute("DELETE FROM sqlite_sequence WHERE name = 'rechnungen'")
