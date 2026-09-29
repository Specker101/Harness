# R13ao-Belege (2026-09-29, Auftrag Teil B): Hinweis bei zu frühem Preflight

Auftrag (Teil B, Wortlaut): „Enthält ein Bash-Aufruf des Workers `preflight.py`, die
Batch-Uhr liegt vor der Umschaltschwelle UND `auftrag.md` hat eine NACHRUECKLISTE
(`hat_nachrueckliste`): dem Worker unmittelbar eine Hook-Nachricht: *…* Nicht
blockieren, nur hinweisen. In `result.json`: `preflight_laeufe` (Anzahl) und
`preflight_frueh` (Anzahl vor der Schwelle mit offener Nachrückliste). Nur berichten:
`preflight_laeufe` für B206–B215 aus den `stream.jsonl`."

Teil A desselben Auftrags ist **R13an** (`docs/_r13an_belege.md`).

## 1. Wo der Hinweis entsteht

| Datei | Was |
|---|---|
| `hx/streamjson.py` | `ist_preflight_aufruf(name, eingabe)` — **eine** Regel für Hook, Zähler und Bericht |
| `hx/uhr.py` | `PREFLIGHT_HINWEIS` (Wortlaut des Auftrags), `preflight_zu_frueh(minuten, umschalt)`, `preflight_hinweis(...)` |
| `tools/batch_uhr.py` | der Hook: liest die PostToolUse-Eingabe von stdin, erkennt den Aufruf, zählt ihn, hängt den Hinweis an `additionalContext` |
| `hx/worker.py` | `write_worker_hooks` gibt `--run <runs/b<N>>` mit; `zaehle_preflight_aufrufe(rd)`; `_finish_run` schreibt die zwei Felder |

**Der Hinweis ist keine Sperre.** Er kommt als zweite Zeile hinter der BATCH-UHR-Zeile:

```
BATCH-UHR (Harness-Messung): 42.0 min von 90 min (Umschalten ab 80) …
PREFLIGHT-HINWEIS: Preflight vor der Umschwellschwelle (42.0 von 80 min). Er ist nur zulässig, wenn alle Posten der NACHRUECKLISTE erledigt sind. Sonst erst die Nachrückliste abarbeiten; ein früher Preflight muss später wiederholt werden und kostet ~10 min.
```

Der **Wortlaut ist zeichengleich** der des Auftrags — einschließlich der Schreibweise
„Umschwellschwelle" (das übrige Programm schreibt „Umschaltschwelle"). Absichtlich nicht
„korrigiert": der Text ist der Beleg, und `test_r13ao_fixes.py` hat ihn wörtlich im Test
stehen (nicht aus `hx.uhr` importiert), damit eine spätere Änderung auffällt. Das
Präfix `PREFLIGHT-HINWEIS: ` ist die einzige Zutat — ohne es wäre die Zeile von der
Uhr-Zeile nicht zu unterscheiden.

## 2. Was als „Aufruf" gilt — und warum nicht jede Erwähnung

Der Auftrag sagt „enthält ein Bash-Aufruf `preflight.py`". **Gemessen** in B206–B215
(`docs/_r13ao_messung.txt`) ist die reine Textsuche aber viel häufiger als ein Start:
23 Treffer, davon nur **14 echte Starts**. Die neun Nicht-Starts sind:

```
cd 'g:\Silent Scope Decomp'; Select-String -Path scripts/preflight.py -Pattern "selftest" …
git add scripts/m114_matrix.py scripts/c_kopf.py scripts/m149_bilanz.py scripts/preflight.py …
Get-Content scripts/preflight.py | Select-Object -First 20
$p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
       $_.CommandLine -like '*preflight.py*before*' }        (B214: Überwachung des Laufs)
```

Ein `Select-String` auf das Skript ist kein Preflight-Lauf; ein Hinweis „das darfst du
jetzt nicht" wäre dort falsch und würde sich abnutzen. Die Regel ist deshalb:

* **Start** = ein Interpreter-Token (`python`, `python.exe`, `py`) mit `preflight.py` als
  Argument im selben Befehlsteil (max. 60 Zeichen Abstand — deckt auch
  `Start-Process -FilePath python -ArgumentList "-u","scripts/preflight.py","before"` ab),
* **kein Filter** = derselbe Befehlsteil enthält `-like`, `CommandLine`, `Select-String`,
  `Get-Content` oder `git add`.

Die Zerlegung in Befehlsteile (`;`, `|`, `&&`, Zeilenumbruch) ist nötig, weil der echte
Lauf in B206 in einem Verbund steht, dessen **späterer** Teil
`Get-Content analysis/_preflight_206.txt | Select-Object -Last 30` ist — über den ganzen
Befehl geprüft hätte dieser Filter den echten Lauf verschluckt.
`nennt_preflight_nur(...)` ist die Gegenprobe für den Bericht (Hook und Zähler benutzen
sie **nicht**). **Falls die wörtliche Textsuche gewünscht ist, ist das eine Zeile in
`hx/streamjson.py` — die Zahl stünde dann bei 23 statt 14.**

## 3. Zähler (Definition nach R387)

* `preflight_laeufe` — Preflight-**Aufrufe**, die der Hook als Start erkannt hat, während
  die Batch-Uhr lief. Aufrufe, nicht Läufe: derselbe Befehl zweimal = zwei. Ohne
  Startzeit im Zustand schreibt der Hook nichts (dann bleibt es bei 0).
* `preflight_frueh` — davon die Aufrufe **vor der Umschaltschwelle**, als `auftrag.md`
  eine offene `NACHRUECKLISTE` trug: genau die Fälle, in denen der Hinweis erschien.

Quelle ist `runs/b<N>/preflight-aufrufe.jsonl` — eine Zeile je erkanntem Start
(`{"ts", "min", "frueh", "werkzeug"}`), die der Hook schreibt. **Nicht** der Mitschnitt:
ob die Nachrückliste in *diesem Moment* offen war, ist eine Laufzeit-Eigenschaft; aus
`stream.jsonl` ist sie nachträglich nicht rekonstruierbar. Eine halb geschriebene letzte
Zeile wird verworfen.

**Ab wann die Zähler greifen:** der Hook bekommt `--run` erst mit dieser Fassung. Der
laufende **B216** hat seine Einstellungsdatei schon geschrieben (ohne `--run`) und wird
deshalb **nicht** angerührt: kein Hinweis, keine Zählung, keine neue Datei unter `runs/`.
Der erste Batch mit Zählern ist der nächste gestartete.

## 4. Bericht B206–B215 (nur berichten)

Quelle `harness/runs/b<N>/stream.jsonl`, Werkzeug `docs/_r13ao_zaehlung.py`, Ausgabe
`docs/_r13ao_messung.txt`:

| Batch | Starts | nur genannt | 1. Start ab Batch-Anfang | vor der Schwelle (75 min)? | NACHRUECKLISTE im Auftrag |
|---|---|---|---|---|---|
| 206 | 1 | 2 | 53,4 min | ja | – |
| 207 | 1 | 0 | 40,6 min | ja | – |
| 208 | 1 | 1 | 14,3 min | ja | – |
| 209 | 1 | 0 | 22,8 min | ja | – |
| 210 | 2 | 2 | 32,4 min | ja | – |
| 211 | 1 | 0 | 27,0 min | ja | ja |
| 212 | 1 | 1 | 41,2 min | ja | ja |
| 213 | 1 | 0 | 92,1 min | nein | ja |
| 214 | 2 | 3 | 57,8 min | ja | ja |
| 215 | 3 | 0 | 23,0 min | ja | ja |
| **Summe** | **14** | **9** | | **9 von 10 Batches** | 5 von 10 |

Lesehilfe: „1. Start ab Batch-Anfang" rechnet ab dem **ersten Zeitstempel im Mitschnitt**
(der Harness-Start liegt Sekunden davor — die Spalte ist auf ~1 min genau), die
Schwelle ist die **heutige** (75 min = Alarm 90 − Vorlauf 15,2 aus der Preflight-Messung
B215); für die alten Batches galt die damals gemessene Zahl. „vor der Schwelle" ist
deshalb eine **Rekonstruktion**, kein Messwert des damaligen Laufs.

**Befund:** neun von zehn Batches haben den Preflight **deutlich zu früh** gestartet
(B208 nach 14 min, B215 nach 23 min), fünf davon mit offener Nachrückliste im Auftrag —
genau die Fälle, für die der Hinweis gebaut ist. Zwei bis drei Starts je Batch (B210,
B214, B215) sind Wiederholungen; bei ~10 min je Lauf sind das ~20–30 min je Batch.

## 5. Tests

`harness/tests/test_r13ao_fixes.py` — **23 Tests**: Erkennung (Starts, Erwähnungen,
Überwachung, `Read`/`Grep`, `description`, fehlende Eingabe), Wortlaut (wörtlich im Test),
Schwellengrenze, der Hook als **Unterprozess** (wie die Claude-CLI ihn aufruft:
stdin-JSON → stdout-JSON) für früh/spät/ohne Nachrückliste/fremder Befehl/ohne
`--run`/ohne `auftrag.md`/zwei Aufrufe, die Zähler samt `_finish_run` → `result.json`
(1 früh + 1 spät = `preflight_laeufe=2, preflight_frueh=1`) und die Verdrahtung
(`write_worker_hooks` gibt `--run` mit).

Volle Reihe: **983 Tests OK** in 466,8 s (`docs/_r13ao_volle_reihe.txt`).

## 6. Nicht geprüft / offen

* Ob der Hinweis beim Modell **ankommt**, ist für diese Zeile nicht erneut gemessen; der
  Weg ist der des BATCH-UHR-Hooks, der in R13ac mit echtem Lauf belegt wurde
  (`docs/_r13ac_hook.txt`).
* Der Hinweis verschwindet **nicht**, wenn der Worker die Nachrückliste im selben Lauf
  erledigt hat (`NACHRUECKLISTE ERLEDIGT` steht in seiner Antwort, nicht im Auftrag): der
  Hook liest `auftrag.md`, wie im Auftrag festgelegt. Der Text ist ein Hinweis, keine
  Sperre — ein späterer Preflight ist damit weiter möglich.
* `_RE_PREFLIGHT_FILTER` ist eine Liste gemessener Fälle, keine vollständige Grammatik
  (Grenze: ein echter Start, der im selben Befehlsteil `-like` oder `Get-Content`
  benutzt, würde nicht gezählt; gemessen kommt das in B206–B215 nicht vor).
