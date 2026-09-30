# R13aw-Belege (2026-09-30): `antwort.md` wird nicht mehr überschrieben (M219-1)

Auftrag (Aussensicht B219, Befund 1, **Gewicht hoch**): der erste Abschlussbericht des
Workers bleibt in `antwort.md`, jede Fortsetzung schreibt nach `antwort-forts<k>.md`;
Reviewer und Außensicht bekommen **beides**; rückwirkend für B214–B218 den ersten
`result`-Text aus `stream.jsonl` als `antwort-bericht.md` danebenlegen (ohne `antwort.md`
anzufassen).

## 1. Was gemessen war

| Quelle | B214 | B215 | B216 | B217 | B218 | B219 |
|---|---|---|---|---|---|---|
| `antwort.md` (Zeichen) | 719 | 1804 | 1227 | 1009 | 1664 | 4654 |
| erster Bericht im Mitschnitt | 6056 | 5584 | 3441 | 4688 | 6283 | 4654 |
| → nachgetragen | ja | ja | ja | ja | ja | nicht nötig |

Quelle: `docs/_r13aw_nachtrag.txt` (`python -u docs/_r13aw_nachtrag.py 214-219 --schreiben`).
Der Bericht mit den Abschnitten 1–6 lag nur im Mitschnitt (`runs/b217/stream.jsonl:74417`,
erstes `result`-Ereignis); in `antwort.md` stand die Kurzantwort der letzten Fortsetzung
(„NACHRUECKLISTE ERLEDIGT"). B219 blieb nur vollständig, weil seine Fortsetzung abgebrochen
wurde (`result.json`: `killed_reason` „cancel").

**Ursache im Code:** `worker._finish_run` schrieb `stats.final_text()` — und das ist der
**letzte** `result`-Text (`hx/streamjson.py:1192`). Bei n Teilläufen überschrieb also jeder
Teillauf die Datei.

## 2. Was jetzt gilt

* `worker.antwort_teile(stats)` liest **alle** `result`-Texte in Reihenfolge
  (`stats.result_ereignisse`); `_finish_run` schreibt den **ersten** nach `antwort.md` und
  jeden weiteren nach `antwort-forts<k>.md` (k = 1..n−1). Ohne Fortsetzung ändert sich
  nichts.
* `runs/b<N>/result.json` trägt `antwort_dateien` (die geschriebenen Dateien) — die
  Dateien entstehen **vor** dem `payload`, damit das Feld stimmt.
* `worker.antwort_text(rd)` baut den vollständigen Text: erst der Bericht, darunter jeder
  Fortsetzungsteil mit Überschrift (`## Fortsetzung <k> (<datei>)`). Liegt ein
  `antwort-bericht.md` daneben (B214–B218), steht **das** vorn und `antwort.md` wird als
  „Kurzantwort (vor der Umstellung überschrieben)" geführt — genau die Batches, in denen
  der Fehler auftrat, haben damit wieder einen Bericht.
* Der **Reviewer** liest diesen Text (`orchestrator.review_context` → `worker_report`);
  die Marker `<TOOL_REQUEST>`/`<PROGRAM_REQUEST>` stehen im ersten Bericht und werden damit
  wieder gefunden. `/send ds` zeigt denselben Text.
* Die **Außensicht** wird im Prompt auf beide Dateien hingewiesen (`aussensicht.eingaben`,
  Tiefenprobe: „… antwort.md (der ERSTE Bericht) + antwort-forts*.md … für B214-B218 …
  antwort-bericht.md").
* Snapshot und Demo zeigen den ganzen Lauf (`res.final_text` = `antwort_text(rd)`).

## 3. Rückwirkend (Auftrag, `--schreiben` gelaufen)

`docs/_r13aw_nachtrag.py` (Probelauf ohne `--schreiben`):

* **gelungen für B214, B215, B216, B217, B218** — fünf `runs/b<N>/antwort-bericht.md`
  (6163 / 5677 / 3483 / 4755 / 6353 Bytes).
* **B219**: `antwort.md` enthält schon den Bericht (4654 Zeichen) → „nichts zu tun".
* B210–B213 hatten keine Fortsetzung (`antwort.md` 8183 / 4809 / 5416 / 4320 Zeichen) →
  kein Nachtrag nötig.
* **`antwort.md` wurde in keinem Fall angefasst** (das Skript schreibt nur
  `antwort-bericht.md`).

## 4. Tests

`harness/tests/test_r13aw_fixes.py` — **18 Tests**: `antwort_teile` (ein/zwei/leere
Ereignisse, `final_text` als Gegenprobe, Rückfall auf `texts`), `antwort_text`
(Reihenfolge Bericht→Fortsetzungen, numerische Sortierung 1/2/10, nachgetragener Bericht,
leerer Ordner), `_finish_run` mit echten Dateien (1/2/3 Teilläufe, `antwort_dateien` in
`result.json`, `final_text` enthält beides), Reviewer-Sicht (`worker_report` mit Bericht
UND Fortsetzung, Marker aus dem Bericht).

## 5. Offen

* Der Nachtrag liegt in `runs/` — das ist im Harness-Repo **gitignoriert**, wandert also
  nicht mit dem Commit. Der Beleg darüber (`docs/_r13aw_nachtrag.txt`) ist versioniert,
  und das Skript läuft auf jedem Rechner erneut.
* Für B214–B218 bleiben die Zwischenantworten mehrerer Fortsetzungen nur im Mitschnitt
  (Dateien gibt es erst ab dem nächsten Lauf).
