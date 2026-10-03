# Belege R13bq (2026-10-03) — Konsolenfenster, Mitschnitt-Stille, CLI-Ausgabe

Auftrag (Nutzer): Beobachtung „Das Harness-Konsolenfenster zeigt zeitweise nichts mehr an
und läuft später weiter; in B257 war `runs/b257/stream-forts1.jsonl` nach dem Start der
Fortsetzung (20:21) rund 45 min lang 0 Bytes und danach 4 MB (21:06)." — erst NUR PRÜFEN,
danach die Punkte **1, 2 und 4** umsetzen (Punkt 4 nur als Messung).

Commits:

| Punkt | Commit | Inhalt |
|---|---|---|
| 1 | `82e2a1e` | QuickEdit beim Start abschalten |
| 2 | `af4a530` | Warnung, wenn der Mitschnitt still bleibt |
| 4 | *(dieser)* | Sonde `docs/_r13bq_sonde.py` + Beleg (nur Messung, kein Umbau) |

Fundstellen tragen `Datei:Zeile@commit`. „gemessen" heißt: am 2026-10-03 am laufenden
Bestand nachgezählt. Das Decomp-Repo wurde nicht angefasst, der Harness nicht neu gestartet.

---

## 1. Wie der Harness in die Konsole schreibt (CONFIRMED)

Es gibt **keinen** eigenen Konsolen-Senker. Jede Log-Zeile geht über `print(..., flush=True)`:

* `hx/util.py:319ff@82e2a1e` Klasse `Log`, `_emit` → `print(line, flush=True)`
  (`hx/util.py:345` Region); davor einmalig `sys.stdout.reconfigure(...)`.
* `hx/watch.py:150/152` (Farben; `GetConsoleMode/SetConsoleMode` dort nur für
  VT-Processing, `hx/watch.py:47`) — **QuickEdit wurde nirgends abgeschaltet**.
* Der Harness selbst läuft unbuffered (`start.ps1:22` `python -u …`), stderr zusätzlich
  nach `logs/start-stderr.log` (`start.ps1:28/34`).

**Kann ein blockierter stdout den Orchestrator anhalten? Ja — INFERENCE (Windows-Verhalten),
nicht als Messwert belegt:** steht das Fenster im Markiermodus (QuickEdit, conhost-Standard),
blockiert der Schreibvorgang den **druckenden** Thread, bis die Auswahl aufgehoben wird.
Während eines Batches drucken der **Takt-Thread** (Telegram-/Limit-Warnungen,
`hx/telegram.py:135`) und der **Haupt-Thread**. Der **Worker ist nicht betroffen**: seine
Ausgabe geht in `runs/b<N>/stream*.jsonl` (`hx/proc.py:86-90`), nie auf die Konsole —
Fenster steht, Batch läuft weiter (genau die gemeldete Beobachtung).

Nebenwirkung, die den Punkt wichtig macht: der STOP-Marker wird in `poll()` gelesen
(`hx/orchestrator.py:1081/1089`), und der läuft im **Takt-Thread**
(`hx/worker.py:1018`, `tick=lambda: self.poll(fast=True)` `hx/orchestrator.py:1846`) —
ein dort hängender Druck blockiert also auch `/stop` und `/pause`.

**Was das Fenster in B257 wirklich tat (gemessen).** Im Fenster 18:21–19:18Z stehen **147**
Zeilen `WARN Telegram haengt` im Protokoll `logs/harness-2026-10-03T164111+0000.log`
(alle aus dem Takt-Thread). Das Fenster war also *nicht* stumm — wenn dort nichts stand, war
es blockiert oder es wurde ins `watch`-Fenster gesehen (das den Mitschnitt zeigt und bei
leerem Mitschnitt still bleibt).

**Umsetzung.** `util.ohne_quickedit_modus(mode)` (reine Bit-Rechnung) und
`util.konsole_quickedit_aus()` (ctypes: `GetConsoleMode`/`SetConsoleMode` auf
`STD_INPUT_HANDLE`, `ENABLE_QUICK_EDIT_MODE` löschen, `ENABLE_EXTENDED_FLAGS` setzen),
aufgerufen in `cli.cmd_run` (`hx/cli.py:45ff@82e2a1e`) vor dem Start. Ohne Konsolenhandle
passiert nichts, Fehler werden nur geloggt. Tests: `tests/test_r13bq_fixes.py::TestQuickEdit`
(5 Fälle, inkl. Nachmessung am echten Konsolenhandle).

---

## 2. Die 45 Minuten von B257 (CONFIRMED, gemessen)

| Größe | Wert |
|---|---|
| Start der Fortsetzung | `logs/harness-2026-10-03T164111+0000.log`: `18:21:47Z` = **20:21:47** („Fortsetzung im selben Chat", anstoss 1); `stream-forts1.err.txt` 20:21:53 |
| Erste Zeile **mit** Zeitstempel im Mitschnitt | `18:22:08.122Z` = **20:22:08** (21 s nach dem Start) |
| Batch-Zeit | `duration_s 9288,6 s`; davon `werkzeug_s **8708,7 s (93,7 %)**`, `api 968,4 s`, `warte_s 0` (`runs/b257/result.json`) |
| Längste Einzelaufrufe | 1323,7 s `m257_fenster.py`, 1082,8 s `hybrid_lauf.exe`, 974,5 / 962,7 s `m257_prewarm.py`, 879,0 s `hybrid_lauf.exe` |
| Lücken zwischen Zeitstempel-Ereignissen im Mitschnitt | 974 / 879 / 582 / 578 s — genau diese Aufrufe |
| Harness-Protokoll im Fenster | nur Telegram-Warnungen, **kein** Worker-Ereignis |

**Umsetzung.** `util.stille_warnung(dauer_s, schwelle_s, letzte_stufe)` (reine Rechnung,
meldet bei jeder vollen Schwelle) + `proc.run_stream(stille_warn_s=…, stille_info=…)`:
bleibt es still, steht eine WARN-Zeile „Mitschnitt still - kein Mitschnitt-Zeichen seit
N min … letzter_aufruf=PowerShell: …" im Protokoll **und damit im Fenster**; Ergebnis trägt
`stille_warnungen`/`stille_max_s`. `streamjson.StreamStats.letzter_aufruf()` nennt den
zuletzt begonnenen Werkzeugaufruf; `worker.run_batch` reicht beides durch, die Schwelle
kommt aus `[limits] stille_warn_min` (**neu, Vorgabe 20 min** — die gemessenen 15–22-min-
Aufrufe sollen nicht jeden Batch anschlagen).

---

## 3. Punkt 4 — die Sonde (NUR MESSUNG, kein Umbau)

`docs/_r13bq_sonde.py` → `docs/_r13bq_sonde.txt`. Zwei minimale echte Aufrufe derselben
Frage (`claude -p --output-format stream-json --verbose --model deepseek-flash[1m]
--max-turns 1`, Prompt über stdin, **ohne** MCP), Laufzeit je ~3 s:

| Modus | Ergebnis (letzter Lauf) |
|---|---|
| **A) `stdout=PIPE`** (wie im Harness) | erstes Byte bei **1,27 s** von 2,8 s Laufzeit, **11 Stücke** für 6221 B, größte Lücke **1,31 s** |
| **B) `stdout=DATEI`** (Gegenprobe) | Datei wächst während des Laufs: 0 B → 2150 B (1,3 s) → 10 154 B (3,0 s) |

**Ergebnis: eine allgemeine Blockpufferung der CLI gibt es NICHT.** Beide Senken bekommen
die Ausgabe WÄHREND des Laufs. Damit ist die naheliegende Annahme („die CLI schreibt nur
blockweise, deshalb war die Datei leer") **widerlegt** — für einen kurzen Lauf ohne
Werkzeugaufruf und ohne MCP-Server.

Nebenbei misst die Sonde den **Verzug der Zeitstempel**: die `timestamp`-Felder im Inhalt
lagen nur **0,00 s** bzw. **0,07 s** vor der Ankunft (`docs/_r13bq_sonde.txt`). Die
Zeitstempel sind also die eigene Uhr der CLI, keine Serverzeit — damit ist die Lesart
„der Inhalt war um 22:33 schon da" bei B257/B258 belastbar.

**Was die Sonde NICHT zeigt:** genau die Lage, in der die 0-Byte-Phasen auftraten, ist nicht
nachgestellt (langer Werkzeugaufruf, MCP-Server, Fortsetzung im selben Chat). Offen bleibt
damit, warum in B257/B258 die Bytes erst am Stück ankamen.

**Was dazu gemessen ist (B258, eigene Proben während des Laufs):**

| Zeit | Datei `runs/b258/stream-forts1.jsonl` | Inhalt |
|---|---|---|
| ~22:43 | **0 Bytes**, mtime = Anlagezeit 22:32:45 | — |
| 22:44:48 | 354 275 B, 1737 Zeilen | erste Zeitstempel-Ereignisse `22:33:00/22:33:01` |
| 22:45:51 | 354 895 B, mtime 22:45:34 | neuestes Zeitstempel-Ereignis weiter `22:33:01` |

Der Harness schreibt jede gelesene Zeile sofort (`hx/proc.py:117`), der Lesefaden wartet
blockierend auf Daten — die ~354 KB sind also **in einem Block ~11 min nach der Erzeugung**
angekommen. Dieselbe Signatur hatte B257 (bei Offset 4,03 MB ein Ereignis mit
Erzeugungszeit `19:05:41Z` = **21:05:41 Ortszeit**, also die „4 MB um 21:06" aus Inhalt von
18:22–19:05).

**Damit stehen zwei getrennte Befunde nebeneinander, beide gemessen:**
1. **Werkzeugzeit** erklärt den fehlenden Fortschritt (93,7 % der Batch-Zeit; während eines
   blockierenden Aufrufs kommt keine Zeile — das ist dokumentiertes Verhalten, s. R13h).
2. **Die Größe der Datei** erklärt das noch nicht: der Inhalt war da, die Bytes kamen später
   am Stück. Ursache **offen** (Kandidaten: MCP-Startphase der CLI, die `init` erst nach dem
   Handschlag ausgibt; Puffer nur in langen Läufen; Handle-/Dateisystem-Verhalten).
   **Vorschlag (nicht umgesetzt):** dieselbe Sonde zweimal mit **MCP wie im Worker** und
   **einem ~90-s-Werkzeugaufruf** fahren und dabei die Ankunft der `init`-Zeile messen —
   damit ist „MCP-Start" von „Werkzeugaufruf" von „Rohr" getrennt.

Die Punkte-2-Warnung liefert ab jetzt zu jeder solchen Phase Zeitstempel im Protokoll; die
nächste Wiederholung ist damit datiert statt geraten.
