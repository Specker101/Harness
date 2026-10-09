# Git / Repo-Hygiene (Silent Scope Decomp)

## Stand 2026-09-14: Upload-Vorbereitung
- History-Rewrite mit git-filter-repo: `.git` von 4.27 GB -> ~6.7 MB; alle 8 Alt-Commits erhalten (keine Squashes).
- Rewrite wurde in einem Temp-Klon durchgefuehrt, danach `.git` getauscht -> im Projektordner wurde NIE eine Arbeitsdatei geloescht (verifiziert: alle 9155 vorher getrackten Pfade existieren weiter).
- Backup der alten History liegt als `.git-old-4gb/` im Projektordner (ignoriert, ~4.2 GB, nach erfolgreichem Push loeschbar).
- Kein Remote konfiguriert (Stand danach).

## Verifiziert 2026-09-21: port/ IST getrackt
- 159 Dateien in `port/` == 159 getrackte Pfade (`git ls-files port`). Kein `git add` offen.
- Working Tree clean, 0 untracked Dateien. Nur `port/build/` ist ignoriert (Build-Artefakte, gewollt).
- Behauptung "port/ ist untracked" war falsch (vermutlich alte Session/Verwechslung mit `mothballed/` bzw. `poc/`).
- **Echter offener Punkt:** Remote `origin` = https://github.com/Specker101/Silent-Scope-Decomp.git
  existiert; `main` ist 2 Commits **vor** `origin/main` (b7f4409 "Stand 21.9.26", 5311a74 "Stand 16.9.26")
  -> Backup-Risiko liegt nur beim fehlenden `git push`, nicht bei fehlendem `git add`.

## Push 2026-09-21 ERFOLGREICH (main = origin/main = 9bbae9c)
- Ursache des "Push geht nicht": NICHT ein Pull-Problem, sondern GitHub lehnt
  `analysis/_m30_texreg_lines.txt` (279,67 MB) ab -> harte Grenze 100 MB/Datei.
  `git rev-list --left-right --count origin/main...main` war `0  3` => reiner
  Fast-Forward, es gab nie etwas zu pullen. **Nie pullen, wenn "behind" = 0 ist.**
- Loesung (Option 1): Rohdatei aus History gepurged + `.gz`-Archiv versioniert.
  Neues Modul `scripts/_texreg_log.py` (bevorzugt .txt, sonst transparent .gz).
  Angepasst: m30_texreg_pairs, m30_texreg_triples, m40_drawn, m40_texreg, m40_validate.
  Archiv `analysis/_m30_texreg_lines.txt.gz` = 3,18 MB (deterministisch, mtime=0),
  entpackt exakt 293259890 Bytes (== Rohdatei).
- **FALLSTRICK gzip.open:** `gzip.open(f,'r')` ist BINAER (wie 'rb').
  Text braucht `'rt'`, sonst `ValueError: Argument 'encoding' not supported in binary mode`.
  `_texreg_log._gz_open()` ergaenzt das 't' automatisch.
- **FALLSTRICK Reihenfolge:** Vor `filter-repo` die Datei erst per `git rm --cached`
  entkoppeln — sonst loescht der Hard-Reset am Ende von filter-repo die Arbeitsdatei
  (bei den PNGs war das schon vorher passiert, daher fiel es nicht auf).
- Verifiziert: Rohdatei 279,7 MB noch auf Platte; 0 Vorkommen in der History;
  0 cgtex/fdc-PNGs in der History; 2335 getrackte Dateien; Worktree clean.
- Aufgeraeumt: Sicherungsbranch `_sicherung_vor_png_purge` geloescht,
  `git reflog expire --expire=now --all` + `git gc --prune=now` -> `.git` 40,8 -> **14 MB**.
- M40-Skripte sind deterministisch: erneuter Lauf erzeugt `_m40_texreg.csv` byte-identisch.

## PNG-Purge aus der History (2026-09-21) — ENDZUSTAND
- Problem: `git rm --cached` entfernt nur aus dem Tree; die 2049 PNGs steckten in `b7f4409`
  ("Stand 21.9.26"), der noch **ungepusht** war -> ein normaler Push haette sie hochgeladen
  (origin/main hatte 0 PNGs, GitHub hätte sie also neu bekommen).
- Fix: `git filter-repo --force --refs origin/main..main --invert-paths
  --path-glob "analysis/cgtex_png*" --path "analysis/fdc_tex"`
- Ergebnis: `b7f4409` -> `8a9fbc9`, `4c430b0` -> `dbea930`; `5311a74` und alle gepushten
  Commits behielten ihren Hash -> origin/main bleibt Vorfahre, **kein Force-Push noetig**.
- Verifiziert: 0 PNG-Vorkommen ueber ALLE Commits; Diff alt->neu = genau 2049 Loeschungen,
  0 Nicht-PNG-Aenderungen; 2334 getrackte Dateien alle auf Platte vorhanden; 2196 PNGs
  lokal; 159/159 port-Dateien; Worktree clean.
- Sicherungsbranch `_sicherung_vor_png_purge` (zeigt auf altes 4c430b0) — nach erfolgreichem
  Push loeschbar, danach `git gc` spart ~19 MB (unreachable Blobs). Unreachable Objekte
  werden NICHT gepusht, der Push-Umfang enthaelt 0 cgtex/fdc-Objekte.
- **FALLSTRICK filter-repo:** Bei vorhandenem `.git/filter-repo/already_ran` (vom
  14.09.-Rewrite) fragt es interaktiv "Treat this run as a continuation ... (Y/N)?" und
  **haengt ohne TTY endlos**. Laeuft danach korrekt durch (~333 s). Kuenftig vorher
  `.git/filter-repo/already_ran` loeschen oder Antwort explizit einspeisen.

## Push-Umfang / grosse Dateien (2026-09-21)
- Push-Payload `origin/main..main`: 1995 Objekte, 318 MB **unkomprimiert** — sieht schlimm
  aus, ist aber harmlos: `analysis/_m30_texreg_lines.txt` (279,7 MB MAME-Debug-Dump
  `[:voodoo0] SSC_TEXREG`) komprimiert auf **3,7 MB** (Faktor 76x, gzip wie zlib-6).
  -> Pack des Push real grob ~5-7 MB. Datei bleibt als Beleg-Kanal getrackt (gelesen von
  `m30_texreg_pairs.py`, `m30_texreg_triples.py`, `m40_drawn.py`, `m40_texreg.py`).
- `.git` = 39,4 MB (enthaelt die 18,8 MB PNG-Blobs noch als unreachable Objekte).
- 8 `analysis/_m*_gl_*_frame.png` sind getrackt, aber mehrere haben **identischen Blob**
  (`28e5d52a8d`) -> git listet den Blob einmal, daher erscheinen nur ~5 Pfade im Push-Umfang.

## Textur-PNGs aus dem Index entfernt (2026-09-21, Commit 4c430b0)
- 2057 PNGs / 18,84 MB waren getrackt; entfernt: `analysis/cgtex_png*` (2019 Dateien)
  + `analysis/fdc_tex` (30 Dateien). Alle reproduzierbar:
  `scripts/m36_texpng.py`, `scripts/m37_scene_extract.py`, `scripts/m34_texextract.py`,
  `scripts/m35_cgtex.py` (schreibt `analysis/fdc_tex`).
- Getrackt bleiben die 8 kleinen `analysis/_m*_gl_*_frame.png` (20 KB, in 8 analysis-Docs
  referenziert und von `m6x/m7x_frame_compare.py` gelesen) -> NICHT ignorieren.
- Achtung: `m38_*`/`m39_*`-Skripte LESEN `analysis/cgtex_png*` -> Extractor vorher laufen lassen.
- `git rm -r --cached` (Dateien auf Platte unveraendert, verifiziert 2196 -> 2196).
- `.git` bleibt trotzdem 39,4 MB: die Blobs stecken weiter in der **History**; kleiner wird
  nur ein Rewrite (git-filter-repo) — bewusst nicht gemacht.
- Merke: `git commit` ohne vorheriges `git add` erfasst `.gitignore`-Aenderungen NICHT
  (hier passiert, per `git commit --amend` korrigiert).

## .gitignore (Root, neu)
Ignoriert: ROMs/NVRAM/MAME-State (`rom/`, `mame_roms/`, `nvram/`, `snap/`, `cfg/`),
Fremdsoftware (`ghidra_12.1.2_PUBLIC/`, `mame/`, `tools/make/`, `tools/msys2-installer.exe`, `tools/ghidra-mcp/`),
`ghidra/*.rep/`, `analysis/tex_dumps/`, `logs/`, `*.log`, Build-Artefakte, `__pycache__/`, `.vscode/*` (Ausnahme `mcp.json`).
`capture/*` ist ignoriert; Ausnahmen: `*.glsl`, `*_stream.txt`, `captured_triangle.txt`, `pc_attrib_new/*.txt`.

## Getrackt (328 Dateien, ca. 29 MB)
`analysis/` (Doku + JSON-Artefakte), `scripts/`, `poc/`, `capture`-Ausnahmen, `mothballed/`,
`.vscode/mcp.json`, `readme.md`, `AGENTS.md`, `.gitattributes`, `.gitignore`.

## Konventionen
- Aufraeumen immer per `git rm --cached` (+ .gitignore); lokale Dateien nie loeschen.
- `.gitattributes`: `* text=auto`, Dump-Formate als `binary`.
- Grosse Anhaenge bleiben lokal: `analysis/_f2942_segment.json` (15.8 MB) ist der groesste getrackte Blob.

## Encoding-Falle (Batch 60, 2026-09-17) — WICHTIG
- **NIE `(Get-Content -Raw) -replace ... | Set-Content -Encoding UTF8`** auf UTF-8-Dateien ohne
  BOM: PS 5.1 liest ohne `-Encoding` als ANSI (cp1252) und schreibt danach UTF-8+BOM ->
  Datei doppelt kodiert (`—` wird `â€"`, `ü` wird `Ã¼`), in B60 dreimal passiert.
- **Reparatur:** BOM weg, `utf-8` dekodieren, je Zeichen `cp1252` kodieren; Zeichen ohne
  cp1252-Entsprechung im Bereich U+0080..U+009F als Rohbyte durchreichen
  (`scripts/m60_fixenc2.py`). Danach auf `â€` und U+0090 pruefen (beide = 0) und ohne BOM
  schreiben. Verlust nur, wenn PS 5.1 ein undefined Byte durch `?` ersetzt hat.
- **Stattdessen:** Textdateien immer mit Python (`io.open(..., encoding='utf-8')`) editieren
  oder `Add-Content -Encoding UTF8` (haengt nur an, kein Rundlauf).

## BOM-Befund 2026-09-23 (Batch 126) — ARBEITSSTAND, R60-Klasse
- Drei Arbeitsstandsdateien trugen eine UTF-8-BOM: `port/src/game_flow.cpp`,
  `scripts/port_regression.py`, `analysis/r1b-workstream.md`.
- **Beleg, dass es NICHT aus Batch 126 stammt:** neun mit demselben Werkzeug
  angelegte/bearbeitete Dateien sind BOM-frei (`slot_show.*`, `port_selftest.cpp`,
  `game_flow.h`, `m104_built.py`, `port-interface.md`, `port-implementation-log.md`,
  `ghidra-mcp-notes.md`, `m126_hidden.py`), und `git show HEAD:` kennt fuer die
  drei Dateien **keine** BOM (alle drei sind stark vorgaengig geaendert).
- **Behoben** per Python (`open(p,'wb').write(b[3:])`, LF/CRLF unveraendert);
  danach Regression erneut 32 + 238 Anker, 0 Fehler.
- **Regel:** BOM **vor** dem Bau pruefen
  (`python -c "print(open(p,'rb').read()[:3])"`), nicht nach dem Push.

## `git checkout -- <datei>` + Editor-Schreibweg (Batch 141, 2026-09-24) — R346
- `scripts/m104_built.py` ist im Index als **"A"** (gestaged, addiert) geführt: der
  Worktree-Stand ist viel **jünger** als der Index. Ein `git checkout -- <datei>`
  (nach einem BOM-Schaden) hat deshalb den **alten Index-Stand** zurückgeholt und
  `B140_HEADS` **und** die B139-`VERDICTS`-Registry (`JUDGE`/`VERDICTS`, R340)
  entfernt. Der **Preflight** hat es als FEHLENDE `R207`-Zeilen gemeldet.
- **Zweitbefund:** ein Editier-Werkzeug meldete Erfolg, die Datei blieb auf der
  **Platte** aber unverändert (0 Treffer im `io.open`-Wortlaut, `LastWriteTime`
  alt). Geschrieben wurde dann per **Python-Skript** (R297-Muster) — Verifikation:
  Zeichenzahl/Suchbegriff direkt nach dem Schreiben.
- **Regel:** nach jedem Schreiben den **Plattenstand** prüfen (`io.open`), nie nur
  die Werkzeugmeldung glauben; `git checkout` nur nach `git diff --cached --stat`
  (Index-Stand gegen Worktree prüfen); Änderungen an getrackten Dateien lieber
  sofort stagen oder sichern.


## Echter Wiederherstellungspunkt (2026-09-24, R349)
- Commit **`d471b88`** "Stand 24.9.26: Port-Batches 91-141 (Waehler-Huellen,
  Szene-Satzkette) + R349-Integritaetspruefung": **1672 Dateien, +256950/-4061**
  in EINEM Commit (`git add -A` + `git commit -F <msg>`). Worktree danach clean.
- Umfang VOR dem Commit (die R346-Frage): gegen HEAD(9bbae9c) **1554 Dateien
  gestaged / +243347 / -4061** + **56 untracked**; davon lagen **50 Dateien
  (+4930/-821) sogar noch UNGESTAGED** vor - die echte Gefahrenzone. In ihr:
  `voter_leaves2.*`, `mission_script.cpp`, `mission_check.cpp`,
  `scripts/{m104_built,m114_pass,m115_pass,m116_pass,m130_ast,m130_ref,preflight}.py`,
  `port_regression.py`, `r1b-workstream.md`, `port-interface.md`,
  `port-implementation-log.md`, `analysis/_m13x_*.txt`, `_pf_prev/*`.
- **Integritaetsmuster (wiederverwenden):** Kopf-Tafel `kVl2Heads[]` (address,
  insn) gegen die `kFn*`-Konstanten in `.h` UND gegen `reg.add(kFn*)` stellen
  (SOLL 35/35/35), dann **jedes Kopfwort gegen das ROM** lesen
  (`rom/build/830d01.27p.main.bin`, Offset = Adresse - 0x80000000) und die
  Adressfolge je Kopf auf Luecken pruefen. FNV-1a ueber die Woerter (BE-Bytes)
  == `EFE73A6E`. Summe/Insn/Adressen allein reichen NICHT.
- **R349b:** `scripts/m139_verdict.py parallel` zippt die ALTE 15-Zeilen-Tafel
  **positionell** gegen die Registry; seit B140 (`P100-Selbstprobe`) sind es
  **16** → die Anzeige-Spalte ist ab dem P100-Block um EINS verschoben
  (Urteile unberuehrt). NICHT repariert, nur gemeldet.
- **Achtung:** `python scripts/preflight.py ...` ueberschreibt Belege
  (`_m130_span.txt`, `_m114_p100.txt`, `_m114_p100sel.txt`); der Altstand geht
  seit R355 automatisch durchnummeriert nach `analysis/_archiv/` (kein
  Vorher-Kopieren von Hand mehr) → nach einem Commit macht der naechste
  Preflight den Worktree wieder schmutzig.
- **R368 (2026-09-25, GEMESSEN) `preflight.py` NICHT durch eine Konsole-Pipe
  schicken:** `python scripts/preflight.py before | Tee-Object -f x.txt |
  Select-Object -Last 30` **haengt** — preflight druckt erst am ENDE, die Pipe
  puffert, und sobald der Lauf in den Hintergrund wandert, wird die Konsole
  nicht mehr gelesen: python fror bei 76 s CPU ein, sein Kind `port_gl.exe
  glstream` stand 5 min bei 0,078 s CPU (GL-Kontext-Aufbau), `Tee` legte nie
  eine Datei an. **Rezept: Datei-Umleitung `*> datei.txt`** (kein Pipe!) und
  danach lesen — damit laeuft `preflight.py before` (R207 + Regression + P100)
  in ~2-3 min durch, GL-Anker inklusive. Ohne UCRT64 auf dem PATH meldet
  `port_gl.exe` stattdessen Exit `0xC0000135` (STATUS_DLL_NOT_FOUND, R310) —
  das sieht wie ein Inhaltsproblem aus, ist keins.

## Bekannte Restpunkte
- 136 getrackte Dateien enthalten absolute Pfade `C:/Users/Arcade/...` (nicht bereinigt; betrifft auch `.vscode/mcp.json`).
- `poc/frame_*.ppm/.raw` (~7 MB) und `capture/`-Ausnahmen sind Renderdumps und koennten ebenfalls ignoriert werden.
- Lokale Abhaengigkeiten werden geklont: `mame/mame` (mamedev/mame), `tools/ghidra-mcp` (bethington/ghidra-mcp).
