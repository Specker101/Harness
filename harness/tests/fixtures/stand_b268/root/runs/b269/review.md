Ergebnis der Prüfung: Ein echter Kernfehler ist gefunden. `mfcr` hat die CR-Bits in umgekehrter Reihenfolge gepackt (`ppc_kern.cpp:548-553`). Daran lag die Buchhaltungsspur über drei Batches. Nach dem Fix hält A4 an Halt-Art FORM `8005D534` (`_preflight_268.txt:32`). Das ist eine Station nach Regel (a). Der Batch endete aber wieder vor der Schwelle (119/135).

<TELEGRAM_SUMMARY>
Ergebnis: Ursache gefunden. Der Hybrid-Kern packte bei `mfcr` die CR-Bits verkehrt (seit B218). Deshalb setzte `mtcrf` am Ende von FUN_8000DFCC CR4 falsch und der gültige Buchhaltungssatz wurde gelöscht. Behoben mit Gegenschalter und Rotprobe (`a6f9058`), dazu `lswi`/`stswi` im Kern. A4 hält jetzt bei Halt-Art FORM 8005D534, Schritt 422M (`_preflight_268.txt:32`). Die Einzel-Rotproben sind jetzt gültig: alle drei Maßnahmen nötig, volle Befehlszeilen im Beleg.
Bewertung: Starker Batch. Fehler: Ende bei 119/135 min, Preflight vor der Schwelle, deshalb keine Fortsetzung (zum vierten Mal). Der Fix wurde nur gegen das eigene Spiegelbild in `m114_matrix` geprüft.
FERTIG WENN erreicht: nein – (a)–(e) ja, (f) Ende vor der Schwelle.
Kosten/Laufzeit: $0.21, 1h59m, 151 Anfragen; Preflight 22 min (Profil-Lauf 765 s nach Kernänderung).
Nächster Batch: Unabhängige ISA-Prüfung der CR- und String-Befehle, dann FORM-Halt 8005D534 lösen und weiter bis zur Schwelle.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 39 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
STATION: ja
M268-1: übernommen als B269 TEIL 1 (Unicorn-Orakel CR/String, CR≠0) – Wirkung noch nicht belegt -> bleibt offen
M268-2: übernommen als B269 TEIL 4 (Anteil bei festem Schritt, Zähler/Nenner getrennt) – offen
M268-3: übernommen (Preflight erst ab Umschaltschwelle) – Harness-Teil beim Nutzer – offen
M268-4: übernommen als OFFENE FRAGE (Ersatzkriterium Schritt 4) – offen
M268-5: übernommen als Ankerposten (B269 TEIL 0) – offen
M268-6: übernommen als B269 TEIL 4 (_schaetzreihe) – offen
M268-7: abgelehnt, Grund: Harness-Code außerhalb des Repos, bleibt beim Nutzer (wie M264-5)
UEBERTRAG: TEIL 5 Iteration ab 8005D534 -> B269 TEIL 2-3
UEBERTRAG: Nutzernotiz SHARC-Upload -> Anker, B269 TEIL 0
ENTSCHIEDEN: B268 Station (a) – Stillstand 0, Zähler ohne Station und ohne Bewegung 0/2
OFFENE FRAGE: Schritt 4 (Boot bis Hauptschleife) braucht einen Kaltstart-Mitschnitt, den es nicht gibt. Soll stattdessen „erstes Attract-Bild baut sich auf (opmode 2→3)" als Abschluss gelten? Vorschlag: ja.
WARTET AUF LIVE-AUFNAHME: MAME-Kaltstart-Log mit cgboard_dsp_shared_w_ppc bis zum ersten Attract-Bild
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Kernform nur gegen das eigene Spiegelbild geprüft (M268-1).**
- (a) Fehlerklasse: Kernform nur gegen das eigene Spiegelbild geprüft. `ppc_kern.cpp` und `m114_matrix.py` trugen denselben Fehler, und der Fall CR = 0 machte die Bitlage unsichtbar (`port/src/ckopf_leaves.cpp:4588`).
- (b) Prüfung: Alle CR-Formen (`mfcr`, `mtcrf`, `mcrf`, `cr*`, `mcrxr` falls vorhanden) und `lswi`/`stswi` laufen gegen Unicorn (`scripts/m209_isa_orakel.py`), mit mindestens 200 Zufallsvektoren je Form, CR ≠ 0 und GPR ≠ 0. Rotprobe: die alte `mfcr`-Lage (`--mfcr-msb-aus`) muss im Orakel ROT werden.
- (c) Nicht geprüft: die übrigen Formen. Sie kommen nur, wenn Zeit bleibt (Streichreihenfolge).

**F2 – Frühes Ende durch Preflight vor der Schwelle (M268-3).**
- (a) Fehlerklasse: Der Worker startet den Preflight, sobald die Posten erledigt sind. Der Harness setzt dann nicht fort. Vierte Wiederholung.
- (b) Prüfung: Der Preflight startet erst nach einer `Get-Date`-Zeile, die die Umschaltschwelle zeigt, oder bei Stopp-Bedingung (i). Der Iterationsposten hat kein Oder.
- (c) Nicht geprüft: der Harness-Fall „Preflight gelaufen → UEBERTRAG". Das ist Harness-Code, er liegt beim Nutzer.

**F3 – Zielmaß mit wanderndem Nenner (M268-2).**
- (a) Fehlerklasse: Der Anteil steigt, weil der Lauf früher hält, nicht weil der Zähler wächst.
- (b) Prüfung: Zähler und Nenner getrennt in einer Trendtafel. Zusätzlich der Anteil an einem festen Schritt (250M, vor jedem bisherigen Halt).
- (c) Nicht geprüft: ob 250M auch künftig vor dem Halt liegt. Sonst ist der Bezug neu festzulegen.

**F4 – Profil-Lauf nach Kernänderung ungewärmt.**
- (a) Fehlerklasse: Der Profil-Lauf (m227) kostete nach der Kernänderung 765 s im Preflight (`_m268/_preflight_zeiten.txt:29`).
- (b) Prüfung: Die Sekunden je Teilschritt kommen ins Dokument. Lässt sich m227 vorwärmen, geschieht das mit der Vorwärmung.
- (c) Nicht geprüft: ein Umbau des Preflights.

<DS_INSTRUCTION>
STRANG: B
Batch 269 - Silent Scope Decomp

SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 40, B-Fenster B266–B275: B269 = 4/10 (R265-1).
**ENTSCHEIDUNG (Reviewer): B268 ist eine Station (a).**
- Regelwortlaut: „Halt mit Halt-Art ≠ Schranke, durch eine Kern- oder Modelländerung, Vorgabe EIN, im gültigen Preflight".
- Zahlen: `Halt-Art Form`, Halt-PC `8005D534`, Schritt 422421553, Kernänderung `a6f9058` (mfcr-Lage Vorgabe EIN), Preflight HEAD `a6f9058` (`_preflight_268.txt:32`).
- Urteil: JA.
- Stillstandszähler (Station) 0. Zähler „ohne Station und ohne Bewegung" 0 von 2.
Vorgabe: `Hybrid-A4 422421553 | 8005D534 | Form`.
**CONFIRMED:** `mfcr` legte die CR-Bits LSB-first (`port/hybrid/ppc_kern.cpp:548-553@a6f9058`). Dadurch löschte `mtcrf 0x8,r12` (`8000E084`) CR4 und setzte den Buchhaltungssatz zurück.
**CONFIRMED:** Die Einzel-Rotproben mit A4-Befehlszeile zeigen, dass alle drei Maßnahmen nötig sind (`_m268/_einzel_rotprobe.txt`).
**Zielmaß:** `Anteil nativ (Schatten)` `1659300/426688687`. Der Zähler ist gegenüber B262 nur um 940 gewachsen, der Nenner sank, weil der Halt früher liegt (Aussensicht M268-2). Bewertet wird nur der Zähler bei festem Bezug (TEIL 4).

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren.
- Vorhersage-Commit `B269: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Inhalt: Bilanzzeilen mit Zählerdefinition, Orakel-Ergebnis je CR- und String-Form, die Form bei `8005D534` und der Halt nach ihrem Bau.
- **Der Preflight startet erst, wenn die Batch-Uhr die Umschaltschwelle erreicht hat.** Unmittelbar davor steht eine `Get-Date`-Zeile mit Batch-Uhr im Dokument. Einzige Ausnahme ist Stopp-Bedingung (i) mit Fundstellen. Bis dahin wird iteriert (TEIL 3). „Alle Posten erledigt" ist kein Grund für den Preflight.
- Jeder Messlauf steht mit voller Befehlszeile im Beleg und hat Kontrollläufe mit derselben Befehlszeile. A4-Befehlszeile: `scripts/m212_zeilen.py:512-517`.
- ROM-Adressen zuerst mit `python scripts/port_suche.py <adresse>`. Ist eine Funktion gebaut, läuft der native Port als Orakel.
- **Eine neue oder geänderte Kernform gilt erst als gebaut, wenn sie gegen Unicorn (`scripts/m209_isa_orakel.py`) mit Vektoren ungleich null geprüft ist.** Der Spiegel in `m114_matrix.py` allein reicht nicht.
- Maßnahme = Änderung unter `port/hybrid/` mit Gegenschalter, ROM-Beleg und Port-, MAME- oder ISA-Beleg, eigener Commit, Rotprobe mit gleicher Befehlszeile.
- Selbsturteile im Dreierformat. Folgerungen mit Einstufung.
- Läufe über 20M Schritte mit `--wanduhr-grenze` ≤ 1500. Läufe, Preflight und `port_build` blockierend mit `timeout=1800000`. Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen.
- Vorwärmung nach dem LETZTEN `port/`-Commit, vor dem Preflight. Hängt der Zwischenspeicher des Profil-Laufs (m227) am Kern (B268: 765 s, `_m268/_preflight_zeiten.txt:29`), wird er mit vorgewärmt, sofern das Werkzeug das kann; sonst die Sekunden nennen. Alle Teilschritt-Sekunden aus `_preflight_zeiten.txt` ins Dokument.
- Belege als `Datei:Zeile@commit`. Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert.

TEIL 0 - Anker und Plan (eigener Commit):
- Ankerkopf: Station B268 im Dreierformat (oben), Stillstand 0, Bewegungszähler 0/2, B-Fenster 4/10.
- Unter `**Offene Entscheidung:**` diesen Posten wörtlich eintragen:
  `**(2) NEU:** Schritt 4 des Hybrid-Plans verlangt Deckung mit Referenzstroemen, die es nur als Savestate-Wiedergabe gibt - soll als Abschluss von Schritt 4 stattdessen "erstes Attract-Bild baut sich auf (opmode 2 -> 3, FUN_80025B7C liefert != 0, Blockzahl > 1)" gelten (A), oder wird ein MAME-Kaltstart-Mitschnitt mit cgboard_dsp_shared_w_ppc bis zum ersten Attract-Bild aufgenommen (B)? (Vorschlag: A, B spaeter als Gegenprobe. bei A: Schritt 4 ist mit vorhandenem Material abschliessbar. bei B: Schritt 4 bleibt bis zur Aufnahme offen.)`
- Dazu eine Zeile `WARTET AUF LIVE-AUFNAHME: MAME-Kaltstart-Log …` als eigener Posten.
- Nutzernotiz (2026-10-04) im Ankerkopf unter „Nächster Schritt", vorgemerkt für den Bildpfad: „Klären, wie die SHARC-Daten (Zeigertabelle 0x01400000, Blöcke) im echten Spiel ins DSP kommen und ob der Hybrid diesen Upload schon sieht. MAME-Dumps aus capture/sharcdumps nur als Zwischenlösung." Kein Auftrag in diesem Batch.

TEIL 1 - Unabhängige ISA-Prüfung (Aussensicht M268-1):
1a. Mit `scripts/m209_isa_orakel.py` (Unicorn) alle CR-Formen des Kerns prüfen: `mfcr`, `mtcrf`, `mcrf`, `crand`, `cror`, `crxor`, `crnand`, `crnor`, `creqv`, `crandc`, `crorc`, dazu `mcrxr`, falls im Kern vorhanden. Außerdem `lswi` und `stswi`. Je Form mindestens 200 Zufallsvektoren mit CR ≠ 0 und GPR ≠ 0, bei `lswi`/`stswi` mit NB ∈ {1,3,4,5,8,0} und Registerumlauf über r31. Verglichen wird der C++-Kern `ppc_kern.cpp`. Erreicht das Werkzeug nur die Python-Welt: beide Welten mit denselben Vektoren gegen Unicorn, und die Lücke benennen.
1b. Rotprobe: Mit der alten `mfcr`-Lage (`--mfcr-msb-aus` bzw. gleichwertig im Orakel) muss `mfcr` ROT werden.
1c. Tafel `_m269/_isa_cr_string.txt` mit Form, Fälle, Abweichungen, Rotprobe. Jede Abweichung ist eine Kernmaßnahme mit eigenem Commit.

TEIL 2 - FORM-Halt `8005D534`:
`port_suche.py 8005D534` (Funktionseintrag zuerst bestimmen) und das Wort dekodieren. Die Form im Kern bauen, mit MAME-Fundstelle unter `mame/mame/src/devices/cpu/powerpc/` bzw. ISA, mit Unicorn-Prüfung nach TEIL 1, Rotprobe (Formhalt kehrt zurück) und eigenem Commit. Danach zwei gleiche A4-Läufe.

TEIL 3 - Iteration bis zur Umschaltschwelle:
Ablauf: neuer Halt bzw. Wartepunkt → `port_suche.py` / Orakel → Maßnahme → Rotprobe → Commit. Ziel: opmode ≠ 0, also `FUN_80025B7C` läuft und die Blockzahl ist > 1. Ende nur an der Umschaltschwelle (`Get-Date`) oder an Stopp-Bedingung (i).

TEIL 4 - Messung des Zielmaßes (Aussensicht M268-2, M268-6):
4a. Trendtafel im Ankerkopf oder `hybrid-plan.md`: `Anteil nativ (Schatten)` B262–B269 mit Zähler und Nenner getrennt, Quelle je Zeile `_preflight_<N>.txt:32`.
4b. Klein: `hybrid_lauf.cpp` gibt zusätzlich den Zähler `Anteil nativ (Schatten)` bei festem Schritt 250000000 aus, dazu `m212_zeilen.py` die Zusatzangabe in der A4-Zeile. Eigener Commit, nur Ausgabe, keine Wirkung auf den Lauf (Beleg: Halt-PC und Schritte unverändert).
4c. `_m269/_schaetzreihe.txt`: je B-Batch B259–B269 die neuen Wartepunkte bzw. gelösten Halte, Halt-PC und Halt-Art, mechanisch aus `_preflight_<N>.txt:32` und den Batch-Dokumenten.

TEIL 5 - Abschluss (erst nach der Schwelle):
- `Get-Date` an der Umschaltschwelle, Vorwärmung, Preflight, dann `python -u scripts/m149_bilanz.py --batch 269 --from-preflight analysis/_preflight_269.txt --write-anchor`.
- Aufräumen (`--komprimieren`) und `check_dateigroesse.py --getrackt` als Auszug.
- Ankerkopf mit Station- und Bewegungszeile im Dreierformat, Zählern, B-Fenster 4/10 und „Nächster Schritt" mit Batch-Nummer 270.
- Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse > 50 Zeilen).

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B269: …`. Vorhersage-Tafel „Vorhersage / Ist / Treffer / Erklärung".

FERTIG WENN: (a) TEIL 0 committet mit Posten (2) und Live-Aufnahme-Posten; (b) `_m269/_isa_cr_string.txt` mit allen genannten Formen, ≥ 200 Vektoren je Form mit CR/GPR ≠ 0, und ROT gewordener `mfcr`-Rotprobe; (c) `8005D534` gelöst mit Unicorn-geprüfter Form, Rotprobe und eigenem Commit, oder Stopp-Bedingung (i); (d) Trendtafel und `_m269/_schaetzreihe.txt`; (e) Preflight erst nach einer `Get-Date`-Zeile an der Umschaltschwelle, gültig, mit Bilanz, Aufräumen und Ankerkopf.
STREICHREIHENFOLGE: 1. TEIL 4b, 2. `mcrxr` und die `cr*`-Formen außer `mfcr`/`mtcrf`/`mcrf`, 3. TEIL 4c. NIE: Vorhersage-Commit, TEIL 0, TEIL 1 für `mfcr`/`mtcrf`/`mcrf`/`lswi`/`stswi`, TEIL 2, TEIL 3 bis zur Schwelle, TEIL 4a, Vorwärmung, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 0: FERTIG WENN Ankerkopf mit Station B268 (Dreierformat), Zählern, B-Fenster 4/10, Posten (2) im Wortlaut, Live-Aufnahme-Posten und Nutzernotiz SHARC committet ist.
2. TEIL 1: FERTIG WENN `_m269/_isa_cr_string.txt` (Unicorn gegen `ppc_kern.cpp`, ≥ 200 Vektoren je Form mit CR/GPR ≠ 0, `mfcr`-Rotprobe ROT) committet ist und jede Abweichung einen eigenen Maßnahmen-Commit hat.
3. TEIL 2: FERTIG WENN die Form bei `8005D534` gebaut ist, mit Unicorn-Prüfung, Rotprobe, eigenem Commit und zwei gleichen A4-Läufen, oder Stopp-Bedingung (i) mit Fundstellen belegt ist.
4. TEIL 4a + 4c: FERTIG WENN die Trendtafel (Zähler/Nenner B262–B269) und `_m269/_schaetzreihe.txt` committet sind.
5. TEIL 3 Iteration: FERTIG NUR WENN eine `Get-Date`-Zeile im Dokument die Umschaltschwelle zeigt oder Stopp-Bedingung (i) mit `port_suche.py`- bzw. Grep-Fundstellen belegt ist.
6. TEIL 5: FERTIG WENN nach der `Get-Date`-Zeile aus Posten 5 Vorwärmung, gültiger Preflight, Bilanz, Aufräumauszug und Ankerkopf (Dreierformat, Zähler, B-Fenster 4/10) committet sind.
</DS_INSTRUCTION>
