# R13bf — vier Harness-Fixes aus den Batches B230–B234

Auftrag des Nutzers (2026-10-01), vier Punkte, je ein Commit. Harness pausiert
(`state=GATE_APPROVAL batch=234`, kein Worker) — die volle Reihe ist erlaubt.

| Teil | Anlass | Datei(en) |
|---|---|---|
| A | Aussensicht B234, Befund **M234-2** (Fehlalarm brach B234 ab) | `hx/streamjson.py`, `tools/check_abbau.py` |
| B | Aussensicht B234, Befund **M234-1** (Bilanz ohne Preflight) | `hx/stand.py`, `hx/bilanz.py` |
| C | Aussensicht B233, Befund **M233-7** (Preflight-Anteil) | `hx/stand.py` |
| D | offene Frage aus Review b233 (zweiter Preflight nach Fortsetzung) | `hx/worker.py`, `prompts/reviewer.md` |

---

## Teil A — Prozess-Detektor: wörtliche PID-Liste ist gezielt (M234-2)

### Der Befund (gemessen)

B234 wurde **vom Harness abgebrochen**: der Prozess-Detektor `streamjson.abbau_gefahr`
meldete „Prozessliste pauschal abgeräumt (ohne feste Nummer und ohne CommandLine-Filter) —
kann den Harness treffen“, der Lauf endete nach 66,5 min (`runs/b234/result.json`,
`killed_reason: event`); die Arbeit lag danach im Stash `harness-wip-b234`.

Der beanstandete Befehl steht im Mitschnitt des abgebrochenen ersten Laufs:

    runs/b234/stream-v1.jsonl:40020   (PowerShell)
    foreach ($id in @(704,13960,18296)) { try { Stop-Process -Id $id -Force } catch {} };
    "killed"; Get-CimInstance Win32_Process -Filter "Name='hybrid_lauf.exe'" |
      Measure-Object | Select-Object -ExpandProperty Count

Die drei Nummern stammen aus dem Ergebnis der vorigen Abfrage
(`runs/b234/stream-v1.jsonl:39715`: „704/13960/18296 … CPU=878/878/873“, drei eigene
`hybrid_lauf.exe`, gestartet 10:28:57 vom eigenen Bisektionslauf). Es war also ein
**gezielter** Abbau dreier eigener, fest benannter Prozesse — genau das, was R13i erlaubt.

Der Detektor erkannte das nicht: `_ABBau_ID` verlangte eine **Ziffer direkt nach `-Id`**
(`stop-process\s+-id\s+\d`, `hx/streamjson.py:166`) — hier steht `$id`. Und `get-ciminstance`
galt als Beleg für eine pauschale Liste (`:165`), obwohl das `Get-CimInstance` nur die
**Zahl der verbliebenen** Prozesse ausgibt.

### Die Regel (jetzt)

`abbau_gefahr` prüft in dieser Reihenfolge (jede Stufe nennt ihren Grund):

1. `$_.CPU` → **Gefahr** (CPU-Zeit-Muster; traf in b178 den Harness).
2. `Stop-Process … -Name` / `taskkill /IM` → **Gefahr** (trifft jeden `python.exe`).
3. `CommandLine -like` → **harmlos** (gezielte Auswahl, R13i; bleibt unverändert).
4. feste Nummer (`-Id 1234`, neu auch `-Id @(704,13960)`) **oder wörtliche Liste**
   (`foreach ($id in @(704,13960,18296)) { … Stop-Process -Id $id }`) → **harmlos**.
5. Schleife, deren Nummernquelle **keine wörtlichen Zahlen** sind (`$liste`,
   `(Get-Process python)`) mit `Stop-Process -Id $var` → **Gefahr** (neu, Gegenprobe).
6. `Get-Process`/`Get-CimInstance` ohne feste Nummer und ohne Filter → **Gefahr**.

Die beiden Erkennungen stehen in eigenen Funktionen (`_abbau_feste_liste`,
`_abbau_schleife_variable`); verlangt wird **beides**: eine rein numerische Liste im
Schleifenkopf UND dieselbe Variable als `-Id` eines `Stop-Process`. Absichtlich **nicht**
erkannt wird die Zuweisung vor der Schleife
(`$ids = 704,13960,18296; foreach ($id in $ids) …`) — der Detektor rät nicht, und der
Fehlalarm war die teurere Richtung.

### Messung (vorher/nachher, dieselbe Sonde)

`docs/_r13bf_abbau.py` liest **jeden** Mitschnitt (`runs/b*/stream*.jsonl`, auch
`stream-v1`, Fortsetzungen) und bewertet alle Shell-Aufrufe mit einem Abbau-Wort:

| Stand | Aufrufe mit Abbau-Wort | gemeldet |
|---|---|---|
| vorher (`docs/_r13bf_abbau_vorher.txt`) | 26 | **1** — und zwar der Fehlalarm in B234 |
| nachher (`docs/_r13bf_abbau.txt`) | 26 | **0** |

Zusatzbefund der Sonde: die 26 Aufrufe verteilen sich auf **alle** Batches; der
b178-CPU-Befehl steht **nicht** als Shell-Aufruf im Mitschnitt (dort nur als Text in
`Write`-Inhalten). Deshalb prüft `tools/check_abbau.py` ihn weiter als **Fall der
Vorlagenliste** (10 → 15 Fälle) und die Gegenprobe läuft seit R13bf über alle Batches,
ZIP-fest (`retention.mitschnitt_zeilen`, R13p) mit der Erwartung „kein gemeldeter Befehl“.

    tools/check_abbau.py: Fehlbewertungen 0 (15 Fälle), Gegenprobe 0 gemeldete Befehle
    Beleg: docs/_abbau_beleg.txt

### Tests

`tests/test_r13i_fixes.py::TestFesteListe` (6 Tests): der **echte** B234-Befehl aus
`stream-v1.jsonl:40020` darf nicht auslösen (und seine kürzeste Form ebenso), `$p | Stop-Process`
und `Stop-Process -Id @(704,13960)` gelten als gezielt, der dokumentierte eigene
Hintergrundlauf (`Start-Process -PassThru` … `Stop-Process -Id $p.Id`) bleibt harmlos; drei
**Rotproben** bleiben erkannt (Variablenliste, `Get-Process`-Auswahl in der Schleife,
`Get-CimInstance`-Auswahl) und der Wächter im Mitschnitt (`StreamStats.abbau`) hält den
B234-Befehl nicht fest, die Variablenliste schon.
Fallstrick im Test: zwei `feed`-Zeilen brauchen **verschiedene** Werkzeug-Kennungen, sonst
dedupliziert `StreamStats` die zweite (im ersten Anlauf `0 != 1`).

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
