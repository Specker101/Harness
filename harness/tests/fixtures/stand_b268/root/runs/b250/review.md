<TELEGRAM_SUMMARY>
Ergebnis: Op 27/29 sind im Kern und gegen Unicorn geprüft (gruen, beide Rotproben ROT). `ab90` gibt jetzt 0 zurück, `ab0c` wird erreicht. `be40` meldet aber weiter einen Fehler, und der Halt-PC steht wieder bei 8001684C (geprüft: `_preflight_249.txt:32`). Welche Stufe scheitert, wurde nicht gemessen.
Bewertung: FERTIG WENN erreicht: ja, aber mit zwei Regelverstößen. Der Preflight dauerte 2335 s, davon 1785 s der Hybrid-Lauf; das liegt über der Grenze von 1800 s. Der Worker wich deshalb auf Hintergrundlauf und Warteaufrufe aus. Außerdem liegen zwei Rohdateien ungetrackt im Baum.
Zwischenprüfung bisher: Innerhalb von `be40` ist der Lauf von Stufe 5 auf mindestens 7 weitergekommen (das ist nur eine Ersatzzahl). Über 8001684C hinaus ist er nicht. Den Ausschlag gibt B250.
Kosten/Laufzeit: $0,23, 2 h 17 min, 160 Anfragen.
Nächster Batch: B250, der letzte von 3. Erst den Hybrid-Lauf schneller und zwischenspeicherbar machen, dann Rückgabewerte messen und die Fehlerstufe beheben, wenn ROM und MAME sie belegen.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 24 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M249-1: übernommen als B250 TEIL 4 (Anteil als „nicht gemessen“ beschriften), Wirkung noch nicht belegt -> offen
M249-2: übernommen als B250 TEIL 1 (Abbruch beim ersten Halt, Zwischenspeicher über Binär-Hash), Wirkung noch nicht belegt -> offen
M249-3: übernommen als B250 TEIL 2 (Rückgabepfade statisch, Widerspruch Stufe 5 gegen 7 klären), Wirkung noch nicht belegt -> offen
M249-4: übernommen für den ersten C-Batch (Preflight-Zeile referenzgleiche Insn), Wirkung noch nicht belegt -> offen
M249-5: übernommen für den ersten C-Batch (Ersatzzahl aus `m242`), Wirkung noch nicht belegt -> offen
M249-6: übernommen als B250 TEIL 0 (Auszug + SHA-256, Rohdatei ignoriert), Wirkung noch nicht belegt -> offen
UEBERTRAG: be40-Stufe -> B250 TEIL 3; 9 fehlende Formen (a) -> B250 TEIL 6
ENTSCHIEDEN: „Über 8001684C hinaus“ heißt: `be40` = 0 gemessen, kein Fehlerweg bei 800167a4, Halt-PC ≠ 8001684C. Sonst geht es nach B250 zurück zu C.
ENTSCHIEDEN: In B250 kommen Werkzeug und Fortschritt zusammen. Ohne schnelleren Lauf lässt sich in der Zeit nichts messen.
OFFENE FRAGE: Soll die Plan/Ist-Tafel des Harness für C auf referenzgleiche Insn umgestellt werden, sobald es die Preflight-Zeile gibt (M249-4)? Vorschlag: ja.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Halt auf dem Fehlerweg wurde als „nach Regel nicht behebbar“ abgeschlossen, obwohl die Ursache weiter vorn liegt.**
- (a) Fehlerklasse: Die Folge eines Fehlers wird mit seiner Ursache verwechselt. 8001684C ist nur das Ende des Fehlerwegs; die Ursache ist die erste fehlschlagende Prüfung in `be40`. Meine Regel aus B249 hat das zugelassen.
- (b) Für jeden Halt auf einem Fehlerweg (Selbstsprung nach einem Fehlercode) verlangt B250, den Fehlercode bis zum ersten fehlschlagenden Vergleich zurückzuverfolgen. Dazu dient eine Rückgabe-Sonde: r3 bei jedem `blr` der genannten Funktionen.
- (c) Nicht verfolgt werden Fehlercodes außerhalb der `be40`-Kette.

**Befund 2: Preflight und Messlauf über der 1800-s-Grenze, dadurch Hintergrundlauf und Warteaufrufe.**
- (a) Fehlerklasse: Ein Preflight-Schritt wächst mit dem Fortschritt (mehr Schritte bis zum Halt). Ohne Abbruch und ohne Zwischenspeicher sprengt er die Zeitgrenze.
- (b) Verwandte Fälle: jeder Lauf mit fester Schrittzahl, also auch die Läufe mit 200M und 20M Schritten. B250 lässt die Sekunden je Teillauf messen. Der A4-Lauf bekommt einen Abbruch beim ersten Halt und einen Zwischenspeicher über den Hash von Binärdatei und Argumenten. Sollwert: Preflight unter 900 s, wenn ein passender Zwischenspeicher vorliegt.
- (c) Die Läufe mit 200M und 20M Schritten werden nicht umgebaut.

**Befund 3: Rohdateien ungetrackt liegen gelassen bzw. riesig committet (je ~240k Zeilen).**
- (a) Fehlerklasse: Es gibt keine Ablageregel für große Rohläufe.
- (b) In B250 wird ein Kurzauszug plus SHA-256 committet und die Rohdatei per `.gitignore` ausgeschlossen. Das gilt für jede neue Rohdatei über 20 MB.
- (c) Schon committete Rohdateien bleiben wie sie sind: keine Löschung, keine Änderung der Historie.

**Befund 4: Die Stufennummern widersprechen sich (`bucket-f2:85` ab90(3)/ab0c(5) gegen Disassembly B249 ab90→5/ab0c→7).**
- (a) Fehlerklasse: Eine alte STRONG-Aussage wird nicht gegengelesen.
- (b) B250 TEIL 2 erstellt eine statische Tafel aller Rückgabepfade mit Adresse. Der Widerspruch wird im neuen Dokument aufgelöst; das alte Dokument bleibt unverändert.
- (c) Die Fehlercodes in den Unterfunktionen außerhalb von `ab0c`/`a7f4` werden nicht geprüft.

<DS_INSTRUCTION>
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
</DS_INSTRUCTION>
