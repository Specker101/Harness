# R13ay-Belege (2026-09-30): die zwei Kennzahlen aus M219-3

Auftrag (Aussensicht B219, Befund 3, Gewicht mittel): **Paket E offen** aus der jüngsten
Messdatei `analysis/_m<N>/_c_paket_e*.txt` mit Datum lesen (nicht aus der B208-Ist-Spalte);
fehlt eine Messung, „nicht gemessen seit B<k>". Den **SOLL-KOEPFE-Median** über die
**Zuwächse** der C Koepfe je C-Batch bilden, nicht über die Gesamtzahl. Test mit den echten
Werten (26 offen; Zuwächse +7, +5).

## 1. Paket E offen — vorher/nachher (gemessen)

| | Wert | Quelle |
|---|---|---|
| vorher (BILANZ-Eingabe) | **38 Koepfe / 2674 Insn → „13 C-Batches"** | `port-batch208-hybrid-kern-2026-09-28.md:214` (Ist-Spalte) |
| gemessen | **26 Koepfe / 2114 Insn** | `analysis/_m219/_c_paket_e_nachher.txt:127` |
| jetzt | `Paket E offen: 26 Koepfe / 2114 Insn   [gemessen B219, 2026-09-30 03:33: _m219/_c_paket_e_nachher.txt]   (B210 -> B219: 12 Koepfe / 560 Insn gebaut)` | `bilanz.gesamt_block` |

Neu: `stand.paket_e_messung(cfg)` liest die jüngste Messung aus
`analysis/_m<N>/_c_paket_e*.txt` (Ordner `_m<N>` = Batch; `_archiv/` zählt **nicht**),
mit `Paket E, offen GESAMT   :   <k> Koepfe / <i> Insn`, dem Messdatum aus dem Dateikopf
(`# Messung: 2026-09-30 03:33, HEAD …`) und der Zeilennummer. Ausgewählt wird nach
( Datum, Änderungszeit, `nachher` vor `vorher`, Name).

**Warum `nachher` vor `vorher`:** gemessen tragen in B219 `_c_paket_e_vorher.txt` und
`_c_paket_e_nachher.txt` **dasselbe** Datum und denselben HEAD (Befund M219-4 — die
„Vorher"-Messung war keine); der Dateiname entscheidet. Ist eine ältere Datei mit
**demselben** Wert vorhanden, nennt die BILANZ das ausdrücklich
(`Vorher-Messung B219 identisch - keine echte Vorher-Messung`), statt einen Null-Delta als
Messung auszugeben.

Verbraucher: `bilanz.gesamt_block` (Telegram `/bilanz` **und** der BILANZ-Block der
Außensicht), `stand.durchsatz` (`offen_koepfe`/`offen_insn` → `batches_koepfe`/
`batches_insn`), `stand.durchsatz_zeilen` (`offen (Paket E, C-Arbeitsvorrat): …`, die
HYPOTHESIS-Hochrechnung, die Quellenzeile) und die Zeile „Projektzahl `c_kopf.py paket_e`"
(dort stand fest `274 / 38`). Fehlt jede Messung: `nicht gemessen seit B<k>` (k = Batch des
letzten Dokuments mit einer Paket-E-Zeile) und **keine** Hochrechnung.

## 2. SOLL-KOEPFE-Median — über die Zuwächse

| | Wert |
|---|---|
| vorher | Median der **Summen** der C Koepfe: 88 (höchstens ca. 114) — beschreibt den halben Bestand |
| jetzt | `MEDIAN der 2 Zuwaechse der C Koepfe je C-Batch mit SOLL-KOEPFE > 0 (+5 (B219), +7 (B216)): 6 Koepfe je C-Batch (Ziel des naechsten Batches: hoechstens ca. 8)` + `(Summen-Mittel derselben Batches, nur zur Einordnung: B219 90, B216 85)` |

`stand.plan_ist_text` bildet den Median über `c_delta` (die Änderung der gemessenen C Koepfe
gegenüber dem Vorgänger-Batch, `stand.plan_ist`), gefiltert auf C-Batches mit
`SOLL-KOEPFE > 0`. Die Summen stehen nur noch als Einordnung daneben — sie sind die Zahl,
die der Reviewer in `b219/review.md` von Hand korrigiert hatte.

## 3. Tests

`harness/tests/test_r13ay_fixes.py` — **16 Tests**, darunter die **echten Werte** gegen das
Decomp-Repo (nur lesend, mit `skipIf`):

* `paket_e_messung`: Werte/Datum/Batch/Zeile, jüngste gewinnt, `nachher` vor `vorher` bei
  gleichem Datum, `vorher` = nächste **andere** Messung, keine Messung → `{}`, `_archiv/`
  zählt nicht;
* `paket_e_offen_text` mit und ohne Messung;
* `durchsatz`/`durchsatz_zeilen`: offener Vorrat aus der Messung, ohne Messung **keine**
  alte Zahl; `bilanz.gesamt_block` mit Messung + Delta (B210 → B219) und mit identischer
  „Vorher"-Datei;
* `plan_ist_text`: Median über die Zuwächse (+7/+5 → 6, Ziel ca. 8) und der Fall ohne
  Vorgängerwert;
* `TestEchteWerte`: 26/2114 (nicht 38), BILANZ-Zeile, Median 6 (nicht 88).

Angepasst (die alten Erwartungen prüften die **abgelöste** Quelle):
`test_r13x_fixes.py` (4 Tests → messungsbasiert, Messdateien werden in die Fixture kopiert),
`test_r13s_fixes.py`, `test_r13ac_fixes.py` (Median-Erwartung), `test_r13t_fixes.py`
(Paket-E-HYPOTHESIS-Zeile braucht jetzt eine Messung).

## 4. Offen

* Die Zeile `(2) nicht ausgefuehrt, Paket E: 1 Koepfe / 38 Insn` kommt aus der kanonischen
  Bilanzdatei des **Workers** (`_m219/_bilanz219.txt`), nicht aus dem Harness-Parser — sie
  bleibt, wie der Worker sie schreibt.
* Der laufende Harness hat die neue Quelle erst nach einem Neustart.
