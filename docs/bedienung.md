# Bedienung des Harness

Alles liegt unter `g:\Harness\harness`. Zwei Bedienwege, **gleichwertig**:

* **Lokal** (Normalfall, am Studio-Rechner): `hx.cli`-Befehle in einem PowerShell-Fenster.
* **Telegram** (Fern-/Notfallzugang): Bot `@Ghidra_studio_bot`, nur für die eingetragene
  User-ID (`allowlist_user_ids` in `harness.toml`).

Zustand und Logs liegen in `state\`, `logs\`, `runs\`, `inbox\` — **kein** Zustand steckt
im Chat oder im Terminal.

---

## 1. Starten und Beenden

```powershell
cd g:\Harness\harness

# eigener Start im Freigabemodus, ZUSTAND PAUSIERT (empfohlen)
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Paused

# ohne -Paused laeuft er sofort los (nur sinnvoll mit Dauerbetrieb)
# mit -Mock laufen Attrappen statt echter API-Aufrufe (kostet nichts, zum Testen)
```

Der Harness läuft **unabhängig von VS Code** in einem eigenen Fenster; das Schließen des
Fensters beendet ihn. Nach einem Neustart nimmt er Zustand und Queue aus `state\` und
`inbox\` wieder auf.

### 1a. NICHT aus dem VS-Code-Terminal starten (gemessen 2026-09-26, R13e)

**Befund.** Prozesse, die aus einem VS-Code-Terminal gestartet werden, liegen in einem
**Job-Objekt von VS Code** (`Code.exe`). Wird dieses Terminal bzw. die Sitzung
aufgeräumt, beendet VS Code den ganzen Job — der Harness stirbt **ohne Spur**: kein
Traceback, keine stderr-Zeile, kein `crash-*.txt`, nur die Logdatei bricht mitten ab.

Beleg (`docs\_start_aus_terminal_beleg.txt`, mit `IsProcessInJob` gemessen):

| Prozess | im Job-Objekt |
|---|---|
| `python` (Skript) → `powershell.exe` → `Code.exe` (utility) → `Code.exe` (Haupt) | **ja** |
| `explorer.exe` (Grenze des Jobs) | nein |
| Harness `python -m hx.cli run --paused`, **in eigenem Fenster** gestartet (PID 1236) | **nein** |

Die zwei stillen Abstürze der Nacht (`logs\harness-2026-09-25T223007+0000.log` und
`…T001234+0000.log`, je **373 Bytes**, Ende in derselben Sekunde wie der Start) tragen
genau dieses Muster: drei INFO-Zeilen, dann nichts — keine Ausnahme, kein Bericht. Die
zwei *anderen* Abstürze derselben Nacht (PermissionError) haben dagegen Berichte
hinterlassen. Damit ist die Ursache eingegrenzt: **getötet, nicht abgestürzt.**

**Regel.** Der Harness wird in einem **eigenen PowerShell-Fenster** gestartet (Startmenü /
Explorer / `Win+R`), **niemals** in einem Terminal innerhalb von VS Code.

**Vorschlag für einen Start ohne jedes Terminal** (nur Vorschlag, noch nicht gebaut):

1. **Am einfachsten:** eine Verknüpfung `Harness starten.lnk` auf dem Desktop, Ziel
   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File g:\Harness\harness\start.ps1 -Paused`,
   Ausführen in `g:\Harness\harness`. Eine Verknüpfung hängt an `explorer.exe`, also
   außerhalb jedes VS-Code-Jobs — genau wie der stabile Lauf der Nacht.
2. **Unabhängig von jedem angemeldeten Fenster:** eine Aufgabe in der
   **Windows-Aufgabenplanung** (`schtasks /create /tn SilentScopeHarness /tr …`,
   Auslöser „Bei Anmeldung“). Sie startet in einer eigenen Sitzung; `start.ps1` läuft
   dann ohne sichtbares Fenster (`-WindowStyle Hidden` wäre zu ergänzen), und `/status`
   bzw. `watch` sind die einzigen Bedienwege. Das ist der robusteste Weg für den
   Dauerbetrieb über Nacht.
3. **Für einen Rechner ohne angemeldeten Nutzer:** ein Dienst-Wrapper (z. B. NSSM) um
   `python -m hx.cli run`. Erst sinnvoll, wenn der Harness ohne interaktives Fenster
   betrieben wird (heute schreibt `start.ps1` bei Fehlern noch ins Fenster und wartet
   auf Enter — das müsste dann entfallen).

Empfehlung: **1.** heute, **2.** vor dem nächsten Nachtlauf.

---

## 2. Lokale Befehle (ohne Telegram)

Immer aus `g:\Harness\harness` aufrufen (`python -m hx.cli …`).

| Befehl | Wirkung |
|---|---|
| `status` | Zustand, Batch, Gate (mit Quelle „vom Nutzer"/„vom Reviewer"), Pause-Info, Kosten, Tarif, Queue, Git-Lage |
| `budget` | Kosten, Alarm-/Hartgrenzen, Tarif |
| `bilanz [--n N]` | **Bilanz** (R13q): Aeste im Vergleich zum Batch N Batches vorher (Vorgabe 1), Projektstand Teil C, Kosten der letzten 24 h, Abo-Auslastung, letzte Batches aus git |
| `thinking [--n N] [--batch B] [--voll]` | **Denkbloecke des Workers** (R13r): die letzten N Denkbloecke aus dem Mitschnitt, je 200 Zeichen; `--voll` ungekuerzt, `--batch` ein bestimmter Batch (sonst der neueste) |
| `pause` | pausieren; ein laufender Batch läuft zu Ende, danach startet nichts Neues |
| `resume` | fortsetzen (`--accept-dirty`, wenn ein unsauberer Arbeitsbaum bewusst akzeptiert wird) |
| `stop` | laufenden Batch abbrechen: WIP wird gesichert (Status + Patch + Stash); danach **beendet sich der Harness** |
| `approve [--text "…"]` | wartenden Batch freigeben; optionaler Text geht als ds-Nachricht mit |
| `number <N>` | Batch-Nummer des **offenen** Auftrags setzen (z. B. wenn der Reviewer eine andere nennt) |
| `send ds "Text"` / `send ds --file auftrag.md` | Nachricht an den **Worker** in die Queue (Zustellung am nächsten Batch-Übergang) |
| `send claude "Text"` / `send claude --file ziele.md` | Nachricht an den **Reviewer** in die Queue (Zustellung am nächsten Review) |
| `ask "Frage"` / `ask --file frage.md` / `ask --neu "Frage"` | **freie Frage an Claude** (eigener Lauf, Modell des Reviewers, **nur lesend**). Antwort kommt direkt zurück; Belegdatei unter `logs\ask\`. Läuft **auch während eines Batches** und beeinflusst ihn nicht. Fragen laufen **nacheinander** und im **selben Chat** weiter (Gedächtnis); `--neu` beginnt einen neuen Chat. |
| `run-instruction --file instruktion.md [--profile ghidra-read] [--program /830d01.27p.main.bin]` | **eigene** Instruktion als nächster Worker-Batch, **am Reviewer vorbei**; im Log/Status als „vom Nutzer" gekennzeichnet; danach normaler Batch-Ende-Review |
| `watch [--batch N] [--run name] [--no-color] [--once]` | Live-Ansicht bzw. Nachspielen; **rein lesend** |
| `profiles` | verfügbare Ghidra-Werkzeugprofile mit Zahlen |
| `probe-telegram` | Bot-Name, Allowlist und Absender der letzten Nachrichten |
| `show-prompts` | Review-Prompt und Worker-Vorspann als Dateien in `preview\` |
| `env-proof` | R16-Nachweis: echter Kleinlauf, der prüft, ob Unterskripte Zugangsdaten sehen — und ob die Werkzeugkette stimmt |
| `rebuild [N]` | Lauf aus dem Mitschnitt **nachrechnen** (Tokens, Kosten, Snapshot), wenn der Harness nach dem Worker-Ende stand |

Ohne laufenden Harness bleiben die Befehle als Datei in `state\ctl\` liegen und werden beim
nächsten Start ausgeführt — `status` zeigt sie dann unter „Lokale Befehle warten".

**Wie schnell wirkt ein Befehl?** Der Harness holt die Steuerdateien am Anfang jedes
Schleifendurchlaufs ab. Im Pausenzustand liegt dazwischen die Telegram-Abfrage (Langpoll,
`poll_timeout_s = 25`), ein lokaler Befehl wirkt also nach **wenigen Sekunden bis ~30 s**.
Im Notfall ist `stop.ps1 -Force` sofort.

---

## 3. Telegram-Befehle

`/status` · `/budget` · `/bilanz [N]` · `/thinking [N] [voll]` · `/pause` · `/resume [ok]` ·
`/stop` · `/approve [Text]` ·
`/number <N>` · `/autonom [on|off]` · `/ds <Text>` · `/claude <Text>` · `/ask <Frage>` ·
`/ask-neu <Frage>` ·
`/review` · `/last [ds|claude] [n]` · `/queue` · `/why` · `/help`

`/ask` ist **kein** Eingriff in den Betrieb: es ist ein eigener, rein lesender Lauf
(Decomp-Repo **und** der ganze Harness-Ordner samt `docs\`-Belegen) im **eigenen Thread** —
der laufende Batch merkt nichts davon. Gesperrt sind `secrets`, `backups` und jede
`.credentials.json` (nachgewiesen: `docs\_ask_zugriff_beleg.txt`). Antworten sind lang und
werden automatisch aufgeteilt; unter der Antwort steht die Zeile mit Modell, Anfragen,
**Token-Zahlen** (statt Dollar — der Lauf geht über das Abo), Chat und Dauer.

**Frage-Chat (`/ask`, R13o):** Die erste Frage öffnet einen Chat, weitere Fragen laufen
darin weiter — Rückfragen („und warum?“) kennen also die vorige Antwort. Ein neuer Chat
beginnt, wenn eine der drei Grenzen aus `[ask]` reißt (30 min ohne Frage, mehr als
10 Fragen, älter als 2 h) — oder sofort mit `/ask-neu <Frage>`. Fragen werden **strikt
nacheinander** abgearbeitet: läuft schon eine, kommt „Frage eingereiht (Platz N)“ und sie
kommt danach dran. Eine Datei-Sperre verhindert außerdem, dass `hx.cli ask` und ein
Telegram-`/ask` dieselbe Session gleichzeitig greifen.

`/review` verwirft einen offenen Auftrag und hebt die Pause auf — der Harness bewertet
sofort neu. `/last claude` liefert die **vollständige** letzte Instruktion.

Nachrichten werden **nie** in einen laufenden Batch injiziert: sie landen als Queue-Datei
und werden am nächsten Übergang zugestellt. Nachrichten über 4000 Zeichen werden
automatisch aufgeteilt (auch einzelne sehr lange Zeilen). Im Freigabemodus sendet der
Harness die Instruktion **vollständig**, nicht als Auszug.

---

## 4. Manuelles Arbeiten in der Pause

Während **PAUSIERT** startet der Harness nichts — du kannst direkt im Repo arbeiten
(VS Code/Copilot oder Claude Code).

Beim `resume` prüft der Harness:

1. **HEAD bewegt oder Arbeitsbaum nicht sauber** → *kein* Worker-Start; du bekommst eine
   Meldung; der **nächste Review** erhält den Hinweis „Nutzer hat in der Pause gearbeitet"
   samt `git log` und Diffstat seit Pausenbeginn.
2. **Arbeitsbaum unsauber** → der Harness wartet. Weiter geht es, wenn du committest
   **oder** ausdrücklich bestätigst: `resume --accept-dirty` (Telegram: `/resume ok`).

Der Hinweis wird **einmal** zugestellt (der nächste Review), damit er den Prompt nicht
dauerhaft vergrößert.

---

## 5. Live-Ansicht (`watch`)

```powershell
# in einem zweiten PowerShell-Fenster:
cd g:\Harness\harness
python -m hx.cli watch                  # was JETZT passiert (Review, Freigabe, Worker)
python -m hx.cli watch --once           # nur ein Bild der jetzigen Lage
python -m hx.cli watch --batch 159      # abgeschlossenen Batch nachspielen
python -m hx.cli watch --run env-proof  # benannten Lauf nachspielen (z. B. env-Beweis)
python -m hx.cli watch --no-color       # klassisches Konsolenfenster ohne ANSI-Codes
```

Ohne Argumente folgt `watch` dem Geschehen: läuft ein **Review**, steht dort „REVIEW LAEUFT
seit …“ samt Mitschnitt des Reviewer-Laufs (`runs/b<N>/reviewer.jsonl`, nur lesende
Werkzeuge Read/Grep/Glob); wartet eine **Freigabe**, werden Zusammenfassung und die
vollständige Instruktion gezeigt; läuft ein **Worker**, erscheint sein Mitschnitt live
(Texte, Werkzeugaufrufe, Ablehnungen, laufende Kosten).

Zusätzlich zeigt `watch` die **Phase des Harness** (`Harness: push` / `review` / `gate` /
`worker`) — also was nach dem Worker-Ende gerade passiert. Die Zahlenzeile erscheint
**nur, wenn sie sich ändert**; nach dem Ende des Workers kommt die Kennzahlen-
zusammenfassung genau einmal.

Farben schaltet `watch` selbst ab, wenn die Konsole kein ANSI kann (klassische
PowerShell), bei `NO_COLOR` oder umgeleiteter Ausgabe; `--no-color` erzwingt es.

**Rein lesend:** `watch` öffnet nur Dateien, die der Harness ohnehin schreibt, kennt keine
Sperren und schreibt nichts. Fenster schließen oder `Strg+C` beendet nur den Zuschauer. Der
laufende Betrieb wird in keiner Weise beeinflusst.

---

## 6. Notfall-Stopp

| Weg | Wirkung |
|---|---|
| `python -m hx.cli stop` | sauber: Stop-Marker, WIP-Sicherung, Worker wird beendet, **Harness-Prozess beendet sich selbst** |
| Telegram `/stop` | dasselbe über den Bot |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1` | setzt den Stop-Marker (greift beim nächsten Durchlauf: WIP-Sicherung + Selbstende) |
| `.\stop.ps1 -Force` | ohne Wartezeit: `taskkill /PID … /T /F` auf den Harness-Prozessbaum |
| Harness-Fenster schließen | sofortiges Ende des Harness (Bot geht offline) |

Was ein Stopp **nicht** tut: es werden keine Analyse- oder Belegdateien gelöscht und keine
Git-Historie umgeschrieben. Ghidra selbst bleibt unangetastet — der Programmwechsel macht
nur der Harness, nicht der Worker.

---

## 7. Was der Harness pro Batch automatisch tut

1. Ghidra erreichbar? (nur bei Ghidra-Profil) — sonst kein Start.
2. Programm **stellen** und prüfen (`load_program_from_project` + `switch_program`).
3. **Projekt-Sicherung** (`.gar`) vor jedem Batch mit schreibendem Ghidra-Profil.
4. Umgebung prüfen (keine fremden Tokens), Modell `deepseek-flash[1m]` per `--model`.
5. Prompt über **stdin** (keine Kommandozeilen-Grenze), Werkzeugprofil, Grenzen
   (Alarm/Hart), Kostenrechnung nach Tarif je Aufruf.
6. **Ghidra speichern** (nur bei `ghidra-standard`/`ghidra-full`) — siehe 7a.
7. Nach dem Batch: Kennzahlen, Snapshot, Review, Push nach `origin/main`
   (Checkpoint-Tags bleiben lokal).

### 7b. Stand vom Remote übernehmen (seit R13n)

Vor **jedem** Batch und beim **Fortsetzen** (`/resume`) prüft der Harness `origin/main`.
Ist **nur der Remote voraus** (lokaler HEAD ist Vorfahre, also nichts Eigenes ungepusht) und
der **Arbeitsbaum sauber**, macht er einen **schnellen Vorlauf** (`merge --ff-only`, kein
Merge, kein Konfliktrisiko) und meldet:

```
Stand vom Remote übernommen: 3 Commit(s) (a1b2c3d -> e4f5g6h)
  * …
```

Diese Commits gelten als **Nutzerarbeit** (Kennzeichnung über den Hash, nicht über den
Commit-Titel): der nächste Review bekommt dafür einen eigenen Block „VOM REMOTE
ÜBERNOMMEN“, und der nächste Worker erfährt es in seinem Vorspann. Wegen R367 gilt dann:
**Neubau** (`port_build.ps1`, `-Gl`) und **eine** vollständige Regression
(`port_regression.py`) zu Batch-Beginn.

Angehalten wird weiter, wenn
* der lokale Stand voraus ist (`ahead > 0`) → Meldung „weicht ab“,
* beide Seiten eigene Commits haben → Meldung „**DIVERGIERT**“,
* der Arbeitsbaum nicht sauber ist → „kein Pull“, Meldung mit den Änderungen.

Ein stehengebliebener Auftrag bleibt in allen diesen Fällen **erhalten** — nach dem
Fortsetzen startet er ohne neuen Review (R13m).

### 7a. Ghidra speichern (seit R13)

Nach jedem Batch mit **schreibendem** Profil (`ghidra-standard`, `ghidra-full`) ruft der
Harness **sofort** `save_all_programs` auf — **vor** Push und Review. Erfolg wird geprüft;
schlägt es fehl, **pausiert** der Harness und meldet per Telegram
(„GHIDRA NICHT GESPEICHERT“), Push und Review unterbleiben. Bei Profil `none` bzw.
`ghidra-read` passiert nichts (Meldung „nicht noetig“).

Dieselbe Sicherung läuft **bei `/stop` und beim Beenden des Harness**, falls seit dem
letzten Speichern noch ein Schreib-Batch offen ist (Merker `ghidra_pending` in
`state/run.json`). Im Messdatenblock jedes Reviews steht dazu eine Zeile
`- Ghidra gespeichert: ja / nein / nicht noetig`.

---

## 9. Git, Werkzeugkette, Reviewer-Modell (Lehren aus B159)

**Git ist nie interaktiv.** Jeder `git`-Aufruf läuft mit `GIT_TERMINAL_PROMPT=0`,
`GCM_INTERACTIVE=never`, `GIT_ASKPASS=` leer und hat ein Zeitlimit
(`[git] timeout_s = 120`, `fetch_timeout_s = 180`, `push_timeout_s = 180`).
Ein Zeitlimit oder Fehler **bricht mit Meldung ab** statt zu warten; ein
**fehlgeschlagener Push pausiert** den Harness (der Remote liegt sonst zurück).

**Werkzeugkette.** Der Worker bekommt den PATH des Harness **plus** die unter
`[env] path_prepend` genannten Verzeichnisse — `"$MSYS_UCRT64"` wird gesucht wie in
`scripts/port_build.ps1` (R310). Damit sieht der Worker denselben Compiler wie deine
Arbeit (`g++ 16.2.0` aus MSYS2-UCRT64, Stand B158), nicht das alte MinGW.org 6.3.0.
Beleg: `python -m hx.cli env-proof` (Abschnitt „Werkzeugkette“ im Bericht).

**Reviewer-Modell.** Der Reviewer läuft mit **`claude-opus-5-5`** und Effort **high**
(`[claude] model_reviewer`, `reviewer_effort`; umgesetzt über `--model` und
`CLAUDE_CODE_EFFORT_LEVEL`). Weicht das Modell **laut Ausgabe** davon ab, wird der
Review **verworfen** (Ablage `runs/b<N>/review-verworfen.md`), per Telegram gemeldet
und pausiert — es wird nichts freigegeben. Modell und Effort stehen in `/status` und
im Messdatenblock des Reviews.

**Batch-Nachrechnen.** Bleibt ein Lauf ohne Abschluss liegen (Harness stand still),
rechnet `python -m hx.cli rebuild <N>` Tokens, Kosten und Snapshot aus
`runs/b<N>/stream.jsonl` nach. Die Ausgabe-Tokens kommen dann aus dem
`result`-Ereignis (die Ereignisse selbst tragen bei DeepSeek keine Ausgabe); die
Gegenprobe steht in den Messdaten (`usage_check`).

**Laufzeit = Wanduhr des Worker-Prozesses.** Gemessen wird die Zeit vom Start bis zum Ende
des Worker-Prozesses; beim Nachrechnen kommt sie aus `duration_ms` des Mitschnitts (nicht
aus `duration_api_ms`, das nur die API-Zeit ist — B159 stand damit mit 289 s in der Bilanz,
während der Prozess 377 s lief). Jede Laufzeit nennt ihre Herkunft; liegt die Harness-Messung
um mehr als 120 s über der Selbstauskunft des `claude`-Prozesses, meldet der Lauf
`ALARM: Harness-Nachlauf … - Ausgabe-Rueckstau pruefen`.

**Frische Reviewer-Session und Übergabe.** Der Wechsel ist verbucht, sobald er entschieden
ist: neue Kennung im Zustand, Übergabe in `sessions/claude-<neu>.md` und
`sessions/vorherige-session.md`. Liegt für die alte Session schon eine brauchbare Übergabe
vor (`reviewer.pending_handover`), wird sie **wiederverwendet** statt erneut abgefragt.
Der Review läuft immer in der neuen Kennung (`--session-id <neu>`); die alte wird nur per
`--resume` für die Übergabe benutzt.

**Frische Reviewer-Session (R13-2).** Eine Session wird nach `[claude] reviewer_rotate`
Reviews **regulär rotiert**. Vor der Rotation bittet der Harness die alte Session um eine
**Übergabe** (`UEBERGABE`-Aufruf, Phase „uebergabe“, Zeitlimit, Fehler ist nicht tödlich);
der Text landet in `sessions/vorherige-session.md` und wandert als Block
`=== UEBERGABE AUS DER VORIGEN SESSION ===` in den Prompt der **neuen** Session. Beide
Schritte stehen im Log (`Reviewer-Session-Wechsel`, `Uebergabe erhalten`,
`Neue Reviewer-Session … uebergabe_zeichen`).

Erzwungen wird die Rotation mit `"force_rotate": true` im Abschnitt `reviewer` von
`state/run.json` — der Merker wird beim nächsten Review verbraucht und danach gelöscht.
Der Session-Mitschnitt der neuen Session: `sessions/claude-<neue-id>.md`.

---

## 8. Batch-Nummern (nur aus dem Anker)

Die Nummer kommt **ausschließlich** aus dem Anker (`analysis/r1b-workstream.md`): Kopfzeile
`**Stand:** BATCH 158` → nächster Batch ist **159**. Der Harness führt keinen eigenen
Zähler mehr. Der Review-Prompt nennt diese Nummer ausdrücklich, und die `DS_INSTRUCTION`
muss damit beginnen.

* Run-Verzeichnis des Laufs: `runs/b<Nummer>/` (`.md`-Review vorher: `review-pre.md`,
nach dem Batch: `review.md`, Mitschnitte `stream.jsonl` und `reviewer.jsonl`).
* Checkpoint-Tag: `harness/b<Nummer>-start` (bleibt lokal).
* **Nennt die Instruktion eine andere Nummer**, startet der Harness nichts: er pausiert,
meldet beide Nummern und bietet an
  * `/number <N>` — Nummer des offenen Auftrags setzen, danach `/approve`,
  * `/review` — neuen Review anfordern (verwirft den offenen Auftrag).

Die Nummer des verworfenen Auftrags wird in `logs/verworfen-<id>.json` abgelegt.

**Review-Verzeichnis = Anker-Nummer.** `runs/b<N>` sammelt alles zu Batch N: die **Worker**-Belege
(`auftrag.md`, `stream.jsonl`, `antwort.md`, `result.json`) und das **Review**, das den
nächsten Batch vorbereitet (`review.md`/`review-pre.md`, `harness-facts.md`, `reviewer.jsonl`).
Ein Review, das Batch 159 bewertet, liegt also in `runs/b160` — die Belege des bewerteten
Laufs bleiben in `runs/b159`. Das Gate trägt dieselbe Nummer (160, der Batch, für den
freigegeben wird); die Messdatenzeile nennt beide (`- Review: bewertet wird Batch 159; die
Instruktion gilt fuer Batch 160`).

**Ein Review ohne gültigen Protokollblock öffnet nie ein Gate.** Fehlt ein Block
(`TELEGRAM_SUMMARY`, `DS_TOOLS` mit Profil, `DS_INSTRUCTION` mit Batch-Nummer) oder stimmt
das Modell nicht, wird der Review **verworfen** (Rohantwort als
`runs/b<N>/review-verworfen-<Stempel>-v<Versuchsnummer>.md`, Mitschnitt v1 als
`reviewer-v1.jsonl`), dann läuft **ein** Wiederholungsversuch mit ausdrücklicher
Format-Erinnerung (`=== FORMAT-ERINNERUNG (ZWEITER VERSUCH) ===` plus die vorige Antwort).
Scheitert auch der, **pausiert** der Harness und meldet per Telegram mit Verweis auf beide
Rohtexte; Protokoll in `logs/review-verworfen-<ts>.json`. Kein Gate, keine Freigabe.

---

## 10. Entscheidungen, Denkblöcke, Absturzschutz (R13c)

### 10a. `ENTSCHEIDUNG NOETIG` ist eine echte Bremse

Der Reviewer nutzt drei Markerzeilen in seiner `<TELEGRAM_SUMMARY>`
(`prompts/reviewer.md`); der Harness wertet sie aus (`hx/protocol.py`,
`parse_offene_punkte`):

| Zeile | Bedeutung | Wirkung |
|---|---|---|
| `ENTSCHEIDUNG NOETIG: …` | die nächste Instruktion hängt von deiner Antwort ab, oder es ist eine grundsätzliche Weichenstellung | **bremst**: das Gate wird auch im Dauerbetrieb **nicht** automatisch freigegeben. Telegram meldet „Wartet auf deine Entscheidung“, `/status` und `watch` zeigen den Punkt |
| `ENTSCHIEDEN: …` | der Reviewer hat **selbst** entschieden (Priorisierung, Weg, Umfang, Profil, Umgang mit Sackgassen) | bremst **nicht**. Sichtbar in `/status` und `watch` als „Entschieden (Reviewer, Widerspruch per /claude)“. **Dein Veto** ist `/claude <Text>`; es wiegt wie eine Nutzerentscheidung |
| `OFFENE FRAGE: …` | nur zur Information (z. B. die Audio-Frage in B159), die Arbeit geht an anderem weiter | bremst **nicht** |
| `WARTET AUF LIVE-AUFNAHME: …` | es fehlt Material, das nur du liefern kannst | bremst **nicht** |

**Wann der Reviewer noch fragt (Entscheidungsregel, R13f).** `ENTSCHEIDUNG NOETIG` benutzt er
nur in fünf Fällen: Änderung an **Projektziel/Umfang**, ein Eingriff aus der **Verbotsliste**,
**Material, das nur du liefern kannst** (nur wenn der nächste Batch ohne dieses Material nicht
weiterkann — sonst `WARTET AUF LIVE-AUFNAHME`), **Abweichung von einer ausdrücklichen
Nutzerentscheidung**, und der **Übergang zur systematischen Dekompilierung**. Alles andere —
auch Wiederholungen und Sackgassen — entscheidet er selbst (`ENTSCHIEDEN: …`) und begründet es
im Batch-Dokument. Die frühere Regel „zweimal dasselbe Problem → Nutzer fragen“ gilt **nicht
mehr** (Veto-Prinzip statt Eskalation).

Freigeben kannst weiterhin **du** (`/approve`); nur der Automat hält an. Die Punkte stehen in
`/status` (Zeilen „Offene Entscheidung/…“) und in `watch` über dem Gate. Bei älteren Gates
ohne das Feld `offene_punkte` werden sie aus der gespeicherten Zusammenfassung abgeleitet —
der Zustand wird dabei **nicht** verändert.

**Verbotsregel im Reviewer-Prompt:** Force-Push, Umschreiben der Historie, Löschen unter
`analysis/`, `restore_project`, Änderungen an den `AGENTS.md`-Grundregeln und am Projektziel
darf der Reviewer **nie** in derselben Instruktion verlangen, in der er die Entscheidung
erfragt — erst in einer späteren Instruktion, nachdem deine Antwort als `/claude`-Nachricht
angekommen ist.

### 10b. Denkblöcke in `watch`

`watch` zeigt `thinking`-Blöcke des Mitschnitts live an: abgesetzt mit Präfix `  ~ `,
gedimmt, Leerraum zusammengezogen, lange Blöcke bei 400 Zeichen gekürzt mit
`[gekuerzt - Denkblock hat <N> Zeichen]`. **Leere** Blöcke (die API liefert bei
`display: "omitted"` Blöcke ohne Text, nur mit `signature`) werden übersprungen.

    python -m hx.cli watch --batch 160              # mit Denkbloecken
    python -m hx.cli watch --batch 160 --no-thinking # ohne
    python -m hx.cli watch --no-thinking             # live, ohne

Reine Anzeige: `watch` liest nur Dateien — kein Einfluss auf Harness, Kosten oder Mitschnitte.

### 10c. Absturzschutz

* **Jede unbehandelte Ausnahme** wird von `Orchestrator.report_crash` festgehalten: vollständiger
  Traceback ins Harness-Log **und** in `logs/crash-<zeit>.txt`, dazu (wenn möglich) Telegram
  „HARNESS ABGESTÜRZT“ mit dem Pfad des Berichts. Der Prozess endet mit Exit-Code 3.
* `start.ps1` schreibt stderr zusätzlich nach `logs/start-stderr.log` und lässt bei einem
  Fehler-Exit das Fenster stehen: Exit-Code, Pfad des Crash-Berichts und dessen letzte
  20 Zeilen, dann „Enter zum Schliessen“.
* `/status` sagt bei totem Prozess ausdrücklich `Harness-Prozess: … - HARNESS LAEUFT NICHT`
  und nennt den letzten Crash-Bericht (`Letzter Crash-Bericht: crash-….txt (<ts>)`).
* **Harte Tode** (TerminateProcess: `taskkill`, Job-Objekt von VS Code, geschlossenes
  Fenster) kommen hier **nie** an — kein Bericht, keine stderr-Zeile, kein
  Ereigniseintrag, Zustand bleibt auf `DS_WORKING`. Erkennung, der belegte Fall vom
  2026-09-26 (ein Worker räumte `Get-Process python | Where-Object { $_.CPU -gt 50 }`
  ab und tötete damit den Harness) und die Gegenmaßnahmen stehen in
  **`abstuerze.md`**. Beim nächsten Start nennt `recover()` den harten Tod und zitiert
  den verbotenen Befehl aus `runs/b<N>/stream.jsonl`.

**Queue erst nach gültigem Review.** `/claude`-Nachrichten gelten erst als zugestellt, wenn
der Review einen gültigen Protokollblock geliefert hat — sonst bleiben sie unverändert in
`inbox/claude` (und werden beim nächsten Review wieder mitgeschickt).

---

## 11. Schlüssel, Überwachung, Bereinigung (R13g, 2026-09-26)

### 11a. Wo die Zugangsdaten liegen (und warum nicht mehr im Harness)

Die drei Schlüsseldateien (`deepseek.key`, `telegram.key`, `claude-oauth.token`) liegen
**außerhalb** des Harness-Ordners:

    %USERPROFILE%\.hx-secrets\        (ACL: nur dieser Windows-Benutzer)

Grund (gemessen): ein ungebundenes `--allowedTools Read` erlaubt **jeden** Pfad — mit dem
alten Ort im Harness konnten Reviewer **und** Worker die Schlüssel lesen
(`docs/_ask_zugriff_regeln.txt`). Seit R13f sind die Leseregeln der Rollen pfadgebunden;
seit R13g liegt der Schlüssel zusätzlich dort, wo kein Modell aus seiner Vorgeschichte
danach sucht. Der **alte** Ordner `g:\Harness\secrets` bleibt leer und bleibt in den
Werkzeugverboten — dort soll niemand mehr suchen.

    python -u tools\setup_secrets.py            # Umzug + Rechte (idempotent)
    python -u tools\setup_secrets.py --check    # nur prüfen
    # Beleg: docs\_secrets_umzug.txt

`[paths] secrets` in `harness.toml` steht auf `$USERPROFILE/.hx-secrets`; die Auflösung
macht `hx/config.py` (der Workspace bleibt damit auf andere Rechner kopierbar). Nach einem
Rechnerwechsel: `python -u tools\setup_secrets.py` einmal laufen lassen.

**Grenze, die man kennen muss:** der Worker läuft als derselbe Windows-Benutzer und hat
PowerShell. Das Verschieben ist eine **Hürde, keine Mauer**. Dicht wird es erst mit einer
eigenen Identität (Option 4 im Bericht vom 2026-09-26).

### 11b. Überwachung: `SECRET-ZUGRIFF`

Worker-, Reviewer- und `/ask`-Mitschnitte werden auf zwei Dinge geprüft (hx/streamjson.py):

| Suche | Wo | Wirkung |
|---|---|---|
| **Schlüsselwert** im Mitschnitt | jede Zeile | Treffer = Leck → Telegram `SECRET-ZUGRIFF`, Zeile in `logs/secret-zugriff.jsonl` |
| **Zugriffspfad** (alt/neu) | nur Werkzeugaufrufe | Treffer → derselbe Alarm. Bei schreibenden Werkzeugen zählt nur das **Ziel**, nicht der Textinhalt; ein Dokument, das den Pfad zitiert, ist **kein** Zugriff |

Der Alarm nennt Art, Werkzeug und Dateinamen — **nie** einen Wert oder ein Pfadfragment
des Inhalts (der Belegtext wird entschärft). Der Review-Messdatenblock enthält zusätzlich
die Zeile `- SECRET-ZUGRIFF (Überwachung): keine | N Treffer …`, damit ein Blick in die
Messdaten genügt.

### 11c. Bereinigung alter Mitschnitte

    python -u tools\scan_secrets.py [--redact] [--kontext]
    # Belege: docs\_secret_scan*.txt

Sucht in `runs/`, `logs/`, `state/`, `cc-worker/`, `cc-reviewer/`, `snapshots/`,
`sessions/`, `sandbox/`, `docs/` nach den Schlüsselwerten (Vergleich **nur im Speicher**;
Ausgabe: Datei, Name, Anzahl). `--redact` ersetzt Fundstellen durch
`<SCHLUESSEL-ENTFERNT>`; `--kontext` zeigt die Herkunft (entschärft).

**Fallstrick:** `sandbox\decomp-link` ist eine **Junction** ins Decomp-Repo. Ein `rglob`
folgt ihr und meldet 69 GB statt 30 MB — das Werkzeug nimmt deshalb `os.walk`
(`followlinks=False`) und überspringt Verknüpfungen sowie Binärartefakte.

---

## 12. Laufzeit: wo die Zeit hingeht (R13h, 2026-09-26)

Frage: manche Batches dauern Stunden und verbrauchen dabei wenige Tokens. Antwort aus
den Mitschnitten (`tools\analyse_laufzeit.py`, Beleg `docs\_laufzeit_analyse.txt`):

| Batch | Wanduhr | Werkzeuge | Modell | davon reines Warten |
|---|---|---|---|---|
| 172 | 7065 s | **5702 s (81 %)** | 1356 s | 481 s |
| 174 | 4767 s | 3315 s (70 %) | 1449 s | **1993 s (42 %)** |
| 175 | 4726 s | 2705 s | 2010 s | **1581 s** |
| 176 | 5218 s | 3657 s (70 %) | 1553 s | 540 s |
| 177 | 3181 s | 1331 s (42 %) | 1844 s | 46 s |

**Der Harness ist nicht die Ursache:** die von ihm selbst gemessene Wanduhr weicht nur um
2–21 s von der Selbstauskunft des Claude-Prozesses ab. Die Zeit steckt in langen
Werkzeugläufen (68K-Emulation: 400–600 s je Lauf; Port-Bau: ~420 s bei echten
Quelländerungen, **6,7 s**, wenn nichts zu bauen ist) — und in reinen Wartebefehlen.

### 12a. Was daran geändert wurde

* **Kosten nicht mehr je Zeile rechnen** (`hx/streamjson.py:TaktGeber`). `cost_usd()`
  kostet ~1 ms; bei jedem der 156.493 Zeilen von b177 waren das ~156 s Rechenzeit im
  Thread, der eigentlich nur die Ausgabe des Kindprozesses abnehmen soll. Jetzt nur noch
  im Takt (2 s): **1,6 s statt 156 s** (b172: 3,5 s statt 115 s), Ergebnis identisch —
  Beleg `docs\_kosten_takt_messung.txt`.
* **Laufzeit-Profil im Review und in der Batch-Meldung.** Werkzeugzeit, Modellzeit und
  Wartezeit stehen ab jetzt in `harness-facts.md` (Zeile `- Laufzeit-Profil: …`) und in
  der Telegram-Meldung am Batch-Ende (`Zeit: …`), samt der drei langsamsten Aufrufe.
* **Worker-Vorspann, Abschnitt „RECHENZEIT"**: unabhängige Rechenläufe **parallel**
  (4 Kerne) statt nacheinander, und kein `Start-Sleep -Seconds 300` als Wartemuster —
  Abbruchbedingung mit kurzem Schritt (10–20 s) oder `Wait-Process -Timeout`.

### 12b. Was der Nutzer selbst entscheiden muss

Der grösste Hebel liegt ausserhalb des Harness: die 68K-Emulationsläufe im Decomp-Repo
laufen **nacheinander** (b177: vier `m177_hull`-Läufe à 77–81 s; b172: zwei
`m172_cc3a.py dyn --only-…` à 488 s/483 s). Auf **4 Kernen** bringt paralleles Fahren
(oder ein `--all`-Modus in einem Prozess statt vieler Einzelaufrufe) grob den Faktor
2–4 auf genau diesen Anteil. Das sind Skripte und Batch-Entscheidungen des Workers —
die Harness-Seite kann sie nur sichtbar machen und anordnen (12a), nicht selbst
umschreiben.

---

## 13. Was mitgeschnitten wird — und wie man nach einem Absturz vorgeht (R13p)

**Alles, was ein Batch tut, steht auf der Platte.** Es gibt keinen Sammel-Export und
keine Aufräumroutine, die Mitschnitte löscht; die Dateien sind Rohbelege und werden
nur nach 14 Tagen gepackt (13c).

### 13a. Wo was steht

| Datei | Inhalt |
| :--- | :--- |
| `runs/b<N>/stream.jsonl` | **Der vollständige Mitschnitt des Worker-Laufs**: jede Zeile der DeepSeek-Ausgabe — Antworttexte, Denkblöcke, jeder Werkzeugaufruf **und dessen Ergebnis**. Das ist die Quelle für `rebuild`, `watch` und alle Token-/Kostenzahlen. (Testläufe: `stream-v1.jsonl` beim zweiten Anlauf.) |
| `runs/b<N>/reviewer.jsonl` | Mitschnitt des Reviews (Prompt-Ereignisse, Antwort, Nutzerlimit-Werte) |
| `runs/b<N>/auftrag.md` | Der vollständige Prompt des Workers (Vorspann + Auftrag + Queue) |
| `runs/b<N>/result.json` | Kennzahlen des Laufs: Exit-Code, Dauer, Anfragen, Token, Kosten, Abbruchgrund |
| `runs/b<N>/harness-facts.md` | Der Messdatenblock, den der Review bekam |
| `runs/b<N>/antwort.md` | Abschlussbericht des Workers (wortgleich im Review) |
| `runs/b<N>/review.md`, `review-prompt-*.md` | Bewertung und der Prompt, mit dem sie entstand |
| `snapshots/b<N>/snapshot.md`, `tools.tsv`, `reasoning.jsonl` | Kennzahlen-Snapshot, Werkzeugzählung, Denkblöcke separat |
| `logs/harness-<startzeit>.log` | Harness-Protokoll als JSONL — **je Start eine neue Datei**, wird nie überschrieben |
| `logs/crash-<zeit>.txt` | Traceback bei einem echten Absturz (Python-Fehler) |
| `logs/secret-zugriff.jsonl` | Jeder Zugriff auf Schluesseldateien (Art, Werkzeug, Dateiname) |
| `logs/rate-limit.json` | Zuletzt gemeldete Abo-Auslastung (Quelle, Zeitpunkt, Prozent) |
| `state/run.json` | Zustand, Batch, Gate, `harness_head`, `remote_work`, `retention` |
| `logs/wip-b<N>-status.txt` / `.patch` | Was bei einem Stopp unfertig im Arbeitsbaum lag |

### 13b. Nach einem Absturz: die Reihenfolge

1. **`watch`** — zeigt den laufenden bzw. letzten Lauf, ohne etwas anzufassen
   (`watch --batch N` spielt einen abgeschlossenen Batch nach).
2. **`python -m hx.cli rebuild [N]`** — rechnet den Lauf aus dem Mitschnitt nach
   (Anfragen, Token, Kosten, Dauer) und markiert das Ergebnis als `nachgerechnet`.
   Geht auch bei gepackten Batches.
3. **Harness neu starten** — beim Start läuft die Spurenkunde (`recover()`): sie
   sichert unfertige Arbeit, sucht im Mitschnitt nach verbotenen Prozessabbrüchen
   und nennt in Telegram, ob der Lauf *hart* abgeräumt wurde.
4. **Bei Python-Fehlern** den Traceback in `logs/crash-<zeit>.txt` lesen; die
   letzte Zeile steht auch in `/status`.
5. **Bei „hängt"** (Prozess läuft, tut aber nichts): `py-spy dump --pid <pid>` gibt
   den Stack aller Threads. Damit wurden zwei Hänger gefunden (Telegram-Aufruf im
   Mitschnitt-Leser; Ausgabe-Pipe ohne EOF).

**Ehrliche Lücke:** Ein *harter* Tod (Prozess von aussen beendet, kein
Python-Fehler) hinterlässt **keinen** Crash-Bericht — dann hilft nur,
`runs/b<N>/stream.jsonl` und das Harness-Protokoll zu lesen, plus die Spurenkunde
beim nächsten Start.

### 13c. Aufbewahrung und Platz (R13p)

Einmal pro Tag packt der Harness (nur wenn gerade kein Lauf arbeitet) die
**Mitschnitte und Snapshots, die älter als 14 Tage sind**, als ZIP — je Datei ein
`stream.jsonl.zip` bzw. je Batch ein `snapshots/b<N>.zip`. Geprüft wird vor dem
Löschen: Prüfsumme (`testzip`) **und** Größe des Eintrags; erst dann verschwindet
das Original, und bei jedem Fehler bleibt es liegen. **Unkomprimiert** bleiben
`result.json`, `harness-facts.md`, `antwort.md`, `auftrag.md`, `review.md` — die
braucht man täglich. Pro Tag werden höchstens `MAX_EINHEITEN` (6) Einheiten gepackt,
damit der erste Lauf die Schleife nicht blockiert; der Rest folgt am nächsten Tag.

`watch --batch N` und `rebuild` lesen gepackte Batches **unverändert** (die Leser
gehen über `hx/retention.mitschnitt_zeilen`).

Sind auf dem Laufwerk des Harness **weniger als 20 GB frei**, kommt einmal täglich
eine Telegram-Warnung (`WENIG PLATZ: …`); in `/status` steht die Zeile
`Aufbewahrung (14 Tage -> ZIP): …`.

### 13d. Was R13p sonst geändert hat

- **Grenzen je Batch** (`[limits]`): Alarm erst bei **500** Anfragen (vorher 250),
  harte Grenze bei **1000** (vorher 400 — sie lag nur 53 über dem je gemessenen
  Maximum und hätte einen normalen langen Batch getötet). Gemessen über alle Batches:
  84–347 Anfragen, $0.10–0.41 pro Lauf. `Alarm` meldet nur, `Hart` bricht ab.
- **Nutzerlimit des Abos (neu)**: Claude Code schreibt in jedem Abo-Mitschnitt
  (Review, Übergabe, `/ask`) ein `rate_limit_event` mit dem Verbrauch von Sitzung
  (5 h) und Woche (7 Tage). Bei **≥ 80 %** kommt einmal je Fenster eine
  Telegram-Warnung mit Rücksetzzeitpunkt in deutscher Zeit; `/status` zeigt beide
  Fenster dauerhaft. Bei 100 % ist bis zum Reset Schluss — das Abo hat kein
  Nachkaufen (`overageStatus: rejected`).
- **Nur-Lese-Git für den Reviewer (neu)**: Er hat jetzt das PowerShell-Werkzeug,
  darf damit aber **ausschließlich** `git log`, `git show`, `git diff`, `git status`
  (ohne `-C`, ohne `--output`). Alles andere wird abgelehnt — gemessen mit
  `tools/check_zugriff4.py`, Beleg `docs/_reviewer_git_beleg.txt`.
- **Review-Prompt**: zwei neue Blöcke **`BATCH-DIFF`** (name-status + Diffstat seit
  dem Checkpoint) und **`HISTORIE`** (letzte 15 Commits + die neuesten
  `analysis/port-batch*.md`). Vorher sah der Reviewer nur die letzten **vier**
  Commit-Betreffe und konnte selbst kein `git log` fahren.

---

## 14. Live-Zahlen im Status und die Bilanz (R13q)

### 14a. `/status` zeigt jetzt den **laufenden** Batch

Zwischen „Worker: PID …" und der Reviewer-Session steht eine Zeile, die sich während
des Batches bewegt:

```
Laufender Batch 196: seit 12m34s | 184 Anfragen | $0.2747 | (245889 ein / 45222144 cache / 170190 aus) | Stand 15:11
```

Sie kommt **nicht** aus dem Mitschnitt: `runs\b<N>\stream.jsonl` wird während des Laufs
bis zu **32 MB** groß (b180), und der Harness müsste ihn bei jeder `/status`-Abfrage
lesen. Stattdessen schreibt der Worker die Zahlen **selbst** — gedrosselt auf alle 15 s
(`LIVE_SEKUNDEN`, im Takt-Block von `run_batch`, nach `state.data["live"]`).

Nach dem Lauf bleibt der letzte Stand stehen (`live_letzte`), `/status` zeigt dann
`Laufender Batch: keiner (letzter Batch 196: 184 Anfragen, $0.2747, Stand 15:29)`.
Gibt es noch gar keine Zahlen: `Laufender Batch: keiner (noch keine Live-Zahlen)`.

### 14b. `/bilanz [N]` — Telegram und Konsole

`/bilanz` (Telegram) und `python -m hx.cli bilanz [--n N] [voll]` zeigen **dieselbe**
Ausgabe, als **festes Format**. Reihenfolge (R13s, Nutzerauftrag 2026-09-28):

1. **Kopf:** `BILANZ Batch 206 gegen 205 (Abstand 1)`, darunter `Anker: BATCH 206 |
   Bilanz: 206` (weicht der Anker ab, steht dort eine ausdrückliche Warnung) und
   `ZULETZT: …` — der Anfang der Anker-`Fertig:`-Zeile, also was der Batch geschafft hat.
2. **`WAS SICH GEAENDERT HAT`** (das Wichtigste zuerst): die verifizierten C-Köpfe und
   der gebaute Paket-E-Vorrat des Batches, danach **nur die bewegten Äste** — sortiert
   nach Größe der Änderung, je Zeile `davor % -> jetzt %`, Delta in **Prozentpunkten**
   und die absolute Zahl in Klammern. Zeilen, die den *offenen Rest* messen
   (`Unterbau (B)`), stehen als `offen 569 -> 465 Insn  -104`. Gibt es keine Bewegung,
   steht dort `keine Zahl bewegt`.
3. **`GESAMT`:** Inventar (Nenner), Bau-Liste und offener Rest **in Prozent** mit
   Delta zum Vorbatch, Blätter, **Paket E offen**, Programm-Inventar, und der
   **DURCHSATZ** (siehe 14c). Fehlt eine Zahl in den Belegdateien, steht dort
   „nicht ermittelbar" — es wird **nie** geschätzt.
4. **Äste-Tabelle:** nur noch Zeilen **mit Prozentzahl** (`/bilanz voll` zeigt alle).
   Je Zeile `vorher -> jetzt` und ein Delta (`=`, `+3`, `+0.4 pp`); bewegte Nebenzahlen
   als `vorher: …`. Gezählt werden Hauptzahl **und** Nebenzahlen — sonst gälte ein Ast,
   dessen Nachzügler wandern, als unverändert.
5. **Zusatzzahlen** (Fälle, R216 a–d, reg_a/reg_f), **Kosten und Abo** (letzte 24 h,
   Tageskosten, Abo-Auslastung aus `logs\rate-limit.json`; fehlt die Datei, wird der
   neueste Review-Mitschnitt ausgewertet), **Aufgaben** (Anker-Stand, offener Auftrag,
   letzte Batch-Betreffe aus `git log`).

**Prozent-Regel** (R13s, Nutzerentscheid „selbst rechnen, wo eine Gesamtheit existiert"):
`pct` aus dem Schnappschuss, sonst `insn_gebaut/insn_gesamt`, `gebaut/(gebaut+offen)`,
`gebaut/total`, `gebaut/benannt` (R207) oder `(a+b)/(a+b+offen_a+offen_b)` (Strang A/B).
Äste ohne Gesamtheit (z. B. `Modi`) bekommen keine Prozentzahl — sie erscheinen nur im
Änderungsblock, wenn sie sich absolut bewegt haben.

Der Vergleichsabstand ist der **erste** Parameter: `/bilanz 5` vergleicht mit dem
nächsten **vorhandenen** Batch ≤ `jetzt − 5` (Batch 154 fehlt im Schnappschuss), und
wenn es keinen gibt, steht dort `kein frueherer Batch vorhanden` — es wird nie unter
den ältesten vorhandenen zurückgegriffen.

Versendet wird die Bilanz als **Monospace-Block**. Geteilt wird **vor** dem Umfassen
der Zäune (sonst zerreißt eine Teilung den Block und Telegram lehnt die Nachricht ab),
und Backticks im Text werden entschärft — ein einzelnes ``` ` ``` würde den Block
sonst beenden.

### 14c. DURCHSATZ — Quelle und Rechenweg (R13s)

Der Block steht in `GESAMT` und rechnet **nur aus Belegdateien**, nichts wird geschätzt:

| Zeile | Quelle | Rechnung |
|---|---|---|
| `Koepfe (R207 gebaut)` | `analysis/_m<N>/_bilanz*.txt`, Zeile **`R207 rueckwaerts`** (maschinengeschrieben von `scripts/m149_bilanz.py`) | Spalte „heute" minus Spalte „Vorbatch" = was **dieser** Batch verifiziert hat |
| `Mittel der letzten N` | dieselbe Reihe (bis zu 5 belegte Batches) | arithmetisches Mittel der Differenzen; die Batches stehen in Klammern dahinter |
| `Insn (nur wo belegt)` | Zeile **`Paket E offen`** der Batch-Dokumente (`analysis/port-batch<N>-*.md`) | Insn offen (Vorbatch) minus Insn offen (heute) |
| `offen (Paket E, C-Arbeitsvorrat)` | dieselbe Tabellenzeile, Spalte „heute" | Köpfe/Insn, die in Paket E noch offen sind |
| `HYPOTHESIS (Paket E, Arbeitsvorrat)` | offen ÷ Mittel | **Schätzung**, ausdrücklich als HYPOTHESIS markiert — sie gilt nur, solange die Rate gleich bleibt |
| `HYPOTHESIS (C gesamt, ABGELEITET)` | Planungsdokument mit der Zeile `OFFEN: <K> Koepfe / <I> Insn` (z. B. B196 §6.1, Quelle `analysis/_m196/_plan_c.txt`) | `<K> - (R207 heute - Bau-Liste damals)`; die Insn über den damaligen **Insn-je-Kopf-Schnitt** fortgeschrieben (deshalb „~" und „Schaetzung") |
| `-> ca. M Batches` | offen ÷ Mittel | **Schätzung** — dieselbe Rate wie oben |

Die **zwei** Hochrechnungen stehen seit R13t getrennt: die Paket-E-Zeile beschreibt nur den
C-**Arbeitsvorrat**, die C-gesamt-Zeile den ganzen C-Strang. Sie ist **abgeleitet** und
nennt Quelle, Stand-Batch und Rechenweg in der Zeile selbst — die Insn-Zahl ist eine
Schätzung, weil die kanonischen Bilanzdateien keine Insn je Batch führen.

**Port-Relevanz (R13t, Punkt 4b).** Feste Zeile am Ende des Durchsatz-Blocks:

    Port-Relevanz: ausgefuehrt X | davon gebaut Y | davon verifiziert Z von X

Die drei Mengen sind **gemessen** (nicht geschätzt) von `tools/r13t_cov_relevanz.py`:

| Menge | Quelle |
|---|---|
| ausgefuehrt | `capture/ppc_coverage.bin` + `ppc_cov_boot.bin` (SSCOV1-Maps), **Rumpf-Fenster** = Eintritt bis erstes `blr`, max. 0x400 B, gegen die 2072 Funktionen aus `analysis/_m60_funcs.json` |
| gebaut | `scripts/m104_built.py` → `built_map()` (der Projektbegriff „gebaut") |
| verifiziert | `scripts/c_kopf.py` → `KOPF_DEF` (registrierte C-Köpfe) |
| Paket E | Wurzeln und offene Blätter aus `analysis/_m<N>/_c_paket_e.txt` |

Das Werkzeug schreibt die Zahl als Cache nach `docs/_port_relevanz.json`; `/bilanz` liest
nur diese Datei (die Messung selbst dauert Sekunden). Fehlt sie, steht dort
„nicht gemessen" — geraten wird nicht. Nachmessen: `python tools/r13t_cov_relevanz.py`, Beleg `docs/_r13t_beleg_4b.txt`.

Warum die Insn nicht durchgängig da sind: die kanonische Bilanzdatei führt nur Köpfe
(nach dem Rumpf gemessen), und die Paket-E-Zeile gibt es erst in neueren Dokumenten.
Fehlt sie, steht das ausdrücklich da, statt eine Zahl zu erfinden.

Dieselbe Reihe (plus PLAN-Spalte und Laufzeit/Abbruchgrund) steht als **PLAN/IST-Tafel**
im Review-Prompt: der Reviewer sieht dort je Batch, was die Instruktion an Köpfen
genannt hat (`runs/b<N>/auftrag.md`, Abschnitt `TEIL 3`: genannte Kopfadressen und die
Insn in Klammern), was tatsächlich verifiziert wurde, wie lange der Batch lief und
warum er endete. Dazu gilt im Reviewer-Prompt die **Median-Regel**: das Ziel des
nächsten Batches darf höchstens ca. das **1,3-fache des Medians** der letzten Batches
sein — Abweichungen begründet der Reviewer in einem Satz.

### 14d. `/ds`-Nachrichten im Review (R13t)

Schickst du mit `/ds` eine Nachricht an den Worker, hängt der Harness sie an den Auftrag
des nächsten Batches (`harness/runs/b<N>/auftrag.md`, Kopfzeile
`NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):`). Genau diesen Block liest
der Review desselben Batches wieder ein und zeigt ihn im Prompt als

    === NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES (/ds) ===

mit der Regel, ob der Worker sie umgesetzt hat und was offen blieb. Quelle ist der
Auftrag (nicht die Queue: die Nachricht ist zu diesem Zeitpunkt schon nach
`harness/inbox/done/` archiviert). War keine Nachricht dabei, steht dort `(keine)`.
Beleg mit echtem Prompt-Ausschnitt: `docs/_r13t_beleg_4_prompt.txt`
(`python tools/r13t_prompt_probe.py`).


---

## 15. Denkblöcke mitlesen (`/thinking`, R13r)

`/thinking` zeigt die **letzten 10 Denkblöcke** des DeepSeek-Workers — je **200 Zeichen**
(wie in `watch`), mit Uhrzeit und Länge:

```
DENKEN b196 - letzte 10 Denkbloecke (je 200 Zeichen)
laeuft seit 12m34s | 184 Anfragen, $0.2747
 1. 14:17:13 (607 Z.) The anchor's Stand block still says BATCH 195 ? I must update … [+407 Zeichen]
 2. 14:17:27 (3068 Z.) The anchor has 5 lines (Stand/Fertig/Naechster Schritt/…) … [+2868 Zeichen]
juengster Eintrag: vor 3 min
Mitschnitt: g:\Harness\harness\runs\b196\stream.jsonl (28 MB, gelesen 3,5 MB)
Mehr: /thinking 20   Ungekuerzt: /thinking 10 voll
```

- **`/thinking 20`** — mehr Einträge (höchstens 50). **`/thinking 10 voll`** — dieselben
  Einträge **ungekürzt** (dann mehrere Telegram-Nachrichten). Ein unbekanntes Wort führt
  zur Nutzungshilfe, nicht zu einer stillen anderen Bedeutung.
- **Live:** läuft ein Batch, wird **dessen** Mitschnitt gelesen — der Pfad steht im
  Zustand (`worker.log`), es wird also mitgelesen, während DeepSeek arbeitet. Ist kein
  Batch aktiv, kommt der neueste abgeschlossene Batch.
- **Quelle** ist `runs/b<N>/stream.jsonl`, Zeile `{"type":"assistant", "message":
  {"content":[{"type":"thinking","thinking":"…"}]}}`. Blöcke **ohne Text** (nur
  `signature`) und `redacted_thinking` zählen nicht — dann steht dort ausdrücklich
  „kein Denkblock MIT TEXT gefunden".
- **Warum nur 200 Zeichen und warum ein Suchdeckel:** der Mitschnitt ist bis zu **28–32 MB**
  groß, und der Befehl läuft im **TaktThread** des Harness. Deshalb liest ein Tail-Leser
  **rückwärts** vom Dateiende in 256-KB-Blöcken, bis die N Einträge da sind — gemessen
  **0,3 s** bei 28 MB (gelesen 1,5–3,5 MB). Findet er innerhalb der letzten **16 MB**
  nichts, sagt er das ausdrücklich; der Deckel ist fest (kein Konfigurationsschlüssel).
- **Unterschied zu `watch`:** `watch` zeigt volle Denkblöcke farbig im Fenster und
  scrollt mit; `/thinking` ist für unterwegs — gekürzt, auf Telegram, jederzeit abrufbar.
- Auf der Konsole: `python -m hx.cli thinking --n 20 --batch 196 --voll` (dieselbe
  Ausgabe; ohne `--batch` der neueste Batch, `env-proof` und `ghidra-smoke` zählen nicht
  als Batch). Zeichen, die die Windows-Konsole nicht kennt (`✓`, `—`), werden dort durch
  `?` ersetzt — in Telegram kommen sie korrekt an.

---

## 16. Offene Fragen an dich (`/fragen`, R13s)

`/fragen` (Telegram) und `python -m hx.cli fragen` zeigen, was gerade **an dir** offen
ist — je Frage als **eine entscheidbare Zeile**:

```
FRAGEN AN DICH (Anker: BATCH 206)

NAECHSTER SCHRITT
  (a) R535 (NEU, GEMESSEN, OFFEN): addc addiert das EINGEHENDE CA NICHT - eine Probe ...

OFFENE FRAGEN AN DICH
  (5) soll prof je Kopf MEHRERE MEM-Varianten fahren?
      Empfehlung: ja | bei ja: - / bei nein: -
  (6) UNKLAR FORMULIERT: offen bleiben: R330, M60_NO_EVID, NEG_IMM_LO, ...
  (4 Posten hat der Reviewer selbst geschlossen - Veto per /claude)

AUS DEM LETZTEN REVIEW
  Entschieden (Reviewer, Widerspruch per /claude): ...
  Wartet auf Live-Aufnahme: 0x40B/0x40E/0x40F
```

Quellen (alle nur lesend): der Ankerkopf (`**Naechster Schritt:**`,
`**Offene Entscheidung:**`), das letzte Review (`runs/b<N>/review.md`, ausgewertet mit
`protocol.parse_offene_punkte`) und ein offenes Gate.

**Wie eine Frage „entscheidbar" wird:** Der Harness zerlegt die Ankerzeile in ihre
`(n) …`-Posten und sucht darin drei Teile — eine **Ja/Nein-Frage** (Satz, der mit
`soll/ist/bleibt/wird/kann/darf/muss/gibt` beginnt und mit `?` endet), eine
**Empfehlung** (`Vorschlag:` / `Empfehlung:`) und die **Folgen** (`bei ja:` / `bei nein:`).
Fehlt einer der Teile, steht der Posten als **`UNKLAR FORMULIERT`** mit dem
Originaltext — nichts wird umgedeutet (Nutzerentscheid 2026-09-28). Die Folgen stehen
als `-`, wenn sie in der Prosa nicht genannt sind; der Harness erfindet sie nicht.

**Antworten** laufen über die gewohnten Wege: `/ds <Text>` schickt die Antwort als
Nutzer-Nachricht in den nächsten Batch (dort wird sie als „vom Nutzer" ausgewiesen),
`/claude <Text>` geht an den Reviewer. Posten, die der Reviewer selbst entschieden hat,
brauchen keine Antwort — sie stehen nur zur Information da (Widerspruch per `/claude`).
