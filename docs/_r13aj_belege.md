# R13aj-Belege (2026-09-29): Werkzeugdauer bei überlappenden Aufrufen

Auftrag: *„Nachtrag zur Werkzeugdauer-Messung (`hx/streamjson.py`, `hx/stand.py`) — (1) prüfen
und berichten, ob mehrere `tool_use` in derselben Assistant-Nachricht stehen; (2) falls ja,
`parallel = <n>` in `langsamste` aufnehmen und `stand.preflight_dauer` nur aus
`parallel = 1` speisen, mit Rückfall auf einen älteren Batch; (3) Tests."*

Werkzeug (nur lesend): `docs/_r13aj_probe.py`, Rohausgabe `docs/_r13aj_messung.txt`.

---

## 0. Teil 1 der Frage: mehrere `tool_use` in EINER Assistant-Nachricht?

**NEIN — in B212/B213/B214 kein einziger Fall.** Verteilung der Werkzeugaufrufe je
Assistant-Nachricht:

| Batch | Nachrichten mit Werkzeugaufruf | Aufrufe je Nachricht |
|---|---|---|
| B212 | 234 | `{1: 234}` |
| B213 | 211 | `{1: 211}` |
| B214 | 293 | `{1: 293}` |

Die Sonde schreibt dazu ausdrücklich `keine Nachricht mit mehr als einem
Werkzeugaufruf`. **Die Annahme des Auftrags ist damit in dieser Form widerlegt**: der
Worker stellt nie zwei Aufrufe in denselben Zug. Die Messung ist trotzdem verfälscht —
**aber aus einem anderen Grund** (Teil 2).

## 0a. Die wirkliche Ursache: der Aufruf davor läuft noch (gemessen)

Die Dauer ist der Abstand `tool_use` → `tool_result`. Ein Aufruf kann **im Hintergrund
weiterlaufen**, während der nächste schon startet (gekappter PowerShell-Aufruf, R13ah).
Dann misst der Abstand das *Warten* mit. Beleg am echten B212-Mitschnitt:

```
Zeile 14789  assistant tool_use   PowerShell  Get-ChildItem capture\ppc_cov_boot.bin …
Zeile 14790  assistant tool_use   Grep        g:\Silent Scope Decomp\scripts        <-- 1 Zeile später
Zeile 14814  user      tool_result (PowerShell)
Zeile 14815  user      tool_result (Grep)
```

Beide Aufrufe starten mit **demselben Zeitstempel** (00:55:23) und enden 601,6 s später.
Ergebnis in `stats.laufzeit.langsamste` von B212:

| Aufruf | gemessene Dauer | Überlappung | echte Arbeit |
|---|---|---|---|
| `Grep g:\Silent Scope Decomp\scripts` | **602,3 s** | 601,6 s mit dem PowerShell-Aufruf | Sekundenbruchteile |
| `Get-ChildItem capture\ppc_cov_boot.bin` | **601,9 s** | 601,6 s mit dem Grep | ~600 s (im Hintergrund) |
| `Grep …\port\hybrid\ppc_kern.cpp` (Zeile 37987) | **511,0 s** | 510,5 s mit `port_build.ps1 -Gl` | Sekundenbruchteile |
| `& .\scripts\port_build.ps1 -Gl` (Zeile 37986) | **511,0 s** | 510,5 s mit dem Grep | ~510 s |

Genau diese **602 s** standen bis R13aj als „Preflight-Dauer“ in der Umschaltschwelle —
obwohl der Aufruf ein Grep mit normalen Treffern war. Ursache und Wirkung sind damit
belegt, nicht vermutet.

Zahl der überlappenden Aufrufe je Batch (Intervall-Schnitt > 1,0 s):

| Batch | Aufrufe | Überlappung > 1,0 s (echter Nebenlauf) | ≤ 1,0 s (Rundung der Zeitstempel) |
|---|---|---|---|
| B212 | 234 | 14 | 16 |
| B213 | 211 | 8 | 2 |
| B214 | 293 | 27 | 18 |

Zwischen „echter Nebenlauf“ und „Rundung“ liegt eine klare Lücke: die kleinen Fälle sind
0,1–0,7 s (Zeile 798/799, 935/936, 2581/2582 …), die großen 1,5–601,6 s. Deshalb
`PARALLEL_TOLERANZ_S = 1,0`.

---

## 1. Änderung 1: `parallel` in `stats.laufzeit.langsamste` (`hx/streamjson.py`)

* Neue Liste `self._intervalle: list[tuple[float, float]]` — jedes beendete Intervall.
* `_tool_ende` setzt
  `parallel = 1 + len(self._offen) + _parallel_dazu(t0, t1)`
  (noch **offene** Aufrufe zählen mit, **abgeschlossene** nur bei einem Schnitt von mehr
  als `PARALLEL_TOLERANZ_S`), und schreibt `"parallel": parallel` in den Eintrag.
* `PARALLEL_TOLERANZ_S = 1.0` (Modulkonstante, gemessen wie oben).
* **Altdaten ohne Feld gelten als `parallel = 1`** — die Leser prüfen
  `int(e.get("parallel") or 1) == 1`, damit die vorhandenen `result.json` gültig bleiben.

## 2. Änderung 2: `stand.preflight_dauer` nimmt nur Einzelaufrufe (Rückfall)

* `preflight_dauer(cfg, anzahl=6, log=None)`: aus `langsamste` zählen nur Einträge mit
  `parallel == 1`. Gibt es im **neuesten** Batch keinen, wird der nächstältere mit einem
  gültigen Wert genommen; das Log bekommt
  `Preflight-Dauer aus B<k>, B<N> nur parallel gemessen` (WARN beim Überspringen selbst,
  INFO beim Rückfall). Rückgabe zusätzlich `{parallel, uebersprungen: [B…]}`, `batch` ist
  der **Quell**-Batch.
* Fenster von 4 auf 6 Batches erhöht (ein Batch mit nur paralleler Messung soll nicht
  sofort ins Leere greifen).
* `worker.umschalt_minuten(cfg, log=None)` reicht das Log durch; die Aufrufer
  (`write_worker_hooks`, `fortsetzung_pruefen`, der Lauf) übergeben ihres.

## 3. Änderung 3: Quelle in der BATCH-UHR

* `uhr.uhr_text(..., preflight_batch=<k>)` hängt `(B<k>)` an:
  `| Preflight zuletzt ~10 min (B213)`. Ohne `preflight_batch` (oder `0`) bleibt die Zeile
  wie bisher — Altverhalten unverändert.
* `worker.write_worker_hooks` gibt `--preflight-batch <k>` mit; `tools/batch_uhr.py` liest
  den Parameter und reicht ihn durch.
* Vorspann (`WORKER_PREAMBLE`) erklärt die Klammer: *„Die Zahl hinter `Preflight` trägt in
  Klammern den Batch, aus dem sie stammt (`(B213)`). … steht dort ein älterer Batch, hat der
  neueste den Preflight-Aufruf nicht allein gemessen …“*.

---

## 3a. Regelseite: `prompts/reviewer.md`, Abschnitt „Lange Befehle“

Damit der **Auftrag** die Messbarkeit nicht selbst zerstört, sagt die Rollenanweisung des
Reviewers (der die `DS_INSTRUCTION` schreibt) dasselbe wie der Worker-Vorspann:

* Preflight, `c_kopf.py mutalle` und `port_build` laufen als **normaler Bash-Aufruf mit
  `timeout=1800000`** (vom Harness freigegeben — `BASH_MAX_TIMEOUT_MS`).
* **Nicht** per `Start-Process` im Hintergrund mit späterem Nachfragen, nicht mit
  Warteschleifen (`Start-Sleep`/Abfrageschleifen sind gesperrt und brechen den Lauf ab).
* **Begründung im Text:** ein blockierender Aufruf ist messbar (seine Dauer ist die Zahl
  für die Umschaltschwelle); im Hintergrund gemessen enthält sie die Wartezeit des
  Nachbaraufrufs (`parallel > 1`) und wird für die Schwelle verworfen.

Festgenagelt durch `TestReviewerRegelLangeBefehle` in `harness/tests/test_r13aj_fixes.py`
(20 Tests in dieser Datei).

---

## 4. Testreihe

`harness/tests/test_r13aj_fixes.py` — **20 Tests**:

| Klasse | was geprüft wird |
|---|---|
| `TestParallelFeld` | Einzelaufruf → `parallel = 1`; zwei überlappende → `2`; 0,2 s Überlappung zählt **nicht**; drei gleichzeitig → `3`; `PARALLEL_TOLERANZ_S == 1.0` |
| `TestPreflightDauerAllein` | Einzelaufruf wird genommen; **nur** paralleler Aufruf im neuesten Batch → Rückfall auf B213 + Logzeile; im selben Batch zählt der einzelne Eintrag; ohne gültige Messung `None`; Alteintrag ohne Feld bleibt gültig |
| `TestSchwelleUhrUndHook` | `umschalt_minuten` nennt `preflight_batch`; Uhrzeile trägt `(B213)`; Hook-Datei trägt `--preflight-batch 213`; `batch_uhr.py` schreibt `(B213)` in den Kontext; Vorspann erklärt die Klammer |
| `TestEchterMitschnitt` | **Regressionspflock am echten B212**: Zeilenausschnitt 14786–14816 → der Grep trägt `parallel = 2` und `> 500 s` (die verfälschte Zahl ist festgehalten) |

Volle Reihe: **898 Tests OK** (vorher 882; +16).

## 5. Was NICHT geprüft ist

* Es gibt **keine** Aussage darüber, ob ein künftiger Worker zwei `tool_use` in dieselbe
  Nachricht schreibt. Das Feld `parallel` deckt beide Wege ab (offene Nachbarn und
  abgeschlossene mit Intervallschnitt), aber die Nachrichtenform selbst ist nur für
  B212–B214 gemessen.
* Die 600-s-Kappung als **Ursache** der Überlappung ist für B212 belegt (der PowerShell-
  Aufruf wurde laut R13ai-Beleg in den Hintergrund geschoben); für B213/B214 sind die
  Überlappungen kurz (≤ 2 s) und harmlos.
