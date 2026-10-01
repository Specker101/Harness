# R13be-Belege (01.10.2026)

Drei Auftraege, drei Commits: (1) Preflight-Zaehler aus dem Mitschnitt, (2) Preflight-Hinweis
VOR dem Aufruf, (3) laengere Batches.

## Teil 1 — Preflight-Zaehler aus dem Mitschnitt (R13be-1)

### Der Befund (gemessen)

`preflight_laeufe` kam aus `runs/b<N>/preflight-aufrufe.jsonl`, das der PostToolUse-Hook
`tools/batch_uhr.py` je erkanntem Aufruf schreibt (`tools/batch_uhr.py:116-124`, gelesen von
`hx/worker.py:1094` `zaehle_preflight_aufrufe`). Der Hook laeuft aber **nur nach erfolgreichen**
Werkzeugaufrufen. Ein Preflight, der Befunde findet, endet mit **Exit 2** — das ist
`is_error=true`, der Hook laeuft nicht, die Zeile fehlt.

Gemessen ueber B220-B228: **Zaehldatei-Zeilen = Starts − Aufrufe mit `is_error`** (17 − 6 = 11).

| Batch | Starts im Mitschnitt | davon `is_error` | Zaehldatei-Zeilen |
|---|---|---|---|
| B220 | 2 | 0 | 2 |
| B221 | 1 | 0 | 1 |
| B222 | 1 | 0 | 1 |
| B223 | 2 | 1 | 1 |
| B224 | 2 | 1 | 1 |
| B225 | 2 | 1 | 1 |
| B226 | 2 | 1 | 1 |
| B227 | 3 | 0 | 3 |
| **B228** | **2** | **2** | **0** |
| Summe | **17** | **6** | **11** |

Der scharfe Fall **B228**: `analysis/_preflight_228.txt` liegt vor (3271 B, 01.10.2026
01:01-01:07 Ortszeit, Zeile 2 `HEAD 2b42ec55…`, Ende `Befunde: 1 - R391 Commit-Reihenfolge` /
`=> BEFORE MIT BEFUNDEN`), und im Mitschnitt stehen **zwei** echte Starts
(`22:44:54` = Fehllauf `_m228/_preflight_228_fehllauf1.txt`, `23:00:58` = der Lauf mit Befund) —
beide mit `is_error=true`. Die Zaehldatei fehlt vollstaendig, `preflight_laeufe=0`.

Nicht die Ursache war dagegen die Erkennungsregel: `streamjson.ist_preflight_aufruf`
(`hx/streamjson.py:355`, Start-Regel `hx/streamjson.py:337`) erkennt **beide** Aufrufe
(`cmd /c "python -u scripts\preflight.py …"` ebenso wie die Form mit `$env:PATH=…;`), und
bloße Erwaehnungen (`Select-String -Path scripts/preflight.py`) korrekt nicht.

Erhalten geblieben ist die Fortsetzungsregel: sie liest `stats.tools` (`hx/worker.py:493-503`,
gefuellt aus dem Mitschnitt in `hx/streamjson.py:832`) — deshalb nannte B228 als Blockgrund die
Uhr und nicht einen falschen Preflight-Stand.

### Die Aenderung

| Stelle | Was |
|---|---|
| `hx/stand.py` `mitschnitt_preflight_aufrufe(cfg, batch, start_zeit, umschalt_min, nachrueckliste)` (neu) | zaehlt die **Starts** aus `stream.jsonl` und `stream-forts*.jsonl` (`_mitschnitt_dateien`), mit `streamjson.ist_preflight_aufruf`; fuehrt zu jedem Aufruf `ts`, `min`, `is_error`, `werkzeug`. `frueh` = Aufruf vor der Umschaltschwelle bei offener NACHRUECKLISTE (Definition wie beim Hook). Ohne `start_zeit` wird sie aus `result.json` abgeleitet (`finished_at − duration_s`). |
| `hx/worker.py` `_finish_run` | `hook_laeufe, hook_frueh = zaehle_preflight_aufrufe(rd)` bleibt; dazu `stand.mitschnitt_preflight_aufrufe(...)` mit der laufenden Schwelle (`umschalt_minuten`), der Startzeit aus `uhr.start_zeit(state)` und `hat_nachrueckliste(auftrag.md)`. Wirksam: `preflight_laeufe = max(Mitschnitt, Hook)`, `preflight_frueh = max(Mitschnitt, Hook)`. Neue Nutzlast-Felder: `preflight_laeufe_hook`, `preflight_frueh_hook`, `preflight_aufrufe`, `preflight_mitschnitt_dateien`; `preflight_laeufe_gesamt = max(preflight_laeufe, Hook + archivierte Fehllaeufe)`. Abweichung wird geloggt (`Preflight-Zaehler: Hook und Mitschnitt weichen ab`). |
| `hx/stand.py` `preflight_zaehler_zeile(..., hook=, mitschnitt=)` | Kontrollzeile der Review-Fakten: `PREFLIGHT-AUFRUFE: n (Quelle Stream|Hook), Hook-Zaehler: m` + **HINWEIS**, wenn beide abweichen; danach wie bisher der Archiv-Abgleich. Der Zusatz `-> k Laeufe` erscheint nur, wenn das Archiv **mehr** belegt als die Zaehler (sonst sind die Fehllaeufe im Mitschnitt enthalten). |
| `hx/orchestrator.py` `harness_facts` | gibt `hook=` und `mitschnitt=` mit. |

**Fallstrick beim Bauen** (gleich zweimal getroffen): der Mitschnitt darf **nicht** auf den Text
`preflight` vorgefiltert werden — das ERGEBNIS eines Preflight-Aufrufs nennt ihn nicht (nur
`exit=0` bzw. `Exit code 2`). Die Zaehlung filtert deshalb auf `"tool_use"`/`"tool_result"`.

### Rueckwirkende Auswertung B220-B229 (mit dem neuen Zaehler)

| Batch | Starts (Mitschnitt) | Hook | frueh (Mitschnitt) | frueh (Hook, alt) | Fehllaeufe | gesamt (neu) | Aufrufe (min / is_error) |
|---|---|---|---|---|---|---|---|
| B220 | 2 | 2 | 2 | 2 | 0 | 2 | 17,5 F · 25,5 F |
| B221 | 1 | 1 | 1 | 1 | 0 | 1 | 19,5 F |
| B222 | 1 | 1 | 1 | 1 | 0 | 1 | 62,7 F |
| B223 | **2** | 1 | **2** | 1 | 1 | 2 | 36,3 **E** · 42,7 F |
| B224 | **2** | 1 | **2** | 1 | 1 | 2 | 29,6 **E** · 37,0 F |
| B225 | **2** | 1 | **2** | 1 | 1 | 2 | 22,4 **E** · 29,4 F |
| B226 | **2** | 1 | **2** | 1 | 1 | 2 | 47,5 **E** · 54,5 F |
| B227 | 3 | 3 | 3 | 3 | 0 | 3 | 0,1 F · 42,3 F · 51,2 F |
| **B228** | **2** | **0** | **1** | **0** | 1 | **2** (vorher 1) | 62,3 **E** · 78,4 **E** |
| B229 | laeuft noch (1 Start um 00:12:14, Ergebnis offen) | — | — | — | — | — | — |
| **Summe B220-B228** | **17** | 11 | 15 | 11 | 4 | 17 | 6 Aufrufe mit Exit≠0 |

Erwartung aus dem Auftrag (17 Starts B220-B228) **bestaetigt**; die Fehllaeufe B223-B226 sind
jetzt ohne Zusatzrechnung enthalten, B228 ist von 0/1 auf 2 korrigiert, und `preflight_frueh`
nennt fuer B228 den fruehen Aufruf (62,3 min) statt 0.

### Tests

`tests/test_r13be_fixes.py` (14 Tests): Zaehlen inkl. `is_error`, Erwaehnung zaehlt nicht,
Startzeit aus `result.json`, Fortsetzungs-Mitschnitt, `frueh` nur mit Schwelle **und** offener
Nachrueckliste, Kontrollzeile (Abweichung mit HINWEIS / Gleichstand ohne / Hook-only-Batch),
Gesamtzahl = Maximum, Verdrahtung. Dazu die **Rotprobe** `TestRotprobe`: der B228-Fall ist
nachgebaut (zwei `is_error`-Starts, **keine** Zaehldatei) — der alte Weg meldet 0 (rot), der neue
2 (gruen).

Angepasst: `tests/test_r13bb_fixes.py::test_result_json_traegt_die_differenz` (neue
Gesamtformel als Quelltext-Zusicherung). Unveraendert gruen: `test_r13ao_fixes.py` (23),
`test_r13bb_fixes.py` (36), `test_r13i_fixes.py` (14), `test_r13ah_fixes.py` (49) — der
Hook-only-Fall ohne Mitschnitt behaelt die alten Zahlen.

## Teil 2 — Preflight-Hinweis VOR dem Aufruf (R13be-2)

### Welche Ereignisse die Worker-CLI kennt (belegt)

Beleg ist das **Hooks-Handbuch im CLI-Binary** der Worker-CLI
(`C:/Users/Benji/.local/bin/claude.exe`, 242 171 040 B, Stand 25.09.2026; Pfad aus
`harness.toml` `[claude] exe`). Byte-Suche und Textfenster daraus:

| Fundstelle im Binary | Wortlaut |
|---|---|
| Ereignis-Tabelle | `| PreToolUse | Tool name | **Run before tool, can block** |` · `| PostToolUse | Tool name | Run after successful tool |` · `| PostToolUseFailure | Tool name | Run after tool fails |` — danach `Notification`, `Stop`, `SubagentStart` … |
| Ereignisse im Code | `executePreToolHooks`, `executePostToolHooks`, `executePostToolUseFailureHooks`, `executePermissionRequestHooks`, `executeSessionStartHooks`, `executePreCompactHooks`, `executeStopFailureHooks` |
| Ausgabefelder | `permissionDecision` – **„allow“, „deny“ oder „ask“ (PreToolUse only)** · `permissionDecisionReason` – Begruendung (PreToolUse only) · `updatedInput` (PreToolUse only) · `additionalContext` – „Text injected into model context“ · `systemMessage`, `continue`, `stopReason`, `suppressOutput` · `decision: "block"` ist **„deprecated for PreToolUse, use hookSpecificOutput.permissionDecision instead“** |
| Blockade per Exit-Code | „wakes the model on exit code 2 (blocking error)“ (Feld `asyncRewake`) — Exit 2 ist die zweite, aeltere Blockadeform |

**Antwort auf die Frage:** PreToolUse kann **beides** — einen Hinweis **anhaengen ohne zu
blockieren** (`additionalContext`) und **mit Begruendung blockieren**
(`permissionDecision: "deny"` + `permissionDecisionReason`). Gewaehlt wurde `deny`, damit der
Worker **vor** dem Aufruf anhaelt statt danach.

### Die Aenderung

| Stelle | Was |
|---|---|
| `tools/batch_uhr.py` `pre_tooluse(eingabe, lauf, state_datei, umschalt)` (neu) + Schalter `--pre` | Stoppt einen Preflight-**Start** genau **einmal je Batch**, wenn **alle drei** Bedingungen gelten: `streamjson.ist_preflight_aufruf`, `uhr.preflight_zu_frueh(minuten, umschalt)`, `_nachrueckliste_offen(lauf)`. Ausgabe: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "PREFLIGHT-HINWEIS: …" + Zusatz}}` (Exit 0). Je Stopp eine Zeile in `runs/b<N>/preflight-blockiert.jsonl` (`ts`, `min`, `umschalt`, `werkzeug`) — **diese Datei ist die Marke**: ihr Vorhandensein laesst jeden weiteren Aufruf durch. Der Zusatz lautet woertlich (Nutzerauftrag): „Falls alle Posten erledigt sind oder ein Posten belegt blockiert ist: das im Batch-Dokument festhalten und den Preflight erneut starten.“ |
| `hx/worker.py` `write_worker_hooks` | schreibt **beide** Ereignisse in dieselbe Einstellungsdatei: `PostToolUse` wie bisher, `PreToolUse` mit denselben Argumenten plus `--pre`. Damit gelten fuer beide Wege dieselben Bedingungen (Uhr, Schwelle, Laufverzeichnis). |

Der Reihenfolge wegen steht die billigste Pruefung zuerst: kein Preflight-Aufruf → sofort
zurueck, **ohne** den Zustand zu lesen (der Hook laeuft vor JEDEM Werkzeugaufruf).

**Nebenwirkung, bewusst:** ein geblockter Aufruf ist im Mitschnitt ein `tool_use` und wird
vom neuen Zaehler aus Teil 1 als **Aufruf** gezaehlt (er wurde versucht). Fuer B228 waere das
+1 gegenueber der Zahl der *ausgefuehrten* Laeufe; die Zahl der Bloecke steht deshalb als
eigene Zeile in `preflight-blockiert.jsonl`.

### Tests

`tests/test_r13be_fixes.py::TestPreToolUseHinweis` (10 Tests, Aufruf des Hooks als
Kindprozess wie durch die CLI): erster Aufruf wird gestoppt (Pruefung von `hookEventName`,
`permissionDecision`, Hinweistext und Zusatz), **zweiter Aufruf laeuft durch** (genau ein
Marken-Eintrag), nach der Schwelle kein Stopp, ohne NACHRUECKLISTE kein Stopp, anderer
Befehl kein Stopp, ohne Startzeit kein Stopp, bloße Erwaehnung kein Stopp, Marke gilt je
Batch, Einstellungsdatei haengt beide Ereignisse mit gleichen Argumenten. Dazu zwei
**Rotproben**: `test_rotprobe_ohne_marke_wieder_stopp` loescht die Marke und zeigt, dass der
Hook dann **erneut** blockt (die Marke ist das Wirksame, nicht Zufall) und
`test_einstellungsdatei_haengt_beide_ereignisse` faellt, wenn der `PreToolUse`-Eintrag oder
das `--pre` fehlt.

