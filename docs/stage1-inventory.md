# Stufe 1 — Inventur: autonomes DeepSeek/Claude/Telegram-Harness

**Projekt:** Silent Scope Decomp (Konami Silent Scope 1 / Hornet / Voodoo 1) — Harness-Vorbereitung
**Datum:** 2026-09-25 · **Arbeitslauf:** Copilot Chat, Modell `deepseek/deepseek-flash` (DeepSeek V4.1 Flash, BYOK)
**Grundlage:** Auftrag „Planung eines autonomen DeepSeek/Claude/Telegram-Harness", Abschnitt 23 → **Stufe 1** (nur Inventur, strikt read-only) + **zentrale Entscheidungsvorlage**
**Reichweite:** Es wurde **nichts installiert, nichts geändert, nichts committet**. Neu angelegt wurde ausschließlich diese Datei (`g:\Harness\docs\stage1-inventory.md`).

## Kennzeichnung (Pflicht in dieser Datei)

| Marker | Bedeutung |
|---|---|
| `[beobachtet: <Pfad/Befehl>]` | in dieser Sitzung selbst gemessen oder gelesen |
| `[offiziell: <URL>]` | offizielle Dokumentation (VS Code / DeepSeek) |
| `[Nutzerangabe]` | vom Nutzer vorgegeben oder laut Nutzer bereits verifiziert |
| `[nicht geprüft]` | offen — gehört in die Testliste für Stufe 2 |

Es wird bewusst **kein** „CONFIRMED" für Dinge vergeben, die nur plausibel klingen. Wo eine Aussage abgeleitet ist, steht „STRONG INFERENCE" mit Begründung.

---

## 0. Umfang, Nachweise, nicht durchgeführte Schritte

**Vorher/Nachher-Nachweis (read-only eingehalten)** `[beobachtet: `git status --porcelain`, `git log --oneline -1`]`

| Repo | HEAD vorher | HEAD nachher | Arbeitsbaum vorher | Arbeitsbaum nachher |
|---|---|---|---|---|
| `g:\Harness` | `4a1e6cd` (main) | `4a1e6cd` | leer | nur `docs/stage1-inventory.md` (neu) |
| `g:\Silent Scope Decomp` | `e439bd7` (main, = origin/main) | `e439bd7` | leer | leer |

**Der vorbereitete Lokaltest (`code chat`) wurde NICHT ausgeführt** — Nutzerentscheidung nach Rückfrage (die Details stehen in §L4 und Anhang B). Grund der Rückfrage: zum Testzeitpunkt war **nur ein einziges VS-Code-Fenster** offen, nämlich dieses (`Harness.code-workspace`), während das Decomp-Arbeitsfenster (`Silent Scope Decomp.code-workspace`) **nicht** lief `[beobachtet: `Get-Process Code | MainWindowTitle` → „Pasted text #1 - Harness (Workspace)"]`. Die Fensterauflösung von `code chat` ohne Flag ist **nicht dokumentiert**; da dieses Fenster den Ordner `Silent Scope Decomp` als Workspace-Wurzel enthält, war ein Landen im Harness-Fenster nicht sicher auszuschließen. Damit sind die Punkte (a)–(g) der Testliste weiterhin **offen** `[nicht geprüft]`.

**Nicht geprüft (bewusst, wegen read-only / fehlender Werkzeuge):** Lokalverhalten von `code chat` (alle sieben Fragen), `claude --version`/`claude -p` (Claude Code ist nicht installiert), Abbruch eines laufenden Turns (nur recherchiert), Telegram-Bot-Anlage, Ghidra-Schreibzugriffe, Windows-24/7-Verhalten (Auto-Logon/RDP).

**Nebenbefund zur Sorgfalt:** Ein einzelner Terminal-Befehl lieferte 20 KB Ausgabe; VS Code hat sie als Werkzeug-Ergebnis im Fenster-Speicher zwischengelagert (`…\workspaceStorage\474534…\GitHub.copilot-chat\chat-session-resources\…\content.txt`) — das ist normales VS-Code-Verhalten und **keine** Projektdatei.

---

## A. Vorhandene Umgebung

### A1 Repos, Workspaces, Prozesse
- `g:\Silent Scope Decomp` = Decomp-Repo: Remote `https://github.com/Specker101/Silent-Scope-Decomp.git`, Branch `main`, `user.name=Specker`, `user.email=benji.go@gmx.de`; HEAD `e439bd7` `[beobachtet: `.git/config`, `git log -1`]`.
- `g:\Harness` = eigener, praktisch leerer Git-Checkout (`.gitignore`, `.gitattributes`, `Harness.code-workspace`, 1 Commit `4a1e6cd` „Zeilenenden-Konvention aus dem Hauptprojekt uebernommen") `[beobachtet: `list_dir`, `git log -1`]`.
- `g:\Harness\Harness.code-workspace` bindet **beide** Ordner ein (`"."` + `"../Silent Scope Decomp"`) → dieses Fenster ist Multi-Root `[beobachtet: Datei]`.
- Getrennt davon existiert `g:\Silent Scope Decomp\Silent Scope Decomp.code-workspace` (Single-Root) — das ist der **bisherige DS-Arbeitsplatz** `[beobachtet: Datei; Zuordnung über `workspace.json`, s. A5]`.
- Zum Testzeitpunkt lief nur dieses Fenster; das Decomp-Fenster war geschlossen `[beobachtet: `Get-Process Code`]`.

### A2 Regelwerk, das Copilot automatisch sieht
- `AGENTS.md` im Repo-Wurzelverzeichnis — in dieser Sitzung **nachweislich automatisch geladen** (als Attachment im Kontext) `[beobachtet: `<attachment filePath="g:\Silent Scope Decomp\AGENTS.md">`]`. Inhalt u. a.: Ghidra MCP = autoritativ; Funde nach `analysis/`; Trennung CONFIRMED / STRONG INFERENCE / HYPOTHESIS; **Anchor-Konvention** („Stand / Fertig / Nächster Schritt / Offene Entscheidung / Fallstricke" oben in der Workstream-Datei); **Batch-Ablauf** (git status → Memory-Sync → Mesa-Check → genau EIN `preflight`-Lauf → `m149_bilanz.py --from-preflight` → Memory-Export → Commit); `analysis/ghidra-mcp-notes.md` wird am Batch-Ende mitcommittet, außer der Diff entfernt > 50 Zeilen.
- `readme.md` (Projektziel, ROM-Varianten, was *nicht* im Repo liegt) `[beobachtet: Datei]`.
- `.github/agents/ghidra-re.agent.md` = Custom Agent **„Ghidra RE"**, Frontmatter `tools:` = `ghidra/*`, `edit`, `read`, `search`, `execute`, `agent`, `todo`, `web`, `vscode`, `vscodeTasks`, `vscodeGeneral`, `vscodeBrowser`, `runInTerminal`, `getTerminalOutput`, `killTerminal`, `terminalLastCommand` `[beobachtet: Datei]`. In dieser Sitzung ist er als wählbarer Agent vorhanden `[beobachtet: Agentenliste der Sitzung]`.
- `analysis/ghidra-mcp-notes.md` (MCP-Setup, Verbindungsarchitektur, Tool-Gating-Befund, Portabilität), `analysis/tooling-cheatsheet.md`, `analysis/r1b-workstream.md` (aktiver Workstream mit Anchor-Block), Batch-Dokumente `analysis/port-batch1xx-*.md`, Belegordner `analysis/_m1xx/`.
- `analysis/_memory/*.md` = **20** gespiegelte Copilot-Memory-Dateien (decoder-regeln, port-skeleton, missionsebene, …) `[beobachtet: `list_dir`]`; Werkzeug `scripts/m151_memory_sync.py` (status/export/import) `[beobachtet: Datei vorhanden; Verhalten laut AGENTS.md]`.
- Copilot-Memory-Scope `repo` liegt **außerhalb** des Repos im VS-Code-Profil und hängt am Workspace-Pfad (s. A5) `[beobachtet: `memory-tool/memories/repo` unter dem Decomp-Hash; in diesem Fenster ist `/memories/repo` leer]`.

### A3 Projektwerkzeuge (Auszug, ~1000 Einträge in `scripts/`)
`[beobachtet: `list_dir g:\Silent Scope Decomp\scripts`]`
- **Batch/Torwächter:** `preflight.py`, `port_regression.py`, `m149_bilanz.py`, `m144_outguard.py`, `m60_inventar.py`, `evidence.py` (Schreibpfad-Wächter R355).
- **Bauen/Umfeld:** `Makefile` (im Wurzelverzeichnis), `scripts/port_build.ps1`, `scripts/setup_mesa.ps1`.
- **Ghidra:** `scripts/start-mcp-bridge.ps1`, `scripts/start-ghidra-headless.ps1`, `scripts/ghidra_http.ps1`, `scripts/ghidra_api.ps1`, `ghidra_dump.ps1`.
- **Analyse:** `m1xx_*.py` (numerierte Werkzeugkette, aktuell bis `m158_t3map.py`), `m151_memory_sync.py`.
- **PowerShell-Anteil:** **35** `.ps1` in `scripts\`, **keine** `.ps1` außerhalb `[beobachtet: `Get-ChildItem -Filter *.ps1`]`.
- **Zahl der Python-Werkzeuge:** mehrere hundert `*.py` `[beobachtet: Verzeichnisliste]`; Projektkonvention ist Python + PowerShell.

### A4 Laufzeitumgebungen und Toolchain (heute gemessen)
| Prüfung | Ergebnis | Kennzeichnung |
|---|---|---|
| `python` (PATH) | `C:\Users\Benji\AppData\Local\Programs\Python\Python312\python.exe`, **3.12.1** | `[beobachtet]` |
| `py -3.10` | „No suitable Python runtime found" — die in den Notizen genannte System-3.10 ist über den Launcher nicht erreichbar | `[beobachtet]` |
| Bridge-venv | `g:\Silent Scope Decomp\tools\bridge-venv\Scripts\python.exe`, 3.12.1, mit `httpx` und `mcp` | `[beobachtet]` |
| JDK 21 | `g:\Silent Scope Decomp\tools\jdk21\bin\java.exe` (portabel im Workspace) | `[beobachtet: Log des Headless-Servers]` |
| `git` | 2.43.0.windows.1 | `[beobachtet]` |
| `g++` (PATH) | `C:\MinGW\bin\g++.exe` = **MinGW.org GCC 6.3.0** (32-bit) — nur der *PATH*-Treffer; gebaut wird mit MSYS2-UCRT64 16.2.0 | `[beobachtet]` |
| `mingw32-make` | `C:\MinGW\bin\mingw32-make.exe` (WinAVR/MinGW-Altbestand im PATH) | `[beobachtet]` |
| `node` / `npm` | **nicht gefunden** (weder PATH noch `C:\Program Files\nodejs`, `C:\Program Files (x86)\nodejs`, `%APPDATA%\npm`, `%LOCALAPPDATA%\nvm`) | `[beobachtet]` |
| `code` (VS-Code-CLI) | `%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd`; VS Code **1.139.1**, Commit `04c0d99f4f` | `[beobachtet]` |
| Copilot-Chat-Extension | 0.67.0 | `[beobachtet: Transcript `session.start`]` |

### A5 Workspace-Storage: Hashes, Memory, Chat-Verläufe (Schlüsselbefund)
Der Ordner `workspaceStorage\<hash>` hängt am **Pfad der Workspace-Datei** `[beobachtet: je `<hash>\workspace.json`]`:

| Hash | Workspace-Datei | Bedeutung |
|---|---|---|
| `474534577e918eba3f49c4950eea27ec` | `file:///g:/Harness/Harness.code-workspace` | **dieses** Multi-Root-Fenster |
| `764c8a21ca38a53d4b37dd4b334fedbe` | `file:///g:/Silent Scope Decomp/Silent Scope Decomp.code-workspace` | **DS-Arbeitsfenster auf G:** (aktuell) |
| `26867c8cf1d77db2f492caf2f786400a` | `file:///f:/Silent Scope Decomp/Silent Scope Decomp.code-workspace` | Altstand vor dem SSD-Umzug (F:) |
| `73f64529838e33e8162bbd627aed450c` | `%APPDATA%\Code\Workspaces\1790352506291\workspace.json` (temporär) | Zweck `[nicht geprüft]` |

**Folgen (wichtig für das Harness):**
1. Copilot-Memory **und** Chat-Verläufe sind **fenstergebunden**. In diesem Fenster ist `/memories/repo` leer, obwohl `analysis/_memory/` im Repo 20 Dateien führt `[beobachtet: Memory-Tool dieser Sitzung + `list_dir`]`.
2. **Kein Werkzeug darf Hashes hartkodieren** — Vorbild ist `scripts/m151_memory_sync.py`, das den Hash über `workspace.json` auflöst `[beobachtet: AGENTS.md-Abschnitt „Copilot-Memory"]`.
3. Ein **Umzug/Kopieren des Projekts ändert den Hash** (F: → G: ist genau das) und damit Memory- und Verlaufsort.

### A6 Claude Code — Stand auf diesem Rechner
- **Nicht installiert/belegt:** `claude` nicht im PATH; `%USERPROFILE%\.claude` existiert nicht; kein npm-Global-Verzeichnis `[beobachtet: `Get-Command claude`, `list_dir`]`.
- **Vorgegeben (nicht hier zu prüfen):** Auth ohne API-Key über `claude setup-token` → 1-Jahres-OAuth-Token in `CLAUDE_CODE_OAUTH_TOKEN` (wird im `--bare`-Modus **nicht** gelesen); non-interaktiv via `claude -p`; lokale MCP-Server funktionieren damit; Browser-/Puppeteer-Weg ist ausgeschlossen `[Nutzerangabe: bereits verifiziert]`.
- **`[nicht geprüft]` und offen:** Claude Code benötigt möglicherweise **kein** Node.js (nativer Windows-Installer). Die **Installation erfolgt durch den Nutzer**, nicht in Stufe 1. Die DeepSeek-eigene Anleitung nennt dagegen den npm-Weg (`npm install -g @anthropic-ai/claude-code`, Node 18+) `[offiziell: https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code]` — deshalb ist dieser Punkt ausdrücklich offen und **kein** Widerspruchsbefund.

### A7 Telegram-Vorprüfung (nur beobachtet, kein Bot, keine Secrets)
- **Erreichbarkeit:** `https://api.telegram.org` → **HTTP 200** (kein Token, kein Login) `[beobachtet: `Invoke-WebRequest -UseBasicParsing`, PS 5.1, Studio-Rechner]`.
- **Vorhandene Python-Pakete:** PATH-Python 3.12.1 → **kein** `telegram`, `telebot`, `aiogram`, `telethon`, `httpx`, `requests`; Bridge-venv → `httpx` ja, `mcp` ja, **kein** Telegram-Paket `[beobachtet: `importlib.util.find_spec`]`.
- **Ableitung (kein Befund):** Die Telegram-Bot-API ist reines HTTPS/JSON, also mit der Standardbibliothek (`urllib.request` + `json`, Long-Polling über `getUpdates`) bedienbar — ein Paket wäre Komfort, keine Voraussetzung `[STRONG INFERENCE, nicht geprüft]`. Die eigentliche Telegram-Planung (Commands, Queue, Autorisierung) folgt in Stufe 2, Abschnitt I.

### A8 Zwei-Rechner-Betrieb (Projektkonvention, portabel gemacht)
- Namen statt „hier/dort": **Studio-Rechner** `BENSSTUDIO`/`Benji` (`g:\Silent Scope Decomp`, bis 2026-09-25 `F:`), **Arcade-Rechner** `DESKTOP-BFHI18Q`/`Arcade` `[beobachtet: `analysis/ghidra-mcp-notes.md`]`.
- Nach jedem Pull/Rechnerwechsel müssen die Harness-Binaries neu gebaut werden (`*.exe`, `build/` sind gitignoriert) `[beobachtet: AGENTS.md „Maschinen-Stand"]`.
- `.git/config` ist nicht versioniert → Git-Identität muss pro Kopie gesetzt werden `[beobachtet: `.git/config` enthält sie lokal; AGENTS.md]`.
- Konsequenz für das Harness: ein Schreib-Lock und eine Branch-/Push-Strategie sind nötig, sonst kollidieren zwei Rechner (offener Punkt, §Risiken).

---

## L. DeepSeek-Laufzeit

### L1 Träger und Modell
- **Träger:** VS Code Copilot Chat (Extension `GitHub.copilot-chat` 0.67.0) mit **BYOK**-Modell aus der Extension `vizards.deepseek-v4-for-copilot` **0.9.3** („DeepSeek V4 for Copilot Chat", vendor `deepseek`) `[beobachtet: `%USERPROFILE%\.vscode\extensions\…\package.json`, `%APPDATA%\Code\User\chatLanguageModels.json`]`.
- **Modellkennzahlen** (aus dem Sessionzustand einer echten Sitzung) `[beobachtet: `chatSessions\<sid>.jsonl`, Zeile 1]`:

| Feld | Wert |
|---|---|
| identifier | `deepseek/deepseek-flash` |
| Name / version | „DeepSeek V4.1 Flash" / v4.1, family `deepseek`, `isBYOK: true` |
| Kontext | `maxInputTokens` 655 360 · `maxOutputTokens` 393 216 |
| Fähigkeiten | `vision: true`, `toolCalling: true`, `agentMode: true` |
| Reasoning | `reasoningEffort` ∈ {none, low, high, max}, Default **high** (im beobachteten Chat auf `high`) |
| Preisinfo (in der UI) | Input $0.15 / 1M · Cache-Input $0.003 / 1M · Output $0.6 / 1M, „Off-peak" |

- **Anbindung:** Extension-Setting `deepseek-copilot.baseUrl`, Default `https://api.deepseek.com`; API-Key über VS-Code-SecretStorage (Kommandos `setApiKey` / `getApiKey` / `clearApiKey`); Diagnose über `deepseek-copilot.debugMode` (minimal | metadata | verbose) und `…openRequestDumpsFolder` `[beobachtet: `package.json`]`. Wo genau Request-Dumps landen, ist `[nicht geprüft]` — im globalStorage existiert **kein** Ordner dieser Extension.
- **Instruktionsquelle im Modelllauf:** `AGENTS.md` (automatisch, s. A2) — die Projektregeln sind also Teil jedes DS-Laufs, ohne dass der Nutzer sie eintippt.

### L2 Wie der DS-Lauf aussieht — und wie man ihn ausliest (zentraler Befund)
Pro Arbeitsfenster existieren **zwei** parallele Mitschriebe je Chat `[beobachtet: Verzeichnisse + Dateiinhalte]`:

| Ort | Form | Inhalt |
|---|---|---|
| `workspaceStorage\<hash>\chatSessions\<sid>.jsonl` | VS-Code-Sessionzustand: `kind:0` = Vollzustand, danach `kind:1`-Patches (`k`/`v`) | `sessionId`, `requests[]`, `selectedModel` (mit allen Kennzahlen), `mode`, `permissionLevel`, `inputText` |
| `workspaceStorage\<hash>\GitHub.copilot-chat\transcripts\<sid>.jsonl` | Ereignisstrom, eine Zeile je Ereignis, `{type,data,id,timestamp,parentId}`, `producer: copilot-agent` | `session.start`, `user.message`, `assistant.turn_start`, `assistant.message` (mit `content`, `toolRequests[]` = Name + Argumente, **`reasoningText`**), `tool.execution_start` (`toolName`, `arguments`), `tool.execution_complete`, `assistant.turn_end` |

**Messwerte aus einer echten (abgeschlossenen) DS-Sitzung im Decomp-Fenster** `[beobachtet: `transcripts\d9a1ed1b….jsonl`]`:
- 868 Zeilen; `user.message = 1`; `assistant.message = 168`; `assistant.turn_start/end = 168`; `tool.execution_start = 181`; `tool.execution_complete = 181`.
- → **Eine** Nutzereingabe (die Batch-Anweisung) führte zu **168 Assistentenschritten mit 181 Toolausführungen**. Genau das „DeepSeek soll lange autonom arbeiten" ist also heute schon technisch der Fall; der Engpass ist der **Übergabepunkt an Claude**, nicht die Laufzeit.
- Zweite DS-Sitzung `2267781a`: 257 Zeilen, 48 Assistentenschritte, 56 Toolausführungen `[beobachtet]`.
- In **diesem** Fenster: `c229ea97` (diese Sitzung) 337 Zeilen / 47 Schritte / 97 Toolausführungen; `0074a362` 50 Zeilen / 9 / 11 `[beobachtet]`.

**Konsequenz für die Snapshot-Mechanik (Stufe 2, Abschnitt G):** Der komplette Verlauf inkl. Tool-Name + Argumenten **und** Reasoning liegt als JSONL vor — ohne VS-Code-API, ohne UI-Automatisierung. Festlegung laut Auftrag: **Standard-Snapshot aus `content` + Tool-Namen**, `reasoningText` **nur** als Rohdatei (nicht in den Claude-Kontext). Dateien sind append-only Ereignisströme; der Snapshot kann also inkrementell („seit letztem Lesepunkt") gebaut werden.

### L3 Rechte, Autonomie, Grenzen
- `permissionLevel` wird **pro Sitzung** geführt und ist im Chat-Datei-Zustand sichtbar: in **allen drei** lesbaren DS-Chats des Decomp-Fensters steht `autoApprove` `[beobachtet: `chatSessions\2267781a…`, `d9a1ed1b…`]` — d. h. der bisherige DS-Betrieb läuft **ohne Rückfragen**.
- Gegenbeispiel in diesem Fenster: Chat `0074a362` startete mit `default` und wurde per Patch auf `autoApprove` gesetzt `[beobachtet: `{"kind":1,"k":["inputState","permissionLevel"],"v":"autoApprove"}`]`.
- Default-Rechtlevel-Optionen und Automatik-Schalter (`chat.permissions.default` ∈ default | autoApprove | autopilot, `/autoApprove`, `chat.tools.global.autoApprove`) `[beobachtet: `analysis/ghidra-mcp-notes.md`, Abschnitt „VS Code: Freigaben & Dauer-Verfügbarkeit"]`.
- **Autonomie-Deckel:** `chat.agent.maxRequests: 500000` in `%APPDATA%\Code\User\settings.json` `[beobachtet]` — praktisch unbeschränkt viele Agent-Schritte pro Anfrage; die Begrenzung ist das Token-/Kontingent-Budget, nicht die Schrittzahl.
- Netz-/Aufmerksamkeitshebel für 24/7 (offiziell, noch nicht genutzt): `chat.notifyWindowOnResponseReceived` und `chat.notifyWindowOnConfirmation` (Ereignis-OS-Benachrichtigung) `[offiziell: https://code.visualstudio.com/docs/chat/chat-overview]`.

### L4 Einen neuen DS-Chat starten
**Offiziell dokumentiert (und lokal als Hilfe verifiziert)** `[offiziell: https://code.visualstudio.com/docs/configure/command-line#_start-chat-from-the-command-line ; `code chat --help`]`:

| Flag | Bedeutung (Wortlaut der Hilfe) |
|---|---|
| *(kein Flag)* | Chat für das **aktuelle Arbeitsverzeichnis**; Fensterauflösung nicht dokumentiert |
| `-m, --mode <mode>` | `ask`, `edit`, `agent` **oder die Kennung eines Custom-Agent**, Default `agent` |
| `-a, --add-file <path>` | Datei als Kontext anhängen |
| `-r, --reuse-window` | „Force to use the last active window for the chat session." |
| `-n, --new-window` | „Force to open an empty window for the chat session." |
| `--maximize` | Chat-Ansicht maximieren |
| stdin | `… \| code chat <prompt> -` liest den Prompt aus stdin |

Zusatzbefund: Custom-Agenten werden als Modus **über eine Kennung** angesprochen; in dieser Sitzung lautet die Kennung des Plan-Modus z. B. `vscode-userdata:/c%3A/…/github.copilot-chat/plan-agent/Plan.agent.md` `[beobachtet: `chatSessions\c229ea97….jsonl`]` → die Kennung eines Projekt-Agenten wie „Ghidra RE" ist **nicht** offensichtlich und gehört in die Testliste.

**Die sieben Fragen (a)–(g) sind offen** `[nicht geprüft]` — Tests vorbereitet, aber auf Nutzerentscheidung **nicht ausgeführt** (Wortlaut der Prompts in Anhang B):
(a) in welchem Fenster/Workspace der Chat landet · (b) ob es ein **neuer** Chat ist · (c) welche **neuen** Dateien in `transcripts/` und `chatSessions/` entstehen und wie sie zuzuordnen sind · (d) `selectedModel` und `permissionLevel` daraus · (e) ob das Ghidra-Tool verfügbar ist (Test 2) · (f) ob `code chat` sofort zurückkehrt oder blockiert und mit welchem Exit-Code · (g) ob `assistant.turn_end` im Transcript erscheint.

**Bekannte Vorbedingungen aus dem Projekt** (gelten auch für `code chat`): Ghidra-Server + Bridge **vor** der Chat-Sitzung starten; die MCP-Tool-Verfügbarkeit wird **pro Sitzung eingefroren** (VS-Code-Bugs #334569 / #328189, Details in §M3) — ein Retry im selben Chat hilft nicht, nur ein **neuer Chat**.

### L5 Offene Frage: Abbruch eines laufenden Turns von außen (nur recherchiert, nicht ausprobiert)
**Belegt aus offizieller Doku** `[offiziell: https://code.visualstudio.com/docs/chat/chat-overview]`:
- Während eine Anfrage läuft, wird der Senden-Knopf zu einem Menü mit **drei** Wegen: **Add to Queue** (aktuelle Antwort läuft ungestört weiter), **Steer with Message** („signals the current request to yield after finishing the current tool execution" — die laufende Antwort stoppt, die neue Nachricht wird sofort verarbeitet), **Stop and Send** (bricht die laufende Anfrage vollständig ab und sendet sofort die neue Nachricht).
- Standardverhalten konfigurierbar: `chat.requestQueuing.defaultAction` = `steer` (Default) oder `queue`.
- **Wirkung eines Abbruchs:** „Stopping a request doesn't undo file edits, terminal commands, or other actions that already completed." Zurücknehmen lassen sich nur **Workspace-Dateien und Chat-Verlauf** über einen **Checkpoint** („checkpoints don't reverse changes to external services").
- Für geplante Läufe (Automations) ist ein Stopp dokumentiert als „Stop for the running session in History" `[offiziell: https://code.visualstudio.com/docs/agents/run/automations]`.
- Sitzungen sind **wiederherstellbar**: beim Neuladen des Fensters werden Chats inkl. Verlauf wiederhergestellt `[offiziell: https://code.visualstudio.com/docs/agents/run/sessions/manage-sessions]`.

**Nicht belegt / zu testen** `[nicht geprüft]`:
- Ein **reiner** Stopp-Knopf ohne neue Nachricht (die Doku beschreibt nur „Stop and Send").
- **Kein** Stopp-/Abbruch-Flag im `chat`-Unterbefehl der CLI (Hilfetext enthält keines) `[beobachtet]` — ob `code chat` einen laufenden Turn überhaupt beenden kann, ist damit offen.
- Wirkung von **Fenster schließen** oder **Prozess beenden** (`taskkill` auf `Code.exe`/Extension-Host/Agent-Host) auf einen laufenden Turn und auf **halbgeschriebene** Session-/Transcript-Dateien (append-only JSONL → Risiko einer unvollständigen letzten Zeile).
- **Ghidra-seitige Folgen:** MCP-Schreiboperationen (Umbenennen, Kommentare, Tags) sind aus Chat-Sicht „external services" und damit **nicht** durch einen Checkpoint rücknehmbar. Ob sie sofort in der Ghidra-Projektdatenbank landen oder erst beim `save_program`, ist `[nicht geprüft]` — **STRONG INFERENCE**: die Projektnotizen zeigen MCP-Schreibwerkzeuge (`rename…`, `add_function_tag`, `save_program`) direkt auf der geöffneten Projekt-DB; für die Abbruch-Semantik in Stufe 2 muss das geprüft werden (Punkt in §Risiken).

### L6 Weitere Steuerkanäle (offiziell)
- **Automations** (Preview, Agents-Fenster, `chat.automations.enabled`, auf Stable standardmäßig aus): gespeicherter Prompt + Workspace + Agent + Modell + Rechte, Schedule **manual | hourly | daily | weekly**, „Run now", Verlauf, Export/Import als `.automation.md`. Doku-Vorbehalte: läuft **nur bei laufendem Agent-Host bzw. offenem VS-Code-Fenster**, **eine** Automation läuft gleichzeitig, verpasste Termine werden nicht verlässlich nachgeholt `[offiziell: https://code.visualstudio.com/docs/agents/run/automations]`. Eignung als Watchdog-Takt `[nicht geprüft]`.
- **Agent-Host-Session-Werkzeuge:** ein Agent kann Sessions/Chats anlegen und Nachrichten an andere Sessions senden — aber „Sending a message to another session always requires your confirmation"; außerdem keine Nachricht an den eigenen Chat `[offiziell: https://code.visualstudio.com/docs/agents/run/sessions/manage-sessions]` → für einen **unbeaufsichtigten** Loop nicht geeignet.
- **`/fork`** (Command `workbench.action.chat.forkConversation`) erzeugt eine neue Sitzung **mit** dem bisherigen Verlauf — laut Projektnotizen ist ein Fork zum **Tool-Refresh untauglich**, weil er die eingefrorene Tool-Liste erbt `[beobachtet: `analysis/ghidra-mcp-notes.md`]`.

### L7 Copilot-spezifische Befunde, die das Harness einplanen muss
- **Tool-Snapshot pro Sitzung** (offener VS-Code-Bug, im Projekt ausführlich belegt): MCP-Tools landen nur über `request.toolReferences` in `availableTools`; fällt das Request-Parsing in das Discovery-Fenster, friert der Client eine Teilmenge ein und lehnt den Rest mit „Tool … is currently disabled by the user" ab. Zwei Issues: `microsoft/vscode#334569`, `microsoft/vscode#328189`; Fix-PRs nicht gemerged. Belegstelle: `analysis/ghidra-mcp-notes.md`, Abschnitt „VS Code: MCP-Tool-Enablement" `[beobachtet: Datei]`.
- Daraus abgeleitete **Arbeitsregel des Projekts:** Server + Bridge **vor** der Chat-Sitzung hochfahren, dann **neue** Sitzung starten; `--lazy` (nur `CORE_GROUPS` = listing/function/program, ≈89 Tools) hält das Discovery-Fenster klein; bei Ablehnung **neuen** Chat öffnen statt retryen; HTTP-Ersatzweg über `scripts/ghidra_http.ps1` `[beobachtet: `analysis/ghidra-mcp-notes.md`, `scripts/start-mcp-bridge.ps1`]`.
- Sitzungsgebunden heißt auch: Nach einem Bridge-/Server-Neustart oder einer `mcp.json`-Änderung sind die Tools erst in einer **neuen** Sitzung verfügbar.

---

## M. Ghidra MCP

### M1 Die reale Kette (ohne GUI)
`[beobachtet: `g:\Silent Scope Decomp\.vscode\mcp.json`, `scripts\start-mcp-bridge.ps1`, `scripts\start-ghidra-headless.ps1`, `logs\ghidra-headless-20260925-164501.out.log`]`

1. **VS Code** liest die **Ordner**-Konfiguration `Silent Scope Decomp\.vscode\mcp.json`:
   `type: stdio`, `command: powershell.exe`, `args: -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ${workspaceFolder}/scripts/start-mcp-bridge.ps1`.
2. **Wrapper** `scripts\start-mcp-bridge.ps1`: prüft `http://127.0.0.1:8089/get_metadata`; läuft der Server nicht, startet er `scripts\start-ghidra-headless.ps1` versteckt als Hintergrundprozess (Logs nach `logs\ghidra-headless-<zeitstempel>.out/.err.log`) und wartet bis zu **300 s**; danach startet er die Bridge. Diagnose **nur** auf stderr + `logs\mcp-bridge.log` (stdout gehört dem MCP-Protokoll). Bridge-Auflösung in dieser Reihenfolge: `<ws>\tools\bridge-venv\Scripts\bridge-mcp-ghidra.exe` → `uv run --directory tools\ghidra-mcp bridge-mcp-ghidra` → `python -m bridge_mcp_ghidra`; gestartet wird mit **`--lazy`**.
3. **Headless-Server** `scripts\start-ghidra-headless.ps1`: JDK 21 aus `tools\jdk21`, Ghidra `ghidra_12.1.2_PUBLIC`, Projekt `ghidra\sscope-uad.gpr`, Programm `/830d01.27p.be.bin`, Port **8089**.
4. **Nachweis heute 16:45:01** (in diesem Fenster!): Log zeigt „Opened project: sscope-uad", „Loaded program from project: 830d01.27p.be.bin", „Registered **245** REST API endpoints" `[beobachtet]`.
5. **Live-Gegenprobe jetzt:** `GET http://127.0.0.1:8089/get_metadata` → **HTTP 200**, `Program Name: 830d01.27p.be.bin`, `Language: PowerPC:BE:32:default`, `Base Address: ffe00000`, `Total Memory Size: 2097152`, `Function Count: 21`, `Symbol Count: 55` `[beobachtet]`. Der Server läuft also, obwohl nur dieses Fenster offen ist — er ist ein **eigener Prozess**, nicht an ein Fenster gebunden.

### M2 Prozess-Lebensdauern (für 24/7 entscheidend)
| Komponente | Lebensdauer | Kennzeichnung |
|---|---|---|
| Ghidra-Headless-Server (java, Port 8089) | **dauerhaft**, bis zum Reboot oder manuellen Beenden; überlebt das Schließen von VS Code | `[beobachtet: Log- und Port-Nachweis; `[STRONG INFERENCE]` für „überlebt Fensterschließen"]` |
| Bridge (`bridge-mcp-ghidra`, stdio) | **pro VS-Code-Fenster/Sitzung** — VS Code startet sie aus `mcp.json` | `[beobachtet]` |
| MCP-Tool-Snapshot im Chat | **pro Chat-Sitzung** eingefroren | `[offiziell: VS-Code-Issues + Projektnotizen]` |
| Ghidra-Projektdatei | `ghidra\sscope-uad.rep\` ist gitignoriert; Änderungen (Namen, Kommentare) gehören zum lokalen Arbeitsstand | `[beobachtet: readme.md]` |

### M3 Grenzen und Fallstricke (Projektwissen, verdichtet)
- Script-Endpunkte der Bridge sind standardmäßig **aus** (`GHIDRA_MCP_ALLOW_SCRIPTS=1` nötig); `.py`-Ghidra-Skripte bräuchten die Jython-Extension `[beobachtet: `analysis/ghidra-mcp-notes.md`]`.
- **Mehrprogramm-Betrieb:** der frisch gestartete Server hat nur `/830d01.27p.be.bin` offen; das PPC-Hauptprogramm `/830d01.27p.main.bin` (Base `0x80000000`) ist nach jedem Serverneustart weg und wird per `POST /load_program_from_project` nachgeladen `[beobachtet: ebd.]`.
- **PowerShell-Fallstrick:** die Projekt-`.ps1` tragen Mark-of-the-Web; Aufrufe brauchen `-ExecutionPolicy Bypass` (so macht es `mcp.json`) `[beobachtet: ebd.]`.
- `.vscode/mcp.json` ist **portabel** (`${workspaceFolder}`), `Silent Scope Decomp.code-workspace` nutzt `"path": "."` `[beobachtet: Dateien]`.
- Agent-Host-Sonderfall: der Agent Host liest `.vscode/mcp.json` **nicht** direkt, sondern bekommt die Server weitergereicht; nativ liest er `.mcp.json` (Wurzel) und `~/.copilot/mcp-config.json` `[offiziell: https://code.visualstudio.com/docs/copilot/customization/mcp-servers]`. Welcher Harness hier läuft (Local vs. Agent Host), ist **nicht abschließend bestimmt** `[nicht geprüft]` — Aufschluss gäbe die Agent-Debug-Ansicht bzw. `Developer: Open Agent Debug Logs`.
- Automatischer Start: `chat.mcp.autostart`, Default `newAndOutdated`, startet Server beim Absenden einer Chat-Nachricht `[offiziell: ebd.]`.

### M4 Anforderung für Stufe 2 (festgehalten, wie beauftragt)
**Harte Reihenfolgeregel:** *Ein neuer DS-Chat darf erst gestartet werden, wenn der Ghidra-Server auf `127.0.0.1:8089` nachweislich erreichbar ist* (Prüfung `GET /get_metadata`).
**Begründung:** Die MCP-Tool-Verfügbarkeit wird **pro Chat-Sitzung eingefroren** — ist die Registrierung beim Sitzungsstart unvollständig, bleiben die fehlenden Tools für die ganze Sitzung gesperrt („disabled by the user"), Retry hilft nicht `[offiziell/Projektbeleg: `analysis/ghidra-mcp-notes.md`, VS-Code #334569/#328189]`. Das Harness muss also: Server prüfen → ggf. starten/warten → **dann** die Sitzung eröffnen; und in einem laufenden Batch **keinen** Bridge-/Server-Neustart zulassen.

---

## Entscheidungsvorlage: wie wird DeepSeek automatisiert?

### Vergleichstabelle
Bewertung 1 (schlecht) bis 5 (gut). Kriterien wie beauftragt, zusätzlich **Abbruchfähigkeit** und **24/7 ohne Desktop-Session**.

| Kriterium | (a) VS Code/Copilot automatisieren | (b) Headless Agent-CLI + DeepSeek-API | (b′) **Claude Code als DS-Worker** über DeepSeeks Anthropic-Endpunkt | (c) eigener Agent-Loop im Harness |
|---|---|---|---|---|
| Setup-Treue zu heute | **5** — identische Instruktionen, Memory, MCP, Tool-Gating, BYOK-Modell | 2 — Copilot-Memory u. VS-Code-Tools fehlen | 3 — Regelwerk + MCP nachbaubar, Memory/VS-Code-Tools fehlen | 1 — alles neu |
| Aufwand | 4 (niedrig: `code chat` + Dateien lesen) | 3 (Installation unbekannt, Node fehlt) | **4** (Claude Code wird für den Reviewer ohnehin installiert) | 2 (hoch) |
| Risiko | 3 — GUI-/Fenster-Abhängigkeit, undokumentierte Fensterwahl, Tool-Snapshot-Bug | 2 — nichts lokal verifiziert | 2 — `[nicht geprüft]`, aber dokumentierter Pfad + getrennte Prozesse | 2 — zweite Wissensbasis, viel Eigenbau |
| **Abbruchfähigkeit** | 2 — UI „Stop and Send" belegt, **kein** CLI-Stopp; Checkpoints nur für Workspace-Dateien/Verlauf | 3 — Prozess-Signal möglich (nicht verifiziert) | **4** — `claude -p` ist ein normaler Prozess (Signal/Timeout), kein Fenster nötig | 5 — vollständig selbst kontrolliert |
| **24/7 ohne Desktop-Session** | 1 — braucht angemeldete Desktop-Sitzung (Auto-Logon/RDP) + offenes Fenster | 4 | **5** — Terminalprozess, auch per Dienst/Aufgabenplanung ohne sichtbaren Desktop | 5 |
| Kontingent/Kosten | Copilot-/BYOK-Kontingent des Nutzers (heute $0.15/$0.6 je 1M, „Off-peak") | DeepSeek-API direkt | DeepSeek-API direkt | DeepSeek-API direkt |
| Wissensbindung | Copilot-Memory + `analysis/` | `analysis/` (+ Memory-Verlust) | `analysis/` (+ Memory-Verlust) | `analysis/` |

### (a) VS Code/Copilot automatisieren — Details
**Wie:** `code chat` mit dem Claude-Instruktionstext startet den DS-Lauf; Claude liest den Zustand aus `transcripts\*.jsonl` + `chatSessions\*.jsonl` (plus `analysis/`-Dateien) und schreibt die nächste Instruktion; Batch-Ende/Recovery liest ebenfalls diese Dateien. Kein Klickpfad, keine UI-Automatisierung nötig.
**Wofür es spricht:** 1:1 derselbe Lauf wie heute (dieselben 168-Schritte-Stränge), null Regeländerung, BYOK-Modell und Auto-Approve wie bisher, Ghidra-MCP-Kette unverändert.
**Risiken (wie beauftragt ergänzt):**
1. **VS Code ist eine GUI-App:** 24/7-Betrieb setzt eine **angemeldete Desktop-Sitzung** voraus (Auto-Logon oder dauerhaft offene RDP-Sitzung); „Fenster/Minimiert/Abgemeldet" ist ungeprüft `[nicht geprüft]`.
2. **Abbruchfähigkeit ungeklärt:** kein CLI-Stopp dokumentiert; „Stop and Send" existiert nur als UI-Weg; Checkpoints stellen Workspace-Dateien und Chat-Verlauf wieder her, **nicht** externe Effekte (u. a. Ghidra-MCP-Schreibzugriffe) `[offiziell: chat-overview]`.
3. **Modell-/Rechte-Erzwingung beim Start ungeklärt:** ob `code chat` mit dem BYOK-Modell `deepseek/deepseek-flash` und `autoApprove` startet (oder mit Default-Modell/`default`-Rechten), weiß man erst nach dem Test `[nicht geprüft]`.
4. Tool-Snapshot-/Gating-Bug des Clients (§L7) — beherrschbar durch die Reihenfolgeregel (§M4), aber ein zusätzlicher Fehlerpfad.
5. Fensterbezogene Speicherorte (A5): landet ein Chat im falschen Fenster, liegen Verlauf und Memory woanders.

### (b) Headless Agent-CLI mit DeepSeek-API + MCP
**Stand der Prüfung:** Auf diesem Rechner ist **kein** Agent-CLI vorhanden (`node`/`npm` fehlen; kein `aider`/`opencode`/`crush`-Eintrag gefunden) `[beobachtet]`. Damit sind konkrete Kandidaten **nicht verifizierbar** und werden hier **nicht** benannt `[nicht geprüft]`. Ohne Node (oder mit zusätzlicher Installation) wäre das Setup zudem nur teilweise zu reproduzieren.
**Bewertung:** heute nicht empfehlbar; als Ausweichweg auch nicht nötig, weil (b′) denselben Nutzen mit einem bereits geplanten Werkzeug bietet.

### (b′) Claude Code als DeepSeek-Worker über DeepSeeks Anthropic-Endpunkt
[nur dokumentiert, nichts getestet — Claude Code ist nicht installiert `[beobachtet]`]

**Offiziell belegte Grundlage** `[offiziell: https://api-docs.deepseek.com/guides/anthropic_api und …/quick_start/agent_integrations/claude_code]`:
- `base_url` = `https://api.deepseek.com/anthropic`; Konfiguration über `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` (Windows-Beispiel der Doku: `$env:ANTHROPIC_BASE_URL=…`, `$env:ANTHROPIC_AUTH_TOKEN=…`).
- Modellnamen: `deepseek-flash[1m]`, `deepseek-v4-pro`, `deepseek-v4-flash`; **Claude-Namen werden gemappt** (`claude-opus*` → `deepseek-v4-pro`, `claude-haiku*`/`claude-sonnet*` → `deepseek-flash`) — ein falscher Modellname führt also nicht zum Abbruch, sondern zu einem anderen DeepSeek-Modell.
- Tool-Unterstützung: `tools` (`name`/`input_schema`/`description`) **voll unterstützt**, `tool_choice` none/auto/any/tool unterstützt; `thinking` unterstützt (`budget_tokens` ignoriert).
- **Wichtig:** das API-Feld `mcp_servers` wird **ignoriert** — serverseitige MCP-Anbindung gibt es nicht. Lokale (clientseitige) MCP-Server sind davon nicht betroffen; laut Nutzerangabe funktionieren lokale MCP-Server mit dem OAuth-Token `[Nutzerangabe]`, die exakte Konfigurationsdatei/-flags ist `[nicht geprüft]`.
- `cache_control` wird **ignoriert** (keine explizite Cache-Steuerung über das Anthropic-Feld).

**Antworten auf die vier gestellten Fragen:**
1. **Übernahme von `AGENTS.md`, `ghidra-re.agent.md` und der MCP-Kette ohne Änderung am Decomp-Repo?**
   - MCP: `scripts/start-mcp-bridge.ps1` ist ein reiner stdio-Wrapper und **nicht** VS-Code-spezifisch — eine Claude-Code-MCP-Konfiguration **außerhalb** des Repos (z. B. im Harness-Ordner) könnte denselben Wrapper mit demselben `--lazy` aufrufen; die harte Voraussetzung (Server muss vorher laufen) bleibt. `[STRONG INFERENCE, nicht geprüft]`
   - `AGENTS.md`: Für den Claude-Harness ist die Projekt-Instruktionsdatei **`CLAUDE.md`** (Wurzel) bzw. `.claude/CLAUDE.md` / `.claude/rules` — `AGENTS.md` steht dort **nicht** in der Liste `[offiziell: https://code.visualstudio.com/docs/copilot/customization/custom-instructions]`. Ohne Repo-Änderung müsste der Inhalt also über einen Claude-Code-Mechanismus (z. B. System-Prompt-Option oder eine Harness-seitige Kopie) eingespeist werden `[nicht geprüft: welche Option das leistet]`.
   - Custom Agent „Ghidra RE": Claude Code kennt eigene Agenten-/Regel-Dateien (`.claude/agents/**`, `.claude/rules`) `[offiziell: VS-Code-Doku nennt diese Pfade als Claude-Format]`; das genaue Pendant zu `.github/agents/*.agent.md` ist `[nicht geprüft]`.
2. **Welche Copilot-Befunde entfallen oder ändern sich?**
   - **Entfällt:** das session-gebundene Einfrieren der MCP-Tool-Liste („disabled by the user") — es ist ein VS-Code-Client-Bug (#334569/#328189) und hängt an `availableTools` des Copilot-Requests. Ein CLI-Agent hat diesen Pfad nicht.
   - **Entfällt ebenfalls:** die Regel „bei Tool-Ablehnung neuen Chat öffnen"; und die Notwendigkeit, ein *Fenster* zu führen.
   - **Neu/anders:** der MCP-Server muss vom Harness/CLI **selbst** gestartet werden (kein `chat.mcp.autostart`), also übernimmt das Harness die Reihenfolgeregel (§M4) aktiv; und die Tool-Liste wird pro **Prozessstart** gebildet, nicht pro Chat-Sitzung.
3. **Welche Projektwerkzeuge setzen PowerShell voraus?**
   - **35** `.ps1` in `scripts\`, u. a. `port_build.ps1` (Bauen inkl. GL-Ziel), `setup_mesa.ps1` (Software-OpenGL), `start-ghidra-headless.ps1`, `start-mcp-bridge.ps1`, `ghidra_http.ps1`, `ppc_*_run.ps1`, `playtest-gl.ps1`, `screenshot-mame*.ps1` `[beobachtet]`.
   - `AGENTS.md` verlangt Aufrufe mit `-ExecutionPolicy Bypass` und verbietet, `preflight.py` durch eine Konsole-Pipe zu schicken (`*>` in eine Datei) `[beobachtet: AGENTS.md]`.
   - Folge für (b′): Claude Code müsste diese Aufrufe in einer PowerShell-Umgebung fahren können; welche Shell der Terminal-Werkzeugkasten nutzt und ob sie konfigurierbar ist, ist `[nicht geprüft]`.
4. **Was geht gegenüber (a) verloren?**
   - Das **Copilot-Memory** (`/memories/repo`, im Decomp-Fenster aktiv; Repo-Spiegel `analysis/_memory/` mit 20 Dateien) hat in Claude Code **kein** Pendant; der Spiegel bleibt als Projektwissen, wird aber nicht mehr automatisch in jeden Lauf injiziert `[beobachtet + STRONG INFERENCE]`.
   - **VS-Code-spezifische Werkzeuge** des heutigen Lookups: `vscode`, `vscodeTasks`, `vscodeGeneral`, `vscodeBrowser`, `runInTerminal`/`getTerminalOutput`/`killTerminal`, Aufgaben aus `.vscode/tasks.json` `[beobachtet: `.github/agents/ghidra-re.agent.md`, `.vscode/tasks.json`]`.
   - **Komfort/Belegbarkeit der UI:** Sessions-Listen, Checkpoints/Undo von Dateiänderungen (Doku: Checkpoint-Wiederherstellung für Dateien und Chat-Verlauf), Chat-Debug-Ansicht (`Developer: Open Agent Debug Logs`, „raw system prompt, user prompt, context, and tool payloads") `[offiziell: chat-overview]`.
   - Dafür **gewonnen:** echte Abbruch-/Timeout-Fähigkeit (Prozess), Betrieb ohne Desktop-Sitzung, exaktere Exit-Codes, Parallelität mehrerer Prozesse mit getrennter Konfiguration (Worker = DeepSeek-Endpunkt, Reviewer = Abo) — genau die Rollentrennung des Auftrags.

### Empfehlung der Inventur
1. **MVP auf (a) aufsetzen** (der heutige manuelle Loop 1:1, keine Regeländerung), aber die vier offenen Punkte aus §L4 vorher testen — vor allem (f) Exit-Code/Blockierverhalten, (a) Fensterziel, (d) Modell/Rechte.
2. **(b′) parallel als „Plan B" prüfen**, sobald Claude Code für den Reviewer installiert ist (Installation durch den Nutzer, nicht in Stufe 1): Es adressiert genau die zwei Schwachpunkte von (a) — Abbruchfähigkeit und 24/7 ohne Desktop-Sitzung — und erzwingt keine Repo-Änderung.
3. **(b) und (c) nicht weiterverfolgen**, solange (a)/(b′) tragen: (b) ist lokal nicht verifizierbar (kein Node/kein CLI), (c) erzeugt eine zweite Wissensbasis und dupliziert Tool-Schema, Approval und Kontextverwaltung.

---

## Offene Punkte / Risiken (Eingang in Stufe 2)

1. **`code chat`-Semantik** — die sieben Fragen (a)–(g) aus §L4; Testprompts liegen in Anhang B.
2. **Custom-Agent-Kennung** für `-m` (z. B. „Ghidra RE") ist unbekannt; nur eine Pfad-Kennung wurde beobachtet (§L4).
3. **Abbruch von außen** (§L5): UI-Weg belegt, CLI-Weg nicht; Wirkung von Fensterschließen/Prozess-Kill auf halbgeschriebene JSONL-Zeilen ungeprüft.
4. **Ghidra-Persistenz bei Abbruch:** landen MCP-Schreibzugriffe sofort in der Projekt-DB? (→ behandelt die Auftragsforderung „Umgang mit bereits in die Ghidra-DB geschriebenen MCP-Änderungen").
5. **Rechte-/Modell-Erzwingung beim Start** (`autoApprove`, BYOK-Modell) — hängt an Punkt 1(d).
6. **Kontingent-Bremse:** Per-Nutzungslimits sind der Engpass; mechanische Vorfilterung, Watchdog nur bei Signal bzw. spätestens alle 60–90 min, „Limit erreicht" als regulärer Zustand (Auftrag) — Design in Stufe 2.
7. **Zwei Rechner/Git:** exklusiver Schreib-Lock, Branch-/Push-Strategie (Auftrag) — zusätzlich zu beachten: der Workspace-Hash und damit Memory/Verlauf ist pfadabhängig (§A5).
8. **Windows-24/7:** Auto-Logon/RDP-Verhalten, wenn ein Fenster nötig ist; Ghidra-Headless ist als eigener Prozess dafür unkritisch (§M2).
9. **Telegram:** Erreichbarkeit belegt, Paketlage leer (§A7); Autorisierung/Queue/Locking erst Stufe 2.
10. **Harness (Local vs. Agent Host) ist nicht bestimmt** (§M3) — beeinflusst, welche Instruktions- und MCP-Pfade greifen (`.github/instructions` vs. `~/.copilot/…`).
11. **Zwei 1-Zeilen-Chatdateien** im Decomp-Fenster (Inhalt nur `{`) — Bedeutung `[nicht geprüft]`; relevant, weil das Harness Chat-Dateien als Zustandsquelle liest und unfertige Dateien nicht als Session werten darf.

---

## Quellen
- Offiziell VS Code: Command Line Interface (`code chat`) · MCP-Server · Custom Instructions · Chat-Sessions/Manage Agent Sessions · Automations · Chat-Übersicht (`Stop and Send`, Benachrichtigungen).
  Basis-URLs: `https://code.visualstudio.com/docs/configure/command-line`, `/docs/copilot/customization/mcp-servers`, `/docs/copilot/customization/custom-instructions`, `/docs/agents/run/sessions/manage-sessions`, `/docs/agents/run/automations`, `/docs/chat/chat-overview` (alle am 2026-09-25 gelesen).
- Offiziell DeepSeek: Anthropic-Kompatibilität (`https://api-docs.deepseek.com/guides/anthropic_api`) und Claude-Code-Integration (`…/quick_start/agent_integrations/claude_code`).
- Projektintern (beobachtet, im Repo): `AGENTS.md`, `readme.md`, `.github/agents/ghidra-re.agent.md`, `.vscode/mcp.json`, `analysis/ghidra-mcp-notes.md`, `analysis/_memory/*`, `scripts/start-mcp-bridge.ps1`, `scripts/start-ghidra-headless.ps1`, `scripts/m151_memory_sync.py` (nur gelesen).
- Lokale Messungen: `git status`/`log`, `Get-Process Code`, `Get-Command`, `code --version`, `code chat --help`, `Invoke-WebRequest` gegen `127.0.0.1:8089` und `api.telegram.org`, Auswertung von `workspaceStorage\*.json`, `chatSessions\*.jsonl`, `transcripts\*.jsonl`.

## Anhang A — Messprotokoll (Kurzform)
- Repos: `git status --porcelain` beide leer (vorher und nachher); HEAD `4a1e6cd` (Harness) / `e439bd7` (Decomp, = `origin/main`).
- Fenster: nur `Pasted text #1 - Harness (Workspace) - Visual Studio Code` (PID 12960).
- Werkzeuge: `code` 1.139.1; `python` 3.12.1; `git` 2.43.0; `g++` MinGW.org 6.3.0; `node`/`npm`/`claude` nicht gefunden; 35 `.ps1` in `scripts\`.
- Ghidra: `GET /get_metadata` → HTTP 200 (830d01.27p.be.bin, PowerPC:BE:32:default, Base ffe00000, 2 MiB, 21 Funktionen, 55 Symbole); Headless-Log von 16:45:01 mit „Registered 245 REST API endpoints".
- Telegram: `https://api.telegram.org` → HTTP 200 (ohne Token).
- Python-Pakete: PATH-Python und Bridge-venv ohne Telegram-Paket (Bridge-venv hat `httpx`, `mcp`).
- Session-Dateien (vorher = nachher, da nichts lief): Decomp-Fenster `764c8a21` → 4 `chatSessions` (2267781a 79 Zeilen, d9a1ed1b 94, 9c93b434 1 = `{`, f0276410 1 = `{`) und 2 `transcripts`; dieses Fenster `474534` → 2 `chatSessions` (0074a362, c229ea97) und 2 `transcripts`.

## Anhang B — vorbereitete Tests (wortgleich, NICHT ausgeführt)
Vorbedingung war erfüllt: Server über `127.0.0.1:8089/get_metadata` erreichbar (HTTP 200) — die Ausführung wurde dennoch auf Nutzerentscheidung gestrichen, weil nur das Harness-Fenster offen war und die Fensterauflösung von `code chat` nicht belegt ist.

**Test 1 (ohne Tools), Arbeitsverzeichnis `G:\Silent Scope Decomp`, Ask-Modus:**

```
code chat -m ask "HARNESS-TEST. Keine Tools verwenden, keine Dateien lesen oder ändern, keinen Batch beginnen. Antworte nur mit: TEST1-OK"
```

**Test 2 (MCP-Nachweis), Arbeitsverzeichnis `G:\Silent Scope Decomp`, Custom-Agent „Ghidra RE":**

```
code chat -m "<Custom-Agent `Ghidra RE`>" "HARNESS-TEST. Rufe genau einmal get_metadata über das Ghidra-MCP auf, sonst keine Tools, keine Dateiänderungen, keinen Batch beginnen. Antworte nur mit dem Programmnamen aus der Antwort und TEST2-OK"
```

**Je Test zu protokollieren (a)–(g):** Fenster/Workspace · neuer Chat ja/nein · neue Datei in `transcripts/` und `chatSessions/` + Zuordnung · `selectedModel` und `permissionLevel` · Ghidra-Tool verfügbar (nur Test 2) · Rückkehrverhalten und Exit-Code · `assistant.turn_end` im Transcript.

**Zusätzlich vor jedem späteren DS-Start zu prüfen (Reihenfolgeregel §M4):** `GET /get_metadata` = HTTP 200, sonst **kein** neuer Chat.
