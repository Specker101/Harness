<TELEGRAM_SUMMARY>
Ergebnis: Die harte Zwischenprüfung endet mit NEIN. Der Halt-PC steht weiter bei 8001684C. Gemessen: Der erste Aufruf von `be40` gibt 0 zurück, der zweite 2. Er scheitert in `FUN_8000c3a8` mit 0x20000000 (geprüft: `_m250/_haltfolge.txt:54-55`). Dazu sind jetzt drei Diagnose-Schalter im Hybrid-Läufer und ein Zwischenspeicher für den A4-Lauf da; der Preflight dauert nur noch 10 min. Der Widerspruch Stufe 5 gegen 7 ist geklärt.
Bewertung: FERTIG WENN erreicht: ja. Zwei Mängel:
- Der Wirkungsbeleg „0,3 s nachher“ meint nur das Lesen aus dem Zwischenspeicher. Der Lauf selbst dauert weiter knapp 30 min (M250-3 stimmt).
- „`b3c4` nicht modelliert“ ist falsch; das Modell steht in `maschine.cpp:655-693` (M250-2 stimmt).
Kosten/Laufzeit: $0,16, 1 h 55 min, 73 Anfragen.
Nächster Batch: B251 ist ein C-Batch mit mindestens 150 referenzgleichen Insn und der neuen Spalte „Art“. Die Kopfzahl (5) ist nur Nebenzahl, weil das Insn-Ziel des Nutzers vom 02.10. Vorrang vor der Median-Regel hat.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 25 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
Insn je C-Batch: B244 15, B246 18, B247 14.
M250-2: übernommen als B251 TEIL 0 (Ankertext korrigieren) und als Voraussetzung, bevor B wieder aufgenommen wird; Wirkung noch nicht belegt -> offen
M250-3: übernommen als B251 TEIL 0 (Satz „Preflight entlastet, Lauf nicht beschleunigt“, Zustandsabzug als Voraussetzung); Wirkung noch nicht belegt -> offen
M250-4: übernommen als B251 TEIL 0 (Zeile 289 von `m60_inventar` ist richtig; geprüft); Wirkung noch nicht belegt -> offen
UEBERTRAG: 9 fehlende Befehlsformen -> Anker, Voraussetzungen für die Wiederaufnahme von B
ENTSCHIEDEN: Zurück zu C ohne Rückfrage (Nutzerentscheid). B ruht bis zum Ende der ausgeführten Menge.
ENTSCHIEDEN: Spalte „Art“, Reihenfolge und Insn je Art übernehme ich ab B251 (Nutzer-Nachricht vom 03.10.).
OFFENE FRAGE: Zur Information: Die erste Grafikkarten-Initialisierung läuft jetzt vollständig durch, gescheitert ist erst der zweite Aufruf. B ruht trotzdem wie vereinbart.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: „`b3c4` nicht modelliert“, obwohl `maschine.cpp:655-693` den Mailslot modelliert (M250-2).**
- (a) Fehlerklasse: Eine „fehlt“-Aussage wurde ohne Grep auf den Bezeichner getroffen. Das ist nach 0x40000000 und M242-1 schon der dritte Fall.
- (b) In B251 TEIL 0 wird die Aussage per Grep auf `0x780C0003` und `b3c4` korrigiert, mit Fundstelle. Jede „fehlt“-Aussage im B251-Dokument braucht eine Grep-Zeile.
- (c) Ob der Mitschnitt den zweiten Aufruf abdeckt (CG-Board 2?), wird erst bei der Wiederaufnahme von B gemessen.

**Befund 2: Wirkungsbeleg misst das Falsche (Lesen aus dem Zwischenspeicher statt Laufdauer, M250-3).**
- (a) Fehlerklasse: Die Messgröße passt nicht zum Messziel.
- (b) Im neuen Dokument steht die Richtigstellung. Die echte Beschleunigung (Zustandsabzug vor `be40`) kommt als Voraussetzung für die Wiederaufnahme in den Anker. Für die neuen Zählzeilen in B251 gilt dasselbe: Jede Zahl wird gegen eine unabhängige Nachrechnung geprüft.
- (c) In B251 wird nichts beschleunigt.

**Befund 3: Die Leserliste stuft eine korrekte Wortindizierung als Fehler ein (M250-4).**
- (a) Fehlerklasse: Die Verwendung einer Indexformel wurde nicht geprüft. `//4` ist bei einem ROM-Wortfeld richtig und nur bei der Abdeckungskarte falsch.
- (b) Jede Zeile „FALSCH“ der Leserliste bekommt die Angabe, welches Feld indiziert wird (Abdeckungskarte oder Wortfeld). Korrigiert wird nur, was die Abdeckungskarte liest.
- (c) Nichts weiter.

**Befund 4: Fortschritt in C seit B244 bei 14–18 Insn je Batch.**
- (a) Fehlerklasse: Die Auswahl richtete sich nach der Kopfzahl, nicht nach dem Umfang.
- (b) Neue Preflight-Zeile „referenzgleiche Insn“. Ausgewählt wird nach Insn und Art, mit Soll 150.
- (c) Ob 150 Insn je Batch bei eigenständigen Blättern überhaupt erreichbar sind, misst erst B251.

<DS_INSTRUCTION>
Batch 251 - Silent Scope Decomp

Strang C (C-Batch, ausgeführte Menge). Kein B-Batch: Die harte Zwischenprüfung B248–B250 endete mit NEIN. Nach dem Nutzerentscheid vom 02.10.2026 ruht B bis zum Ende der ausgeführten Menge.
SOLL-INSN: mindestens 150 neue referenzgleiche Insn, Ziel ~200 (Nutzerentscheid 02.10., hat Vorrang)
SOLL-KOEPFE: 5 (nur Nebenzahl; reichen 5 Köpfe für 150 Insn nicht, gilt das Insn-Soll)

STAND UEBERNEHMEN:
- HEAD 0ad8696, Baum sauber, gültiger `_preflight_250.txt`. C Köpfe 139/7748/0.
- Ausgeführte Menge: 1081/2076 Spannen. Spannen-Insn 69355, davon nicht referenzgleich 65052 (`_preflight_249.txt:21`). Die referenzgleiche Summe 4303 steht heute nur als Differenz da.
- Ergebnis der Zwischenprüfung: NEIN.
  - Erster Aufruf von `be40` = 0, zweiter = 2.
  - Zweiter Aufruf scheitert in `FUN_8000c3a8` mit 0x20000000.
  - Halt-PC 8001684C.
  - Beleg: `_m250/_haltfolge.txt:54-83@0ad8696`.
- NUTZER-NACHRICHT 03.10. (bindend):
  - Die Kandidatenliste bekommt eine Spalte „Art“ (Spiellogik / Hardware-Boot-Init / Menü-Service).
  - Einordnung nach Aufrufer, angesprochenen MMIO- bzw. Proxy-Adressen und Textbezug; im Zweifel Spiellogik.
  - Reihenfolge: erst Spiellogik und Menü/Service, Hardware/Boot-Init ans Ende (nicht streichen).
  - Im Bericht die Insn nach Art aufschlüsseln.
- NUTZER-NACHRICHT 02.10. (bindend): Insn-Soll ≥150, Ziel ~200. Köpfe unter 10 Insn nur als Beifang. Die Summe der neuen referenzgleichen Insn steht im Bericht.

ARBEITSWEISE:
- Startroutine nach `AGENTS.md`.
- Vorhersage-Commit `B251: Vorhersage` VOR jeder Änderung unter `port/` und `scripts/`. Er nennt Sollwert und Zählerdefinition je Bilanzzeile, insbesondere:
  - neue Zeile „referenzgleiche Insn“ vorher (4303) und nachher,
  - `327er-Pool` nach der Korrektur von `m53`,
  - Ersatzzahl,
  - Insn je Art.
- Die Werkzeugänderungen (Zählzeile, Art-Spalte, `m53`) betreffen Zählung und Auswahl, nicht den Prüfweg `vergl`/`mut`. Deshalb sind sie hier zusammen mit dem Kopfbau erlaubt (Reviewer-Entscheid).
- Je Kopf: `vergl` 0 + `mut` ROT in `_m251/`.
- Für `c_kopf.py`, `port_build` und den Preflight einen blockierenden Aufruf mit `timeout=1800000` verwenden, ohne Hintergrund und ohne Warten.
- „Fehlt“ nur mit Grep auf den Bezeichner in `analysis/` und `port/`, mit Fundstelle.
- Eigene Entscheidungen als `ENTSCHEIDUNG (Worker): …`.

TEIL 0 - Richtigstellungen (Dokument + Anker, keine alten Belege ändern):
- M250-2: Grep auf `0x780C0003` und `b3c4` in `port/hybrid/`. Ins B251-Dokument kommt: „Mailslot modelliert (`maschine.cpp:655-693@0ad8696`). Offen ist, ob der Mitschnitt (`sharc_folge.inc`, nur dsp2/CG-Board 1) den zweiten `be40`-Aufruf abdeckt.“
- M250-3: Satz „A4-Zwischenspeicher entlastet den Preflight. Der Lauf selbst ist nicht schneller (1640–1772 s je Lauf in B250).“
- M250-4: `analysis/_m251/_coverage_leser_korrektur.txt`. Je Zeile „FALSCH“ aus `_m248/_coverage_leser.txt`: welches Feld indiziert wird (Abdeckungskarte oder ROM-Wortfeld) und ob es wirklich falsch ist. `m60_inventar.py:289` ist RICHTIG (`W[k]`, Wortfeld).
- Ankerkopf, Abschnitt „Voraussetzungen für die Wiederaufnahme von B“:
  1. Zustandsabzug vor `be40`, um die Läufe zu verkürzen,
  2. Mailslot-Verlauf beim zweiten Aufruf von `c3a8` (erwartetes gegen geliefertes Byte, Board-Zuordnung),
  3. die 9 Formlücken aus `_m249/_formluecken.txt` (a).

TEIL 1 - Zählung und Auswahl:
- (a) M249-4: Die Preflight-Zeile `Ausgefuehrte Menge` (aus `m242_ausgefuehrt.py`) nennt ausdrücklich „referenzgleiche Insn <n>“. Gegenprobe: n = Spannen-Insn − nicht referenzgleich.
- (b) M249-5: Die Ersatzzahl „MAME-Coverage“ rechnet `m242` selbst und gibt sie in derselben Zeile oder einer eigenen aus. Abgleich gegen 3665/50636 (`_m247/_index_korrigiert.txt:6`): gleich oder Abweichung erklärt.
- (c) Spalte „Art“ in `_m251/_ausgefuehrt_kandidaten.txt`:
  - Regeln im Skriptkopf: Aufrufer-Kette zu bekannten Boot-/Init-Wurzeln (`be40`, CG-Init, Ladepfad), MMIO-/Proxy-Konstanten (0x78xxxxxx, 0x74xxxxxx, 0x7Dxxxxxx, 0x40000000 …), Textbezug zu Menü/Test/Service; sonst Spiellogik.
  - Summen offener Insn je Art.
  - Stichprobe: je Art 5 Einträge per `disassemble_function` von Hand geprüft, Ergebnis im Dokument.
- (d) `scripts/m53_pool.py:100`: `o = (a - BASE) >> 2` wird zu `o = a - BASE`, mit Grenztest (Anteil außerhalb = 0 %). Delta der Zeile `327er-Pool` und der Mitleser `m54`/`m58` laut Vorhersage.

TEIL 2 - Köpfe (Hauptarbeit, mindestens 150 Insn):
- Auswahl aus den Kandidaten der Art Spiellogik bzw. Menü/Service, größte zuerst, solange sie in die Batch-Uhr passen. Eigenständige Blätter bevorzugt.
- Köpfe unter 10 Insn nur als Beifang.
- Je Kopf `vergl` 0 + `mut` ROT (`_m251/_vergl_<adr>.txt`, `_mut_<adr>.txt`).
- Tafel im Dokument: Kopf | Art | Insn | `vergl` | `mut`. Dazu Summe gesamt und Summe je Art.
- Mit `vergl alle` belegen, dass alle Köpfe weiter gleich sind.

TEIL 3 - Abschluss:
- Genau ein gültiger Preflight (`_preflight_251.txt`), Bilanz, Memory-Export, Commit, Baum leer.
- Ankerkopf: Stand B251 (C), referenzgleiche Insn vorher/nachher, Insn je Art, Reihe „Insn je C-Batch: B244 15, B246 18, B247 14, B251 <n>“.

FERTIG WENN: mindestens 150 neue referenzgleiche Insn (Preflight-Zeile „referenzgleiche Insn“ zeigt das Delta) mit `vergl` 0 + `mut` ROT je Kopf + Spalte „Art“ mit Stichprobe + Ersatzzahl vom Werkzeug + Korrekturliste der Leser (TEIL 0) + Abschnitt „Voraussetzungen für die Wiederaufnahme von B“ im Anker + genau ein gültiger Preflight + Bilanz + leerer Baum.

STREICHREIHENFOLGE:
- Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat, mit einer `Get-Date`-Zeile im Dokument.
- Reihenfolge:
  1. Köpfe über 150 Insn hinaus
  2. TEIL 1 (d) Korrektur von `m53` (dann Übertrag in B252)
  3. TEIL 1 (b) Ersatzzahl
- NIE: TEIL 0, TEIL 1 (a) und (c), 150 Insn, Vorhersage, Preflight, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Richtigstellungen. FERTIG WENN: `_m251/_coverage_leser_korrektur.txt` liegt vor, M250-2 und M250-3 stehen als Sätze im Dokument, der Abschnitt „Voraussetzungen für die Wiederaufnahme von B“ steht im Anker.
2. Zählzeile. FERTIG WENN: der Preflight zeigt „referenzgleiche Insn <n>“; die Gegenprobe gegen die Differenz stimmt.
3. Art-Spalte. FERTIG WENN: `_m251/_ausgefuehrt_kandidaten.txt` hat die Spalte „Art“, Summen je Art und eine Stichprobe von 5 je Art im Dokument.
4. Köpfe. FERTIG WENN: neue referenzgleiche Insn ≥ 150, je Kopf `vergl` 0 + `mut` ROT, Tafel mit Insn je Art.
5. Abschluss. FERTIG WENN: gültiger `_preflight_251.txt` + `_m251/_bilanz.txt` + Ankerkopf mit Insn-Reihe + leerer Baum.
6. `m53`. FERTIG WENN: `m53_pool.py:100` liest den Byte-Index, Grenztest 0 %, Delta von `327er-Pool` wie vorhergesagt oder erklärt.
7. Ersatzzahl. FERTIG WENN: `m242` gibt die MAME-Coverage-Ersatzzahl aus; Abgleich mit 3665/50636 im Dokument.
</DS_INSTRUCTION>
