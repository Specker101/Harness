Prüfung fertig. Hauptbefund: Die Einzel-Rotproben aus B267 sind ungültig. Sie liefen ohne die A4-Startparameter (`--sharc-antwort`, `--kalibrierung`, siehe `scripts/m212_zeilen.py:512-517`) und erreichen deshalb die Hauptschleife nie, egal welche Maßnahme fehlt (`_m267/_r1_takt.txt:12-21`). Außerdem hat der Worker bei 91 von 128 min aufgehört, ohne gültige Stopp-Bedingung.

<TELEGRAM_SUMMARY>
Ergebnis: Die drei B266-Maßnahmen sind jetzt Vorgabe EIN (zwei zeichengleiche A4-Läufe, 303 s / 321 s). Der Ablauf am Engpass ist gemessen: Der gültige NVRAM-Satz wird nach `0x800B3A60` geladen und sofort von FUN_80015ED4 wieder zurückgesetzt. Hält man ihn per Schalter fest (Erkundung, Vorgabe AUS), läuft der Boot weiter bis zum Halt FORM bei 8002C4D8 (fehlender Befehl `lswi`).
Bewertung: Zwei schwere Fehler. Erstens sind die Einzel-Rotproben ungültig, sie liefen ohne A4-Parameter, es fehlte der Kontrolllauf; „alle drei nötig" ist damit nicht belegt. Zweitens Ende bei 91/128 min ohne Stopp-Bedingung, FERTIG WENN (g) verletzt (zum zweiten Mal nach B265). Der Grund für das Zurücksetzen bleibt HYPOTHESIS, obwohl FUN_80015D60 nativ im Port liegt (`bookkeeping.cpp:22-48`) und als Orakel dienen kann. Meine Annahme „Satz ungültig" war falsch: Die Aufnahme ist gültig, erst der RAM-Satz wird zurückgesetzt.
FERTIG WENN erreicht: nein – (a)–(f) ja, (a) aber mit falschem Aufruf; (g) nein.
Kosten/Laufzeit: $0.18, 1h31m, 123 Anfragen, Preflight da34a9a gültig, Hybrid-Lauf 6,8 s.
Nächster Batch: Rotproben richtig wiederholen, Reset-Zweig per Port-Orakel finden, `lswi` in den Kern.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 38 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
STATION: nein
UEBERTRAG: TEIL 1a Einzel-Rotprobe (ungültig) -> B268 TEIL 1
UEBERTRAG: TEIL 3 Iteration bis Schwelle -> B268 TEIL 2-5
ENTSCHIEDEN: B267 = Bewegung (Vorgabe hängt jetzt am neuen Wartepunkt e=0x11 in der Hauptschleife, Maßnahmen b222df4 mit Gegenschalter), Zähler 0/2
ENTSCHIEDEN: Werkzeugwunsch get_xrefs_to erledigt (im Profil vorhanden, 1× benutzt)
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Rotprobe mit anderen Startparametern als der Vergleichslauf.**
- (a) Fehlerklasse: Der Vergleich lief nicht unter gleichen Bedingungen. Die Rotproben fehlten `--sharc-antwort`, `--stopp-bei-halt`, `--pcs` und `--kalibrierung`, sie wurden aber gegen A4-Läufe aus B266 verglichen. Alle drei Läufe sind zeichengleich (Wegmass 3123 wie der 200M-Lauf ohne A4). Das ist das Zeichen dafür, dass die Maßnahme gar nicht gewirkt hat.
- (b) Prüfung: Jede Messreihe hat einen eigenen Kontrolllauf mit derselben Befehlszeile (alle EIN und alle AUS). Die volle Befehlszeile jedes Laufs steht im Beleg. Sind alle Varianten zeichengleich, gilt der Befund „Schalter wirkungslos, Aufruf prüfen", nicht „nötig".
- (c) Nicht geprüft: ob die B266-Messwerte mit `--takt` dieselben Schritte zeigen wie ohne. Die Instrumentierung wird nicht gegengeprüft.

**F2 – Port-Orakel nicht genutzt, Funktion nachprogrammiert.**
- (a) Fehlerklasse: Die Prüfsumme wurde in Python nachgerechnet (`scripts/m267_nvram.py`), statt den gebauten nativen Ablauf `Bookkeeping::entry` (`port/src/bookkeeping.cpp:22-48`) auf denselben Zustand anzuwenden. Damit bleibt der Zweig (iVar3/iVar4) HYPOTHESIS.
- (b) Prüfung: Für jede Funktion der Kette, die `port_suche.py` als gebaut meldet, läuft der native Port als Orakel auf dem Hybrid-Zustand. Die Zwischenwerte (Maske, repair, repair2) werden gegen die gemessenen Register an den Rückkehrstellen `80015DBC`/`80015DD4` gestellt.
- (c) Nicht geprüft: ob der native Port in allen Zweigen ROM-gleich ist.

**F3 – Frühes Batch-Ende über ein leichtes Oder in der Nachrückliste.**
- (a) Fehlerklasse: Posten 5 ließ „Maßnahme liegt vor" als Abschluss zu. Der Worker schloss damit bei 91/128 min, gegen FERTIG WENN (g). Gleiches Muster in B265.
- (b) Prüfung: Der Iterationsposten der Nachrückliste schließt nur mit `Get-Date` an der Umschaltschwelle oder mit Stopp-Bedingung (i) samt Grep-Fundstellen. Andere Posten enthalten kein Oder, das einen Abschluss vor der Iteration erlaubt.
- (c) Nicht geprüft: die Qualität der Arbeit nach der Schwelle.

**F4 – Eigener Fehler im Auftrag.**
- (a) Fehlerklasse: Ich habe „der Buchhaltungssatz ist also ungültig" als Tatsache in STAND UEBERNEHMEN geschrieben, obwohl es eine Folgerung war.
- (b) Prüfung: Folgerungen im Auftrag tragen ab jetzt die Einstufung (CONFIRMED / STRONG INFERENCE / HYPOTHESIS).
- (c) Nicht geprüft: nichts darüber hinaus.

<DS_INSTRUCTION>
STRANG: B
Batch 268 - Silent Scope Decomp

SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 39, B-Fenster B266–B275: B268 = 3/10 (R265-1).
**ENTSCHEIDUNG (Reviewer):**
- B267 ist keine Station (opmode 00, c 02).
- B267 ist eine **Bewegung**: Die Vorgabe steht jetzt am neuen Wartepunkt e=0x11 (Handler 17) der Hauptschleife. Die Maßnahmen haben Gegenschalter, eigenen Commit `b222df4` und die Rotprobe „alle AUS" mit A4-Parametern aus B266.
- Zähler „ohne Station und ohne Bewegung": 0 von 2.
Vorgabe: `Hybrid-A4 900000000 | 80008450 | Schranke` (`_preflight_267.txt`, HEAD `da34a9a`). `--cg-quittung`, `--vblank1`, `--cg-status` sind Vorgabe EIN.
**Berichtigungen (Reviewer-Befund):**
- **CONFIRMED:** `_m267/_einzel_rotprobe.txt` ist **ungültig**. Die drei Läufe nutzten nicht die A4-Befehlszeile (`scripts/m212_zeilen.py:512-517@da34a9a`: `--schritte N --nativ-weiter [--ohne-schatten] --sharc-antwort --stopp-bei-halt --pcs --kalibrierung <A4_KALIB>`). Sie erreichen die Hauptschleife nie, alle drei sind zeichengleich (Wegmass 3123, `_m267/_r1_takt.txt:12-21`). „Alle drei nötig" ist damit **nicht belegt**.
- **CONFIRMED:** Die NVRAM-Aufnahme ist gültig (`_m267/_nvram_buchhaltung.txt:9-21`). Meine B267-Aussage „Satz ungültig" war falsch. Der RAM-Satz `0x800B3A60` wird geladen (Schritt 272759681, `8000D194`) und von `FUN_80015ED4` zurückgesetzt (Schritt 272760705, `80015EEC`).
- **HYPOTHESIS:** Das Zurücksetzen kommt aus `repair`/`repair2`. Der Port bildet `FUN_80015D60` nativ ab: `port/src/bookkeeping.cpp:22-48` (`entry`: `block_verify`, `block_repair`, `check_block2`, Reset bei `repair != 0 || repair2 != 0 || !gate_open`), `:255-260` (`check_block2`). Das ist das Orakel.
- **CONFIRMED (Erkundung, Vorgabe AUS):** Mit `--satz-gueltig` hält der Boot bei Halt-Art FORM, `8002C4D8`, Wort `7CA744AA` = `lswi r5,r7,8` (op31 xo597), Wegmass 9423 (`_m267/_exploration.txt`).
**Stationsregel:** (a) Halt-Art ≠ Schranke, (b) opmode ≠ 0 oder c ≥ 3, (c) Kaltstart-Präfix. Jeweils durch eine Kern- oder Modelländerung, mit Vorgabe EIN und im gültigen Preflight. **Bewegung** nach R265-1.
**Zielmaß:** `Anteil nativ (Schatten)` (B267: 1658360/900000000), wird berichtet. Ersatzzahlen: Halt-PC, Wegmass, e-Wert.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren.
- Vorhersage-Commit `B268: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Inhalt: Bilanzzeilen mit Zählerdefinition, Vorhersage je Rotprobe, Vorhersage zum Reset-Zweig, Vorhersage zum Halt nach der Maßnahme.
- **Jeder Messlauf steht im Beleg mit seiner vollen Befehlszeile.** Jede Messreihe hat Kontrollläufe mit derselben Befehlszeile (alle EIN, alle AUS). Sind alle Varianten zeichengleich, heißt der Befund „Schalter wirkungslos – Aufruf prüfen".
- ROM-Adressen zuerst mit `python scripts/port_suche.py <adresse>`, die Ausgabe kommt ins Dokument. Pflicht: `80015D60`, `8000DFCC`, `8000E090`, `8000E190`, `80016154`, `80015ED4`, `8002C4D8`. **Meldet `port_suche.py` eine Funktion als gebaut, läuft der native Port als Orakel**, kein Nachbau in Python.
- Jedes Selbsturteil im Dreierformat (Regelwortlaut / Zahlen / Ja-Nein). Folgerungen tragen ihre Einstufung.
- Maßnahme = Änderung unter `port/hybrid/` mit Gegenschalter, ROM-Beleg und Port- oder MAME-Beleg, je Maßnahme ein eigener Commit. Rotprobe mit derselben Befehlszeile.
- **Kein Batch-Ende vor der Umschaltschwelle**, außer mit Stopp-Bedingung (i): Bedingung mit Adresse, Schreiber und Sollwert, sie hängt an Material außerhalb des Repos, mit Fundstellen. „Alle Posten erledigt" ist kein Ende.
- Läufe über 20M Schritte mit `--wanduhr-grenze` ≤ 1500. Läufe, Preflight und `port_build` blockierend mit `timeout=1800000`. Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen.
- Vorwärmung (`scripts/m267_prewarm.py`) nach dem LETZTEN `port/`-Commit, vor dem Preflight. `Hybrid-Lauf`-Sekunden aus `_preflight_zeiten.txt` ins Dokument (Soll < 30 s).
- Belege als `Datei:Zeile@commit`. Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. Im B268-Dokument und im Ankerkopf die Berichtigung „B267-Einzel-Rotprobe ungültig (falsche Befehlszeile)". Das B267-Dokument NICHT ändern.

TEIL 1 - Einzel-Rotproben richtig (Übertrag aus B267):
1a. Fünf Läufe zu je 300M mit der A4-Befehlszeile (ohne Schatten): alle EIN, alle AUS, und je eine Maßnahme AUS. Je Lauf: volle Befehlszeile, Halt-PC, Hauptschleife erreicht, Loop-A/B-Umläufe, Eintritte `FUN_80026C34`, c/e. Tafel `_m268/_einzel_rotprobe.txt` mit „nötig ja/nein".
1b. Ist eine Maßnahme nicht nötig: ihre Vorgabe zurück auf AUS (eigener Commit), dazu zwei gleiche A4-Läufe.

TEIL 2 - Reset-Zweig pinnen (Orakel):
2a. Im Vorgabe-Lauf die Rückgabe-Register an den Stellen nach `bl 8000DFCC` (`80015DBC`), nach `bl 80016154` (`80015DD4`), nach `FUN_8000E090` (Maske) und je Kopie das Ergebnis von `FUN_8000E190` (berechnete Summe) messen, mit Schritt. Außerdem den NVRAM-Inhalt `0x7D020000..0x7D021FFF` und den Satz `0x800B3A60` unmittelbar vor `FUN_80015D60` sichern.
2b. Orakel: den nativen `port::Bookkeeping::entry` (`port/src/bookkeeping.cpp:22-48`) mit genau diesem NVRAM- und RAM-Zustand laufen lassen (kleiner Treiber, Vorbild `scripts/m267_orakel.cpp`). Ausgeben: `verify_mask`, `repair`, `repair2`, Reset ja/nein. Tafel `_m268/_orakel_reset.txt`: Port gegen Hybrid, Stufe für Stufe.
2c. Die erste abweichende Stufe weiter zerlegen. Prüfen, ob ein Interpreterbefehl in der Prüfsummenschleife falsch rechnet (Befehlsfolge von `FUN_8000E190` gegen `port/src/nvram.cpp`), ob ein nativer Kopf im Hybrid diese Funktion ersetzt, ob das NVRAM-Modell abweicht, oder ob Uhr- bzw. RTC-Felder beteiligt sind. Ergebnis mit Einstufung.

TEIL 3 - Maßnahme:
Die Ursache aus TEIL 2 als Kern- oder Modelländerung beheben, mit Gegenschalter, Rotprobe (gleiche Befehlszeile) und eigenem Commit. Danach Vorgabe EIN nach zwei gleichen A4-Läufen unter 1500 s. Vorhersage: der A4-Lauf hält bei Halt-Art FORM, `8002C4D8`.

TEIL 4 - Kern: `lswi` (op31 xo597):
`lswi` nach der PowerPC-ISA in den Interpreter bauen. MAME-Fundstelle unter `mame/mame/src/devices/cpu/powerpc/` per Grep (`lswi`). Dazu ein Formfall in der vorhandenen Formprüfung (die Prüfung, die die Preflight-Zeile `Formen der C-Koepfe orakelgeprueft` liefert), mit einer Rotprobe, die ohne den Bau ROT wird. Verwandte Formen derselben Familie (`lswx`, `stswi`, `stswx`) per Grep auf Vorkommen im ROM prüfen und mitbauen, wenn sie vorkommen. Eigener Commit.

TEIL 5 - Iteration bis zur Schwelle:
Ablauf: neuer Halt bzw. Wartepunkt → `port_suche.py` / Orakel → Maßnahme → Rotprobe → Commit. Ziel: opmode ≠ 0, also `FUN_80025B7C` läuft und die Blockzahl ist > 1. Ende nur an der Umschaltschwelle (`Get-Date`) oder an Stopp-Bedingung (i).

TEIL 6 - Abschluss:
- Vorwärmung, Preflight, dann `python -u scripts/m149_bilanz.py --batch 268 --from-preflight analysis/_preflight_268.txt --write-anchor`.
- `rohlauf_aufraeumen.py --komprimieren` und `check_dateigroesse.py --getrackt` als Auszug ins Dokument.
- Ankerkopf B268 mit Preflight-HEAD, Station- und Bewegungszeile im Dreierformat, beiden Zählern, B-Fenster 3/10 und „Nächster Schritt" mit Batch-Nummer 269.
- Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse > 50 Zeilen).

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B268: …`. Vorhersage-Tafel „Vorhersage / Ist / Treffer / Erklärung".

FERTIG WENN: (a) `_m268/_einzel_rotprobe.txt` mit fünf Läufen derselben A4-Befehlszeile, volle Befehlszeilen im Beleg; (b) `_m268/_orakel_reset.txt` mit nativem `Bookkeeping::entry` gegen die Hybrid-Register und der ersten abweichenden Stufe; (c) eine Maßnahme aus TEIL 3 mit Gegenschalter, Rotprobe und eigenem Commit, oder belegte Stopp-Bedingung (i); (d) `lswi` gebaut mit Formfall und ROT gewordener Rotprobe; (e) gültiger Preflight (`Hybrid-Lauf` < 30 s), Bilanz, Aufräumen, Ankerkopf; (f) Ende an der Umschaltschwelle mit `Get-Date` oder an Stopp-Bedingung (i).
STREICHREIHENFOLGE: 1. TEIL 1b, 2. die verwandten Formen in TEIL 4 (nur `lswi` bleibt Pflicht), 3. TEIL 5 über den ersten neuen Halt hinaus. NIE: Vorhersage-Commit, TEIL 0b, TEIL 1a, TEIL 2a-2c, TEIL 3, Vorwärmung, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 0b + TEIL 1a: FERTIG WENN die Berichtigung im Dokument und im Ankerkopf steht und `_m268/_einzel_rotprobe.txt` (fünf Läufe, gleiche A4-Befehlszeile, volle Befehlszeile je Lauf, „nötig ja/nein") committet ist.
2. TEIL 2a/2b: FERTIG WENN `_m268/_orakel_reset.txt` den nativen `Bookkeeping::entry` (verify_mask/repair/repair2/Reset) gegen die gemessenen Register bei `80015DBC`/`80015DD4` stellt, committet.
3. TEIL 2c + TEIL 3: FERTIG WENN die erste abweichende Stufe mit Einstufung benannt ist und ein Commit unter `port/hybrid/` mit Gegenschalter und Rotprobe vorliegt, danach Vorgabe EIN mit zwei gleichen A4-Läufen. Sonst: Stopp-Bedingung (i) mit Fundstellen.
4. TEIL 4: FERTIG WENN `lswi` im Interpreter gebaut ist, mit Formfall, ROT gewordener Rotprobe und eigenem Commit.
5. TEIL 6: FERTIG WENN Vorwärmung, gültiger Preflight mit `Hybrid-Lauf` < 30 s, Bilanz, Aufräumauszug und Ankerkopf (Dreierformat, beide Zähler, B-Fenster 3/10) committet sind.
6. TEIL 5 Iteration: FERTIG NUR WENN eine `Get-Date`-Zeile im Dokument die Umschaltschwelle zeigt oder Stopp-Bedingung (i) mit Grep- bzw. `port_suche.py`-Fundstellen belegt ist. Ein neuer Preflight danach, falls sich `port/` oder `scripts/` geändert hat.
</DS_INSTRUCTION>
