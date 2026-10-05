<TELEGRAM_SUMMARY>
Ergebnis: B252 (Strang C) +191 referenzgleiche Insn (4813 → 5004, Zweitkopie 0), +5 Köpfe (141 → 146). Ersatzzahl MAME-Coverage 4364/50636. Preflight sauber: 1301 s (B251: 2324 s). Insn je Art: Spiel 120, Menü 71, Boot 0.
Insn-Reihe je C-Batch: B244 15, B246 18, B247 14, B251 510 (255 davon Zweitkopie), B252 191.
Bewertung: FERTIG WENN erreicht: ja (Soll ≥150 erfüllt, Ziel ~200 knapp verfehlt). Befunde: (1) Die Vorhersage „Delta 0“ für die Mitleser m54/m58 war falsch. Gemessen: m54 163 → 250 Wörter, m58 5,7 % → 3,0 % (`_m252/_m54_m58_delta.txt`). (2) Gebaut wurden Blätter mit 57/40/34/31/29 Insn, obwohl 175/160/126 mit Span==Rumpf offen waren (`_m252/_zwillinge.txt` Z.12-14). (3) Die Vorwärmung dauerte 1764,5 s (35 s unter der Grenze); ihr Skript liegt nur in TEMP. (4) Marker-Widerspruch: ein `tool_request read_memory` wurde gemeldet, der Bericht sagt „Marker: Keine“. (5) Die Zwillingssuche ergab nur eine Gruppe, mit Phantom-Span (444 statt 31 Insn).
Kosten/Laufzeit: Preflight 1301 s, Vorwärmung 1764,5 s. Die übrigen Messwerte stehen im Harness-Prompt.
Nächster Batch: B253, C. TEIL 0 Besuchskarte `--pcs` + Vorwärmskript ins Repo, dann die größten Span==Rumpf-Blätter (175/160/126) zuerst.
B-SCHRITT: kein B-Batch (Strang C)
M250-3: übernommen als 0c-Vorwärmung - Wirkung nur teilweise belegt (`_preflight_252.txt` Z.33 Treffer, aber 1764,5 s Vorwärmung als Fixaufwand, Schlüssel unverändert) -> offen
UEBERTRAG: B252-Posten 4, Teil 0b (Schlüssel ohne Exe-SHA) -> B253 TEIL 0
UEBERTRAG: Neubewertung der Kandidatenwahl nach korrigierter m54/m58-Karte -> B253 TEIL 1
UEBERTRAG: Vorwärmskript `m252_prewarm.py` ins Repo -> B253 TEIL 0
UEBERTRAG: Boot-Init-Köpfe (nicht gestrichen) -> B253 NACHRUECKLISTE 6
UEBERTRAG: Rest der Blätter 91/85/83/77 -> B253 TEIL 2, falls Zeit
VERWORFEN: Zwillingsgruppe 8007CC94/8008538C - Phantom-Span, nur 31 Insn
ENTSCHIEDEN: B253 TEIL 0 = A4 mit `--pcs`; Schlüsseländerung nur mit Beleg, sonst Vorwärmung per Repo-Skript.
ENTSCHIEDEN: Auswahl nach Insn absteigend, nur Span==Rumpf.
ENTSCHIEDEN: Strang B ruht (Nutzerentscheid 02.10.).
OFFENE FRAGE: Bei 64351 offenen Spannen-Insn und 150-200 Insn je Batch sind es über 300 Batches. Sollen später größere Pakete (Funktionen mit Aufrufbaum) gebaut werden?
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**Befund 1: Vorhersage „Delta 0“ ohne Messung (Mitleser m54/m58).**
(a) Fehlerklasse: Eine Vorhersage übernimmt „unverändert“ für Zähler, die dieselbe korrigierte Quelle lesen (Byte-Index statt `>>2`), ohne Probemessung.
(b) Verwandt sind alle Zähler, die `cov_hit` oder `gelesen` nutzen: m53, m54, m58 und die Bilanzzeile „MAME-Coverage“. Die Instruktion verlangt in der Vorhersage je Mitleser eine Probemessung (NEU gegen ALT in TEMP) oder den Wert „unbekannt“ statt „0“.
(c) Nicht geprüft wird, ob die Mitleser inhaltlich noch sinnvoll sind (ob die Karte als Bezugsgröße taugt). Das bleibt offen bis TEIL 1.

**Befund 2: Kleinere statt größte Blätter gewählt.**
(a) Fehlerklasse: Die Auswahl richtet sich nach Bequemlichkeit statt nach der Zielgröße (Insn).
(b) Verwandt: Kandidatenreihenfolgen in allen C-Batches. Die Instruktion legt die Reihenfolge nach Tafel 1b fest (Insn absteigend, Span==Rumpf). Abweichungen nur mit einer Zeile im Batch-Dokument, die den Grund nennt (Messung, nicht Aufwand).
(c) Nicht geprüft: ob große Blätter sich bei der Verifikation anders verhalten als kleine. Das zeigt B253.

**Befund 3: Hilfsskript nur in TEMP, Messung 35 s unter der Grenze.**
(a) Fehlerklasse: Ein Beleg-/Ablaufwerkzeug liegt außerhalb des Repos und ist damit nicht wiederholbar.
(b) Verwandt: alle `$env:TEMP`-Skripte (auch m54/m58-Delta „TEMP-Ausgaben“). Die Instruktion verlangt, dass jedes Skript, dessen Ausgabe in `analysis/_m253/` zitiert wird, unter `scripts/` liegt. Prüfung: Grep nach `TEMP` im Batch-Dokument liefert 0 Treffer ohne Repo-Gegenstück.
(c) Nicht geprüft: die Laufzeit-Reserve der Vorwärmung selbst. Bleibt offen, bis TEIL 0 den Schlüssel ändert oder die Besuchskarte liefert.

**Befund 4: Marker-Widerspruch (`tool_request` gemeldet, Bericht „Marker: Keine“).**
(a) Fehlerklasse: Der Abschlussbericht stimmt nicht mit den Maschinen-Markern überein.
(b) Die Instruktion verlangt, vor dem Abschluss die tatsächlich benutzten Ghidra-Werkzeuge aufzulisten. Ein Werkzeug außerhalb des Profils wird als `TOOL_REQUEST` gemeldet und im Bericht genannt.
(c) Nicht geprüft wird, ob `read_memory` im Profil `ghidra-read` enthalten ist. Der Worker benennt es im Bericht, ich rate nicht.

**Befund 5: Phantom-Span (m103-Span größer als wahrer Rumpf).**
(a) Fehlerklasse: Eine Spannen-Zahl wird als Rumpfgröße gelesen.
(b) Verwandt: „Spannen-Insn 69355“, „nicht referenzgleich 64351“ und die Prognose >300 Batches. TEIL 3 misst in `_ausgefuehrt_kandidaten.txt` die Zahl und Insn-Summe der Zeilen mit Span≠Rumpf.
(c) Nicht geprüft: eine Neuberechnung der gesamten Bilanzbasis. Das bleibt der Entscheidung nach TEIL 3 vorbehalten.

<DS_INSTRUCTION>
Batch 253 - Silent Scope Decomp

STAND UEBERNEHMEN:
Strang C (Handport). Messziel: referenzgleiche Insn (Preflight-Zeile „referenzgleich Insn“). Stand nach B252: 5004 Insn, 146 Köpfe, MAME-Coverage 4364/50636 (Ersatzzahl, nicht Fortschritt). Köpfe sind nur Nebenzahl. Strang B ruht (Nutzerentscheid 02.10.). Nutzerentscheid C-Zuschnitt: Summe neuer referenzgleicher Insn je Batch, Soll mindestens 150, Ziel etwa 200 bis 260. Das hat Vorrang vor der Median-Regel. Köpfe unter 10 Insn sind nur Beifang. Reihenfolge nach Art: Spiellogik und Menü/Service zuerst, Hardware/Boot-Init ans Ende, nicht streichen. Lies den Ankerkopf B252 und `analysis/port-batch252-c-ausgefuehrte-menge-2026-10-03.md` (Abschnitte TEIL 0c und TEIL 1). Belege: `analysis/_m252/_zwillinge.txt` (Tafel 1b), `_m252/_a4_vorwaermung.txt`, `_m252/_m54_m58_delta.txt`, `_m251/_ausgefuehrt_kandidaten.txt`.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`: `git status`, Memory-`status`, Mesa-Prüfung, `g++ --version`.
- Vorhersage-Commit `B253: Vorhersage` VOR dem ersten `port/`-Diff. Nenne je Bilanzzeile einen Sollwert und die Zählerdefinition. Für die Mitleser m54/m58 gilt: Probemessung (NEU gegen ALT, Skript unter `scripts/`) oder „unbekannt“, nicht „0“. Nenne die Insn je Art (Spiel/Menü/Boot) als Sollwert.
- Belege: `Datei:Zeile@commit`. Jedes Skript, dessen Ausgabe zitiert wird, liegt unter `scripts/`. Kein Skript in TEMP.
- Alle langen Befehle (A4-Lauf, `c_kopf.py mutalle`, `port_build`, Preflight) laufen als blockierender Bash-Aufruf mit `timeout=1800000`, nicht im Hintergrund, ohne Warteschleife (R13aj).
- Zeitangaben nur an der Batch-Uhr (Umschaltschwelle). Streichen nur mit unmittelbar vorher gemessener `Get-Date`-Zeile im Batch-Dokument.
- Eigene Entscheidungen im Batch-Dokument als `ENTSCHEIDUNG (Reviewer/Worker): … - Begründung`.
- Alle verwendeten Ghidra-Werkzeuge im Bericht auflisten. Wird ein Werkzeug außerhalb des Profils gebraucht (z. B. `read_memory`), melde es als `TOOL_REQUEST` UND nenne es im Bericht („Marker: …“ muss mit den Maschinenmarkern übereinstimmen).
- Verbote: kein Force-Push, keine Historie umschreiben, keine Belege löschen, kein `restore_project`, keine Änderung der Grundregeln in `AGENTS.md`.
- `disassemble_bytes` nicht benutzen (R398). Für Belege `disassemble_function`/`decompile_function` auf bestehenden Funktionen.

TEIL 0 - Preflight-Kosten (Werkzeug, klein halten; Begründung: der Fixaufwand betrug in B252 ~51 min, die Messgröße bleibt unverändert):
0a. Hybrid-A4-Lauf (`hybrid_lauf.exe --schritte 900000000 --nativ-weiter --ohne-schatten --sharc-antwort --stopp-bei-halt --kalibrierung …`) EINMAL mit `--pcs` (`port/hybrid/hybrid_lauf.cpp:2314-2318`) laufen lassen und die Besuchskarte ablegen (`analysis/_m253/_a4_besuchskarte.txt`).
0b. Mit der Karte prüfen: Sind die Eintritts-PCs der 146 Köpfe (ckopf_leaves.cpp/kHeads) im A4-Lauf besucht? Ergebnis als Tafel (Kopf | besucht ja/nein). Nur wenn kein neuer Kopf besucht wird, darf der Cache-Schlüssel (`scripts/m212_zeilen.py:317`) ohne Exe-SHA gebildet werden (Schlüssel = Quellstand der in A4 benutzten Teile, ohne `ckopf_leaves.cpp`). Dann muss ein Gegenlauf die identische A4-Ausgabe zeigen (696571792 Schritte, Halt 8001684C). Ist das nicht belegbar, ändere den Schlüssel nicht und dokumentiere `Fehlstelle: …`.
0c. Das Vorwärmskript `m252_prewarm.py` (nur in TEMP gewesen) wird unter `scripts/` abgelegt (R355-konform) und für den Fall 0b-nein weiterverwendet (ein blockierender Aufruf vor dem Preflight).
Nichts in TEIL 0 darf die gemessene Zahl 5004 oder die Hybrid-Zahlen verschieben (Beleg: Preflight-Zeilen 21 und 32).

TEIL 1 - Karte und Kandidatenwahl (Messung, kein Bau):
1a. Grep, ob m54/m58 in die Kandidatenliste oder die Art-Zuordnung eingehen (`m242_ausgefuehrt.py`, `m251_*`). Ergebnis: ja/nein, mit `Datei:Zeile@commit`. Bei „ja“ die Kandidatenliste auf der korrigierten Karte neu erzeugen und den Unterschied nennen.
1b. Phantom-Span messen: In `analysis/_m251/_ausgefuehrt_kandidaten.txt` die Zeilen mit Span≠Rumpf zählen und die Insn-Differenz summieren. Dann die offenen Spannen-Insn (69355) und „nicht referenzgleich 64351“ neu in „Rumpf-Insn“ umrechnen, als Tafel und als Prognose „Batches bis fertig bei 200 Insn je Batch“. Ersatzzahl kennzeichnen.

TEIL 2 - Serienbau C (Hauptteil):
Baue die Blätter in dieser Reihenfolge nach Tafel 1b (Insn absteigend, Span==Rumpf = ja, F1/F2 eigenständig): 80029A50 (175), 800619EC (160), 8004F5A4 (126), danach 80050A58 (91), 8002B20C (85), 8000EC80 (83), 80023864 (77), solange das Ziel nicht erreicht ist. Je Kopf der gewohnte Weg: `KOPF_DEF`/`WERTE_DEF`/`MUT`, `c_kopf.py vergl` + `mut` (je Kopf 0 Abweichungen, je Kopf eine ROT gewordene Rotprobe), Art je Kopf mit Begründung (Aufrufer, MMIO, Textbezug; im Zweifel Spiellogik). Weicht die Reihenfolge ab, nenne den gemessenen Grund (kein Aufwandsargument). Menü/Service-Blätter 8001B658 (41) und 80017BBC (40) kommen nach den ersten drei, wenn die Insn-Summe sie braucht. Kein Werkzeugumbau in diesem Teil (der steht in TEIL 0). Kopfzahl ist Nebenzahl.

TEIL 3 - Doku und Bilanz:
Zeige die Insn je Art (Spiel/Menü/Boot) und die Reihe „referenzgleiche Insn je C-Batch“ (B244 15, B246 18, B247 14, B251 510 davon 255 Zweitkopie, B252 191, B253 …). Benenne die Ersatzzahlen ausdrücklich als solche (MAME-Coverage, Spannen-Insn, Köpfe-Gesamtzahl). Ankerkopf nach `AGENTS.md`. Memory-Export. Genau ein gültiger Preflight, danach Bilanz mit `--write-anchor`; nach dem Preflight nichts mehr unter `scripts/` ändern.

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen. `analysis/ghidra-mcp-notes.md` mitcommitten (Bremse: >50 gelöschte Zeilen). Genau ein gültiger `preflight`-Lauf (blockierend, `timeout=1800000`), danach `m149_bilanz.py --batch 253 --from-preflight … --write-anchor`. Abweichungen von der Vorhersage erklären, nicht glätten. Ankerblock am Ende mit `UEBERTRAG:`-Zeilen und Marker-Zeile.

FERTIG WENN: Summe neuer referenzgleicher Insn ≥150 (Ziel ~200), je Kopf eine ROT gewordene Rotprobe und `vergl`/`mut` 0 Abweichungen; Insn je Art berichtet; TEIL 0b mit Tafel und Ergebnis (Schlüssel belegt geändert oder `Fehlstelle:`-Zeile); TEIL 1a/1b-Ergebnisse dokumentiert; Vorwärmskript unter `scripts/`; genau ein gültiger Preflight + Bilanz; kein Skript in TEMP zitiert.

STREICHREIHENFOLGE: 1. Köpfe über dem Ziel (~260), 2. TEIL 1b Prognose-Tafel, 3. TEIL 0b Schlüsseländerung (die Besuchskarte 0a und das Repo-Skript 0c bleiben), 4. TEIL 1a. NIE: Vorhersage-Commit, Preflight, Bilanz, Memory-Export, die ersten drei Blätter (175/160/126).

## NACHRUECKLISTE
1. Die ersten drei Blätter 80029A50, 800619EC, 8004F5A4 gebaut und verifiziert (je Kopf `vergl`/`mut` 0, Rotprobe ROT); FERTIG WENN: Summe ≥150 Insn im Preflight (Zeile „referenzgleich Insn“ gegen 5004).
2. Vorwärmskript unter `scripts/` und TEIL 0a-Besuchskarte `analysis/_m253/_a4_besuchskarte.txt` abgelegt; FERTIG WENN: beide per Commit im Repo, Grep `TEMP` im Batch-Dokument ohne Treffer ohne Repo-Gegenstück.
3. TEIL 0b: Tafel Kopf | besucht und Entscheidung zum Schlüssel (geändert mit Gegenlauf identisch 696571792/8001684C, oder `Fehlstelle:`-Zeile); FERTIG WENN: Beleg im Batch-Dokument.
4. TEIL 1a/1b: m54/m58-Wirkung auf die Kandidatenwahl (ja/nein mit `Datei:Zeile@commit`) und Phantom-Span-Messung (Zeilenzahl, Insn-Differenz, neue Prognose); FERTIG WENN: Tafel im Batch-Dokument.
5. Weitere Blätter 80050A58, 8002B20C, 8000EC80, 80023864 (nur wenn die Insn-Summe unter ~200 liegt oder Zeit bleibt); FERTIG WENN: je Kopf verifiziert wie Posten 1.
6. Boot-Init-Köpfe nicht streichen: mindestens einen Hardware/Boot-Init-Kandidaten aus `_ausgefuehrt_kandidaten.txt` wählen, Art mit Begründung, im Anker unter „Naechster Schritt“ einreihen (Bau erst, wenn Spiellogik und Menü/Service-Blätter erschöpft sind); FERTIG WENN: Ankerzeile mit Kandidat und Reihenfolge.
</DS_INSTRUCTION>
