**Review B258:** Das FERTIG WENN ist erreicht. Der Zustandsabzug funktioniert: Ab dem Abzug läuft der Kontrolllauf in 79,7 s zum selben Halt, damit ist das 5-Minuten-Ziel des Nutzers erfüllt. Mit dem SHARC-Fix bewegt sich der Halt erstmals seit B248, auf `80008300`. Die dortige Lücke ist einfach: `mtspr` auf Register 1018 ist laut MAME das Cache-Register DCCR des 403GA. Als Station zählt das noch nicht: der Fix ist standardmäßig aus, und den vollen Lauf mit Fix hat der Worker nicht gemessen, obwohl er billig ist. B259 schaltet den Fix nach dieser Messung ein und fährt die nächsten Halte ab.

<TELEGRAM_SUMMARY>
Ergebnis:
- Das Fenster ist von 842 auf 123 s geschrumpft. Ursache war eine zweite 4-MB-Kopie je Kopf-Ruf.
- Zustandsabzug bei S = 215016862: Die Gegenprobe ab Abzug läuft in 79,7 s und ist zeichengleich (696571792/8001684C/1511). Damit ist das Nutzerziel „unter 5 min“ erreicht. Die Rotprobe ist ROT (`_m258/_abzug.txt:2-7`).
- Fix `--sharc-handschlag`: `c3a8` liefert 0 statt 0x20000000, `be40` liefert 0 statt 2. Danach entsteht ein **neuer Halt `80008300`, `EXC spr 1018`, Schritt 256610158** (`_m258/_fix.txt:10-13`, `_lauf3c.txt:4-6`). Der Halt bewegt sich zum ersten Mal seit B248.
Bewertung: Starker Batch. Befunde:
(1) Den Punkt „Vorgabe EIN“ hat der Worker als „nicht erfüllt“ geführt, ohne den billigen vollen A4-Lauf mit Fix zu messen. Der Batch endete nach 78 min. Meine Nachrückliste hatte diesen Posten nicht, das ist mein Anteil.
(2) Der native Anteil ist eine Mischzahl: Ein Schattenzähler wurde mit dem Kalibrierwert 1511 verrechnet, und die Zahl ist als „0..Halt“ beschriftet (Dok:182-184).
(3) Die SPR 1018 ist DCCR des 403GA (`mame/mame/src/devices/cpu/powerpc/ppccom.h:175`). Das ist keine offene Hardwarefrage.
FERTIG WENN erreicht: ja.
Kosten/Laufzeit: 0,188 $, 78 min, 126 Anfragen.
Nächster Batch: Fix-Vorgabe EIN nach Messung, DCCR/ICCR modellieren, Halte iterativ abfahren, nativer Anteil aus einem Lauf.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 29 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: B258 TEIL 3d (Vorgabe EIN) -> B259 TEIL 1
UEBERTRAG: nativer Anteil als Einzelmessung -> B259 TEIL 4
ENTSCHIEDEN: Die Station zählt, sobald `Hybrid-A4` im Preflight mit der Vorgabe EIN den neuen Halt zeigt.
ENTSCHIEDEN: Hybrid-Läufe bis 20M Schritte brauchen keine Wanduhrgrenze.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Eine Bedingung wurde als „nicht erfüllt“ geführt, obwohl sie nicht erhoben war (3d). Dazu fehlte der Posten in der Nachrückliste, und der Batch endete 57 min vor der Schwelle.**
- (a) Fehlerklasse: Ein bedingter Schritt galt als freiwillig. Die Messung, die die Bedingung entscheidet, wurde nicht gemacht. Die Nachrückliste deckte nicht jeden TEIL ab.
- (b) Verwandte Fälle: jeder TEIL mit „nur wenn …“. Prüfung in der Instruktion: Jeder bedingte TEIL nennt die Messung, die die Bedingung entscheidet, als eigenes FERTIG WENN. Die Nachrückliste enthält **jeden** TEIL. Die Halt-Iteration in TEIL 3 läuft ausdrücklich bis zur Umschaltschwelle weiter.
- (c) Nicht geprüft: ob ein früheres Ende in anderen Batches dieselbe Ursache hatte.

**F2: Mischzahl aus zwei Zählweisen (Schattenzähler minus Kalibrierwert, falsch als „0..Halt“ beschriftet).**
- (a) Fehlerklasse: Zähler aus verschiedenen Messverfahren werden miteinander verrechnet.
- (b) Verwandte Fälle: `Ersatz 9`/`Ersatz C`, `57819/200000000` und `nativ_bis_dahin 1511`. Prüfung in TEIL 4: ein einziger Lauf 0..Halt mit Schatten und ein einziger Zähler. Dazu die Halt-Schrittverschiebung durch den Schatten (B258: +28445) als eigene Zeile.
- (c) Nicht geprüft: ob die Kalibrierwerte der 195348 Rufe stimmen.

**F3: SPR 1018 wäre fast als offene Lücke geführt worden („HYPOTHESIS“).**
- (a) Fehlerklasse: „fehlt/unbekannt“ ohne Suche nach dem Bezeichner.
- (b) Verwandte Fälle: jede weitere `EXC spr N` und jede unbekannte Adresse in der Halt-Iteration. Prüfung in TEIL 3: Zu jedem neuen Halt gehört ein Grep auf SPR-Nummer bzw. Adresse in `mame/mame/src/devices/cpu/powerpc/` und `analysis/`, mit Fundstelle.
- (c) Nicht geprüft: die Cache-Semantik selbst. Im Hybrid wird DCCR/ICCR nur gespeichert, ohne Wirkung.

<DS_INSTRUCTION>
Batch 259 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 30, **Serie „spielbare Beta“ 5 von 8** (bisher 0 gezählte Stationen in B255–B258). C ruht.
Vorgabe-Halt (`Hybrid-A4`): `696571792 | 8001684C | Selbstsprung | nativ_bis_dahin 1511` (`_preflight_258.txt`, HEAD `30a8d03`).
B258 hat gemessen (`analysis/port-batch258-b-zustandsabzug-2026-10-03.md@3c6b4a5`):
- Fenster 123,4 s.
- Abzug `port/build/abzug_s.bin` bei S = 215016862 (SHA `7fdbfac8…`), Gegenprobe ab Abzug 79,7 s zeichengleich (`_m258/_abzug.txt:2-7`).
- Fix `--sharc-handschlag` (Vorgabe AUS): `c3a8` = 0, `be40` = 0 (Schritt 256572910). Danach **neuer Halt `80008300`, Wort `7C7AFBA6`, `EXC spr 1018`, Schritt 256610158** (`_m258/_fix.txt:10-13`).
**Fehlstelle geklärt (R13az):** `7C7AFBA6` = `mtspr 1018, r3`. SPR 1018 = 0x3FA = **DCCR** des 403GA (`mame/mame/src/devices/cpu/powerpc/ppccom.h:175`, Schreibweg `ppccom.cpp:2170`, Leseweg `:1982`). Der Boot-Lader setzt ICCR/DCCR ebenfalls (`analysis/initial-ppc-analysis.md:74,240`). Das ist keine unbekannte Hardware.
ENTSCHEIDUNG (Reviewer): Eine Station zählt, sobald `Hybrid-A4` im gültigen Preflight mit Vorgabe EIN einen neuen Halt-PC zeigt. Zwischenhalte innerhalb des Batches werden dokumentiert, zählen aber erst über diese Zeile.
ENTSCHEIDUNG (Reviewer): Hybrid-Läufe bis 20M Schritte brauchen keine Wanduhrgrenze. Alle längeren Läufe tragen `--wanduhr-grenze` ≤ 1500.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B259: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Je Bilanzzeile Sollwert und Zählerdefinition. Ausdrücklich: `Hybrid-A4` nach Vorgabe EIN, Dauer des vollen A4-Laufs mit Fix, Halt nach dem DCCR-Modell.
- Blockierend mit `timeout=1800000` (gilt auch für `preflight.py`, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe. Höchstens 3 Läufe über 600 s. Lauftafel im Dokument.
- **Zu jedem neuen Halt** (R13az): Wort dekodieren (offline, kein `disassemble_bytes`). Grep auf SPR-Nummer, Adresse bzw. Mnemonik in `mame/mame/src/devices/cpu/powerpc/` und `analysis/`, Fundstelle mit `Datei:Zeile`. „Unbekannt“ nur mit `Fehlstelle: gesucht in …, nicht gefunden (Grep "<Bezeichner>")`.
- Modelle tragen „Hybrid-Gerüst, im Port zu ersetzen“, ROM-Beleg und MAME-Beleg. „Blockiert“ nur mit Messung auf demselben HEAD. Laufzeit ist keine Blockade. **Der Batch endet nicht vor der Umschaltschwelle der Batch-Uhr**, solange TEIL 3 einen weiteren Halt bearbeiten kann.
- Belege als `Datei:Zeile@commit`. Rohläufe über 20 MB heißen `*_roh.txt` und werden nicht getrackt. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_259.txt`.

TEIL 1 - Fix-Vorgabe EIN (B258 3d, Bedingung messen):
1a. Voller A4-Lauf ab Schritt 0 mit A4-argv + `--sharc-handschlag`, `--wanduhr-grenze 1500`. Soll: Halt `80008300 | EXC spr 1018 | 256610158`, wie ab Abzug. Wanduhr notieren.
1b. Ist 1a gleich und unter 1500 s: Vorgabe auf EIN stellen (`--sharc-handschlag-aus` als Gegenschalter). Prüfen, dass `Hybrid-Lauf 200M` und `Hybrid-Lauf 20M` unverändert bleiben (Fix wirkt erst ab 215M). Ist 1a ungleich: erste Abweichung mit Schritt und PC belegen, Vorgabe bleibt AUS, weiter mit TEIL 2.

TEIL 2 - DCCR/ICCR modellieren:
2a. `mtspr`/`mfspr` für SPR 0x3FA (DCCR) und 0x3FB (ICCR) im Hybrid-Kern als einfache Register (speichern/lesen, keine Cache-Wirkung). Beleg MAME `ppccom.cpp:1982,2170` und ROM-Fundstelle `80008300`. Kopf-Kommentar „Hybrid-Gerüst, im Port zu ersetzen“.
2b. Rotprobe: Mit dem Schalter `--form-aus 31/467` oder einem Gegenschalter kommt `EXC spr 1018` bei `80008300` wieder. Kurzlauf 20M zeichengleich.
2c. Abzug neu erzeugen, falls das Abzugsformat sich ändert (S unverändert, Größe/SHA neu). Die Gegenprobe ohne Fix muss weiter zeichengleich sein.

TEIL 3 - Halt-Iteration ab Abzug (Hauptarbeit, bis zur Umschaltschwelle):
Schleife: Lauf ab Abzug mit Fix bis Halt (`--wanduhr-grenze 600`) → Halt klassifizieren (Form-EXC / Selbstsprung / Gerätezugriff / Schranke) → Grep-Pflicht (Arbeitsweise) → beheben, wenn klein und mit MAME- und ROM-Beleg modellierbar → Rotprobe → nächster Lauf.
Je Halt eine Zeile in `_m259/_haltfolge.txt`: Schritt, PC, Wort, Klasse, Fundstelle, Maßnahme, Commit. Je behobenem Halt ein Commit `B259 Halt <PC>: …`.
Stopp-Bedingung je Halt (nicht Batch-Ende): Braucht ein Halt ein Gerätemodell ohne Fundstelle oder Material vom Nutzer: Zeile mit Grep-Beleg schreiben und `WARTET AUF LIVE-AUFNAHME`-Kandidat nennen. Danach ist die Iteration für diesen Strang zu Ende, weiter mit TEIL 4.
Ein Selbstsprung in einer Warteschleife wird nicht umdefiniert. Die Schleife wird mit Lesepfad und erwarteter Bedingung beschrieben.

TEIL 4 - Nativer Anteil als Einzelmessung (NIE streichen):
Ein einziger Lauf **ab Schritt 0** mit Schatten (A4-argv ohne `--ohne-schatten`, mit der in TEIL 1 gültigen Vorgabe) bis zum Halt, `--wanduhr-grenze 900`. Ergebnis: `nativ x / Schritte` aus **einem** Zähler, Bereich 0..Halt. Die Halt-Schrittverschiebung gegen den Lauf ohne Schatten bekommt eine eigene Zeile. Die B258-Zahl „29908/696600237 (0..Halt)“ im Dokument als Mischzahl berichtigen (Kalibrierwert 1511 ≠ Schattenzähler). `57819/200000000` bleibt Ersatzzahl.

TEIL 5 - Vorwärmung, Preflight, Bilanz, B-Bericht:
Vorwärmung blockierend (A4 jetzt kurz), dann Preflight und `m149_bilanz.py --batch 259 --from-preflight analysis/_preflight_259.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.
Die Vorhersage nennt die geänderte `Hybrid-A4`-Zeile als neue Station (falls TEIL 1b EIN).
Ankerkopf B259: Preflight-HEAD aus Zeile 3, Station(en), Haltfolge, nativer Anteil (TEIL 4), „Serie 5 von 8, Stationen k“. Die alte Zeile „7 von 8 ohne neue Station“ (`analysis/r1b-workstream.md:90@3c6b4a5`) als überholt kennzeichnen.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B259: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) voller A4-Lauf mit Fix gemessen und Vorgabe-Entscheidung belegt; (b) DCCR/ICCR modelliert mit Rotprobe ROT, 20M zeichengleich; (c) `_m259/_haltfolge.txt` mit mindestens einem Halt jenseits `80008300` oder belegter Stopp-Bedingung; (d) nativer Anteil 0..Halt aus einem Lauf und einem Zähler; (e) ein gültiger Preflight + Bilanz, `Hybrid-A4` zeigt den neuen Halt (bei Vorgabe EIN); (f) Ankerkopf B259 mit Stationszählung.

STREICHREIHENFOLGE: 1. weitere Halte in TEIL 3 über den ersten hinaus, 2. TEIL 2c (nur wenn das Abzugsformat unverändert bleibt), 3. Berichtigung der B258-Mischzahl im alten Dokument. NIE: Vorhersage-Commit, TEIL 1, TEIL 2a-2b, erster Halt in TEIL 3, TEIL 4, Preflight, Bilanz, Memory-Export, Ankerkopf/B-Bericht.

## NACHRUECKLISTE
1. TEIL 1 Vorgabe EIN; FERTIG WENN: voller A4 mit Fix (Wanduhr, Halt) im Dokument und Vorgabe EIN oder belegte Abweichung mit Schritt und PC.
2. TEIL 2 DCCR/ICCR; FERTIG WENN: Lauf ab Abzug kommt über `80008300` hinaus, Rotprobe ROT, 20M zeichengleich.
3. TEIL 4 nativer Anteil; FERTIG WENN: `nativ x / Schritte` 0..Halt aus einem Schattenlauf plus Zeile zur Halt-Verschiebung.
4. TEIL 5 Preflight/Bilanz/Anker; FERTIG WENN: gültiger Preflight mit neuem `Hybrid-A4` (bei EIN), Bilanz, Ankerkopf B259.
5. TEIL 3 erster Halt jenseits `80008300`; FERTIG WENN: Zeile in `_m259/_haltfolge.txt` mit Klasse, Grep-Fundstelle und Maßnahme.
6. TEIL 3 weitere Halte; FERTIG WENN: je Halt eine Zeile und ein Commit, bis zur Umschaltschwelle oder bis zur belegten Stopp-Bedingung.
</DS_INSTRUCTION>
