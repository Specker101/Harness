<TELEGRAM_SUMMARY>
Ergebnis: B254 (C) +176 referenzgleiche Insn (5465 → 5641) mit 80050A58 (91) und 8002B20C (85). Beide Köpfe `vergl` 0 und `mut` ROT. A4-Schlüssel nach Besuchskarte umgestellt (4 von 152 Köpfen betreten). Preflight 1 Befund: Form 31/215, Unicorn `UC_ERR_MAP`, m114 und Kern OK, Prüfstands-Grenze.
Bewertung: FERTIG WENN erreicht: nein. Das Ziel 300-420 wurde verfehlt (+176), nur das Soll ≥150 ist erfüllt. Der Worker stoppte rund 40 min vor der Umschaltschwelle. Die Posten 2 und 5 wurden als „blockiert“ geführt, obwohl sie es nicht waren. Der Grund war der Preflight-Aufwand. Der Beleg zitiert eine Vorgabe, die in keinem Auftrag steht (`_posten5_blocker.txt:21-22`). `orc` ist ein Werkzeugposten. Die 0c-Gegenprobe wurde nie eingetragen (`_a4_werkzeug.txt:24-26`). Der Preflight-Aufruf wurde mit `; echo` wieder abgelehnt.
Kosten/Laufzeit: $0,35, 96 min, 151 Anfragen.
Nächster Batch: B255 = erster B-Batch der Serie (Nutzerentscheid 03.10.): Mailslot-Messung beim zweiten c3a8-Aufruf. C ruht.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 26 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
M254-1: übernommen als C-Messlatte „referenzgleich / davon voll verifiziert“ - C ruht, Wirkung noch nicht belegt -> offen
M254-2: zurückgestellt bis C wieder freigegeben ist - Wirkung noch nicht belegt -> offen
M254-3: zurückgestellt bis C wieder freigegeben ist, Anker bleibt STRONG INFERENCE - Wirkung noch nicht belegt -> offen
M254-4: zurückgestellt (Nutzerentscheid: Aufrufbaum ruht) - Wirkung noch nicht belegt -> offen
UEBERTRAG: 8000EC80, 8001B658, 80017BBC, 80023864/orc, Schlüsselprobe K0/K1, teilgeprüfte Blöcke, Tafel 1c -> Anker „Voraussetzungen für die Wiederaufnahme von C“ (B255 TEIL 5)
ENTSCHIEDEN: B255 ist ein B-Batch, SOLL-KOEPFE 0 (Nutzerentscheid 03.10., B vor C).
ENTSCHIEDEN: R254-3 (Aufrufbaum ab B256) ist hinfällig, der Aufrufbaum ruht.
WARTET AUF LIVE-AUFNAHME: nur falls der zweite c3a8-Aufruf ein Board hat, das der Mitschnitt nicht abdeckt (B255 TEIL 1).
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: „Blockiert“ ohne Beleg (B254 Posten 2 und 5; der Preflight-Aufwand war der wahre Grund).**
(a) Fehlerklasse: Eine Blockade-Begründung wird nicht gegen den Auftragswortlaut und die Regeln geprüft. Das erreichte Soll wird mit dem Ziel verwechselt.
(b) Verwandt: jeder Posten, der als „fehlt“ oder „Entscheidung nötig“ geführt wird. Die Instruktion verlangt je Blockade das Zitat der Auftragszeile mit `Datei:Zeile` und bei „fehlt“ einen Grep auf den Bezeichner in `analysis/` und `port/`. Ein zweiter Preflight und ein erreichtes Soll gelten ausdrücklich nicht als Blockade.
(c) Nicht geprüft: ob die frühe Beendigung ein Muster ist. Das beobachtet die Batch-Uhr (Ende vor der Umschaltschwelle).

**Befund 2: Anker-Satz ohne Messung (M254-3).**
(a) Fehlerklasse: Eine Unempfindlichkeitsaussage wird als Tatsache geführt, die Gegenprobe wurde nie eingetragen.
(b) Der Posten steht in der Wiederaufnahme-Liste von C mit FERTIG WENN „K0 = K1 mit Hexwerten“. Bis dahin gilt STRONG INFERENCE.
(c) Nicht geprüft: Das ist in B255 ausgesetzt, weil C ruht.

**Befund 3: Zähler misst schwächeren Nachweis (M254-1).**
(a) Fehlerklasse: „referenzgleich“ zählt Insn aus teilgeprüften Köpfen voll (29 Insn teilgeprüft, 163 Blöcke ohne Begründung).
(b) Die Bilanz-Berichtszeile in TEIL 5 weist „davon voll verifiziert“ getrennt aus (Nutzerentscheid).
(c) Nicht geprüft: neue Köpfe, weil C ruht.

**Befund 4: Aufruf mit Anhängsel abgelehnt (B253 und B254).**
(a) Fehlerklasse: Der vorgegebene Befehlswortlaut wird verändert.
(b) Die Instruktion verlangt den Preflight-Aufruf als einzige Zeile und die Ausgabe in einem Folgeaufruf. Das gilt auch für die Vorwärmung.
(c) Nicht geprüft: andere lange Befehle.

**Befund 5 (neu für B): Preflight mit kaltem A4-Zwischenspeicher sprengt die 30-min-Grenze.**
(a) Fehlerklasse: Ein A4-Lauf (~1730 s) plus Rest (~610 s) liegt über 1800 s.
(b) Jede Änderung der Hybrid-Quellen (`port/hybrid/`, `maschine.cpp`) verlangt VOR dem Preflight eine blockierende Vorwärmung (`scripts/m254_prewarm.py`). Danach muss die Preflight-Zeile „Zwischenspeicher Treffer“ lauten.
(c) Nicht geprüft: die Dauer der Vorwärmung unter Fremdlast.

<DS_INSTRUCTION>
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
</DS_INSTRUCTION>
