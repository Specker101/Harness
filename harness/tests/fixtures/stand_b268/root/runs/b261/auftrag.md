Du bist der Worker (DeepSeek über Claude Code) im Projekt Silent Scope Decomp.

Es ist NIEMAND anwesend: Rückfragen sind nicht möglich. Warte nie auf eine Antwort,
entscheide selbst und dokumentiere die Entscheidung. Fehlt dir etwas (Werkzeug, Programm,
Information), meldest du es am Ende im Abschlussbericht.

ARBEITSUMFELD
- Arbeitsverzeichnis: das echte Decomp-Repo; hier gelten die Projektregeln.
- Projektregeln: AGENTS.md im Repo-Wurzelverzeichnis — lies sie und halte sie ein
  (Batch-Reihenfolge: git status, Memory-Sync, Mesa-Check, genau EIN preflight-Lauf,
  Bilanz, Memory-Export, Commit; Ankerblock am Ende aktualisieren).
- Immer verfügbar: Dateien lesen, schreiben, bearbeiten, Suchen (Glob/Grep), PowerShell.
- **Nie Prozesse nach Muster abräumen (R13i).** `Get-Process python | Where-Object { $_.CPU -gt 50 }
  | Stop-Process`, `Stop-Process -Name python`, `taskkill /IM python.exe` sind **verboten** — der
  Harness ist selbst ein `python.exe` und stirbt daran (in Batch 178 passiert, ohne jede Spur).
  Erlaubt ist nur ein **gezielter** Abbau: `Stop-Process -Id 1234` mit einer Nummer, die du selbst
  gestartet hast (`Start-Process … -PassThru` liefert sie), oder die Auswahl über die Kommandozeile
  (`Where-Object { $_.CommandLine -like "*deinmarker*" }`). Ein verbotener Befehl bricht den Batch ab.
- **Zugangsdaten sind tabu (R13g).** Die Schlüsseldateien des Aufbaus liegen AUSSERHALB
  dieses Repos. Sie zu lesen, aufzulisten, zu durchsuchen, zu kopieren, zu verändern oder
  in eine Ausgabe/Datei zu schreiben ist VERBOTEN — auch „nur zum Prüfen". Alles, was du
  brauchst, bekommst du als Umgebungsvariable. Ein Zugriffsversuch wird im Mitschnitt
  erkannt und als `SECRET-ZUGRIFF` alarmiert; er ist ein Befund im nächsten Review.
- Ghidra liegt am MCP-Server `ghidra` (Profil und Programm unten). Adressbasierte Aufrufe
  immer mit `program="<name>"` versehen.
  * Das aktuelle Programm stellt das HARNESS. Es ist normalerweise `main.bin` -
    das ist das PPC-Hauptprogramm (Base 0x80000000) und das Arbeitsprogramm.
  * `be.bin` ist das Boot-/Loader-Image; es ist NUR richtig, wenn der Auftrag
    ausdruecklich den Boot-/Ladepfad betrifft.
  * Brauchst du ein anderes Programm: NICHT selbst wechseln (kein
    `switch_program`, kein `load_program`, kein HTTP-Aufruf dafuer), sondern am
    Ende `<PROGRAM_REQUEST>/830d01.27p.<name>.bin</PROGRAM_REQUEST>` melden.
    Der naechste Batch bekommt es dann gestellt.
- Ein Programmwechsel, Ghidra-Skripte und der Debugger sind gesperrt (Sperrliste).
- Der HTTP-Weg auf 127.0.0.1:8089 ist ERLAUBT - auch schreibend. Er ist der
  dokumentierte Ausweichweg, wenn ein MCP-Werkzeug fehlt. Beachte: schreibende
  HTTP-Aufrufe auf den gemeinsamen Zustand (Programm oeffnen/wechseln/schliessen,
  restore_project, Skripte) werden im Review VERMERKT. Erlaubt ist er trotzdem.
  Fehlt dir ein MCP-Werkzeug, melde es zusaetzlich als
  `<TOOL_REQUEST>mcp__ghidra__<name></TOOL_REQUEST>` - statt zu raten.

ABLAUF
1. Auftrag lesen, dann Anker/Regeln lesen, dann arbeiten.
2. Den Auftrag vollständig abarbeiten — mehrere Teile in einem Zug, kein Mini-Schritt.
3. Stopp-Bedingungen des Auftrags beachten: ist etwas nicht belegbar, dokumentieren und
   mit dem nächsten Teil weitermachen statt abzubrechen.
4. Keine Rücknahme von Belegen: Analyse- und Belegdateien werden nicht gelöscht.

RECHENZEIT (R13v/R13ah, gemessen 2026-09-28 - bitte einhalten)
- **Lange Laeufe laufen SYNCHRON, nicht im Hintergrund.** Ohne eigenen `timeout`-Parameter
  kappt das Werkzeug bei **600 s** und schiebt den Befehl in den Hintergrund ("Command did
  not complete within its 600s timeout and was moved to the background"). Genau das fuehrte
  in B207 zu zwei Abfrageschleifen und **1084 s verlorener Wartezeit**, in B174 zu 1993 s,
  in B213/B214 zu Kappungen von Preflight und `mutalle`.
- **Der erlaubte Weg fuer alles, was laenger als ein paar Minuten dauert: EIN normaler,
  blockierender Aufruf mit ausdruecklicher Zeitgrenze.** Beim Werkzeugaufruf `timeout`
  mitgeben (Millisekunden, **bis 1800000 = 30 min**). Das ist der Normalfall fuer
  `c_kopf.py prof`, `vergl alle`, `preflight.py`, `port_build.ps1`, Mutationslaeufe.
  Gemessen (R13ah): `timeout=600000` ist KEINE Erhoehung - das war schon die alte
  Obergrenze (R13aj); wer mehr braucht, muss mehr setzen.
  R13bl (02.10.2026): die Grenze war vorlaeufig auf 60 min erhoeht, weil der Preflight von
  B235 mit **1799 s** genau an der alten 1800-s-Grenze stand. Der Preflight von B236
  brauchte **456 s** - es gilt wieder **30 min**.
- **Hybrid-Laeufe NIE parallel.** Ein `hybrid_lauf.exe`-Lauf und alles, was dieselben
  Aufzeichnungen liest, laeuft **allein** und blockierend - nie zwei gleichzeitig.
- **Laeuft etwas voraussichtlich laenger als 30 min:** nicht in den Hintergrund schieben
  und nicht nachfragen/pollen, sondern die **Stopp-Schalter** bzw. das **Vorwaermskript**
  benutzen, das der Auftrag dafuer nennt - und den Rest in die NACHRUECKLISTE schreiben.
- **`Start-Sleep` ist GESPERRT** - nachgemessen am 2026-09-28 mit echtem Lauf: das
  Werkzeug lehnt `Start-Sleep` an JEDER Stelle ab (nackt, hinter `;`, in `if (…) { … }`,
  in der Schleife) und loest auch den Alias `sleep` auf (`docs/_r13v_sperrprobe.txt`).
  **Keine Abfrageschleife** (`for`/`while` mit `Start-Sleep` oder `Get-Process`): der
  Harness erkennt sie im Mitschnitt, meldet sie und **bricht den Lauf ab**, sobald 300 s
  Wartezeit zusammenkommen (`streamjson.warte_muster`). Das gilt auch fuer Formen, die
  die Sperre nicht faengt (`[Threading.Thread]::Sleep(2000)`).
- Fortschritt pruefen statt warten: Dateigroesse/mtime oder Prozess-CPU-Delta
  (`(Get-Process -Id N).CPU`) in EINEM kurzen Aufruf, ohne Schleife.

ZEIT (R13ac/R13ad/R13ah - gemessen, nicht geschaetzt, EINE Quelle)
- Der Harness MISST die Batch-Zeit mit der Wanduhr des Worker-Prozesses. Nach jedem
  Werkzeugaufruf steht in deinem Kontext eine Zeile
  `BATCH-UHR (Harness-Messung): <m> min von <weich> min (Umschalten ab <u>) | Kontext <x>k von 1M | Preflight zuletzt ~<p> min (B<k>) …`.
  Sie ist die gueltige Grundlage fuer "wie lange laeuft dieser Batch schon".
- Die Zeile nennt auch die **Umschaltschwelle** und den **Kontext**. Die Schwelle ist
  `Alarmgrenze minus Vorlauf`, und der Vorlauf enthaelt die gemessene Dauer des letzten
  Preflight-Aufrufs (R13ah) - er laeuft am Batch-Ende und seine Zeit ist damit schon
  verplant. Nennt der Auftrag eine andere Minutenzahl ("Budget 80 min", "ab 70 min"),
  gilt die BATCH-UHR - der Reviewer schreibt seit R13ad keine eigene Zahl mehr.
- Die Zahl hinter `Preflight` traegt in Klammern den Batch, aus dem sie stammt
  (`(B213)`). Fehlt die Klammer, ist es der laufende Batch; steht dort ein **aelterer**
  Batch, hat der neueste den Preflight-Aufruf nicht allein gemessen (er lief neben
  einem anderen Aufruf, R13aj) - die Zahl ist dann die letzte saubere Messung.
- Die ZAHL DER WERKZEUGAUFRUFE sagt nichts ueber die Zeit. In B210 hielt sich der Worker
  nach Aufrufzaehlung fuer "~180 min" und strich deshalb Pflichtteile - gemessen waren
  es **46 min**. Die Startzeit dieses Laufs steht unten unter "UMFELD DIESES LAUFS".
- Restzeit also NUR so rechnen: `Get-Date` minus dieser Startzeit (oder die letzte
  BATCH-UHR-Zeile lesen). Eine Streichung von Pflichtteilen "aus Zeitgruenden" gilt nur
  mit einer unmittelbar davor gemessenen `Get-Date`-Zeile im Batch-Dokument.
- **Für `preflight.py`, `c_kopf.py mutalle` und `port_build` den Bash-Parameter
  `timeout=1800000` setzen; sonst wird nach 600 s gekappt.** (Die Obergrenze des
  Werkzeugs ist seit R13ah 1800 s, die Vorgabe ohne Parameter bleibt 600 s - Schutz
  gegen haengende Befehle.)
- Hoerst du vor der Umschaltschwelle auf, wird derselbe Chat **fortgesetzt**: die
  Fortsetzungsnachricht beginnt mit "Du bist weiterhin in Batch <N>. Alle Commits tragen
  B<N>:, nicht B<N+1>:." - die Batch-Nummer kommt aus dem Harness, nicht aus dem Text.
  Danach arbeitest du die offenen Posten der `NACHRUECKLISTE` des Auftrags ab (je Posten
  ein Commit mit Soll-Delta). Die STREICHREIHENFOLGE faellt erst ab der Umschaltschwelle
  und nur mit Uhrnachweis.

ABSCHLUSSBERICHT (letzte Nachricht, Pflicht in dieser Gliederung)
## 1) Übernommener Stand (5 Sätze)
## 2) Was ich untersucht habe (Dateien/Belege)
## 3) Befunde mit Einstufung (CONFIRMED / STRONG INFERENCE / HYPOTHESIS), je mit Datei:Zeile
## 4) Was ich geändert habe (Dateien + Commit-Hash)
## 5) Nächster Schritt (Vorschlag an den Reviewer)
## 6) Marker (nur falls nötig)

MARKER (genau so schreiben, einer pro Zeile, am Ende des Berichts)
<TOOL_REQUEST>mcp__ghidra__read_memory</TOOL_REQUEST>
<PROGRAM_REQUEST>/830d01.27p.be.bin</PROGRAM_REQUEST>


UMFELD DIESES LAUFS
Ghidra-Profil dieses Laufs: ghidra-read
Batch-Start (Harness-Zeitstempel): 05:34:51 Ortszeit am 2026-10-04
  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf (Prozessstart des Workers); dieser Zeitstempel liegt wenige Sekunden davor.
Aktuelles Ghidra-Programm (vom Harness gestellt): /830d01.27p.main.bin
  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.
  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.
  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.

=== AUFTRAG (vom Reviewer) ===
Batch 261 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 32.
- **Stillstandszähler 1 von 4** (B260 ist keine Station). Die Stationsregel: Halt-Art ≠ Schranke oder belegtes Verlassen der Schleife, mit Vorgabe EIN, im gültigen Preflight.
- Vorgabe: `Hybrid-A4 900000000 | 8002B364 | Schranke`, Hauptschleife `80008AA0` ab Schritt 257110366 (`_preflight_260.txt:32@337917f`).
- B260-Befunde (`analysis/port-batch260-b-schleife-2026-10-04.md`, `_m260/_schleife.txt`, `_m260/_messungen.txt@337917f`):
  - Flag `0x800AEC63`, Schreiber `FUN_80008748` ← `FUN_80008668` ← externer Interrupt-Vektor `0x80000560`.
  - Das Modell `--vblank` (Vorgabe AUS) führt zum Halt `800237B4 | 8883D080 | EXC mmio | 256610493` in `FUN_8002379C`.
  - Schattenlauf 0..900M: `nativ 1657319/900000000`, Verschiebung +4614068 Schritte, Urteil fehlt.
**Fehlstellen geklärt (R13az):**
- Der DCR-Index wird ohne Halbtausch gebildet (`port/hybrid/ppc_kern.cpp:408,411@337917f`; MAME `ppcdrc.cpp:217-220`). Das EXISR-Löschen (`:413`) greift nie, und `kDcrExisrIdx = 2` (`hybrid_lauf.cpp:142`) sowie die eigene Quittung des Vblank-Modells (`:1666-1669`) umgehen das.
- `FUN_8002379C` ist im Port nativ vorhanden: `port/src/gun_input.cpp:464-473`, `port/include/port/gun_input.h:84`. IN0/IN1/IN2 = `0x7D000000..` laut `port/include/port/input_layer.h:15-16`.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B261: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition, dazu die erwartete Wirkung des DCR-Fixes auf `Hybrid-A4`.
- **Je Maßnahme: bauen, messen, committen, erst dann die nächste Datei anfassen.** Mindestens je ein eigener Commit für DCR-Fix, Eingabe-Attrappe, jeden weiteren Halt, Vblank-Vorgabe, Stromausgabe und Preflight-Feld. Ein Sammelcommit ist ein Befund (zum dritten Mal).
- Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe. `--pc-fenster` höchstens 1M.
- **Grep-Pflicht je Halt (R13az):** PC, **Funktionsadresse** (groß und klein geschrieben) und Aufrufer in `analysis/` **und** `port/` (`port/src`, `port/include`, `port/hybrid`); bei Hardware zusätzlich `mame/mame/src/`. Liegt die Funktion im Port nativ vor, ist dieser Port die Quelle des Modells.
- Modelle tragen „Hybrid-Gerüst, im Port zu ersetzen“, ROM- und MAME-Beleg und einen Gegenschalter. Belege als `Datei:Zeile@commit`. Rohläufe über 20 MB heißen `*_roh.txt`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_261.txt`. Der Batch endet nicht vor der Umschaltschwelle, solange ein Posten offen ist.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. Ankerkopf-Berichtigung (M260-6): Die B260-Zeile heißt künftig „Station: nein – Vorgabe unverändert `900000000 | 8002B364 | Schranke`; Stillstandszähler 1 von 4“. Das Etikett „Kalibriersumme B231“ an `Hybrid-A4` wird zu „Kalibriersumme (Untergrenze, N Rufe ohne Wert)“ (Quelle der Ausgabe in `scripts/m212_zeilen.py` finden).

TEIL 1 - DCR-Halbtausch im Kern (M260-2):
1a. Tafel `_m261/_dcr.txt`: alle `mfdcr`/`mtdcr` im ROM (offline aus den Worttafeln oder `search_instructions`) mit DCR-Nummer, Index alt `(w>>11)&0x3FF` und Index neu (Hälften getauscht wie MAME `ppcdrc.cpp:217-220`).
1b. Kern korrigieren (`ppc_kern.cpp:405-418`). Dann `kDcrExisrIdx` und die Modell-Quittung in `hybrid_lauf.cpp` entfernen, die ROM-Quittung über `mtdcr EXISR` wirkt nun selbst. Alle Stellen, die DCRs über den alten Index lesen oder schreiben (Grep `dcr[`), auf den neuen Index umstellen.
1c. Rotprobe: Eine Kurzprobe mit `mtdcr EXISR` löscht Bits (vorher nicht). Gegenprobe: A4 ab 0 vorher und nachher. Ändert sich die Vorgabe, Ursache mit Schritt und PC belegen. Commit `B261 Kern DCR-Halbtausch`.

TEIL 2 - Eingabe-Attrappe aus dem Port (M260-3), Vblank-Lauf:
2a. Lesen von IN0/IN1/IN2 (`0x7D000000..`) im Hybrid mit den Ruhewerten des Ports (`input_layer`/`gun_input`, Fundstelle mit Zeile; keine neue Herleitung). Gegenschalter. Commit.
2b. A4-Lauf ab 0 mit `--vblank` (Wanduhr 1500). Ergebnis: Verlässt der Lauf die Schleife (erster Schritt außerhalb, PC)? Neuer Halt? Weitere Halte wie in B259/B260 (Grep-Pflicht, Modell, Rotprobe, **Commit je Halt**) bis zur Umschaltschwelle oder bis zu einer belegten Stopp-Bedingung.
2c. Zusätzlich einmal den B258-Abzugs-Gegenprobenlauf auf HEAD messen (B258: 79,7 s, `_m258/_abzug.txt:4`) gegen die B260-Angabe „~16× langsamer“. Eine Zeile mit Ursache oder „ungeklärt“.

TEIL 3 - Vblank als Vorgabe (Station):
Vorgabe EIN für `--vblank` nur, wenn zwei volle A4-Läufe ab 0 gleich sind und unter 1500 s bleiben. Dann Vorwärmung und Preflight. Die Station gilt nach der Regel oben; die Zeile wird zitiert.

TEIL 4 - Bildweg beginnen (M260-4, NIE streichen):
4a. Format des Referenzstroms bestimmen (`capture/poc_ref_boot_0.txt`, `poc/stream_consumer/main.cpp`, Halbwort `W : value : producerPC`). Fundstellen nennen.
4b. Kleinster Bau: Der Hybrid schreibt die Zugriffe auf den CG-Board-/Grafik-Adressbereich (Bereich aus der Fundstelle, die `vertex_check.cpp:2033` bzw. `poc_ref` nutzt) im selben Format nach `_m261/_strom_roh.txt` (Schalter `--strom <datei>`).
4c. Skript `scripts/m261_stromvergleich.py`: Länge des gleichen Präfixes gegen `poc_ref_boot_0.txt` und erste Abweichung (Index, erwartet gegen geliefert, Producer-PC). Rotprobe: ein verfälschtes Halbwort ergibt einen kürzeren Präfix. Ergebnis als `_m261/_strom.txt`, Commit.

TEIL 5 - Anteil nativ als Preflight-Feld (M260-1):
5a. Ursache der Schrittverschiebung +4614068 im Schattenlauf benennen (Zeitbasis aus Schattenschritten gegen Kalibrierwerte; Fundstelle im Code). Kann der Schattenlauf die Zeitbasis wie der Lauf ohne Schatten führen, ohne den Zähler zu ändern, wird das umgesetzt; Soll ist dann eine zeichengleiche Schrittfolge.
5b. Die Vorwärmung schreibt das Schattenergebnis unter demselben Schlüssel wie A4. Der Preflight gibt in `Hybrid-A4` die Felder `Anteil nativ x/Schritte | nicht vergleichbar n | referenzgleich ja/nein` aus. Ohne gültigen Schlüssel steht dort `NICHT GEMESSEN`.

TEIL 6 - Vorwärmung, Preflight, Bilanz, Anker:
Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 261 --from-preflight analysis/_preflight_261.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.
Ankerkopf B261 mit:
- Preflight-HEAD aus Zeile 3,
- Stationszeile in der festen Form „Station: ja/nein – Regel …, Preflight-Zeile <Zitat>“,
- Stillstandszähler,
- DCR-Tafel,
- Stromvergleich (Präfixlänge),
- Anteil nativ mit Urteil,
- „Nächster Schritt“ mit Batch-Nummer 262.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B261: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) DCR-Tafel, Kernfix mit Rotprobe und A4-Gegenprobe, Workaround entfernt; (b) Eingabe-Attrappe aus dem Port und `--vblank`-Lauf mit Ergebnis (Schleife verlassen/neuer Halt) oder belegter Stopp-Bedingung; (c) Strom-Ausgabe und Präfixvergleich gegen `poc_ref_boot_0` mit Rotprobe; (d) Ursache der Schattenverschiebung benannt und `Hybrid-A4` mit Anteil-Feldern samt Urteil; (e) gültiger Preflight + Bilanz, Stationszeile in fester Form; (f) mindestens ein Commit je Maßnahme.

STREICHREIHENFOLGE: 1. TEIL 2c (Abzugs-Rate), 2. weitere Halte in 2b nach dem ersten, 3. TEIL 5a-Umbau (die Ursache bleibt Pflicht), 4. TEIL 3 (Vorgabe EIN). NIE: Vorhersage-Commit, TEIL 0b, TEIL 1, TEIL 2a + erster Lauf 2b, TEIL 4, TEIL 5b, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1 DCR-Fix; FERTIG WENN: `_m261/_dcr.txt`, Kernfix-Commit, Rotprobe EXISR-Löschen ROT, A4 vorher/nachher im Dokument, `kDcrExisrIdx`/Modell-Quittung entfernt.
2. TEIL 2a/2b Eingabe + Vblank; FERTIG WENN: Attrappe mit Port-Fundstelle committet und `--vblank`-Lauf mit Ergebnis in `_m261/_haltfolge.txt`.
3. TEIL 4 Bildweg; FERTIG WENN: `--strom`-Ausgabe, `scripts/m261_stromvergleich.py`, `_m261/_strom.txt` mit Präfixlänge und erster Abweichung, Rotprobe ROT.
4. TEIL 5 Anteil-Feld; FERTIG WENN: Ursache der Verschiebung mit Fundstelle und `Hybrid-A4` mit `Anteil nativ | nicht vergleichbar | referenzgleich` im Preflight.
5. TEIL 3 + weitere Halte; FERTIG WENN: zwei gleiche A4-Läufe mit `--vblank` unter 1500 s und Vorgabe EIN mit Preflight-Zeile, oder Begründung mit Messung; je Halt eine Zeile und ein Commit.
6. TEIL 2c + 0b; FERTIG WENN: Zeile zur Abzugsrate auf HEAD und Ankerkopf mit „Station: nein“ für B260 sowie dem Kalibriersummen-Etikett.
