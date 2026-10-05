<TELEGRAM_SUMMARY>
Ergebnis: B253 (Strang C) +461 referenzgleiche Insn (5004 → 5465), +3 Köpfe (146 → 149): 80029A50 (175), 800619EC (160), 8004F5A4 (126). Je Kopf `vergl` 0 und `mut` ROT. Preflight sauber, 593 s (B252: 1301 s), `_preflight_253.txt` Z.21. Vorhersage 5465 und MAME 4825 exakt getroffen. Insn je Art: Spiel 581 / Menü 71 / Boot 0.
Insn-Reihe je C-Batch: B244 15, B246 18, B247 14, B251 510 (255 Zweitkopie), B252 191, B253 461.
Bewertung: FERTIG WENN erreicht: ja (≥150, Ziel 200-260 übertroffen). Marker-Befund aus B252 behoben (Bericht und Maschinenmarker stimmen). Befunde: (1) 4 von 150 Köpfen werden in A4 betreten, alle alt (`_a4_besuchskarte.txt`), trotzdem blieb der Cache-Schlüssel an den Exe-SHA gebunden (`port-batch253…md:165-172`). Ergebnis: 1713 s Vorwärmung je Batch, ein Drittel der Laufzeit. (2) Fehllauf des Preflights, weil `m193_head.exe` veraltet war. (3) Ein Preflight-Aufruf mit Pipe wurde abgelehnt. (4) Die eigenständigen Blätter gehen zur Neige (nach 77 Insn kommen 57, 57, 52 …).
Kosten/Laufzeit: $0,21 (gerechnet), 97 min, 111 Anfragen, Werkzeuge 87 % der Zeit (Vorwärmung 1713 s, Preflight 3 Läufe).
Nächster Batch: B254, C. Zuerst Cache-Schlüssel nach Besuchskarte, dann Blätter 80050A58/8002B20C/8000EC80/80023864, danach Messung „Köpfe mit nativen Callees“.
B-SCHRITT: kein B-Batch (Strang C)
M250-3: übernommen als 0a-Karte + Vorwärmskript im Repo - Wirkung noch nicht belegt (Vorwärmung weiter 1713 s, Schlüssel unverändert) -> offen
UEBERTRAG: Nachrückposten 5 (Blätter 80050A58/8002B20C/8000EC80/80023864) -> B254 TEIL 2
UEBERTRAG: Boot-Init 80013A88 (190) -> Anker „Naechster Schritt“, nach den Spiellogik-/Menü-Blättern
UEBERTRAG: Schlüssel-Frage (Vorwärmung vermeiden) -> B254 TEIL 0
ENTSCHIEDEN: Schlüssel-Granularität nach Besuchskarte statt nach Datei (B254 TEIL 0, mit Rückfall auf Vorwärmung).
ENTSCHIEDEN: SOLL-KOEPFE 6 als Nebenzahl, Insn-Ziel 300-420.
OFFENE FRAGE: ~53643 Rumpf-Insn offen, ~268 Batches bei 200 Insn je Batch. Soll nach den Blättern auf Funktionen mit Aufrufbaum umgestellt werden? Die Messung dazu steht in B254 TEIL 3.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Cache-Schlüssel auf Datei- statt Nutzungsebene.**
(a) Fehlerklasse: Eine Ersatzgröße (Exe-SHA, `ckopf_leaves.cpp` komplett) sperrt den Zwischenspeicher, obwohl nur ein winziger Teil (4 von 150 Köpfen) benutzt wird. Die Folge ist ein fester Aufwand von ca. 29 min je Batch.
(b) Verwandt: jeder Zwischenspeicher oder Prüfpfad mit Exe-SHA im Schlüssel (`scripts/m212_zeilen.py:317`). Die Instruktion verlangt den Schlüssel nach Besuchskarte und einen Gegenbeleg: Preflight-Zeile „Zwischenspeicher Treffer“ OHNE neuen A4-Lauf nach dem Hinzufügen neuer Köpfe, A4-Zeile identisch (696571792/8001684C). Für jeden neuen Kopf gilt eine Tafel „Eintritts-PC ∈ Besuchskarte: ja/nein“; „ja“ erzwingt Cache-Miss.
(c) Nicht geprüft: ob die Besuchskarte die vollständige PC-Menge des A4-Laufs ist. Das ist Teil des Belegs in TEIL 0. Eine volle A4-Wiederholung mit Exe-SHA bleibt als Stichprobe offen (B258).

**Befund 2: Fehllauf durch veraltetes Harness-Binary (`m193_head.exe`).**
(a) Fehlerklasse: Vorbedingung des Preflights (alle untracked Binaries frisch) ist nicht mechanisch geprüft (R367).
(b) Verwandt: `port_selftest.exe`, `port_gl.exe`, `hybrid_lauf.exe`, `ppc_poc.exe`. Die Instruktion legt den Bauaufruf fest (`mingw32-make all gl hybrid head193`) und lässt `_m254/_binary_quellen.txt` mit Zeitstempel je Binary gegen Quellen vor dem Preflight schreiben (Grep: kein Binary älter als seine Quelle).
(c) Nicht geprüft: ob weitere Binaries außerhalb der Liste existieren.

**Befund 3: Preflight-Aufruf mit Pipe abgelehnt (R368 alt).**
(a) Fehlerklasse: Ein Aufrufmuster aus der Erinnerung verletzt eine Projektregel.
(b) Die Instruktion gibt den Wortlaut vor: genau `python -u scripts/preflight.py before *> analysis/_preflight_254.txt`, Ausgabe in einem EIGENEN Aufruf lesen.
(c) Nicht geprüft: weitere Aufrufmuster.

**Befund 4: Blätter gehen zur Neige.**
(a) Fehlerklasse: Die Insn-Reihe hängt an einer endlichen Kandidatenklasse; Planung ohne Vorschau.
(b) TEIL 3 misst die nächste Klasse (Kandidaten, deren bl/b-Ziele nur native referenzgleiche Köpfe sind): Anzahl, Insn-Summe, größte 15.
(c) Nicht geprüft: Bauaufwand und die Fähigkeit des c_kopf-Gerüsts für bl-Aufrufe (nur per Grep belegt oder `Fehlstelle:`).

**Befund 5 (Zählerbasis): 74 Fälle `span < rumpf`** sind nur Hypothese (Worker), keine Prüfung in B254. Das bleibt bis zur Neuberechnung der Bilanzbasis offen.

<DS_INSTRUCTION>
Batch 254 - Silent Scope Decomp

STAND UEBERNEHMEN:
Strang C (Handport). Messziel: referenzgleiche Insn (Preflight-Zeile „referenzgleich Insn“). Stand nach B253: 5465 Insn, C Köpfe 149/8456/0, MAME-Coverage 4825/50636 (Ersatzzahl, nicht Fortschritt), Rumpf-Insn offen ~53643 (Phantom-Span-bereinigt, `analysis/_m253/_phantom_span.txt`). Strang B ruht (Nutzerentscheid 02.10.). Nutzerentscheid C-Zuschnitt: Summe neuer referenzgleicher Insn je Batch, Soll mindestens 150, Ziel hier 300 bis 420; Köpfe nur Nebenzahl; Spiellogik und Menü/Service zuerst, Hardware/Boot-Init ans Ende, nicht streichen. Lies den Ankerkopf B253 und `analysis/port-batch253-c-ausgefuehrte-menge-2026-10-03.md` (TEIL 0a/0b/0c, Art-Tafel). Belege: `_m253/_a4_besuchskarte.txt`, `_m253/_phantom_span.txt`, `_m252/_zwillinge.txt` (Tafel 1b), `_m251/_ausgefuehrt_kandidaten.txt`, `scripts/m212_zeilen.py:317`, `scripts/m253_prewarm.py`.
SOLL-KOEPFE: 6
Begründung zur Median-Abweichung: die Köpfe sind Nebenzahl (Nutzerentscheid), Median 5, Ziel höchstens 6; die Insn-Zahl bestimmt den Umfang.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md` (`git status`, Memory-`status`, Mesa-Prüfung, `g++ --version`).
- Vorhersage-Commit `B254: Vorhersage` VOR dem ersten `port/`-Diff: je Bilanzzeile Sollwert und Zählerdefinition, Insn je Art (Spiel/Menü/Boot), Preflight-Dauer-Soll, Mitleser m54/m58 per Probemessung oder „unbekannt“.
- Belege `Datei:Zeile@commit`; jedes zitierte Skript liegt unter `scripts/`, nichts in TEMP.
- Lange Befehle (A4-Lauf, `c_kopf.py mutalle`, `port_build`, Preflight) als blockierender Aufruf mit `timeout=1800000`, nicht im Hintergrund, ohne Warteschleife (R13aj).
- Preflight-Aufruf EXAKT: `python -u scripts/preflight.py before *> analysis/_preflight_254.txt`; die Ausgabe in einem EIGENEN Folgeaufruf lesen (keine Pipe, keine Verkettung mit `Get-Content`).
- Vor dem Preflight ALLE Harness-Binaries frisch bauen: `mingw32-make all gl hybrid head193`; danach `analysis/_m254/_binary_quellen.txt` mit Zeitstempel je Binary gegen die Quellen (kein Binary älter als seine Quelle). Genau ein gültiger Preflight (R13ad: bei Fortsetzung der letzte); ein Fehllauf wird unverändert nach `analysis/_m254/_preflight_254_fehllauf<k>.txt` archiviert, mit Ursache.
- Zeitangaben nur an der Batch-Uhr (Umschaltschwelle); Streichen nur mit unmittelbar vorher gemessener `Get-Date`-Zeile im Batch-Dokument.
- Alle benutzten Ghidra-Werkzeuge im Bericht nennen (Marker muss mit Maschinenmarkern übereinstimmen). Nur lesende Werkzeuge auf bestehenden Funktionen (`disassemble_function`/`decompile_function`), kein `disassemble_bytes` (R398).
- Verbote: kein Force-Push, keine Historie umschreiben, keine Belege löschen, kein `restore_project`, keine Änderung der Grundregeln in `AGENTS.md`.

TEIL 0 - A4-Schlüssel nach Besuchskarte (Werkzeug, klein halten; Begründung: die Vorwärmung kostet 1713 s, ein Drittel der Batch-Laufzeit, die Messgröße bleibt unverändert):
0a. Ändere den Schlüssel in `scripts/m212_zeilen.py:317` so, dass NICHT der Exe-SHA zählt, sondern: SHA der Hybrid-Quellen ohne `ckopf_leaves.cpp` + SHA der Funktionskörper der in `_a4_besuchskarte.txt` betretenen Köpfe (11D40/0F7E4/0CA48/14F18) + `g++ --version`. Neue Köpfe sind zulässig, wenn ihr Eintritts-PC NICHT in der PC-Menge der Besuchskarte steht; ein neuer Kopf mit Treffer erzwingt Cache-Miss (Tafel „Kopf | Eintritts-PC | in Karte“ je Batch, Skript unter `scripts/`).
0b. Vorbedingung: die Karte muss die vollständige besuchte PC-Menge des A4-Laufs enthalten. Belege das (Rohausgabe lokal vorhanden, Zählung gegen `--pcs`-Ausgabe) oder schreibe `Fehlstelle: …`; dann bleibt der alte Schlüssel.
0c. Gegenbeleg: A4 EINMAL mit dem neuen Schlüssel vorwärmen (`scripts/m253_prewarm.py`, blockierend), BEVOR die B254-Köpfe gebaut werden. Nach dem Bau der Köpfe zeigt der Preflight „Zwischenspeicher Treffer“ ohne neuen A4-Lauf, und die Zeile Hybrid-A4 ist identisch (696571792, Halt 8001684C).
0d. Rückfall: ist 0a-0c nicht belegbar, Schlüssel unverändert lassen, Vorwärmung nach dem Bau der Köpfe wie in B253, Ergebnis mit `Fehlstelle:` dokumentieren. Kein weiterer Werkzeugumbau.

TEIL 1 - Serienbau C (Hauptteil):
Baue in dieser Reihenfolge (Tafel 1b, Insn absteigend, Span==Rumpf = ja): 80050A58 (91), 8002B20C (85), 8000EC80 (83), 80023864 (77); danach Menü/Service 8001B658 (41) und 80017BBC (40), solange das Ziel nicht erreicht ist und SOLL-KOEPFE nicht überschritten wird. Je Kopf: `KOPF_DEF`/`WERTE_DEF`/`MUT`, `c_kopf.py vergl` + `mut` (je Kopf 0 Abweichungen, je Kopf ROT gewordene Rotprobe), Art je Kopf mit Begründung (Aufrufer, MMIO, Textbezug; im Zweifel Spiellogik). Abweichungen von der Reihenfolge nur mit gemessenem Grund. Das Skript `m253_prewarm.py` ist nach jeder `port/`-Änderung nur dann nötig, wenn TEIL 0d gilt.

TEIL 2 - Doku und Bilanz:
Insn je Art (Spiel/Menü/Boot) und die Reihe „referenzgleiche Insn je C-Batch“ (B244 15, B246 18, B247 14, B251 510, B252 191, B253 461, B254 …). Ersatzzahlen (MAME-Coverage, Spannen-Insn, Köpfe) als solche kennzeichnen. Ankerkopf nach `AGENTS.md`, Memory-Export, genau ein gültiger Preflight, danach `m149_bilanz.py --batch 254 --from-preflight analysis/_preflight_254.txt --write-anchor`; nach dem Preflight nichts mehr unter `scripts/` ändern.

TEIL 3 - Vorschau (Messung, kein Bau; zuletzt):
Nach den Blättern: Tafel 1c „Kandidaten (Spiellogik/Menü) mit bl/b-Zielen, die ALLE auf bereits referenzgleiche native Köpfe oder bekannte Bibliotheksziele zeigen“: Anzahl, Insn-Summe (Rumpf, nicht Span), die größten 15. Grep, ob das `c_kopf`-Gerüst `bl` auf native Köpfe nachbilden kann (`Datei:Zeile@commit`) oder `Fehlstelle: gesucht in analysis/ und port/, nicht gefunden (Grep "<Bezeichner>")`. Ergebnis als Tafel; das Bauen kommt erst in einem späteren Batch.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen; `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse: >50 gelöschte Zeilen, dann melden). Abweichungen von der Vorhersage erklären, nicht glätten. Ankerblock am Ende mit Posten, `UEBERTRAG:`-Zeilen und `GESCHLOSSEN`-Vermerken.

FERTIG WENN: Summe neuer referenzgleicher Insn ≥150 (Ziel 300-420) im Preflight („referenzgleich Insn“ gegen 5465), je Kopf `vergl` 0 und `mut` ROT; Insn je Art berichtet; TEIL 0 mit Beleg (Schlüssel geändert und „Zwischenspeicher Treffer“ ohne neuen A4-Lauf, oder `Fehlstelle:`-Zeile); `_binary_quellen.txt` ohne veraltetes Binary; genau ein gültiger Preflight + Bilanz; kein Skript in TEMP zitiert.

STREICHREIHENFOLGE: 1. Köpfe über SOLL-KOEPFE (6), 2. TEIL 3 Vorschau, 3. Menü-Blätter 8001B658/80017BBC, 4. TEIL 0 über 0a/0b hinaus (Rückfall 0d statt Weiterbau). NIE: Vorhersage-Commit, Preflight, Bilanz, Memory-Export, die ersten zwei Blätter (80050A58, 8002B20C).

## NACHRUECKLISTE
1. Blätter 80050A58 und 8002B20C gebaut und verifiziert (je Kopf `vergl` 0, `mut` ROT); FERTIG WENN: beide im Preflight in „referenzgleich Insn“ (Zuwachs ≥176 gegen 5465).
2. Blätter 8000EC80 und 80023864 gebaut und verifiziert; FERTIG WENN: je Kopf wie Posten 1, Summe aller Posten 1+2 ≥336 Insn.
3. TEIL 0: A4-Schlüssel nach Besuchskarte (0a-0c mit Gegenbeleg „Zwischenspeicher Treffer“ ohne neuen A4-Lauf, identische A4-Zeile) oder `Fehlstelle:` + Rückfall 0d; FERTIG WENN: Beleg im Batch-Dokument.
4. Vorbedingungs-Tafel: `_m254/_binary_quellen.txt` und Preflight-Aufruf ohne Pipe; FERTIG WENN: ein gültiger Preflight ohne Fehllauf durch veraltete Binaries.
5. Menü/Service-Blätter 8001B658 (41) und 80017BBC (40), falls Insn-Summe unter ~300 oder SOLL-KOEPFE nicht erreicht; FERTIG WENN: je Kopf wie Posten 1.
6. TEIL 3 Tafel 1c (Köpfe mit nativen Callees) plus `bl`-Fähigkeit des Gerüsts; FERTIG WENN: Tafel im Batch-Dokument und Ankerzeile „Naechster Schritt“ mit dem Kandidatenvorschlag für B255 (Boot-Init 80013A88 bleibt dahinter eingereiht).
</DS_INSTRUCTION>
