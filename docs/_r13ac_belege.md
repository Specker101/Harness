# R13ac - Belege (Batch-Uhr, Preflight-Trend, Zaehler-Trennung, watch-Uhr, PLAN/Median)

Anlass: Aussensicht zu B210 (`runs/meta-210.md`, Befunde M210-1 bis M210-4; M210-2 und
M210-4 ausdruecklich "Harness-Sache") und die Nutzerpruefung vom 2026-09-28 (Punkt 1-5).
Alles unten ist **gemessen**; wo etwas nur abgeleitet ist, steht es dran.

## 1) Zeit (M210-1, Nutzerpunkt 1) - der Hook-Weg ist belegt

**Frage:** erlaubt Claude Code einen `PostToolUse`-Hook, der nach JEDEM Werkzeugaufruf eine
Zeile Kontext einblendet - und kommt die Zeile beim Modell an?

**Antwort: ja, gemessen.** Beleg `docs/_r13ac_hook.txt` (Sonde
`tools/r13ac_probe_hook.py`, ein echter Worker-Aufruf mit `envs.worker_env`, Modell
`deepseek-flash[1m]`):

* Aufbau: `state/run.json` mit `worker.started_at = jetzt - 42 min`; Einstellungsdatei mit
  `PostToolUse` (ohne Matcher) -> `tools/batch_uhr.py`; Grenzen absichtlich auffaellig
  (Weich **77** min, Hart **123** min).
* Antwort des Modells (woertlich):
  `BATCH-UHR (Harness-Messung): 42.1 min von 77 min seit Batch-Start 22:26:08 (Ortszeit).
  Weichgrenze 77 min, harte Grenze 123 min. …`
* Verdikt in der Belegdatei: *"Der Hook-Text KOMMT BEIM MODELL AN (BATCH-UHR-Zeile mit
  77/123 genannt)."*

Die CLI-Doku dazu (geprueft, `code.claude.com/docs/en/hooks`): `PostToolUse` liefert
`hookSpecificOutput.additionalContext`, das "next to the tool result" als System-Reminder
eingefuegt wird; Einstellungsdateien kommen ueber `--settings <datei>` in den Lauf
(`claude --help`, Version 2.1.282). Zwei Hinweise der Doku sind uebernommen:

* Hooks aus einer Einstellungsdatei laufen in `-p`/SDK-Sitzungen auch in einem nicht
  "vertrauten" Ordner - deshalb wird die Datei **vom Harness erzeugt** (nicht aus dem
  Decomp-Repo gelesen).
* Der Text ist **faktisch** formuliert, nicht als Systemanweisung ("diese Zahl ist die
  Wanduhr des Worker-Prozesses") - die Doku warnt, dass Anweisungsformulierungen die
  Prompt-Injection-Abwehr des Modells ausloesen.

**Einbau:** `worker.write_worker_hooks` schreibt `runs/b<N>/worker-hooks.json` mit
`command = sys.executable`, `args = [tools/batch_uhr.py, --state <state/run.json>,
--weich <limits.alarm_wall_s/60>, --hart <limits.hard_wall_s/60>]`;
`worker.build_command` haengt `--settings` an. Schalter: `[claude] worker_hooks = true`
(`harness.toml`). Fehlt das Skript oder ist der Schalter aus, wird kein Hook gehaengt.

**Zusaetzlich im Vorspann** (der vom Nutzer genannte Rueckfallweg, er schadet nicht):
`build_prompt` schreibt als absolute Ortszeit
`Batch-Start (Harness-Zeitstempel): <HH:MM:SS> Ortszeit am <Datum>` in den Umfeld-Block,
und der Vorspann traegt den Abschnitt **ZEIT (R13ac - gemessen, nicht geschaetzt)** mit dem
Satz, dass die Zahl der Werkzeugaufrufe nichts ueber die Zeit sagt (B210: "~180 min"
geschaetzt, **46 min** gemessen, `snapshots/b210/reasoning.jsonl:174` gegen
`runs/b210/result.json`).

## 2) Trend und Durchsatz (M210-2) - zwei Zaehler, getrennt und benannt

**Befund:** die Trendzeile stand auf dem R207-Zaehler ("verifiziert: +0 Koepfe (78 -> 78)"),
das Durchsatzfenster liess B209 aus (die kanonischen Bilanzdateien
`analysis/_m209/_bilanz*.txt` gibt es nicht) und mischte R207 mit C Koepfen.

**Messung mit den echten Dateien** (`analysis/_preflight_198.txt` … `_preflight_210.txt`,
Zeile 15 = `C Koepfe`):

| Batch | Datei | `C Koepfe` |
|---|---|---|
| 198 | `_preflight_198.txt:15` | 17 / 408 / 0 |
| 199 | `_preflight_199.txt:15` | 45 / 1080 / 0 |
| 203 | `_preflight_203.txt:15` | 59 / 1416 / 0 |
| 205 | `_preflight_205.txt:15` | 73 / 1752 / 0 |
| 206 | `_preflight_206.txt:15` | 78 / 1872 / 0 |
| 207-209 | ebenda | 78 / 2903 / 0 |
| 210 | `_preflight_210.txt:15` | 78 / 2795 / 0 |

`stand.c_trend(cfg, 12)` liefert daraus **B198 17 -> B210 78 = +61 Koepfe**, Spanne 12
Batches, **lueckenlos**, 13 Dateien (Test `test_plus_61_ueber_das_fenster`).
`n` ist die Spanne in Schritten, nicht die Zahl der Dateien.

Der Durchsatz-Block nennt jetzt beide Zaehler getrennt
(`stand.durchsatz_zeilen`, Beispielausgabe mit den echten Dateien):

    Durchsatz    : C Koepfe (Preflight-Messung, analysis/_preflight_<N>.txt Zeile "C Koepfe")
                   letzter gemessener Batch B210: 78 Koepfe (+61 seit B198)
                   Trend B198 17 -> B210 78 = +61 Koepfe (12 Batches, lueckenlos, 13 Dateien)
                   Mittel: +5.1 Koepfe je Batch (B und C zusammen, ueber 12 Schritte); +6.1 je C-Batch (10 C-Batch-Schritte im Fenster)
                   Quelle dieser Zeilen: analysis/_preflight_198.txt bis analysis/_preflight_210.txt (Zeile "C Koepfe", 13 Dateien)
                   Zaehler R207 (gebaut, ALLE Straenge - nicht mit den C Koepfen mischen) letzter Batch 210: 686 -> 686 (+0)
                   Mittel der letzten 5 nach R207 (B+C gemischt): +2.8 Koepfe je Batch   (Fenster: 210: +0, 208: +0, 207: +0, 206: +5, 205: +9   - LUECKENHAFT: die kanonischen Bilanzdateien fehlen fuer B209)

Ohne Preflight-Reihe steht dort **NICHT GEMESSEN** (`test_ohne_quelle_nicht_gemessen`), und
die Kalender-Hochrechnung entfaellt dann mit "nicht rechenbar" - die Grundlage ihrer Zahl
wird ausdruecklich genannt (`kalender_zeilen`: "Grundlage: Preflight-Messung …").
Der C-Durchsatz zaehlt nur **benachbarte** Schritte, die in einem C-Batch enden
(Test `test_luecke_wird_benannt_nicht_als_null_gezaehlt`: +28 und +14 -> 21,0; der Schritt
ueber die Luecke zaehlt nicht).

## 3) "C verifiziert" (M210-3) - Kopfzahl und Bahnabdeckung sind zwei Dinge

**Befund:** `_preflight_210.txt:15` (`C Koepfe 78 / 2795 / 0`) gegen `:17`
(`Bahnabdeckung 55/78 | Bloecke 326/434 | verifiziert 55 | teilgeprueft 23`). Der Bilanz-Kopf
zeigte "C verifiziert: 78" und meinte damit die Kopfzahl, waehrend dieselbe Datei 23 der 78
als nur teilgeprueft auswies.

**Jetzt** (`bilanz.gesamt_block`, mit den echten Dateien):

    C Koepfe referenzgleich: 78 Koepfe / 2795 Faelle / 0 Abweichungen   (+0 Koepfe / -108 Faelle (B209 -> B210))   [B210, _preflight_210.txt]
    C verifiziert: 55 von 78 Koepfen (Bahnabdeckung B210, 23 teilgeprueft, Bloecke 326/434; Quelle: analysis/_preflight_210.txt)

Neu gelesen wird die Bahnabdeckungszeile in `stand.preflight_bahnabdeckung`; liefert eine
Preflight-Datei eine **Nachrueckliste** mit eigener `verifiziert`-Zahl (ab B211 geplant,
Format noch nicht gesehen -> tolerant gesucht), hat **sie** den Vorrang - Test
`test_nachrueckliste_hat_vorrang` (62 von 80, Quelle "Nachrueckliste 1"). Fehlt beides,
steht "nicht gemessen".

## 4) PLAN und Median (M210-4)

**Befund:** PLAN las die Heuristik "genannte Kopfadressen" und zeigte "B210 | 6 Koepfe",
waehrend der Auftrag "keine neuen Koepfe" verlangte (`runs/b210/auftrag.md:148`); die
Median-Regel zaehlte B- und Aufraeum-Batches als Null-Batches mit und ergab fuer den
naechsten C-Batch die Obergrenze 0.

**Jetzt:** PLAN = die Zeile `SOLL-KOEPFE: <n>` der DS_INSTRUCTION (`stand.soll_koepfe`),
sonst **"-"**. Der MEDIAN wird nur ueber **C-Batches mit `SOLL-KOEPFE > 0`** gebildet und
steht auf den **gemessenen C Koepfen** der Preflight-Datei. Die Tafel hat dafuer getrennte
Spalten (R207 und C Koepfe werden nicht mehr in einer Zelle gemischt):

    Batch | PLAN (SOLL-KOEPFE der Instruktion) | IST (R207 gebaut, alle Straenge) | C Koepfe (Preflight) | Laufzeit (result.json) | Abbruch
    B210 | - | +0 Koepfe | 78 (+0) | 46m11s | kein Abbruch
    …
    MEDIAN: nicht gemessen (kein C-Batch im Fenster mit SOLL-KOEPFE > 0)      <- Stand heute, B211 hat die erste Soll-Zeile

Der Reviewer-Prompt nennt dieselbe Regel (`hx/reviewer.py`, PLAN/IST-Block).

## 5) watch-Anzeige (Nutzerpunkt 5) - Ursache mit Datei:Zeile

**Befund:** "Batch 210 laufend: … 200.6 min" um 22:11, obwohl B210 laut
`runs/b210/result.json` 46 min lief (`duration_s 2771.05`, `finished_at`
2026-09-28T20:34:55Z -> Start 21:48 Ortszeit).

**Ursache:** `hx/watch.py`, `Watcher._print_stats` rechnete `up = time.time() - self.started`,
und `self.started` wird im Konstruktor gesetzt (`Watcher.__init__`) - also ab dem Start des
**Zuschauers** (watch lief seit ~18:50; 18:50 + 200,6 min = 22:10). Datei:Zeile vorher:
`hx/watch.py` `_print_stats`, Zeilen mit `up = time.time() - self.started` und
`self.started = time.time()`.

**Behoben:** neue Methode `Watcher._uhr_teil` liest
`hx.uhr.start_zeit(state)` -> `state/run.json:worker.started_at` (Prozessstart des Workers)
- **dieselbe** Quelle wie die BATCH-UHR im Worker. Ist der Lauf beendet, steht dort
`Laufzeit <hms> (runs/b<N>/result.json, Lauf beendet)`; fehlt beides, steht
"Laufzeit nicht gemessen". Die watch-Minuten erscheinen nur noch im Zusatz
`seit watch-Start: … min`, klar benannt.

**Gegenprobe (echte Daten, laufender Betrieb):**

* `state/run.json` waehrend B211: `worker.started_at = 2026-09-28T21:06:48+00:00`
  (23:06:48 Ortszeit); `hx.cli status` meldete zur selben Zeit "Laufender Batch 211: seit
  14m23s" - beide Zahlen kommen jetzt aus diesem einen Feld.
* Rueckwaerts gegen B210: `finished_at 20:34:55Z - duration_s 2771,05 s = 21:48:43
  Ortszeit` = die Startzeit, die der Reviewer-Bericht nennt (46 min, Start 21:48).
* Rueckwaerts gegen B211 (nach dessen Ende, `duration_s 2243,53` = 37m23s,
  `finished_at 2026-09-28T21:44:19Z`): `finished_at - duration_s` = **23:06:55 Ortszeit**
  gegen den **waehrend** des Laufs abgelesenen Zustandswert `worker.started_at` =
  **23:06:48 Ortszeit** - Abstand **7 s** (0,3 % von 37 min). Die 7 s sind der Anlauf der
  CLI bis zu ihrem eigenen `duration_ms`-Nullpunkt; damit liegen beide Wege innerhalb der
  Genauigkeit, die die Anzeige zusagt (der Vorspann sagt ausdruecklich "wenige Sekunden").
* Test `test_gegenprobe_gegen_result_json`: Startzeit = `jetzt - duration_s` -> die
  Anzeige nennt dieselben Minuten wie `result.json` (±0,2 min).
* Test `test_watch_ueber_mehrere_batches`: Batch 210 beendet (46m11s aus `result.json`),
  Batch 211 laeuft seit 3 min -> die Anzeige folgt dem **laufenden** Batch.

## Grenzen / was absichtlich NICHT gebaut wurde

* Die exakte Startzeit eines fertigen Batches steht **nicht** mehr im Zustand (der Harness
  loescht `worker` am Ende). Nachrechenbar ist sie aus `result.json`
  (`finished_at - duration_s`); genau das macht die Gegenprobe oben.
* Der Hook laeuft **nach** dem Werkzeugaufruf. Der allererste Aufruf eines Batches sieht
  noch keine BATCH-UHR-Zeile - dafuer steht die absolute Startzeit im Vorspann.
* Ob der Hook in einem Batch **tatsaechlich** gefeuert hat, ist hier nur ueber die Sonde
  belegt (ein echter Worker-Aufruf mit derselben Einstellungsdatei), nicht ueber einen
  ganzen Batch: B211 lief bereits, als der Hook eingebaut wurde. Der naechste Batch (B212)
  ist der erste mit Hook; dort steht die Zeile im Mitschnitt.
* Die Zahlen des Trendfensters haengen an den Preflight-Dateien: fehlt eine, wird sie als
  Luecke genannt, nicht geschaetzt.

## Selbst reingefallen - und was daraus fuer die Tests folgt

Der erste Anlauf von `tests/test_r13ac_fixes.py` las die echten Preflight-Dateien direkt
aus `g:\Silent Scope Decomp` und nahm dort "das neueste Fenster" (`c_trend(cfg, 12)`).
Waehrend der **vollen Testreihe** beendete sich B211 und schrieb `_preflight_211.txt` -
das Fenster rutschte auf B199..B211, und drei Tests wurden rot:

    AssertionError: Tuples differ: (199, 45) != (198, 17)
    AssertionError: 'Trend B198 17 -> B210 78 = +61 Koepfe' not found in '… Trend B199 45 -> B211 78 = +33 …'
    AssertionError: 211 != 210

Das ist genau der Fallstrick, der seit R13x in den Projektnotizen steht ("der neueste
Batch ist kein stabiler Bezug, solange der Harness laeuft", B209 schrieb sein Dokument
mitten in eine Testreihe). **Behoben** wie dort beschrieben: die Spanne B198..B210 wird
einmal in `tests/_tmp_r13ac_real/decomp/analysis` **kopiert** (13 Preflight-Dateien
**plus** die kanonischen `_m203.._m210/_bilanz*.txt`), und geprueft wird die Kopie; dazu
ein Test, der die Kopie gegen das lebende Repo haelt
(`test_die_kopie_stimmt_mit_dem_lebenden_repo`), plus ein synthetischer Test fuer das
R207-Fenster mit Luecke (`test_r207_fenster_mit_luecke_wird_benannt`).

**Testreihe (gemessen):** volle Reihe `python -u -m unittest discover -s tests` =
**700 Tests OK** (378 s, rc=0), gefahren am Gate vor B212.


