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
Batch-Start (Harness-Zeitstempel): 17:07:02 Ortszeit am 2026-10-03
  - Die exakte Messung ist die BATCH-UHR-Zeile im Verlauf (Prozessstart des Workers); dieser Zeitstempel liegt wenige Sekunden davor.
Aktuelles Ghidra-Programm (vom Harness gestellt): /830d01.27p.main.bin
  - main.bin = PPC-Hauptprogramm (Base 0x80000000) - das Arbeitsprogramm.
  - be.bin = Boot-/Loader-Image - nur bei Aufträgen zum Ladepfad.
  - Ein anderes Programm NICHT selbst stellen: PROGRAM_REQUEST melden.

=== AUFTRAG (vom Reviewer) ===
Batch 256 - Silent Scope Decomp

STRANG: B
STAND UEBERNEHMEN:
Strang B, B-Batch 27, **Serie „spielbare Beta“ Batch 2 von 8** (Nutzerentscheid 03.10.2026; die Serie begann mit B255; B251–B254 waren C-Batches und zählen nicht). C ruht.
Fortschritt zählt nur, wenn sich der echte Halt-PC bei unveränderten Schaltern ändert. Heute: `8001684C`, Selbstsprung, 696571792 Schritte. Den Halt nicht umdefinieren.
Ursache aus B255 (CONFIRMED, `analysis/port-batch255-b-hybrid-mailslot-2026-10-03.md` §3-§4, `_m255/_sharc_auszug.txt`): Beim zweiten `c3a8`-Austausch steht der Folgenindex auf 4791 statt auf dem Zählerbeginn 4798. `b3c4` bricht nach 6 Runden ohne Bit7-Wechsel ab (`lis 0x2000`). Der Fix `sharc_exchange_start` richtet die Folge am Austausch-Eintritt `8000C3E8` auf den nächsten Zählerbeginn aus. Er wurde gebaut und zurückgenommen, sein Code steht nur beschrieben in §4. Mit Fix hielt der A4-Lauf nach >3096 s CPU nicht. Der 216,6M-Lauf mit Fix brauchte 31 min (ohne Fix ~90 s), das ist ungemessen.
Nutzerauftrag 03.10. 12:51: Der Zustandsabzug vor `be40` hat Priorität gleich nach der Mailslot-Messung. Ziel: Diagnose- und Kontrolllauf bis zum Halt in unter 5 Minuten. Die Wirkung wird gemessen: Laufzeit vorher und nachher, gleicher Halt-PC und gleiche Schrittzahl.
SOLL-KOEPFE: 0

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. Zusätzlich `Get-Process hybrid_lauf,python` notieren: Prozesse aus B255 nennen, nicht stoppen (Fremdlast im Bericht).
- Vorhersage-Commit `B256: Vorhersage` VOR dem ersten `port/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition. Messvorhersagen: Schrittrate je Schalter, Abzug-Schritt S, Kontrolllaufzeit, `be40`-Rückgabe mit Fix.
- Belege `Datei:Zeile@commit`. Skripte nur unter `scripts/`. Rohläufe über 20 MB heißen `*_roh.txt` (R250).
- **Lange Läufe:** nur blockierend mit `timeout=1800000`. **Verboten:** `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen (B255 hat das so gemacht, das ist ein Verstoß gegen R13aj). Ein Lauf, der 1800 s nicht schafft, ist ein Befund mit gemessener Rate und wird verkürzt (Abzug, Schrittgrenze), nicht ausgelagert.
- **A4-Zwischenspeicher:** Cachedateien schreibt nur `scripts/m212_zeilen.py`/`m254_prewarm.py`. Kopieren, Umbenennen und Anlegen von Hand ist verboten (B255 hat die B254-Datei kopiert; die B255-A4-Zeile ist deshalb keine Messung).
- Preflight-Aufruf als einzige Zeile: `python -u scripts/preflight.py before *> analysis/_preflight_256.txt`. Die Ausgabe wird in einem eigenen Folgeaufruf gelesen. Wird der Aufruf vom Harness abgelehnt, steht der Ablehnungstext wörtlich im Batch-Dokument.
- **Klartext (M255-5):** Der Harness-Satz „Kein neuer Preflight nötig, der vorhandene gilt“ ist eine Zustandsmeldung, kein Verbot. Weitere Arbeit unter `port/` und `scripts/` ist nach einem Preflight erlaubt; danach folgt ein neuer Preflight, der letzte gilt (R13bf).
- „Blockiert“ nur mit Beleg: Zitat der Auftragszeile mit `Datei:Zeile`, bei „fehlt“ ein Grep auf den Bezeichner. Laufzeit und Preflight-Dauer sind keine Blockade. Der Batch endet nicht vor der Umschaltschwelle der Batch-Uhr, solange Posten offen sind. Streichen nur mit `Get-Date`-Zeile.
- Modelle als „Hybrid-Gerüst, im Port zu ersetzen“, mit ROM-Beleg (Entscheidung B234). Kein `disassemble_bytes` (R398). Benutzte Ghidra-Werkzeuge im Bericht nennen.
- Verbote: kein Force-Push, keine Historie umschreiben, keine Belege löschen, kein `restore_project`, keine Änderung der AGENTS-Grundregeln.

TEIL 0 - Klein, vorab:
0a. **Schrittraten je Schalter**: je 20M Schritte ohne Zusatzschalter, mit jedem A4-Schalter einzeln (`--nativ-weiter`, `--ohne-schatten`, `--sharc-antwort`, `--stopp-bei-halt`, `--pcs`, `--kalibrierung`) und mit allen zusammen (A4-argv, `scripts/m212_zeilen.py:468-471@HEAD`). Tafel Schritte/s. Bezug B250: 200M in 81,4 s gegen A4 696M in ~1730 s.
0b. **Schlüsselursache B255**: die Bausteine von `_cache_key` (`scripts/m212_zeilen.py:420-436@HEAD`) einzeln für den jetzigen Stand ausgeben, je Hybrid-Quelldatei Roh-SHA und SHA nach LF-Normalisierung, und gegen die B254-Werte vergleichen (`_m254/_a4_werkzeug.txt:12-17`: Quellen `cb6486b3d069ab05`, Körper `85c9d5173a831df5`). Den abweichenden Baustein benennen. Ist es das Zeilenende, wird der Fix des Schlüssels erst in TEIL 1d gebündelt (ein kalter Lauf).
0c. **Zählung (M255-2)**: Im Anker und im B-Bericht zählen nur Batches mit Strang B: B248, B249, B250, B255, B256. Stationen: 1 (B248). Rechenbasis „B-Batches je Station“ neu ausrechnen. Die Ankerzeile „7 von 8“ berichtigen und die Schwelle „8 B-Batches der Serie ohne neue Station“ ab B255 zählen.

TEIL 1 - Zustandsabzug (Nutzerpriorität):
1a. Abzug bei einem Schritt S, der vor dem ersten Punkt liegt, an dem der Fix wirken kann: vor dem ersten Eintritt `8000C3E8`, oder später mit Beleg „Zustand bei S mit Fix gleich ohne Fix“ (Hash über Register, RAM und Gerätezustand). Der Abzug enthält alles, was der Lauf braucht: Kern, RAM, Gerätemodelle, Folgenindex, `pending`, Zeitbasis, Zähler. Ablage gitignoriert unter `port/build/`; im Beleg stehen Größe und SHA.
1b. **Gegenprobe**: Lauf ab Abzug bis zum Halt mit A4-Schaltern. Soll: Schritte 696571792, Halt-PC 8001684C, Halt-Art Selbstsprung, `nativ_bis_dahin 1511`, alles identisch zur B254-Zeile. Laufzeit vorher und nachher messen. Ziel unter 5 min. Wird das Ziel verfehlt, die Ursache aus den Raten in 0a benennen und z. B. reine Ausgabeschalter abtrennen. Die Zeile des Ergebnisses ändert sich dadurch nicht.
1c. Rotprobe: einen Abzug mit einem verfälschten Byte (z. B. Folgenindex +1) laden. Soll: eine abweichende Zeile.
1d. A4 und Preflight ab Abzug: `m212` startet den A4-Lauf aus dem Abzug, falls 1b gleich ist. Der Schlüssel umfasst den Schlüssel des Abzugs und, falls 0b es zeigt, die LF-normalisierten Quellen. Die Cachedatei trägt den Schlüssel des Erzeugerlaufs; der Preflight meldet eine Abweichung als Befund (M255-4). Danach eine Vorwärmung blockierend und unter 1800 s. Ist 1b ungleich, wird 1d nicht gebaut und die Abweichung mit Schritt und PC belegt.

TEIL 2 - Fix ab Abzug messen (M255-1):
2a. `sharc_exchange_start` nach Dokument §4 neu bauen, Schalter `--sharc-handschlag`, **vorerst Vorgabe AUS**. Schrittrate mit Fix gegen ohne Fix über 20M Schritte ab Abzug. Läuft der Fix langsam: Ursache benennen (Suchschleife über Zählerbeginne? In der Folge gibt es nur [0, 4798]).
2b. Kurzlauf ab Abzug mit `--stopp-bei-pc` hinter dem zweiten `be40`-Ruf. Soll mit Fix: `c3a8` = 0, `be40` = 0. Rotprobe: ohne Fix 2 und 0x20000000 (B250-Werte).
2c. Lauf ab Abzug mit Fix bis Halt oder 900M Schritte, blockierend. Berichte Halt-PC, Halt-Art und Schritte, oder bei 900M ohne Halt das PC-Histogramm der letzten 10M Schritte und die erste fehlschlagende Prüfung danach (Dreischritt: Vergleich, erwartet gegen geliefert, Ursachenklasse). Gibt es einen dritten `c3a8`-Austausch ohne Zählerbeginn in der Folge, ist das eine eigene Zeile.
2d. Vorgabe EIN nur, wenn der A4-Lauf ab Abzug mit Fix in einen blockierenden Aufruf unter 1800 s passt. Dann Vorwärmung und Preflight; ein neuer Halt-PC in `Hybrid-A4` ist die **neue Station**. Passt er nicht, bleibt der Schalter AUS. Die Station wird dann als „Kurzlauf-belegt, A4 ausstehend“ geführt und zählt noch nicht. Die gemessene Rate steht dabei.

TEIL 3 - B-Bericht (Pflicht, Batch-Dokument und Ankerkopf):
aktuelle Station, nächste bekannte Station mit Beleg, Aufwandsschätzung mit ausgeschriebener Rechenbasis (nur B-Batches, 0c; HYPOTHESIS), „Serie k von 8, davon ohne neue Station m“. `Anteil nativ` steht als NICHT GEMESSEN, nicht als Fortschritt. Wirkung des Abzugs: Laufzeit vorher und nachher, gleicher Halt-PC und gleiche Schritte.

TEIL 4 - Doku und Bilanz:
Ankerkopf nach `AGENTS.md`, Memory-Export, danach `m149_bilanz.py --batch 256 --from-preflight analysis/_preflight_256.txt --write-anchor`; nach dem Preflight nichts mehr unter `scripts/` ändern. Abweichungen von der Vorhersage erklären.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen. `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse: >50 gelöschte Zeilen, dann melden). Ankerblock mit `UEBERTRAG:` und `GESCHLOSSEN`.

FERTIG WENN: (a) Tafel der Raten aus 0a und benannter Schlüsselbaustein aus 0b; (b) Abzug mit Gegenprobe 1b (696571792/8001684C/Selbstsprung identisch), Laufzeit vorher und nachher, Rotprobe 1c ROT; (c) Kurzlauf 2b mit Fix `be40` = 0 und Rotprobe ohne Fix = 2; (d) Ergebnis 2c (neuer Halt oder 900M mit Histogramm und erster fehlschlagender Prüfung); (e) kein Hintergrundlauf und keine kopierte Cachedatei; (f) ein gültiger Preflight (der letzte, „Zwischenspeicher Treffer“, Cache aus eigenem Lauf) + Bilanz; (g) B-Bericht mit Zählung nur aus B-Batches.

STREICHREIHENFOLGE: 1. Posten 6 (nativer Anteil), 2. Posten 5 (Formlücken), 3. TEIL 1d (A4 ab Abzug; dann bleibt der Fix-Schalter AUS), 4. TEIL 2c über das erste Ergebnis hinaus. NIE: Vorhersage-Commit, TEIL 1a-1c, TEIL 2b, Preflight, Bilanz, Memory-Export, TEIL 3.

## NACHRUECKLISTE
1. TEIL 1a-1c Zustandsabzug mit Gegenprobe und Rotprobe; FERTIG WENN: Kontrolllauf ab Abzug liefert 696571792/8001684C/Selbstsprung identisch, Laufzeit vorher und nachher stehen im Batch-Dokument, Rotprobe ROT.
2. TEIL 2a/2b Fix hinter Schalter, Rate und Kurzlauf; FERTIG WENN: `be40` zweiter Ruf = 0 mit Fix und = 2 ohne Fix, gemessen ab Abzug.
3. TEIL 2c Lauf mit Fix bis Halt oder 900M; FERTIG WENN: Halt-PC, Halt-Art und Schritte, oder Histogramm und erste fehlschlagende Prüfung mit Beleg.
4. TEIL 0 + TEIL 1d (Raten, Schlüsselursache, A4 ab Abzug mit Herkunftsvermerk der Cachedatei); FERTIG WENN: Preflight-Zeile `Hybrid-A4` stammt aus eigenem Lauf ab Abzug, Vorwärmung unter 1800 s blockierend.
5. Formlücken aus `_m249/_formluecken.txt` (`19/0, 19/150, 27, 29, 31/26, 31/163, 31/412, 31/597, 31/725`); FERTIG WENN: je Form „verifiziert oder offen mit Grund“, mindestens eine geschlossen.
6. Nativer Anteil (M255-3): Kalibrierwerte für die 195348 Rufe ohne Kalibrierwert (`_preflight_255.txt:32`) bzw. Schrittzählung des nativen Anteils im A4-Lauf; FERTIG WENN: `Hybrid-A4` nennt Schritte UND Anteil nativ als Messwert, oder Fehlstelle mit Grep und Grund.
