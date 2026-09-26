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
| `pause` | pausieren; ein laufender Batch läuft zu Ende, danach startet nichts Neues |
| `resume` | fortsetzen (`--accept-dirty`, wenn ein unsauberer Arbeitsbaum bewusst akzeptiert wird) |
| `stop` | laufenden Batch abbrechen: WIP wird gesichert (Status + Patch + Stash); danach **beendet sich der Harness** |
| `approve [--text "…"]` | wartenden Batch freigeben; optionaler Text geht als ds-Nachricht mit |
| `number <N>` | Batch-Nummer des **offenen** Auftrags setzen (z. B. wenn der Reviewer eine andere nennt) |
| `send ds "Text"` / `send ds --file auftrag.md` | Nachricht an den **Worker** in die Queue (Zustellung am nächsten Batch-Übergang) |
| `send claude "Text"` / `send claude --file ziele.md` | Nachricht an den **Reviewer** in die Queue (Zustellung am nächsten Review) |
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

`/status` · `/budget` · `/pause` · `/resume [ok]` · `/stop` · `/approve [Text]` ·
`/number <N>` · `/autonom [on|off]` · `/ds <Text>` · `/claude <Text>` · `/review` ·
`/last [ds|claude] [n]` · `/queue` · `/why` · `/help`

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
| `OFFENE FRAGE: …` | nur zur Information (z. B. die Audio-Frage in B159), die Arbeit geht an anderem weiter | bremst **nicht** |
| `WARTET AUF LIVE-AUFNAHME: …` | es fehlt Material, das nur du liefern kannst | bremst **nicht** |

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

**Queue erst nach gültigem Review.** `/claude`-Nachrichten gelten erst als zugestellt, wenn
der Review einen gültigen Protokollblock geliefert hat — sonst bleiben sie unverändert in
`inbox/claude` (und werden beim nächsten Review wieder mitgeschickt).
