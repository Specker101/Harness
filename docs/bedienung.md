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

---

## 2. Lokale Befehle (ohne Telegram)

Immer aus `g:\Harness\harness` aufrufen (`python -m hx.cli …`).

| Befehl | Wirkung |
|---|---|
| `status` | Zustand, Batch, Gate (mit Quelle „vom Nutzer"/„vom Reviewer"), Pause-Info, Kosten, Tarif, Queue, Git-Lage |
| `budget` | Kosten, Alarm-/Hartgrenzen, Tarif |
| `pause` | pausieren; ein laufender Batch läuft zu Ende, danach startet nichts Neues |
| `resume` | fortsetzen (`--accept-dirty`, wenn ein unsauberer Arbeitsbaum bewusst akzeptiert wird) |
| `stop` | laufenden Batch abbrechen: WIP wird gesichert (Status + Patch + Stash) |
| `approve [--text "…"]` | wartenden Batch freigeben; optionaler Text geht als ds-Nachricht mit |
| `send ds "Text"` / `send ds --file auftrag.md` | Nachricht an den **Worker** in die Queue (Zustellung am nächsten Batch-Übergang) |
| `send claude "Text"` / `send claude --file ziele.md` | Nachricht an den **Reviewer** in die Queue (Zustellung am nächsten Review) |
| `run-instruction --file instruktion.md [--profile ghidra-read] [--program /830d01.27p.main.bin]` | **eigene** Instruktion als nächster Worker-Batch, **am Reviewer vorbei**; im Log/Status als „vom Nutzer" gekennzeichnet; danach normaler Batch-Ende-Review |
| `watch [--batch N]` | Live-Ansicht des laufenden Batches bzw. Nachspielen eines fertigen; **rein lesend** |
| `profiles` | verfügbare Ghidra-Werkzeugprofile mit Zahlen |
| `probe-telegram` | Bot-Name, Allowlist und Absender der letzten Nachrichten |
| `show-prompts` | Review-Prompt und Worker-Vorspann als Dateien in `preview\` |
| `env-proof` | R16-Nachweis: echter Kleinlauf, der prüft, ob Unterskripte Zugangsdaten sehen |

Ohne laufenden Harness bleiben die Befehle als Datei in `state\ctl\` liegen und werden beim
nächsten Start ausgeführt — `status` zeigt sie dann unter „Lokale Befehle warten".

**Wie schnell wirkt ein Befehl?** Der Harness holt die Steuerdateien am Anfang jedes
Schleifendurchlaufs ab. Im Pausenzustand liegt dazwischen die Telegram-Abfrage (Langpoll,
`poll_timeout_s = 25`), ein lokaler Befehl wirkt also nach **wenigen Sekunden bis ~30 s**.
Im Notfall ist `stop.ps1 -Force` sofort.

---

## 3. Telegram-Befehle

`/status` · `/budget` · `/pause` · `/resume [ok]` · `/stop` · `/approve [Text]` ·
`/autonom [on|off]` · `/ds <Text>` · `/claude <Text>` · `/review` · `/last [ds|claude] [n]` ·
`/queue` · `/why` · `/help`

Nachrichten werden **nie** in einen laufenden Batch injiziert: sie landen als Queue-Datei
und werden am nächsten Übergang zugestellt. Nachrichten über 4000 Zeichen werden
automatisch aufgeteilt. `/resume ok` ist die Bestätigung für einen unsauberen Arbeitsbaum.

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
python -m hx.cli watch                  # laufender Batch, live
python -m hx.cli watch --batch 1        # abgeschlossenen Batch nachspielen
python -m hx.cli watch --run env-proof  # benannten Lauf nachspielen (z. B. env-Beweis)
```

Gezeigt wird: Texte des Workers, Werkzeugaufrufe in Kurzform (Name + gekürzte Argumente),
abgelehnte Aufrufe, laufende Kosten/Anfragen/Laufzeit; am Ende die Batch-Kennzahlen und die
Reviewer-Antwort (`TELEGRAM_SUMMARY` und `DS_INSTRUCTION` lesbar).

**Rein lesend:** `watch` öffnet nur Dateien, die der Harness ohnehin schreibt, kennt keine
Sperren und schreibt nichts. Fenster schließen oder `Strg+C` beendet nur den Zuschauer. Der
laufende Betrieb wird in keiner Weise beeinflusst.

---

## 6. Notfall-Stopp

| Weg | Wirkung |
|---|---|
| `python -m hx.cli stop` | sauber: Stop-Marker, WIP-Sicherung, Worker wird beendet |
| Telegram `/stop` | dasselbe über den Bot |
| `powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1` | setzt den Stop-Marker (greift beim nächsten Durchlauf) |
| `.\stop.ps1 -Force` | zusätzlich den Harness-Prozessbaum hart beenden (`taskkill /PID … /T /F`) |
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
6. Nach dem Batch: Kennzahlen, Snapshot, Review, Push nach `origin/main`
   (Checkpoint-Tags bleiben lokal).
