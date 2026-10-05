<TELEGRAM_SUMMARY>
Ergebnis: Das K033906-Modell beantwortet die PCI-ID-Prüfung von `FUN_8000ab90` jetzt so, wie ROM und MAME es vorgeben. Der Halt-PC in der Preflight-Zeile ist von 8001684C auf 8000A164 gewandert (geprüft: `_preflight_248.txt:32`). Mit Modell aus oder falscher ID bleibt der Lauf wie vorher bei 8001684C stehen (Rotprobe wirkt). Der Indexfehler in `m209` ist behoben. 28 Leser der Abdeckungskarte sind aufgelistet; dabei kam ein zweiter falscher Leser heraus (`m53_pool.py:100`).
Bewertung: FERTIG WENN erreicht: ja. Einzige Ausnahme: Die Rückgabe von `ab90` und die Stufe von `be40` sind nicht zu sehen, weil der Lauf noch innerhalb von `ab90` hält.
Der neue Halt liegt allerdings in unserem eigenen Interpreter: Die Befehle `andis.` (Op 29) und `xoris` (Op 27) fehlen im Hybrid-Kern (geprüft: `ppc_kern.cpp:343-352`). Ob das Spiel selbst über 8001684C hinauskommt, ist damit noch offen.
Messbefund: Der Anteil „nativ 1511“ ist eine Kalibriersumme aus B231, kein Messwert, und steht seit B231 unverändert.
Der Batch war mit 54 min zu klein geschnitten.
Kosten/Laufzeit: $0,20, 54 min, 122 Anfragen.
Nächster Batch: B249 (2 von 3). Alle fehlenden Befehlsformen erfassen, Op 27/29 ergänzen und prüfen, dann den Halt weiter treiben, solange die Uhr reicht.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 23 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
UEBERTRAG: Rückgabe von ab90 und Stufe von be40 -> B249 TEIL 3
UEBERTRAG: Indexfehler in `m53_pool.py:100` -> Anker „Nächster Schritt“, erster C-Batch nach B250
UEBERTRAG: C-Zuschnitt nach Insn (≥150, größte Blätter, <10 Insn nur Beifang, Summe berichten) -> erster C-Batch nach B250 (Regel steht schon im Anker, Zeile 28)
VERWORFEN: B209-Beleg nachziehen – alte Belege bleiben laut AGENTS.md unverändert
ENTSCHIEDEN: Der Zwischenstand gilt formal als „Halt bewegt“, aber nicht als „über 8001684C hinaus“. Das ist erst erreicht, wenn `be40` Stufe 5 hinter sich hat. Es wird keine Planfrage vorgezogen; die Entscheidung fällt nach B250.
ENTSCHIEDEN: `m53` wird nicht in einem B-Batch korrigiert.
ENTSCHIEDEN: `read_memory` lehne ich erneut ab (offline lesen, Regel R398).
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Halt an einer fehlenden Befehlsform im Hybrid-Kern (Op 29 `andis.`, Op 27 `xoris`).**
- (a) Fehlerklasse: Der Interpreter kann nicht alle Befehlsformen, die in tatsächlich ausgeführtem ROM-Code vorkommen. Jede fehlende Form wird erst als Halt sichtbar, also ein Batch je Lücke.
- (b) Verwandte Fälle: alle primären Opcodes und alle erweiterten Op-31-, 19- und 59/63-Formen. TEIL 1 lässt ein vollständiges Inventar erstellen: Formen in der ausgeführten Menge (korrigierter Index) und im statischen Rumpf der `be40`-Kette, abgeglichen mit `ppc_kern.cpp`. Jede neu eingebaute Form muss in `m227_formen.py gruen` „gruen“ sein und braucht eine ROT gewordene Rotprobe.
- (c) Nicht geprüft: Formen außerhalb der ausgeführten Menge und der `be40`-Kette. Ebenso nicht, ob schon vorhandene Formen auch die Flags (CR, XER) richtig setzen; das prüft `m227` nur für die gelisteten Formen.

**Befund 2: „davon nativ 1511“ ist eine Kalibriersumme, kein Messwert.**
- (a) Fehlerklasse: Die Messgröße passt nicht zum Ziel. Ziel A4 ist der gemessene native Anteil; geführt wird eine feste Zahl.
- (b) TEIL 4 lässt die Herkunft der Zahl mit `Datei:Zeile` belegen und festhalten, was eine echte Messung bräuchte. Im Bericht wird die Zahl als Ersatzzahl beschriftet.
- (c) In B249 wird kein Messumbau gemacht. Das bleibt offen bis zur Auswertung nach B250.

**Befund 3: zweiter falscher Indexleser (`m53_pool.py:100`, `>>2`; 49 von 327 Urteilen betroffen).**
- (a) Gleiche Fehlerklasse wie M247-1: falsche Einheit beim Index.
- (b) Die Leserliste ist vollständig. Die Korrektur samt Vorhersage-Delta kommt in den ersten C-Batch.
- (c) Ob ältere Anker- oder Bilanzzahlen aus `m53`, `m54` oder `m58` falsch sind, wird nicht nachgerechnet.

**Befund 4: Batch nach 54 von 150 min beendet.**
- (a) Fehlerklasse: Der Auftrag endete an der ersten Folgestufe und füllte die Batch-Uhr nicht.
- (b) B249 läuft deshalb als Schleife „messen → einordnen → beheben“ bis zur Umschaltschwelle, mit klaren Regeln, was behoben werden darf.
- (c) Nichts weiter.

<DS_INSTRUCTION>
Batch 249 - Silent Scope Decomp

Strang B, B-Batch 24 (B-SCHRITT 4/5 „Boot bis Hauptschleife“). Zweiter von DREI B-Batches der harten Zwischenprüfung (Nutzerentscheid 02.10.2026).
SOLL-KOEPFE: 0 (B-Batch, kein Kopfbau)

STAND UEBERNEHMEN:
- HEAD 3ca59c5, Baum sauber, gültiger `_preflight_248.txt` (SAUBER).
- `Hybrid-A4`: 181055466 Schritte | nativ 1511 (Kalibriersumme B231, KEIN Messwert) | Halt-PC 8000A164 | Halt-Art Form (`_preflight_248.txt:32@3ca59c5`).
- Der neue Halt liegt in `FUN_8000a110`, Wort 7528F000 = `andis. r8,r9,0xf000`. `port/hybrid/ppc_kern.cpp` kennt Op 24/25/26/28, aber nicht Op 27 (`xoris`) und nicht Op 29 (`andis.`) (`ppc_kern.cpp:343-352@3ca59c5`).
- `ab90` hat die PCI-Prüfung bestanden (1027 Proxy-Kommandos, `_m248/_proxy_protokoll.txt`). Seine Rückgabe und die Stufe von `be40` sind noch nicht beobachtet.
- Zwischenprüfung: Zählt nur, wenn der Halt-PC der Preflight-Zeile `Hybrid-A4` (Schalter wie in `_preflight_248.txt`) NICHT 8001684C ist UND `be40` über Stufe 5 hinauskommt. Eine Halt-Art „Form“ ist eine Lücke unseres Interpreters, kein Halt des Spiels. Halt nicht umdefinieren.

ARBEITSWEISE:
- Startroutine nach `AGENTS.md`.
- Vorhersage-Commit `B249: Vorhersage` VOR der ersten Änderung unter `port/`. Er nennt je Bilanzzeile Sollwert und Zählerdefinition, insbesondere:
  - `Hybrid-A4`: Halt-PC, Halt-Art,
  - Rückgabe von `ab90` und Stufe/Rückgabe von `be40`, wenn sie erreicht werden,
  - Formenzeile von `m227`.
  „Schritte bis Halt“ ist laut B248 §5b kein Fortschrittsmaß: nur nennen, nicht als Fortschritt werten.
- Strang-B-Maß (A4): Der Bericht nennt die ausgeführten Schritte UND den nativen Anteil. „nativ 1511“ wird ausdrücklich als „Kalibriersumme, kein Messwert“ beschriftet.
- Eigene Entscheidungen des Workers kommen als `ENTSCHEIDUNG (Worker): …` ins Dokument, nicht als „(Reviewer)“.
- Was behoben werden darf:
  1. eine fehlende Befehlsform, wenn sie in `m227_formen.py gruen` gegen Unicorn mit Abw 0 „gruen“ ist und eine Rotprobe hat (absichtlich falsche Fassung → Abw > 0, danach zurück);
  2. eine MMIO- oder Proxy-Antwort, wenn sie ROM-belegt ist (Leser-Adresse) und MAME-belegt (`Datei:Zeile`), mit Aus-Schalter oder Rotprobe; im Code als „Hybrid-Geruest, im Port zu ersetzen“ markiert.
  Alles andere wird nur gemessen und eingeordnet.
- Preflight-Dauer: Prüfe in `scripts/c_kopf.py` (`_interpreter_quelle`/`_mess_hash`), ob `port/hybrid/ppc_kern.cpp` dort eingeht.
  - Wenn ja, läuft der Profil-Cache kalt (B247: 1446 s). Plane den Abschluss so, dass der Preflight mit dieser Dauer vor der Umschaltschwelle fertig ist.
  - Dauer je Preflight-Gruppe ins Dokument.
- Preflight, `port_build` und `m227`/`c_kopf`-Läufe als normalen blockierenden Aufruf mit `timeout=1800000`.
- Rohwörter offline oder per `disassemble_function`. Kein `/disassemble_bytes` (R398).
- „Fehlt“ nur mit Grep auf den Bezeichner in `analysis/` und `port/`.

TEIL 1 - Inventar der Formlücken (nur messen, vor der Vorhersage):
- Dekodiere alle Wörter
  (a) der ausgeführten Menge (Abdeckungskarte, Index = adresse − 0x80000000) und
  (b) der statischen Rümpfe von `FUN_8000be40`, `ab90`, `ab0c`, `a7f4`, `a110` samt Primitiven `a32c`/`a07c`/`9ff8`/`9f60` und `b048`.
- Gleiche ab, welche Formen `ppc_kern.cpp` behandelt: primärer Opcode und bei 19/31/59/63 der erweiterte Opcode.
- Ausgabe `analysis/_m249/_formluecken.txt`: Form | Anzahl in (a) | Anzahl in (b) | erste Adresse | im Kern ja/nein.
- Summenzeile: Zahl der fehlenden Formen in (b) und in (a).

TEIL 2 - Op 27 `xoris` und Op 29 `andis.` einbauen:
- Semantik nach MAME `ppccom`/`ppc_ops` (`Datei:Zeile`). `andis.` setzt CR0.
- `m227_formen.py gruen` erweitern, sodass beide Formen geprüft werden. Danach „gruen“ mit Abw 0 und je eine ROT gewordene Rotprobe (z. B. `andis.` ohne CR0-Setzen).
- Hybrid-Lauf mit dem Preflight-Schaltersatz: neuer Halt-PC und Halt-Art. Gegenprobe `--k033906-aus` ergibt weiterhin 8001684C.
- Fehlen laut TEIL 1 weitere Formen in (b), dürfen sie im selben Zug nach derselben Regel eingebaut werden.

TEIL 3 - Halt weiter treiben (Schleife bis zur Umschaltschwelle):
- Je Durchgang:
  1. A4-Lauf messen.
  2. Halt einordnen (Form / MMIO / Proxy-Antwort / Schleife des Spiels / Fehlerweg), mit Disassembly der Haltstelle.
  3. Beheben, wenn die Regel in ARBEITSWEISE es erlaubt.
  4. Eine Zeile in `analysis/_m249/_haltfolge.txt`: Durchgang | Halt-PC | Art | Funktion | Behebung + Beleg | Rotprobe.
- Sobald beobachtbar, festhalten: Rückgabe von `ab90`, Rückgabe und Stufe von `be40`, Erreichen von `ab0c`. Für jede Leseadresse 0x2480000–0x2480093 die Zuordnung zum Voodoo-Register (`mame/…/voodoo*.cpp`, Zeile).
- Endet ein Durchgang an einer Stelle, die nach der Regel nicht behebbar ist, wird sie mit Grund und Beleg benannt. Danach die Messung abschließen, nicht weiter raten.

TEIL 4 - Herkunft der Zahl „nativ“ (nur Doku, kein Umbau):
- Wo wird `davon nativ 1511` berechnet (`Datei:Zeile@HEAD`) und was zählt sie?
- Was müsste eine echte Messung des nativen Anteils am Hybrid-Lauf zählen? Höchstens 10 Zeilen im Dokument, eingestuft als CONFIRMED oder HYPOTHESIS.

TEIL 5 - Abschluss:
- Genau ein gültiger Preflight (`_preflight_249.txt`). Ein Fehllauf wird mit Ursache archiviert.
- Bilanz, Memory-Export, Commit.
- Ankerkopf:
  - Zeile „Zwischenprüfung: B248 Halt-PC 8001684C→8000A164 (Form-Lücke); B249 [Halt-PC, Art, be40-Stufe]; B250 offen“,
  - „Nächster Schritt“ mit dem Übertrag `m53_pool.py:100` für den ersten C-Batch nach B250.

FERTIG WENN: `_formluecken.txt` mit Summenzeile + Op 27/29 eingebaut, „gruen“ in `m227` mit je einer ROT gewordenen Rotprobe + `_haltfolge.txt` mit mindestens einem Durchgang nach dem Einbau (neuer Halt-PC und Art belegt, Gegenprobe `--k033906-aus` = 8001684C) + Abschnitt TEIL 4 + genau ein gültiger Preflight + Bilanz + Ankerkopf mit Zwischenprüfungszeile.

STREICHREIHENFOLGE:
- Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat (bzw. die vorgezogene Abschlusszeit bei kaltem Cache), mit einer `Get-Date`-Zeile im Dokument.
- Reihenfolge:
  1. weitere Durchgänge in TEIL 3 über den ersten hinaus
  2. TEIL 4
  3. Formen aus TEIL 1 jenseits von Op 27/29
- NIE: TEIL 1, TEIL 2 samt Rotproben, erster Durchgang TEIL 3, Vorhersage, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Formlücken. FERTIG WENN: `_m249/_formluecken.txt` mit Spalten (a)/(b) und Summenzeile liegt vor.
2. Op 27/29. FERTIG WENN: `m227 gruen` zeigt beide Formen mit Abw 0, und je eine Rotprobe ist ROT belegt.
3. Erster Durchgang. FERTIG WENN: `_m249/_haltfolge.txt` nennt den Halt-PC und die Art nach dem Einbau; die Gegenprobe mit `--k033906-aus` ergibt 8001684C.
4. Abschluss. FERTIG WENN: gültiger `_preflight_249.txt` + `_m249/_bilanz.txt` + Ankerkopf mit Zwischenprüfungszeile und Übertrag für `m53`.
5. Herkunft „nativ“. FERTIG WENN: Abschnitt TEIL 4 mit `Datei:Zeile` steht im Dokument.
6. Weitere Durchgänge. FERTIG WENN: `_haltfolge.txt` endet an einer nach der Regel nicht behebbaren Stelle (mit Grund) oder an der Umschaltschwelle (mit `Get-Date`-Zeile).
</DS_INSTRUCTION>
