# Belege R13v (2026-09-28) - Warteschleifen und Kostenzaehler

Alles rein LESEND erzeugt; keine Aenderung im Decomp-Repo.

## 1. Warteschleifen in B207 - welche Befehle, worauf, warum

Werkzeug `tools/warte_analyse.py`, Beleg `docs/_r13v_beleg_b207.txt`
(Quelle: `harness/runs/b207/stream.jsonl`, 91166 Zeilen, 152 bewertete Werkzeugaufrufe).

| Klasse | gemessene Dauer |
|---|---|
| **poll** (Abfrageschleife) | **1083,7 s** |
| sleep (einzelner Schlaf) | 31,6 s |
| hintergrund (`Start-Process`) | 1,5 s |
| arbeit (echte Laeufe) | 939,9 s |

Die zwei Abfrageschleifen (Datei:Zeile im Mitschnitt):

* `runs/b207/stream.jsonl:76873` - **601,9 s**
  `for ($i=0; $i -lt 40; $i++) { if (-not (Get-Process -Id 4996 …)) { break };
   Start-Sleep -Seconds 20 }`
* `runs/b207/stream.jsonl:77152` - **481,8 s** (dieselbe Form, 28 Schritte)
* dazu `runs/b207/stream.jsonl:76669` - `Start-Sleep -Seconds 30` (31,6 s)

**Worauf gewartet wurde:** PID **4996** - gestartet in
`runs/b207/stream.jsonl:66903`:
`Start-Process -FilePath "python" -ArgumentList "-u","scripts/c_kopf.py","mutalle"
 -RedirectStandardOutput "analysis\_m207\_c_kopf_m…"`. Der Mutationslauf ueber alle
registrierten Koepfe dauerte laenger als die Werkzeug-Grenze, also wurde er in den
Hintergrund geschoben und danach abgefragt.

**Warum nicht synchron mit Tool-Zeitgrenze - belegt:**
`runs/b207/stream.jsonl:76897` traegt die Werkzeugantwort
*„Command did not complete within its **600s timeout** and was moved to the background
(ID: brxv9hw6u). Output is being written to: C:\Users\…"*.
Die Obergrenze des Werkzeugs ist also **600 s = 10 min**, der Standard niedriger; ein
7-Minuten-Lauf ist damit nur mit ausdruecklicher `timeout`-Angabe synchron zu fahren (der
Worker hat 17 Aufrufe MIT `timeout`-Argument gemacht - bei den Warteschleifen aber nicht).
Das Ergebnisverzeichnis nennt die Wartezeit als `warte_s: 1390 s` (Schaetzung mit
Schleifenzahl) - gemessen sind es 1083,7 s.

## 2. Kostenzaehler: Ausgabe-Token sind enthalten - nachgerechnet

Werkzeug `tools/kosten_nachrechnung.py`, Beleg `docs/_r13v_beleg_kosten207.txt`.

| Groesse | Wert (B207) |
|---|---|
| Nutzung je Nachricht (`assistant.message.usage`), Maximum je id | miss 140736 / hit 23056384 / creation 0 / **output 0** |
| `result`-Ereignis (Gesamtlauf) | miss 140224 / hit 23056896 / creation 0 / **output 137354** |
| `message_delta` mit usage | **keins** (die CLI traegt sie hier nicht) |
| genommen | **output 137354** (aus dem `result`-Ereignis, `streamjson.output_total`) |

Nachrechnung mit `hx/pricing.py` (offpeak: cache_hit 0,003 / cache_miss 0,15 / output 0,60
USD je 1M):

    MIT  Ausgabe: 140736*0.15 + 23056384*0.003 + 137354*0.60  = $0,172692
    OHNE Ausgabe: 140736*0.15 + 23056384*0.003 +      0*0.60  = $0,090280

Der Harness meldet fuer B207 **$0,1727** - also **exakt** der Wert MIT Ausgabe. Ohne
Ausgabe waeren es 47,7 % weniger. Gegenprobe B206 (223 Anfragen, gemeldet $0,2934):

    214745*0.15 + 50466304*0.003 + 183020*0.60 = $0,293423  (gemeldet $0,2934)

**Befund:** der Zaehler ist in Ordnung; die Ausgabe steckt drin. Die Vermutung „dasselbe
Verhaeltnis wie vor dem Befund" trifft nicht zu: beide Zahlen (B206/B207) sind
NACH der Korrektur, und ihr Ausgabe-Anteil ist verschieden gross (37,4 % bzw. 47,7 %).
Die fruehere Unterdeckung von ~38 % entspricht genau dem, was fehlt, wenn man die
Ausgabe weglaesst (`$0,0903` statt `$0,1727` = 47,7 % weniger; fuer B206 37,4 %).
**Keine Aenderung noetig** - `streamjson.output_total()` nimmt das Maximum aus
Ereignis-Summe und `result`-Ereignis, `cost_usd()` verteilt die Gesamtausgabe auf die
Aufrufe, wenn die Einzelwerte fehlen.

## 3. Was gebaut wurde (R13v)

| Ebene | Datei:Zeile | Wirkung |
|---|---|---|
| Ursache weg | `hx/envs.py` (`worker_env`) | `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` = 600 000 ms → lange Laeufe synchron in einem Aufruf |
| Sperre | `hx/worker.py::build_command` | `--disallowedTools PowerShell(Start-Sleep*) Bash(sleep *)` |
| Erkennung | `hx/streamjson.py::warte_muster` | Abfrageschleife / fester Schlaf ≥ 30 s / Schleife mit Prozessabfrage; `Wait-Process` ist erlaubt |
| Eingriff | `hx/streamjson.py::warte_entscheidung` + `hx/worker.py::on_event` | erster Fund = Alarm, ab 300 s (einzeln oder summiert) **Abbruch** mit `killed_reason = "warteschleife"` |
| Sichtbarkeit | `hx/streamjson.py::laufzeit_profil`, `hx/orchestrator.py::laufzeit_zeile` | Zeile `WARTESCHLEIFEN n Aufrufe / ~s geschaetzt` in `harness-facts.md` und im Review |
| Erlaubter Weg | `hx/worker.py::WORKER_PREAMBLE` (Abschnitt RECHENZEIT) | synchron mit `timeout` bis 600000 ms; sonst `Start-Process -PassThru` + EIN `Wait-Process -Id $p.Id -Timeout 480`; `Start-Sleep` gesperrt, keine Abfrageschleife |

Tests: `harness/tests/test_r13v_fixes.py` (13). Angepasst:
`tests/test_r13h_fixes.py::test_worker_vorspann_warn_vor_grossen_schlafschritten`
(verlangte den alten, irrefuehrenden Satz „kurzer Schritt (10-20 s)").
Werkzeuge: `tools/warte_analyse.py`, `tools/kosten_nachrechnung.py`.
Reihe: **469 Tests gruen** (vorher 456 + 13).
