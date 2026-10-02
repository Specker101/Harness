<TELEGRAM_SUMMARY>
Ergebnis: B242 hat die Teilprüf-Zählung repariert. Sie zählt jetzt die gebauten Köpfe: C 123, davon 31 teilgeprüft, 126 Blöcke ohne Begründung (`_preflight_242.txt:16`). 800859E8 ist zu 100 % geprüft. Neu ist die Zeile „Ausgefuehrte Menge“: 909 Funktionen, davon 69 referenzgleich (`:21`). Die Fallrümpfe von 800660D4 sind als blockiert gemeldet.
Bewertung: FERTIG WENN nein, weil Posten 6 (Fallrümpfe) offen ist. Befunde:
- Die Blockade „Tafel nur per Live-Aufnahme“ ist nicht geprüft: die SDA-Zelle im ROM-Abbild, der Hybrid-Speicher und eine Rohsuche nach dem Wort fehlen (M242-1).
- Bei 80085408 kommt „0 ohne Begründung“ zu 34 von 42 Blöcken durch Umbeschriften zustande (M242-2). Meine Regel aus B241 hat das zugelassen.
- Die Insn-Zahl der ausgeführten Menge zählt nur ausgeführte Wörter, nicht die Funktionsgröße (M242-4).
- Die Bilanz liegt als `_bilanz_242.txt` statt `_bilanz.txt`; für B241 fehlt sie ganz.
Kosten/Laufzeit: $0,20, 66 min, Preflight 1396 s.
Nächster Batch: B243 (C, 0 neue Köpfe), Prüfstand-Erweiterung mit einer Speicherzelle je Fall.
B-SCHRITT: kein B-Batch (Strang C)
M242-1: übernommen als B243 TEIL 1 – offen
M242-2: übernommen. Paket E gilt als gebaut; der Prüfstand-Rest läuft als eigene Restzahl und wird in B243 TEIL 2 abgebaut – offen
M242-3: Bilanz-Dateiname übernommen als B243 BATCH-ENDE. Der Median im Harness ist deine Sache – offen
M242-4: übernommen als B243 TEIL 3 – offen
M242-5: Harness-Sache, siehe Frage – offen
UEBERTRAG: B242-Posten 6 (Fallrümpfe 800660D4) -> B243 TEIL 1+2
ENTSCHIEDEN: Paket E = alle echten Köpfe gebaut und referenzgleich. Teilgeprüft/Prüfstand-Rest wird getrennt geführt und blockiert den Phasenwechsel nicht.
OFFENE FRAGE: Eine Abbruch-Marke hat die Aussensicht dreimal ausgelöst, das Kontingent steht bei 86 % (Reset 06.10.). Bitte im Harness auf einmal je Review begrenzen und den Takt senken? Vorschlag: ja.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – „Material fehlt“ ohne Suche im Abbild** (800660D4, `port-batch242-…md:277-288`; M242-1). Dieselbe Klasse wie `0x40000000` (Prüfpunkt b).
(a) Fehlerklasse: Eine Blockade wird aus fehlenden Ghidra-Xrefs abgeleitet, ohne das Datenwort selbst zu lesen.
(b) Verwandt sind alle Lückenbegründungen mit „RAM-Tafel“ oder „nur live“. Die Instruktion verlangt je Fall drei Wege mit Ergebnis: Wort im ROM-Abbild lesen, Hybrid-Speicher nach dem Boot, Rohsuche nach dem Zielwort im ROM. Erst wenn alle drei leer sind, gilt „Material fehlt“.
(c) Ob die Tafel zur Laufzeit umgeschrieben wird, prüft die Instruktion nur über den Hybrid-Speicher, nicht über eine Schreibüberwachung.

**F2 – Erledigt durch Umbeschriften** (80085408: 34 von 42 Blöcken nach „Prüfstand kann nicht erzeugen“; M242-2). Die Ursache ist meine B241-Regel: „ohne Begründung 0“ war erreichbar, indem man eine Klasse vergibt.
(a) Fehlerklasse: Die Zielzahl lässt sich durch eine Kategorie statt durch Arbeit erreichen.
(b) Verwandt sind alle Klassen in `_luecken_begruendet.txt`. Ab B243 zählt „Prüfstand kann nicht erzeugen“ als **offene Restzahl**, nicht als erledigt, in einer eigenen Spalte der C-Zeile. Erfolg zeigt sich nur daran, dass die Zahl **erreichter** Blöcke steigt.
(c) Ob einzelne Begründungen sachlich stimmen, wird nur stichprobenartig geprüft (3 je Kopf).

**F3 – Zielzahl misst eine andere Größe** („12171 Insn“ = ausgeführte Wörter, nicht der Funktionsumfang; M242-4).
(a) Fehlerklasse: Der Nenner beziehungsweise die Größeneinheit einer Phasenzahl ist nicht definiert.
(b) Die Zeile bekommt zusätzlich die Insn-Summe der vollen Spannen und den Rest „nicht referenzgleich / nicht voll verifiziert“. Die Definition „ausgeführt“ steht im Dokument.
(c) Den Abgleich mit der Harness-Zahl 1086 leistet die Instruktion nicht; das ist Harness-Sache.

**F4 – Bilanzdatei uneinheitlich benannt** (`_bilanz_242.txt`, B241 ohne Datei; M242-3).
(a) Fehlerklasse: Kanonische Dateinamen werden nicht eingehalten.
(b) Ab B243 heißt die Datei `_m<N>/_bilanz.txt`; geprüft wird per Glob im Dokument.
(c) B241 wird nicht nachgeholt, weil die Bilanz einen frischen Preflight braucht.

**Prüfpunkt a:** Das C-Ziel sind die referenzgleichen Köpfe (123, in B242 unverändert, SOLL 0). Die Phasenzahl „ausgeführt referenzgleich 69/909“ ist die neue Zielgröße; „Insn“ darin ist bis TEIL 3 eine Ersatzzahl.

<DS_INSTRUCTION>
Batch 243 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD 2ddba14, Arbeitsbaum sauber. Gültiger Preflight `analysis/_preflight_242.txt`.
- C Köpfe 123/7138/0, davon teilgeprüft 31 / 126 Blöcke ohne Begründung (`:16`). Ausgeführte Menge 909/2076, referenzgleich 69 (`:21`).
- 800660D4: Rumpf offen 106 Insn; Verteiler `[SDA(0x518)]+0x108+index*4`, `bctr`.
- Das Case-Format setzt keine Speicherzelle je Fall.
- Strang B ruht.
- B243 ist ein **C-Batch (Strang C)**. SOLL-KOEPFE: 0 (Prüfstand und Abdeckung statt neuer Köpfe).

ENTSCHEIDUNG (Reviewer, wortgetreu ins Batch-Dokument und in den Ankerkopf):
„Paket E gilt als abgeschlossen, wenn alle echten Paket-E-Köpfe gebaut und referenzgleich sind (erreicht in B241/B242). Teilgeprüfte Blöcke, ‚Prüfstand kann nicht erzeugen‘ und ‚Rumpf offen‘ werden als eigene Restzahl geführt, gelten NICHT als erledigt und blockieren den Phasenwechsel nicht. Erfolg bei dieser Restzahl ist nur ein Anstieg der erreichten Blöcke, keine Umklassifizierung.“

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Erst `B243: Vorhersage` committen (leere `git status --porcelain port/ scripts/`), dann Änderungen unter `port/` und `scripts/`.
- Preflight genau einmal am Ende. Zwischenprüfungen nur über Einzelgruppen.
- Lange Aufrufe blockierend mit `timeout=1800000`.
- Keine neue `.py` unter `analysis/`.
- Nutzer- und Reviewerentscheide werden wortgetreu übernommen. Urteile nur „erfüllt“ oder „nicht erfüllt + Grund“.
- **Keine Umklassifizierung von Lücken in diesem Batch**, außer von „Prüfstand kann nicht erzeugen“ zu „erreicht“.
- Jede neue Kennzahl braucht eine Gegenprobe mit einem bekannten Positivfall.

TEIL 0 – Doku (nur `analysis/`):
- Die Entscheidung oben eintragen.
- Ankerposten zur Live-Aufnahme der Tafel von 800660D4 auf „ruht bis B243 TEIL 1“ setzen.
- Commit `B243: TEIL 0`.

VORHERSAGE: je Bilanzzeile ein Soll mit Definition; Soll für „erreichte Blöcke gesamt“ (heute aus der Bahnabdeckung).

TEIL 1 – Verteiler-Tafel von 800660D4 (M242-1), alle drei Wege:
- a) Die SDA-Basis aus `decompressed-ppc-analysis.md:80-88` und `ckopf_leaves.cpp:23` abgleichen; welche gilt? Dann das Wort an SDA+0x518 im dekomprimierten Abbild lesen (`read_memory` oder Worttafel) und, wenn es ein Zeiger ist, die acht Wörter an Zeiger+0x108.
- b) Hybrid-Läufer bis 200M: dieselben Zellen aus dem Speicher ausgeben (vorhandene Speicher-Ausgabe oder ein kleiner Schalter).
- c) Rohsuche im ROM-Abbild nach den Wörtern `8006612C` und den übrigen Fallrumpf-Adressen.
- Ergebnis als `_m243/_tafel_660D4.txt`, mit Urteil „Tafel bekannt (Quelle)“ oder „alle drei Wege leer“. Nur im zweiten Fall bleibt die Live-Aufnahme eine Materialfrage.

TEIL 2 – Prüfstand: Speicherzelle je Fall:
- Das Case-Format (`scripts/c_kopf.py`, `port/src/c_kopf_drv.cpp`) bekommt MEM-Setzungen je Fall, in beiden Welten gleich.
- Regression: alle 123 Köpfe `vergl` 0, kalter Profil-Lauf mit „abweichend 0“.
- Anwenden:
  - a) auf 800660D4, wenn TEIL 1 die Tafel liefert: Fallrümpfe nativ portieren, Fälle je Index, `vergl` 0, Rotprobe auf einen Fallrumpf ROT;
  - b) auf die Köpfe mit „Prüfstand kann nicht erzeugen“, größte Gewinne zuerst, beginnend mit 80085408.
- Messen: erreichte Blöcke gesamt vorher/nachher und „Prüfstand kann nicht erzeugen“ vorher/nachher (`_m243/_pruefstand_delta.txt`).
- Die C-Zeile führt „Prüfstand kann nicht erzeugen k“ als eigene Restzahl. Gegenprobe: 80085408 wird mitgezählt.

TEIL 3 – Ausgeführte Menge präzisieren (M242-4):
- Die Zeile ergänzen um: Insn der vollen Spannen, Rest „nicht referenzgleich“ und Rest „referenzgleich aber teilgeprüft“.
- Die Definition „ausgeführt“ (Quelle, Phase, Spannenregel) und den Nenner 2076 gegen 2087 (Gesamtzeile) in je einem Satz.

TEIL 4 – Bilanz-Anzeige:
- `m149_bilanz.ORDER` um `Hybrid-A4` und `Ausgefuehrte Menge` ergänzen.
- Die `\s{2,}`-Muster für Werte über 56 Zeichen reparieren.
- Gegenprobe: Beide Zeilen erscheinen in der Bilanz.

BATCH-ENDE:
- Preflight einmal: `python -u scripts/preflight.py before *> analysis/_preflight_243.txt`, blockierend mit `timeout=1800000`.
- Zeilendiff zu `_preflight_242`, mit Erklärung je geänderter Zeile.
- Bilanz mit `--write-anchor`; die Datei heißt **`analysis/_m243/_bilanz.txt`** (Glob-Beleg im Dokument).
- Memory-Export, Commit.
- Ankerkopf `**Stand:** BATCH 243` mit Grep-Beleg und `git status --porcelain` leer.

FERTIG WENN: `_m243/_tafel_660D4.txt` enthält alle drei Wege mit Urteil UND das Case-Format kann MEM je Fall (alle 123 Köpfe `vergl` 0, kalter Profil-Lauf abweichend 0) UND die erreichten Blöcke gesamt sind gestiegen (`_m243/_pruefstand_delta.txt`) UND die C-Zeile führt „Prüfstand kann nicht erzeugen“ als Restzahl UND `_m243/_bilanz.txt` + genau ein gültiger Preflight liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. TEIL 4.
2. TEIL 2b über 80085408 hinaus.
3. TEIL 3.
NIE streichen: TEIL 0, Vorhersage, TEIL 1, TEIL 2 (Format + Regression + 80085408), Preflight, Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku und Vorhersage. FERTIG WENN: Die Reviewer-Entscheidung steht wortgetreu im Anker, und `B243: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/`.
2. Tafel. FERTIG WENN: `_m243/_tafel_660D4.txt` enthält die Wege a, b und c mit Ergebnis und das Urteil.
3. Prüfstand-Format. FERTIG WENN: MEM je Fall wirkt in beiden Welten, alle 123 Köpfe haben `vergl` 0, und der kalte Profil-Lauf ist abweichend 0.
4. Abdeckung. FERTIG WENN: `_m243/_pruefstand_delta.txt` zeigt mehr erreichte Blöcke für 80085408 (und 800660D4, falls die Tafel bekannt ist).
5. Ausgeführte Menge. FERTIG WENN: Die Zeile nennt Spannen-Insn und beide Reste, und die Definition steht im Dokument.
6. Bilanz-Anzeige. FERTIG WENN: `Hybrid-A4` und `Ausgefuehrte Menge` erscheinen in `_m243/_bilanz.txt`.
</DS_INSTRUCTION>
