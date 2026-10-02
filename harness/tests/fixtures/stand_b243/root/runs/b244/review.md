<TELEGRAM_SUMMARY>
Ergebnis: Die Verteiler-Tafel von 800660D4 steht im ROM-Abbild (`_m243/_tafel_660D4.txt`). Die Blockade „nur per Live-Aufnahme“ war damit falsch, und die SDA-Basis in der Altdoku war ein Zahlendreher. Der Prüfstand kann jetzt eine Speicherzelle je Fall setzen. 80085408 ist bei 56 von 57 Blöcken, insgesamt sind 802 von 978 Blöcken erreicht. Alle Köpfe bleiben referenzgleich, 123/7148/0 (`_preflight_243.txt:16`).
Bewertung: FERTIG WENN ja. Die Fallrümpfe von 660D4 sind nicht portiert. Befunde:
- „Spannen-Insn 124316“ ist das ganze Programm, nicht die ausgeführte Menge.
- Anker und Altdoku tragen noch widerlegte Aussagen.
- 660D4 zählt als referenzgleich, obwohl der Körper fehlt.
- 3 Preflight-Läufe aus bekannten Ursachen, zusammen 45 % der Laufzeit.
Kosten/Laufzeit: $0,24, 104 min.
Nächster Batch: B244 = Phasenwechsel zur ausgeführten Menge. Gebaut werden 4 Köpfe aus den 840 nicht referenzgleichen, Blätter zuerst, die kleinsten voran.
B-SCHRITT: kein B-Batch (Strang C)
M243-1: übernommen als B244 TEIL 0 – offen
M243-2: Die Harness-Änderung kann ich nicht vornehmen; ich setze keine neue Abbruch-Marke. Frage R242-1 bleibt bei dir – offen
M243-3: übernommen als B244 TEIL 1a – offen
M243-4: übernommen als B244 TEIL 1b – offen
M243-5: übernommen: Phasenwechsel in B244 – offen
M243-6: übernommen. Pflichtschritte vor dem Preflight; ein Fehllauf aus bekannter Ursache zählt als Befund – offen
UEBERTRAG: Fallrümpfe 800660D4 -> Anker-Restposten „Rumpf offen“ (nicht ausgeführt, nach der ausgeführten Menge)
ENTSCHIEDEN: Köpfe mit offenem Rumpf zählen nicht als referenzgleich.
OFFENE FRAGE: Der Dauerbetrieb ist aus. Soll er nach der Harness-Korrektur (Abbruch-Marke nur einmal, Takt der Aussensicht senken) wieder an?
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Korrekturen landen nur im Batch-Dokument** (Anker `r1b-workstream.md:67-74` mit veraltetem „Nächster Schritt“; Offene Entscheidung (3) „Live-Aufnahme“ widerlegt; SDA2 `0x800ADABC` an 6 Stellen in `decompressed-ppc-analysis.md`; M243-1).
(a) Fehlerklasse: Neues wird angehängt, Widerlegtes nicht ersetzt.
(b) Verwandt sind alle Aussagen, die ein Batch widerlegt. Die Instruktion verlangt am Batch-Ende einen Grep auf jede widerlegte Aussage (Adresse oder Wortlaut) in `r1b-workstream.md`, `hybrid-plan.md` und `decompressed-ppc-analysis.md`. Treffer werden ersetzt, mit Verweis auf den Beleg; das Ergebnis des Greps kommt ins Dokument.
(c) Ältere Batch-Dokumente werden nicht nachgezogen; dort gilt `@commit`.

**F2 – Referenzgleich trotz fehlendem Körper** (800660D4, `ckopf_leaves.cpp:4440`; M243-3).
(a) Fehlerklasse: Der Vergleich ist gleich, weil beide Prüfwelten an derselben Stelle aufhören.
(b) Betroffen sind alle Köpfe mit `RUMPF_OFFEN_DEF` oder `host.disp`-Ausstieg innerhalb der eigenen Spanne. Sie kommen aus „referenzgleich“ heraus und erscheinen als „Rumpf offen“. Gegenprobe: 660D4 zählt nicht mehr. Daneben gilt „C verifiziert“ als Trendzahl.
(c) Andere Ausstiege (Host-Rufe auf fremde Funktionen) werden nicht geprüft; die sind Vertrag, kein Loch.

**F3 – Größenzahl über die falsche Menge** (`m242_ausgefuehrt.py:96`, Spannen über alle 2076; M243-4). Wiederholung von M242-4.
(a) Fehlerklasse: Die Summe läuft über die Grundmenge statt über die Zielmenge.
(b) Die Summe wird nur über ausgeführte Spannen und über ausgeführte, nicht referenzgleiche Spannen gebildet. Gegenprobe: Die Summe muss kleiner als 124316 und größer als 12171 sein.
(c) Den Abgleich mit dem Harness-Inventar (53535) prüft die Instruktion nur als Erklärungssatz.

**F4 – Preflight-Fehlläufe aus bekannter Ursache** (`port_gl` nicht neu gebaut, KeyError in der Bilanz; M243-6). Dieselbe Ursache wie in B237.
(a) Fehlerklasse: Vorab prüfbare Bedingungen werden nicht vorab geprüft.
(b) Vor dem Preflight sind Pflicht: `port_build.ps1` und `port_build.ps1 -Gl`, außerdem ein Trockenlauf des Parsers `m149_bilanz.m_preflight` auf `_preflight_243.txt` plus die neuen Zeilen, ohne Exception und mit allen ORDER-Schlüsseln. Ein Fehllauf aus diesen Ursachen gilt als Befund.
(c) Fehlläufe aus neuen Ursachen werden nicht verhindert.

**Prüfpunkt a:** Ab jetzt misst C an der Zielzahl „ausgeführt referenzgleich“ (69/909); die Kopfzahl 123 ist die Gesamtzahl. „Spannen-Insn“ ist bis zur Korrektur eine Ersatzzahl.
**Prüfpunkt b:** Die B242-Blockade war falsch. Belegt ist das per Lesen der Zelle (`_m243/_tafel_660D4.txt`).

<DS_INSTRUCTION>
Batch 244 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD 5c8345f, Arbeitsbaum sauber. Gültiger Preflight `analysis/_preflight_243.txt`.
- C Köpfe 123/7148/0, C verifiziert 92.
- Ausgeführte Menge 909, referenzgleich 69, nicht referenzgleich 840 (`:21`).
- Tafel von 800660D4 bekannt (`_m243/_tafel_660D4.txt`); die Fallrümpfe sind nicht portiert.
- Strang B ruht.
- **B244 ist der Phasenwechsel:** C-Batch auf der ausgeführten Menge (Nutzerrahmen 01.10. Punkt 2).
- SOLL-KOEPFE: 4 (Median 3, höchstens 1,3-fach).

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Erst `B244: Vorhersage` committen (leere `git status --porcelain port/ scripts/`), dann Änderungen unter `port/` und `scripts/`.
- Lange Aufrufe blockierend mit `timeout=1800000`.
- Keine neue `.py` unter `analysis/`.
- **Pflicht vor dem einen Preflight (M243-6):**
  1. `scripts\port_build.ps1` und `scripts\port_build.ps1 -Gl`;
  2. Parser-Trockenlauf: `python -c` mit Import von `m149_bilanz`, `m_preflight()` auf den Text von `_preflight_243.txt` plus jeder neuen oder geänderten Zeile. Keine Exception, alle ORDER-Schlüssel gefunden. Ausgabe nach `_m244/_parser_trocken.txt`.
  - Ein Fehllauf aus einer dieser Ursachen ist ein Befund.
- **Widerlegtes wird ersetzt, nicht ergänzt.**
- Nutzer- und Reviewerentscheide wortgetreu übernehmen; Urteile binär.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.

TEIL 0 – Doku korrigieren (M243-1), nur `analysis/`:
- Ankerkopf:
  - „Nächster Schritt“ auf B244 setzen;
  - die erledigte Zeile „OFFEN (M242-1): ORDER kennt Hybrid-A4 nicht“ entfernen;
  - Offene Entscheidung (3) (Live-Aufnahme der Tafel) mit **GESCHLOSSEN** führen, Beleg: „Tafel im Abbild, `_m243/_tafel_660D4.txt`“.
- Reviewer-Entscheidung wortgetreu: „Köpfe mit offenem Rumpf (fehlender Körper innerhalb der eigenen Spanne) zählen nicht als referenzgleich; sie werden als ‚Rumpf offen‘ geführt (Reviewer B243).“
- Restposten im Anker: „800660D4 Fallrümpfe (106 Insn), nicht ausgeführt, nach der ausgeführten Menge“.
- `decompressed-ppc-analysis.md`: SDA2 `0x800ADABC` → `0x800ADA5C` an allen Stellen (Zeilen 80, 82, 87, 102, 104, 209 laut M243-1; per Grep prüfen), mit Verweis `_m243/_tafel_660D4.txt`.
- Danach muss Grep `800ADABC` über `analysis/*.md` leer sein, ausgenommen Batch-Dokumente.
- Commit `B244: TEIL 0`.

VORHERSAGE: je Bilanzzeile ein Soll mit Definition, besonders: C referenzgleich (nach TEIL 1a, ohne Rumpf-offen-Köpfe), ausgeführt referenzgleich, die Spannen-Insn aus TEIL 1b.

TEIL 1 – Zählung (klein, vor den Köpfen):
- a) **(M243-3)** Köpfe mit `RUMPF_OFFEN_DEF` (mindestens 800660D4) aus „referenzgleich“ herausnehmen und als „Rumpf offen n“ in der C-Zeile und in „Ausgefuehrte Menge“ führen. Gegenprobe: 660D4 erscheint dort und nicht unter referenzgleich.
- b) **(M243-4)** In `m242_ausgefuehrt.py` die Spannen-Insn nur über die 909 ausgeführten Spannen bilden und zusätzlich über die nicht referenzgleichen ausgeführten. Gegenprobe: 12171 < Wert < 124316. Ein Satz zum Unterschied gegenüber dem Inventar.

TEIL 2 – Köpfe aus der ausgeführten Menge:
- Liste der nicht referenzgleichen, ausgeführten Funktionen, **Blätter zuerst, kleinste zuerst**, nach `_m244/_ausgefuehrt_kandidaten.txt`. Schon gebaute, aber nicht referenzgleiche Köpfe zuerst prüfen.
- 4 Köpfe bauen. Je Kopf:
  - Ghidra-Dekompilat und Disassembly, `rumpf_end`;
  - Port, Registry, KOPF_DEF, MUT, Fall-Datei;
  - `_m244/_vergl_<k>.txt` mit 0 Abweichungen, `_m244/_mut_<k>.txt` ROT;
  - Bahnabdeckung „ohne Begründung“ 0, oder erreicht mit begründetem Rest. Keine neuen Einträge „Prüfstand kann nicht erzeugen“ ohne ROM-Stelle.
- Live-Lage je Kopf: KOPFWEIT im 200M-Lauf oder „nicht ausgeführt“.

BATCH-ENDE:
- Pflichtschritte aus ARBEITSWEISE.
- Preflight einmal: `python -u scripts/preflight.py before *> analysis/_preflight_244.txt`, blockierend mit `timeout=1800000`.
- Zeilendiff zu `_preflight_243`, mit Erklärung je Zeile.
- Bilanz mit `--write-anchor` nach `analysis/_m244/_bilanz.txt`.
- Grep-Liste der in diesem Batch widerlegten Aussagen gegen Anker/Plan/Altdoku, mit Ergebnis im Dokument.
- Memory-Export, Commit.
- Ankerkopf `**Stand:** BATCH 244` mit Grep-Beleg und `git status --porcelain` leer.

FERTIG WENN: 4 Köpfe aus der ausgeführten Menge mit `vergl` 0 + `mut` ROT UND „Ausgefuehrte Menge … referenzgleich“ ≥ 73 UND 660D4 wird als „Rumpf offen“ gezählt, nicht als referenzgleich UND die Spannen-Insn liegt im Gegenprobenbereich UND Grep `800ADABC` (ohne Batch-Dokumente) ist leer UND `_m244/_parser_trocken.txt` liegt vor UND genau ein gültiger Preflight + `_m244/_bilanz.txt` liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. Köpfe 3 und 4.
2. Live-Lage.
NIE streichen: TEIL 0, Vorhersage, TEIL 1a/1b, Köpfe 1 und 2, Pflichtschritte vor dem Preflight, Preflight, Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku. FERTIG WENN: Der Ankerkopf trägt „Nächster Schritt B244“, (3) ist GESCHLOSSEN, die Reviewer-Entscheidung steht wortgetreu, und Grep `800ADABC` (ohne Batch-Dokumente) ist leer.
2. Vorhersage. FERTIG WENN: `B244: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/`.
3. Zählung. FERTIG WENN: 660D4 steht unter „Rumpf offen“, und die Spannen-Insn der ausgeführten Menge liegt zwischen 12171 und 124316 (Gegenproben im Dokument).
4. Köpfe 1 und 2. FERTIG WENN: je `vergl` 0 und `mut` ROT in `_m244/`.
5. Köpfe 3 und 4. FERTIG WENN: je `vergl` 0 und `mut` ROT in `_m244/`.
6. Preflight und Bilanz. FERTIG WENN: `_m244/_parser_trocken.txt` liegt vor, es gibt genau einen gültigen Preflight ohne Fehllauf aus bekannter Ursache, und `_m244/_bilanz.txt` liegt vor.
</DS_INSTRUCTION>
