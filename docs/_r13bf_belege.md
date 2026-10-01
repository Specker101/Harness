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
