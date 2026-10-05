**Review B264:** Das FERTIG WENN ist nur teilweise erreicht. Gemessen ist viel:
- 1680 Bilder bis 900M und 2776 weitere bis 1800M, alle mit nur einem Block.
- Die Ursache dafür: `state+0xC = -1`, deshalb läuft die Szenen-Pipeline nie an.
- Die Intro-Kette des Betriebsmodus friert beim Unterzustand `c=2` ein (`_m264/_intro.txt`).

Die Blockade „ohne MAME-Aufzeichnung nicht entscheidbar“ ist aber falsch. `FUN_800261C4` und seine Unterhandler sind im Port nativ gebaut und dokumentiert (`port/include/port/opmode.h:60-61`, `port/src/opmode_screens.cpp:80-107`). Die Grep-Pflicht ist zum dritten Mal an `port/` gescheitert.

Die Aussensicht hat außerdem recht: Die Bildreferenz stammt aus einem Savestate mit Eingabe-Wiedergabe, nicht aus einem Kaltstart. Der Präfix taugt deshalb vorerst nicht als Stationsmaß. Der Stillstandszähler steht auf 3 von 4. B265 nutzt die native Port-Logik als Orakel und baut die erste echte Maßnahme.

<TELEGRAM_SUMMARY>
Ergebnis:
- Volle Bildsuche bis 1800M: alle Bilder 1 Block, Präfix höchstens 25.
- Ursache gemessen: `state+0xC = -1` in allen Bildern, die Szenen-Pipeline (`FUN_80017674`) läuft nie.
- Die Intro-Kette friert bei `c=2` ein, `e` bleibt nach Schritt 346149393 stehen (`_m264/_intro.txt:11-28`).
Bewertung:
- Befund: Die Blockade „ohne MAME-Aufzeichnung nicht entscheidbar“ ist falsch. `FUN_800261C4` und die Unterhandler sind nativ im Port dokumentiert (`port/include/port/opmode.h:60-61`, `port/src/opmode_screens.cpp:80-107`). Die Grep-Pflicht scheiterte zum dritten Mal an `port/`.
- Die Bildreferenz ist ein Savestate mit Eingabe-Wiedergabe, kein Kaltstart (`capture/inp/README.md:6-12`).
FERTIG WENN erreicht: teilweise. (d) Maßnahme fehlt, die Stopp-Bedingung ist unbegründet.
Kosten/Laufzeit: 0,254 $, 131 min, 154 Anfragen.
Nächster Batch: Port-`opmode` als Orakel für `c=2`, die erwartete Bedingung modellieren, Kaltstart-Referenz suchen.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 35 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M264-1: übernommen als B265 TEIL 1 + Grep-Pflicht je Funktion der Kette - offen
M264-2: übernommen: Stationszähler = Maß der B-Phase, Anteil nativ = Zielmaß, das in reiner B-Phase nicht steigt (Anker) - offen
M264-3: übernommen als B265 TEIL 0c - offen
M264-4: übernommen: Präfix zählt nur noch gegen eine Kaltstart-Referenz, Suche in B265 TEIL 4 - offen
M264-5: übernommen als OFFENE FRAGE (Harness-Code liegt außerhalb des Repos) - offen
M264-6: übernommen als B265 TEIL 0b - offen
UEBERTRAG: B264 N4/N6 Maßnahme -> B265 TEIL 2/3
ENTSCHIEDEN: B264 ist keine Station, Stillstandszähler 3 von 4. Ohne Station in B265 geht die Frage „B weiter oder C“ an den Nutzer.
ENTSCHIEDEN: An der Schranke zählt als Station auch ein belegter neuer Zustand der Betriebsmodus-Kette durch eine Kern- oder Modelländerung.
OFFENE FRAGE: Die Mischrechnung im Harness (`hx/stand.py`) widerspricht sich selbst („0 von 2 = 31 %“, Befund M264-5). Sie ist nur außerhalb des Repos zu korrigieren.
WARTET AUF LIVE-AUFNAHME: Kaltstart-MAME-Log mit `cgboard_dsp_shared_w_ppc` bis zum ersten Attract-Bild, falls TEIL 4 keines findet.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Die Grep-Pflicht ist zum dritten Mal an `port/` gescheitert** (0x40000000, `gun_input`, jetzt `opmode`).
- (a) Fehlerklasse: Gesucht wurde nur nach dem Halt-PC bzw. in `capture/`, nicht nach jeder Funktion der Aufrufkette.
- (b) Verwandte Fälle: jede Kette mit Dispatcher bzw. Unterhandlern. Prüfung in der Instruktion: Tafel `_m265/_kette_grep.txt` mit **jeder** Funktion der Kette (`FUN_80026C34`, `FUN_80025CDC`, `FUN_80026718`, `FUN_800261C4` + Unterhandler, `FUN_80026538`) und je einer Grep-Zeile über `port/` und `analysis/` mit Treffern. Ohne diese Tafel gilt eine Blockade nicht.
- (c) Nicht geprüft: ob der Port-Automat in allen Zweigen referenzgleich ist. Er dient als Orakel und ist selbst nicht gegen MAME belegt.

**F2: Referenz mit anderem Anfangszustand** (Savestate plus Wiedergabe gegen Kaltstart).
- (a) Fehlerklasse: Vergleichsbasis nicht gleichgesetzt, wie schon F3 in B262.
- (b) Prüfung in TEIL 4: Jede Referenz bekommt eine Zeile zu ihrem Anfangszustand (Kaltstart, Savestate, Eingaben) mit Fundstelle. Eine Präfix-Station zählt nur gegen eine Kaltstart-Referenz.
- (c) Nicht geprüft: SHARC- und Board-1-Anteile der Referenz.

**F3: „Code-Commit nach gültigem Preflight unzulässig“** (falsche Regelauslegung, B264 Hinweis).
- (a) Fehlerklasse: veraltete Regel. Seit R13bf ist ein neuer Preflight zulässig, der letzte gilt.
- (b) Prüfung: Der Auftrag nennt die Regel ausdrücklich.

**F4: Etiketten am nativen Anteil, zum vierten Mal** (M264-3).
Die Instruktion verlangt die Umbenennung in der Quelle (`hybrid_lauf.cpp`, `m149_bilanz.py`). Ich prüfe die Preflight-Zeilen 30 und 32 im nächsten Review wörtlich.

<DS_INSTRUCTION>
Batch 265 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 36. **Stillstandszähler 3 von 4.** Ohne Station in diesem Batch geht die Frage „B weiter oder C“ an den Nutzer.
Vorgabe: `Hybrid-A4 900000000 | 80008448 | Schranke` (`analysis/_preflight_264.txt:32`, HEAD `4fb379b`).
B264 (`analysis/port-batch264-b-attract-bild-state-2026-10-04.md`, `_m264/`):
- Alle Bilder bis 1800M haben 1 Block, `state+0xC = -1`, die Szenen-Pipeline läuft nie.
- Betriebsmodus `opmode = 0` (`FUN_80025CDC`). Unterphase `c`: `0→1→2`. Zähler `e` (`cfg+0x1E`) schreibt nur `80026748` (Werte 1..6, zuletzt Schritt 346149393). Danach bleibt `c=2` stehen (`_m264/_intro.txt:11-28`, Basis `0x800AE378`: `+0x1A`/`+0x1C`/`+0x1E`/`+0x2C`).
- Abzug bei 900M: `analysis/_m264/_abzug_900m.bin` (gitignoriert; fehlt er, neu erzeugen).
**Fehlstelle geklärt (R13az, Befund M264-1):** Die Kette ist im Port nativ beschrieben und gebaut:
- `port/include/port/opmode.h:14,48,60-61,99,115`: `FUN_80026718` hat 5 Init-Schritte, `FUN_800261C4` ist der Dispatcher mit 32 Unterhandlern.
- `port/src/opmode_screens.cpp:80-107`: Statusschirm `FUN_80026538`, wartet auf IN2 Bit 4.
- `analysis/port-batch88b-nutzlast-2026-09-21.md:102-113`: Handler setzen `cfg+0x1E` auf Schritt+1, 8, 16 oder −1.
- `port/include/port/opmode_check.h:24-25`.
Die B264-Blockade „nicht entscheidbar ohne MAME-Aufzeichnung“ ist aufgehoben.
**Referenz (Befund M264-4):** `poc_ref_boot_0..3` stammen aus einem Savestate plus Eingabe-Wiedergabe (`scripts/ppc_poc_frame_run.ps1:20-21`, `capture/inp/README.md:6-12`). Sie heißen ab jetzt „Savestate-Referenz“.
ENTSCHEIDUNG (Reviewer): Solange `Hybrid-A4` an der Schranke endet, ist eine Station (a) ein Halt mit Halt-Art ≠ Schranke, (b) ein belegter neuer Zustand der Betriebsmodus-Kette (`opmode`/`c` über den B264-Stand hinaus) oder (c) ein gewachsener Präfix gegen eine **Kaltstart**-Referenz. Jeweils durch eine Kern- oder Modelländerung, mit Vorgabe EIN und im gültigen Preflight. Ein Schranken-PC, der sich ohne Kern- oder Modelländerung verschiebt, zählt nicht.
ENTSCHEIDUNG (Reviewer, M264-2): In der B-Phase ist der Stationszähler das Fortschrittsmaß (Nutzerentscheid 03.10.). `Anteil nativ (Schatten)` bleibt das Zielmaß und wird je Batch berichtet; in reiner B-Phase steigt es nicht.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` = `scripts/hooks` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B265: Vorhersage` VOR jedem `port/`/`scripts/`-Diff, mit Sollwert und Zählerdefinition je Bilanzzeile sowie der Vorhersage, worauf der Handler bei `c=2` wartet.
- **Grep-Pflicht je Funktion der Aufrufkette** (nicht nur am Halt-PC), über `port/`, `analysis/`, `capture/`, `mame/mame/src/`. Ergebnis in der Tafel `_m265/_kette_grep.txt`, eine Zeile je Funktion mit Treffern. Ohne diese Tafel gilt keine Blockade.
- „Maßnahme“ heißt Änderung unter `port/hybrid/` (Kern oder Modell) mit Gegenschalter, ROM- und MAME- bzw. Port-Beleg. Die Rotprobe nimmt die Änderung zurück und zeigt den alten Zustand. Je Maßnahme ein eigener Commit.
- **Nach einem Preflight sind weitere Arbeiten unter `port/` und `scripts/` erlaubt (R13bf).** Danach folgt ein neuer Preflight, der letzte gilt. Das ist kein Grund, den Batch zu beenden.
- Der Batch endet nicht vor der Umschaltschwelle, außer mit belegter Stopp-Bedingung nach der Tafel oben.
- Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert gesichert. Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe.
- Belege als `Datei:Zeile@commit`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_265.txt`.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. (M264-6) In `analysis/hybrid-plan.md` die Nutzerklarstellung vom 03.10.2026 wörtlich eintragen (Quelle `runs/b260/review.md` bzw. Anker): Schwelle 4 B-Batches ohne Station, Zähler neu ab jeder Station. Dazu die Stationsregel aus STAND UEBERNEHMEN. Die alte Zeile mit der Schwelle 3 (`hybrid-plan.md:249-250`) als überholt kennzeichnen.
0c. (M264-3) Feldnamen in der Quelle: Die Ausgabe `native_ersetzt` im Lauf ohne Schatten heißt `Kalibriersumme` (`port/hybrid/hybrid_lauf.cpp`, Stelle per Grep). Die Preflight-/Bilanzzeile `Hybrid-Anteil nativ 57819/200000000` heißt `Hybrid-Anteil nativ (200M-Probe, nicht A4)` (`scripts/m212_zeilen.py`, `scripts/m149_bilanz.py`). Eigener Commit.

TEIL 1 - Port-Orakel für `c=2` (M264-1):
1a. Tafel `_m265/_kette_grep.txt` (siehe ARBEITSWEISE).
1b. Aus dem Abzug bei 900M bzw. dem `--state4-log` den Zustand bei `c=2` auslesen: `cfg+0x1A/0x1C/0x1E/0x20/0x2C`, IN2, den aktiven Unterhandler (Index = `e`, Tafel `r2+0x830`), seine Schleifen- bzw. Wartebedingung (Ghidra plus Port-Code).
1c. Orakel: Den nativen `port::OpMode`-Automaten auf denselben RAM-Zustand setzen (kleiner Treiber unter `scripts/` oder ein Selbsttest-Fall, Fundstelle `port/src/opmode*.cpp`) und einen Schritt rechnen. Ergebnis: was der Port an derselben Stelle liest und schreibt, gegen den Hybrid-Zustandslog. Ergebnis `_m265/_orakel.txt` mit der erwarteten Bedingung (z. B. IN2-Bit, Sicherungsdaten/EEPROM, Timer, Gerätezustand) und Fundstelle.

TEIL 2 - Maßnahme:
2a. Die erwartete Bedingung im Hybrid modellieren (Eingabe-Attrappe mit Flanke, Sicherungsdaten, Gerätezustand …): Gegenschalter, Port- bzw. MAME-Beleg, eigener Commit.
2b. Wirkung im Vorgabe-Lauf (Wanduhr ≤ 1500): Verlauf von `opmode`/`c`/`e` und Blockzahl je Bild vor und nach der Maßnahme. Rotprobe: Gegenschalter → `c=2` bleibt stehen.
2c. Neuer Kettenzustand → Vorgabe EIN nur mit zwei gleichen A4-Läufen unter 1500 s. Dann Vorwärmung und Preflight; die Station gilt nach Regel (b).

TEIL 3 - Iteration (offener Posten):
Nächster Wartepunkt der Kette bzw. der nächste Halt → Orakel bzw. Grep-Tafel → Maßnahme → Rotprobe → Commit, bis zur Umschaltschwelle oder zu einer belegten Stopp-Bedingung. Ziel ist, dass `FUN_80025B7C` (Szenenaufbau, Betriebsmodus 2) bzw. `FUN_80017674` läuft und die Blockzahl > 1 steigt.

TEIL 4 - Kaltstart-Referenz suchen (M264-4):
In `capture/` je Log mit `cgboard_dsp_shared_w_ppc` den Anfangszustand bestimmen (Kaltstart, Savestate, Wiedergabe; Fundstellen: Skripte, Kopf der Logs, README). Kandidaten u. a. `error-attract-20260828-015654.log`, `error-20260828-013421.log`, `error_boot_f*.log`. Tafel `_m265/_referenzen.txt`. Gibt es eine Kaltstart-Log mit Bildmarken: Referenz mit Schreib-PCs wie in B263 erzeugen und Bildsuche fahren. Gibt es keine: im Anker als `WARTET AUF LIVE-AUFNAHME` führen (Kaltstart-MAME-Log mit `cgboard_dsp_shared_w_ppc` bis zum ersten Attract-Bild).

TEIL 5 - Abschluss:
Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 265 --from-preflight analysis/_preflight_265.txt --write-anchor` (nie durch eine Pipe). `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt` als Auszug ins Dokument.
Ankerkopf B265 mit:
- Preflight-HEAD aus Zeile 3,
- Stationszeile nach der Regel oben,
- Stillstandszähler (4 von 4 ohne Station, dann ausdrücklich „Frage B oder C an den Nutzer fällig“),
- Kettenzustand vorher/nachher,
- Referenztafel,
- „Nächster Schritt“ mit Batch-Nummer 266.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B265: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) `_m265/_kette_grep.txt` mit jeder Funktion der Kette; (b) `_m265/_orakel.txt` mit der Wartebedingung bei `c=2` und Port-Fundstelle; (c) mindestens eine Maßnahme unter `port/hybrid/` mit Gegenschalter, Rotprobe und eigenem Commit sowie Kettenzustand vorher/nachher; (d) `_m265/_referenzen.txt` mit Anfangszustand je Referenz; (e) Feldnamen aus 0c in der Preflight-Zeile; (f) gültiger Preflight + Bilanz, Aufräumen, Ankerkopf mit Stationszeile; (g) kein Batch-Ende vor der Umschaltschwelle ohne belegte Stopp-Bedingung.

STREICHREIHENFOLGE: 1. TEIL 4 über die Tafel hinaus (Referenzbau), 2. TEIL 2c (Vorgabe EIN), 3. TEIL 0b. NIE: Vorhersage-Commit, TEIL 0c, TEIL 1a-1c, TEIL 2a-2b, Tafel aus TEIL 4, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1a/1b Grep-Tafel und Zustand; FERTIG WENN: `_m265/_kette_grep.txt` und Zustand bei `c=2` (cfg-Felder, IN2, Unterhandler) committet.
2. TEIL 1c Orakel; FERTIG WENN: `_m265/_orakel.txt` mit dem, was der Port-Automat an derselben Stelle liest und schreibt, und der Wartebedingung mit Fundstelle.
3. TEIL 2a/2b Maßnahme; FERTIG WENN: Commit unter `port/hybrid/` mit Gegenschalter, Rotprobe (`c=2` bleibt), Verlauf `opmode`/`c`/`e` und Blockzahl vorher/nachher.
4. TEIL 0c + TEIL 4 Tafel; FERTIG WENN: Preflight-Zeilen mit `Kalibriersumme` und `(200M-Probe, nicht A4)`, `_m265/_referenzen.txt` mit Anfangszustand je Referenz.
5. TEIL 5 Abschluss; FERTIG WENN: gültiger Preflight, Bilanz, Aufräumauszug, Ankerkopf mit Stationszeile und Stillstandszähler.
6. Offener Iterationsposten (TEIL 3 + 2c + 0b); FERTIG WENN: `Get-Date`-Zeile zeigt die Umschaltschwelle erreicht, oder belegte Stopp-Bedingung mit Grep-Tafel über jede Funktion der Kette.
</DS_INSTRUCTION>
