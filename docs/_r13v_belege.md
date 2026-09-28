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

## 4. Nachprobe vor dem Neustart: faengt die Sperre auch die Schleife? (R13v2)

Werkzeug `tools/r13v_sperrprobe.py`, Beleg `docs/_r13v_sperrprobe.txt`. Es laeuft der
**echte** `claude`-Prozess mit **genau** der Worker-Kommandozeile
(`hx.worker.build_command`, Profil `none`) und der Worker-Umgebung (`hx.envs.worker_env`);
das Modell bekommt je Fall einen Befehl woertlich zum Ausfuehren, bewertet wird der
Mitschnitt (`tool_use`-Eingabe + `tool_result`), nicht die Modellprosa. 11 Faelle,
je 4–7 s.

| Befehl | Sperre | Ergebnis |
|---|---|---|
| `Write-Output "hallo"` | wie im Batch | ausgefuehrt (Werkzeug laeuft) |
| `Start-Sleep -Seconds 3` | wie im Batch | **blockiert** |
| `for ($i=0; $i -lt 40; $i++) { …; Start-Sleep -Seconds 20 }` | wie im Batch | **blockiert** |
| `if ($true) { Start-Sleep -Seconds 3 }` | wie im Batch | **blockiert** |
| `Write-Output "a"; Start-Sleep -Seconds 3` | wie im Batch | **blockiert** |
| `for (…) { …; sleep -Seconds 20 }` (Alias) | wie im Batch | **blockiert** |
| `Write-Output "Start-Sleep -Seconds 3"` | wie im Batch | ausgefuehrt |
| `[Threading.Thread]::Sleep(2000)` | wie im Batch | ausgefuehrt |
| Schleife | zusaetzlich `PowerShell(*Start-Sleep*)` | blockiert (nicht noetig) |
| Schleife | zusaetzlich `PowerShell(for *)` | blockiert (nicht noetig) |

Wortlaut der Ablehnung (aus dem Mitschnitt):
*„Permission to use PowerShell with command for ($i=0; $i -lt 40; $i++) { … } has been
denied."*

**Fazit:** die Sperre ist **keine** Praefix-Regel; der Werkzeugkasten prueft die
Bestandteile des Befehls (alias-bewusst), deshalb faellt auch die Schleife darunter.
Nicht gesperrt ist `[Threading.Thread]::Sleep(…)` - dafuer greift nur der Waechter.

## 5. Notbremse: was der naechste Batch vorfindet

Sonde `tools/r13v_waise_probe.ps1` (Herzschlag `tools/r13v_herzschlag.py`), Beleg
`docs/_r13v_waise.txt` (Zeitstempel alle 0,5 s in eine Datei; frische Datei = Prozess
lebt, `ENDE` = beendet).

| Fall | nach `taskkill /T /F` auf den Baum |
|---|---|
| V3: Kind im Baum eines **lebenden** Shells | beendet (Herzschlag steht bei 17:32:48) |
| V2/V4: per WMI gestartet, **kein** Elternbezug | laeuft weiter (Herzschlag frisch, 0,2–0,4 s) |
| V1: Kind per `Start-Process`, startender Shell endet | in dieser Sitzung beendet — **weicht vom echten Betrieb ab** |

Dass der echte Hintergrundlauf ebenfalls ohne Elternbezug weiterlaeuft, zeigt B207:
PID 4996 lebte **ueber 19 Minuten nach dem Ende des startenden Werkzeugaufrufs**
(`stream.jsonl:66903` gestartet, danach 601,9 s + 481,8 s Poll-Zeit bis zum Verschwinden).
Der Harness raeumt nichts auf: kein Prozess-Scan, kein Nachfassen. Was sonst liegen
bleibt (Mitschnitt, `result.json` mit `killed_reason`, verbrauchter Auftrag, Push+Review
ohne Ruecknahme, kein Zwang zum sauberen Baum), steht in `docs/bedienung.md` §12c.

**R13v2 (kleine Korrektur, aus dieser Messung):**
`hx/streamjson.py::warte_normalisiert` schaetzt jetzt auch `sleep -Seconds N` und
`[Threading.Thread]::Sleep(N)`; vorher stand bei solchen Befehlen `0,0 s` und der Fund
blieb ein **Alarm** statt eines Abbruchs (gemessen an der Sondenschleife: 800 s statt 0 s).
Tests dazu in `tests/test_r13v_fixes.py`
(`test_alias_und_fremdschlaf_werden_gemessen`, `test_blosse_erwaehnung_ist_keine_warteschleife`).

