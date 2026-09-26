# Harte Tode: erkennen, erklären, verhindern (R13i, 2026-09-26)

Diese Datei sammelt die **stillen** Tode des Harness — Fälle, in denen der Prozess
verschwindet, ohne Traceback, ohne Crash-Bericht, ohne Eintrag im
Windows-Ereignisprotokoll. Sie ist aus zwei echten Ausfällen vom 2026-09-26 entstanden.

## 1. Warum es keinen Crash-Bericht gab

`Orchestrator.report_crash` (R13c) schreibt bei jeder **unbehandelten Ausnahme** einen
Bericht nach `logs/crash-<zeit>.txt` und meldet per Telegram. Ein
`TerminateProcess` (Taskkill, Job-Objekt, geschlossenes Konsolenfenster) kommt dort
**nie** an — der Prozess ist von einem Moment auf den anderen weg. Erkennungsmerkmale:

| Merkmal | Normaler Absturz | Harter Tod |
|---|---|---|
| `logs/crash-*.txt` | ja | **nein** |
| `logs/start-stderr.log` | Traceback | **leer** |
| Ereignisprotokoll (`python.exe`) | oft Application Error | **leer** |
| Zustand `state/run.json` | PAUSED/STOPPED | **bleibt auf `DS_WORKING`** |
| Kindprozesse (Worker) | beendet | **manchmal verwaist** |

## 2. Belegter Fall: der Worker räumt Prozesse nach Muster ab

Der Harness starb am 2026-09-26 um 21:37:57, mitten in Batch 178. Ursache im
Mitschnitt (`runs/b178/stream.jsonl`, letzter Werkzeugaufruf):

```powershell
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CPU -gt 50 } |
  ForEach-Object { "kill $($_.Id) cpu=$($_.CPU)"; Stop-Process -Id $_.Id -Force }
```

Das trifft **jeden** `python.exe` mit über 50 s CPU-Zeit — und der Harness *ist* ein
`python.exe` (`python -m hx.cli run`, zu dem Zeitpunkt ~370 s CPU). Was der Worker
aufräumen wollte, waren seine eigenen Emulationsläufe; getötet hat er sich seinen
Auftraggeber.

Prüfbefehl für die Vergangenheit (findet Muster-Abbau in allen Mitschnitten):

```
python -u ..\docs\_abbau_scan.py        # -> docs\_abbau_scan.txt
```

Ergebnis über b171-b178: **genau ein** gefährlicher Befehl (b178). Die sechs anderen
Abbau-Befehle waren gezielt (`Stop-Process -Id 1234`) oder über die Kommandozeile
gefiltert (`Where-Object { $_.CommandLine -like "*port4c2*" }`) — beide harmlos.

### Gegenmaßnahmen

1. **Regel im Worker-Vorspann** (`hx/worker.py`, Abschnitt „Nie Prozesse nach Muster
   abräumen"): verboten sind CPU-Filter, `-Name`, `taskkill /IM` und pauschale Listen;
   erlaubt ist nur eine feste Nummer (`Start-Process … -PassThru`) oder ein
   CommandLine-Marker.
2. **Notbremse** (`hx/streamjson.py:abbau_gefahr` + `hx/worker.py`): erkennt der Harness
   den Befehl im Mitschnitt, beendet er den Lauf mit `killed_reason=prozess_abbau` und
   alarmiert. Achtung: der Befehl ist zu diesem Zeitpunkt schon unterwegs — die Regel
   ist die eigentliche Absicherung, die Bremse nur die zweite Linie.
3. **Erkennung belegt** (`tools/check_abbau.py` → `docs/_abbau_beleg.txt`): 10/10
   Testfälle korrekt, null Fehlalarme auf den echten Befehlen.

## 3. Der zweite Fall bleibt offen

Der Lauf von 17:46 starb um 20:26:53 (Ortszeit) **unmittelbar nach „Batch beendet"**
von b177 — zwischen der Batch-Buchhaltung und dem Beginn des Reviews (dort läuft der
Git-Push). Es gibt keinen Crash-Bericht, keine stderr-Zeile, keinen Ereigniseintrag.
Ein Muster-Abbau steht in b177 **nicht**. Damit ist dieser Tod nicht erklärt; die
Signatur ist dieselbe wie in Abschnitt 2.

**Das ist der Grund, warum „Selbstheilung" (Wächter + Rollback) im Plan liegt**
(`selbstheilung-plan.md`) — und warum sie **nicht** jeden Ausfall als Codefehler
behandeln darf: bei einem harten Kill ist der Code in Ordnung.

## 4. Was der Harness jetzt selbst meldet

`recover()` prüft beim Start, ob der vorige Lauf mitten in einem Batch stand
(`state/run.json` sagt `DS_WORKING`, aber kein Worker-Prozess lebt). Dann:

* sichert es den WIP (`git stash` + Patch),
* sucht in `runs/b<N>/stream.jsonl` nach Muster-Abbau und **zitiert den Befehl**
  (`orchestrator.abbau_ursache`),
* meldet per Telegram: „Der vorige Lauf wurde HART abgeräumt (kein Crash-Bericht) …".

## 5. Fallstrick: `wip_rescue` und das falsche Repo

`gitsafe.Git` arbeitet mit `cwd = cfg.decomp`. Liegt dieses Verzeichnis **innerhalb**
eines anderen Repos (Test-Tempordner im Harness-Repo!), dann sucht `git` seine Wurzel
selbst und arbeitet still am **äußeren** Repo. Am 2026-09-26 hat so ein
`git stash push -m harness-wip-b178` den Arbeitsbaum des Harness gestasht und
unversionierte Arbeit weggeräumt (zweimal, beide Male aus einem Testlauf mit
`recover()`).

Dagegen zwei Maßnahmen:

* **Repo-Wache** in `gitsafe.Git`: vor jedem Aufruf wird `git rev-parse --show-toplevel`
  mit `cfg.decomp` verglichen; passt es nicht, wird der Aufruf mit `rc=128` verweigert
  und im Log als Fehler gemeldet (`Git-Repo-Wache`).
* **Tests** legen in ihrem Wegwerf-`decomp` ein echtes `git init` an
  (`test_r13c_fixes`, `test_r13i_fixes`).

Wer Arbeit im Harness-Repo hat, sollte sie **committen**, bevor ein Harness startet:
nach einem harten Tod räumt `recover()` den Arbeitsbaum per `git stash` ab. Ein
gestashtes Paket lässt sich mit `git stash list` / `git stash pop` zurückholen.
