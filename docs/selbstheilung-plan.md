# Selbstheilung: `/fix` und Wächter — **Plan, nichts gebaut** (2026-09-26)

Auftrag: „Selbstheilung (NUR Plan, nichts bauen)". Dieses Dokument ist der
Entwurf; **es ist keine Zeile Code dafür entstanden.** Der Nutzer entscheidet
danach, ob gebaut wird.

Grundlage (alles gemessen, nicht angenommen):

- Der Harness kann **still sterben**: am 2026-09-26 um 00:30 und 02:12 je ein
  Lauf mit 373-Byte-Protokoll, **ohne** Traceback, ohne stderr-Zeile, ohne
  Crash-Bericht. Ursache belegt: der Kindprozess lebte im **Job-Objekt von
  `Code.exe`** (aus einem VS-Code-Terminal gestartet) und wurde mit dem Terminal
  abgeräumt — nicht unsere Software. Beleg und Startempfehlung:
  `docs/bedienung.md` §1a.
- `start.ps1` ist heute **kein** Wächter: es startet `hx.cli run`, schreibt
  stderr zusätzlich nach `logs/start-stderr.log` und bleibt bei Exit-Code ≠ 0
  mit Meldung stehen. Danach ist Schluss — es startet nichts neu.
- Es gibt **keinen Herzschlag**. Weder `state/run.json` noch `logs/*.jsonl`
  tragen ein Feld, das „der Takt läuft noch" belegt. Ein Wächter braucht das.
- Das Harness-Repo (`g:\Harness`) hat **kein Remote**; alle Änderungen sind nur
  lokal. Ein Rollback muss also lokal und ohne Netz funktionieren.
- Die Testsuite steht bei **220 Tests, grün** (2026-09-26, inkl. der 20 neuen
  R13f-Tests). Das ist die Messlatte für „gesund" im Sinne dieses Plans.

---

## Teil A — `/fix <Beschreibung>`

### A1. Ablauf (Entwurf)

1. **Anhalten.** `/fix` kommt per Telegram oder Konsole. Läuft ein Batch, wird
   er wie bei `/pause` **zu Ende gefahren**; der Harness geht danach in den
   Zustand `PAUSED` und startet **keinen** neuen Batch. Der Bot bleibt erreichbar
   (er ist der, der berichtet).
2. **Wartungslauf.** Ein eigener Claude-Code-Lauf mit dem **DeepSeek-Token**
   (`envs.worker_env`), Arbeitsverzeichnis `g:\Harness\harness`.
   Werkzeugrechte wie beim Worker (Read/Write/Edit/Grep/Glob/PowerShell), aber
   **räumlich gebunden** an `g:\Harness\harness`:
   - erlaubt: `Write(//g:/Harness/harness/**)`, `Edit(//g:/Harness/harness/**)`,
     `Read/Grep/Glob(//g:/Harness/harness/**)` — **ohne** ungebundene
     Werkzeugnamen (R13f: ein blosses `Read` liest alles, s. u.),
   - verboten: `g:\Harness\secrets`, `g:\Silent Scope Decomp`,
     `g:\Harness\docs`, `g:\Harness\backups`, `g:\Harness\sandbox`,
   - zusätzlich gesperrt: `mcp__ghidra` (kein Ghidra-Zugriff in der Wartung).
   
   **Wichtig:** `logs/`, `runs/` und `state/` liegen *innerhalb* dieser Wurzel.
   Sie werden zusätzlich ausdrücklich gesperrt (`Write/Edit` darauf), damit eine
   Wartung nicht den Betriebszustand oder den Kontostand verbiegt:
   `logs/PROTECT` — konkret: `Write(//g:/Harness/harness/state/**)` usw. in
   `--disallowedTools`.
3. **Prompt** kommt aus einer eigenen Datei `prompts/fix.md`: Rolle
   „Wartungsingenieur", Aufgabe = nur die beschriebene Störung beheben, **kein**
   Umbau, **keine** neuen Funktionen, keine Änderung an `harness.toml`-Budget,
   keine Änderung an `prompts/*.md` (Rollenvorgaben!) ohne ausdrückliche
   Nennung, keine Commits (committen tut der Harness).
4. **Testpflicht, vom Harness geprüft.** *Nach* dem Lauf fährt **der Harness**
   (nicht das Modell) die Suite:
   `python -u -m unittest discover -s tests -p "test_*.py"`. Behauptungen des
   Modells („alle Tests grün") zählen **nicht** — die Zahl kommt aus dem
   Prozess-Exit-Code und dem `Ran N tests`-Text. Rot ⇒ kein `/fixok`-Angebot.
5. **Bericht per Telegram** (immer, auch bei Abbruch):
   - `git diff --stat` und die vollständige Diff-Datei als Belegdatei
     (`docs/_fix_<stempel>.diff`),
   - Testergebnis (Anzahl, Exit-Code, Laufzeit),
   - **Risiko-Einschätzung**: berührte Dateien, `start.ps1`/`harness.toml`
     betroffen? neue Abhängigkeit? Netzzugriff?
   - Kosten/Anfragen/Limit des Wartungslaufs.
6. **Warten auf `/fixok`.** Bis dahin: Zustand bleibt `PAUSED`, es wird **nichts
   committet** und **nichts neu gestartet**. Alternativen: `/fixdrop` (Änderungen
   verwerfen, zurück zum Stand vor dem Wartungslauf) und `/fixlog` (Bericht
   erneut senden).
7. **Nach `/fixok`:** Commit im Harness-Repo (`fix: <Beschreibung>`), dann
   Neustart — und dort greift der Wächter aus Teil B.

### A2. Zwei Betriebsarten (Punkt, der leicht übersehen wird)

- **`/fix` beim laufenden Harness** (Normalfall): der Harness pausiert sich
  selbst, fährt die Wartung im **eigenen Thread** (wie `/ask`, R13f — ein
  blockierender Unterprozess im Takt würde den Telegram-Eingang verstopfen),
  berichtet und wartet.
- **`/fix` bei totem Harness**: dann gibt es niemanden, der Telegram liest. Die
  Wartung muss deshalb **auch** als Konsolenbefehl existieren, der ohne
  laufenden Harness arbeitet (`scripts\fix.ps1 -Beschreibung "…"`), mit
  demselben Ablauf und derselben Testpflicht, und der den Bericht per Telegram
  schickt (dafür reicht der Bot-Token, kein Harness-Prozess).

### A3. Offene Entscheidungen zu Teil A

| Frage | Vorschlag | Warum offen |
|---|---|---|
| Modell des Wartungslaufs | **DeepSeek** (wie beauftragt) für die Reparatur; **Opus (Reviewer-Token)** nur für die *Diagnose* auf Abruf | DeepSeek ist billig und hat den grössten Kontext; der Reviewer hat die besseren Datei-Werkzeuge, kostet aber Pro-Kontingent. Der Auftrag nennt DeepSeek — die Diagnose-Ausnahme wäre neu. |
| Darf die Wartung `prompts/*.md` ändern? | **nein**, ausser die Beschreibung nennt genau diese Datei | Rollenvorgaben sind Verhalten; eine „Reparatur", die den Reviewer-Prompt lockert, wäre eine stille Vollmachtsänderung. |
| Darf die Wartung Tests ändern? | **ja, aber sichtbar**: Teständerungen werden im Bericht **gesondert** ausgewiesen, mit Anzahl neuer/entfernter Tests | „Tests grün" ist wertlos, wenn die Wartung die Tests anpasst. Der Bericht muss das zeigen, die Entscheidung bleibt beim Nutzer. |
| Budgetdeckel | `--max-turns 60` und harte Kostenobergrenze über den bestehenden Tageszähler (`budget`) | Ein Reparaturlauf ohne Deckel kann ein Kontingent leerlaufen. |
| Mehrere `/fix` hintereinander | je Reparatur ein eigener Commit + Bericht, kein Sammellauf | Sonst ist der Rollback nicht zurechenbar („letzter funktionierender Commit"). |

---

## Teil B — Wächter in `start.ps1`

### B1. Warum ein Wächter **allein in `start.ps1`** nicht reicht (CONFIRMED)

Die beiden stillen Tode kamen aus dem **Job-Objekt von `Code.exe`**: startet man
`start.ps1` aus einem VS-Code-Terminal, hängt der Harness mit im Job des Editors
und wird mit ihm abgeräumt. Ein Wächter, der als Kind **desselben** Terminals
läuft, stirbt mit — er würde genau den Fall nicht abdecken, für den er gedacht
ist. Konsequenz für den Plan: der Wächter gehört in eine **eigene Instanz**
(Task Scheduler bzw. ein von Hand geöffnetes PowerShell-Fenster ausserhalb von
VS Code). `start.ps1` bleibt der Starter und wird nur um die Schleife erweitert;
die Aufsicht von aussen ist der eigentliche Träger.

### B2. Entwurf der Schleife

```
start.ps1 [-Paused] [-Mock] [-Watch] [-MaxNeustarts N] [-GesundSekunden S]
  1. Harness starten (hx.cli run), stderr nach logs/start-stderr.log
  2. auf exit warten
  3. Todesart klassifizieren (siehe B3)
  4. Entscheidung: neu starten | rollen und neu starten | nur melden
  5. Telegram-Nachricht bei jeder Entscheidung (ein Satz + Belege)
```

### B3. Todesarten — der Kern des Entwurfs

Der teure Fehler wäre, **jeden** Ausfall als Codefehler zu behandeln und
automatisch zurückzurollen. Die drei Fälle sind messbar unterscheidbar:

| Klasse | Kennzeichen | Richtige Antwort |
|---|---|---|
| **A Start-Absturz** | Exit ≠ 0 **und** Crash-Bericht `logs/crash-*.txt` **und** Todeszeit < `S` Sekunden nach Start | **Rollback-Kandidat** (zweimal derselbe Commit ⇒ rollen) |
| **B Stiller Tod** | Exit ≠ 0 oder Prozess weg, **kein** Crash-Bericht, Protokolldatei < 1 KB, Laufzeit > 60 s | **kein** Rollback — Code war in Ordnung. Einmal neu starten, melden. |
| **C Hänger** | Prozess lebt, **kein** frischer Herzschlag seit `S` Sekunden | Prozess beenden, einmal neu starten; **Rollback nur**, wenn der Hänger am selben Commit wiederkehrt |

Begründung: B ist genau der Job-Objekt-Fall vom 2026-09-26; C ist der
RDP/GL-Treiber-Fall (R372). In beiden war **kein Commit schuld** — ein Rollback
würde funktionierende Arbeit wegwerfen und den Ausfall verlängern.

### B4. Was „gesund" heisst (muss neu gebaut werden)

Heute gibt es keinen Herzschlag. Vorschlag, minimal:

- Der Orchestrator schreibt im Takt (z. B. jede Runde und bei jedem
  Zustandswechsel) `state/heartbeat.json`:
  `{"pid": …, "takt": N, "zeit": "<ISO>", "zustand": "RUNNING|PAUSED|BATCH|REVIEW"}`,
  atomar (`util.write_json_atomic`) — **eine** kleine Datei, kein Wachstum.
- **Gesund** = (1) Prozess mit dieser PID lebt, (2) Herzschlag jünger als
  `S` Sekunden (Vorschlag `S = 180`, ein Batch-Takt ist viel kürzer), (3)
  `logs/start-stderr.log` seit dem Start **ohne** neuen Traceback, (4)
  `state/run.json` lesbar und mit plausibler Batch-Nummer (nicht kleiner als
  beim Start).
- `hx.cli status` und `watch` zeigen den Herzschlag mit an (ein Feld) — dann ist
  „gesund" auch von Hand prüfbar, nicht nur im Wächter.

### B5. Rollback — ehrlich benannte Grenzen

Geplanter Weg: `gitsafe` (`git log`, `is_ancestor`) markiert **vor** dem
Neustart den Stand als gut (`git tag -f harness-gut`), nach `/fixok` wird der Tag
verschoben. Beim Rollback: `git reset --hard harness-gut`, danach Neustart,
danach Telegram-Nachricht mit der übersprungenen Commit-Kennung.

Grenzen, die im Bericht stehen müssen:

1. **Nicht getrackte Dateien** (u. a. `logs/`, `runs/`, `state/`, `__pycache__`,
   `docs/_*`) bleiben liegen. Ein Rollback stellt Code wieder her, **nicht** den
   Betriebszustand. `state/run.json` wird deshalb **ausdrücklich nicht**
   zurückgesetzt (Buchführung/Anker darf nicht rückwärts springen).
2. **Kein Remote ⇒ kein Netz-Rückfall.** Existiert der Tag nicht (erster Start),
   ist der Rollback nicht möglich: dann nur neu starten und melden.
3. **Fehlerhafte Wartung + grüne Tests** ist möglich (Tests decken nicht alles).
   Deshalb bleibt `/fixok` eine **Nutzerentscheidung**; der Rollback ist die
   Notbremse, kein Ersatz dafür.
4. **Endlosschleife.** `-MaxNeustarts` (Vorschlag 3) und eine wachsende Wartezeit
   verhindern Karussell-Starts; danach bleibt der Wächter mit Meldung stehen.
5. **Ein Wächter kann den Wartungslauf nicht überwachen.** Wenn `/fix` selbst
   den Harness zerlegt, sieht der Wächter nur „startet nicht mehr" — deshalb der
   Test-Vorlauf **vor** `/fixok` und der Tag **vor** der Wartung.

---

## Risiken (Gesamtbild)

| Risiko | Wirkung | Gegenmittel im Entwurf |
|---|---|---|
| Wächter läuft im Job-Objekt von VS Code und stirbt mit | Selbstheilung wirkt genau nicht | eigene Instanz (Task Scheduler), B1 |
| Automatischer Rollback bei Umgebungsfehlern | wirft gute Arbeit weg | Todesarten A/B/C, B3 |
| Wartung schreibt in `state/`, `logs/`, `secrets` | verfälschte Buchführung bzw. Schlüsselabfluss | räumlich gebundene Rechte + Verbotsliste, A1 |
| „Tests grün" ist nur eine Behauptung | falsche Sicherheit | Testlauf macht **der Harness**, A1.4 |
| Wartung ändert Tests oder Rollenvorgaben | grün auf dem Papier | gesonderter Ausweis im Bericht, A3 |
| `/fix` bei totem Harness nicht erreichbar | Selbstheilung versagt im wichtigsten Fall | Konsolenvariante `scripts\fix.ps1`, A2 |
| Kosten/Pro-Kontingent | unerwartete Kosten | Deckel + Tageszähler, A3 |
| Wächter startet, während `watch` und Telegram parallel laufen | doppelte Ausgabe, verwirrte Zustände | Neustart nur nach Klassifikation; `watch` bleibt rein lesend |

## Offene Punkte, die **der Nutzer** entscheiden muss

1. **Bauen oder nicht** — und wenn ja, Teil A zuerst, Teil B zuerst, oder beides
   zusammen? (Empfehlung: **Herzschlag + `status`-Anzeige** zuerst, das ist klein
   und macht „gesund" überhaupt erst prüfbar; `/fix` danach; der Wächter zuletzt.)
2. **Modell des Wartungslaufs** (DeepSeek wie beauftragt, oder Opus für die
   Diagnose) — siehe A3.
3. **Automatischer Rollback erlaubt?** Der Entwurf erlaubt ihn nur für Klasse A
   (Start-Absturz am selben Commit). Soll er ganz entfallen (nur melden), ist das
   eine zulässige, sogar vorsichtigere Wahl.
4. **Darf die Wartung Tests ändern?** (Vorschlag: ja, aber sichtbar ausgewiesen.)
5. **Startinstanz**: Task Scheduler einrichten (Aufgabe des Nutzers, nicht des
   Harness) — Voraussetzung dafür, dass Teil B überhaupt greift.
