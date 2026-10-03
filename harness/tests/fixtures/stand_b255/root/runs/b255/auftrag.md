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
Batch-Start (Harness-Zeitstempel): 14:43:40 Ortszeit am 2026-10-03
  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf (Prozessstart des Workers); dieser Zeitstempel liegt wenige Sekunden davor.
Aktuelles Ghidra-Programm (vom Harness gestellt): /830d01.27p.main.bin
  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.
  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.
  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.

=== AUFTRAG (vom Reviewer) ===
Batch 255 - Silent Scope Decomp

STAND UEBERNEHMEN:
Strang B (Hybrid-Läufer), B-Batch 26, **Batch 1 von bis zu 8 aufeinanderfolgenden B-Batches** (Nutzerentscheid 03.10.2026, ersetzt Reihenfolge B/C: Ziel ist eine möglichst frühe spielbare Beta; B hat Vorrang; C ruht). Ziel der Serie: der Hybrid-Lauf kommt über den zweiten `be40`/`c3a8`-Aufruf hinaus, weiter Richtung Hauptschleife und erstes Attract-Bild. **Fortschritt zählt nur, wenn sich der echte Halt-PC bei unveränderten Schaltern ändert** (heute `8001684C`, Selbstsprung, 696571792 Schritte; den Halt nicht umdefinieren). Nach 8 B-Batches ohne neue Station geht die Frage „B weiter oder C“ an den Nutzer, vorher nicht.
Messziel B: Anteil der nativen Köpfe an den ausgeführten Schritten. Die Preflight-Zeile `Anteil nativ NICHT GEMESSEN (Kalibriersumme B231)` ist KEIN Messwert. Der Halt-PC ist die Fortschrittszahl der Serie.
Stand: B248 bewegte den Halt, B249 und B250 stehen unverändert bei `8001684C`. Der zweite `be40`-Ruf liefert 2 (Schritt 216571301), die erste fehlschlagende Funktion ist `FUN_8000c3a8` mit Rückgabe `0x20000000` (Schritt 216571291). Der Wert stammt aus `FUN_8000b3c4` (Mailslot-Byte `0x780C0003`) und ist nicht entschieden (`analysis/_m250/_haltfolge.txt:38-74`). Lies außerdem `analysis/port-batch250-b-boot-stufe-haltfolge-2026-10-03.md` (Abschnitte 6 und 9), die Ankerzeilen „Voraussetzungen für die Wiederaufnahme von B“, `port/hybrid/maschine.cpp:655-730` (Mitschnitt-Modell, Schreib- und Lese-Modell, `kSharcFolge`) und `port/hybrid/sharc_folge.inc`.
SOLL-KOEPFE: 0 (B-Batch, kein Kopfbau)
C ruht: C-Posten werden nur in der Wiederaufnahme-Liste (TEIL 5) geführt.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md` (`git status`, Memory-`status`, Mesa-Prüfung, `g++ --version`).
- Vorhersage-Commit `B255: Vorhersage` VOR dem ersten `port/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition. Dazu eine Vorhersage der Messung (erwartete Abdeckung ja/nein, erwartete Ursachenklasse), die eine Messung widerlegen kann.
- Belege `Datei:Zeile@commit`. Jedes zitierte Skript liegt unter `scripts/`, nichts in TEMP. Rohläufe über 20 MB heißen `*_roh.txt` und werden per `scripts/m250_auszug.py` belegt (R250).
- Lange Befehle (A4-Vorwärmung, `port_build`, Preflight) als blockierender Aufruf mit `timeout=1800000`, nicht im Hintergrund, keine Warteschleife. Die Diagnoseläufe bis zum zweiten `be40`-Ruf (Schritt ~216,6 M, gemessen ~90 s) laufen kurz über `--stopp-bei-pc` / `--rueckgabe-sonde`. Ein voller A4-Lauf braucht ~1730 s.
- Preflight-Aufruf als EINZIGE Zeile des Aufrufs, genau so: `python -u scripts/preflight.py before *> analysis/_preflight_255.txt`. Kein `echo`, `Get-Content`, keine Pipe und keine Verkettung (B253 und B254 deshalb abgelehnt). Ausgabe und Exit-Code in einem EIGENEN Folgeaufruf lesen.
- Ändert sich etwas unter `port/hybrid/` oder `port/src/` (Hybrid-Quellen), ist der A4-Zwischenspeicher kalt. Dann VOR dem Preflight `scripts/m254_prewarm.py` als blockierenden Aufruf laufen lassen. Ein Preflight mit kaltem Speicher überschreitet die 1800 s. Der Preflight muss „Zwischenspeicher Treffer“ melden. Alle Änderungen unter `scripts/` und `port/` liegen VOR der Vorwärmung. Ein zweiter Preflight nach einer Änderung ist zulässig, der letzte zählt (R13bf).
- Vor dem Preflight alle Harness-Binaries bauen (`mingw32-make all gl hybrid head193`), danach `_m255/_binary_quellen.txt` (kein Binary älter als seine Quelle).
- „Blockiert“ oder „fehlt“ NUR mit Beleg: (i) Zitat der Auftragszeile mit `Datei:Zeile`, (ii) bei „fehlt“ der Grep auf den Bezeichner (die Adresse oder das Symbol) über `analysis/` und `port/` mit Fundstelle oder `Fehlstelle: gesucht in analysis/ und port/, nicht gefunden (Grep "<Bezeichner>")`. Aufwand, ein zweiter Preflight und die Preflight-Dauer sind KEINE Blockade. Der Batch endet nicht vor der Umschaltschwelle der Batch-Uhr, solange Nachrückposten offen sind. Streichen nur mit unmittelbar vorher gemessener `Get-Date`-Zeile im Batch-Dokument.
- Eine Behebung braucht ROM-Stelle und Analysedokument; die MAME-Quelle ist nicht Pflicht, wo MAME konstruktionsbedingt keine hat (Entscheidung B234, `analysis/r1b-workstream.md`). Geraten wird nicht. Kein `disassemble_bytes` (R398). Alle benutzten Ghidra-Werkzeuge im Bericht nennen.
- Verbote: kein Force-Push, keine Historie umschreiben, keine Belege löschen, kein `restore_project`, keine Änderung der Grundregeln in `AGENTS.md`.

TEIL 1 - Mailslot-Messung beim zweiten c3a8-Aufruf (Hauptteil, erster Auftrag der Serie):
Messe an `FUN_8000c3a8` / `FUN_8000b3c4` (Mailslot `0x780C0000..3`, Lesebyte `0x780C0003`), jeweils für den ersten UND den zweiten Aufruf:
a) **Zugriffsprotokoll** je PPC-Zugriff auf `0x780C0000..3`: Schritt, PC, Richtung (Schreiben/Lesen), gelieferte Byte, Antwortindex `sharc_folge_idx_`, `kSharcFolgeN`. Schreib- oder Lesemodell: die Schalter des A4-Laufs stehen in `scripts/m212_zeilen.py` (argv) und werden benannt (`--sharc-antwort` ja/nein).
b) **Erwartet gegen geliefert**: für den fehlschlagenden Vergleich (`8000c54c cmplw r3,r31` mit r31 = 0x2000 und `8000c590 cmplw r3,r5` gegen die Shared-RAM-Summe) die Operanden: Schritt, PC, erwartetes Byte oder Wort (aus dem ROM-Code und mit Ghidra-Beleg), geliefertes Byte. Der B250-Befund war nur STRONG INFERENCE (nicht bis zum Einzelvergleich heruntergemessen). Hier wird er heruntergemessen oder bleibt ausdrücklich so eingestuft.
c) **Board-Zuordnung**: Welches Board (CG-Board 0 oder 1, DSP) adressiert der zweite Aufruf, belegt aus ROM (Parameter oder Auswahlschreibung in `c3a8`/`b3c4`) und aus dem Mitschnitt (`sharc_folge.inc` deckt laut Anker nur dsp2/CG-Board 1)? Tafel „Aufruf | Board | Quelle des Beleges“.
d) **Deckt der Mitschnitt den zweiten Aufruf ab?** ja/nein mit Zahlen: benötigte Antworten gegen `kSharcFolgeN` und die Anzahl der Zugriffe in Aufruf 2. Wird der Index am Folgenende festgehalten (`sharc_folge_idx_ + 1u < kSharcFolgeN`), steht das als eigene Zeile. Erste Abweichung: Ursachenklasse (Folge erschöpft / falsches Board / Pending-Zeitmodell / anderes) mit Beleg.
e) Ist der Mitschnitt nicht ausreichend: Grep nach der Erzeugung der Folge (`kSharcFolge`, `sharc_folge.inc`, `konppc`, `m_dsp_comm_sharc`) in `analysis/`, `scripts/` und `port/` und die Frage, ob ein weiterer Mitschnitt aus den vorhandenen MAME-Quellen/Werkzeugen erzeugbar ist. Nur wenn nicht, `WARTET AUF LIVE-AUFNAHME: <Board, Zeitpunkt, was aufzuzeichnen ist>`, dann mit TEIL 2 über das ROM-abgeleitete Modell weiter. Die Arbeit hängt davon nicht ab.
Erwartet: Tafel im Batch-Dokument, Rohlauf als `*_roh.txt` mit Auszug.

TEIL 2 - Behebung und Halt-Messung (nur wenn TEIL 1 die Ursache eindeutig benennt):
Das kleinste Modell, das den zweiten `c3a8`-Aufruf mit der ROM-Erwartung beantwortet (z. B. die Folge für das zweite Board, oder der Handschlag aus `FUN_8000b3c4`), als „Hybrid-Gerüst, im Port zu ersetzen“, mit ROM-Beleg. Je Änderung eine Rotprobe (eine Antwort bewusst verfälschen: der zweite `be40`-Ruf liefert dann wieder ungleich 0), danach der Kurzlauf bis zum zweiten `be40`-Ruf (Soll: Rückgabe 0 statt 2). Danach Vorwärmung und Preflight. Halt-PC bei unveränderten Schaltern berichten. Bewegt er sich: neue Station notieren und den nächsten Halt nach demselben Dreischritt (erster fehlschlagender Vergleich, erwartet gegen geliefert, Ursachenklasse) messen, solange die Batch-Uhr es zulässt. Bewegt er sich nicht: die nächste fehlschlagende Prüfung mit Beleg benennen. Der Halt wird nicht umdefiniert, kein Schalter wird geändert, um ihn zu bewegen.

TEIL 3 - B-Bericht (Nutzerentscheid, nach JEDEM B-Batch Pflicht, im Batch-Dokument UND im Ankerkopf):
Drei Zeilen: **aktuelle Station** (Halt-PC, Halt-Art, Schritte laut Preflight `Hybrid-A4`), **nächste bekannte Station** (die nächste fehlschlagende Prüfung oder der nächste bekannte Halt, mit Beleg; „unbekannt“, wenn nicht gemessen), **Aufwandsschätzung mit Rechenbasis** (Batches = Anzahl bekannter Stationen × gemessener Batches je Station aus B248 bis B255; die Rechenbasis wird ausgeschrieben, die Zahl ist HYPOTHESIS). Die Serie führt „B-Batch k von 8“ und die Zahl der Batches ohne neue Station. Die Preflight-Zeile `Anteil nativ` wird unverändert als „NICHT GEMESSEN“ gemeldet, nicht als Fortschritt.

TEIL 4 - C-Messlatte berichten (Nutzerentscheid, C ruht):
In der Bilanz-Doku die Zeilen „referenzgleiche Insn der ausgeführten Menge“ (heute 5641) und „davon voll verifiziert“ getrennt von „davon in teilgeprüften Köpfen“ (29; Quelle `_m254/_teilgeprueft_c.txt`). Reihe je C-Batch (B251 510, B252 191, B253 461, B254 176). Kein neuer Kopfbau in diesem Batch.

TEIL 5 - Doku, Wiederaufnahme-Liste von C, Bilanz:
Im Anker einen Abschnitt „Voraussetzungen für die Wiederaufnahme von C“ mit diesen Posten: 8000EC80 (83, Treffer-Kopf, `r23 += 8` je Bit, `_m254/_posten2_blocker.txt`), 8001B658 (41, Treffer-Kopf, schon einmal verifiziert), 80017BBC (40), 80023864 (77, braucht `orc` op31 xo 412 analog `andc`, `scripts/m114_matrix.py:789`; ein Werkzeugposten, kein fehlendes Material), Schlüsselprobe K0/K1 (M254-3), teilgeprüfte Blöcke von 80029A50 (17/34) und 8004F5A4 (17/31), Tafel 1c, Boot-Init 80013A88 (190, ans Ende). Plus die Regel „Treffer-Köpfe gebündelt, eine Vorwärmung“ (M254-2). Ankerkopf nach `AGENTS.md`, Memory-Export, danach `m149_bilanz.py --batch 255 --from-preflight analysis/_preflight_255.txt --write-anchor`; nach dem Preflight nichts mehr unter `scripts/` ändern. Abweichungen von der Vorhersage erklären, nicht glätten.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen; `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse: >50 gelöschte Zeilen, dann melden). Ankerblock mit `UEBERTRAG:`-Zeilen und `GESCHLOSSEN`-Vermerken. Die `B-SCHRITT`-Zeile nennt „B-Batch 26 (1 von 8 der Serie)“.

FERTIG WENN: (a) Tafel TEIL 1a-d im Batch-Dokument, mit Antwort auf „deckt der Mitschnitt den zweiten Aufruf ab“ (ja oder nein, mit Zahlen) und „Board-Zuordnung“ mit Beleg; (b) erwartet gegen geliefert am ersten fehlschlagenden Vergleich gemessen (oder ausdrücklich STRONG INFERENCE mit Grund); (c) entweder `Hybrid-A4`-Halt-PC im Preflight ≠ 8001684C bei unveränderten Schaltern mit Rotprobe, oder die nächste fehlschlagende Prüfung mit Beleg und der gemessene Grund, warum nicht behoben; (d) TEIL 3-Bericht mit Station, nächster Station und Rechenbasis; (e) genau ein gültiger Preflight (der letzte, „Zwischenspeicher Treffer“) + Bilanz; (f) Wiederaufnahme-Liste von C im Anker.

STREICHREIHENFOLGE: 1. TEIL 2 über die erste neue Station hinaus, 2. Posten 5 (Zustandsabzug), 3. Posten 4 (Formlücken), 4. TEIL 4. NIE: Vorhersage-Commit, TEIL 1, Preflight, Bilanz, Memory-Export, TEIL 3, Wiederaufnahme-Liste von C.

## NACHRUECKLISTE
1. TEIL 1 Mailslot-Messung (a-d) mit Tafel, Rohlauf-Auszug, Antwort „Abdeckung ja/nein“ und Board-Zuordnung; FERTIG WENN: Tafel im Batch-Dokument, Quelle je Zeile `Datei:Zeile@commit`.
2. TEIL 2 Behebung mit Rotprobe und Kurzlauf (zweiter `be40`-Ruf: Rückgabe 0), oder ein gemessener Grund, warum nicht; FERTIG WENN: Rotprobe ROT gewordener Kurzlauf oder Beleg „nicht behebbar mit ROM-Beleg“.
3. TEIL 3 B-Bericht (Station / nächste Station / Aufwand mit Rechenbasis) und TEIL 5 Wiederaufnahme-Liste von C im Anker; FERTIG WENN: die drei Zeilen und die Liste mit allen acht Posten im Ankerkopf.
4. Die 9 Formlücken aus `_m249/_formluecken.txt` (`19/0, 19/150, 27, 29, 31/26, 31/163, 31/412, 31/597, 31/725`); FERTIG WENN: je Form ein Eintrag „verifiziert oder offen mit Grund“, mindestens eine Form geschlossen.
5. Zustandsabzug vor `be40` zur Verkürzung der Läufe; FERTIG WENN: der Kurzlauf bis zum Halt braucht weniger als ein Zehntel der A4-Zeit (gemessen), oder die Fehlstelle (Grep) mit Grund.
6. TEIL 4 C-Messlatte-Zeilen („davon voll verifiziert“) in der Bilanz-Doku; FERTIG WENN: beide Zahlen mit Rechenweg im Batch-Dokument.
