**Review B259:** Der Halt hat sich bewegt. Mit eingeschaltetem SHARC-Fix und vier kleinen Modellen läuft das ROM bis zur Schrittgrenze von 900M. Laut Preflight ist das eine neue `Hybrid-A4`-Zeile, nach der Regel des Nutzers also eine Station, und der Stillstandszähler steht wieder auf 0. Die Schleife, in der der Lauf jetzt steht, ist bekannt: Es ist die Abfrageschleife in `main` (`f5-descr-batch61…md:282-289`). Der Worker hat sie trotzdem als „inhaltlich zu Ende“ geführt. Den nativen Anteil gibt es weiterhin nicht als echten Messwert. B260 untersucht, worauf diese Schleife wartet.

<TELEGRAM_SUMMARY>
Ergebnis:
- Fix-Vorgabe EIN (voller A4 80,1 s). Vier Halte behoben, je mit MAME-Beleg und Rotprobe: DCCR (`8000830`0), `isync`, `cntlzw`, K056800-Host (`_m259/_haltfolge.txt:6-26`).
- Danach kein Halt mehr. Der Preflight zeigt `Hybrid-A4 900000000 | 8002B364 | Schranke` (`_preflight_259.txt:32`, HEAD `5bfb0a2`).
Bewertung:
- Die Station zählt nach der Nutzerregel; der Zähler ohne neue Station steht auf 0.
- Befund 1: Der Worker nannte die Iteration „inhaltlich zu Ende“. Tatsächlich ist `FUN_8000E7A0`+`FUN_8002B360` = `FUN_80008B9C`, das Abfrageschritt der Hauptschleife `while(Flag)` in `FUN_800089A0` (`analysis/f5-descr-batch61-2026-09-17.md:282-289`). Der Lauf wartet also auf ein Flag; vermutlich das Vblank-Signal IRQ0 (`hornet.cpp:1312`).
- Befund 2: Wieder ist eine Kalibriersumme (1739) als „Anteil nativ“ geführt. Laut Preflight ist der Anteil NICHT GEMESSEN, 385491 Rufe haben keinen Wert.
- Befund 3: Vier Halte stecken in einem Commit.
FERTIG WENN erreicht: teilweise. (d) fehlt: kein Schattenlauf 0..Halt.
Kosten/Laufzeit: 0,138 $, 127 min, 107 Anfragen.
Nächster Batch: Schleife und Flag-Schreiber messen, dann IRQ0 modellieren. Schattenweg beschleunigen, damit der Anteil echt gemessen wird.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 30 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: B259 N3 Schattenanteil 0..Halt -> B260 TEIL 4
UEBERTRAG: B259 N6 weitere Halte (Warteschleife) -> B260 TEIL 1+3
ENTSCHIEDEN: Nutzerklarstellung vom 03.10. übernommen. B259 ist Station, Stillstandszähler 0 von 4.
ENTSCHIEDEN: Endet `Hybrid-A4` an der Schranke, zählt als nächste Station ein Halt mit einer Art ≠ Schranke oder das belegte Verlassen der B259-Warteschleife. Der Halt selbst wird nicht umdefiniert.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1: Kalibriersumme als „Anteil nativ“ ausgegeben (zweimal in Folge: B258, B259).**
- (a) Fehlerklasse: Ersatzzahl als Zielmaß. Die Kalibriersumme ist eine Untergrenze mit 385491 Rufen ohne Wert.
- (b) Verwandte Fälle: `57819/200000000` und `nativ_bis_dahin`. Weil der Fehler wiederkehrt, ändert die Instruktion den Weg: Zuerst wird der Schattenweg schnell gemacht, dann misst **ein** Schattenlauf 0..Ende. Die Kalibriersumme heißt in jedem Text „Kalibriersumme (Untergrenze, N Rufe ohne Wert)“. Prüfung: Ich lese im nächsten Review die Ankerzeile und das Wort „Anteil“ nach.
- (c) Nicht geprüft: ob der Schatten die Schrittfolge verschiebt. Das wird nur berichtet, nicht bewertet.

**F2: Bekanntes Projektwissen nicht gesucht („Iteration inhaltlich zu Ende“, obwohl die Schleife als Hauptschleifen-Abfrage dokumentiert ist).**
- (a) Fehlerklasse: Die Grep-Pflicht nach R13az wurde nur auf MAME angewendet, nicht auf `analysis/` für die Funktionsadressen.
- (b) Verwandte Fälle: jeder Schranken- und Selbstsprung-PC. Prüfung: Zu jeder Schleife bzw. jedem Halt gehört ein Grep auf Funktions- und Aufruferadressen in `analysis/`, mit Fundstelle. Das Flag in TEIL 1 wird mit Schreibern (Querverweise) belegt.
- (c) Nicht geprüft: die Vollständigkeit der Ghidra-Querverweise bei indirekten Schreibern (über Zeiger).

**F3: Rotproben ab Abzug unmöglich, weil der Abzug Schalter überschreibt (R259b).**
- (a) Fehlerklasse: Ein wiederhergestellter Zustand überschreibt ausdrückliche Befehlszeilen-Optionen.
- (b) Verwandte Fälle: alle Schalter, die im Abzug gespeichert werden. Prüfung in TEIL 0b: Die Befehlszeile gewinnt. Rotprobe ab Abzug mit `--form-aus` muss ROT werden.
- (c) Nicht geprüft: die Versionierung des Abzugsformats.

**F4: Mehrere Halte in einem Commit.**
Einmal-Sache mit falscher Begründung („`git add -p` nötig“). Die Instruktion verlangt einen Commit direkt nach jedem behobenen Halt.

<DS_INSTRUCTION>
Batch 260 - Silent Scope Decomp

STRANG: B
SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 31. **Nutzerklarstellung 03.10.2026:** Die 8er-Grenze ist ein Stillstandsmelder. Der Zähler „ohne neue Station“ beginnt nach jeder bestätigten Station bei 0. Die Frage „B oder C“ geht erst nach 4 B-Batches in Folge ohne neuen Halt-PC an den Nutzer. Der Halt wird nicht umdefiniert.
**B259 ist eine Station** (`_preflight_259.txt:32@ef095de`: `Hybrid-A4 900000000 | 8002B364 | Schranke`, vorher `696571792 | 8001684C | Selbstsprung`). Stillstandszähler: **0 von 4**.
Vorgabe jetzt: `--sharc-handschlag` EIN, DCCR/ICCR, `isync`, `cntlzw`, K056800-Host-Attrappe (`5bfb0a2`). Abzug `port/build/abzug_s.bin` bei S = 215016862. Voller A4 ~240 s, ab Abzug ~169 s.
**Fehlstelle geklärt (R13az):** Die „Warteschleife“ `FUN_8002B360`/`FUN_8000E7A0` ist `FUN_80008B9C`, der Abfrageschritt der Hauptschleife. Aufrufer ist `FUN_800089A0` (main) mit `while (Flag) { FUN_80008B9C(); }` (`analysis/f5-descr-batch61-2026-09-17.md:282-289`, `analysis/bucket-b-2026-09-16.md:101-104`). Hauptschleife `80008AA0` (`analysis/bericht-b221-berichtspunkt-hybrid.md:24`). IRQ0 = „Vblank CG Board 0“ (`mame/mame/src/mame/konami/hornet.cpp:1312`), Quittung `:811-815`. Der Hybrid-Kern hat einen Ausnahmeweg über EVPR (`port/hybrid/ppc_kern.cpp:860-865`) und EXISR/EXIER (`:413-415`).
ENTSCHEIDUNG (Reviewer): Endet `Hybrid-A4` an der Schranke, ist die nächste Station entweder ein Halt mit Halt-Art ≠ Schranke oder das belegte Verlassen der B259-Schleife (erster Schritt außerhalb mit PC), beides im gültigen Preflight mit Vorgabe EIN.
ENTSCHEIDUNG (Reviewer): `1739` ist eine **Kalibriersumme (Untergrenze, 385491 Rufe ohne Wert)**, kein Anteil. Das Wort „Anteil nativ“ steht nur an einer Zahl aus einem Schattenlauf.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B260: Vorhersage` VOR jedem `port/`/`scripts/`-Diff, mit Sollwerten und Zählerdefinitionen je Bilanzzeile.
- **Ein Commit direkt nach jedem behobenen Halt oder Modell** (`B260 Halt <PC>: …` bzw. `B260 Modell <Name>: …`). Mehrere Maßnahmen in einem Commit sind ein Befund.
- Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500, blockierend mit `timeout=1800000` (auch Preflight, `port_build`). Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen, Abräumen über `Get-Process`/Variable/Pipe.
- **Grep-Pflicht (R13az) zu jedem Halt und jeder Schleife:** Grep auf PC, Funktionsadresse **und** Aufruferadresse in `analysis/` und `port/`. Bei Hardware zusätzlich in `mame/mame/src/`. Fundstelle mit `Datei:Zeile`, sonst `Fehlstelle: gesucht in …, nicht gefunden (Grep "<Bezeichner>")`.
- Modelle tragen „Hybrid-Gerüst, im Port zu ersetzen“, ROM- und MAME-Beleg und einen Gegenschalter. „Blockiert“ nur mit Messung auf demselben HEAD. Der Batch endet nicht vor der Umschaltschwelle, solange ein Posten offen ist.
- Belege als `Datei:Zeile@commit`. Rohläufe über 20 MB heißen `*_roh.txt` und werden nicht getrackt. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_260.txt`.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. **Abzug-Falle R259b beheben** (`port/hybrid/hybrid_lauf.cpp:1494-1495,1521@5bfb0a2`): Ausdrückliche Befehlszeilenschalter (`--form-aus`, `--attrappe-aus`, Gegenschalter) gewinnen gegen den Abzug. Rotprobe ab Abzug mit `--form-aus 31/26` muss am `cntlzw`-PC `80026D6C` halten.
0c. Die B259-Texte (Batch-Dokument und Ankerkopf) berichtigen: „Anteil nativ 1739/900000000“ heißt dort künftig „Kalibriersumme 1739 (Untergrenze, 385491 Rufe ohne Wert)“.

TEIL 1 - Schleife vermessen (nur messen und lesen):
1a. Lauf ab Abzug bis 900M mit PC-Histogramm der letzten 10M Schritte, zugeordnet zu Funktionen (`get_function_by_address`). Erster Schritt, an dem `80008AA0` (Hauptschleife) und `80008B9C` erreicht werden.
1b. In `FUN_800089A0` (`decompile_function`) die `while (Flag)`-Schleife bestimmen, in der der Lauf steht: Adresse des Flags und erwarteter Wert.
1c. Schreiber des Flags über Ghidra-Querverweise (`get_xrefs_to` bzw. die verfügbaren Lesewerkzeuge). Klasse des Schreibers: Ausnahme-/Interruptweg (welcher Vektor) oder normaler Code. Zustand im Lauf: MSR[EE], EXIER, EXISR, EVPR (aus dem Kern).
1d. Ergebnis als `_m260/_schleife.txt`: Flag, Schreiber, Klasse, erwartete Quelle. Ist es nicht der Interruptweg, die tatsächliche Quelle benennen und TEIL 3 darauf ausrichten.

TEIL 2 - Schritt 4 messbar machen:
2a. Die A4-Ausgabe (`hybrid_lauf` + `scripts/m212_zeilen.py`) bekommt das Feld `Hauptschleife 80008AA0 erreicht ja/nein (erster Schritt n)`. Gegenprobe: Ein mutiertes Wort im Startpfad ergibt `nein`.
2b. Schritt-4-Teil „deckt sich mit den Referenzströmen `capture/poc_ref_*.txt`“ (`analysis/hybrid-plan.md:356-359`): Grep, ob ein Vergleichsweg Hybrid→Kommandostrom existiert. Existiert er: Zahl der Abweichungen messen. Fehlt er: Fehlstelle mit Grep benennen und den kleinsten Bauweg in 3 Sätzen beschreiben (kein Bau in diesem Batch).

TEIL 3 - Quelle des Flags modellieren (Haltfolge fortsetzen):
3a. Ist TEIL 1 = externer Interrupt IRQ0/Vblank: Gerüstmodell `--vblank`, Vorgabe AUS. Bestandteile: periodisches Setzen des EXISR-Bits (Periode aus MAME-Takt und Bildrate, mit Fundstelle), Zustellung über den vorhandenen Ausnahmeweg an EVPR+Vektor nur bei MSR[EE] und EXIER, Quittung über das Sysreg (`hornet.cpp:811-815`) und das Löschen von EXISR. MAME-Fundstelle für die 403-Zustellung (`ppccom.cpp`, `ppc4xx_set_irq_line` o. ä., per Grep).
3b. Lauf ab Abzug mit `--vblank` bis Halt oder 900M. Ergebnis: Wird die Schleife verlassen (erster Schritt außerhalb, PC)? Neuer Halt? Jeden weiteren Halt wie in B259 in `_m260/_haltfolge.txt` behandeln (Grep-Pflicht, Modell, Rotprobe, Commit je Halt), bis zur Umschaltschwelle oder bis zu einer belegten Stopp-Bedingung.
3c. Vorgabe EIN nur, wenn der volle A4-Lauf mit `--vblank` unter 1500 s gemessen ist und die Ergebniszeile reproduzierbar ist (zwei Läufe gleich). Dann Vorwärmung und Preflight; der neue Wert in `Hybrid-A4` ist die Station.

TEIL 4 - Nativer Anteil echt messen (NIE streichen):
4a. Den B258-Fix (`rim`/`g_rim`, keine 4-MiB-Kopie je Ruf) in den **Schattenweg** übertragen (`hybrid_lauf.cpp:525,1406@5bfb0a2`). Kurzlauf 20M mit Schatten zeichengleich, 200M mit Schatten weiter `101577/200000000`.
4b. **Ein** Schattenlauf ab Schritt 0 bis zum Ende der Vorgabe (900M oder Halt), `--wanduhr-grenze 1500`. Ergebnis: `Anteil nativ x / Schritte` aus diesem einen Zähler und die Schrittverschiebung gegenüber dem Lauf ohne Schatten als eigene Zeile. Ist der Lauf nicht in 1500 s fertig: Rate und erreichte Schritte, Ursache aus `--kopf-zeit`.

TEIL 5 - Vorwärmung, Preflight, Bilanz, Anker:
Vorwärmung blockierend, Preflight, `m149_bilanz.py --batch 260 --from-preflight analysis/_preflight_260.txt --write-anchor`. Nach dem Preflight nichts mehr unter `scripts/` ändern.
Ankerkopf B260 mit:
- Preflight-HEAD aus Zeile 3,
- Station (ja/nein, Beleg),
- Stillstandszähler „k von 4“,
- Schleifenbefund,
- `Anteil nativ` aus TEIL 4b (sonst „NICHT GEMESSEN“ + Kalibriersumme als Untergrenze),
- „Nächster Schritt“ mit Batch-Nummer 261. Die Zeile nannte B258 und war veraltet.
Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse >50 Zeilen), Ankerblock mit `UEBERTRAG:`/`GESCHLOSSEN`.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B260: …`. Abweichungen von der Vorhersage erklären.

FERTIG WENN: (a) `_m260/_schleife.txt` mit Flag-Adresse, Schreiber, Klasse und Belegen; (b) A4-Feld „Hauptschleife erreicht“ mit Gegenprobe; (c) Quelle des Flags modelliert und Lauf ab Abzug mit Ergebnis (Schleife verlassen/neuer Halt) oder belegte Stopp-Bedingung; (d) `Anteil nativ` aus einem Schattenlauf 0..Ende oder gemessene Rate mit Ursache; (e) Abzug-Falle behoben mit Rotprobe ab Abzug ROT; (f) gültiger Preflight + Bilanz, Ankerkopf B260 mit Stillstandszähler; (g) je Modell bzw. Halt ein Commit.

STREICHREIHENFOLGE: 1. TEIL 2b (Referenzstrom-Messung bzw. Bauweg), 2. weitere Halte in TEIL 3b nach dem ersten, 3. TEIL 3c (Vorgabe EIN), 4. TEIL 0c. NIE: Vorhersage-Commit, TEIL 0b, TEIL 1, TEIL 2a, TEIL 3a + erster Lauf 3b, TEIL 4, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 1 Schleife; FERTIG WENN: `_m260/_schleife.txt` committet mit Flag, Schreiber (Querverweis), Klasse und MSR/EXIER/EXISR-Stand.
2. TEIL 4 Anteil nativ; FERTIG WENN: Schattenweg ohne 4-MiB-Kopie (20M zeichengleich, 200M = 101577) und ein Schattenlauf 0..Ende mit `Anteil nativ x / Schritte`, oder Rate mit `--kopf-zeit`-Ursache.
3. TEIL 3a/3b Flag-Quelle; FERTIG WENN: Modell hinter Schalter mit MAME-Beleg, Lauf ab Abzug mit Ergebnis und Rotprobe (Schalter aus → Schleife bleibt).
4. TEIL 0b + 2a; FERTIG WENN: Rotprobe ab Abzug mit `--form-aus` ROT, A4-Feld „Hauptschleife erreicht“ mit Gegenprobe `nein`.
5. TEIL 3c + weitere Halte; FERTIG WENN: Vorgabe EIN mit zwei gleichen A4-Läufen unter 1500 s und Preflight-Zeile, oder Begründung mit Messung; je weiterem Halt eine Zeile und ein Commit.
6. TEIL 2b + 0c; FERTIG WENN: Referenzstrom-Abweichungszahl oder Fehlstelle mit Grep und Bauweg, B259-Texte berichtigt.
</DS_INSTRUCTION>
