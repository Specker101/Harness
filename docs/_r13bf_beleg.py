"""R13bf: Belegabschnitte an `docs/_r13bf_belege.md` anhaengen (UTF-8, LF).

Aufruf:  python -u docs/_r13bf_beleg.py <teil>      (teil = b, c, d)
"""
from __future__ import annotations

import pathlib
import sys

ZIEL = pathlib.Path(__file__).resolve().parent / "_r13bf_belege.md"

TEIL_B = """
---

## Teil B — Bilanz ohne Preflight (M234-1)

### Der Befund (gemessen)

B234 brach **vor** dem Preflight ab (`runs/b234/result.json`: `rc 1`,
`killed_reason: event`, `preflight_laeufe: 0`), `analysis/_preflight_234.txt` gab es
nicht. Die Bilanz führte trotzdem „C Koepfe 115/6271/0 referenzgleich“ und meldete
`C Koepfe : 115 referenzgleich (110 -> 115: +5)`. Die 115 sind die **Soll-Spalte** der
Soll/Ist-Tafel des Batch-Dokuments
(`analysis/port-batch234-c-ausgefuehrte-koepfe-2026-10-01.md:49`:
`| C Koepfe | 110 / 6187 / 0 | **115 / 6271 / 0** | …`), die 110 die Ist-Spalte.

Zwei Ursachen, beide behoben:

1. `stand.ist_wert` nahm die **letzte numerische Zelle** der Zeile — in der neuen
   Tafelreihenfolge (`Ist (B233) | Soll (B234)`) ist das die **Soll-Spalte**.
2. `stand.kernzahlen` fiel für einen Batch ohne Preflight-Datei auf das Dokument zurück
   (R13x-Verhalten für die Zeit *vor* der Preflight-Ära) und trug so eine Vorhersage als
   Messwert (`hx/bilanz.py::_stand_reihe`).

### Die Änderung

| Ort | vorher | nachher |
|---|---|---|
| `stand.ist_wert` | letzte Zahlzelle der Zeile | Zellen unter einer Spaltenüberschrift mit dem Wort **Soll** zählen **nie** (`stand.tabellen_kopf` liest die Kopfzeile; ohne Kopfzeile bleibt die alte Regel) |
| `stand.kernzahlen` | Rückfall auf die Ist-Spalte für **jeden** Batch ohne Preflight-Datei | nur noch **vor** der Preflight-Ära; innerhalb der Ära setzt eine fehlende eigene Datei `c_nicht_gemessen: True` + `c_erwartet: _preflight_<N>.txt` und **keine** C-Zahl |
| `bilanz._stand_reihe` | filtert Zeilen ohne Wert heraus | behält die Lückenmarke (sonst ist die Lücke nicht benennbar) |
| `bilanz.gesamt_block` | — | eigene Zeile `B<N> nicht gemessen (keine analysis/_preflight_<N>.txt) - die Zahl bleibt auf dem Stand von B<k>` |

Die „Preflight-Ära“ beginnt beim ältesten Preflight-Batch im Fenster
(`stand.preflight_dateien`); davor (B155…B197, dort gibt es die Dateien nicht) bleibt der
Dokumentweg unverändert erhalten.

### Beleg vorher/nachher (`docs/_r13bf_bilanz.py` → `docs/_r13bf_bilanz.txt`)

Gerechnet auf der **eingefrorenen Fixture** `tests/fixtures/stand_b234_luecke`
(echter Dokumentstand 01.10.2026 10:51, ohne `_preflight_234.txt`):

```
Dokumentzeile 49 (Soll/Ist-Tafel):
  | `C Koepfe` | 110 / 6187 / 0 | **115 / 6271 / 0** | +5 Koepfe, … |

  vorher (letzte Zahlzelle)      : (115, 6271, 0)
  nachher (Ist-Spalte, R13bf)    : (110, 6187, 0)

  kernzahlen B233: c_koepfe=110 c_quelle='_preflight_233.txt' gemessen
  kernzahlen B234: c_koepfe=None NICHT GEMESSEN erwartet=_preflight_234.txt

  bilanz.gesamt_block:
    C Koepfe referenzgleich: 110 Koepfe / 6187 Faelle / 0 Abweichungen   [B233, _preflight_233.txt]
    B234 nicht gemessen (keine analysis/_preflight_234.txt) - die Zahl bleibt auf dem Stand von B233
  Gegenprobe: '115' in den Bilanzzeilen oben? nein - die Soll-Spalte ist keine Messung

  Rotprobe (mit _preflight_234.txt):
    C Koepfe referenzgleich: 115 Koepfe / 6271 Faelle / 0 Abweichungen … [B234, _preflight_234.txt]
```

Im **lebenden** Repo ist der Fall inzwischen überholt: der wiederholte B234-Lauf hat
`_preflight_234.txt` geschrieben (01.10.2026 12:53, `C Koepfe 115/6271/0`), und das
Dokument trägt ab Zeile 300 eine zweite Tafel
(`| Bilanzzeile | Soll (Vorhersage) | Ist (_preflight_234.txt) | Urteil |`) — dort steht
der Messwert in der **Ist**-Spalte, die Soll-Spalte davor wird jetzt übersprungen.
Deshalb der Fixture-Weg: der Zustand von 10:51 ist sonst nicht mehr herstellbar.

### Tests

`tests/test_r13bf_fixes.py` (10 Tests, Fixture-basiert):
Soll/Ist-Spalte (110 gewinnt gegen 115; nur-Soll-Tabelle ergibt keinen Wert; Tabelle
ohne Kopfzeile bleibt wie vorher; Paket-E-Zeile ebenso), Lücke (keine C-Zahl,
`c_nicht_gemessen`, letzter gemessener Stand B233, Bilanz nennt die Lücke und zeigt
**keine** 115), **Rotprobe** mit vorhandener Datei (115 wird gemessen, keine Lücke),
und der Schutz für alte Batches vor der Ära (Dokumentweg bleibt).
Angepasst: `tests/test_r13x_fixes.py` — `test_nur_vorhersagetafel_ergibt_keinen_ist_wert_aus_prosa`
prüft jetzt `None` (der Test hieß schon so, er prüfte aber die Soll-Spalte), und
`test_prosa_zelle_wird_nicht_als_wert_gelesen` stellt die Ist-Spalte hinter die Soll-Spalte.
"""


def main() -> int:
    teil = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    text = ZIEL.read_text(encoding="utf-8")
    if teil not in ("b", "c", "d"):
        print("teil fehlt (b|c|d)")
        return 2
    neu = {"b": TEIL_B}.get(teil, "")
    if not neu:
        print(f"Teil {teil.upper()} steht noch nicht in diesem Werkzeug")
        return 2
    marke = next(z for z in neu.splitlines() if z.startswith("## "))
    if marke in text:
        print("schon vorhanden - nichts geaendert")
        return 0
    ZIEL.write_text(text.rstrip("\n") + "\n" + neu, encoding="utf-8", newline="\n")
    print(f"Teil {teil.upper()} angehaengt, Datei jetzt "
          f"{len(ZIEL.read_text(encoding='utf-8').splitlines())} Zeilen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
