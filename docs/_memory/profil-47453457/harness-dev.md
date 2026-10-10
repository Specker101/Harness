# Harness (g:\Harness) — Entwickler-Notizen


- **R13bw-13 (2026-10-07, gepusht `54186d2`, Gate 1665 Tests OK).** Die Preflight-Sperre
  prueft jetzt **OFFEN** statt vorhanden: `tools/batch_uhr._nachrueckliste_offen` = Auftrag
  traegt den Abschnitt UND `worker.nachrueckliste_marker(lauf)` ist leer. Der Marker zaehlt
  nur **Worker-Aeusserungen** (`antwort*.md`, `text`-Bloecke des LIVE gelesenen
  `stream.jsonl`) — `thinking` (Erwaegung) und `user` (die Anweisung `ERLEDIGT_TEXT`) NICHT.
  **S2**: `streamjson.langlauf_aufruf` sperrt `hybrid_lauf`, `port_regression`,
  `m2*_lang*.py` ab Marker oder ab `Schwelle-30min` (`--schritte` < 200M frei) → Beleg
  `runs/b<N>/langlauf-blockiert.jsonl`. **Fallstricke der Erkennung:** Pfade mit Leerzeichen
  (`G:\Silent Scope Decomp\…`) — `\S*[\\/]` scheitert, im `&`-Zweig `.*[\\/]` nehmen; die
  zweistufige Form `$exe="…hybrid_lauf.exe"; & $exe --schritte …` braucht die Alias-Aufloesung;
  Abfrage-/Lese-Segmente (`Get-CimInstance`, `git add`, `python -c "import …"`) ausschliessen.

- **R13bw-9/10 (2026-10-06, gepusht `7050a13`).** (a) Der **letzte C-Batch** und der B-Lauf
  kommen aus `stand.strang_lauf()` (rueckwaerts ueber die Batch-Ordner) — NICHT aus der
  Preflight-Zeilenreihe (`TREND_FENSTER`+1 = 14 Zeilen, lief bei langem B-Lauf aus und
  druckte „B0"). Reisst die Reihe: `letzter_c = None` + „[UNTERGRENZE …]". (b) **R277-1
  umgesetzt:** der Stations-Stillstand ist KEIN Ausloeser mehr (`aussensicht.station_*` und
  die B-Phasen-Marke sind entfernt); neue Pflichtzeile `BEWEGUNG: ja|nein` im
  `prompts/reviewer.md`, Zaehler „weder Station noch Bewegung" (`stand.fortschritt_zaehler`,
  Schwelle 6), nur Telegram-Hinweis (`orchestrator.fortschritt_hinweis_pruefen` →
  `notify_once`, Schluessel = erster Batch des Laufs) — kein `gruende`-Eintrag, keine Frage.
  Alte Batches ohne Zeile liest `stand._anker_bewegung()` aus dem Ankerkopf nach (Zuordnung:
  Batch, der VOR dem `Bewegung:`-Vermerk genannt ist). Reviewer-Prompt-Aenderung ⇒ neue
  Reviewer-Sitzung (R13ab) ⇒ Zaehler greift erst ab dem ersten Batch mit der Zeile.
  Zum Wirksamwerden muss der **laufende** Harness neu gestartet werden (Agent startet nie neu).

- **Git-History bereinigen (Lehre B261, 2026-10-04): NICHT `git gc --prune=now` laufen
  lassen, bevor geprüft ist, was weg ist.** `git filter-branch --index-filter` entfernt
  die Datei auch aus dem **Arbeitsbaum** (der Filter setzt den Baum auf den neuen Stand) —
  bei getrackten Riesen-Logs war das der ungewollte Datenverlust. Reihenfolge:
  (1) Kopie/`.gz` der Rohdaten sichern, (2) History umschreiben, (3) Arbeitsbaum prüfen,
  (4) erst dann Reflog verfallen lassen + gc. GitHub lehnt Dateien > 100 MB ab, die
  Meldung nennt nur eine. Wache in beiden Repos: `scripts/check_dateigroesse.py`
  (+ `scripts/hooks/pre-commit|pre-push` über `git config core.hooksPath scripts/hooks`);
  große Rohausgaben komprimiert ablegen (`scripts/rohlauf_komprimieren.py`).

- Code liegt unter `g:\Harness\harness` (Paket `hx`), Start: `start.ps1 [-Paused] [-Mock]`.
  Läuft im EIGENEN PowerShell-Fenster außerhalb VS Code; Stop: `stop.ps1 [-Force]`
  (Force = taskkill auf alle `python.exe` mit `hx.cli`), Marker `state/STOP`.
- Steuerkanal lokal = Dateien in `state/ctl/{pause,resume,stop,approve}.ctl` + `instruction.json`.
  Immer über `hx.cli` schreiben (nie per Hand), sonst führt der nächste Start sie aus.
  Wirkung: nächster Schleifendurchlauf, im Pausenzustand bis ~30 s (Telegram-Langpoll 25 s).
- `hx.cli demo` läuft isoliert in `state/_demo_<scenario>` (kopiert `profiles/`); sonst
  schreibt die Attrappe in den echten Eingang.
- Fallstrick: Attribut `self.run` in `hx/watch.py` überschrieb die Methode `run()` →
  neuer Name `self.run_name`. Vor jeder Demoname-Frage: prüfen, ob der Name eine
  Methode des Objekts ist.
- Tests: `python -m unittest discover -s tests` (294 Tests, alle gruen, ohne API-Kosten,
  Stand R13l 2026-09-27).
  R13-Dateien: `tests/test_r13_fixes.py` (Ghidra-Speichern, Rotation/Uebergabe),
  `tests/test_r13b_fixes.py` (Kennung, Rotation/Reuse, gescheiterter Review, Queue, Laufzeit).
- Review-Gueltigkeit (R13b): `orchestrator.review_ok` verlangt Modell + Bloecke + Summary +
  Instruktion mit Batch-Nummer + Profil. Ungueltig ⇒ Rohantwort als
  `runs/b<N>/review-verworfen-<Stempel>-v<N>.md`, EIN Wiederholungsversuch mit
  Format-Erinnerung, danach PAUSED + Telegram + `logs/review-verworfen-<ts>.json` — NIE ein Gate.
- Queue (R13b): `read_queue_block(target, mark=False)` + `commit_queue(...)` — zugestellt
  wird erst nach gueltigem Review.
- Nummern (R13b): Review-Verzeichnis = Anker-Nachfolger (`expected_batch()`), Worker-Belege
  bleiben in `runs/b<state.batch>`; `review_context` liest `antwort.md` aus dem Belegordner.
- Laufzeit (R13b): Wanduhr des Worker-Prozesses — Vorrang `duration_ms` aus dem Mitschnitt,
  sonst Harness-Messung; `duration_harness_s` dient der Rueckstau-Warnung (>120 s ⇒ ALARM).
- Fallstrick (R13b): Bei `new_session=True` MUSS der Aufrufer eine frische Kennung uebergeben —
  die alte Kennung liess Claude Code mit "Session ID … is already in use" sofort abbrechen
  (rc=1, leere Antwort, Modell None).
- Ghidra-Speichern (R13): `worker.save_ghidra_after_batch` läuft in `_finish_run` (vor Push/
  Review), `state.data["ghidra_pending"]` + `last_profile`; Haken in `cancel_check` ("Stopp")
  und `run()`-`finally` ("Harness-Ende") über `orchestrator.save_ghidra_if_pending`.
  Fehler ⇒ `ghidra_failed` ⇒ Push/Review werden übersprungen. Messdatenzeile
  `Ghidra gespeichert: ja/nein/nicht noetig`.
- Reviewer-Rotation (R13): Uebergabe der alten Session via `reviewer.run_handover`
  (Phase "uebergabe", Fehler nicht tödlich) → `sessions/vorherige-session.md`;
  `reviewer.force_rotate=true` in `state/run.json` erzwingt sie einmalig
  (überlebt Neustart; /status zeigt "Wechsel beim naechsten Review erzwungen").
- Attrappe: `ReviewResult.session_id` MUSS bei `new_session=True` eine neue Kennung
  liefern, sonst schlägt die Rotationsprüfung nur wegen der Attrappe fehl.
- R13c-Entscheidungs-Bremse: `protocol.parse_offene_punkte` liest `ENTSCHEIDUNG NOETIG:`
  (bremst: `orchestrator.gate_wait_decision` verhindert die automatische Freigabe im
  Dauerbetrieb), `OFFENE FRAGE:` und `WARTET AUF LIVE-AUFNAHME:` bremsen nicht. Gate traegt
  `offene_punkte`; Altbestand wird aus der gespeicherten Summary abgeleitet (Zustand bleibt
  unberuehrt). Anzeige in `/status` und `watch`.
- R13c-watch: thinking-Bloecke mit Text abgesetzt (`  ~ `, gedimmt, ab 400 Zeichen gekuerzt),
  leere uebersprungen, Schalter `watch --no-thinking`. Rein lesend.
- R13c-Absturzschutz: `Orchestrator.report_crash` (Traceback in Log + `logs/crash-<ts>.txt`
  + Telegram „HARNESS ABGESTÜRZT", Exit-Code 3 über `cmd_run`); `start.ps1` schreibt stderr
  nach `logs/start-stderr.log` und laesst bei Exit≠0 das Fenster offen (`Read-Host`);
  `/status` meldet „HARNESS LAEUFT NICHT" + letzten Crash-Bericht.
- Fallstricke beim Testen:
  * `_loop()`-Tests: `git_preflight`/`git.checkpoint`/`run_worker`/`poll`/`peak_gate` patchen
    UND einen Poll-Zaehler als Notbremse setzen — sonst läuft die Schleife endlos weiter
    (Git-Vorprüfung schlägt im Temp-Verzeichnis fehl → `continue` ohne quit).
  * PowerShell 5.1 schreibt `cmd *> datei` als UTF-16: beim Auswerten BOM beachten.
    Fuer Belege `2>&1 | Out-File -Encoding utf8 <datei>` nehmen - sonst zeigt das
    read_file-Werkzeug die Datei als Hexdump des BOM.
  * Demo-Helfer `ein_durchlauf` schaltet `orch.tg` ab, damit der laufende Harness seine
    Telegram-Nachrichten behält (getUpdates-Offset ist botspezifisch).
- Terminalausgabe beim laufenden Harness ist unzuverlässig abgeschnitten → Ergebnisse in
  Dateien schreiben (`*> ..\docs\_x.txt`) und danach lesen.
- R13d (2026-09-26): Harness starb ZWEIMAL an `PermissionError [WinError 5]` bei
  `os.replace(run.json.tmp -> run.json)` (in `phase("review")` und `state.set`).
  Ursache: zweiter Prozess (`hx.cli watch`, liest `run.json` alle 1,5 s) hielt die
  Datei offen. GEMESSEN (C: und G:, gleiches Ergebnis): Rename-Ersetzen scheitert
  mit WinError 5, solange IRGENDEIN Handle offen ist — auch mit FILE_SHARE_DELETE
  (dann geht `DeleteFile`, aber kein Rename). Abhilfe: `util.replace_with_retry`
  (Nachsicht 5 ms→50 ms, 40 Versuche ≈ 1,8 s) in `write_text_atomic`;
  `util.open_shared_read` (share=RWD) fuer unsere Leser (hilft beim Loeschen, NICHT
  beim Ersetzen). Tests `tests/test_r13d_fixes.py`, Beleg
  `docs/_teilungsfehler_probe.py` -> `docs/_teilungsfehler_beweis.txt`.
- R13e (2026-09-26, Sammelauftrag nach der ersten Nacht): sieben Punkte umgesetzt.
  KURZFORM: (1) `review.dir` im Zustand - das Review von Batch N liegt in
  `runs/b<N+1>`, watch las bisher den VORIGEN Review. (2) Ghidra: `save_all_programs`
  nach JEDEM Batch mit Ghidra-Profil, Sicherung vor jedem Ghidra-Batch (12,1 MB/~2 s),
  HTTP-Beruehrung des Zustands im Review vermerkt. (3) STILLE ABSTUERZE: Prozesse aus
  dem VS-Code-Terminal liegen im Job von Code.exe (IsProcessInJob gemessen) - der
  Harness NIE aus dem VS-Code-Terminal starten, nur eigenes Fenster/Verknuepfung.
  (4) Reviewer-Limit setzt von selbst fort (Zeit aus der Meldung, sonst stuendlich).
  (6) Telegram-Kopf "AUTOMATISCH FREIGEGEBEN" im Dauerbetrieb. (7) Pausen-Erkennung
  rechnet Harness-Commits nicht als Handarbeit (git merge-base --is-ancestor).
  (8/9) watch zaehlt je Batch und zeigt das Batch-Ende auch pausiert.
  (10) `--lazy` bei der MCP-Bridge ENTFERNT: damit waren nur 97 von 215 Werkzeugen
  sichtbar, 76 erlaubte fehlten (get_xrefs_to, search_instructions, ...). Beleg:
  `docs/_ghidra_tools_audit.py` vergleicht /mcp/schema mit den Profillisten.
  NEU: `harness/tests/test_r13e_fixes.py` (34 Tests), gesamt 196 gruen.
  Werkzeugfehler im Mitschnitt zaehlen jetzt richtig (`<tool_use_error>`/`is_error`;
  "requires approval" = gesperrt) - vorher zaehlten zitierende Dokumente mit.
- R13f (2026-09-26): (1) Entscheidungsregel - der Reviewer entscheidet den Regelfall
  selbst; Zeile `ENTSCHIEDEN: …` in `<TELEGRAM_SUMMARY>` (4. Schluessel in
  `parse_offene_punkte`, bremst NICHT, Anzeige in /status + watch zuerst). `ENTSCHEIDUNG
  NOETIG` nur noch in fuenf Faellen (Ziel/Umfang, Verbotsliste, Material nur vom Nutzer,
  Abweichung von Nutzerentscheidung, Uebergang zur systematischen Dekompilierung);
  Eskalationsregel "zweimal dasselbe Problem" entfaellt (Veto per /claude).
  (2) `/ask` = freie Frage (hx/ask.py, prompts/ask.md, hx.cli ask, Telegram /ask),
  Opus/Abo-Token, eigener Lauf, im EIGENEN THREAD (`_do_ask`) - ein blockierender
  Unterprozess im Takt wuerde den Mitschnitt eines laufenden Batches anhalten.
  (3) SICHERHEIT, gemessen: `--allowedTools Read` OHNE Pfadbindung erlaubt JEDEN Pfad -
  Reviewer UND Worker lasen `g:\Harness\secrets\deepseek.key`. Wirksam ist nur
  `Read(//g:/Pfad/**)` (+ ausdrueckliches `--disallowedTools Read(//…/secrets/**)`).
  Der Worker bleibt offen (PowerShell) - Optionen beim Nutzer.
  Beleg: `docs/_ask_zugriff_regeln.txt`, `docs/_ask_zugriff_beleg.txt`.
  (4) Plan ohne Bau: `docs/selbstheilung-plan.md` (/fix + Waechter, Todesarten A/B/C).
- Fallstrick: ein absoluter Pfad AUSSERHALB des Arbeitsverzeichnisses wird abgelehnt,
  auch wenn eine `Read(//…/**)`-Regel ihn erlaubt - die Wurzel muss zusaetzlich per
  `--add-dir` angemeldet sein (der Reviewer hatte das nicht).
- Fallstrick: `harness/.gitignore` enthaelt `!tests/**`. Das hebt jede Sperre des
  Wurzel-`.gitignore` unter `tests/` auf - `_tmp_*`-Testordner (mit eingebettetem
  Git-Repo) tauchen dann als untracked auf. Neue Test-Ausnahmen MUESSEN in
  `harness/.gitignore` NACH der Test-Ausnahme stehen.
- Fallstrick: `Read` hat eine Groessengrenze von 256 KB. Ein Modell meldet das gern als
  "VERWEIGERT" - bei Zugriffsproben deshalb eine KLEINE Kontrolldatei nehmen.
- R13g (2026-09-26): Schluessel aus dem Harness heraus (Option 3) + Ueberwachung.
  (1) Ablage: `%USERPROFILE%\.hx-secrets` mit ACL nur fuer den Benutzer
  (`tools/setup_secrets.py`, idempotent, Beleg `docs/_secrets_umzug.txt`);
  `[paths] secrets = "$USERPROFILE/.hx-secrets"`, `hx/config.py:expand_path` loest
  `$VAR`/`%VAR%` auf. `g:\Harness\secrets` ist leer und bleibt in den Verboten.
  (2) `hx/streamjson.py: SecretWatch` + `StreamStats(secret_watch=)`: SchluesselWERTE
  in JEDER Zeile (Leck), Zugriffspfade NUR in Werkzeugaufrufen (bei Schreibern nur
  das Ziel) - ein Dokument, das den Pfad zitiert, ist KEIN Zugriff. Alarm
  "SECRET-ZUGRIFF" (Art, Werkzeug, Dateiname - nie ein Wert), Beleg
  `logs/secret-zugriff.jsonl`, Zeile im Review-Messdatenblock
  (`orchestrator.secret_zeile`). Beleg `docs/_secretwatch_beleg.txt`.
  (3) Bereinigung: `tools/scan_secrets.py [--redact --kontext]`; 6 Fundstellen,
  ALLE aus den eigenen Zugriffsproben (nicht aus Batches), entschaerft.
- Fallstrick: `json.dumps` schreibt Windows-Pfade als `g:\\Harness\\...`. Eine
  Pfadsuche muss erst backslash->slash und DANN mehrfache Schraegstriche
  zusammenziehen (`streamjson._norm`), sonst bleibt der Treffer aus.
- Fallstrick: `g:\Harness\sandbox\decomp-link` ist eine JUNCTION ins Decomp-Repo.
  `rglob` folgt ihr und meldet 69 GB statt 30 MB. Immer `os.walk(followlinks=False)`.
- Fallstrick: `stop.ps1` hinterlaesst den Marker `state/STOP`. Der naechste Start
  liest ihn im `poll()` und beendet sich SOFORT wieder. Nach einem Stopp fuer den
  Nutzer den Marker loeschen (`state/STOP`) - der Merker `stopped` in run.json ist
  dagegen harmlos, `run()` hebt ihn beim Start auf (bis PAUSIERT).
- R13h (2026-09-26): Laufzeit - warum manche Batches Stunden dauern (Nutzerfrage).
  MESSUNG (`tools/analyse_laufzeit.py` -> `docs/_laufzeit_analyse.txt`): der Harness ist
  NICHT die Ursache (harness_s weicht 2-21 s von der Selbstauskunft des claude-Prozesses
  ab). Die Zeit steckt in Werkzeugen (bis 81 %: 68K-Emulation 400-600 s je Lauf, Port-Bau
  ~420 s) und in reinen Wartebefehlen (`Start-Sleep`; b174: 1993 s = 42 % der Laufzeit).
  GEBAUT: (1) `TaktGeber` - Summen/Kosten NICHT je Zeile rechnen. `cost_usd()` kostet
  ~1 ms; bei 156.493 Zeilen waren das ~156 s im Leser-Thread. Jetzt im 2-s-Takt:
  1,6 s statt 156 s, Ergebnis identisch (`docs/_kosten_takt_messung.txt`).
  (2) `TaktThread` - waehrend eines langen Werkzeugaufrufs kommt KEINE Mitschnittzeile,
  also tickte der Harness nicht: /stop und /pause wirkten bis zu 10 min nicht.
  (3) Laufzeit-Profil (`StreamStats.laufzeit_profil`) in `harness-facts.md` und in der
  Telegram-Batch-Meldung (`Zeit: Werkzeuge … Modell … reines Warten … langsamste …`).
  (4) Worker-Vorspann "RECHENZEIT": parallel statt nacheinander (4 Kerne), kein
  `Start-Sleep -Seconds 300`, Abbruchbedingung mit kurzem Schritt.
  OFFEN (Decomp-Repo, nicht Harness): die 68K-Skripte laufen nacheinander - Faktor 2-4
  waere drin. Belege: `docs/_laufzeit_analyse.txt`, `docs/_kosten_takt_messung.txt`.
- Fallstrick: `& .\scripts\port_build.ps1 -Gl 2>&1 | Select-Object -Last 6` liess
  PowerShell mit `out-lineoutput: NullReferenceException` enden (Exit 1), obwohl der Bau
  erfolgreich war. Bei langen Ausgaben `*> datei.txt` nehmen und die Datei lesen.
- Bau-Messung: `port_build.ps1 -Gl` dauert 6,7 s, wenn nichts zu bauen ist ("Nothing to
  be done"), ~420 s nur bei echten Quellaenderungen (b177 aenderte port/src/audio68k_*).
  Kein Fixkostenproblem - kein Build-Trick noetig.
- R13i (2026-09-26): harte Tode des Harness (Nutzer: "harness ist wieder abgestuerzt").
  BEFUND (belegt): Der Worker setzte in b178 `Get-Process python | Where-Object
  { $_.CPU -gt 50 } | Stop-Process -Force` ab und toetete damit den HARNESS (selbst ein
  python.exe mit ~370 s CPU). Kein Crash-Bericht, keine stderr-Zeile, kein
  Ereignisprotokoll - Zustand bleibt auf DS_WORKING. Der zweite Tod (b177, direkt nach
  "Batch beendet") hat dieselbe Signatur, ist nicht belegt.
  GEBAUT: (1) `streamjson.abbau_gefahr` erkennt Muster-Abbau (CPU-Filter, -Name,
  taskkill /IM, pauschale Liste); gezielte `-Id`/CommandLine-Filter bleiben still
  (Beleg `tools/check_abbau.py` -> `docs/_abbau_beleg.txt`: 10/10, in allen Batches
  genau 1 Treffer). (2) Notbremse im Worker (killed_reason=prozess_abbau). (3) Regel im
  Vorspann. (4) `orchestrator.abbau_ursache` + `recover()` nennt den harten Tod beim
  naechsten Start. (5) `reviewer.py` fehlte der Import von streamjson (R13g-Bug, lag in
  try/except -> nur WARN-Zeile). (6) Repo-Wache in `gitsafe.Git`
  (`git rev-parse --show-toplevel` == cfg.decomp, sonst rc=128).
- FALLSTRICK (teuer, 2026-09-26): `wip_rescue` macht `git stash push` mit
  `cwd=cfg.decomp`. Zeigt der auf ein Verzeichnis INNERHALB eines anderen Repos
  (Test-Tempordner im Harness-Repo!), arbeitet git still am AEUSSEREN Repo - mein Test
  `test_recover_nennt_den_harten_tod` hat so ZWEIMAL den Arbeitsbaum des Harness
  gestasht (`harness-wip-b178`) und unversionierte Arbeit weggeraeumt. Zurueckholen:
  `git stash list` / `git stash pop`. Lehre: (a) Tests brauchen ein eigenes `git init`
  im Wegwerf-decomp, (b) Repo-Wache eingebaut, (c) Arbeit im Harness-Repo VOR einem
  Harness-Start committen.
- Fallstrick: PowerShell zerlegt mehrzeilige `git commit -m "..."` (Zeilenumbrueche, Klammern) - Commit-Nachrichten immer per Datei + `git commit -F` (z.B.
  `.git/COMMIT_MSG_<ref>.txt`).
- Memo: `pyflakes` ist installiert (`python -m pyflakes hx tools tests`); die
  Testsuite prueft damit auf undefinierte Namen (test_r13i_fixes.TestModulnamen).
- Belege: `g:\Harness\docs\_watch_b001.txt`, `_watch_envproof.txt`, `_demo_check.txt`,
  `_test_check.txt`, `_neustart_beweis.md`, Bedienung: `g:\Harness\docs\bedienung.md`.
  Nachtbericht B161-B174: `g:\Harness\docs\_nachtbericht_b161_174.md`.

- R13j (2026-09-27): Ausgabe-Pipe ohne EOF - "Worker fertig, Harness wartet".
  `proc.run_stream` hat jetzt `eof_gnade_s` (60 s, `res.eof_offen_s`): ist das Kind
  beendet (`proc.poll() is not None`) und kommt so lange keine Zeile mehr, gilt der
  Lauf als fertig (WARN "Ausgabe-Pipe ohne EOF"). FALLSTRICK: die Gnade sitzt in
  DERSELBEN Schleife wie `on_event` - ein blockierendes `on_event` verhindert sie
  (genau das war R13k). Die Ursache des zweiten Haengers war NICHT die Pipe.
- R13k (2026-09-27, BELEGT): Der Mitschnitt-Leser machte den Telegram-Takt
  (`on_event -> takt_jetzt -> poll -> get_updates`). Blieb der Aufruf haengen
  (py-spy-Stack `urlopen -> ssl.read`), stand der ganze Batch: kein Ende, kein
  `result.json`, kein Push, und `/stop` wirkte nicht (der Abbruch wird IM LESER
  geprueft). Jetzt tickt NUR der Takt-Thread (R13h); `on_event` ruft kein Netz mehr.
  `tests/test_r13k_fixes.py` prueft das per AST (Textsuche zaehlte Kommentare mit).
- R13l (2026-09-27, GEMESSEN): Das Socket-Zeitlimit befreit NICHT - `urlopen(...,
  timeout=15)` stand ueber 17 min in `ssl.read` (CPU eingefroren). Deshalb hat
  `telegram.call` jetzt eine harte Wanduhr-Grenze (`grenze=`): eigener Daemon-Faden
  + `join(grenze)`, danach `TelegramError("Zeitgrenze hart gerissen")`. Aufgegebene
  Aufrufe zaehlen gegen `MAX_HAENGER=2` (`haengende_aufrufe()`), weitere werden
  sofort abgelehnt. Grenzen: kurze Abfrage 8 s, Langpoll `poll_timeout+20`, senden 20 s.
  LEHRE: In einem Thread, der den Lauf traegt, nie ungeschuetzt ins Netz greifen.
- WERKZEUG: `py-spy dump --pid <pid>` (installiert) gibt den Stack des haengenden
  Harness aus - belegen statt raten. Genau so wurde R13k/R13l gefunden.
- WENN DER HARNESS HAENGT: Telegram `/stop` kann wirkungslos sein (Hauptthread im
  Netz). Dann `powershell -NoProfile -ExecutionPolicy Bypass -File
  g:\Harness\harness\stop.ps1 -Force` bzw. `taskkill /PID <pid> /T /F`; danach
  `state/STOP` loeschen und mit `.\start.ps1 -Paused` neu starten.
- Ein haengender Lauf beendet `_finish_run` NICHT: kein `runs/b<N>/result.json`,
  kein `review.dir`, kein Push, keine Ghidra-Sicherung. Die Commits des Workers
  sind trotzdem da (`git log` im Decomp-Repo) - nur ungepusht.
- FALLSTRICK (2026-09-27, teuer): Bleibt der Push aus (Haenger, harter Tod, Fenster
  geschlossen), liegt `origin/main` hinter dem lokalen Stand. `git_preflight`
  verlangt Gleichstand ⇒ der Harness pausiert bei JEDER Batch-Vorpruefung
  ("origin/main weicht ab ... kein Merge durch das Harness"); `/resume` hilft nur
  bis zur naechsten Vorpruefung. Abhilfe:
  `git -C "g:\Silent Scope Decomp" push origin main`.
- R13m (2026-09-27): Der Auftrag wird erst beim WIRKLICHEN Start verbraucht.
  Vorher stand `clear_gate()` VOR der Git-Vorpruefung - ein Git-Halt warf den
  bezahlten Auftrag weg, und der naechste Versuch liess einen zweiten Opus-Review
  laufen (genau das passierte am 2026-09-27). Tests `tests/test_r13m_fixes.py`.
- Geaenderter Harness-Code wirkt erst nach einem NEUSTART des Harness-Fensters;
  waehrend er laeuft, laeuft die alte Fassung im Speicher (neue Log-Meldungen
  zeigen, was aktiv ist - "Telegram haengt" = R13l).
- Fallstrick beim Schreiben der Memory-Dateien: `Path.write_text` uebersetzt `\n`
  auf Windows in CRLF - danach findet das Memory-Werkzeug nichts mehr (LF noetig).
- R13n (2026-09-27): Auto-Pull. `orchestrator.git_sync(anlass) -> (ok, meldung, art)`
  laeuft in `git_preflight` (vor jedem Batch) UND in `_do_resume`. Nur wenn
  `behind>0`, `ahead==0` und HEAD Vorfahre des Remote ist UND der Baum sauber ist,
  gibt es `git merge --ff-only origin/main` (nach dem schon gelaufenen fetch).
  Art: "ok"/"geholt"/"abweichung"/"unsauber"/"pull-fehler"/"unpruefbar" - beim
  Fortsetzen sperrt NUR eine echte Abweichung, "unpruefbar" (kein Repo, fetch-Fehler)
  laeuft weiter (sonst waere /resume ohne git unmoeglich).
  Uebernommene Commits = NUTZERARBEIT, erkannt am HASH (`remote_work` in run.json),
  nicht am Titel - "B172: ..." vom anderen Rechner waere sonst Harness-Arbeit.
  Review: Block in `pause_work_note()`; Worker: `remote_hinweis` im Vorspann;
  Messdatenblock: `remote_work_zeile()`. Beides mit R367 (NEUBAU + EINE volle
  Regression zu Batch-Beginn).
- R13o (2026-09-27): /ask mit Gedaechtnis. Session in `logs/ask/session.json`,
  Rotation `[ask]` (fenster_min 30 / max_fragen 10 / max_alter_min 120),
  `--session-id` beim ersten Mal, sonst `--resume`; `/ask-neu` erzwingt neu;
  bei gerissener Session EIN Versuch mit frischer Kennung.
  Strikt nacheinander: Sperre `logs/ask/ask.lock` (Alterung 1800 s, Warten 900 s)
  + Warteschlange im Orchestrator (`_ask_arbeiter`) mit "Frage eingereiht (Platz N)".
  Leserecht: ganz `g:\Harness` (`cfg.harness_home`) + Decomp; verboten: secrets
  (alt+neu), `backups/`, jede `.credentials.json` (`profiles.credential_verbote`,
  auch fuer den Reviewer). Beleg: `tools/check_zugriff3.py` (8 Aufgaben je Rolle).
  Hinweis: Token-Zahlen + "Abo" statt Dollar (die Zahl war mit DeepSeek-Preisen
  gerechnet, `hx/pricing.py`). `--max-turns` = `[ask] max_turns` (25).
- FALLSTRICK (Windows, teuer in Tests): `git` legt Objektdateien NUR-LESEND an.
  `shutil.rmtree` scheitert daran mit WinError 5 und laesst den Ordner stehen - der
  naechste Testlauf scheitert dann beim `git clone` in denselben Pfad. Loesung:
  `shutil.rmtree(p, onexc=...)` mit `os.chmod(path, stat.S_IWRITE)` (Tests
  `tests/test_r13n_fixes.py`, Helfer `_weg`).
- FALLSTRICK: `os.kill(pid, 0)` ist unter Windows KEINE Lebendpruefung - Python
  beendet den Prozess damit. Sperren/Locks deshalb nur ueber Alter pruefen.
- Geaenderter Harness-Code wirkt erst nach einem NEUSTART des Harness-Fensters;
  `prompts/*.md` und `harness.toml` liest der laufende Prozess dagegen gemischt
  (Prompts pro Lauf von der Platte, Konfiguration nur beim Start).
- R13p (2026-09-27, Auftrag des Nutzers): fuenf Punkte in einem Commit `8157c35`.
  (1) Grenzen: `alarm_requests` 250 -> **500** und ZWINGEND `hard_requests` 400 ->
  **1000** - die harte Grenze lag nur 53 ueber dem je gemessenen Maximum (b176 =
  347 Anfragen) und haette den Alarm sonst unerreichbar gemacht. Real: 84..347
  Anfragen, $0.10..0.41 je Batch.
  (2) NUTZERLIMIT: Claude Code schreibt in jeden ABO-Mitschnitt (Review, Uebergabe,
  /ask - NICHT beim DeepSeek-Worker) ein `rate_limit_event` mit
  `rate_limit_info.unifiedWindows.{five_hour,seven_day}` = Auslastung 0..1 +
  `resetsAt`. `streamjson` liest es, `schreibe_rate_limit` legt die letzten Werte
  nach `logs/rate-limit.json`, der Takt warnt ab 80 % EINMAL je Fenster
  (`notify_once` mit Schluessel `rate:five_hour@<resetsAt>`), /status zeigt beide
  Fenster. Reset-Zeiten deutscher Zeit: `streamjson.resets_zeit` ->
  `27.09.2026 17:00 (UTC+02:00)`. `overageStatus: rejected` = kein Nachkaufen.
  (3) REVIEW-PROMPT: neue Bloecke `BATCH-DIFF` (name-status + Diffstat seit
  `last_checkpoint`, `orchestrator.batch_diff_text`) und `HISTORIE` (15 Commits +
  neueste `analysis/port-batch*.md`, `historie_text`). Vorher sah der Reviewer nur
  die letzten VIER Commit-Betreffe.
  (4) NUR-LESE-GIT fuer den Reviewer: Werkzeug `PowerShell` gestellt
  (`CLAUDE_CODE_USE_POWERSHELL_TOOL=1` in `envs.reviewer_env`), Erlaubnisliste NUR
  `PowerShell(git log|show|diff|status *)`; zweiter Riegel `profiles.git_schreib_verbote`
  (schreibende Unterbefehle, `--output`, fremde Shell-Befehle wie Get-Content/
  Remove-Item/Invoke-Expression). Doku-Regeln: `*` MUSS nach dem Unterbefehl stehen,
  Deny schlaegt Allow, im `-p`-Lauf wird alles ohne Allow-Regel abgelehnt.
  Beleg `tools/check_zugriff4.py` -> `docs/_reviewer_git_beleg.txt` (10 Aufgaben,
  alle Erwartungen erfuellt).
  (5) AUFBEWAHRUNG `hx/retention.py`: einmal taeglich und nur ohne laufenden Batch
  werden `stream.jsonl`/`reviewer.jsonl`(+v1/handover) und die Snapshots aelter als
  14 Tage als ZIP abgelegt (Pruefsumme + Groesse geprueft, erst dann Original weg;
  max. 6 Einheiten je Tag). Unkomprimiert bleiben result.json, harness-facts.md,
  antwort.md, auftrag.md, review.md. Unter 20 GB frei -> Telegram-Warnung.
- FALLSTRICK (R13p, real gefunden): JEDER Leser von `runs/b<N>/stream.jsonl` muss
  ueber `retention.mitschnitt_zeilen()` gehen - die Datei kann `<name>.zip` sein.
  Betroffen waren `watch._tail`, `worker.rebuild_from_stream`, `worker.write_snapshot`
  (der brach mit FileNotFoundError ab) und `orchestrator.abbau_ursache`.

- R13q (2026-09-27, Commit `45296c7`): Live-Zahlen + Bilanz.
  (1) `/status` zeigt Dauer und Kosten des LAUFENDEN Batches: `worker.LIVE_SEKUNDEN`
  = 15 s, `live_schreiben(t, cost)` im Takt-Block von `run_batch` (NACH
  `takt.faellig()`, sonst je Zeile) schreibt `state.data["live"]` =
  {batch, ts, requests, cost_usd, input_miss, cache_read, output}; Fehler nur
  Log-Warnung. `state.worker_finished()` hebt den Stand nach `live_letzte` auf.
  Der Mitschnitt wird dafuer NIE gelesen (b180: 32 MB) - der Leser-Thread ist
  derselbe, der das Kind-Ende pruefen soll. Anzeige: `orchestrator.live_batch_zeile()`.
  (2) `hx/bilanz.py` = `/bilanz [N]` (Telegram) und `hx.cli bilanz --n N`: feste
  Reihenfolge Kopf -> Ast-Tabelle -> Zusatz -> PROJEKTSTAND -> KOSTEN/ABO -> AUFGABEN.
  Quellen: `analysis/_bilanz_snapshot.json` (nur lesend), Batch-Dokument/Ankerkopf fuer
  die C-Zahlen, `runs/b*/result.json` (24 h), `logs/rate-limit.json` (Abo).
  `vergleichs_batch` nimmt den naechsten VORHANDENEN Batch <= jetzt-N (154 fehlt
  wirklich) und NIE einen aelteren als den aeltesten vorhandenen (dann "kein
  frueherer Batch vorhanden").
- FALLSTRICK (R13q): Telegram rendert Festbreitenschrift nur im Code-Block. Beim
  Senden `split_message(...)` ZUERST, dann jeden Teil mit ``` umfassen - andersherum
  zerreisst die Teilung den Block. Backticks IM Text vorher zu `'` machen (ein
  einzelnes Backtick beendet den Block). `Telegram.send(text, mono=True)`,
  `say(text, mono=...)`, Grenze `telegram.Telegram.MONO_LIMIT = 3800`.
- FALLSTRICK (R13q): Die Tageskosten im Zustand sind unter dem **UTC**-Datum
  abgelegt (`orchestrator.status_text` -> `datetime.now(timezone.utc)`); wer
  `spent` liest, muss dieselbe Basis nehmen, sonst zeigt die Bilanz abends einen
  anderen Tag als /status. Feld heisst `spent` (nicht `spend`).
- FALLSTRICK (R13q): Die C-Zahlen (Inventar/gebaut/offen/Blaetter) stehen in den
  Belegdateien als PROSA mit Fettmarken und Zeilenumbruechen
  ("**591 Koepfe / 28858 Insn** in der\nBau-Liste"). Muster ohne `\**` und ohne
  `\s*` scheitern still: im ersten Anlauf meldete die Bilanz "offen 2072 Koepfe"
  (die Inventarzeile!) und "gebaut 0/0". Jetzt `hx/bilanz.py::_INV/_BAU/_OFFEN/_BLATT`.
- FALLSTRICK (R13q): Lange Sammelwerte in einer Tabellenspalte werden abgeschnitten
  ("Insn 4627/7959 (offe.."). Richtig ist kurze Hauptzahl + Detailzeile
  (`wert()`/`detail()`), und "geaendert" zaehlt Hauptzahl UND Nebenzahlen - sonst
  gilt ein Ast mit wandernden Nachzueglern als unveraendert.
- R13q-Tests: `tests/test_r13q_fixes.py` (23), volle Reihe 379 gruen (vorher 356).
- R13r (2026-09-27, Commit `e0db6f2`): `/thinking [N] [voll]` - Denkbloecke mitlesen.
  (1) Quelle: `runs/b<N>/stream.jsonl`, Zeile `{"type":"assistant","message":{"content":
  [{"type":"thinking","thinking":"…","signature":"…"}]},"timestamp":"…"}`. Solche Zeilen
  gibt es in JEDEM Batch (b180/b195 je ~16, b196 mehr), Text 200-800 Zeichen;
  `thinking_delta` kommt NICHT vor; Bloecke mit LEEREM Text (nur `signature`) zaehlen nicht.
  Der Live-Pfad des laufenden Batches ist `state.data["worker"]["log"]`
  (`state.worker_started(pid, str(stream_path), session_id)`).
  (2) Neu `hx/denken.py`: TAIL-Leser (rueckwaerts in 256-KB-Bloecken vom Dateiende,
  Stop bei N Treffern, fester Deckel `MAX_SCAN_BYTES = 16 MB`), damit der TaktThread -
  dort laeuft `handle_command` - nicht auf einen 32-MB-`read_text` wartet. Gemessen:
  28-MB-Mitschnitt in 0,29 s, gelesen 3,5 MB. `argumente()` (N 1..50, Vorgabe 10,
  voll-Woerter), `beschreibe()`, `neuester_mitschnitt()`, `mitschnitt_fuer_batch()`.
  (3) `orchestrator.thinking_pfad()/_do_thinking()/thinking_zusatz()`, Versand
  `say(text, mono=True)`; Aliase `thinking`/`denken`; `hx.cli thinking [--n] [--batch]
  [--voll]`.
- FALLSTRICK (R13r, von den Tests gefunden): Der ZIP-Weg lieferte die Treffer
  alt->neu, der Tail-Weg neu->alt - `denkbloecke()` dreht EINMAL um, also muessen
  beide privaten Leser dieselbe Reihenfolge liefern.
- FALLSTRICK (R13r): Der Deckel-Merker darf nicht `pos > untergrenze` sein (wahr auch
  bei genug Treffern), sondern `pos > 0 and len(treffer) < n` - sonst meldet die Anzeige
  "nur die letzten 16 MB durchsucht", obwohl alles gefunden wurde.
- FALLSTRICK (R13r): `runs/` enthaelt auch `env-proof` und `ghidra-smoke` - eine reine
  Namenssortierung macht einen Nebenlauf zum "neuesten Batch". Nur `b<N>` mit Ziffern
  zaehlen (`denken.neuester_mitschnitt`).
- FALLSTRICK (R13r): Die Windows-Konsole ist cp1252 und starb an `→`/`✓`/`—` in
  Denktexten (`UnicodeEncodeError`, gemessen). `hx/cli.py:_druck()` faengt das ab;
  Telegram ist davon nicht betroffen (UTF-8), dort kommen die Zeichen korrekt an.
- R13r-Tests: `tests/test_r13r_fixes.py` (30), volle Reihe **409 gruen** (vorher 379).
- R13s (2026-09-28, Commit `e1270f2`): lesbare Bilanz + `/fragen`.
  (1) NEU `hx/stand.py` = die Datenschicht: `anchor_bloecke` (Kopf in Stand/Fertig/
  Naechster Schritt/Offene Entscheidung), `offene_entscheidungen` (Posten `(n) …`,
  `GESCHLOSSEN` zaehlen), `entscheidbar` (Ja/Nein-Frage + `Vorschlag:` + `bei ja/nein`),
  `c_zahlen` (Soll/Ist-Tafel der Batch-Dokumente), `bilanz_je_batch`
  (`analysis/_m<N>/_bilanz*.txt`), `durchsatz`, `plan_ist`, `median`, `fragen_text`.
  (2) `bilanz.bericht` neue Reihenfolge: Kopf/ZULETZT -> WAS SICH GEAENDERT HAT (Prozent,
  nur Bewegtes) -> GESAMT (Prozent-Deltas + DURCHSATZ mit HYPOTHESIS) -> Aeste-Tabelle
  nur mit Prozentzeilen (`voll` zeigt alle) -> Zusatz/Kosten/Aufgaben.
  (3) `/fragen` (Telegram + `hx.cli fragen`): jede offene Frage EINE entscheidbare Zeile,
  sonst `UNKLAR FORMULIERT`; dazu die Reviewer-Marker des letzten Reviews.
  (4) Review-Prompt: PLAN/IST-Tafel (`review_context["plan_ist"]`) + Median-Regel
  (Ziel <= 1,3x Median); `prompts/reviewer.md` mit Pflichtbloecken `FERTIG WENN:` und
  `STREICHREIHENFOLGE:`, Werkzeug/Serie-Regel und FERTIG-WENN-Pruefung in der Summary.
- FALLSTRICK (R13s): Die Angaben in den Batch-Dokumenten sind TABELLENZEILEN, nicht Prosa
  - und die Zeile `**C Koepfe**` traegt **Koepfe / FAELLE / Abweichungen** (78*24 = 1872),
  die zweite Zahl ist also NICHT Insn (im ersten Anlauf falsch angenommen). Insn je Batch
  gibt es nur in der Zeile `Paket E offen`, und die existiert erst in neueren Dokumenten.
- FALLSTRICK (R13s): Der Durchsatz gehoert NICHT aus Dokument-Prosa gelesen, sondern aus
  `analysis/_m<N>/_bilanz*.txt` (maschinengeschrieben von `scripts/m149_bilanz.py`):
  Zeile `**R207 rueckwaerts** | **<vorher>** … | **<heute>** …` = Vorbatch/Heute. Die
  Dateinamen sind uneinheitlich (`_bilanz.txt`, `_bilanz_196.txt`, `_bilanz204.txt`) -
  je `_m<N>`-Ordner die neueste nehmen. Die Zeile `R207` steht auch in den Batch-
  Dokumenten (Rueckfall, wenn die Bilanzdatei fehlt).
- FALLSTRICK (R13s): Der Anker schreibt Posten FETT: `**(5) NEU:** …` - ein Posten-Muster
  `(?:^|\s)\((\d+)\)` findet sie nicht (vor der Klammer steht `*`). Und die Frage steht
  oft am ENDE einer langen Vorrede, nicht am Anfang; das Fragezeichen steht hinter der
  Klammer `(Vorschlag: ja)` und geht beim Abschneiden verloren.
- FALLSTRICK (R13s): `re.search(r"^TEIL\s*3\b.*$", MULTILINE)` deckt die GANZE Zeile ab -
  wer danach `text[m.end():]` schneidet, verliert die Kopfadressen, die in genau dieser
  Zeile stehen (im ersten Anlauf "0 Koepfe geplant"). Ab `m.start()` schneiden.
- R13s-Tests: `tests/test_r13s_fixes.py` (27), volle Reihe **436 gruen** (vorher 409).
- Belege: `docs/_r13s_belege.md` (Punkt 3 + Punkt 6 mit Datei:Zeile), `_r13s_beleg_4a.txt`
  (34 von 78 Koepfen mit CA-Befehlen), `_r13s_beleg_4b.txt` (1299 von 2072 Funktionen
  ausgefuehrt, davon 64 der 78 verifizierten = 4,9 %), Werkzeuge `tools/r13s_*.py`.
- R13t (2026-09-28): `/ds`-Nachrichten im Review + Port-Relevanz + getrennte Hochrechnung.
  (1) `stand.ds_nachrichten(cfg, batch)` liest den Block ab `QUEUE_KOPF`
  ("NACHRICHTEN AUS DER QUEUE") aus `cfg.root/runs/b<N>/auftrag.md` - NICHT aus der Queue,
  die ist beim Review schon nach `inbox/done/` archiviert. `orchestrator.review_context`
  legt ihn als `"ds_queue"` ab, `reviewer.build_prompt` zeigt ihn als
  `=== NUTZER-NACHRICHTEN AN DEN WORKER DIESES BATCHES (/ds) ===` + Regel.
  (2) `stand.port_relevanz(cfg)` liest den Cache `docs/_port_relevanz.json`
  (**`cfg.harness_home`**, nicht `cfg.root` - root ist `g:\Harness\harness`!); geschrieben
  von `tools/r13t_cov_relevanz.py`. Zahlen 2026-09-28: Inventar 2072, ausgefuehrt 1086
  (Rumpf-Fenster Eintritt..erstes `blr`, max 0x400 B), gebaut 686 -> 416 ausgefuehrt,
  verifiziert (`KOPF_DEF`) 78 -> 56, Paket-E-Wurzeln 86 -> 66, offene Blaetter 17 -> 12.
  (3) `stand.c_offen_gesamt` + `_c_gesamt_zeilen`: zweite HYPOTHESIS-Zeile "C gesamt",
  abgeleitet aus dem neuesten Dokument mit "OFFEN: X Koepfe / Y Insn" (B196 §6.1,
  1481/94913, Bau-Liste 591) minus R207-Delta.
- R535 (2026-09-28): **FEHLALARM** - `addc` addiert das eingehende CA NICHT (ISA: nur
  `adde`/`addze`/`addme`/`subfe`/`subfze`/`subfme`). Der Interpreter
  (`Silent Scope Decomp\scripts\m114_matrix.py:394-405`) rechnet richtig, nur sein
  Kommentar ist falsch; CA-lesende XOs sind dort GAR NICHT implementiert. Die
  B206-"Probe" hatte nur den Interpreter auf `+ self.ca` geaendert (12/74 rot) - kein
  Defektbeweis. ECHT bleibt: `port/src/ckopf_leaves.cpp:1977` addiert CA an einem `addc`
  (ROM-Wort `0x7C005014` bei `8005BF74`+0x20, XO=10) = `adde`-Semantik.
  Werkzeug `tools/r13s_ca_zensus.py --kopf 0x8005BF74`.
- FALLSTRICK (R13t): `docs/_r13t_beleg_4b.txt` per `*>` geschrieben ist UTF-16 -
  Anzeige ueber `Get-Content` geht, `read_file` zeigt Hexdump. Fuer Belege
  `2>&1 | Out-File -Encoding utf8` nehmen.
- R13t-Tests: `tests/test_r13t_fixes.py` (10), volle Reihe **446 gruen** (vorher 436).
- R13t2 (2026-09-28, Commit `6f77da1`): (1) `tools/r13t2_port_ca_scan.py` = CA-Zensus MIT
  Port-Seite (Kopf -> Portfunktion aus `const Head kHeads[]` in `ckopf_leaves.cpp:2363`,
  Brace-Matching, Muster "Inkrement MIT Vergleich" im Fenster +-2). Ergebnis: 34/78 Koepfe
  mit CA-Formen, KEINE CA-lesende Form in den Koepfen; genau EIN Treffer
  `ckopf_leaves.cpp:1977`. Programmweit lesend: `addze` 382x, `subfe` 18x (ueber
  `analysis/_m60_inventar.csv` mit `size` - legit CA-Ketten in game_result.cpp /
  mission_content_helpers.cpp). (2) `r13t_cov_relevanz.py` rechnet die Paket-E-Huelle
  selbst (Ruf-Abschluss ab den 86 Wurzeln: 265 Koepfe/28 offen gegen Projektzahl 274/38)
  und die drei Klassen: 677/28976 ausgefuehrt-nicht-gebaut, 1/38 nicht-ausgefuehrt-Paket-E,
  725/24521 Rest. Cache `docs/_port_relevanz.json`, Anzeige `stand._relevanz_zeilen`.
  (3) `_c_gesamt_zeilen` nimmt die GEMESSENE Klassensumme, sonst "nicht ermittelbar".
  Volle Reihe **452 gruen**.
- FALLSTRICK (R13t2, teuer): `if (r0 >= r10) r0 += 1u;` matcht NICHT `\+\s*1u\b` -
  `+=` schiebt ein `=` dazwischen. CA-Muster brauchen `\+=?\s*1u?` UND die Pruefung, ob
  der VERGLEICH in den Zeilen davor steht (mehrzeilige `if (...)`), sonst meldet der Scan
  faelschlich 0 Treffer (erster Anlauf: 0 statt 1).
- Warum 8005BF74 gruen war (R13t2, gemessen): alle 24 `CASE`-Zeilen von
  `analysis/_m197/_ck_5BF74.case` haben r5 = 0 und `[r3+8] = 0x10000` -> `diff > 0` ->
  frueher Ausgang `ckopf_leaves.cpp:1979`; die Schleife mit dem verschobenen r0 laeuft nie.
  Fallfabrik: `c_kopf.py:1472 _faelle`, Facher `:1427/:1429`, ROM-Leitern `WERTE_DEF :1521`,
  Vergleich `cmd_vergl :1852` + `_diff :1825` (Zeile fuer Zeile, Speicherabbild `:1389`).
- Interpreter lehnt unbekannte Opcodes LAUT ab (`m114_matrix.py:539/567/383-389/267/584`) -
  keine stille Falle, keine weitere Ablehnungsregel noetig (Punkt 2 R13t2).
- R13t3 (2026-09-28, Commit `c560d16`): Readme-Widerspruch belegt (der Satz "the tone is the
  last missing piece of a runnable port", `readme.md:640-642`, meint Zweig B/Milestone 4,
  nicht ein Spiel-Binary - Milestones `:752-766`, Paket F `:53`, GL-Anker = Kette, nicht
  Szenen). A/B/C verglichen: Interpreter deckt **97,3 %** der ROM-Befehlsworte (117648
  Woerter in den Inventarbereichen, fehlen 3158/35 Formen: addze 382, mfcr 109, stwx 60,
  mtdcr 56, mfdcr 51, mulli 55, cntlzw 57), MAME nennt **PPC 403GA @ 32 MHz**
  (`mame/mame/src/mame/konami/hornet.cpp:29`), `poc/ppc_native/ppc_core.h` ist KEINE CPU
  (Kernschicht, `run()` Z. 718). Empfehlung B als Pruef-Fahrzeug; static recompilation
  bleibt vertagt (`readme.md:661-673`). Messweise: `op == N` UND `op in (...)` aus
  `m114_matrix.py` extrahieren, sonst zaehlt man die Lade-/Speicherbefehle falsch
  (erster Anlauf 32,8 % statt 97,3 %).
- R13t4 (2026-09-28): Queue-Werkzeug ist `hx.queue.archive(root, ids, ziel)` (verschiebt
  nach `inbox/done/`, `pending` sieht sie danach nicht mehr; `state.delivered` muss NICHT
  mitgepflegt werden). **WICHTIGSTER FALLSTRICK:** `state/run.json` hat
  `autonomous: True` = Dauerbetrieb AN; dann gibt der Harness am Gate SELBST frei
  (`orchestrator.py:2104`), sobald der Review keinen `ENTSCHEIDUNG NOETIG`-Punkt hat -
  "Worker startet nicht bis /approve" gilt nur mit `/autonom off` (`:711-719`).
- Gate-Befehlsfolge (R13t4, belegt): `start.ps1` (eigenes Fenster) -> Telegram
  `/autonom off` -> `/review` (`:720-726` setzt `review_now` + `paused=False`, verwirft
  einen offenen Auftrag, `:1982-1992`) -> Review laeuft (`:2036-2039`) -> Gate haelt
  (`:2102-2113`, Zustand `GATE_APPROVAL`, `:2106-2112`) -> Freigabe mit `/approve [Text]`
  (`:354-363`, Text landet als /ds) oder `python -m hx.cli approve [Text]`
  (`cli.py:1072`, Datei `state/ctl/approve`, gelesen `:399-401`).
- Decomp-Schnittstelle fuer den Hybrid-Laeufer (R13t4, belegt): `render_sink.h` endet in
  Paketen (KEINE Strombytes), `render_sinks.h` trennt `DrawSink` (Produktion) von
  `TransportRecorderSink` (Pruefpfad), `sharc_consumer.h` laeuft einen 16-Bit-Strom IM
  SPEICHER ab; Dateien nur im Pruefpfad (`render_check.cpp:38`, `sharc_state.cpp:15/54`).
  `host_registry.h` = der Einhaengepunkt (Implementierung je PPC-Adresse registriert,
  nicht registrierte Adresse = harter `UnimplementedFunction`), `struct PpcContext`.
- R13u (2026-09-28): ZUSTELL-REGEL der /claude-Queue. Bis R13t buchte `_loop`
  `commit_queue("claude", ids)` direkt nach dem gueltigen Review (`orchestrator.py`, alte
  Zeile ~2060) - ein `/review` verwarf danach das Gate (`discard_gate`), die Nachricht lag
  aber schon in `inbox/done/` und ward nie wieder gelesen. Jetzt: die IDs reisen im Gate
  (`gate_from_review(..., claude_ids=)` -> `extra={"claude_queue_ids": [...]}`) und werden
  erst beim Worker-Start zugestellt (nach `s.clear_gate()`); `discard_gate` laesst sie
  liegen und warnt nur, wenn eine Datei schon in `done/` liegt. Tests
  `tests/test_r13u_fixes.py` (4), R13b-Test + `hx.cli demo` (Szenario 11) angepasst.
- `/ds`-Semantik (R13t4 gemessen): `read_queue_block("ds")` beim Worker-Start (`:2151`,
  `mark=True`) -> sofort `commit_queue`; ein verworfenes Gate laesst sie liegen, nach dem
  Start ist sie weg (auch wenn der Batch scheitert). Ein wiederholtes `/review` laeuft in
  DERSELBEN Reviewer-Session mit Verlauf (`session_id` aus dem Zustand, `new_session` nur
  bei Rotation, `:1321-1322`).
- R13v (2026-09-28): WARTESCHLEIFEN + Kostenzaehler.
  (1) BEFUND aus `runs/b207/stream.jsonl`: `:66903` Start-Process `c_kopf.py mutalle`
  (PID 4996), `:76873` Poll-Schleife 601,9 s, `:77152` zweite 481,8 s = **1083,7 s**
  gemessen (Schaetzung 1390 s); `:76897` belegt die Werkzeug-Grenze: "Command did not
  complete within its **600s timeout** and was moved to the background" - DESHALB wurde
  gepollt. Werkzeug `tools/warte_analyse.py` (klassifiziert poll/sleep/warten/hintergrund/
  arbeit, nennt stream.jsonl-Zeile und PIDs).
  (2) GEBAUT: `streamjson.warte_muster()`/`warte_entscheidung()` (Abfrageschleife, fester
  Schlaf >= 30 s; `Wait-Process` ist erlaubt) + `stats.warteschleifen` + Zeile
  `WARTESCHLEIFEN n / ~s` im Laufzeit-Profil; `worker.on_event` meldet den ersten Fund und
  BRICHT ab 300 s ab (`killed_reason="warteschleife"`); `build_command` sperrt
  `PowerShell(Start-Sleep*)`/`Bash(sleep *)`; `envs.worker_env` setzt
  `BASH_DEFAULT_TIMEOUT_MS=BASH_MAX_TIMEOUT_MS=600000` (dann laeuft ein 10-Minuten-Lauf
  synchron); Vorspann nennt den erlaubten Weg (`Start-Process -PassThru` + EIN
  `Wait-Process -Id $p.Id -Timeout 480`).
  (3) KOSTEN: **kein Defekt**. Gemessen (`tools/kosten_nachrechnung.py`): die
  assistant-Ereignisse tragen output=0, das `result`-Ereignis traegt 137354; Nachrechnung
  MIT Ausgabe = $0,172692 = gemeldet $0,1727 (ohne Ausgabe waeren es 47,7 % weniger).
  `message_delta` mit usage gibt es in unseren Streams NICHT.
- FALLSTRICK (Test): Zeitgeber-Tests duerfen nicht auf feste Wanduhr schlafen
  (`time.sleep(0.4)` + ">=2 Schlaege") - unter Last verhungern sie und werden rot, ohne
  dass etwas kaputt ist (`test_r13h_fixes.TestTaktThread`). R13v hat sie auf
  "auf den zweiten Schlag warten, 5 s Obergrenze" umgestellt.
- Belege R13t: `docs/_r13t_belege.md` (Index), `_r13t_beleg_4b.txt`, `_r13t_beleg_4_prompt.txt`,
  `_r13t_beleg_1_kopf.txt`, `_r13t_ca_zensus.json`, `_port_relevanz.json`.
  Queue-Inhalt: `_r13t_ds_r535.txt` (Widerlegung), `_r13t_claude_r535.txt` (an den Reviewer),
  `_r13t_ds_altposten.txt` (sechs Nutzerentscheidungen 1 ja/2 ja/3 nein/4 ja/5 ja/6 ja).

- R13v2 (2026-09-28, Commit `b8b2b05`): Nachprobe VOR dem Neustart (Nutzerfrage).
  (1) SPERRE NACHGEMESSEN mit ECHTEM claude-Lauf (`tools/r13v_sperrprobe.py`, Beleg
  `docs/_r13v_sperrprobe.txt`, 11 Faelle je 4-7 s; Aufbau: `worker.build_command`
  + `envs.worker_env` unveraendert, Modell fuehrt Befehle wortwoertlich aus, Bewertung
  aus dem Mitschnitt). ERGEBNIS: `PowerShell(Start-Sleep*)` ist **keine Praefix-Regel** -
  der Befehl wird in seine Bestandteile zerlegt und alias-bewusst geprueft. Blockiert:
  nackt, hinter `;`, in `if (…) { … }` UND in der `for`-Schleife (die Frage war: ja);
  Alias `sleep` wird aufgeloest. NICHT gesperrt: blosse Erwaehnung im Text
  (`Write-Output "Start-Sleep …"`) und `[Threading.Thread]::Sleep(2000)`.
  Die irrefuehrende Behauptung im Kommentar `worker.build_command` ist korrigiert.
  (2) NOTBREMSE (`proc.kill_tree` = `taskkill /PID <claude> /T /F`) mit Herzschlag
  gemessen (`tools/r13v_waise_probe.ps1` + `r13v_herzschlag.py`, Beleg
  `docs/_r13v_waise.txt`): Prozesse IM Baum sterben, Prozesse OHNE Elternbezug
  (WMI `Win32_Process.Create`) laufen weiter. B207 zeigt den echten Fall: PID 4996 lebte
  >19 min nach dem Ende des startenden Werkzeugaufrufs. Der Harness raeumt nichts auf
  (kein Prozess-Scan), verlangt keinen sauberen Baum, wiederholt Batch N nicht - der
  Abbruch geht in Push+Review (alles in `docs/bedienung.md` 12c).
  (3) KLEINE KORREKTUR: `streamjson.warte_normalisiert` schaetzt auch `sleep -Seconds N`
  und `[Threading.Thread]::Sleep(N)` - vorher 0,0 s ⇒ nur Alarm statt Abbruch.
  Volle Reihe **473 Tests OK** (vorher 471).
- FALLSTRICK (Sonde, teuer): Ein PowerShell-Aufruf, dessen Ausgabe in eine Variable/
  Pipe geht, wartet auf das Schliessen der Pipe - ein UEBERLEBENDER Enkel haelt sie
  offen (Messung hing 120 s). Belege in der Sonde deshalb SELBST schreiben
  (`| Out-File -Encoding utf8 $beleg`) und den Aufruf mit `| Out-Null` fahren.
- FALLSTRICK (Sonde): `Start-Process -ArgumentList '-c','import time; time.sleep(9)'`
  quotet NICHT - python bekommt `-c import` und stirbt mit SyntaxError (Messung war
  wertlos). Fuer solche Sonden eine Skriptdatei nehmen (`r13v_herzschlag.py`).
- R13v3 (2026-09-28, Auftrag des Nutzers vor dem Neustart): drei Punkte.
  (1) `/autonom`: **kein Defekt**. Gemessen (`tools/r13v3_zustand_probe.py`, Beleg
  `docs/_r13v3_beleg_zustand.txt`): der Telegram-Befehl schreibt sofort
  (`orchestrator.py:718`); beim Laden werden nur FEHLENDE Felder aus `state.DEFAULTS`
  ergaenzt; Stop/Neustart fassen das Feld nicht an. `state/run.json` steht auf **false**
  (mein R13v2-Bericht "True" kam aus der Sitzungszusammenfassung und war FALSCH - Zustand
  nie aus dem Gedaechtnis berichten).
  (2a) Aufraeumen: `hx/aufraeumen.py` = Job-Objekt (`KILL_ON_JOB_CLOSE`) + Nachsuche.
  **JOB ZUERST, DANN DAS KIND** - wird der Job erst nach dem Start des Kindes zugewiesen,
  erbt es ihn nicht (erster Messanlauf war dadurch wertlos; Zeitreihe
  `tools/r13v3_job_zeitreihe.py` hat es entlarvt). Mit richtiger Reihenfolge stirbt auch
  ein `Start-Process`-Kind mit dem Job (gemessen). Die Nachsuche faengt, was nicht im Job
  landet (WMI `Win32_Process.Create`): Name aus `KILL_NAMEN` + juenger als Batch-Start +
  (Wurzel in der Kommandozeile ODER waehrend des Laufs als Nachfahre gesehen ODER direktes
  Kind eines Lauf-Prozesses). `nachfahren_pids` wird im Worker alle 60 s in einem
  **Daemon-Thread** aufgenommen (`PID_AUFNAHME_S`, im `on_event` VOR dem Takt-Riegel) -
  nur so ist der B207-Fall belegbar (Kommandozeile nennt nur `scripts/c_kopf.py`, Shell
  tot). R13i-Schutz: `vorfahren(os.getpid())` + `NIE_ANFASSEN`.
  (2b) `orchestrator.wip_nach_abbruch` laeuft direkt nach `run_batch`, wenn
  `res.killed_reason`: `gitsafe.wip_rescue` + `ref` (Neu: `git rev-parse stash@{0}`),
  Zustand `letzter_abbruch`, Telegram-Meldung, Review-Block
  `=== ABBRUCH DES BEWERTETEN LAUFS ===`.
  (2c) Die Nummer kommt NUR aus dem Ankerkopf (`expected_batch()`), also dieselbe Nummer
  und derselbe Ordner `runs/b<N>` - deshalb `worker.sichere_vorgaenger` (umbenannt nach
  `*-v1.*`, u. a. `stream-v1.jsonl`, das `retention.MIT_ZIP` schon kannte).
  Tests `tests/test_r13v3_fixes.py` (26), Belege `docs/_r13v3_belege.md` +
  `_r13v3_beleg_aufraeumen.txt` + `_r13v3_beleg_zustand.txt`, Doku `docs/bedienung.md` 12d.
- FALLSTRICK (Umgebung): `envs.base_env` prueft `k in environ` - mit `os.environ`
  (Windows-Fall unempfindlich) geht das gut, mit `dict(os.environ)` faellt z. B.
  `SystemRoot` weg und `claude.exe` (Bun) startet mit rc=1 ("%SystemRoot% … is not set").
  Werkzeuge, die den Worker nachbauen, muessen `os.environ` SELBST uebergeben.
- R13w (2026-09-28, Commit `1eee551`): AUSSENSICHT (Meta-Review), Plan vorher freigegeben.
  Neues Modul `hx/aussensicht.py` + `prompts/aussensicht.md` + `[meta]` in harness.toml.
  Auftrag: "stimmen Messgroessen, Plan und Annahmen noch?" (nicht "war der Batch gut?"),
  frische Session, Reviewer-Modell, nur Read/Grep/Glob + vier Nur-Lese-Git-Befehle.
  Ausgabe strikt: `<AUSSENSICHT>`, je Befund `<BEFUND n gewicht empfaenger>` mit
  Beleg/Aussage/Empfehlung, `<PRUEFUNG id status/>` zu frueheren Befunden; max 7, nach
  Gewicht sortiert. Beleg gelockert gueltig: Datei:Zeile ODER Zahl+Quelldatei ODER
  "Fehlstelle: gesucht in …". Empfaenger Reviewer -> je Befund EINE /claude-Nachricht;
  Nutzer -> Telegram + /fragen. Ablage runs/meta-<batch>.md(+.json/.jsonl), Register
  state/meta_befunde.json; /bilanz-Zeile + /status-Zeile.
  Ausloeser (`faellig`): vorgemerkt (/meta), alle 10 Batches (ERSTE loest der Nutzer aus -
  sonst feuert der erste Start nach 207 Batches sofort), Worker-Abbruch, Marker-Zeilen
  `MEILENSTEIN ERREICHT:`/`ABBRUCHKRITERIUM ERREICHT:` in den letzten Review-Summaries,
  B-Schritt-Stillstand (Pflichtzeile `B-SCHRITT: n/5 …` im Reviewer-Prompt), C-Kernzahl-
  Stillstand NUR ueber die letzten C-Batches (`ist_b_batch` = B-SCHRITT-Zeile vorhanden).
  Je Batch genau EINMAL (`geprueft_batch`; `/meta` sticht den Merker).
  Lauf SYNCHRON, Pruefpunkt in `_loop` VOR dem Review -> Reviewer-Befunde stehen im selben
  Review; laeuft ein Worker, wird nur vorgemerkt. `hx.cli meta`/`control meta.ctl` bei
  laufendem Harness = nur vormerken (nur der Harness schreibt den Zustand).
  `prompts/reviewer.md`: Pflichtzeile B-SCHRITT (B-Batches), bedingte Meilenstein-/
  Abbruchzeilen, Antwortpflicht `M<batch>-<n>: uebernommen/abgelehnt, Grund …`
  (`antworten_uebernehmen` -> Status im Register; unbeantwortet bleibt "offen").
  Tests `tests/test_r13w_fixes.py` (29), volle Reihe **528 Tests OK**.
  Beleg `docs/_r13w_belege.md`, Doku `docs/bedienung.md` 12e.
- NEBENBEFUND (2026-09-28, gemessen): Als R13w committet wurde, LIEF der Harness NICHT -
  `state/run.json` = STOPPED (Batch 207, Phase "gate Batch 208"), letzter Logeintrag
  14:22:53 UTC "Harness beendet sich nach Stopp", nur ein `hx.cli watch` (PID 13352) lebte.
  Vor Arbeiten am "laufenden" Betrieb IMMER erst `state/run.json` + Prozessliste pruefen;
  die Nutzerangabe "laeuft gerade" muss nicht stimmen. (Spaeter lief B209 wirklich: dann
  nur lesen, .py-Aenderungen greifen ohnehin erst nach Neustart, `prompts/*.md` je Lauf.)
- ORDNER-KONVENTION `runs/b<N>/` (R13x, gemessen an b205..b209 - haeufigste Fehlerquelle):
  `orchestrator.review` schreibt das Review mit `ziel=rdir` = `runs/b<expected_batch>`,
  also in den Ordner des NAECHSTEN Batches. In `runs/b<N>/` liegen damit
  auftrag/stream/result/antwort des Batches N, aber `harness-facts.md`, `review.md` und
  `reviewer.jsonl` des Batches **N-1** (Kopfzeile "Review: bewertet wird Batch N-1").
  Beleg: b208/harness-facts.md nennt 47m26s (= b207), b209/harness-facts.md nennt 19m20s
  (= b208). Wer Laufzeit/Kosten eines Batches braucht, liest `runs/b<N>/result.json`.
- R13x (2026-09-28, Aussensicht-Befund M208-3, vier Punkte):
  (a) Die C-Koepfe-Zeile kommt aus `analysis/_preflight_<N>.txt` (maschinengeschrieben, ab
  B198 vorhanden), nicht aus der Worker-Prosa: B202/B203 schreiben 53/1272, gemessen sind
  45/1080 bzw. 59/1416. (b) `Paket E offen` (keine Preflight-Zeile) kommt aus der
  **Ist-Spalte** der Soll/Ist-Tafel; die Vorhersagetafel Paragraph 5 steht in JEDEM
  Dokument davor und darf nie als Messwert gelten (B206: Soll Bl 15/1083, Ist Bl 17/1202).
  Lese-Regel `stand.ist_wert`: letzte Zeile mit dem Etikett (Markup weg, klein), darin die
  letzte Zelle, die MIT dem Zahlenmuster BEGINNT (Prosa-Spalte "Abweichung" faellt raus).
  (c) Laufzeit/Abbruch aus `result.json` (Rueckfall `runs/b<N+1>/harness-facts.md` nur mit
  passender Kopfzeile). (d) `/status` nach dem Lauf aus `result.json`: die Live-Zahlen
  (`state.data["live"]`) haben KEINE Ausgabe-Tokens - DeepSeek liefert sie erst im
  `result`-Ereignis (B207 Live $0.0903 gegen echt $0.1727).
  Werkzeuge: `stand.kernzahlen` (eine Reihe fuer alle Anzeigen, `c_quelle` je Eintrag),
  `stand.ist_wert`, `stand.lauf_ist`, `orchestrator.letzter_batch_zeile`.
  Belege `docs/_r13x_belege*.{md,txt}`, Tests `tests/test_r13x_fixes.py` (32; echte
  B202/B203/B206-B208-Belege + Attrappen). Volle Reihe 560 OK.
- R13y (2026-09-28, Commit `e889ea3`): KENNUNGEN FUER FRAGEN (Nutzerauftrag, kein neuer
  Befehl). Neues Modul `hx/fragen.py`.
  Kennungen: Ankerposten `A5` (Postennummer), Reviewer-Marker `R209-1` (Review, das B209
  bewertete - der Ordner ist b210; `fragen.bewerteter_batch` liest die Fakten-Kopfzeile,
  Rueckfall Ordner-1), Aussensicht `M208-1` (vergleicht sie selbst).
  KEIN Zustandsspeicher: alles abgeleitet (Ankerkopf, letztes Review, meta_befunde.json,
  `inbox/claude/*.md` + `inbox/done/*.md`). Status: offen -> beantwortet (Nachricht liegt
  noch in der Queue) -> aufgenommen (Gate-`claude_queue_ids` oder done/) = weg aus /fragen.
  Antwort: `/claude A5 ja` / `M208-1: abgelehnt, weil …` - fuehrende Kennungen (mehrere,
  tolerant kleingeschrieben, Trenner , ; :), Anhang mit Wortlaut+Empfehlung; unbekannte
  Kennung = NICHT einreihen + gueltige nennen. Auch `hx.cli send claude` prueft das.
  `stand.fragen_text` ist nur noch ein Eingang (Import im Aufruf - `fragen` liest `stand`,
  ein Modulimport waere ein Kreis). `/status` zeigt eine Zeile "Fragen an dich: …".
  Aussensicht: `entscheidungstraeger` teilt Befunde nach Traeger (Nutzer nur Ziel/Scope/
  Budget/fruehere Nutzerentscheidungen; sonst Reviewer; beide = zwei Befunde `M208-5a`
  Nutzer / `M208-5b` Reviewer; `verteile` ueberschreibt das Modell und loggt `umgeleitet`/
  `geteilt`). `aussensicht.fragen_zeilen` entfaellt (M-Befunde stehen direkt in /fragen).
  Achtung Wortliste: NICHT "ziel" allein - "Ziel des naechsten Batches" ist Zuschnitt und
  muss beim Reviewer bleiben (Test).
  Tests `tests/test_r13y_fixes.py` (27), volle Reihe **588 Tests OK**.
  Belege `docs/_r13y_belege.md` + `_r13y_belege.txt` + `_r13y_fragen_echt.txt`,
  Doku `docs/bedienung.md` Paragraph 16/16a/16b + neuer Paragraph 17 "Was nehme ich wann".
- TIPP Belegdateien: `python skript.py *> datei` schreibt die Umlaute in der
  Konsolencodepage um ("pr├╝ft"). Belege im Skript SELBST als UTF-8 schreiben (StringIO
  sammeln und am Ende `open(..., encoding="utf-8", newline="\n")`).
- R13z (2026-09-28, Commit `a7841b0`): TAKT 3, QUOTE, ZWEI PFLICHTABSCHNITTE IM REVIEW.
  1. `harness.toml [meta] every_batches` 10 -> **3** (vorlaeufig; Begruendung
  `docs/bedienung.md` §12e, Auswertung nach einer Woche anhand der Quote). Dieselbe Zahl
  als Vorgabe in `aussensicht.STANDARD` (sonst greift bei fehlendem Schluessel still ein
  anderer Takt). `/bilanz` UND `/status` zeigen: "Aussensicht: n Befunde, davon u
  uebernommen, a abgelehnt, o offen   (letzte Aussensicht: Batch N; k Befunde in diesem
  Lauf; Takt: alle 3 Batches)" (`aussensicht.klasse/quote/zeile`; `orchestrator.meta_zeile`
  setzt KEIN zweites "Aussensicht:" davor). Klassen: uebernommen = uebernommen|beantwortet
  (altes R13w-Wort)|erledigt; abgelehnt = abgelehnt|verworfen; ALLES ANDERE (auch falsch
  geschrieben) = offen - `offene()` benutzt dieselbe Klasse. `antworten_uebernehmen`
  speichert das Verdiktwort so, wie der Reviewer es schreibt ("übernommen" ->
  "uebernommen", vorher wurde daraus "beantwortet"). Altbestand im echten Register
  (M208-2/-4) steht noch als "beantwortet" und zaehlt richtig.
  2. `prompts/reviewer.md`: Pflichtabschnitt `## VERALLGEMEINERUNG` zwischen `</DS_TOOLS>`
  und `<DS_INSTRUCTION>` (im review.md, NICHT in der TELEGRAM_SUMMARY; der Harness wertet
  ihn nicht aus, `review_ok` bleibt unberuehrt): je Befund (a) Fehlerklasse (b) verwandte
  Faelle + WIE die Instruktion sie mitprueft (c) was sie ausdruecklich NICHT prueft.
  Beispiel: F1 (slw-Feldvertauschung) -> alle Formen mit rS in Feld 6-10, rA in Feld 11-15.
  3. Ankerposten MUESSEN entscheidbar sein; naechster Review formuliert A1-A3 neu oder
  schliesst sie (`GESCHLOSSEN`). Dafuer musste der Parser mitziehen: `stand.entscheidbar`
  nimmt jetzt auch `Vorschlag: A`/`Empfehlung: B` und `bei A:`/`bei B:`; A/B-Frage wird
  auch ohne Fragewort erkannt, wenn `(A)`/`(B)`, `A oder B` oder "Weg A" im Posten steht
  (`_fragesatz`); "Vorschlag: Abstand" ist KEINE A/B-Empfehlung (Wortgrenze).
  Anzeige: "Empfehlung: A | bei A: … / bei B: …" in /fragen und im `anhang` (`_folgen`).
  Tests `tests/test_r13z_fixes.py` (24), volle Reihe **612 Tests OK** (375 s).
  Belege `docs/_r13z_belege.md` + `_r13z_belege.txt`.
- R13aa (2026-09-28, Commit `68f1537`): NACHBESSERUNG AUS DER AUSSENSICHT (runs/meta-209.md).
  1. STRANG-KLASSIFIKATION: der Ausloeser "Kernzahl ohne Bewegung" hielt B208/B209 fuer
  C-Batches, weil `ist_b_batch` allein an der Pflichtzeile `B-SCHRITT:` hing - die fehlt in
  JEDEM Review seit B205. Neu: `stand.strang_von_batch(cfg, batch) -> {"strang","quelle"}`
  aus 4 Quellen: (1) Pflichtzeile im Review (`runs/b<N+1>/review.md` - die Ordner-Konvention
  ist die Falle!), (2) Marker im Auftrag, der DIESEN Batch nennt, (3) Zeile, die mit
  "Strang B/C" BEGINNT (Auftrags-Kopf), (4) `Mischverhaeltnis ...` in hybrid-plan.md
  (`stand.plan_mischung`). Fremde Erwaehnungen zaehlen NICHT ("B210 = C-Batch" im
  b209-Auftrag). Unbekannt = "" zaehlt wie bisher als C-Batch (nichts raten).
  Pflichtzeile-Warnung: `stand.pflichtzeile_hinweis` + Block
  "=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===" im Review-Prompt
  (`orchestrator.review_context` -> `reviewer.build_prompt`), `orchestrator.pflichtzeile_melden`
  schreibt ins Protokoll (B: warn, C: info).
  2. BELEGREGEL ERWEITERT (`aussensicht.beleg_gueltig`): zusaetzlich "Eingabe <Abschnitt>",
  "=== <BLOCK> ===" , "runs/b<N>" und "runs/b<N>/result.json". Verworfene Befunde werden
  NICHT weggeworfen: `verworfene_speichern` legt sie als zweite Liste ("verworfen") in
  state/meta_befunde.json (Kennung `M209-v1`; `ledger_schreiben` OHNE "verworfen" loescht
  die Liste nicht). `/fragen` zeigt sie als "AUSSENSICHT (verworfen - pruefen?)" mit dem
  nicht anerkannten Beleg + Quelle - nur wenn der NEUESTE Lauf (runs/meta-*.json,
  `aussensicht.letzte_bericht_batches`) welche verworfen hat. `fragen._RE_ID` kennt die
  `-v`-Form; `anhang` nennt jetzt auch die Quelle. Die Quote zaehlt sie NICHT.
  3. HOCHRECHNUNG GETRENNT (`stand.durchsatz` + `kalender_zeilen` + `_mischung_zeile`):
  "Mittel der letzten N (B+C gemischt)" (gekennzeichnet, nicht mehr gerechnet), "nur
  C-Batches: +X je C-Batch", "Mischung: c C von n im Fenster; Regel hybrid-plan.md",
  dann "-> x C-Batches" und "-> ca. y KALENDER-Batches" (x / Anteil; Anteil aus der Regel,
  sonst gemessen). Die drei Vorratsklassen rechnen in C-Batches. Alte Sammelzeile
  "noch ca. N Batches fuer die K offenen Koepfe" entfaellt.
  Tests `tests/test_r13aa_fixes.py` (33, echte Belege B207-B210 + hybrid-plan.md),
  volle Reihe **645 Tests OK**. Mitgezogen: test_r13w_fixes (3 Stillstands-Tests auf die
  Ordner-Konvention), test_r13s_fixes, test_r13t2_fixes.
  Belege `docs/_r13aa_belege.md` + `_r13aa_belege.txt`; Doku §12e/§12f/§14c/§16a.
- R13ab (2026-09-28, Nutzerpruefung): DER SYSTEMPROMPT KAM BEI `--resume` NICHT AN.
  GEMESSEN (tools/r13ab_probe_systemprompt.py, Beleg docs/_r13ab_probe.txt): eine geaenderte
  `--append-system-prompt-file`-Datei wird in einer laufenden Session NICHT neu gelesen
  (erst PROBE-A, nach Aenderung auf PROBE-B per --resume weiter PROBE-A). Der Harness haengt
  sie bei JEDEM Aufruf an (reviewer.build_command) - das genuegt NICHT.
  Deshalb fehlte die Pflichtzeile `B-SCHRITT:` in den Reviews B209/B210: die Reviewer-Session
  war am 2026-09-27T22:02:56Z angelegt, die Regel kam erst mit R13w (2026-09-28T16:32:52Z).
  Der Reviewer hat sie NICHT ignoriert (also kein `review_ok`-Umbau!).
  Auch wichtig: der mitgeschriebene `logs/review-prompt-*.md` IST NUR DER NUTZER-PROMPT -
  die Rollenanweisung steht dort nie. Wer pruefen will, ob eine Regel ankam, muss die
  SESSION-Zeit gegen die Commit-Zeit der prompts-Datei halten.
  FIX: `reviewer.prompt_hash` (12 Hex) + `state.reviewer_new_session(prompt_hash=…)`;
  `orchestrator.do_review` rotiert bei Abweichung (eine Session ohne Hash rotiert EINMAL).
  `rotate` ist jetzt ein lokaler Steuerbefehl (control.NAMES) + `hx.cli rotate` ->
  `_do_rotate` setzt `reviewer.force_rotate` (vorher wurde das Flag nur gelesen).
  Ausserdem (Punkt 4): `/fragen` hat zwei Listen - `ENTSCHIEDEN`-Zeilen stehen unter
  "ZUR KENNTNIS (Veto per /claude <Kennung> moeglich)" (`zur_kenntnis` im Posten,
  `_liste_zeilen`), `/status` zaehlt sie getrennt ("n offen, m zur Kenntnis").
  Tests `tests/test_r13ab_fixes.py` (17); test_r13b/r13/r13e tragen in ihren kuenstlichen
  Reviewer-Zustaenden jetzt den prompt_hash (sonst greift die Hash-Rotation).
- R13ac (2026-09-28, Aussensicht M210-1..4 + Nutzerpruefung): BATCH-UHR + TREND + ZAEHLER.
  GEMESSEN (tools/r13ac_probe_hook.py, echtes Worker-Modell, Beleg docs/_r13ac_hook.txt):
  ein `PostToolUse`-Hook ueber `--settings <datei>` KOMMT BEIM MODELL AN
  (`hookSpecificOutput.additionalContext`; das Modell nannte die Zeile woertlich, inkl. der
  auffaelligen Grenzen 77/123) - fuer weitere Hook-Ideen ist der Weg damit offen (Doku:
  code.claude.com/docs/en/hooks; `--bare` schaltet Hooks ab).
  EINGEBAUT: hx/uhr.py = EINE Quelle fuer "seit wann laeuft der Batch":
  `state/run.json -> worker.started_at`. Benutzer: watch (`Watcher._uhr_teil`), /status,
  tools/batch_uhr.py (PostToolUse-Hook), worker.build_prompt (absolute Startzeit im Vorspann).
  FALLSTRICK/GEMESSEN: watch zaehlte vorher ab `Watcher.started` (Start des ZUSCHAUERS):
  "Batch 210 laufend: 200.6 min" bei 46 min Laufzeit. Nach einem Lauf ist
  `worker.started_at` WEG (`state.worker_finished` loescht `worker`) - dann ist
  `runs/b<N>/result.json` die Quelle (`duration_s`, Gegenprobe `finished_at - duration_s`).
  TREND (M210-2): `stand.c_trend` liest die Zeile "C Koepfe" je analysis/_preflight_<N>.txt;
  `n` = SPANNE in Schritten, es werden n+1 Dateien gelesen (n=12 -> B198..B210),
  B198 17 -> B210 78 = +61. Der Durchsatz nennt ZWEI Zaehler getrennt (C aus Preflight,
  R207 aus den Bilanzdateien) und markiert ein Fenster mit Luecke als LUECKENHAFT
  (B209 hat keine `_m209/_bilanz*.txt`). C-Rate = Delta / benachbarte C-Schritte (6.1),
  NICHT / Anzahl C-Batches (sonst Faktor n/(n-1) zu klein).
  "C verifiziert" (M210-3) kommt aus `Bahnabdeckung ... verifiziert <n>` (B210: 55 von 78);
  eine `Nachrueckliste` mit eigener verifiziert-Zahl haette Vorrang. Kopfzahl heisst jetzt
  "C Koepfe referenzgleich".
  PLAN (M210-4) = Zeile `SOLL-KOEPFE: <n>` der Instruktion, sonst "-"; MEDIAN nur ueber
  C-Batches mit SOLL>0. `stand.geplante_koepfe` (Adress-Heuristik) ist NICHT mehr PLAN.
  Tests tests/test_r13ac_fixes.py (37, echte Preflight-Dateien), mitgezogen
  r13s/r13t/r13t2/r13aa. Commits 13cec08 (Code) + 907d534 (Testfix/Belege).
  VOLLE Reihe am Gate vor B212: **700 Tests OK** (378 s).
  SICH SELBST REINGEFALLEN (der R13x-Fallstrick, zum zweiten Mal): die ersten
  "echte-Dateien"-Tests lasen `stand.c_trend(load_config(), 12)` direkt aus dem lebenden
  Repo. Waehrend der vollen Reihe beendete B211 und schrieb `_preflight_211.txt` ->
  Fenster rutschte auf B199..B211 -> drei Tests rot ("211 != 210"). LEHRE: echte Belege
  fuer Tests IMMER erst in `tests/_tmp_*/decomp/analysis` KOPIEREN (preflight + die
  `_m<N>/_bilanz*.txt`), dann dort pruefen; zusaetzlich ein Test "Kopie == lebendes Repo".

- R13ac2 (2026-09-29, zwei Nutzerpunkte vor dem Neustart am Gate B212), Commit 9208df0.
  1) BATCH-ART: `stand._pflicht_strang` liest ZUERST die Pflichtzeilen der Instruktion
     `^STRANG: B|C` bzw. `SOLL-KOEPFE: <n> (Strang B, …)`; `stand.auftrags_text(cfg,b)`
     nimmt `runs/b<N>/auftrag.md` (ab "=== AUFTRAG") und sonst `runs/b<N>/review.md`
     (ab "<DS_INSTRUCTION>") - letzteres ist der Fall "Batch steht am Gate" (B212).
     GEMESSEN: B211 und B212 jetzt B (vorher "" -> als C gezaehlt, B211 loeste deshalb
     eine Aussensicht aus, runs/meta-211.md); B208/B209 B, B210 C unveraendert.
  2) `stand.posten_status(text)` -> (offen, n_geschlossen, mitgezogene ohne eigenes Wort).
     Sammel-Schluss erkannt an "Alle Posten GESCHLOSSEN", "GESCHLOSSEN als
     Entscheidungs-/Ankerposten/-frage", "Keine offene (Nutzer-)Frage". Mitgezogene Posten
     sind KEINE offenen Fragen; `fragen._anker_posten` legt sie mit `zur_kenntnis=True`
     unter "ZUR KENNTNIS" (Label "(Sammel-Schluss im Anker)"). A4/A5 sind damit weg aus
     "OFFENE FRAGEN". FALLSTRICK: `frage` darf bei einem offenen, NICHT entscheidbaren
     Posten nicht auf den Rohtext gesetzt werden - sonst steht dort nicht mehr
     "UNKLAR FORMULIERT" (test_r13s/test_r13y wurden rot).
  Volle Reihe: **709 Tests OK** (427 s).
- R13ac3 (2026-09-29, Nutzerpunkt 3), Commit ab0facc: TIEFENPROBE der Aussensicht.
  Je Lauf zieht `aussensicht.tiefenprobe_waehlen(cfg, zufall=None)` EINEN Batch aus den
  letzten 10 gelaufenen (`runs/b<N>/result.json` = gelaufen); Kandidaten = Fenster minus
  `state/meta_befunde.json -> tiefenprobe.gezogen`; alle dran -> neuer Zyklus.
  `tiefenprobe_stand` liest die Rotation IMMER gegen das aktuelle Fenster;
  `ledger_schreiben` bewahrt den Schluessel `tiefenprobe` (wie `verworfen`);
  gemerkt wird erst nach einem Lauf MIT Ergebnis (`run()`), ein Abbruch verbrennt keinen
  Batch. `bericht` schreibt "- Tiefenprobe: Batch N aus dem Fenster B..B.." (auch wenn das
  Modell die Nummer nicht nennt); `runs/meta-<batch>.json` traegt `tiefenprobe`.
  Prompt-Block "=== TIEFENPROBE (Pflicht): BATCH <N> ===" + Pflichtabschnitt fuer Funde
  aus aelteren Batches (gegen HEAD/Anker/heutige Belege pruefen; behoben = KEIN Befund,
  sondern Zeile "geprueft: <Fund>, behoben in B<N> (Beleg)"). Gleiche Regel in
  `prompts/aussensicht.md`.
  GEMESSEN am echten Stand: Fenster B202..B211. Volle Reihe: **725 Tests OK** (329 s).
- FALLSTRICK (bei R13x erlebt): "der neueste Batch" ist KEIN stabiler Bezug fuer Tests
  oder Anzeigen, solange der Harness laeuft - er schreibt laufend neue Batch-Dokumente
  (B209 schrieb sein Dokument MITTEN in die R13x-Testreihe, ein Test wurde dadurch rot).
  Reale Belege fuer Tests deshalb in eine eingefrorene Kopie legen (Tests/_tmp_*/decomp/
  analysis + runs) und dort pruefen; in den Anzeigen je Zeile den Eintrag MIT Wert nehmen
  (`bilanz._letzter_mit`), nicht "den neuesten".


- R13an (2026-09-29, Commit `3b1265e`): PARSER-MELDUNGEN. `stand.plan_mischung` nimmt
  jetzt die Zeile MIT `n B : m C` (bei mehreren die mit `ENTSCHEIDUNG`, sonst die letzte);
  `plan_mischung_pruefen` meldet "nicht erkannt" ins Log UND in die Review-Fakten
  (Muster R13ae). FALLSTRICK: solche Meldungen NICHT an denselben if/else-Zweig haengen wie
  eine andere Pruefung - die "positive Zeile" der Preflight-Pruefung verschwand dadurch
  (`test_r13ae_fixes.test_ohne_luecke_steht_die_positive_zeile` wurde rot). Fehlende Datei
  und fehlendes Verhaeltnis sind ZWEI Wortlaute ("nicht lesbar" / "nicht erkannt").
- TESTS NIE gegen Dauer-Dokumente des Decomp-Repos: `tests/fixtures/` mit eingefrorener
  Kopie (Revision im Docstring, ohne Vorspann, damit die Zeilennummern stimmen). Lebende
  Reads gibt es nur noch fuer ABGESCHLOSSENE Nummernbereiche (`_preflight_<N>.txt`,
  `port-batch<N>-*.md`, `runs/b<N>/…`) mit `skipIf`; Bestandsaufnahme:
  `docs/_r13an_bestand.txt` + `docs/_r13an_bestand_probe.py`.
- R13ao (2026-09-29, Commit `da2452e`): PREFLIGHT-ZAEHLER + FRUEH-HINWEIS.
  `streamjson.ist_preflight_aufruf` = Shell-Werkzeug UND Interpreter (`python`/`py`) mit
  `preflight.py` als Argument UND der Befehlsteil ist kein Filter (`-like`, `CommandLine`,
  `Select-String`, `Get-Content`, `git add`); `=_RE_PREFLIGHT_FILTER` ueber den GANZEN
  Befehl haette echte Laeufe verschluckt (B206: der `Get-Content` steht hinter `;`).
  GEMESSEN B206-B215: 23 Treffer der reinen Textsuche, aber nur 14 echte Starts; 9 von 10
  Batches starten den Preflight VOR der Schwelle (`docs/_r13ao_messung.txt`).
  Der Hook schreibt je Start eine Zeile nach `runs/b<N>/preflight-aufrufe.jsonl` (dafuer
  gibt `write_worker_hooks` jetzt `--run <rd>` mit; ohne `--run` schreibt er NICHTS ->
  ein schon laufender Batch bleibt unberuehrt); `worker.zaehle_preflight_aufrufe` zaehlt
  nach `result.json` (`preflight_laeufe`, `preflight_frueh`). `hx/uhr.PREFLIGHT_HINWEIS`
  traegt den Wortlaut aus dem Auftrag; die Schreibweise "Umschwellschwelle" wurde am
  2026-09-30 (R13ap, Nutzerentscheid) zu "Umschaltschwelle" korrigiert. Der Test hat den
  Text woertlich im Quelltext, damit eine Aenderung auffaellt.
- FALLSTRICK (eigene Werkzeugnutzung, zweimal passiert): einen Replace NICHT mit einer
  blossen Funktionskopf-Zeile als `oldString` verankern - dabei gingen Docstring-Zeilen in
  `hx/worker.py` verloren. Immer 3 Zeilen Kontext mitgeben.
- `harness/runs/` und `harness/state/` sind gitignoriert (`.gitignore`) - neue
  Lauf-Artefakte dort erzeugen kein Git-Rauschen. Volle Reihe nach R13ao: 983 Tests OK.
- R13ap (2026-09-30): PREFLIGHT-DATEIEN KODIERUNGSTOLERANT. GEMESSEN: von 62
  `analysis/_preflight_*.txt` sind 53 UTF-8-BOM, 5 UTF-16 LE (B155-B158 + **B216**), 4
  UTF-8 ohne BOM. `_preflight_216.txt` (FF FE) wurde als UTF-8 gelesen -> drei
  `PARSER: Zeile ... nicht erkannt` im Review von B216 (`runs/b217/harness-facts.md:23-25`),
  der C-Trend endete auf B215. Ursache liegt im Decomp-Repo: ein `*>`-Redirect in
  PowerShell 5.1 schreibt UTF-16 (B216: Preflight via `Start-Process powershell -Command`).
  GEBAUT: `util.erkenne_kodierung` / `dekodiere` / `read_text_erkannt` / `read_bytes_shared`
  (binaer, mit denselben Freigaben wie `open_shared_read`) + EINE Lesestelle
  `stand.preflight_text(pfad) -> (text, kodierung)`; alle vier Leser
  (`preflight_zeilen_pruefen`, `preflight_bahnabdeckung`, `hybrid_verlauf`,
  `preflight_c_koepfe`) gehen darueber; `stand.preflight_kodierung_hinweis` schreibt
  "Preflight B<N> in UTF-16, gelesen" als EIGENEN Block in die Review-Fakten (nicht in den
  if/else-Zweig der Preflight-Pruefung!). `worker.archiviere_preflight_vor_fortsetzung`
  kopiert weiter byteweise (`shutil.copy2`) - Kopien nie dekodieren.
  Fixture `tests/fixtures/preflight_216_utf16.txt` = Byte-Kopie (4866 B, FF FE),
  Tests `tests/test_r13ap_fixes.py` (22), Belege `docs/_r13ap_belege.md` + `_r13ap_messung.txt`.
- R13aq (2026-09-30): GESCHEITERTE AUSSENSICHT ZAEHLT NICHT. GEMESSEN: `runs/meta-217.jsonl`
  endet `subtype=error_max_turns`, `is_error=true`, `num_turns=31`,
  "Reached maximum number of turns (30)"; gelungene Laeufe meta-208..214 brauchten 17..35
  Zuege (meta-214 = 35). Ursache: `[meta] max_turns` stand auf 30 (`harness.toml`, Rueckfall
  `aussensicht.STANDARD`), gesetzt ueber `--max-turns` in `build_command`. Der Harness setzte
  danach trotzdem `letzter_lauf_batch`/`geprueft_batch` (bedingungslos im `finally`) ->
  rc=1 zaehlte als gelaufen, Takt "alle 3" rechnete von 217 (naechster Lauf B220).
  GEBAUT: `aussensicht.gelaufen(res)` = `rc == 0` UND Antwortblock (`<AUSSENSICHT>` oder
  Befund); `Ergebnis.subtype/zuege` aus dem `result`-Ereignis; im Orchestrator setzt NUR
  `gelaufen` die Takt-Marke (`geprueft_batch` dagegen auch im Fehlerfall - sonst wiederholt
  die Schleife den Lauf in JEDEM Durchgang), Fehlvermerk `gescheitert_batch/grund/ts`,
  Telegram "Aussensicht B<N> gescheitert (<Grund>), wird beim naechsten Batch-Ende
  wiederholt", keine Verdikte/Queue/Registereintrag; Wiederholung genau einmal beim
  naechsten Batch-Ende, aus ZWEI Quellen: Zustandsvermerk UND `aussensicht.bericht_zustand`
  (juengster Bericht mit `gelaufen:false` oder `rc != 0`, der nicht durch einen gelungenen
  ueberholt ist - so wird auch der alte meta-217 richtig behandelt, ohne state/runs zu
  aendern). `zeile()` nennt die letzte GELUNGENE Aussensicht + "zuletzt gescheitert: B…".
  Zuglimit: `[meta] meta_max_turns` (Alias) oder `max_turns`, Vorgabe **50**; Prompt-Frist
  "spaetestens nach <max-5> Zuegen" (`build_prompt`) + Abschnitt in `prompts/aussensicht.md`.
  `_RE_VERDIKT` + `UEBERNOMMEN_WORTE` kennen "zur kenntnis" (zaehlt wie "erledigt");
  Register-Nachtrag M213-4a ueber `docs/_r13aq_nachtrag.py --schreiben` (Probelauf ist
  Vorgabe, schreibt seinen Beleg selbst als UTF-8 - `| Out-File` verstuemmelt Umlaute).
  FALLSTRICK (Test): Attrappen fuer `aussensicht.run` mit `rc=0` brauchen eine Summary,
  sonst greift die neue Regel (`test_r13w_fixes`/`test_r13ah_fixes` angepasst).
  Tests `tests/test_r13aq_fixes.py` (30), Belege `docs/_r13aq_belege.md` + `_r13aq_messung.txt`
  + `_r13aq_nachtrag.txt`.
- R13ar (2026-09-30): ZUGUHR DER AUSSENSICHT + FRUEHWARNUNG. GEMESSEN (echte CLI-Laeufe,
  `docs/_r13ar_limit_probe_reviewer.txt`): `--max-turns N` zaehlt **Werkzeugrunden**
  (Modellantworten MIT Werkzeugaufruf) und bricht danach ab; `num_turns` im Ergebnis ist
  eine ANDERE Zahl = Werkzeugergebnisse + 1 (8/8 Laeufe geprueft). Damit ist das R13aq-Raetsel
  geloest: `[meta] max_turns = 30` stand seit R13w unveraendert (`1eee551`), meta-214 brauchte
  nur 23 Runden (`num_turns=35`) und lief durch, meta-217 genau 30 Runden ⇒ Abbruch.
  Werkzeug: `harness/harness/tools/aussensicht_uhr.py` (PostToolUse-Hook, ueber
  `--settings runs/meta-<N>-hooks.json`, geschrieben von `aussensicht.write_hook_settings`,
  gehaengt in `aussensicht.run`; `build_command(cfg, hooks_settings=…)`). Ausgabe je
  Werkzeugaufruf: "AUSSENSICHT-UHR: Zug X von Y (Werkzeugrunden). Noch R Zuege bis zum
  Abbruch."; ab `X >= Y-5` zusaetzlich "JETZT die Antwort im Blockformat schreiben,
  Unvollstaendiges als nicht geprueft kennzeichnen." GEMESSEN mit echtem Lauf: das Modell
  nennt die Zeile woertlich (`docs/_r13ar_probe_hook.txt`).
  FALLSTRICK: die Hook-Eingabe zaehlt man NICHT (parallele Aufrufe in einer Antwort kaemen
  mehrfach) - die Runden werden im Transcript gezaehlt (`transcript_path` aus der
  Hook-Eingabe, `hx.streamjson.runden_aus_zeilen` = dieselbe Zahl wie `max_turns`).
  `streamjson.StreamStats.runden()` (neue Methode) + `Ergebnis.zug_runden`; `runs/meta-<N>.json`
  traegt `zug_runden`, der Bericht "- Zuege (Werkzeugrunden): X von Y - num_turns laut CLI: N".
  FRUEHWARNUNG `aussensicht.limit_hinweis(batch, runden, grenze)` = Telegram + Zeile
  "- LIMIT PRUEFEN: …" ab > 80 % des Limits, Log "Zuglimit fast erreicht".
  NEBENBEFUND: im WORKER-Umfeld (DeepSeek base_url) wirkt `--max-turns` NICHT
  (`docs/_r13ar_limit_probe.txt`, Limit 2 ⇒ 4 Zuege); im Reviewer-/Abo-Umfeld wirkt es.
  Tests `tests/test_r13ar_fixes.py` (27), Belege `docs/_r13ar_belege.md` (+ `_r13ar_zuege.txt`,
  `_r13ar_limit_probe*.txt`, `_r13ar_hook_eingabe.txt`, `_r13ar_cli_hilfe.txt`).
- R13as (2026-09-30, Aussensicht M218-1, Commit `202654e`): REIHENFOLGE-WAECHTER. Neues Modul
  `hx/reihenfolge.py` wertet nach jedem Batch `runs/b<N>/stream.jsonl` gegen den Zeitpunkt des
  ersten Commits mit BETREFF `B<N>: Vorhersage` aus (`git log --all --format=%H%x1f%cI%x1f%s`;
  BOM verkraftet, Rumpf-Treffer zaehlt nicht). Gezaehlt werden port/-Schreibzugriffe DAVOR
  (Edit/Write mit `file_path` unter port/, Umleitung nach port/, Copy/Move MIT port/ als ZIEL,
  Set-Content/Remove-Item/…, git checkout|restore|stash|reset|clean auf port/ oder ganzen Baum),
  alle mtime-Setzer im Batch (`LastWriteTime =`, touch, os.utime …) und GETRENNT die Zugriffe in
  einem Worktree `erkundung-b<N>`. `streamjson.StreamStats.zeilen` + `tools[i]["zeile"]` liefern
  die Belegstelle (`stream.jsonl:24699`).
  GEMESSEN B208-B219: Abweichungen B208 (20), B209 (8), B211 (32), B213 (4), B214 (20), B218 (18);
  sauber B210/B212/B215/B216/B217; erster mtime-Befehl der Reihe in B218 (`:80521`).
  FALLSTRICK 1: PowerShell schreibt `Copy-Item`/`Remove-Item` GROSS - ohne `re.IGNORECASE` in
  `_verb_treffer` wurde die Wiederherstellung still uebersehen (Test hat es aufgedeckt).
  FALLSTRICK 2: der TEXT in `-Value` nennt in B217 port/ (`:73332`) - Werte von
  `-Value/-Content/-Filter/-Pattern/…` und Zeichenketten mit Backtick/`#` sind keine Pfade;
  Here-Strings (`@'…'@`) werden vorher entfernt. Kein Treffer sind Lesen unter port/, port/build-
  Artefakte und `git status --porcelain port/ Makefile`.
  result.json: `reihenfolge_port_vor_vorhersage`, `erkundung`, `mtime_manipulation` (+
  `reihenfolge_port_gesamt/vorhersage_ts/commits/fehler`); Faktenzeile `- REIHENFOLGE-WÄCHTER:
  sauber` bzw. `ABWEICHUNG - n port/-Schreibzugriffe vor der Vorhersage, m mtime-Befehle`,
  ohne Vorhersage-Commit ausdruecklich "nicht einzuordnen". Tests `tests/test_r13as_fixes.py` (42)
  mit Ausschnitten aus dem echten B218-Mitschnitt; Belege `docs/_r13as_belege.md` +
  `_r13as_belege.txt` (`python -u docs/_r13as_belege.py schreiben` rechnet jeden Batch nach).
- R13at (2026-09-30, Commit `21ac8ac`): ZUGLIMIT 70, FRIST AB LIMIT-8. `[meta] max_turns` 50 -> 70
  (Alias `meta_max_turns` hat Vorrang); `aussensicht.FRIST_ABSTAND = 8` ist EINE Quelle:
  `build_prompt` schreibt "spaetestens nach <Limit-8> Zuegen", `write_hook_settings` gibt dem Hook
  `--limit 70 --frist 8` mit (Rueckfall im Hook: 8). GEMESSEN (`docs/_r13at_messung.txt`, zwei
  Quellen): die Zahl im Auftrag ist `num_turns`, nicht die der CLI - meta-218 num_turns=41, aber
  30 Runden von 50; meta-214 num_turns=35, 23 Runden von 30 (deshalb lief er durch); meta-217
  brach bei genau 30 Runden ab. Merke: `runden >= grenze - abstand` heisst, ein GROESSERER
  Abstand feuert FRUEHER (Testfalle!). Tests `tests/test_r13ar_fixes.py` (30),
  `tests/test_r13aq_fixes.py` (30).
- R13au (2026-09-30, Commit `1c99cb1`): RECHNERLAST. Neues Modul `hx/last.py` (`Recorder`,
  60-s-Takt, Start in `worker.run_batch`, Stop im `finally`, `res.last`); misst CPU gesamt
  (`psutil.cpu_percent(interval=1.0)` - mit `cpu_percent(None)` direkt nach dem Start kam 0.0),
  freien RAM und python-/java-Prozesse in drei Gruppen: eigene (Harness-Baum ueber ppid), ghidra
  (Java mit ghidra/GhidraMCP/-Dghidra.home), fremd (Rest; nur das erzeugt `fremdlast_minuten`).
  Rueckfall ohne psutil: `GetSystemTimes`/`GlobalMemoryStatusEx` per ctypes, Prozessliste dann nur
  per tasklist (`last_quelle` = windows). result.json: `cpu_mittel`, `cpu_max`, `ram_frei_min`,
  `fremdlast_minuten` (+ `last_*`); Faktenzeile `- RECHNERLAST: CPU … (Spitze …), RAM frei min …,
  FREMDLAST in n von m Minuten (bis k Prozesse: …), Ghidra lief mit (…)` bzw. "nicht gemessen
  (<Grund>)". Die Fremdlast ist GRUNDRAUSCHEN (watch, Bridge, VS-Code-Helfer) - die Spitze steht
  deshalb in der Zeile. ARBEITSREGEL (bedienung.md 12u + Einleitung): waehrend ein Batch laeuft
  nur die betroffenen Testdateien, volle Reihe nur am Gate/gestoppt, Zustand vorher aus
  state/run.json nennen. Maschine gemessen: i7-930, 4 Kerne/8 Threads, 6135 MB RAM, Messlauf
  84 % belegt (986 MB frei), Worker (claude.exe) 211 MB RSS, Ghidra `-Xmx2g`
  (start-ghidra-headless.ps1:100). Tests `tests/test_r13au_fixes.py` (17).
- R13av (2026-09-30, Commit `2f05afa`): VOLLE TESTREIHE ALS BELEG. `docs/_r13av_lauf.py`
  faehrt sie genau wie die Kommandozeile (`os.chdir(harness)` + `discover("tests",
  pattern="test_*.py")` - OHNE `top_level_dir`, sonst "Start directory is not importable",
  weil `tests/` kein Paket ist) und schreibt `docs/_r13av_volle_reihe.txt` SELBST als UTF-8
  mit LF (unittest schreibt nach stderr, eine Konsole-Pipe verstuemmelt Umlaute). Kopf:
  Zeitpunkt, HEAD, Harness-Zustand (R13au-Regel); Fuss: Dauer, Testzahl, Fehler, Ergebnis.
  Stand 30.09.2026: **1124 Tests, 0 Fehler/Fehlschlaefe, OK in 438,5 s** (auf ausdruecklichen
  Wunsch trotz laufendem Batch 219 - die Lastregel wurde bewusst verlassen). Die Datei traegt
  nur den Runner-Strom (Punkte + Bilanz, ~1,5 KB), nicht die stdout-Ausgaben der Tests; die
  aelteren `_r13a*_volle_reihe.txt` (~10 KB) waren Shell-Umleitungen und enthalten sie mit.
  `--ziel=` wird gegen `docs/` aufgeloest (der Runner wechselt nach `harness`), Beleg
  `docs/_r13aw_volle_reihe.txt`: 1174 Tests, OK in 495,3 s.
- R13aw/ax/ay (2026-09-30, Commits `240ac6c`/`36912e0`/`329d3ec` + `6b1eb08` Doku): drei
  Fixes nach Aussensicht B219. (1) ANTWORTDATEIEN: `worker.antwort_teile(stats)` nimmt ALLE
  `result`-Texte - `stats.final_text()` ist der LETZTE (hx/streamjson.py:1192), deshalb
  enthielt `runs/b214..218/antwort.md` nur "NACHRUECKLISTE ERLEDIGT", der Pflichtbericht stand
  allein im `stream.jsonl`. `_finish_run` schreibt jetzt den ERSTEN Text nach `antwort.md`,
  jeden weiteren nach `antwort-forts<k>.md` (VOR dem payload, sonst fehlt
  `result.json[antwort_dateien]`); `worker.antwort_text(rd)` baut daraus den Volltext (Bericht,
  dann Fortsetzungen mit Ueberschrift; ein `antwort-bericht.md` steht vorn) und ist die Quelle
  fuer `review_context.worker_report`, `/send ds`, Snapshot, Demo und den Aussensicht-Prompt.
  Nachtrag `docs/_r13aw_nachtrag.py --schreiben` erzeugte `antwort-bericht.md` fuer B214-B218
  (fasst `antwort.md` NIE an). (2) UEBERTRAG: `worker.preflight_gestartet(stats)` (echter Start
  ueber `streamjson.ist_preflight_aufruf`; Nennung in description, `Select-String`-Filter oder
  `Read` zaehlen NICHT) -> `fortsetzung_pruefen` gibt
  `{"ja": False, "grund": "Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG",
  "uebertrag": True}`; Log + Faktenzeile "Kein Fortsetzungsanstoss: …", `result.json`
  `fortsetzung_grund`/`fortsetzung_uebertrag` (auch in `stats`, davon liest
  `orchestrator.fortsetzungen_zeile`). (3) KENNZAHLEN: `stand.paket_e_messung` liest
  `analysis/_m<N>/_c_paket_e*.txt` (`Paket E, offen GESAMT`, Datum aus dem Kopf, `_archiv/`
  ausgenommen; Auswahl (Datum, mtime, `nachher` vor `vorher`, Name) - `_vorher`/`_nachher`
  tragen denselben Kopf). Verbraucher: `bilanz.gesamt_block`, `stand.durchsatz`/
  `durchsatz_zeilen`, Projektzahl. Nichts gemessen -> "nicht gemessen seit B<k>", KEINE
  Hochrechnung aus der Soll/Ist-Ist-Spalte. `plan_ist_text`-Median jetzt ueber die ZUWaechse
  der C Koepfe je C-Batch (`c_delta`, +7/+5 -> 6), nicht ueber Summen (das ergab 88).
  Fallstricke: `standmod`-NameError in `bilanz.gesamt_block` (Modul importiert `stand`);
  `/memories/repo/*.md` liegen ausserhalb des Repos -> Spiegel `analysis/_memory/`.
- R13az (2026-09-30, Commit `b8a2def`): ZWEI FESTE PRUEFPUNKTE in `prompts/aussensicht.md`
  (Punkt 7 + eigener Abschnitt) und `prompts/reviewer.md` (Punkt 6 + eigener Abschnitt).
  (1) Messziel gegen Messgroesse je Strang: B = Anteil nativer Koepfe an den ausgefuehrten
  Schritten (A4, `hybrid-plan.md:9-10`, `readme.md:21`), C = referenzgleiche Koepfe; eine
  mitlaufende Ersatzzahl ist ein Befund und muss in der Instruktion als Ersatzzahl stehen;
  Zahl seit mehreren Batches bei 0 = Befund. Anlass `M221-2a/2b` (0 von 108546736 = 0 %,
  `bericht-b221-berichtspunkt-hybrid.md:128`). (2) „fehlt"/Blockade nur nach Grep auf den
  **Bezeichner** (Adresse/Symbol, nicht Dateiname) ueber `analysis/` + `port/`, Fundstelle
  `Datei:Zeile`, sonst `Fehlstelle: gesucht in analysis/ und port/, nicht gefunden (...)`.
  Anlass `0x40000000` (`bucket-d-fun80013d80.md:121` = 403GA-SPU, seit 16.09. geklaert,
  B220-B222 uebersehen; `runs/b222/review.md:3`). (3) Nur Reviewer: „uebernommen" gilt erst
  als erledigt, wenn die **Wirkung belegt** ist — Zeilenform
  `M214-4: uebernommen als <Ziel> - Wirkung belegt: <Datei:Zeile>` bzw.
  `… - Wirkung noch nicht belegt -> bleibt offen`. Merke: `aussensicht.antworten_uebernehmen`
  nimmt das **letzte** Verdiktwort der Zeile (`hx/aussensicht.py:1338`) — ein `offen` am
  Zeilenende haelt den Befund bewusst im Register (`M214-4`, `state/meta_befunde.json`).
  Tests `tests/test_r13az_fixes.py` (26), darunter die Prompt-Zeilen wortgleich gegen das
  Register ausgefuehrt und die zitierten Fundstellen gegen die echten Dateien (skipIf).
  Wirkung: Aussensicht liest den Prompt sofort (immer frische Session), der Reviewer rotiert
  beim naechsten Review ueber den Prompt-Hash — kein Neustart noetig.
- R13ba (2026-09-30, Commit `2c90b87`): EINE RATE JE C-BATCH (Aussensicht M221-5). Vorher
  rechneten PLAN/IST (Median ueber C-Batches mit SOLL-KOEPFE > 0: 6) und die Durchsatzzeile
  der BILANZ (Mittel ueber ALLE C-Batches: 3.0) mit verschiedenen Grundmengen -> "9" gegen
  "4 C-Batches" fuer denselben Vorrat. Neu `stand.rate_text` + `stand.c_rate` (hx/stand.py:432,
  :444) liefern beide Zahlen mit Definition in EINER Zeile
  `Median Zuwachs (Kopf-Batches): 6 | Mittel ueber alle C-Batches: 3,0` (Mittel mit
  Dezimalkomma, Harness-Ausgabe bleibt sonst ASCII); **gerechnet wird der Median**
  (`d['rate_c_koepfe']`), Rueckfall Mittel mit benannter `quelle`. Verbraucher:
  `kalender_zeilen` (Paket-E-, C-gesamt- und "nicht ausgefuehrt"-Hochrechnung),
  `_relevanz_zeilen`, `plan_ist_text` (MEDIAN-Zeile wortgleich + neue Klammerzeile),
  `durchsatz_zeilen` (neue Zeile `C-Rate je C-Batch: …`). Die alte Zeile
  `(Summen-Mittel derselben Batches, nur zur Einordnung: …)` ist ersetzt (dritter Wert,
  Summen statt Rate) - `test_r13ay`/`test_r13ac` darauf angepasst.
  FALLSTRICK: `durchsatz()` darf `c_rate()` NICHT aufrufen - das waere ein Kreis
  (`c_rate` -> `plan_ist` -> `durchsatz`); die Textbauer holen die Rate selbst
  (`durchsatz_zeilen:1666`).
- R13ba-Nachtrag (2026-09-30, Commit `b5bc803`): AUSWAHL DER PAKET-E-MESSDATEI. Der alte
  Schluessel `(datum, mtime, stand, name)` sortierte eine Datei OHNE Datum hinter jede
  datierte -> die B222-Dateien (kein `# Messung:`-Kopf) verloren gegen B219: "offen" blieb
  26 statt 25, und der Vergleich kippte zu `(B222 -> B219: -1 Koepfe / -103 Insn gebaut)`.
  Jetzt `(batch, stand-Rang, datum, mtime, name)` mit Rang `nachher`(2) > blosse Messung(1)
  > `vorher`(0) - Batchnummer aus dem Ordnernamen ZUERST, Datum nur Anzeige/-
  Gleichstand-Entscheider (`stand.py:435`). Datum tolerant in `stand.paket_e_datum`
  (`stand.py:355`, Muster `:345`, nur die ersten 15 Kopfzeilen `:352`): `# Messung: 2026-09-30
  03:33` (B219) und `… Datum 2026-09-30, HEAD …` (B222); fehlt es, gilt die Dateizeit
  (`datum_quelle="dateizeit"`, Anzeige "(Datum aus Dateizeit)", `stand.py:489`) und die
  Review-Fakten melden `PARSER: Messdatum in <Datei> nicht erkannt` (`stand.py:466`, Aufruf
  `orchestrator.py:2370` - nur der Fehlerfall). Gemessen: gewaehlt `_m222/_c_paket_e.txt`
  (25/2011), Paar B219 -> B222, `+1 Koepfe / +103 Insn gebaut`. Tests
  `test_r13ba_fixes.py` (31). MERKE: Tests, die auf LEBENDEN Repo-Dateien rechnen, machen
  sich mit dem naechsten Batch selbst ungueltig (B222 hat `_m222/...` angelegt und
  `test_r13ay::test_offener_vorrat_ist_26_nicht_38` rot gemacht) - solche Pruefungen
  gehoeren auf eine eingefrorene Fixture (`TestOffenerVorratGefroren`) oder hinter einen
  skipTest, der die Identitaet der echten Datei prueft.
- R13bb (2026-09-30, vier Commits `f26ffb8`/`e6d16a3`/`c4604e7`/`2790f61`): VIER HARNESS-PUNKTE
  aus Aussensicht B224/Review B225.
  (1) FORTSETZUNG NACH PREFLIGHT: `worker.fortsetzung_pruefen` gibt bei gestartetem Preflight
  einen Anstoss, wenn `umschalt_min - minuten >= limits.fortsetzung_min_rest_min`
  (Default 20, in `harness.toml`), sonst UEBERTRAG wie bisher; Entscheidung traegt
  `preflight_erneut`/`rest_min`; der R13ah-Aufruf `archiviere_preflight_vor_fortsetzung`
  laeuft unveraendert VOR dem Anstoss, der Anstoss-Text sagt "Nach der Nacharbeit neuer
  Preflight, der letzte gilt"; `fortsetzungen[k].preflight_erneut` + Log
  "Fortsetzung trotz Preflight".
  (2) PREFLIGHT-ZAEHLER GEGEN ARCHIV: `stand.preflight_archiv(cfg, batch)` zaehlt
  `_m<N>/_preflight_<N>_fehllauf*.txt` und `*ueberholt*.txt` (`_vor_fortsetzung<k>.txt` NICHT -
  byteweise Kopie eines gezaehlten Laufs); `stand.zaehle_preflight_aufrufe(cfg, batch)` liest
  die Aufrufdatei, `stand.preflight_zaehler_zeile(...)` liefert die Faktenzeile; result.json:
  `preflight_archiv_fehllauf`/`_ueberholt`, `preflight_ungezaehlt`,
  `preflight_laeufe_gesamt`. Gemessen fehlte je ein Fehllauf in B218 (2 statt 3), B223, B224.
  (3) MISCHREGEL: `stand.plan_mischung` nimmt Zeilen mit "Mischverhaeltnis" ODER Gilt-Wort und
  waehlt (1) letzte Gilt-Zeile, (2) letzte mit ENTSCHEIDUNG, (3) letzte mit Verhaeltnis; neu
  `zeile_nr`/`ab_batch`/`stand`/`zustand`. Die geltende Zeile "AB B222 GILT 1 B : 1 C" enthaelt
  das Wort Mischverhaeltnis NICHT - vorher gewann 2 B : 1 C (Anteil 33 % -> 50 %).
  Die PAARLISTE bleibt nur an der gewaehlten Zeile (R13an), sonst leer.
  (4) PAKET-E-KOPFZEILE: `paket_e_messung` liest ueber `util.read_text_erkannt` (BOM/UTF-16),
  Feld `kodierung`; UTF-16 + Datum lesbar ergibt eine Faktenzeile
  "PAKET-E-KOPFZEILE: … Datum erkannt"; `_m224/_c_paket_e_nachher.txt` ist UTF-8-BOM (mit
  `read_text` galt sie als datumslos).
- R13bc (2026-09-30, Commit `824844a`): REALTESTS AUF EINGEFRORENE FIXTURE UMGESTELLT.
  Anlass: drei Realtest-Gruppen prueften den LEBENDEN Repo-Stand und schalteten sich mit
  `skipTest` ab, sobald er weiterzog (gemessen: B224 +3 Koepfe ⇒ Median 6→5 ⇒ `test_r13ay`
  rot; neueste Messdatei 222→224 ⇒ `test_r13ba` skip; `hybrid-plan.md` Zeile 354→368 ⇒
  `test_r13bb` skip). Ein Test, der sich selbst abschaltet, meldet keinen Fehler mehr.
  Neue Fixture `tests/fixtures/stand_b224/` (86 Dateien, 645 KB, Stand 30.09.2026/B224):
  `decomp/analysis/` (26 `_preflight_200..225.txt`, 17 `_m<N>/_bilanz*.txt`, 9
  `_m{210,219,222,224}/_c_paket_e*.txt`, 3 `_m{218,223,224}/_preflight_<N>_fehllauf1.txt`,
  `hybrid-plan.md`) + `root/runs/b200..b225/auftrag.md` + `preflight-aufrufe.jsonl` (218/223/224);
  Kennzahlen und Bauanleitung in `tests/fixtures/stand_b224/README.md`.
  Umgestellt: `test_r13ay` (`TestEchteWerte` → `TestMedianDerZuwaechseGefroren`, Median 5 aus
  +3/+5/+7), `test_r13ba` (`TestEchteDateienB222`+`TestEchteWerte` → `TestFesterStandB224` +
  `TestFesterStandRate`: 20/1657, Vorher-Paar B222 22/1849, Median 4, Mittel 2,375),
  `test_r13bb` (`TestRueckblickEchteBatches`/`TestEchterPlanMischregel`/`TestEchtePaketEDateiB224`
  → `TestRueckblickFesterStand`/`TestPlanMischregelFesterStand`/`TestPaketEDateiFesterStand`).
  Muster: `StandFixtureMixin.stand_laden()` kopiert die Fixture in ein Temp-Repo und setzt
  `cfg`/`wurzel`/`dec` hart; Klasse `Basis` bleibt fuer den Aufbau.
  WICHTIG: `.gitattributes` hat `harness/tests/fixtures/**  -text`; ohne die Regel schneidet
  `core.autocrlf=true` beim `git add` das UTF-8-BOM ab (Messdatei) — Fixture NACH der Regel
  stagen (`git rm -r --cached harness/tests/fixtures` dann `git add`), Blob pruefen
  (`\xef\xbb\xbf# Mes`). Kodierungen: `_preflight_216.txt` ist UTF-16 LE, 215/223/224 UTF-8-BOM,
  `_m224/_c_paket_e_nachher.txt` UTF-8-BOM; Beleg `docs/_r13bc_kodierung.txt`.
  NICHT umgestellt (muessen den lebenden Stand lesen): Zitatpruefungen `test_r13az::TestAnlassImRepo`,
  `test_r13x::TestEchteBelege`, `test_r13ah` `_preflight_212..214`, `test_r13ac`/`test_r13ae`
  Kopie-gegen-Original, `test_r13aa` `runs/b207..209`.
  Fallstrick Git-Werkzeuge in PowerShell: `git cat-file blob :pfad *> datei` schreibt UTF-16
  (Blob-Bytes per Python-`subprocess` pruefen, nicht ueber die Konsole) - eine Uebereinstimmung
  dagegen prueft man mit `Compare-Object (git ls-files ...) (Get-ChildItem -Recurse Name)`.
  `git commit` mit `-F <datei>` nehmen, wenn die Nachricht `->` oder Anfuehrungszeichen enthaelt.
- R13bc-Nachtraege (`7ca1c40`, `b02b308`): Byte-Treue der Fixture nach frischem Checkout
  belegt (`git checkout-index -f --prefix=<tmp>`, 6 von 6 identisch, `docs/_r13bc_checkout.txt`);
  volle Reihe am Gate gefahren (`docs/_r13bc_volle_reihe.txt`, 1268 Tests / 0 Fehler /
  1 skip / OK / 635 s, Zustand GATE_APPROVAL batch=226).
  LEHRE: zwischen "geschlossener Nummernkreis" und "ROLLENDES FENSTER" unterscheiden!
  `test_r13ah::test_alle_drei_felder_der_echten_dateien` las `hybrid_verlauf(cfg, 8)` - die
  letzten 8 Preflight-Dateien. Bei B219 lagen B212-214 noch im Fenster, ab B226 nicht mehr,
  und der Test schaltete sich still ab (`skipTest("echte Preflight-Dateien fehlen")`), obwohl
  die Dateien existieren. Jetzt Fixture + Fenster 14 (`B212..B225`) und eine eigene Zusicherung,
  dass die drei im Fenster liegen.
  WERKZEUG: `docs/_r13bc_skipfind.py` benennt einen Skip, statt ihn zu raten - faehrt nur die
  Testdateien mit `skip`-Stelle einzeln mit `python -m unittest discover -s tests -p <datei> -v`
  und sammelt Zeilen `... skipped 'Grund'`.
  Bei `verbosity=1` nennt unittest den Namen NICHT ("OK (skipped=1)") - fuer die volle Reihe
  also immer die skipfind-Nebenpruefung fahren, sonst bleibt der Skip unbekannt.
- R13bd (2026-09-30, Commit `01fc77c` + Beleg `604e310`): LEERLAUF-PRUEFUNG DER TESTREIHE.
  Werkzeuge: `docs/_r13bd_audit.py` (Laufzeit-Instrumentierung + AST-Bauformen),
  `_r13bd_verdacht.py` (Liste), `_r13bd_leerlauf.py` (fuenf Modi: normal, A-fenster-leer,
  B-datei-leer, C-datei-weg, E-format-geaendert), `_r13bd_einzelfall.py` (ein Fall laut).
  Gemessen: 1268 Tests, 153 mit lebendem Zugriff, 24 mit Leerlauf-Bauform; KEIN Test liest das
  lebende `state/`. Rollende Fenster auf lebenden Daten nur an 3 Stellen (test_r13ah
  hybrid_stillstand, sowie die Kopie-Klassen in test_r13ac/test_r13ae).
  Umgestellt: test_r13ah Hybrid-Test auf Fixture + "Baetche liegen im Fenster"; die zwei
  Kopie-Vergleiche mit `assertTrue(moeglich)` bzw. `assertTrue(self.kopiert)`; `_r13av_lauf.py`
  nennt jetzt JEDEN Skip mit Name und Grund (vorher nur "skipped=1").
  VORHER/NACHHER mit demselben Werkzeug: 9 Treffer auf 3 Tests -> 5 auf 2 Tests, beide
  verbliebenen widerlegt (`_r13bd_leerlauf_vorher.txt` / `_r13bd_leerlauf.txt`).
  INSTRUMENT-FALLSTRICKE (teuer gelernt, gelten fuer jede kuenftige Simulation):
  (1) `hx.util.open_shared_read` liest auf Windows ueber einen DATEIDESKRIPTOR
      (`_winapi.CreateFile` + `open(fd)`) - Patches auf `Path.read_text`/`builtins.open`
      greifen dort NICHT, die Datei kam mit vollem Inhalt an. Leser zusaetzlich auf der
      hx-Ebene einhaengen, und zwar in JEDEM hx-Modul (die Module importieren sie direkt).
  (2) `shutil.copy2` kopiert auf Windows ueber `_winapi.CopyFile2` - ebenfalls am Patch vorbei.
      Tests, die ihre Vorlage kopieren, sind in den Modi "leer"/"Format geaendert" nicht
      pruefbar (gemessen: Kopien behielten 1909/2345 Byte).
  (3) `harness.toml` nie mit-leeren: dann scheitert `load_config()` im `setUpClass` und der
      Modus meldet faelschlich "greift hart zu".
  (4) "gruen in einem Modus" ist nur dann ein Fund, wenn der Test lebende Pfade WIRKLICH
      angefasst hat (Kennzahl "kein lebender Zugriff im Test") UND die Zusicherung am lebenden
      Inhalt haengt. Die zweite Haelfte bleibt Handarbeit.
  Volle Reihe am Gate danach: 1268 Tests, 0 Fehler, 0 Fehlschlaege, 0 uebersprungen, OK.
  FALLSTRICKE: (a) Tests gegen LEBENDE Repo-Dateien werden mit dem naechsten Batch falsch -
  B224 landete waehrend dieses Batches (Median der Kopf-Batches 6 -> 5, neueste Messung
  222 -> 224, `test_r13ay`/`test_r13ba` rot) -> Regel pruefen + bei Identitaet der echten
  Datei skippen. (b) PowerShell: `git commit -m` mit `->` oder `\"` bricht ab ("unknown switch
  `>`") - im Betreff/Text keine Pfeile und keine escapten Quotes. (c) Testartefakte in das
  Wegwerf-Verzeichnis schreiben (sonst liegt `tests/_tmp_*` als untracked im Repo, weil
  `harness/.gitignore` `!tests/**` hat).

- R13be (2026-10-01, drei Commits `e179f5a`/`0dfcb14`/`276b23a`): Preflight-Zaehler aus dem
  Mitschnitt, PreToolUse-Hinweis, laengere Batches. Belege `docs/_r13be_belege.md` (3 Teile).
  (1) ZAEHLER: `preflight_laeufe` kam aus `runs/b<N>/preflight-aufrufe.jsonl`, das der
  PostToolUse-Hook schreibt - der laeuft NUR nach ERFOLGREICHEN Aufrufen. Ein Preflight mit
  Befunden endet Exit 2 = `is_error=true`, der Hook schreibt nichts. Ueber B220-B228 gilt exakt
  Zaehldatei-Zeilen = Starts - `is_error`-Aufrufe (17-6=11); B228 hatte 2 Starts und
  `preflight_laeufe=0`. Jetzt `stand.mitschnitt_preflight_aufrufe(cfg, batch, …)` aus
  `stream.jsonl` + `stream-forts*.jsonl` (Regel `streamjson.ist_preflight_aufruf`), der
  Hook-Zaehler bleibt KONTROLLE: Faktenzeile `PREFLIGHT-AUFRUFE: n (Quelle Stream),
  Hook-Zaehler: m` + HINWEIS bei Abweichung (`stand.preflight_zaehler_zeile`).
  FALLSTRICK (zweimal getroffen): NICHT auf den Text `"preflight"` filtern - die
  `tool_result`-Zeile nennt ihn nicht (nur `exit=0`/`Exit code 2`), die Treffer verschwinden
  still. Auf `'"tool_use"'`/`'"tool_result"'` filtern und die Bloecke auswerten.
  (2) PreToolUse: Die Worker-CLI kennt `PreToolUse` („Run before tool, can block"),
  `PostToolUse`, `PostToolUseFailure`; Ausgabe `hookSpecificOutput.permissionDecision`
  allow/deny/ask + `permissionDecisionReason` (Exit 2 = blockierender Fehler). `tools/batch_uhr.py
  --pre` blockt einen Preflight-Start EINMAL je Batch (Marke: `preflight-blockiert.jsonl`,
  deren Existenz laesst alles Weitere durch); `write_worker_hooks` haengt beide Ereignisse mit
  gleichen Argumenten. Nebenwirkung: ein geblockter Aufruf zaehlt im Mitschnitt als Start.
  (3) `harness.toml alarm_wall_s` 5400 -> 9000 (150 min), Umschaltschwelle 135 min,
  `hard_wall_s` bleibt 10800; Rueckfallwerte in `worker.py` (3) und `watch.py` (1) mitgezogen;
  `reviewer.md`: ~2 Stunden Arbeit + NACHRUECKLISTE 4-6 Posten. Neue Kennzahl
  `stand.aufwand_anteile`: Startroutine = Start bis erster SCHREIBENDER Werkzeugaufruf,
  Preflight/Schluss = letzter Preflight-Start bis Laufende, Arbeit = Rest (Minuten + Prozent),
  in `result.json["aufwand"]` + Faktenzeile `AUFWAND: …` (Rueckblick rechnet aeltere Batches
  nach). Gemessen B220-B229: fest 9-11 min je Batch = 26 % (33 min) bis 13 % (87 min); kein
  Lauf kam an die alte Schwelle (laengster 87 min).
  FALLSTRICKE: (a) `uhr.start_zeit(state)` braucht das DICT - `state.data` uebergeben, sonst
  AttributeError erst am Batch-Ende. (b) Ein Block-Kommentar in `harness.toml` verschluckte die
  Folgezeile (`umschalt_vor_alarm_s` fiel still auf den Code-Rueckfall) - TOML kennt nur `#`
  bis Zeilenende, beim Einfuegen IMMER die Nachbarzeilen nachlesen. (c) Nach einer Aenderung an
  `_finish_run` ALLE Testdateien fahren, die es aufrufen (`test_r13ad` fehlte -> Fehler aus
  Teil 1 blieb einen Commit lang unbemerkt). (d) Schwellen-Tests ziehen die Zahl aus der Config
  (`umschalt_minuten(cfg)`), nicht aus einer zweiten festen Zahl - beim Suchen nach den Stellen
  aber auch die ABGELEITETEN Zahlen mustern (`75.0`, `65.0`, `135`), nicht nur `5400`: eine
  Suche nach `alarm_wall_s|5400|9000|90 min|75 min` uebersah `test_r13aj_fixes.py:229`
  (feste `75.0`) - der erste Lauf der vollen Reihe am Gate war deshalb rot (1 Fehlschlag,
  Commit `4e88950`), der zweite gruen: 1302 Tests, 0 Fehler, 0 uebersprungen,
  `docs/_r13be_volle_reihe.txt`.
- R13bf (2026-10-01, vier Auftraege des Nutzers, je ein Commit `f5a113c`/`71fa095`/
  `f022446`+`714e45b`/`9182952`): Belege `docs/_r13bf_belege.md` (Teile A-D).
  **(A) Prozess-Detektor** (`streamjson.abbau_gefahr`): eine WOERTLICHE PID-Liste in einer
  Schleife (`foreach ($id in @(704,13960,18296)) { Stop-Process -Id $id }`) ist GEZIELT und
  wird nicht mehr gemeldet - dieser Fehlalarm brach B234 nach 66,5 min ab (Befehl im
  Mitschnitt des abgebrochenen Laufs: `runs/b234/stream-v1.jsonl:40020`; der vom Nutzer
  genannte `stream.jsonl:39715` ist die tool_result-Zeile mit den drei PIDs). Neu ist auch
  die Gegenprobe: eine Schleife ueber eine Variable/`Get-Process`-Auswahl OHNE woertliche
  Zahlen bleibt verdaechtig. Sonde `docs/_r13bf_abbau.py` ueber ALLE Mitschnitte:
  vorher 26 Abbau-Aufrufe/1 gemeldet (= der Fehlalarm), nachher 26/0. `tools/check_abbau.py`
  jetzt mit 15 Faellen, ueber alle Batches und ZIP-fest; ACHTUNG: der b178-CPU-Befehl steht
  NICHT als Shell-Aufruf im Mitschnitt (nur als Text in Write-Inhalten) - die Gegenprobe
  erwartet deshalb 0 gemeldete Befehle.
  **(B) Bilanz ohne Preflight** (M234-1): `stand.ist_wert` liest NIE eine Zelle aus einer
  Spalte, die `Soll` heisst (Kopfzeile ueber `stand.tabellen_kopf`); `stand.kernzahlen`
  faellt in der Preflight-Aera nicht mehr aufs Dokument zurueck, sondern setzt
  `c_nicht_gemessen` + `c_erwartet`, und `bilanz.gesamt_block` schreibt
  `B<N> nicht gemessen (keine analysis/_preflight_<N>.txt) - die Zahl bleibt auf dem Stand
  von B<k>`. Fixture `tests/fixtures/stand_b234_luecke` (echter Dokumentstand 10:51, OHNE
  `_preflight_234.txt` - im lebenden Repo gibt es sie seit 12:53 wieder, der Fall ist dort
  ueberholt).
  **(C) Aufwandskennzahl**: `preflight_min` ist jetzt die SUMME der Dauer ALLER
  Preflight-Laeufe (`stand.mitschnitt_preflight_aufrufe` liefert je Aufruf `dauer_s`/`ende`),
  dazu `schluss_min` (Ende des letzten Laufs bis Laufende) und `fester_min`; B233 alt
  10,2 min/9,3 % -> neu 27,7 min/25,3 %. Feld aus der ALTEN Form (ohne `fester_min`) wird
  nachgerechnet. Rueckblick B220-B234: `docs/_r13bf_aufwand.txt` (fester Aufwand 31 %).
  **(D) Zweiter Preflight** nur, wenn seit dem letzten Preflight unter `port/`/`scripts/`
  etwas geaendert wurde (`worker.aenderung_seit_preflight`: Commits nach dem Start +
  nicht committete Dateien mit juengerer Dateizeit; `worker.letzter_preflight_start` aus dem
  Mitschnitt). Sonst steht im Anstoss "Kein neuer Preflight noetig, der vorhandene gilt";
  der Erledigt-Satz steht jetzt IMMER ZULETZT. Messdaten `fortsetzungen[k].preflight_neu`/
  `preflight_aenderung(_unbekannt)`. Wirkung im Betrieb noch nicht gemessen (Harness pausiert).
  FALLSTRICK (meine eigene Werkzeugnutzung, dreimal): `python -c "…[print(…) for …]"` in
  PowerShell bleibt in der Fortsetzungszeile (`>>`) haengen und frisst die naechsten Befehle -
  mehrzeilige/k bracket-lastige Python-Aufrufe IMMER als Skriptdatei unter `docs/` fahren.
- R13bj (2026-10-01, Nutzerauftrag nach B235): NUMMER, LAUF-ORDNER, ZEITGRENZEN.
  (1) Die Batchnummer zaehlt jetzt der HARNESS: `orchestrator.own_batch()` = letzter Start
  (`state.last_batch_number`) + 1; `expected_batch()` nimmt ihn und faellt nur ohne Zaehler
  auf Anker+1 zurueck. Der Anker ist Gegenprobe: `batch_number_line()` und die eigene
  Faktenzeile `batch_nummer_fakten_zeile()` nennen eine ABWEICHUNG (Anlass: B234 wurde nicht
  in den Ankerkopf fortgeschrieben -> der naechste Lauf bekam wieder 235, und das Review zu
  B235 ueberschrieb in `runs/b235/review.md` das Review zu B234).
  (2) `gate_from_review` erkennt die FORTSETZUNG: Instruktion nennt die Nummer des bewerteten
  Laufs -> `tools["fortsetzung"]=true`, kein `number_mismatch`. Nummernregel fuer den
  Reviewer kommt aus `batch_nummer_regel()` ueber `review_context` (EINE Quelle, nicht mehr
  in `reviewer.py` nachgebaut).
  (3) `orchestrator.lauf_ordner_blockiert(batch, fortsetzung)`: enthaelt `runs/b<N>/` schon
  ein `result.json`, pausiert der Harness VOR `clear_gate()` (Auftrag bleibt stehen, Muster
  R13m). Fortsetzung ist es auch, wenn die Nummer == `state.batch` (Altbestand-Gates ohne das
  Feld).
  (4) `worker.sichere_vorgaenger` VERSCHIEBT die Belege des Vorlaufs nach `runs/b<N>/lauf<k>/`
  (`LAUF_BELEGE`/`LAUF_MUSTER`; Review-Belege `review.md`/`harness-facts.md`/`reviewer.jsonl`
  bleiben oben). `retention.kandidaten` packt `lauf*/` mit. Die alten `*-v1.*`-Namen liest
  `MIT_ZIP` weiter.
  (5) Zeitgrenzen VORLAEUFIG: `bash_max_timeout_s` 1800 -> 3600 (B235-Preflight war
  **1799,187 s** bei 1800 s Grenze, `analysis/_m235/_preflight_zeiten.txt`), `hard_wall_s`
  10800 -> 14400 (B235 lief 2h53m), `timeout=3600000` in Worker-Vorspann + `prompts/reviewer.md`,
  Fallbacks in `worker.py`/`watch.py` und `uhr.MAX_START_ALTER_S` 4h -> 5h.
  RUECKBAU-VERMERK: `docs/bedienung.md` §13 (zurueck auf 1800/10800/1800000, sobald der
  Preflight wieder unter 900 s liegt).
  BELEG-RETTUNG (Lehre): der Harness legt von JEDEM Review eine Volltextkopie unter
  `logs/review-<ts>.md` ab - damit ist ein ueberschriebenes `runs/b<N>/review.md`
  wiederherstellbar. Das Review zu B234 lag als `logs/review-2026-10-01T112543+0000.md`
  (10 673 B) und ist als `runs/b235_lauf1_sicherung/review_zu_b234.md` zurueckgeholt
  (SHA-256 gleich); `runs/b235_lauf1_sicherung/` ist die Vollsicherung des ersten B235-Laufs.
  FALLSTRICK (vom vollen Testlauf gefunden): ein Ordner unter `runs/`, der mit `b` beginnt und
  nicht `b<Zahl>` heisst (Sicherung `b235_lauf1_sicherung`), bricht jeden Leser, der
  `glob("b*")` ohne Ziffernpruefung verwendet - `int(name[1:])` wirft ValueError, `dirs[-1]`
  haelt die Sicherung fuer den neuesten Lauf, und eine Kopie des `result.json` zaehlt Kosten
  DOPPELT. Dafuer gibt es jetzt EINE Stelle: `hx/util.py::batch_ordner(runs)` (nur `b<Zahl>`,
  aufsteigend); benutzt in `orchestrator._do_send`, `orchestrator.letzte_review_datei` und
  `bilanz.kosten_block` (zweimal). `aussensicht`/`denken`/`stand`/`fragen` hatten es schon.
- R13bk (2026-10-01, Nutzerauftrag vor dem Hochladen): HARNESS-REPO AUF GITHUB.
  `g:\Harness` liegt jetzt als **privates** Repo `Specker101/Harness`, Branch `main`,
  Commit `c77348a`, 491 Dateien. `gh` ist NICHT installiert - angelegt wurde es ueber die
  GitHub-API mit der in Windows gespeicherten Anmeldung (Credential-Helper `manager`);
  der Zugangswert lief nur durch `git credential fill` in der Shell und wurde nie ausgegeben.
  PRUEFUNG VOR DEM PUSH (Belege bleiben UNGETRACKT - Nutzerentscheid): Werkzeuge
  `docs/_r13bk_upload_pruefung.py` (+ `.txt`), `_r13bk_hinweise_art.py`, `_r13bk_namensrest.py`.
  Ergebnis 0 harte Funde: Historie 111 Commits x 4 Muster = 0; die 3 Werte aus `.hx-secrets`
  wortwoertlich gegen 1029 Blobs = 0; `secrets/`, `harness/secrets/`, `backups/` nie getrackt;
  kein Blob > 50 MB; keine Gitlinks. Die 496 Arbeitsbaum-Treffer sind `password` in
  Fremd-Bibliotheksquellcode (pip/httpx/pydantic/urllib3) und das SPIEL-PASSWORT des Ports
  (`PASSWORD=<8 Zeichen>` als Testeingabe in Laufprotokollen) - kein Zugangsdatum.
  FALLSTRICKE (eigene Werkzeuge, teuer): (a) `git cat-file --batch-check` OHNE Eingabe wartet
  ewig auf stdin - `stdin=DEVNULL` setzen; der erste Lauf stand 27 min bei 0,15 s Kernelzeit.
  (b) `check-ignore` auf einen NICHT vorhandenen Pfad meldet "NICHT IGNORIERT" (Fehlalarm).
  (c) "nicht ignoriert" ist fuer eine GETRACKTE Datei normal - nur "nicht ignoriert UND nicht
  getrackt" ist ein Fund. (d) `sandbox/` ist eine Junction ins Decomp-Repo: `os.walk` steigt
  trotz `followlinks=False` hinein (Python 3.12 zaehlt Junctions nicht als Symlink), 5a listet
  dann 4-GB-Dateien als "Dateien des Harness". (e) Pfadmuster in `git ls-files -- <muster>`
  greifen NICHT in die Tiefe - `runs/` fand die getrackten Fixtures
  `harness/tests/fixtures/stand_b224/root/runs/` nicht; Namenslisten sind kein Ersatz fuer die
  Inhaltspruefung.
  OFFEN (empfohlen, NICHT umgesetzt): `.env` und `*.key` sind von KEINER Ignorier-Regel erfasst
  (nur `secrets/` ist es) - ein `git add -A` wuerde z. B. `harness/foo.key` mitnehmen.
- R13bl (2026-10-02): Zeitgrenzen ZURUECKGEBAUT (`hard_wall_s` 14400 -> 10800,
  `bash_max_timeout_s` 3600 -> 1800 / `timeout=1800000` im Vorspann + `prompts/reviewer.md`,
  Preflight von B236 = 456 s), R391-Sperre im PreToolUse-Hook (erst Vorhersage-Commit),
  Pflichtzeile B-SCHRITT fuehrt die B-Nummer als Zaehlung. Volle Reihe 1369 OK.
- R13bm (2026-10-02, fuenf Punkte, Commit `07f5cda`..`c443cdd` + Belege): (1) `api_errors`
  gefuellt (Text "API Error"/Modellfeld `<synthetic>`, mit Mitschnittzeile);
  (2) Infrastrukturabbruch als eigene Klasse (`worker.infra_abbruch_regel`: rc!=0 UND kein
  anderer Abbruchgrund UND letzte Antwort ein API-Fehler) -> KEIN Review, derselbe Batch
  startet nach 15 min als Fortsetzung (Gate-Quelle `infra`, ohne `/approve`), nach 2
  Neustarts Pause + Telegram; (3) Session-Limit ist ein WARTEZUSTAND: Rohtext als
  `review-limit-<stempel>-v<versuch>.md` (nicht `review-verworfen`), Wiedereinstieg =
  gelesene Reset-Zeit + 5 min, auch der 2. Versuch laeuft nicht in `review_failed`;
  (4) Aussensicht an derselben Limit-Uhr (`Ergebnis.limit_reached`, `_aussensicht_limit`,
  `meta["nach_limit_grund"]` wiederholt sie nach der Wartezeit); (5) `uhr.MAX_START_ALTER_S`
  geprueft und auf 4 h zurueck (harte Grenze + 1 h; die Zahl steuert NUR, ob ein
  Startzeitstempel geglaubt wird). Volle Reihe 1406 OK (`docs/_r13bm_volle_reihe.txt`).
- R13bn (2026-10-02, drei Punkte): (1) `aussensicht` Marker-Ausloeser
  (`MEILENSTEIN`/`ABBRUCHKRITERIUM ERREICHT:`) haben jetzt eine `gemeldet_bis`-Sperre je
  Review-Datei (`MARKE_MARKER_SCHLUESSEL`, `marker_marke_setzen` im Orchestrator) - EINE
  Marke hatte vier Laeufe ausgeloest (meta-240..243). KEINE Migration: gemessen liegt die
  Marke aus `runs/b241/review.md` nicht mehr im Fenster der letzten 3 Zusammenfassungen.
  (2) Verbrauch je Aufruftyp gemessen (nur lesend): Review 87 / Aussensicht 22 / /ask 66 /
  Worker 107 Laeufe in 7 Tagen; HYPOTHESIS 57 Reviews je Woche (konservativ).
  (3) Prognose: Median der Koepfe je C-Batch aus der LUECKENLOSEN PREFLIGHT-Reihe (die
  Bilanzdateien fehlen fuer einzelne Batches - B241), Kalender-Hochrechnung mit dem
  GEMESSENEN C-Anteil (>=2 C-Batches am Ende -> 100 %, Strang B ruht), Trend zusaetzlich
  auf `C verifiziert` (`stand.verifiziert_trend`). Fixture `tests/fixtures/stand_b243`.
  FALLSTRICKE: (a) `assistant`-Ereignisse wiederholen die `usage` ihrer Nachricht mehrfach -
  Tokens NUR aus dem `result`-Ereignis (sonst Vielfaches). (b) `stand.durchsatz` gibt
  `rate_c_koepfe` NICHT heraus (das setzt `durchsatz_zeilen`) - wer die Rate braucht, ruft
  `c_rate` selbst (Kreis-Gefahr). (c) `durchsatz_zeilen` bricht bei leerem Bilanz-Fenster
  ab - eine Fixture ohne `_m<N>/_bilanz*.txt` druckt gar keinen Durchsatz-Block.
  (d) Aendert sich die BASIS einer Kennzahl, werden auch die ERWARTUNGEN der eingefrorenen
  Fixture-Tests rot (`test_r13ba`, `test_r13ay`): Fixture-DATEIEN nicht anfassen, die neuen
  Zahlen am Ort begruenden.
- R13bo (2026-10-02, Nutzerauftrag Harness-Wartung): MODELLWAHL JE REVIEW-ANLASS + TAKT 4.
  (1) `[claude] reviewer_modell` = Sonnet 5.5 (C-Batches), `reviewer_modell_b` = Opus 5.5
  (B-Strang/Erkundung); UNKLARE Art ("" aus `stand.strang_von_batch`) = Opus (vorsichtige
  Seite). `reviewer.review_modell(cfg,batch) -> (modell, art)`; `build_command(..., modell=)`;
  `run_review(..., batch=, modell=)`. Reasoning bleibt `reviewer_effort=high` fuer alle
  Abo-Laeufe. (2) `aussensicht_modell` (Opus) statt geteiltem `model_reviewer`; `/ask` bekam
  `ask_modell` (Opus), damit es nicht still auf Sonnet mitzieht. (3) `[meta]
  aussensicht_takt = 4` (vorher `every_batches = 3`); `aussensicht.takt` liest
  `aussensicht_takt`, sonst `every_batches`, sonst STANDARD (4); Ereignis-Ausloeser
  unveraendert. (4) GEWAEHLTES Modell in `runs/b<N>/result.json` (Feld `review`, via
  `Orchestrator.review_in_result`, VOR den Gueltigkeits-/Limit-Zweigen) UND in der
  Telegram-Zusammenfassung (`review_modell_zeile` + Summary in EINER Nachricht).
  Tests `tests/test_r13bo_fixes.py` (20); angepasst: test_r11 (ohne Batch = Opus),
  test_r13z (Takt 4), test_r13w (aussensicht_modell). MERKE: `run_review` OHNE `batch`
  = Art "unklar" = Opus; `build_command` OHNE `modell` = Sonnet (nur fuer run_handover).
  Neuer Paragraph 19 in docs/bedienung.md = Testfenster "Reviewer Sonnet" (Auswertung nach
  6 Batches, Rueckfallregel 2+ hochgewichtige Reviewer-Befunde je 3 Batches = zurueck auf
  Opus, Ergebnis als Telegram-Meldung); `docs/_r13bn_verbrauch.py --modell` = Tabelle je
  Aufruftyp UND Modell. Commits 3343672 (Code) + 4c770d3 (Doku).
- R13bo-4 (2026-10-02, Commit 59a427e): `/ask` auf `claude-sonnet-5-5` (`[claude]
  ask_modell`) - im Testfenster laeuft nur noch die AUSSENSICHT auf Opus. Reasoning:
  `/ask` baut die Umgebung ueber `envs.reviewer_env` (`hx/ask.py:315`), dort setzt
  `hx/envs.py:156` `CLAUDE_CODE_EFFORT_LEVEL` aus `[claude] reviewer_effort` = "high" -
  EINE Effort-Quelle fuer Reviewer, Aussensicht und /ask. Test in test_r13bo_fixes
  (`test_ask_nutzt_das_konfigurierte_modell`, `test_ask_und_reviewer_teilen_die_effort_quelle`).
- R13bo-5 (2026-10-03, Nutzerauftrag Harness-Wartung, 4 Commits 0abecab/45279fa/269632a/2cef348):
  (1) STILLSTANDSMELDER: `stand.hybrid_a4_verlauf` liest die Zeile **`Hybrid-A4`** (echter
  Halt-PC + "Schritte bis erster Eintritt echter Halt"), nicht `Hybrid-Lauf` (dort steht die
  200M-Schranke 8000EC3C, die seit B238 steht - B250 schlug damit falsch an, obwohl B248 den
  Halt 8000A164 erreichte). `stand.preflight_hybrid_fehler` schliesst Preflights aus, deren
  **Hybrid**-Zeile den STATUS `FEHLER` traegt - `"FEHLER" in zeile` ist FALSCH (die GL-Zeile
  heisst in jeder Datei "0 sonst. FEHLER" -> leere Reihe). `aussensicht.hybrid_stillstand`
  schweigt, wenn die letzten 3 Batches alle C waren (`HYBRID_RUHE_C_BATCHES`); `hybrid_neuester_b`
  (Marke) nutzt dieselbe Quelle. Grund heisst weiter "Hybrid-Lauf haengt".
  (2) C-ZIELGROESSE AUF INSN: `stand.ausgefuehrte_menge` liest die Preflight-Zeile
  `Ausgefuehrte Menge` (ref_insn explizit oder abgeleitet `Spannen-Insn - davon nicht
  referenzgleich`; `offen_insn` = "davon nicht referenzgleich"; `teilgeprueft`; optionales
  `Zweitkopien`). `stand.c_insn_rate` = Median der EIGENEN Insn der letzten 4 C-Batches;
  Prognose = offene Rumpf-Insn / Median mit min/max-Spanne als HYPOTHESIS. `plan_ist_text`
  zeigt C-INSN + ZIEL + HYPOTHESIS; die Kopf-Medianzeile hat KEIN "hoechstens ca. N" mehr
  (Tests test_r13ay/test_r13s entsprechend angepasst). Messreihe B251-B254 = 510/191/461/176,
  Median 326, offen 63714 -> ca. 195 C-Batches.
  (3) WORKER-VORLAGE (`hx/worker.py::WORKER_PREAMBLE`): "Unabhaengige Rechenlaeufe parallel
  starten" und der Hintergrund-"Weg 2" (Start-Process/Wait-Process) sind GESTRICHEN; neu:
  EIN blockierender Aufruf (timeout bis 1800000 = 30 min), "Hybrid-Laeufe NIE parallel",
  Stopp-Schalter/Vorwaermskript des Auftrags. Wortlaut "bis 1800000 = 30 min" NICHT aendern
  (test_r13ah/test_r13bl/test_r13bj pruefen ihn). Tests test_r13h/test_r13v pruefen den
  neuen Stand. Der gezielte Prozessabbau (`Start-Process … -PassThru` fuer die PID) bleibt.
  (4) Der Aussensicht-Lesebaum ist NUR `cfg.root` (harness/)+`cfg.decomp` - `g:\Harness\tools`
  und `docs` sind fuer das MODELL unlesbar (der Harness-Code liest sie ueber `cfg.harness_home`).
  (5) In `runs/b<N>/result.json` steht das Review-Modell IM Block `review`
  (`review.modell` = GESEHENE Liste aus `result.modelUsage`, `review.modell_soll` = gewaehlt,
  `review.art` = B/C/unklar) - geschrieben von `Orchestrator.review_in_result`;
  Aussensicht-Modell: `runs/meta-<N>.json`; /ask: kein result.json.
  Belege `docs/_r13bo5_belege.md`, Messung `docs/_r13bo5_verbrauch.txt`.
- R13bp (2026-10-03, Nutzerauftrag Harness-Wartung, 6 Commits `f593940`/`5d38d7e`/
  `8ae8a15`/`66e7e94`/`976ee00`/`8467507`, gepusht): vier Punkte + Belege.
  (1) STRANGERKENNUNG (`stand.strang_von_batch`): Primaerquelle ist die Pflichtzeile
  `STRANG: B|C` im Auftrag des Batches selbst, danach der uebrige Auftragstext, ERST DANN
  die `B-SCHRITT`-Zeile des Reviews (Rueckfall). Anlass (gemessen): `runs/b255/review.md`
  bewertet B254 und traegt dort die B-SCHRITT-Zeile des NAECHSTEN B-Batches ("4/5 …
  B-Batch 26") -> B254 galt als B-Batch. `prompts/reviewer.md` verlangt die Zeile jetzt.
  Neue Fixture `tests/fixtures/stand_b255` (16 Dateien, byte-true; MD5-Vergleich mit
  `git hash-object` taeuscht wegen `text=auto` - Blob-Laenge vergleichen).
  (2) `worker.PREFLIGHT_GILT_TEXT` sagt jetzt, dass weitere Arbeit unter port/ und scripts/
  erlaubt ist (danach neuer Preflight, der letzte gilt).
  (3) `streamjson.warte_muster` zaehlt `Wait-Process` (`WARTE_WAITPROC_GRUND`),
  `warte_sekunden` schaetzt `-Timeout N`; `warte_erlaubt`/`warte_verstoesse` trennen
  Zaehlung von Verstoss, die Notbremse (`worker.on_event`) sieht nur Verstoesse. Gemessen
  B255: 2x600 s statt gemeldeter 0,5 s, 0 Verstoesse. Verbotene Muster werden jetzt ZUERST
  geprueft (vorher machte Wait-Process auch eine Abfrageschleife still erlaubt).
  (4) A4-Stillstand: die Preflight-Zeile `Zwischenspeicher Treffer|neu` (seit B250) wird
  gelesen (`stand.cache_herkunft`, Feld `cache`); Treffer fallen aus der Vergleichsreihe
  (`aussensicht.hybrid_stillstand`), sonst meldet der Waechter Wiederholungen als
  Stillstand. `hybrid_neuester_b` bleibt auf ALLEN Eintraegen (sonst Dauerfeuer). Die
  Cachedatei `port/build/hybrid_cache/<key>.txt` traegt KEINEN Herkunftsvermerk.
  Volle Reihe am Gate: 1479 Tests, 0 Fehler, 0 uebersprungen, OK (492,1 s),
  `docs/_r13av_volle_reihe.txt`; Belege `docs/_r13bp_belege.md`.
- R13bq (2026-10-03, Nutzerauftrag "Konsolenfenster zeigt nichts", 5 Commits
  `82e2a1e`/`af4a530`/`0be8ecf`/`9b5066b`, gepusht; Punkt 3 des Auftrags war NUR PRUEFEN):
  (1) QUICKEDIT: der Harness druckt jede Log-Zeile mit `print(..., flush=True)`
  (`hx/util.py` `Log._emit`); ein markierter Text im Fenster blockiert den druckenden
  Thread (Takt-Thread = Telegram-Warnungen + STOP-Marker, oder Haupt-Thread). Der Worker
  ist nicht betroffen (Ausgabe in `runs/b<N>/stream*.jsonl`). Neu: `util.ohne_quickedit_
  modus` + `util.konsole_quickedit_aus` (ctypes, STD_INPUT_HANDLE), Aufruf in `cli.cmd_run`.
  (2) STILLE-WARNUNG: `util.stille_warnung` (reine Rechnung, je volle Schwelle) +
  `proc.run_stream(stille_warn_s=, stille_info=)` -> WARN-Zeile "Mitschnitt still ..." mit
  dem letzten Werkzeugaufruf (`streamjson.StreamStats.letzter_aufruf`), Schwelle
  `[limits] stille_warn_min = 20` (B257: Einzelaufrufe bis 1323 s = 93,7 % Werkzeugzeit).
  (4) SONDE `docs/_r13bq_sonde.py` (nur Messung): die claude-CLI puffert NICHT allgemein -
  mit `stdout=PIPE` kamen 11-22 Stuecke waehrend des Laufs (erstes Byte bei 1,3 s von 2,8 s),
  mit `stdout=DATEI` wuchs die Datei ebenfalls laufend. Die CLI-Zeitstempel im Inhalt lagen
  nur 0,00-0,07 s vor der Ankunft (eigene Uhr). Die 0-Byte-Phasen in B257/B258 (Datei 0 B
  bei Inhalt aus 11-45 min davor) sind damit NICHT erklaert - naechster Messvorschlag im
  Beleg: dieselbe Sonde mit MCP wie im Worker + einem ~90-s-Werkzeugaufruf.
  Volle Reihe am Gate: 1493 Tests, 0 Fehler, 0 uebersprungen, OK (633,5 s);
  Belege `docs/_r13bq_belege.md`, Sonde `docs/_r13bq_sonde.txt`.


- R13bt (2026-10-04, Nutzerauftrag Harness-Wartung, 4 Commits 0a6c07b/67c7616/2df5767/0940e2d, gepusht):
  (1) MISCHUNGS-ZEILE OHNE GEMISCHTE GROESSEN (Befund M264-5). `_mischung_zeile` druckte
  `{c} C von {n} Batches im Fenster ({anteil_gemessen*100:.0f} %)` - Zaehler/Nenner aus dem
  BILANZ-Fenster (harness/hx/stand.py:2644@0a6c07b^), die Prozentzahl aus der PREFLIGHT-Reihe
  (4/13 = 31 %). Jetzt: Prozent aus den EIGENEN Zahlen (`c/n`), die Reihen-Quote als eigene
  benannte Zeile; laeuft die Reihe reine B-Batches, ruht die C-Hochrechnung (`anteil_c=None`)
  und die Kalender-Prognose verschwindet statt einen Plan-Anteil zu zitieren.
  Beleg docs/_r13bt_sonde.txt (vorher/nachher, echter Stand).
  (2) STILLSTANDZAEHLER DER B-PHASE (Regel analysis/hybrid-plan.md:257-274: Schwelle 4
  B-Batches ohne Station, Zaehler ab jeder Station neu). `stand.station_von_batch`,
  `stillstand_zaehler`, `b_phase_zeile`; C-Batches zaehlen nicht und setzen nicht zurueck, der
  neueste unbewertete Batch sperrt die Zeile nicht. QUELLE ist die neue Pflichtzeile
  `STATION: ja|nein` im Review (`runs/b<N+1>/review.md`) - der Harness raet nicht: fehlt sie,
  heisst der Zaehler UNTERGRENZE. Kein Rueckfuellen alter Reviews.
  (3) FALLSTRICK (GEMESSEN, teuer): `_winapi.CreateFile` scheitert an JEDEM Nicht-ASCII-Zeichen
  im Pfad (WinError 2 bei Umlaut im Dateinamen, 3 im Elternordner), obwohl `Path.is_file()`
  True sagt und `open()` dieselbe Datei liest - `read_text` auf so einem Pfad STUERZT ab.
  `_oeffne_shared` weicht fuer nicht-ASCII auf `open()` aus. Deshalb Testklassen-Namen ASCII
  halten (der Wegwerf-Ordner kommt aus dem Klassennamen). Beleg docs/_r13bt3_pfade.txt.
  Volle Reihe am Gate TROTZ laufendem Worker B265: 1540 Tests, 0 Fehler, 0 uebersprungen,
  OK (568,0 s), docs/_r13bt_volle_reihe_lauf1.txt.
- R13bt-5 (2026-10-04, drei Nutzerentscheide, Commit 14901aa, gepusht): (1) KEINE Nachtragung -
  der Untergrenzen-Wortlaut bleibt bis zum Review nach B265. (2) `SCHWELLE 4 ERREICHT` loest
  ZUSAETZLICH eine Aussensicht aus (wie MEILENSTEIN ERREICHT): `aussensicht.station_stillstand`,
  `station_neuester_b`, `station_gemeldet_bis`, `station_marke_setzen`, `station_beteiligt`;
  die Marke haelt den ERSTEN Batch des gezahlten Laufs (`von`), NICHT den neuesten - der
  Zaehler waechst innerhalb des Laufs weiter (4,5,6...), eine Marke auf dem neuesten Batch
  startete einen bezahlten Lauf JE Batch; nach einer Station springt `von`. (3) C-Batches
  setzen den Zaehler NICHT zurueck (eigener Test).
  FALLSTRICK (vom vollen Lauf selbst gefunden): die B-Phase-Zeile trug BACKTICKS um
  `STATION: ja|nein` und riss damit den Telegram-Codeblock der BILANZ auf -
  `test_r13q_fixes.TestBilanz` wacht darueber (2 Fehlschlaege). BILANZ-Textzeilen NIE mit
  Backticks bauen; `stand.STATION_ZEILE` ist deshalb ohne. Erster Lauf rot (Beleg
  docs/_r13bt5_volle_reihe_fehllauf1.txt), zweiter gruen (docs/_r13bt5_volle_reihe.txt,
  1547 Tests, 0 Fehler, OK 546,2 s, Zustand CLAUDE_REVIEWING).
  ZWEITER FUND: die B-Phase-Zeile hing am Durchsatz-Block und fehlte ganz, wenn keine
  Bilanzdatei da war - sie wird jetzt in BEIDEN Ausgaengen angehaengt (Quelle sind die
  Reviews, nicht die Bilanzdateien).
- R13bu (2026-10-04, Nutzerentscheid "Prompt-Regel ja, Werkzeug ja, Zentraltafel spaeter"):
  ROM-ADRESSEN-SUCHE. Ursache der drei Fehlfunde (B260/B264/0x40000000), GEMESSEN an den
  Mitschnitten: (a) `Grep` OHNE `path` laeuft repo-weit, der analysis/-Vorrat frisst das
  `head_limit` (B264: 19 Altbelege + 1 Port-Treffer bei `head_limit: 20`; B265 mit
  `path: "port\\src"` + `head_limit: 80` fand denselben Dispatcher), (b) ohne `-i` fehlt die
  Haelfte (`FUN_800261C4` opmode.h:61 vs. `FUN_800261c4` game_words.inc:71), (c) die Adresse
  kommt auch NACKT ohne `0x` vor (20 von 24 Treffern bei 8002379C), (d) eine
  Instruktionsadresse (800237B4) ist nicht der Funktionseintrag (8002379C).
  GEBAUT: Decomp `scripts/port_suche.py` (gepusht 7da2a74, Regel in AGENTS.md a5f2f7f) und
  Harness `hx/worker.py::WORKER_PREAMBLE` Block "ROM-ADRESSEN SUCHEN" + Test
  `tests/test_r13bu_fixes.py` (6); Beleg docs/_r13bu_belege.md. Harness-Commit 4b7f889,
  gepusht; volle Reihe am Gate 1553 Tests, 0 Fehler, OK 608,5 s
  (docs/_r13bu_volle_reihe.txt, Zustand GATE_APPROVAL). Aufruf:
  `python scripts/port_suche.py <adresse> [--schreiben] [--voll] [--selftest]`.
- R13bv (2026-10-04, Nutzerauftrag "watch zeigt Fortsetzungs-Streams"): Nach einer Fortsetzung
  im selben Chat schreibt der Worker `runs/b<N>/stream-forts<k>.jsonl` (worker.py:1067);
  `hx/watch.py::_follow_live` las nur `stream.jsonl` und blieb nach dem ersten Teil stumm
  (B266, ~40 min ohne Anzeige). Jetzt EINE Quelle: `_mitschnitt_reihe(rd)` (Teil 0 =
  stream.jsonl, dann forts NUMERISCH sortiert; `.jsonl.zip` mitgenommen, wenn entpackt fehlt)
  + `_tail_reihe(rd, who, zaehler)` (Zeilenstand JE DATEI in `self.seen_forts`, EINE Trennzeile
  `--- Fortsetzung <k> ---`, Rueckgabe "gab es neue Zeilen?"); benutzt in `_follow_live`,
  `_replay` (`--batch N`) und `_snapshot` (`--once`), die letzten beiden nennen die Teile
  ("  Mitschnitte: …"). Herzschlag `_herzschlag(b, rd)`: nach `HERZSCHLAG_S = 60 s` Stille eine
  Zeile "Batch N laufend, letzte Aktivitaet vor X min (Mitschnitt: …)", gedrosselt auf 1/60 s;
  die Zahlenzeile `_print_stats` (R11-4) bleibt unveraendert. Commits R13bv-1 50c63a9 (live)
  und R13bv-2 77076bb (--batch/--once), gepusht; volle Reihe 1564 bzw. 1569 Tests OK.
  Fallstricke beim Testen: `_follow_live` ist eine Endlosschleife - im Test `time.sleep`
  patchen (side_effect) und nach n Runden `KeyboardInterrupt` werfen (die Schleife faengt ihn);
  der Zustand kommt aus `root/state/run.json` (`state`, `batch`, `last_batch_number`).
  WERKZEUG-REGELN (R13az nachgezogen): zuerst `python scripts/port_suche.py <adresse>`,
  Ausgabe ins Batch-Dokument; sonst path immer (port zuerst), `-i`, nackte Adresse,
  head_limit >= 80, bei Instruktionsadressen den Funktionseintrag suchen.
  FALLSTRICK beim Bauen (vom Selbsttest gefunden): `\b` direkt nach der Adresse bricht am
  `u`-Suffix - `0x800237B4u` wurde NICHT gefunden (`input_check.cpp:39`, `cfg.h:87` fielen
  still raus); jetzt `(?!…)`. Und: `kCfg*`/`kRam*` sind WERTE, keine Funktionsadressen -
  nur `kFn*` als Port-Symbol zaehlen, sonst haelt `kMechanism = 0x40000000u` (Bit-30-Maske)
  Einzug als "Funktionsbeleg". `0x40000000` hat im Port 0 Funktionsbelege (SPU-Block,
  Float-Wort 2.0, Maske).


- R13bw-14 (2026-10-07, Commit `5e07d60`, gepusht): SCHATTEN-AUSSENSICHT + SCHATTEN-VERGLEICH
  als Nur-Lese-Werkzeuge (NICHT in `hx/`): `harness/tools/schatten_aussensicht.py` faehrt den
  echten Auftrag mit anderem Modell (`--batch N… --ja`; `--trocken` zeigt nur den Befehl),
  pinnt die Tiefenprobe aus der echten `meta.md`, laesst `ablage_pruefen`/`tiefenprobe_merken`/
  `schreibe_rate_limit`/`verteile` aus und schreibt nur `docs/_sonnet_vergleich_b<N>.md`
  (Mitschnitt in `%TEMP%`); `harness/tools/schatten_vergleich.py` vergleicht gegen
  `runs/b<N>/meta.md` (Befunde gefunden/verpasst/zusaetzlich, Verdikte gleich/anders,
  Werkzeugrunden, Dauer, Nutzerlimit vor/nach) und schreibt nichts.
  MESSUNG B285/B289: Sonnet 191 s/18 Runden/3 Befunde bzw. 411 s/31/7 gegen Opus 379 s/37/6
  bzw. 393 s/51/5; 5h-Limit 25->46 % bzw. 25->60 %. Grenzen: Angepinnt ist NUR die
  Tiefenprobe (uebrige Eingaben = Stand von heute ⇒ Verdikt-Reihen nur fuer alte Kennungen
  lesbar); Schluessel eines Befunds = erste `Beleg:`-Referenz ⇒ "gefunden 0" ist mechanisch.
  `[claude-code:unrecognized_model]` steht genauso in jedem C-Batch-Review - kein Hinweis auf
  ein anderes Modell (`result.modelUsage` = `claude-sonnet-5-5`).
  PowerShell-Falle erneut: `python … *> datei` schreibt UTF-16 - Beleg per `StringIO` +
  `write_text(..., encoding="utf-8", newline="\n")` schreiben.


- R13bw-15 (2026-10-07, Commits `a54d430` + Gate `2d9972d`, gepusht): NUTZERLIMIT VOR/NACH DEM
  LAUF in der Aussensicht. `hx/streamjson.py::rate_limit_info(stand)` (nimmt `lies_rate_limit`
  ODER `info`-Objekt) + `rate_limit_delta_zeile(vor, nach, beschriftung="Nutzerlimit")` ->
  "Nutzerlimit: Sitzung 25 % -> 46 %, Woche 27 % -> 30 %" (fehlende Seite `?`, beide leer
  "nicht gemessen"); `aussensicht.Ergebnis.rate_limit_vor/.rate_limit_nach`, gelesen in `run`
  vor dem Lauf und nach `schreibe_rate_limit`; Kopfzeile in `bericht` direkt hinter `- Lauf:`;
  Rohwerte in `runs/b<N>/meta.json` unter `nutzerlimit`. Tests
  `tests/test_r13bw15_fixes.py` (13), Gate 1685 Tests OK (569,5 s).
  REVIEWER BEWUSST OHNE ZEILE: `runs/b<N>/review.md` ist die Antwortdatei selbst
  (`orchestrator.py` schreibt `(res.text or "") + "\n"`, Kopie `logs/review-<stempel>.md` in
  `reviewer.py` ebenso) - Kopfzeile waere ein Eingriff. `harness-facts.md` ist EINGABE
  (entsteht VOR dem Lauf) und kann den Nachher-Wert nicht kennen.
- R13bw-16 (2026-10-07, Commits `c0dafe0` + Gate `d6d8c7b`, gepusht): REGEL "ROHZEILENPROBE"
  im Worker-Vorspann (`hx/worker.py::WORKER_PREAMBLE`), direkt hinter "ROM-ADRESSEN SUCHEN"
  und vor "ABLAUF", im Stil des Nachbarn (ASCII-Umlaute, vier Aufzaehlungspunkte): drei
  zufaellige Ausgabeeintraege gegen die Rohzeilen (MAME mit Zeilennummer, Hybrid mit
  Schritt/pc), Zufallssaat nennen, `Datei:Zeile` ins Batch-Dokument, `WEGGELASSEN:`/
  `NICHT ZULAESSIG:` im Dateikopf. Quelle: Decomp `AGENTS.md` "## Rohzeilenprobe"
  (Commit `edf12a0`, 26 Zeilen - der Vorspann traegt nur die Kurzform).
  Tests `tests/test_r13bw16_fixes.py` (6, inkl. Gegenprobe gegen die echte AGENTS.md mit
  skipTest und Deckel gegen Aufblaehen des Blocks); Gate 1691 Tests OK (508,6 s).
  Decomp-Repo dabei NICHT angefasst (nur gelesen).
  Zusatzregel fuer Decomp-Arbeit: neue Regel nur ausfuehren, wenn der Harness am Gate steht
  (`state/run.json`: state=GATE_APPROVAL, worker=None) - sonst nur den Diff zeigen.
- R13bw-17 (2026-10-08, Commits `229e9f9` + Gate `de4d9b0`, gepusht): PREFLIGHT-TEXTE NENNEN
  DEN MARKER. Befund aus B292: Worker hatte die Nachrueckliste fertig, hielt es im
  Batch-Dokument fest und wartete - S1 (`worker.nachrueckliste_marker`) liest aber nur
  `antwort*.md` + `text`-Bloecke des Mitschnitts, also blieb die Sperre. Textproblem, keine
  Logik: `hx/uhr.py::PREFLIGHT_HINWEIS` (PostToolUse-Hinweis) UND
  `tools/batch_uhr.py::BLOCK_ZUSATZ` (Grund des deny, angehaengt in `pre_tooluse`, Zeile
  ~343) sagen jetzt beide "schreibe als ANTWORTTEXT eine eigene Zeile `NACHRUECKLISTE
  ERLEDIGT` (nicht in ein Dokument, nicht in einen Werkzeugaufruf) - danach ist der
  Preflight sofort erlaubt"; der Satz vom Batch-Dokument/der Schranke ist gestrichen.
  Tests: `test_r13ao_fixes` (Wortlaut-Literal + neuer Test), `test_r13bw13_fixes` (neuer
  Test auf den deny-Text); Doku `docs/bedienung.md` §12p (zitierter Text + Nachtrag).
  Gate 1693 Tests OK (745,9 s). Die Hook-Texte greifen SOFORT, weil `batch_uhr.py` bei
  jedem Hook-Aufruf als frischer Unterprozess laeuft - kein Neustart noetig.
- R13bw-18 (2026-10-08, Commits `351b746` + Gate `cc0a0ae`, gepusht; Gate 1707 Tests OK in
  646,1 s): WAECHTER VOR DEM
  GATE-LAUF + Startzustand im Beleg. `hx/state.py::laufender_lauf(pfad)` (+
  `LAUFENDE_ZUSTAENDE = (DS_WORKING, CLAUDE_REVIEWING)`) ist die EINE Quelle fuer "laeuft
  gerade etwas?"; `docs/_r13av_lauf.py::wache()` bricht damit VOR dem Lauf mit rc=2 und
  klarer Meldung ab (`--trotzdem` uebersteuert und schreibt eine Warnung in den Bericht);
  `kopf(zustand_start)` nennt "Harness-Zustand beim Start:" UND "… am Ende:".
  Tests `tests/test_r13bw18_fixes.py` (14, inkl. Doku-Zeilen). Doku §12z + Einleitung.
  WICHTIG (Auftragsmuster): VORAB `state/run.json` lesen; nur bei GATE_APPROVAL+worker leer
  darf die volle Reihe laufen - sonst bauen, nur betroffene Testdateien fahren und die volle
  Reihe aufschieben. Bei diesem Auftrag war der Vorabbefund CLAUDE_REVIEWING ⇒ aufgeschoben
  (16 betroffene Dateien einzeln gruen); der Zustand war danach frei (GATE_APPROVAL).
- R13bx (2026-10-09/10, committet+gepusht `aa0df0d`, Gate **1732 Tests OK in 624,6 s**,
  `docs/_r13bx1_volle_reihe.txt`; Wirkung erst nach NEUSTART des Harness):
  AUSSENSICHT AUF DEEPSEEK (Vorgabe `auto`, Schwelle `seven_day` 0,8, Denkstufe `high`).
  Anlass: das Claude-Wochenkontingent ist knapp (09.10.: `seven_day` 87 %), die Aussensicht
  soll ab `seven_day >= 0.8` automatisch auf `deepseek-flash[1m]` laufen, Denkstufe waehlbar.
  EFFORT-NACHWEIS (`docs/_effort_probe.txt`): der Mitschnitt traegt KEIN Effort-Feld
  (`runs/b313/meta.jsonl`: weder `perTurnEffort` noch `"effort"`) - der PostToolUse-Hook
  liefert es, Form `"effort": {"level": "max"}` (OBJEKT, kein Text; ein Vergleich gegen den
  blanken Namen meldet faelschlich ABWEICHUNG). `--effort` kennt low|medium|high|xhigh|max
  (`docs/_r13ar_cli_hilfe.txt:81`); `max` KOMMT auf dem DeepSeek-Endpunkt an, `modelUsage`
  nennt `deepseek-flash[1m]` (kein stilles Mapping, obwohl `claude-*` abgebildet wird -
  `docs/stage1-inventory.md:266`). Merke: `docs/stage2-architecture.md:539` hatte "nie max"
  als E1-Entscheidung - die ist damit pruefbar geworden.
  GEBAUT: `hx/envs.py::_deepseek_env` (EINE Quelle; `worker_env` verhaltensgleich),
  `aussensicht_deepseek_env(cfg, environ, token, effort)`, `precheck`-Rolle "aussensicht"
  (`ROLLEN_DEEPSEEK`, verbietet das Abo-Token); `[claude] config_dir_aussensicht` = eigener
  Ordner, NICHT `cc-worker` (`.claude.json` ist read-modify-write); `.gitignore` +
  `cc-aussensicht/`. Werkzeuge (nur von Hand, NICHT in hx/): `tools/effort_probe.py`,
  `tools/beleg_probe.py` (Belegquote), `tools/schatten_aussensicht.py` um
  `--anbieter abo|deepseek` + `--effort` + getrennte Dateinamen erweitert (Abo-Pfad und
  `_sonnet_vergleich_b<N>.md` unveraendert, Paragraph 19a bleibt gueltig).
  MESSUNG (6 Laeufe, b309/b313/b317, NUR DeepSeek): high 11 Befunde / Belegquote 100 % /
  210-333 s; max 11 Befunde / 100 % / 389-423 s. `max` findet NICHT mehr und braucht ~47 %
  mehr Zeit. Ueberlappung high gegen max: 0-1 gemeinsame Stelle von 4 je Batch - die
  Streuung zwischen Laeufen uebersteigt den Unterschied der Stufen (3 Batches x 1 Lauf
  reichen fuer keinen Qualitaetsentscheid).
  FALLSTRICK (Auswertung): der Vergleich gegen die ECHTE Opus-Aussensicht ist NICHT sauber -
  der Schattenlauf pinnt nur die Tiefenprobe und baut alles andere aus dem Stand von HEUTE
  (Opus B309 zitiert `analysis/_preflight_299.txt`, DeepSeek `analysis/_preflight_321.txt`).
  Sauber ist nur high gegen max.
  FALLSTRICK (Werkzeug): `beleg_probe` meldete "Datei fehlt" fuer `_m242/_c_paket_e.txt` -
  der Pfad war nur ABGESCHNITTEN (`analysis/` fehlte). Vorsatz-Kandidaten versuchen UND den
  Fund ausweisen, sonst meldet man einen Qualitaetsunterschied, den es nicht gibt.
  NACHTRAG R13bx-2 (2026-10-10, committet `d5ac67a`, Gate 1742 Tests OK in 613,2 s):
  DER TAKT HAENGT AM ANBIETER. `[meta] aussensicht_takt_deepseek = 2` (Abo bleibt 4) -
  auf DeepSeek laeuft die Aussensicht alle 2 Batches, um die geringere Befundzahl
  auszugleichen. `takt(cfg, anbieter)` / `grenzen(cfg, anbieter)` / `faellig(...,
  anbieter=...)`: ohne Anbieter gilt der ABO-Takt, damit kein Aufrufer sich aendert.
  Den Anbieter bestimmt `Orchestrator.aussensicht_anbieter()` EINMAL je Batch (Merker an
  der Batchnummer) - `faellig` wird in JEDEM Schleifendurchlauf gefragt und darf
  `logs/rate-limit.json` nicht jedes Mal lesen. Der Anlass nennt `[DeepSeek-Takt]`,
  /bilanz und /status zeigen beide Takte, wenn sie sich unterscheiden.
  GEMESSEN (meine Kostensorge war unbegruendet, Nutzer hatte recht): ein Befund kostet
  ~250-300 Zeichen im Reviewer-Prompt; der Block NACHRICHTEN AUS DER QUEUE hatte in den
  letzten 12 Review-Prompts 1.510-7.271 Zeichen bei ~40.000 gesamt und fehlte in 8 von 12
  ganz -> die Verdopplung bringt +1,5 bis 4 % Mehrlast, kein Kostenfaktor.
  MEMORY-SICHERUNG (Auftrag "alles absichern"): `tools/memory_sichern.py` sichert ALLE
  repo-Profile nach `backups/memory-<stempel>/` (SHA-256-Manifest, prueft jede Kopie) und
  mit `--spiegel` nach `docs/_memory/profil-<hash>/` (getrackt, per Push off-site).
  Grund: es gibt DREI Workspace-Profile (26867c8c 20, 47453457 3, 764c8a21 21 Dateien);
  nur `764c8a21` war ueber `m151_memory_sync.py` gespiegelt - `harness-dev.md` (132 KB,
  DIESE Datei) existierte genau EINMAL. FALLSTRICK: VS Code benutzt **32** Hexzeichen als
  Workspace-Hash, nicht 64 - mit der falschen Laenge kollidierten alle Ordnernamen.
- R13bx-3 (2026-10-10, committet `c684b14`, Gate 1745 Tests OK in 544,7 s): `/autonom` OHNE
  Zusatz raeumt `autonom_trotz_peak` mit ab. NUTZERBEFUND: nach `/autonom yolo` ->
  `/autonom` (aus) -> `/autonom` (an) meldete Telegram wieder "PEAK WIRD IGNORIERT" - das
  war KEIN Anzeigefehler: der Merker wurde bei der blanken Umschaltung unveraendert
  uebernommen und zurueckgeschrieben, und `autonom_yolo()` (= `autonomous` AND Flag) hat das
  Peak-Warten in `orchestrator.py` wirklich uebersprungen. Der blanke Fall war in KEINEM Test
  und in keiner Docstring-Zeile erfasst; `on`/`off` raeumten den Merker dagegen beide ab.
  Jetzt: yolo nur noch ausdruecklich per `/autonom yolo`; die AUS-Meldung nennt das
  abgeraeumte yolo. Tests `test_r13bw5_fixes.py` (17 -> 20), Hilfezeile in `hx/telegram.py`.
  LEHRE: einen Merker, der nur MIT einem anderen Schalter wirkt, beim Ausschalten des
  anderen mit abraeumen - sonst kommt er beim Wiedereinschalten als Nebeneffekt zurueck.
- R13bx-4 (2026-10-10, committet `273a020`, Gate 1751 Tests OK in 636,3 s): die
  Session-Limit-Pruefung laeuft nur noch auf dem ABO-Pfad. NUTZERBEFUND: der DeepSeek-Lauf
  brach nach ~2 min ab mit "ins Session-Limit gelaufen (rc=0)", der Harness pausierte eine
  Stunde und startete keinen Batch. GEMESSEN (`runs/b321/meta.jsonl`): rc=0, `meta.err.txt`
  nur `[claude-code:unrecognized_model]`; ausgeloest hat das Muster `quota` aus
  `protocol.LIMIT_PATTERNS` im ENGLISCHEN DENKTEXT (`:2984` "save weekly quota", `:11290`
  "Weekly quota now 87%", `:14921`), die anderen sechs Muster 0 Treffer. Die Aussensicht SOLL
  ueber das Kontingent reden (M309-3b, M313-3, M317-1b zitieren `logs/rate-limit.json`) -
  jeder englische "quota"-Satz haette den Harness wieder eine Stunde gekostet. Jetzt
  `aussensicht.limit_erreicht(anbieter, roh, text)`: bei `deepseek` gar keine Pruefung (die
  Umgebung traegt kein Abo-Token, `envs.precheck` bricht sonst ab). Musterliste UNVERAENDERT
  (Teil b bewusst nicht gemacht: es gibt kein `logs/review-limit-*.md`, also kein echtes
  Limit-Beispiel als Beleg - die Liste kam aus einem MVP-Sammelcommit ohne Nachweis).
  RESTGEFAHR offen und dokumentiert (`docs/bedienung.md` §21b): eine ABO-Aussensicht mit
  englischem "quota" kann weiterhin falsch anschlagen. OFFEN: `reviewer.run_review` hat
  dieselbe Pruefung - bei einem DeepSeek-Reviewer dort mitbauen.
  LEHRE: einen Fehlalarm nicht an der Musterliste geradebiegen, wenn der ANBIETER die
  Ursache ist - und `looks_like_limit` ueber den ganzen Mitschnitt laeuft auch ueber
  DENKTEXT, den man selbst nie geschrieben hat. Beleg: Test speist die echte Rohzeile ein.
