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
| `rotate` | **Reviewer-Session beim naechsten Review wechseln** (R13ab). Der Harness merkt sich den Hash von `prompts/reviewer.md` in dem Moment, in dem die Session angelegt wurde, und rotiert **selbst**, wenn sich die Datei geaendert hat - der Befehl ist fuer den Fall, dass ohne Prompt-Aenderung gewechselt werden soll (Details §9b) |
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
`/ask-neu <Frage>` · `/meta` ·
`/review` · `/last [ds|claude] [n]` · `/queue` · `/why` · `/help`

`/ask` ist **kein** Eingriff in den Betrieb: es ist ein eigener, rein lesender Lauf
(Decomp-Repo **und** der ganze Harness-Ordner samt `docs\`-Belegen) im **eigenen Thread** —
der laufende Batch merkt nichts davon. Gesperrt sind `secrets`, `backups` und jede
`.credentials.json` (nachgewiesen: `docs\_ask_zugriff_beleg.txt`). Antworten sind lang und
werden automatisch aufgeteilt; unter der Antwort steht die Zeile mit Modell, Anfragen,
**Token-Zahlen** (statt Dollar — der Lauf geht über das Abo), Chat und Dauer.

**`/autonom on|off` ist dauerhaft (R13v3, gemessen):** der Befehl schreibt den Wert
sofort in `state/run.json` (`orchestrator.handle_command`); beim Start werden fehlende
Felder nur aus den Vorgaben ergänzt, gespeicherte Werte bleiben. Weder `/stop` noch ein
Neustart fassen das Feld an — nur `/autonom` selbst (und die Attrappe `hx.cli demo`, die
in einen eigenen Zustand schreibt) ändert es. Eine fehlende Zustandsdatei bedeutet **AUS**
(so war es auch hier: `state/run.json` steht auf `false`). Beleg:
`docs\_r13v3_beleg_zustand.txt`, Tests `tests/test_r13v3_fixes.TestAutonomHaelt`.

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

### 9b. Wie `prompts/reviewer.md` beim Reviewer ankommt (R13ab, gemessen 2026-09-28)

**Der Befund, der die Prüfung ausgelöst hat:** die Pflichtzeile `B-SCHRITT:` fehlte in den
Reviews B209/B210, obwohl die Regel seit R13w in `prompts/reviewer.md` steht. Zwei Messungen
erklären das:

**1. Der gesendete Prompt enthält die Rollenanweisung NICHT.** Was der Harness je Review
mitschreibt, ist der **Nutzer-Prompt** (`logs/review-prompt-<ts>.md`: Messdaten, Diff,
Historie, PLAN/IST, Anker, Snapshot). Die Rollenanweisung geht als
`--append-system-prompt-file prompts/reviewer.md` daneben (`hx/reviewer.py:96-98`, ebenso
`ask.py`/`aussensicht.py`/`worker.py`). Am echten Beleg: im Prompt der Reviews B209
(`logs/review-prompt-2026-09-28T172525+0000.md`) und B210 (`…T181337+0000.md`) kommt das
Wort `B-SCHRITT` nur **zitiert** vor (Commit-Betreffe, Ankerzeilen); die Regel selbst steht
in `prompts/reviewer.md:275/287/290`.

**2. Bei `--resume` liest die CLI die Datei NICHT neu.** Gemessen mit zwei Mini-Aufrufen
(`tools/r13ab_probe_systemprompt.py`, Beleg `docs/_r13ab_probe.txt`): neue Session mit
`MARKER: PROBE-A` → Antwort `PROBE-A`; danach dieselbe Session per `--resume`, Datei auf
`MARKER: PROBE-B` geändert → Antwort **weiterhin `PROBE-A`**. Der Harness hängt die Datei
zwar bei jedem Aufruf an (auch beim Fortsetzen), sie kommt aber nicht an.

Die laufende Reviewer-Session war älter als die Regel: Session angelegt **2026-09-27
22:02:56Z**, die Regel kam mit **R13w am 2026-09-28 16:32:52Z**. Sie hat sie nie gesehen —
der Reviewer hat sie also nicht ignoriert; er konnte sie nicht kennen.

**Was der Harness jetzt tut.** `reviewer.prompt_hash` bildet einen Hash von
`prompts/reviewer.md`; `state.reviewer_new_session` speichert den Hash der Fassung, mit der
die Session **angelegt** wurde. `orchestrator.do_review` vergleicht ihn vor jedem Review und
**rotiert bei Abweichung** (neue Session mit Übergabe, `Sessions-Wechsel`-Grund im Log und
in Telegram). Eine Session aus einer älteren Fassung hat noch keinen Hash — sie rotiert
**einmal**, danach ist der Zustand vollständig. Manuell geht es mit `hx.cli rotate`
(bzw. `state/ctl/rotate`), was `reviewer.force_rotate` setzt.

> Für `prompts/ask.md` und `prompts/aussensicht.md` gilt derselbe Mechanismus nicht: die
> Aussensicht startet **immer** eine frische Session (R13w), und `/ask` beginnt bei
> `--neu`/abgelaufener Chatgrenze neu. Betroffen ist nur die langlebige Reviewer-Session.

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

**Queue erst nach gültigem Review — und `/claude` erst mit der FREIGABE (R13u).**
`/claude`-Nachrichten gelten erst als zugestellt, wenn
1. der Review einen gültigen Protokollblock geliefert hat **und**
2. das daraus entstandene Gate **freigegeben** ist (der Worker also wirklich startet).
Bis dahin bleiben sie unverändert in `inbox/claude` und werden beim nächsten Review wieder
mitgeschickt. Die Nachrichten-IDs reisen dafür im Gate (`claude_queue_ids`); erst der
Worker-Start verbucht sie als zugestellt und legt sie nach `inbox/done/`.

**Warum (gemessen):** bis R13u buchte der Harness sie schon nach dem gültigen Review als
zugestellt (`orchestrator.py` R13b-Fassung). Ein `/review` verwirft aber den ganzen Auftrag
(`discard_gate`) — die Nachricht lag dann bereits in `done/` und wurde nie wieder gelesen:
deine Anweisung war weg, ohne dass sie je eine freigegebene Instruktion erreicht hätte.
Jetzt gilt: ein verworfenes Gate lässt die Nachricht liegen (nichts wird zurückbewegt, also
auch nichts doppelt). Scheitert der Review zweimal, bleibt sie ohnehin liegen.

**`/ds` (an den Worker)** wird beim **Worker-Start** zugestellt und archiviert (nicht erst
am Batch-Ende). Ein verworfenes Gate lässt sie ebenfalls liegen — sie wird ja erst beim
Start gelesen. Erst nach dem Start ist sie in `done/`, auch wenn der Batch danach
scheitert (gewollt: der Worker hat den Text gesehen).

### 10d. `## VERALLGEMEINERUNG` — Pflichtabschnitt im Review (R13z, 2026-09-28)

Jeder Review trägt **zwischen** `<DS_TOOLS>` und `<DS_INSTRUCTION>` einen Abschnitt, der
mit `## VERALLGEMEINERUNG` beginnt (`prompts/reviewer.md`). Er gehört ins **`review.md`**
(der nächste Reviewer liest ihn dort) und **nicht** in die `<TELEGRAM_SUMMARY>` — die
bleibt bei ca. 1500 Zeichen. Je Befund dieses Reviews beantwortet er drei Fragen:

| | Frage |
|---|---|
| (a) | **Welche Fehlerklasse** steckt dahinter (Ursache, nicht der Einzelfall)? |
| (b) | **Welche verwandten Fälle** haben dieselbe Ursache, und **wie prüft die Instruktion sie mit** (Werkzeug, Menge, Sollwert)? |
| (c) | **Was prüft die Instruktion ausdrücklich NICHT** — welche Lücke bleibt offen (und bis wann)? |

Beispiel für (b): F1 (`slw` mit vertauschten Feldern) → **alle Formen mit `rS` in Feld
6–10 und `rA` in Feld 11–15**; die Instruktion lässt den Formenprüfer genau diese Menge
zählen und je Form eine ROT gewordene Rotprobe vorlegen.

Der Abschnitt ist **kein Bewertungstext**, sondern die Brücke von einem gefundenen Fehler
zur Prüfung seiner **Klasse**: ein Befund, den die Instruktion nur für den Einzelfall
behebt, kommt im nächsten Batch als derselbe Fehler wieder. Der Harness wertet den
Abschnitt **nicht** maschinell aus (er ist Prosa im `review.md`, die Blockprüfung
`review_ok` bleibt unberührt) — die Pflicht steht im Reviewer-Prompt, nicht im Parser.
Schreibst du „nichts zu verallgemeinern", dann mit Begründung (z. B. „Einmal-Sache:
fehlende Zahl in einer Belegzeile").

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
* **Worker-Vorspann, Abschnitt „RECHENZEIT"** (R13h; **R13v hat ihn ersetzt**, s. 12c):
  unabhängige Rechenläufe **parallel** (4 Kerne) statt nacheinander.

### 12c. Warteschleifen: technisch verhindert, nicht nur verboten (R13v, 2026-09-28)

Gemessen in B207 (`runs/b207/stream.jsonl`, Beleg `docs/_r13v_beleg_b207.txt`): das
Werkzeug kappte einen Lauf bei **600 s** und schob ihn in den **Hintergrund**
(`stream.jsonl:76897` — *„Command did not complete within its 600s timeout and was moved
to the background"*). Der Worker wartete danach in **zwei Abfrageschleifen** auf PID 4996:
`stream.jsonl:76873` **601,9 s**, `stream.jsonl:77152` **481,8 s** — zusammen **1083,7 s**
von 2845 s Laufzeit (der Harness-Schätzwert lag bei 1390 s). In B174 waren es 1993 s.
Der Vorspann verbot das bis dahin nur in Prosa und empfahl sogar „kurze Schritte (10–20 s)"
— also genau das Muster.

Drei Ebenen ersetzen das Verbot:

| Ebene | Was | Wo |
|---|---|---|
| **Ursache weg** | Werkzeug-Zeitgrenze des Workers auf **600 000 ms als Standard** — ein 7–10-Minuten-Lauf läuft synchron in EINEM Aufruf, es gibt keinen Grund mehr, im Hintergrund zu starten | `hx/envs.py` (`BASH_DEFAULT_TIMEOUT_MS`, `BASH_MAX_TIMEOUT_MS`) |
| **Sperre** | `PowerShell(Start-Sleep*)` und `Bash(sleep *)` werden dem Werkzeug **verboten** | `hx/worker.py::build_command` (`--disallowedTools`) |
| **Wächter mit Eingriff** | Der Mitschnitt wird live geprüft: Abfrageschleife (`for`/`while`/`do` mit `Start-Sleep`/`Get-Process`), fester Schlaf ≥ 30 s, Schleife mit Prozessabfrage. Erster Fund = **Alarm** (Telegram + Bericht), ab **300 s** Wartezeit (einzeln oder summiert) **bricht der Lauf ab** mit Grund `warteschleife` | `hx/streamjson.py::warte_muster`/`warte_entscheidung`, `hx/worker.py::on_event` |

Der **erlaubte Weg** steht im Vorspann (Abschnitt „RECHENZEIT") und wird im Test
festgehalten: synchron mit `timeout` (bis 600 000 ms) für alles bis 10 Minuten, sonst
`Start-Process … -PassThru` + **EIN** `Wait-Process -Id $p.Id -Timeout 480`. `Wait-Process`
und `Start-Process -Wait` gelten als erlaubt, `Start-Sleep` nicht.
Die Zeile `- Laufzeit-Profil: …` nennt die Warteschleifen jetzt ausdrücklich
(`WARTESCHLEIFEN n Aufrufe / ~s geschätzt`), damit der Reviewer den nächsten Auftrag
darauf zuschneiden kann.

#### Nachgemessen mit echtem claude-Lauf (2026-09-28)

Die Sperre war nur behauptet — jetzt ist sie gemessen. Werkzeug
`tools/r13v_sperrprobe.py` fährt den **echten** `claude`-Prozess mit **genau** der
Kommandozeile des Workers (`hx.worker.build_command`, Profil `none`) und der Umgebung
des Workers; das Modell bekommt je Fall einen Befehl wörtlich zum Ausführen, bewertet
wird der Mitschnitt (nicht die Modellprosa). Beleg: `docs/_r13v_sperrprobe.txt`
(11 Fälle, gesamt ≈ 60 s Rechenzeit).

| Befehl | Sperrliste | Ergebnis |
|---|---|---|
| `Write-Output "hallo"` | wie im Batch | **ausgeführt** (das Werkzeug läuft also) |
| `Start-Sleep -Seconds 3` | wie im Batch | **blockiert** |
| `for ($i=0; $i -lt 40; $i++) { …; Start-Sleep -Seconds 20 }` | wie im Batch | **blockiert** |
| `if ($true) { Start-Sleep -Seconds 3 }` | wie im Batch | **blockiert** |
| `Write-Output "a"; Start-Sleep -Seconds 3` | wie im Batch | **blockiert** |
| `for (…) { …; sleep -Seconds 20 }` (PowerShell-Alias) | wie im Batch | **blockiert** |
| `Write-Output "Start-Sleep -Seconds 3"` (blosse Erwähnung) | wie im Batch | **ausgeführt** |
| `[Threading.Thread]::Sleep(2000)` | wie im Batch | **ausgeführt** (nicht gesperrt) |
| dieselbe Schleife | zusätzlich `PowerShell(*Start-Sleep*)` | blockiert (nicht nötig) |
| dieselbe Schleife | zusätzlich `PowerShell(for *)` | blockiert (nicht nötig) |

**Befund:** `PowerShell(Start-Sleep*)` ist **keine Präfix-Regel**. Der Werkzeugkasten
löst den Befehl in seine Bestandteile auf (alias-bewusst) und prüft jeden Teil — deshalb
wird auch die Schleife abgelehnt, obwohl sie mit `for (` beginnt. Eine blosse
Erwähnung im Text zählt nicht. Nicht gesperrt bleibt `[Threading.Thread]::Sleep(…)`;
dafür greift nur der Wächter — seit R13v2 wird auch diese Schreibweise **geschätzt**
(vorher 0 s ⇒ nur Alarm, kein Abbruch), siehe `hx/streamjson.py::warte_normalisiert`.

#### Notbremse: was danach im Arbeitsbaum liegt

`hx/proc.py::kill_tree` beendet mit `taskkill /PID <claude> /T /F` **den Baum** des
Worker-Prozesses. Messung mit der versionierten Sonde `tools/r13v_waise_probe.ps1`
(Beleg `docs/_r13v_waise.txt`, Herzschlag-Dateien statt Vermutungen):

| Fall | nach `taskkill /T /F` |
|---|---|
| Prozess **im Baum** (Kind des lebenden Werkzeug-Shells, V3) | **beendet** (Herzschlag steht) |
| Prozess **ohne Elternbezug** (per WMI `Win32_Process.Create` gestartet, V2/V4 = Muster „im Hintergrund weiterlaufen") | **läuft weiter** (Herzschlag frisch) |
| Kind eines Shells, das per `Start-Process` startete und dann **endete** (V1) | beendet — in dieser Sitzung, siehe Warnung unten |

Dass der Hintergrundlauf im echten Betrieb ebenfalls **ohne** Elternbezug weiterläuft,
ist an B207 ablesbar: PID 4996 wurde in Zeile `66903` gestartet und lebte **über 19
Minuten nach dem Ende des aufrufenden Werkzeugaufrufs** weiter (die Poll-Schleifen
brauchten 601,9 s und 481,8 s, bis er verschwand). Der Sandkasten und der echte Betrieb
weichen hier ab (V1 stirbt, B207 nicht) — **maßgeblich ist der belegte B207-Fall**: eine
verschwundene Startshell ist **kein** Beweis, dass der Lauf beendet ist.

Der Harness **räumt danach nichts
auf**: es gibt keinen Prozess-Scan und kein Nachfassen (die Muster-Prüfung in
`on_event`/`abbau_ursache` liest nur den Mitschnitt). Der nächste Batch kann also einen
fremden `python`-Lauf antreffen, der weiter in `analysis/…` schreibt — erkennbar an
`WARTESCHLEIFEN` / `GRENZE AUSGELOEST: warteschleife` im `result.json` des Vorgängers und
daran, dass Belegdateien weiter wachsen.

Weiter steht nach einem Abbruch:

* `runs/b<N>/stream.jsonl` (endet an der Abbruchstelle), `stream.err.txt`,
  `result.json` mit `"killed_reason": "warteschleife"`, `antwort.md` (ggf. leer),
  `harness-facts.md` mit der Zeile `WARTESCHLEIFEN …`;
* der Auftrag ist **verbraucht** (Gate gelöscht, `/claude`-Queue zugestellt — R13u);
  die Nummer des nächsten Reviews kommt **aus dem Ankerkopf des Decomp-Repos**
  (`expected_batch()` = Anker + 1, `orchestrator.py:1460`) — hat der Worker den Anker nicht
  mehr fortgeschrieben, ist das dieselbe Nummer `N`, sonst `N+1`. Ein abgebrochener Batch
  wird **nicht** automatisch wiederholt; der Reviewer entscheidet (typisch: Aufräum-Batch);
* der Batch geht den **normalen Weg weiter** — Push und Review (`orchestrator.py:2210`),
  keine automatische Rücknahme. Unfertige Änderungen des Workers bleiben im Arbeitsbaum;
  die Git-Vorprüfung des nächsten Batches verlangt **keinen sauberen Baum**
  (`orchestrator.py:996`), sie holt nur den Remote-Stand. Gesichert werden sie erst,
  wenn der **Harness** gestoppt wird (`wip_rescue`, `orchestrator.py:1126/2026/2281`).

### 12d. Aufräumen nach einem Abbruch (R13v3, 2026-09-28)

Der Abbruch selbst (`kill_tree` = `taskkill /PID <claude> /T /F`) beendet nur den Baum.
Seit R13v3 hängt am Worker-Lauf ein **Job-Objekt**; nach dem Lauf wird zusätzlich
**nachgesucht** und der **halbe Stand gesichert**. Alles gemessen, nicht behauptet:
`docs/_r13v3_beleg_aufraeumen.txt` (Sonde `tools/r13v3_aufraeumen_probe.py`,
Herzschlag-Dateien) und `docs/_r13v3_beleg_zustand.txt`.

| Ebene | Was | Wo | Gemessen |
|---|---|---|---|
| **Job-Objekt** | Der Worker-Prozess wird **sofort nach dem Start** in einen Job mit `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` aufgenommen; beim Schließen (Ende **jedes** Laufs, auch normal) beendet Windows alles darin | `hx/aufraeumen.py::Job`, `hx/proc.py::run_stream(job=)`, `hx/worker.py` | Kind stirbt mit dem Job — **auch** ein per `Start-Process` gestarteter Hintergrundlauf. **Die Reihenfolge ist tragend:** wird der Job erst zugewiesen, wenn das Kind schon existiert, erbt es ihn nicht (erster Messanlauf war genau deswegen wertlos) |
| **Nachsuche** | Prozessliste per WMI, dann genau benannte Arbeitsprozesse (python, g++, gcc, make, mingw32-make, cmake, ninja, ppc_poc, port_selftest, port_gl), die **jünger als der Batch-Start** sind und **belegt** zu diesem Lauf gehören: Wurzel in der Kommandozeile **oder** während des Laufs als Nachfahre gesehen **oder** direkter Nachfahre eines Lauf-Prozesses. Beendet wird gezielt (`Stop-Process -Id …`) | `hx/aufraeumen.py::nachsuche`/`kandidaten`, `hx/worker.py` | Waisen ohne Elternbezug (per WMI gestartet, Muster B207) werden gefunden; ein fremder Prozess außerhalb der Wurzel bleibt unangetastet |
| **PID-Nachweis** | Alle 60 s werden die **lebenden Nachfahren** des Workers aufgenommen (`nachfahren_pids`, Daemon-Thread, der Leser wartet nie). Nötig, weil ein Hintergrundlauf wie in B207 **keinen Pfad** nennt (`scripts/c_kopf.py`) und sein startendes Shell längst tot ist | `hx/worker.py` (`PID_AUFNAHME_S`) | ohne diesen Nachweis: 0 Treffer; mit Nachweis: gefunden und beendet |
| **R13i-Schutz** | Der eigene PID-Kreis (Harness + Vorfahren) und Prozesse mit `hx.cli`/`harness\hx`/`ghidra` in der Kommandozeile werden **nie** angefasst | `aufraeumen.vorfahren`, `NIE_ANFASSEN` | der Harness stand im Beleg unter „ausgenommen" |
| **Halber Stand** | Direkt nach dem Abbruch läuft `wip_rescue` (wie beim Stoppen): `git status` + `git diff HEAD` als Belegdateien nach `logs/` **und** `git stash push -m harness-wip-b<N>` mit Referenz | `orchestrator.wip_nach_abbruch`, `gitsafe.wip_rescue` | Meldung nennt Dateizahl + Stash-Referenz; scheitert die Sicherung, wird das **laut** gemeldet (nicht still) |
| **Meldung im Review** | Der nächste Review bekommt den Block „ABBRUCH DES BEWERTETEN LAUFS" mit Grund, Sicherung (`git stash apply <ref>`) und dem Hinweis, dass die Nummer **nicht** übersprungen wird | `orchestrator.abbruch_zeile/abbruch_block`, `reviewer.build_prompt` | Block steht im Prompt; Messdatenzeile `Letzter Abbruch (R13v3): …` |
| **Belege der Vor-Fassung** | Weil die Nummer aus dem Ankerkopf kommt, läuft der nächste Batch ggf. in **denselben** Ordner. Vorher werden `stream.jsonl`, `stream.err.txt`, `auftrag.md`, `result.json`, `antwort.md`, `harness-facts.md` nach `*-v1.*` umbenannt | `worker.sichere_vorgaenger` | `stream-v1.jsonl` bleibt neben dem neuen `stream.jsonl` stehen (Test) |

**Warum die Nummer gleich bleibt:** `expected_batch()` = **Ankerkopf + 1**
(`orchestrator.py:1460`) — es gibt bewusst keinen zweiten Zähler. Schreibt ein
abgebrochener Worker den Anker nicht fort, bekommt der nächste Lauf dieselbe Nummer;
das Review liegt wieder in `runs/b<N>`, die Belege des abgebrochenen Laufs liegen als
`*-v1.*` daneben. Gemessen am echten Anker: Kopf BATCH 207 → nächster Lauf 208, und
`state["batch"] = 999` ändert daran nichts (`docs/_r13v3_beleg_zustand.txt`).

### 12e. Aussensicht — der Meta-Review (R13w, 2026-09-28)

**Anderer Auftrag als der Reviewer.** Der Reviewer fragt „war dieser Batch gut?". Die
Aussensicht fragt: **„stimmen Messgrößen, Plan und Annahmen noch?"** Sie prüft bewusst
skeptisch: Messen die Kennzahlen, was sie behaupten? Stimmen Aussagen in `readme.md`,
`AGENTS.md` und Anker mit dem Code? Welche Probleme wiederholen sich? Ist der Plan beim
gemessenen Durchsatz realistisch? Was würde ein Aussenstehender bezweifeln? Wurden
frühere Aussensicht-Befunde umgesetzt?

**Sie entscheidet nichts und ändert nichts.** Ihre Werkzeuge sind `Read`, `Grep`, `Glob`
und die vier Nur-Lese-Git-Befehle; Schreiben, Bash, Ghidra und Netz sind verboten,
Schlüssel/`backups`/`.credentials.json` gesperrt. Sie läuft **immer in einer frischen
Session** (kein Verlauf) mit dem Reviewer-Modell über das Abo.

| Was | Wie |
|---|---|
| **Start** | `/meta` (Telegram, jederzeit) oder `python -m hx.cli meta [--grund …] [--mock]`; zusätzlich automatisch (s. u.) |
| **läuft gerade ein Worker** | `/meta` wird nur **vorgemerkt** (Antwort: „vorgemerkt, laeuft nach Batch N") und läuft **direkt nach dem Batch-Ende, VOR dem Review** — so stehen Befunde für den Reviewer schon in dessen Review. Mehrfaches Vormerken zählt **einmal**. In Pause/Gate/Leerlauf läuft sie sofort; während einer Pause lösen **Automatik**-Auslöser nicht aus |
| **Automatik** | (a) alle `[meta] every_batches` Batches (**seit R13z vorläufig 3** — Begründung unten; die **erste** Aussensicht löst du per `/meta` aus, damit der erste Start nicht sofort einen Lauf kostet), (b) Worker-Abbruch (`letzter_abbruch` aus R13v3), (c) Zeile `MEILENSTEIN ERREICHT:` bzw. `ABBRUCHKRITERIUM ERREICHT:` in der neuesten Review-Zusammenfassung, (d) **B-Schritt** über zwei B-Batches unverändert (Pflichtzeile `B-SCHRITT: <n>/5 …`), (e) eine **C-Kernzahl** über die letzten zwei **C-Batches** unverändert. Je Batch wird höchstens **einmal** entschieden. **Welcher Batch ein B-Batch ist**, liest der Harness aus mehreren Belegen (Pflichtzeile im Review, Marker im Auftrag `runs/b<N>/auftrag.md`, Zeile `Mischverhaeltnis …` in `analysis/hybrid-plan.md`) — vorher hing das allein an der Pflichtzeile, die seit B205 in jedem Review fehlte, und (e) hielt B208/B209 fälschlich für C-Batches (R13aa) |
| **Eingaben** | Bilanz-Trend der letzten 12 Batches, PLAN/IST-Tafel, die letzten 10 `TELEGRAM_SUMMARY`, Ankerkopf, Ziel-/Scope-Abschnitte aus `readme.md`/`AGENTS.md`, `/fragen`, Kosten/Laufzeiten je Batch, die noch offene `/ds`-Queue und die **Befundliste der letzten Aussensicht** |
| **Stichprobenpflicht** | (1) mindestens zwei Aussagen aus den Zusammenfassungen gegen die Rohbelege des Batches (`runs/b<N>/result.json`, `antwort.md`, `review.md`) prüfen, (2) für mindestens einen Batch die Denkblöcke `snapshots/b<N>/reasoning.jsonl` lesen **und (3) die TIEFENPROBE** (R13ac3, s. u.) — damit nicht dieselben aufbereiteten Zahlen die einzige Quelle sind. **Achtung:** `runs/b<N>/harness-facts.md` gehört zu Batch N−1 (siehe §14e) |
| **Ausgabe** | `<AUSSENSICHT>` (2–4 Zeilen, inkl. Stichprobenergebnisse) + je Befund `<BEFUND n gewicht empfaenger>Beleg/Aussage/Empfehlung</BEFUND>` + `<PRUEFUNG id status/>` zu früheren Befunden. **Höchstens 7** Befunde, sortiert nach Gewicht (`hoch`/`mittel`/`niedrig`), Empfänger `Reviewer` oder `Nutzer` |
| **Belegpflicht** | gültig ist `Datei:Zeile` **oder** eine Zahl mit Quelldatei **oder** `Eingabe <Abschnitt>` (ein Eingabeblock beim Namen genannt) **oder** ein Lauf-/Belegordner (`runs/b<N>`, `runs/b<N>/result.json`) **oder** `Fehlstelle: gesucht in <Ort>, nicht gefunden`. Nur Befunde **ganz ohne** Beleg werden verworfen — und im Bericht als verworfen **genannt** und unter `/fragen` als „verworfen — prüfen?" gezeigt (R13aa, s. u.) |
| **Verteilung** | Empfänger `Reviewer` → **eine `/claude`-Nachricht je Befund** in die Queue; Empfänger `Nutzer` → Telegram **und** unter `/fragen` |
| **Ablage** | Bericht `runs/meta-<batch>.md` (mit Rohantwort), Maschinenfassung `runs/meta-<batch>.json`, Mitschnitt `runs/meta-<batch>.jsonl`, Register `state/meta_befunde.json` |
| **Anzeige** | `/bilanz` zeigt die **Quote** des Registers: `Aussensicht: n Befunde, davon u uebernommen, a abgelehnt, o offen   (letzte Aussensicht: Batch N; k Befunde in diesem Lauf; Takt: alle 3 Batches)`; `/status` zeigt dieselbe Zeile (hinter dem Vorgemerkten) |
| **Grenzen** | harte Zeitgrenze `[meta] wall_s` (Vorgabe 900 s); schlägt der Lauf fehl, wird das gemeldet und der Betrieb läuft weiter. Die Aussensicht blockiert **ihren eigenen** Lauf (synchron wie der Review) |

**Tiefenprobe — ein zufälliger Batch je Lauf (R13ac3, 2026-09-29).** Zusätzlich zur
Stichprobe des neuesten Batches zieht der Harness **vor** jedem Lauf **einen** Batch aus den
letzten **zehn gelaufenen** (Ordner mit `runs/b<N>/result.json`) und nennt ihn im
Eingabeblock `=== TIEFENPROBE (Pflicht): BATCH <N> ===` samt seiner Rohbelege (Auftrag,
`antwort.md`, `result.json`, `snapshots/b<N>/reasoning.jsonl`, Mitschnitt). Geprüft wird
**in der Tiefe**: die Denkblöcke, die Belege und jede prüfbare Behauptung des
Abschlussberichts gegen die Rohdaten. Die Nummer steht im Bericht
(`- Tiefenprobe: Batch N aus dem Fenster B…B…`) — auch dann, wenn das Modell sie nicht
nennt; zusätzlich trägt `runs/meta-<batch>.json` den Schlüssel `tiefenprobe`.

**Rotation.** Die gezogenen Nummern stehen im Register (`state/meta_befunde.json` →
`tiefenprobe.gezogen`); **derselbe Batch kommt erst wieder, wenn alle anderen des Fensters
dran waren** — dann beginnt ein neuer Zyklus (im Bericht als „neuer Zyklus" benannt).
Fällt ein Batch aus dem Fenster (zehn Läufe später), zählt er nicht mehr zur Rotation.
Gemerkt wird die Ziehung erst, wenn der Lauf etwas geliefert hat — ein abgebrochener Lauf
verbrennt keinen Batch.

**Pflicht bei Funden aus älteren Batches.** Die Tiefenprobe greift in die Vergangenheit.
Jeder solche Fund wird gegen den **aktuellen** Stand geprüft (`git log -1`/`git show`,
Ankerkopf, heutige Belegdateien): gilt er **heute noch** oder kehrt er als Muster wieder,
wird er ein **Befund**; ist er **behoben**, steht er nur als eine Zeile in `<AUSSENSICHT>`:
`geprueft: <Fund>, behoben in B<N> (Beleg: <Datei:Zeile|Commit>)`. Die Befundliste soll
zeigen, was **jetzt** zu tun ist.

**Antwortpflicht des Reviewers (R13w).** Jede `/claude`-Nachricht trägt eine ID
`M<batch>-<n>`. Der Reviewer antwortet in der nächsten `TELEGRAM_SUMMARY` mit
`M208-3: übernommen (…)` oder `M208-3: abgelehnt, Grund …`. Der Harness übernimmt den
Status in das Register; **unbeantwortete Befunde bleiben „offen"** und werden in jedem
weiteren Review erneut vorgelegt (und in `/bilanz` gezählt). Ein „abgelehnt, Grund …" ist
eine vollwertige Antwort.

**Einstellungen** (`harness.toml`, Abschnitt `[meta]`): `every_batches`, `wall_s`,
`max_turns`, `max_befunde`, `summaries`, `bilanz_zeitfenster`.

**Takt auf 3 statt 10 (R13z, 2026-09-28 — vorläufig, Nutzerentscheidung).** Zwei Gründe:

1. Es läuft ein **neuer B-Strang** (Hybrid-Kern, Kontrollfluss). Dort kippen
   **Plan-Annahmen** schneller als in der C-Serienarbeit: ob „Maschine = Speicherkarte"
   trägt, ob der Kern die ISA trifft, ob der Plan-Zuschnitt noch stimmt — das sind
   Aussagen, die nach wenigen Batches schon falsch sein können. Der Meta-Review ist
   genau dafür da, und alle 10 Batches ist bei einem Drei-Batch-Vorsprung zu spät.
   Ausserdem melden die Aussensicht-Auslöser (b)–(e) neben dem Takt weiter: die 3 ist ein
   **Grundtakt**, kein Ersatz für die anderen Auslöser.
2. Der Takt kostet Abo-Kontingent (ein Opus-Lauf je Aussensicht). Deshalb ist 3 nicht
   endgültig: **nach einer Woche** wird anhand der **Quote** im Register
   `state/meta_befunde.json` entschieden, ob es so bleibt. Gelesen wird sie in
   `/bilanz`/`/status`:

   ```
   Aussensicht: 7 Befunde, davon 4 uebernommen, 1 abgelehnt, 2 offen   (letzte Aussensicht: Batch 208; 7 Befunde in diesem Lauf; Takt: alle 3 Batches)
   ```

   Gelesen wird die **Übernahmequote** (`uebernommen ÷ Befunde`):

   | Quote | Was das heißt | Folge |
   |---|---|---|
   | über ~⅓ | die kurzen Abstände finden echte, umsetzbare Punkte | Takt bleibt bei 3 (oder noch kürzer, wenn ein Batch-Zuschnitt es verlangt) |
   | darunter, meist `abgelehnt` | die Befunde zielen am Betrieb vorbei | Takt zurück auf 10 und im nächsten Review klären, warum |
   | viele `offen` | der **Reviewer** antwortet nicht (die Quote misst auch ihn) | Takt unverändert; die unbeantworteten Befunde kommen als `/claude`-Nachricht wieder |

   Gezählt wird **je Kennung**: ein geteilter Befund (`M208-5a` Nutzer / `M208-5b`
   Reviewer, §16a) zählt zweimal, weil beide Teile einzeln beantwortet werden. Spiegelt
   das Register ein Verdikt, steht das Wort **so** darin, wie der Reviewer es geschrieben
   hat (`uebernommen`, `abgelehnt`, `erledigt`, `verworfen`). In der Quote zählt
   `beantwortet` (das Wort aus R13w, steht noch in älteren Einträgen) und `erledigt`
   (die Aussensicht hat selbst nachgeprüft) als **übernommen**, `verworfen` als
   **abgelehnt**; alles Unbekannte gilt weiter als **offen**. Ein falsch geschriebener
   Status lässt einen Befund also nicht stillschweigend verschwinden.

### 12f. Strang-Klassifikation, verworfene Befunde, getrennte Hochrechnung (R13aa, 2026-09-28)

Nachbesserung aus `runs/meta-209.md` (drei Punkte):

**1. Welcher Batch ist ein B-Batch?** Der Auslöser „Kernzahl ohne Bewegung" hatte B208/B209
als **C-Batches** gezählt — beide waren B-Batches, die C-Zahl durfte sich also gar nicht
bewegen. Ursache: die Klassifikation hing allein an der Pflichtzeile `B-SCHRITT:` des
Reviewers, und die fehlte in **jedem** Review seit B205. Jetzt liest
`stand.strang_von_batch` mehrere Belege, in dieser Reihenfolge:

| Quelle | Beispiel (echter Beleg) |
|---|---|
| **Pflichtzeile der Instruktion** (R13ac2, 2026-09-29) | `STRANG: B (B-Batch 4 …). SOLL-KOEPFE: 0.` (`runs/b212/review.md:51`) bzw. `SOLL-KOEPFE: 0 (Strang B, B-Batch 3 …)` (`runs/b211/auftrag.md:97`) |
| Pflichtzeile im Review dieses Batches | `B-SCHRITT: 2/5 Maschine, B-Batch 2 von max 20` bzw. `B-SCHRITT: kein B-Batch (Strang C)` |
| Marker im **Auftrag** des Batches, der ihn nennt | `runs/b208/auftrag.md`: „B208 ist der ERSTE Batch von Strang B"; `runs/b209/auftrag.md`: Zeile „Strang B, Batch 2 von hoechstens 20" |
| Zeile `Mischverhaeltnis …` in `analysis/hybrid-plan.md` | „Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer): **B208 B, B209 B, B210 C**" |

**R13ac2 (2026-09-29): die Pflichtzeilen sind die ERSTE Quelle.** Gemessen: B211 trug nur
`SOLL-KOEPFE: 0 (Strang B, …)` — keine Quelle griff, der Batch galt als **C-Batch** und
löste eine Aussensicht aus (`runs/meta-211.md`). Gelesen werden jetzt zuerst `STRANG: B|C`
und `SOLL-KOEPFE: <n> (Strang B, …)` aus der Instruktion, die den Batch bestellt hat:
`runs/b<N>/auftrag.md` (Auftrag, wie gesendet) — und solange der Batch am Gate steht,
`runs/b<N>/review.md` (der Review, der ihn bestellt; `runs/b212/review.md:51`).
Durchsucht wird nur der Auftrags-/Instruktionsteil, nicht die Prosa des Reviews — dort
stehen fremde Batches.

Sagt keine Quelle etwas, bleibt der Batch **unbekannt** und zählt wie bisher als C-Batch
(die vorsichtige Seite — geraten wird nichts). Fremde Erwähnungen zählen nicht: der
B209-Auftrag nennt „B210 = C-Batch", das macht B209 nicht zum C-Batch.

**Fehlt die Pflichtzeile in einem B-Batch, wird gewarnt.** Der Block
`=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===` steht im nächsten Review-Prompt
(`reviewer.build_prompt`), und beim Review wird es ins Protokoll geschrieben
(`orchestrator.pflichtzeile_melden`: B-Batch → Warnung, C-Batch → Hinweis, unbekannt →
Info). Gemessen: `stand.ohne_pflichtzeile` findet B208 und B209.

**2. Verworfene Befunde werden nicht weggeworfen.** `beleg_gueltig` nimmt jetzt auch
`Eingabe <Abschnitt>`, `=== <EINGABEBLOCK> ===` und Lauf-/Belegordner (`runs/b209`,
`runs/b209/result.json`) an — M209-4 (Laufzeiten je Batch, Beleg `runs/b206`) war an der
alten Regel gescheitert. Was trotzdem durchfällt, wird mit eigener Kennung
(`M209-v1`) im Register gespeichert (`state/meta_befunde.json`, zweiter Schlüssel
`verworfen`) und in `/fragen` als **`AUSSENSICHT (verworfen - pruefen?)`** gezeigt —
mit dem nicht anerkannten Beleg und dem Verweis auf die Rohantwort in
`runs/meta-209.md`. Die Quote (§12e) zählt diese Befunde **nicht** mit. Antworten geht wie
bei jeder Kennung: `/claude M209-v1 pruefen` — der Anhang trägt den Wortlaut mit.

**3. Die Hochrechnung ist getrennt.** `/bilanz` nennt jetzt (a) das gemischte Mittel
**gekennzeichnet** als „B+C gemischt", (b) den Durchsatz **je C-Batch**, (c) die
**Mischung** (gemessener C-Anteil im Fenster *und* die Regel aus `hybrid-plan.md`) und
(d) daraus **zwei** Hochrechnungszeilen: `-> x C-Batches` und
`-> ca. y KALENDER-Batches`. Am echten Stand (2026-09-28): +4,8 Köpfe je C-Batch, Anteil
33 % (Regel 2 B : 1 C) → 295 C-Batches → ca. **886** Kalender-Batches für den ganzen
C-Strang (vorher stand dort „ca. 369 Batches" aus +3,8 gemischt).

### 12g. Kernzahl-Auslöser: entprellt, SOLL-bewusst, nur „C Koepfe" (2026-09-29)

Der Grund „Kernzahl ohne Bewegung über die letzten C-Batches" steuerte drei Läufe
(`runs/meta-209.md`, `meta-210.md`, `meta-211.md`) und führte in **jedem** Anlass
`C Abweichungen = 0` mit — eine Kennzahl mit Zielwert 0, die zwangsläufig stillsteht.
Nachbesserungen (Nachtrag zu Commit `01180db`):

| Punkt | Vorher | Jetzt |
|---|---|---|
| **Kriterium** | `C Koepfe`, `C Faelle`, Paket E, Bau-Liste, Inventar, C-Vorrat (ODER) | **nur `C Koepfe`** (Ist-Delta 0 bei `SOLL-KOEPFE > 0`, `KERNZAHL_KRITERIUM`); `C Faelle` steht nur als **Information** im Anlass-Text (`kernzahl_info_text`) |
| **`C Abweichungen`** | Teil der verglichenen Kernzahlen | **entfernt** — der Zielwert ist 0, die Zahl steht immer still |
| **Entprellung Stillstand** | feuerte bei jedem Batch, solange das C-Paar stillstand | Marke `kernzahl_gemeldet_bis` in `state.data["meta"]` = Nummer des neuesten **gemeldeten** C-Batches; es feuert nur, wenn `neuester_C > Marke`. **Nicht** die Variante `neu.batch > letzter_lauf_batch` |
| **Entprellung Serie** | `c_soll_null_serie` feuerte bei jedem Batch der Serie | Marke `c_soll_null_gemeldet_bis` = neuester C-Batch der gemeldeten Serie; erneut nur, wenn ein **neuer** C-Batch die Serie verlängert oder eine neue Serie entsteht |
| **SOLL-bewusst** | ein C-Batch ohne Bau-Auftrag konnte einen Stillstand melden | Stillstand nur bei `SOLL-KOEPFE > 0` in `runs/b<N>/auftrag.md`; drei C-Batches in Folge mit `SOLL-KOEPFE: 0` sind der **eigene Grund** `c_soll_null_serie` |

Beide Marken setzt **nur** ein erfolgreicher Lauf (`rc=0`), an dem der jeweilige Grund
beteiligt war — nicht schon beim Auslösen (`orchestrator._do_aussensicht`). Fehlt
`kernzahl_gemeldet_bis` (ältere Zustände), gilt einmalig **210**: der Stillstand B207/B210
ist in `runs/meta-212.md` gemeldet und darf nicht erneut feuern. `c_soll_null_gemeldet_bis`
startet bei **0**: nach der Regel „fehlende `SOLL-KOEPFE`-Zeile = SOLL > 0" bilden
B207/B210/B213 **keine** SOLL-0-Serie. Gemessen: B207 (`runs/b207/auftrag.md` hat keine
`SOLL-KOEPFE`-Zeile, Prosa „Dieser Batch baut KEINE neuen Koepfe"), B210 (keine Zeile,
Prosa „keine neuen Koepfe"), B213 (`runs/b213/review.md:59` `SOLL-KOEPFE: 0`; der Auftrag
entsteht erst beim Start). Die Serie `[207, 210, 213]` = `(None, None, 0)` feuert also
**nicht** — eine Migration war nicht nötig. Fehlt die Zeile, wird geloggt und der Batch als
`SOLL > 0` behandelt (kein Stillstand verschluckt, nichts geraten).

### 12h. Batch-Zeitbudget, Kontext, Fortsetzung (R13ad, 2026-09-29)

**Eine Zeitquelle.** Der Reviewer schrieb bis B212 eigene Minutenzahlen in die Aufträge
(„Budget 80 min", „ab 70 min") — die standen in keiner Config und widersprachen der
Batch-Uhr (90 min). Jetzt gilt: `alarm_wall_s = 5400` (90 min) bleibt, neu ist
`umschalt_vor_alarm_s = 600` → **Umschaltschwelle 80 min**. Der Reviewer nennt **keine
eigene Zahl** mehr, sondern formuliert relativ („ab der Umschaltschwelle laut Batch-Uhr").
Die BATCH-UHR-Zeile (Hook nach jedem Werkzeugaufruf) zeigt jetzt
`… min von 90 min (Umschalten ab 80) | Kontext 310k von 1M`.

**Kontext.** Die Kontextgroesse einer Anfrage ist `input_tokens + cache_read_input_tokens +
cache_creation_input_tokens`. Sie steht in `runs/b<N>/result.json` als
`kontext_letzte_anfrage`, `kontext_max` und `kontext_verlauf` (jede 25. Anfrage, die letzte
immer dabei), ferner im Live-Zustand (`state/run.json → live.kontext`) und in den
Review-Fakten. Rückblick B205–B212: 222k–391k am Laufende, **keine** Kompaktierung
(`compact_boundary` kam nie vor) — die Tabelle steht in `docs/_r13ad_belege.md`.

**Fortsetzung.** Hört ein Lauf regulär (und früh) auf, prüft der Harness
`worker.fortsetzung_pruefen` — nur wenn **alle** Bedingungen gelten, wird derselbe Chat
mit `--resume <session-id>` fortgesetzt:

| Bedingung | Wert |
|---|---|
| regulaeres Ende | letzte Antwort **ohne** Werkzeugaufruf, `killed_reason` leer, rc 0 |
| Batch-Uhr | **vor** der Umschaltschwelle (80 min) |
| Kontext | `kontext_letzte_anfrage < kontext_schwelle` (Vorgabe 550000) |
| Auftrag | Abschnitt `## NACHRUECKLISTE` vorhanden |
| Anzahl | weniger als `max_fortsetzungen` (Vorgabe 2) |

Antwortet der Worker `NACHRUECKLISTE ERLEDIGT`, ist Schluss. Zeit, Anfragen (1000) und
Kosten ($2) gelten **kumuliert** über alle Teilläufe; die harte Wanduhr wird je Teillauf um
die verbrauchte Zeit gekürzt. Die Fortsetzung hängt ihren Mitschnitt an `stream.jsonl` an
(`stream-forts<N>.jsonl` bleibt als Rohbeleg liegen), damit `watch`, `rebuild` und der
reasoning-Snapshot unverändert funktionieren. In `result.json` steht `fortsetzungen`
(`[{minute, kontext, antwort_kurz}, …]`), in den Review-Fakten eine Zeile daraus.

**Pflichtabschnitt des Reviewers.** Jede `DS_INSTRUCTION` endet mit `## NACHRUECKLISTE`
(nummerierte offene Posten mit prüfbarem FERTIG WENN). Ohne ihn gibt es keinen Anstoss —
vor R13ad fand sich der Abschnitt in **keinem** Auftrag. Bei einem Batch **mit** Fortsetzung
gilt der **letzte** `preflight`-Lauf als der eine gültige; frühere sind überholt und **kein**
Regelverstoß.

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
| `runs/b<N>/result.json` | Kennzahlen des Laufs: Exit-Code, Dauer, Anfragen, Token, Kosten, Abbruchgrund — **die** Quelle für Laufzeit und Kosten des Batches |
| `runs/b<N>/harness-facts.md` | Der Messdatenblock, den der Review bekam — gehört zu Batch **N−1** (der Review von N−1 liegt in `runs/b<N>/`) |
| `runs/b<N>/antwort.md` | Abschlussbericht des Workers (wortgleich im Review) |
| `runs/b<N>/review.md`, `review-prompt-*.md` | Bewertung und der Prompt, mit dem sie entstand |
| `snapshots/b<N>/snapshot.md`, `tools.tsv`, `reasoning.jsonl` | Kennzahlen-Snapshot, Werkzeugzählung, Denkblöcke separat |
| `logs/harness-<startzeit>.log` | Harness-Protokoll als JSONL — **je Start eine neue Datei**, wird nie überschrieben |
| `logs/crash-<zeit>.txt` | Traceback bei einem echten Absturz (Python-Fehler) |
| `logs/secret-zugriff.jsonl` | Jeder Zugriff auf Schluesseldateien (Art, Werkzeug, Dateiname) |
| `logs/rate-limit.json` | Zuletzt gemeldete Abo-Auslastung (Quelle, Zeitpunkt, Prozent) |
| `state/run.json` | Zustand, Batch, Gate, `harness_head`, `remote_work`, `retention` |
| `logs/wip-b<N>-status.txt` / `.patch` | Was bei einem Stopp unfertig im Arbeitsbaum lag |

**Suchen in `runs/`, `state/` und `logs/` immer mit `Select-String` (PowerShell), nie mit
der VS-Code-Suche:** diese Ordner sind per `.gitignore`/`search.exclude` ausgeblendet
(`harness/runs/`, `harness/logs/`, `harness/state/`), die Suche meldet dann „keine Treffer",
obwohl welche da sind (gemessen 2026-09-29: `NACHRUECKLISTE` steht in
`runs/b211/auftrag.md:170`, `runs/b212/auftrag.md:169` und `runs/b213/review.md:126`).

    Select-String -Path runs\b2*\auftrag.md -Pattern 'NACHR(UE|Ü)CKLISTE' -CaseSensitive:$false

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

Nach dem Lauf bleibt der letzte Stand als `live_letzte` stehen. **`/status` zeigt dann aber
nicht mehr die Live-Zahl**, sondern das Ergebnis `runs\b<N>\result.json` (R13x, Befund
M208-3d):

```
Laufender Batch: keiner (letzter Batch 208: 19m20s, $0.1232, 77 Anfragen, 118786 Ausgabe-Tokens, fertig 19:21 - aus runs/b208/result.json)
```

**Warum das noetig war:** die Live-Zahlen enthalten die **Ausgabe-Tokens nicht**. DeepSeek
liefert Eingabe und Cache in den `assistant`-Ereignissen exakt, die Ausgabe aber erst im
abschliessenden `result`-Ereignis - waehrend des Laufs steht dort also 0 und die
Live-Kosten sind zu niedrig (gemessen B207: Live `$0.0903` gegen echt `$0.1727`; B208:
`$0.0512` gegen `$0.1232`). Solange ein Batch **laeuft**, steht die Einschraenkung
deshalb ausdrücklich in der Zeile (`[Live-Zahlen OHNE Ausgabe-Tokens ...]`). Fehlt die
`result.json`, bleiben die Live-Zahlen stehen - mit demselben Vermerk und dem Hinweis,
dass die Datei fehlt.

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
| `Mittel der letzten N (B+C gemischt)` | dieselbe Reihe (bis zu 5 belegte Batches) | arithmetisches Mittel der Differenzen; die Batches stehen in Klammern dahinter. **Gemischt** heißt: B-Batches zählen mit — sie bauen keine Köpfe. Für die Hochrechnung wird diese Zahl **nicht** mehr benutzt |
| `nur C-Batches` | dieselbe Reihe, B-Batches ausgelassen | Mittel **je C-Batch** — das ist der Durchsatz, mit dem gerechnet wird |
| `Mischung` | `stand.strang_von_batch` (Klassifikation) + Zeile `Mischverhaeltnis …` aus `analysis/hybrid-plan.md` | zwei Zahlen getrennt: der **gemessene** C-Anteil im Fenster und die **Regel** (z. B. „2 B : 1 C" → jeder 3. Batch ist ein C-Batch) |
| `Insn (nur wo belegt)` | Zeile **`Paket E offen`**, **Ist-Spalte** der Soll/Ist-Tafel des Batch-Dokuments (`analysis/port-batch<N>-*.md`) | Insn offen (letzter belegter Wert) minus Insn offen (heute) |
| `offen (Paket E, C-Arbeitsvorrat)` | dieselbe Tabellenzeile, **Ist-Spalte** | Köpfe/Insn, die in Paket E noch offen sind |
| `HYPOTHESIS (Paket E, Arbeitsvorrat)` | offene Köpfe ÷ Durchsatz **je C-Batch** | **Schätzung** — und zwar in **zwei** Schritten: `-> x C-Batches` und daraus `-> ca. y KALENDER-Batches` (x ÷ C-Anteil). Vorher stand dort eine einzige Zahl aus dem gemischten Mittel („ca. 369 Batches"), die den C-Stillstand nicht enthielt (M209-3, R13aa) |
| `HYPOTHESIS (C gesamt, ABGELEITET)` | Planungsdokument mit der Zeile `OFFEN: <K> Koepfe / <I> Insn` (z. B. B196 §6.1, Quelle `analysis/_m196/_plan_c.txt`) | `<K> - (R207 heute - Bau-Liste damals)`; die Insn über den damaligen **Insn-je-Kopf-Schnitt** fortgeschrieben (deshalb „~" und „Schaetzung") |
| `-> x C-Batches` / `-> ca. y KALENDER-Batches` | offene Köpfe ÷ Durchsatz je C-Batch, danach ÷ C-Anteil | **Schätzung** — beide Schritte stehen einzeln da, damit die Annahme sichtbar ist |

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
**Der C-Arbeitsvorrat in drei Klassen (R13t2).** Direkt darunter stehen die noch nicht
gebauten Köpfe (`Inventar minus Bau-Liste`), getrennt nach dem, was die vorhandenen
Aufnahmen zeigen:

| Klasse | Definition | Stand 2026-09-28 |
|---|---|---|
| (1) ausgeführt, noch nicht gebaut | Coverage im Rumpf-Fenster gesetzt | 677 Köpfe / 28976 Insn |
| (2) nicht ausgeführt, Paket E | außerhalb der Aufnahmen, aber in der Paket-E-Hülle | 1 Kopf / 38 Insn |
| (3) nicht ausgeführt, sonstiger Rest | weder Aufnahme noch Paket E | 725 Köpfe / 24521 Insn |

„nicht ausgeführt“ heißt **in den vorhandenen Aufnahmen nicht ausgeführt**, nicht
„unnötig“ — die Aufnahmen decken nur Boot + einen Teil von Level 1 ab. Die Paket-E-Hülle
rechnet das Werkzeug **selbst** nach (Ruf-Abschluss ab den Wurzeln aus `_c_paket_e.txt`:
265 Köpfe, davon 28 offen; Projektzahl `c_kopf.py paket_e`: 274 / 38 — die kleine
Differenz steht in der Anzeige). Jede Klasse bekommt eine Hochrechnung
(offene Köpfe ÷ Durchsatz **je C-Batch** — die Klasse wird in C-Batches abgearbeitet,
nicht in jedem Kalender-Batch). Die Aufnahme-Zeile nennt die beiden Karten
mit Szene (`ppc_coverage.bin` = Gameplay-Replay, `ppc_cov_boot.bin` = Boot+Attract),
Herkunft (`analysis/f5-descr-batch42-2026-09-17.md:87-88`) und die Grenze der Aussage.
Warum die Insn nicht durchgängig da sind: die kanonische Bilanzdatei führt nur Köpfe
(nach dem Rumpf gemessen), und die Paket-E-Zeile gibt es erst in neueren Dokumenten.
Fehlt sie, steht das ausdrücklich da, statt eine Zahl zu erfinden.

Dieselbe Reihe (plus PLAN-Spalte und Laufzeit/Abbruchgrund) steht als **PLAN/IST-Tafel**
im Review-Prompt: der Reviewer sieht dort je Batch, was die Instruktion an Köpfen
genannt hat (`runs/b<N>/auftrag.md`, Abschnitt `TEIL 3`: genannte Kopfadressen und die
Insn in Klammern), was tatsächlich verifiziert wurde, wie lange der Batch lief
(`runs/b<N>/result.json` des **eigenen** Ordners) und warum er endete. Dazu gilt im
Reviewer-Prompt die **Median-Regel**: das Ziel des nächsten Batches darf höchstens ca.
das **1,3-fache des Medians** der letzten Batches sein — Abweichungen begründet der
Reviewer in einem Satz.

### 14e. Woher die C-Zahlen kommen (R13x, Befund M208-3)

Die Aussensicht hat vier Stellen gefunden, an denen eine **Vorhersage oder eine fremde
Zeile als Messwert** weitergetragen wurde. Die Regel ist seit R13x:

| Anzeige | Quelle | Warum nicht anders |
|---|---|---|
| `C verifiziert` (`/bilanz`), `verifiziert` im Änderungsblock, Kernzahlen der Aussensicht | **Preflight-Zeile** `analysis/_preflight_<N>.txt` (Zeile `C Koepfe`, maschinengeschrieben) | Das Batch-Dokument trägt die Zahl nicht immer richtig weiter (B202/B203 nennen 53/1272, gemessen sind 45/1080 bzw. 59/1416). Fehlt die Preflight-Datei (vor dem C-Strang), gilt die **Ist-Spalte** des Dokuments. |
| `Paket E offen`, `Insn (nur wo belegt)` | **Ist-Spalte** der Soll/Ist-Tafel (§6) des neuesten Batch-Dokuments | Eine Preflight-Zeile gibt es dafür nicht; die Vorhersagetafel (§5) nennt einen **Sollwert** (B206: `Bl 15 / 1083` vorhergesagt, gemessen `Bl 17 / 1202`). |
| Laufzeit/Abbruch in der PLAN/IST-Tafel | `runs/b<N>/result.json` | `runs/b<N>/harness-facts.md` gehört zu Batch **N−1**: der Harness legt sie in den Ordner des nächsten Batches (`orchestrator.review`, `ziel=rdir`). Gemessen: `runs/b208/harness-facts.md` nennt `47m26s` (b207), `runs/b208/result.json` `1160,907 s = 19m20s`. |
| `letzter Batch …` in `/status` | `runs/b<N>/result.json` desselben Batches | Die Live-Zahlen haben keine Ausgabe-Tokens (s. 14a). |

**Wie das Dokument gelesen wird** (`hx/stand.py`, `ist_wert`): von allen
Markdown-Tabellenzeilen, deren **erste Zelle** das Etikett ist (`C Koepfe`,
`Paket E offen` — Markup wie `**`, Backticks wird entfernt), zählt die **letzte**
Zeile, und darin die **letzte Zelle, die mit dem Zahlenmuster beginnt**. Damit gewinnt
die Soll/Ist-Tafel gegen die Vorhersagetafel (§5 steht immer davor), und die
Spalte „Abweichung/Quelle“ am Zeilenende kann nicht als Wert gelesen werden. Jede
Delta-Zeile nennt die verglichenen Batches (`(B207 -> B208)`), weil ein Vergleich auch
über eine Lücke laufen kann (Paket E: B206 -> B208, B207 führt die Zeile nicht).

Belege: `docs/_r13x_belege.md` (vorher/nachher an den echten Dateien von B206–B208),
Tests `tests/test_r13x_fixes.py`.

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

## 16. Offene Fragen an dich (`/fragen`, R13s/R13y/R13ab)

`/fragen` (Telegram) und `python -m hx.cli fragen` zeigen, was gerade **an dir** offen
ist — jede Frage mit **Kennung**, je Frage als **eine entscheidbare Zeile**. Seit R13ab
(Punkt 4) gibt es **zwei** Listen: unter „OFFENE FRAGEN AN DICH" steht nur, was wirklich
eine **Entscheidung von dir** braucht; die `ENTSCHIEDEN`-Zeilen des Reviewers (er hat den
Regelfall selbst entschieden, du kannst nur ein Veto einlegen) stehen in einem eigenen
Abschnitt **„ZUR KENNTNIS"**:

```
FRAGEN AN DICH (Anker: BATCH 206)

NAECHSTER SCHRITT
  (a) R535 (NEU, GEMESSEN, OFTEN): addc addiert das EINGEHENDE CA NICHT - eine Probe ...

OFFENE FRAGEN AN DICH
  A5        ANKERPOSTEN (5): soll prof je Kopf MEHRERE MEM-Varianten fahren?
            Empfehlung: ja | bei ja: eigener Werkzeugschritt / bei nein: -
            Quelle: Ankerkopf r1b-workstream.md
  A6        UNKLAR FORMULIERT: offen bleiben: R330, M60_NO_EVID, ...
  R209-1    ENTSCHEIDUNG NOETIG (bremst): Soll der Hybrid-Kern gegen Unicorn geprueft ...
  R209-2    OFFENE FRAGE: Du nennst 21 Referenzstroeme, gezaehlt sind 20. Welcher fehlt?
  R209-3    WARTET AUF LIVE-AUFNAHME: 0x40B/0x40E/0x40F
  M208-1    AUSSENSICHT (Gewicht mittel): Der Zielsatz in readme.md nennt kein Budget ...
            Empfehlung: Das Budget im Zielsatz der readme nachtragen.
            Beleg: readme.md:640-642
  (4 Posten hat der Reviewer selbst geschlossen - Veto per /claude)

ZUR KENNTNIS (Veto per /claude <Kennung> moeglich)
  R209-4    ENTSCHIEDEN: Zuerst wird der Interpreter streng gemacht.
            Quelle: b210/review.md

ANTWORTEN: /claude <Kennung> <Text>   (z. B. "/claude A5 ja" oder "/claude M208-1: abgelehnt, weil ...")
```

Was wohin gehört:

| Quelle | Abschnitt |
|---|---|
| Ankerposten `A<n>`, Aussensicht-Befund `M<batch>-n` (Empfänger du), verworfener Befund `M<batch>-v<n>` | OFFENE FRAGEN |
| `ENTSCHEIDUNG NOETIG:` (bremst), `OFFENE FRAGE:`, `WARTET AUF LIVE-AUFNAHME:` | OFFENE FRAGEN |
| `ENTSCHIEDEN:` des Reviewers | **ZUR KENNTNIS** (Veto per `/claude`) |

`/status` zählt dieselben Töpfe getrennt: `Fragen an dich: 4 offen, 2 zur Kenntnis
(offen: A1, R210-1, …) (zur Kenntnis: R210-4, R210-5)`. Beide Listen sind über die Kennung
antwortbar — auch ein Kenntnis-Punkt („`/claude R209-4 Widerspruch: bitte anders`").

**Ankerposten unter einem Sammel-Schluss (R13ac2, 2026-09-29).** Ein Block kann seine
Posten auch **sammelweise** schließen: `Alle Posten GESCHLOSSEN. … **(4)** A1
MEM-Varianten, **(5)** 42704, **(6)** …: GESCHLOSSEN als Entscheidungsposten … **Keine
offene Nutzerfrage.**` Posten **ohne eigenes Statuswort**, die dieser Sammel-Schluss
mitzieht, sind **keine** offenen Fragen — sie standen als `A4`/`A5` unter „OFFENE FRAGEN
AN DICH" und stehen jetzt unter **ZUR KENNTNIS** mit dem Vermerk
„(Sammel-Schluss im Anker)". Sie verschwinden also nicht, sondern werden einsortiert.
Ohne Sammel-Schluss bleibt ein solcher Posten offen (und wird als `UNKLAR FORMULIERT`
gezeigt, wenn keine entscheidbare Zeile daraus wird).

### 16a. Die Kennungen (R13y, 2026-09-28)

| Kennung | Woher | Beispiel |
|---|---|---|
| `A5` | Ankerposten `(5)` im Ankerkopf — die Kennung ist die Postennummer | `A12` |
| `R209-1` | Marker-Zeile des Reviews, das **Batch 209** bewertet hat (fortlaufend in der Reihenfolge `ENTSCHEIDUNG NOETIG` → `OFFENE FRAGE` → `WARTET AUF LIVE-AUFNAHME` → `ENTSCHIEDEN`) | `R209-2` |
| `M208-1` | Aussensicht-Befund (vergleicht sie selbst) | `M208-5b` |

Es gibt **keinen neuen Befehl** und **keinen eigenen Speicher**: die Kennungen werden aus
den vorhandenen Belegen abgeleitet (Ankerkopf, letztes Review, Aussensicht-Register,
Queue-Dateien). Deshalb bleiben sie auch nach einem Harness-Neustart oder einem
abgebrochenen Batch gültig.

**Wie eine Frage „entscheidbar" wird** (R13s, erweitert R13z): Der Harness zerlegt die
Ankerzeile in ihre `(n) …`-Posten und sucht darin drei Teile — eine **Frage**, eine
**Empfehlung** (`Vorschlag:` / `Empfehlung:`) und die **Folgen**:

| Teil | Form | Beispiel |
|---|---|---|
| Frage | **Ja/Nein**: Satz, der mit `soll/ist/bleibt/wird/kann/darf/muss/gibt` beginnt und mit `?` endet. **A/B** (R13z): derselbe Satz, wenn im Posten `(A)`/`(B)`, `A oder B` oder „Weg A" steht — dann genügt auch ein Fragesatz ohne Fragewort | „Soll der Kern gegen `mame/` geprüft werden (A) oder gegen die ISA (B)?" |
| Empfehlung | `Vorschlag:` / `Empfehlung:` + `ja` / `nein` / `kein…` / `A` / `B` | `(Vorschlag: A)` |
| Folgen | `bei ja:` / `bei nein:` bzw. `bei A:` / `bei B:` | `bei A: gemessener Vergleich je Form. bei B: nur Stichproben.` |

Fehlt einer der Teile, steht der Posten als **`UNKLAR FORMULIERT`** mit dem Originaltext —
nichts wird umgedeutet (Nutzerentscheid 2026-09-28); er bekommt aber trotzdem seine
Kennung, damit auch eine unklare Frage beantwortbar ist (dann am besten den Wortlaut
nennen). Der Ankerposten gehört dem **Reviewer**: seit R13z ist im Reviewer-Prompt
festgehalten, dass jeder Posten diese drei Teile haben **muss** (Wortlaut in der
Instruktion, der Worker trägt ihn in den Ankerkopf ein) und dass erledigte Posten mit dem
Wort `GESCHLOSSEN` geführt werden — sonst bleiben sie für immer offen. Die Marker-Zeilen
des Reviewers tragen keine Empfehlung — sie wird nicht erfunden.

Ein geteilter Aussensicht-Befund (Ziel/Scope-Anteil beim Nutzer, Sachanteil beim
Reviewer) trägt zwei Kennungen: `M208-5a` (du) und `M208-5b` (Reviewer). Die Kurzform
`M208-5` gilt für beide Teile.

**Verworfene Befunde (`M209-v1`, R13aa).** Hat die **Beleg-Regel** einen Aussensicht-Befund
aussortiert, steht er trotzdem unter `/fragen` — mit der Kennung `M<batch>-v<n>` und der
Marke **`AUSSENSICHT (verworfen - pruefen?)`**:

```
  M209-v1   AUSSENSICHT (verworfen - pruefen?): Das vorzeitige Ende wiederholt sich auch
            nach der Get-Date-/70-min-Regel (B208, B209). ...
            Empfehlung: Die Auftraege der B-Batches sollten eine geordnete Nachrueckliste ...
            Beleg: nicht anerkannt: Laufzeiten aus den Kosten und Laufzeiten je Batch ...
            Quelle: runs/meta-209.md (Rohantwort dort)
```

Der Beleg steht als **„nicht anerkannt"** dabei — du kannst also selbst urteilen, ob die
Regel zu streng war. Zeigt der Lauf **neueste** verworfene Befunde; das Register behält
alle. Antworten läuft wie sonst: `/claude M209-v1 pruefen` (der Anhang trägt den Wortlaut
mit). Die Quote in `/bilanz` zählt sie **nicht** mit.

### 16b. Antworten mit Kennung (`/claude`, R13y)

Beginnt eine `/claude`-Nachricht mit einer Kennung, gilt sie als **Antwort auf genau
diese Frage**:

```
/claude A5 ja, aber erst nach den Paket-E-Blaettern
/claude M208-1: abgelehnt, das Budget steht in hybrid-plan.md
/claude A5, M208-1: ja bzw. abgelehnt
```

Der Harness hängt dann **Wortlaut der Frage und Empfehlung** (den Stand von jetzt) an die
Nachricht an — der Reviewer sieht also, worauf sich „ja" bezieht, auch wenn der
Ankerposten später umgeschrieben wird. Danach steht die Frage in `/fragen` unter
**`BEANTWORTET, WARTET AUF REVIEW`** und verschwindet ganz, sobald das Review die
Nachricht gelesen hat (dann steht sie nur noch als `aufgenommen (nicht mehr offen)` mit
ihrer Kennung).

Eine **unbekannte** Kennung am Anfang wird abgewiesen: die Nachricht wird **nicht** in die
Queue gelegt, und der Harness antwortet mit den gültigen Kennungen. Eine Nachricht
**ohne** Kennung am Anfang geht unverändert an den Reviewer (Hinweise, Wünsche, freier
Text). Mehrere Kennungen in einer Nachricht sind erlaubt.

## 17. Was nehme ich wann? (R13y)

| Ich will … | Befehl | Ankunft |
|---|---|---|
| **Nachlesen**, was offen ist | `/fragen` | sofort (rein lesend) |
| **Antworten** auf eine Frage | `/claude <Kennung> <Text>` | beim nächsten Review |
| Einen **Hinweis/Wunsch** loswerden, der auch später noch passt | `/claude <Text>` | beim nächsten Review (als „vom Nutzer, nicht verhandelbar") |
| Dass der **nächste Batch sofort anders läuft** (am Gate) | `/ds <Text>` | mit dem nächsten Auftrag — nur am Batch-Übergang, **nicht** in einen laufenden Batch |
| Eine **Frage an Claude** außerhalb des Betriebs (nur lesend) | `/ask <Frage>` | sofort, eigener Lauf (kostet Abo-Kontingent) |
| Den **Zwischenstand** sehen | `/status` (Zustand, letzter Batch, offene Kennungen) | sofort |
| Die **Bilanz** (Äste, Durchsatz, Kosten) | `/bilanz [N]` | sofort |
| **Nur zusehen** | `/thinking [N]`, `hx.cli watch` | sofort, rein lesend |

Faustregeln:

* **`/fragen` ist zum Lesen, `/claude` zum Antworten** — und für alles, was der Reviewer
  wissen soll, ohne eine Batch-Instruktion zu ändern.
* **`/ds` nur, wenn der kommende Batch wirklich anders laufen soll.** Es ist die einzige
  Rückmeldung, die den Worker direkt erreicht; sie geht am Reviewer vorbei und gilt für
  genau einen Batch. Antworten auf Fragen gehören **nicht** hierher (sie brauchen die
  Bewertung des Reviewers).
* **Wissen/Belege statt Zurufe**: Wenn dir etwas auffällt (Messung, Widerspruch,
  fehlender Beleg), ist `/claude` der richtige Weg — der Reviewer prüft es und entscheidet
  selbst.

## 18. Die Batch-Uhr (R13ac, 2026-09-28)

Anlass: der Worker schätzte seine Laufzeit an der Zahl der Werkzeugaufrufe. In B210 hielt
er sich für "~180 min" (`snapshots/b210/reasoning.jsonl:174`), gemessen waren **46 min**
(`runs/b210/result.json`) — mit dieser Zeitnot strich er Pflichtteile. Die watch-Anzeige
zeigte denselben Batch als "200.6 min", weil sie ab dem Start des **Zuschauers** zählte.

### 18a. Eine Zahl, eine Quelle

Alle Zeitangaben kommen aus **einem** Feld: `state/run.json` → `worker.started_at`
(Prozessstart des Workers, geschrieben von `state.worker_started`). Modul: `hx/uhr.py`.

| Anzeige | Quelle | Beispiel |
|---|---|---|
| `hx.cli watch` "… min seit Batch-Start" | `worker.started_at` | `19.8 min seit Batch-Start 23:06:48 (Harness-Messung)` |
| `hx.cli status` "Laufender Batch 211: seit …" | `worker.started_at` | `seit 19m48s` |
| **BATCH-UHR** im Worker (nach jedem Werkzeugaufruf) | `worker.started_at` | siehe 18b |
| Vorspann `Batch-Start (Harness-Zeitstempel)` | derselbe Moment, wenige Sekunden vor dem Prozessstart | `23:06:48 Ortszeit am 2026-09-28` |
| Laufzeit eines **beendeten** Batches | `runs/b<N>/result.json` (`duration_s`) | `46m11s` |

Ist der Lauf beendet, steht in `watch` `Laufzeit 46m11s (runs/b210/result.json, Lauf
beendet)`. Fehlt beides, steht "Laufzeit nicht gemessen" — es wird nichts geschätzt. Die
watch-Minuten erscheinen nur noch im Zusatz `seit watch-Start: … min`, klar benannt.

### 18b. Die BATCH-UHR im Worker (PostToolUse-Hook)

Der Harness schreibt je Lauf eine Einstellungsdatei `runs/b<N>/worker-hooks.json` und hängt
sie mit `--settings` an den Worker. Darin steht ein `PostToolUse`-Hook (ohne Matcher), der
`tools/batch_uhr.py` aufruft; der Hook legt nach **jedem** Werkzeugaufruf eine Zeile in den
Kontext des Modells:

    BATCH-UHR (Harness-Messung): 42.1 min von 90 min seit Batch-Start 21:48:11 (Ortszeit).
    Weichgrenze 90 min, harte Grenze 180 min. Diese Zahl ist die Wanduhr des
    Worker-Prozesses (state/run.json:worker.started_at) - die Zahl der Werkzeugaufrufe sagt
    nichts ueber die Zeit (B210: '180 min' geschaetzt, 46 min gemessen).

* **Gemessen**, dass die Zeile beim Modell ankommt: `tools/r13ac_probe_hook.py`,
  Beleg `docs/_r13ac_hook.txt` (echter Worker-Aufruf, auffällige Grenzen 77/123 — das
  Modell nannte sie wörtlich).
* Die Grenzen kommen aus `[limits]` (`alarm_wall_s` = Weichgrenze, `hard_wall_s` = harte).
* **Abschalten:** `[claude] worker_hooks = false` in `harness.toml` (dann bleibt nur die
  Vorspann-Regel). Fehlt `tools/batch_uhr.py`, wird kein Hook gehängt.
* Der Hook ist **still**, wenn kein Lauf läuft, und bricht nie ab: jeder Fehler endet mit
  Rückgabewert 0 und ohne Ausgabe.
* Der erste Werkzeugaufruf eines Batches sieht die Zeile noch nicht — dafür steht die
  absolute Startzeit im Vorspann (`UMFELD DIESES LAUFS`), zusammen mit der Regel
  „Restzeit nur aus `Get-Date` minus dieser Startzeit".

### 18c. Trend, „verifiziert", PLAN und Median (M210-2 bis M210-4)

* **Trend und Durchsatz** nennen **zwei Zähler getrennt**: die **C Koepfe** aus den
  maschinengeschriebenen Preflight-Dateien (`analysis/_preflight_<N>.txt`, Zeile
  `C Koepfe`), lückenlos über die letzten 12 Batches, und den **R207-Zähler** (gebaut, alle
  Stränge). Fehlt die Preflight-Reihe, steht dort „NICHT GEMESSEN"; ein Fenster mit Lücke
  (B209 hat keine Bilanzdatei) wird als „LUECKENHAFT" benannt. Gemessen heute:
  **B198 17 → B210 78 = +61 Koepfe**.
* **„C verifiziert"** im Bilanz-Kopf kommt jetzt **nur** aus der Bahnabdeckungszeile des
  Preflights (heute 55 von 78). Die Kopfzahl heißt **„C Koepfe referenzgleich"** — sie
  sagt „gleich zur Referenz", nicht „geprüft".
* **PLAN** kommt aus der Zeile `SOLL-KOEPFE: <n>` der DS_INSTRUCTION (B211 hat sie
  erstmals), sonst `-`. **MEDIAN** zählt nur C-Batches mit `SOLL-KOEPFE > 0` und steht auf
  den gemessenen C Koepfen; gibt es keinen solchen Batch, steht „nicht gemessen" und der
  Reviewer soll die Soll-Zeile nachliefern.

