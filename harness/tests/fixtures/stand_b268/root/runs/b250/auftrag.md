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
- **Der erlaubte Weg fuer alles, was laenger als ein paar Minuten dauert:**
  1. **Synchron mit ausdruecklicher Zeitgrenze:** beim Werkzeugaufruf `timeout`
     mitgeben (Millisekunden, **bis 1800000 = 30 min**). Das ist der Normalfall fuer
     `c_kopf.py prof`, `vergl alle`, `preflight.py`, `port_build.ps1`, Mutationslaeufe.
     Gemessen (R13ah): `timeout=600000` ist KEINE Erhoehung - das war schon die alte
     Obergrenze; wer mehr braucht, muss mehr setzen.
     R13bl (02.10.2026): die Grenze war in R13bj vorlaeufig auf 60 min erhoeht, weil der
     Preflight von B235 mit **1799 s** genau an der alten 1800-s-Grenze stand. Der
     Preflight von B236 brauchte **456 s** - die Bedingung fuer den Rueckbau ist erfuellt,
     es gilt wieder **30 min**. Wer laenger braucht, nimmt Weg 2.
  2. **Nur wenn es laenger als 30 min dauern kann:** `Start-Process … -PassThru` und
     dann **EIN** `Wait-Process -Id $p.Id -Timeout 480` - und danach die Ausgabe
     lesen. Kein zweiter Wartebefehl, keine Schleife.
- **`Start-Sleep` ist GESPERRT** - nachgemessen am 2026-09-28 mit echtem Lauf: das
  Werkzeug lehnt `Start-Sleep` an JEDER Stelle ab (nackt, hinter `;`, in `if (…) { … }`,
  in der Schleife) und loest auch den Alias `sleep` auf (`docs/_r13v_sperrprobe.txt`).
  **Keine Abfrageschleife** (`for`/`while` mit `Start-Sleep` oder `Get-Process`): der
  Harness erkennt sie im Mitschnitt, meldet sie und **bricht den Lauf ab**, sobald 300 s
  Wartezeit zusammenkommen (`streamjson.warte_muster`). Das gilt auch fuer Formen, die
  die Sperre nicht faengt (`[Threading.Thread]::Sleep(2000)`).
- **Unabhaengige Rechenlaeufe parallel starten, nicht nacheinander.** Die Maschine hat
  4 Kerne; ein Lauf ueber alle IDs in EINEM Prozess ist fast immer schneller als viele
  Einzelaufrufe hintereinander (jeder zahlt das Laden erneut).
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
Batch-Start (Harness-Zeitstempel): 01:32:35 Ortszeit am 2026-10-03
  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf (Prozessstart des Workers); dieser Zeitstempel liegt wenige Sekunden davor.
Aktuelles Ghidra-Programm (vom Harness gestellt): /830d01.27p.main.bin
  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.
  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.
  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.

=== AUFTRAG (vom Reviewer) ===
Batch 250 - Silent Scope Decomp

Strang B, B-Batch 25 (B-SCHRITT 4/5 „Boot bis Hauptschleife“). DRITTER und letzter B-Batch der harten Zwischenprüfung (Nutzerentscheid 02.10.2026).
SOLL-KOEPFE: 0 (B-Batch, kein Kopfbau)

STAND UEBERNEHMEN:
- HEAD 846c3d9. Ungetrackt: `analysis/_m249/_a4_an.txt`, `_a4_aus_err.txt`.
- Gültiger `_preflight_249.txt`: `Hybrid-A4` 696571792 Schritte | nativ 1511 (Kalibriersumme) | Halt-PC 8001684C | Selbstsprung (`:32@846c3d9`). Der Preflight dauerte 2335 s, davon `Hybrid-Lauf` 1784,6 s (`_m249/_preflight_zeiten.txt:33,42`).
- `ab90` = 0, `ab0c` erreicht (Proxy-Anfragen 02480000/84–87, 02788000). `be40` ≠ 0, Stufe nicht gemessen (`_m249/_haltfolge.txt:80-93`).
- `scripts/m212_zeilen.py:288-301` fährt den A4-Lauf immer über volle 900M Schritte, ohne Abbruch am Halt.
- ZWISCHENPRÜFUNG (gilt nach B250, Reviewer-Präzisierung, keine Umdefinition): „Über 8001684C hinaus“ = alle drei Bedingungen zugleich:
  - `be40` gibt 0 zurück (gemessen),
  - der Frame-Treiber nimmt bei 800167a4 bzw. 800167d0 NICHT den Fehlerweg,
  - der Halt-PC der Preflight-Zeile `Hybrid-A4` ist ≠ 8001684C.
  Sonst geht es nach B250 zurück zu C, und B ruht.

ARBEITSWEISE:
- Startroutine nach `AGENTS.md`. Zusätzlich: laufende `hybrid_lauf`- und `python`-Prozesse auflisten (nur melden, nicht beenden).
- Hintergrundläufe und Warteaufrufe (`Start-Process`, `run_in_background`, `Wait-Process`, `Start-Sleep`) sind verboten (R13aj).
  - Jeder Hybrid-, Preflight- und Build-Lauf ist blockierend mit `timeout=1800000`.
  - Ein Hybrid-Lauf, der voraussichtlich länger als 25 min dauert, wird nicht gestartet. Stattdessen die Stopp-Schalter aus TEIL 1 benutzen.
- Reihenfolge: TEIL 0 und TEIL 2 (ohne `port/`-Änderung) → Vorhersage-Commit `B250: Vorhersage` → erst dann `port/`- und `scripts/`-Änderungen.
- Die Vorhersage nennt:
  - Sekunden je Teilschritt des Preflights (`Hybrid-Lauf` mit Zwischenspeicher-Treffer),
  - Text und Werte der A4-Zeile,
  - Rückgabewert von `be40` nach jeder Behebung.
- Was behoben werden darf (wie in B249):
  1. eine Befehlsform mit `m227 gruen` Abw 0 und ROT gewordener Rotprobe;
  2. eine Proxy- bzw. Voodoo-Antwort mit ROM-Leser-Adresse und MAME-`Datei:Zeile` (`voodoo.cpp`, `voodoo_regs.h`, `k033906.cpp`, `konppc.cpp`, `hornet.cpp`), mit Rotprobe, markiert „Hybrid-Geruest, im Port zu ersetzen“.
- NEU: Ein Halt auf einem Fehlerweg ist nicht „nicht behebbar“. Er wird bis zur ersten fehlschlagenden Prüfung zurückverfolgt (Rückgabe-Sonde aus TEIL 1).
- Eigene Entscheidungen als `ENTSCHEIDUNG (Worker): …`.
- Werkzeug und Fortschritt im selben Batch sind hier ausdrücklich erlaubt (Reviewer-Entscheid). Die Wirkung von TEIL 1 wird deshalb getrennt belegt, bevor TEIL 3 beginnt.

TEIL 0 - Ablage der Rohdateien (M249-6):
- Für `_m249/_a4_an.txt` und `_a4_aus_err.txt`: Größe, SHA-256 und einen Kurzauszug (Kopf, Meldezeilen, Haltzeilen; höchstens 200 Zeilen) als `_m249/_a4_an_auszug.txt` committen.
- Die Rohdateien kommen in `.gitignore`. Neue Regel im Anker unter „Fallstricke/Regeln“: Rohläufe über 20 MB heißen `*_roh.txt`, sind ignoriert und werden durch Auszug + SHA-256 belegt.
- Nichts löschen.

TEIL 1 - Hybrid-Lauf schneller und zwischenspeicherbar (M249-2), Wirkung belegen:
- `hybrid_lauf`:
  - Schalter `--stopp-bei-halt`: Ende beim ersten Eintritt in den echten Halt bzw. Selbstsprung, mit identischen Meldezeilen.
  - Schalter `--stopp-bei-pc <adr>`: Ende beim n-ten Erreichen der Adresse.
  - Schalter `--rueckgabe-sonde <adr,…>`: protokolliert r3 und den Schritt bei jedem `blr` der genannten Funktionen.
- `m212_zeilen.py` (A4):
  - nutzt `--stopp-bei-halt`;
  - legt das Ergebnis in einem Zwischenspeicher ab, Schlüssel = SHA-256 von `hybrid_lauf.exe` + argv + Kalibrierdatei;
  - meldet in der Zeile „Zwischenspeicher Treffer/neu“.
- Wirkungsbeleg in `analysis/_m250/_a4_werkzeug.txt`:
  - (i) A4-Werte (Halt-PC, Schritte, nativ) mit und ohne `--stopp-bei-halt` gleich;
  - (ii) Laufzeit vorher und nachher;
  - (iii) Rotprobe des Zwischenspeichers: Binärdatei geändert → „neu“, unverändert → „Treffer“.
- Die Sekunden je Teillauf der Gruppe `Hybrid-Lauf` (200M, 20M, A4) werden einzeln gemessen und ins Dokument geschrieben.

TEIL 2 - `be40` statisch (M249-3), vor der Vorhersage:
- Tafel `analysis/_m250/_be40_stufen.txt`: jeder Rückgabepfad von `FUN_8000be40` (Adresse → Code → aufgerufene Funktion → Bedingung).
- Ebenso die Fehlercodes von `FUN_8000ab0c` und seiner sieben Unterfunktionen (`80009ab4`, `80009964`, `80009810`, `800096ac`, `80009584`, `80009548`, `800093bc`) sowie von `FUN_8000a7f4`. Alles per `disassemble_function`.
- Den Widerspruch zu `analysis/bucket-f2-2026-09-16.md:85@846c3d9` (ab90(3) → ab0c(5)) gegen B249 (8000bf04→5, 8000bf14→7) im B250-Dokument auflösen. Das alte Dokument bleibt unverändert.
- Für jede Unterfunktion: welche Proxy-Adressen sie liest und welche Werte sie erwartet.

TEIL 3 - Fehlerstufe messen und beheben (Schleife bis zur Umschaltschwelle):
- Lauf mit `--rueckgabe-sonde` auf `be40`, `ab0c`, dessen Unterfunktionen, `a7f4`, `a110`, `b048` und `--stopp-bei-pc` nach der Rückkehr von `be40` (800167a4). Das hält jeden Durchgang kurz.
- Je Durchgang eine Zeile in `analysis/_m250/_haltfolge.txt`: Durchgang | `be40`-Rückgabe | erste fehlschlagende Funktion + Code | fehlschlagender Vergleich (Adresse, erwarteter Wert laut ROM, gelieferter Wert) | Behebung + MAME-Beleg | Rotprobe.
- Liefert `be40` 0: einen vollen A4-Lauf mit `--stopp-bei-halt` fahren und den neuen Halt-PC, die Art und das Disassembly der Haltstelle nennen.

TEIL 4 - A4-Zeile ehrlich beschriften (M249-1):
- In `m212_zeilen.py` heißt der Teil `davon nativ` künftig „Anteil nativ NICHT GEMESSEN (Kalibriersumme B231: 1511)“. Die Zahl der Rufe ohne Kalibrierwert bleibt stehen.
- Die Bilanz darf eine Änderung dieser Zeile nicht als Fortschritt beim nativen Anteil führen. Im Dokument steht ein Satz dazu.

TEIL 5 - Abschluss und Ergebnis der Zwischenprüfung:
- Genau ein gültiger Preflight (`_preflight_250.txt`), blockierend; mit Zwischenspeicher-Treffer Soll < 900 s.
- Bilanz, Memory-Export, Commit, Baum leer (`git status --porcelain` leer).
- Ankerkopf:
  - Zeile „Zwischenprüfung: B248 Formlücke (8000A164); B249 8001684C, be40 ≥7; B250 [be40-Rückgabe, Halt-PC] → ERGEBNIS: über 8001684C hinaus JA/NEIN (drei Bedingungen einzeln)“.
  - Bei NEIN unter „Nächster Schritt“: „C-Batch B251 (Nutzerentscheid: B ruht bis Ende der ausgeführten Menge); zuerst M249-4 (Preflight-Zeile referenzgleiche Insn), M249-5 (Ersatzzahl in `m242`), `m53_pool.py:100`“.
  - Bei JA: „Planfrage bis zum ersten Attract-Bild an den Nutzer (Stationen, Batch-Schätzung, Abbruchkriterium)“.

TEIL 6 - Übrige Formlücken (streichbar):
- Die 9 Formen aus `_m249/_formluecken.txt` (a), die der Kern nicht kann, nach Regel 1 einbauen: `m227 gruen` + Rotprobe je Form.

FERTIG WENN: `_a4_werkzeug.txt` belegt (i) gleiche Werte, (ii) Laufzeitgewinn und (iii) Zwischenspeicher-Rotprobe + `_be40_stufen.txt` mit aufgelöstem Widerspruch 5/7 + `_haltfolge.txt` mit gemessener `be40`-Rückgabe und erster fehlschlagender Funktion (bzw. `be40` = 0 und neuer Halt-PC) + A4-Zeile mit „NICHT GEMESSEN“ + genau ein gültiger Preflight unter 1800 s, blockierend + Bilanz + Ankerkopf mit dem Ergebnis der Zwischenprüfung + leerer Baum.

STREICHREIHENFOLGE:
- Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat, mit einer `Get-Date`-Zeile im Dokument.
- Reihenfolge:
  1. TEIL 6
  2. weitere Durchgänge in TEIL 3 über den ersten Behebungsversuch hinaus
  3. TEIL 4
- NIE: TEIL 0, TEIL 1 samt Wirkungsbeleg, TEIL 2, erster gemessener Durchgang TEIL 3, Vorhersage, Preflight, Bilanz, Memory-Export, Ankerkopf mit Ergebnis der Zwischenprüfung.

## NACHRUECKLISTE
1. Werkzeug. FERTIG WENN: `_m250/_a4_werkzeug.txt` belegt (i) gleiche A4-Werte, (ii) Laufzeit vorher/nachher und (iii) Zwischenspeicher-Rotprobe Treffer/neu.
2. Statik be40. FERTIG WENN: `_m250/_be40_stufen.txt` mit allen Rückgabepfaden und aufgelöstem Widerspruch 5/7 liegt vor.
3. Messung. FERTIG WENN: `_m250/_haltfolge.txt` nennt die gemessene `be40`-Rückgabe und die erste fehlschlagende Funktion mit Vergleich (oder `be40` = 0 und neuen Halt-PC).
4. Abschluss. FERTIG WENN: gültiger `_preflight_250.txt` (blockierend, < 1800 s) + `_m250/_bilanz.txt` + Ankerkopf mit Ergebnis der Zwischenprüfung (drei Bedingungen) + leerer Baum.
5. Ablage. FERTIG WENN: `_m249/_a4_an_auszug.txt` mit SHA-256 committet, Rohdateien in `.gitignore`, Regel im Anker.
6. A4-Beschriftung. FERTIG WENN: die Preflight-Zeile trägt „Anteil nativ NICHT GEMESSEN“.
7. Formlücken. FERTIG WENN: die 9 Formen haben `m227 gruen` + Rotprobe, oder es steht mit `Get-Date` im Dokument, dass sie wegen der Schwelle gestrichen wurden.
