**Review B260:** Das FERTIG WENN ist nur teilweise erreicht, eine neue Station gibt es nicht. Belegt ist der Kernbefund: Das ROM steht in der Hauptschleife (`80008AA0`, erreicht bei Schritt 257110366, mit Gegenprobe). Es wartet auf das Flag `0x800AEC63`, und dieses Flag wird nur im externen Interruptweg geschrieben, also beim Vblank. Mit `--vblank` entsteht ein neuer Halt `800237B4`. Die Vorgabe bewegt sich aber nicht, deshalb ist die Ankerzeile „Station: ja“ falsch; der Stillstandszähler steht auf 1 von 4. Alle fünf Aussensicht-Befunde habe ich am Code bzw. Anker nachgeprüft und übernehme sie. B261 korrigiert zuerst einen Kernfehler bei den DCR-Registern und übernimmt dann die vorhandene Eingabe-Portierung für den neuen Halt.

<TELEGRAM_SUMMARY>
Ergebnis:
- Die Schleife ist `while(Flag)` in main `FUN_800089A0`, die Hauptschleife `80008AA0` wird bei Schritt 257110366 erreicht (Gegenprobe ergibt „nein“). Flag `0x800AEC63`, Schreiber ist der externe Interruptweg (Vektor 0x500), also IRQ0/Vblank.
- `--vblank` (Vorgabe AUS) führt zum neuen Halt `800237B4`, einer MMIO-Lesung.
- Schattenweg 2× schneller. Ein Schattenlauf 0..900M ergibt `nativ 1657319/900000000`.
- Die Abzug-Falle ist behoben.
Bewertung:
- Gute Analyse, aber keine Station: `Hybrid-A4` steht unverändert auf Schranke 8002B364. Der Anker schreibt trotzdem „Station: ja“.
- Kernfehler: Der DCR-Index wird ohne Halbtausch gebildet (`ppc_kern.cpp:408`). Das Löschen von EXISR greift deshalb nie, und das Vblank-Modell hat eine eigene Quittung erfunden.
- Der Halt `800237B4` liegt in `FUN_8002379C`, das im Port schon nativ existiert (`port/src/gun_input.cpp:464`). Der Worker hat das nicht gefunden.
- Wieder ein Sammelcommit. Abzugsläufe sind plötzlich ~16× langsamer, ungeklärt.
FERTIG WENN erreicht: teilweise. (g) Commit je Maßnahme nein, (f) Stationszeile falsch.
Kosten/Laufzeit: 0,184 $, 131 min, 116 Anfragen.
Nächster Batch: DCR-Fix, Eingabe-Attrappe aus dem Port, Vblank als Vorgabe zur Station, Bildweg beginnen (NIE streichen).
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 31 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M260-1: übernommen als B261 TEIL 5 - Wirkung noch nicht belegt -> bleibt offen
M260-2: übernommen als B261 TEIL 1, bestätigt an `ppc_kern.cpp:408-416` - Wirkung noch nicht belegt -> bleibt offen
M260-3: übernommen als B261 TEIL 2, bestätigt an `gun_input.cpp:464-473` - Wirkung noch nicht belegt -> bleibt offen
M260-4: übernommen als B261 TEIL 4 (NIE streichen) - Wirkung noch nicht belegt -> bleibt offen
M260-6: übernommen als B261 TEIL 0b - Wirkung noch nicht belegt -> bleibt offen
UEBERTRAG: B260 N5 Vorgabe EIN + weitere Halte -> B261 TEIL 2/3
UEBERTRAG: B260 N6 Bauweg Kommandostrom -> B261 TEIL 4
ENTSCHIEDEN: B260 ist keine Station, Stillstandszähler 1 von 4.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Kernfehler wird mit einem Modell umgangen statt im Kern behoben (DCR-Halbtausch, M260-2).**
- (a) Fehlerklasse: Die Feldlage beim Dekodieren ist falsch, hier das vertauschte 5/5-Bit-Feld bei `mfdcr`/`mtdcr`.
- (b) Verwandte Fälle: Jeder DCR-Zugriff mit einer Nummer, deren Hälften ungleich sind, z. B. BR0–7 (0x80–0x87), IOCR (0xA0), EXISR (0x40). Prüfung in TEIL 1: Eine Tafel aller DCR-Nummern, die das ROM benutzt (Suche nach `mfdcr`/`mtdcr`), mit Index alt und neu. Rotprobe: EXISR-Löschen wirkt. Gegenprobe: A4 vorher und nachher.
- (c) Nicht geprüft: die Semantik der übrigen DCRs über das Speichern hinaus.

**F2: Vorhandene Portierung nicht gefunden (`FUN_8002379C` in `gun_input`, M260-3), obwohl die Grep-Pflicht `port/` nannte.**
- (a) Fehlerklasse: gesucht wurde nur nach der Halt-PC, nicht nach der Funktionsadresse.
- (b) Verwandte Fälle: jeder Halt in einer Funktion, die im Port nativ vorliegt. Prüfung: Je Halt ein Grep auf die Funktionsadresse in Groß- und Kleinschreibung über `port/` (inklusive `port/src`, `port/include`). Der Treffer bestimmt die Quelle des Modells.
- (c) Nicht geprüft: ob die Ruhewerte aus `input_layer` den echten Automatenwerten entsprechen.

**F3: Stationsbeschriftung gegen die Regel (zweites Mal, M260-6).**
- (a) Fehlerklasse: Eine Zählerzeile wird frei formuliert statt aus der Regel abgeleitet.
- (b) Prüfung in TEIL 0b und 6: Die Stationszeile im Anker hat die feste Form „Station: ja/nein – Regel: Halt-Art ≠ Schranke oder Schleife verlassen, Vorgabe EIN, Preflight-Zeile <Zitat>“.
- (c) Ansonsten keine Lücke.

**F4: Sammelcommit, zum zweiten Mal.**
- (a) Fehlerklasse: Die Vorgabe „ein Commit je Maßnahme“ wirkt nicht.
- (b) Prüfung: Die Instruktion verlangt je Maßnahme Bauen, Messen und Committen, bevor die nächste Datei angefasst wird. Ich zähle im nächsten Review die Commits gegen die Maßnahmen.

**F5: Zielmaß aus einem Lauf, der vom Referenzlauf abweicht (M260-1).**
- (a) Fehlerklasse: Die Messgröße verändert das Gemessene, hier verschiebt der Schatten die Zeitbasis.
- (b) Prüfung in TEIL 5: Die Ursache der Verschiebung wird benannt und, wenn möglich, beseitigt. Das Preflight-Feld trägt das Urteil „referenzgleich ja/nein“.
- (c) Nicht geprüft: die Kalibrierwerte selbst.

<DS_INSTRUCTION>
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
</DS_INSTRUCTION>
