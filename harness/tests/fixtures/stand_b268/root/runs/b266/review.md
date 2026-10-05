Die Prüfung ist fertig. Ergebnis: Die Maßnahme ist echt und belegt, aber der Batch war **keine Station**, und der Worker hat zu früh aufgehört. Es folgt das Review.

<TELEGRAM_SUMMARY>
Ergebnis: Ursache des B264-Einfrierens gefunden. Die 4-Byte-Auffüllung der IN3-Attrappe hat IN2 überschrieben, deshalb lief fälschlich der Service-Schirm. Fix `--attrappen-schonen` mit Rotprobe, Vorgabe EIN (`maschine.cpp:1026-1034@072c0dc`, `_m265/_kettenzustand.txt`).
Bewertung: Die Belege stimmen. Die Station-Angabe „ja (b)" ist falsch: Regel (b) verlangt opmode oder c über B264 hinaus. Jetzt gilt opmode=0, c=1, e=2, und c=1/e=2 gab es schon (`_m264/_intro.txt:24`). Die eigene Vorhersage (c=3, e≥8) ist nicht eingetreten und wurde nicht erklärt. „SCHRITTGRENZE = kein Wartepunkt" ist falsch: FUN_80026C34 wurde nur noch 2× betreten statt 838×, die Hauptschleife hängt also woanders. Wahrscheinlich in `while(Flag){FUN_80008B9C();}` (`f5-descr-batch61:285-286`). Ende nach 96 min trotz offener Spur.
FERTIG WENN erreicht: nein – (a)–(f) ja, (g) nein.
Kosten/Laufzeit: $0.24, 1h36m, 153 Anfragen, Preflight gültig (cfafb34).
Nächster Batch: Warteflag der Hauptschleife finden, nachbilden, iterieren.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 36 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
STATION: nein
M264-1: übernommen – Wirkung belegt: _m265/_kette_grep.txt + Orakel fand die Ursache
M264-2: übernommen – Wirkung belegt: hybrid-plan.md:274-277
M264-3: übernommen – Wirkung belegt: _preflight_265.txt:30,32
M264-4: übernommen – Wirkung belegt: _m265/_referenzen.txt
M264-5: übernommen (STATION-Zeile) – hx/stand.py nicht prüfbar, offen
M264-6: übernommen – Wirkung belegt: hybrid-plan.md:253-263
UEBERTRAG: TEIL 3 Iteration (opmode 2/Blockzahl>1) -> B266 TEIL 1-3
ENTSCHIEDEN: B265 ist keine Station, Stillstand 4/4
ENTSCHIEDEN: B266 bleibt Strang B (konkrete Warteschleife belegt)
OFFENE FRAGE: Strang B ist seit vier Batches ohne echten Boot-Fortschritt (die Zahl, bei der du gefragt werden wolltest). Weiter am Hybrid-Boot arbeiten oder wieder Köpfe nativ portieren? Weiter = nächster Engpass liegt offen; Köpfe = Kern wächst, Boot ruht. Vorschlag: B266 noch B, ohne Station ab B267 C.
WARTET AUF LIVE-AUFNAHME: MAME-Kaltstart-Log mit cgboard_dsp_shared_w_ppc bis zum ersten Attract-Bild
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Station falsch selbst bewertet.**
- (a) Fehlerklasse: Der Worker beurteilt sein eigenes Erfolgsmaß nach dem Sinn der Regel, nicht nach ihrem Wortlaut. Die Klammer „opmode/c über den B264-Stand hinaus" wurde übergangen.
- (b) Prüfung: Dasselbe gilt für jedes Selbsturteil (Station, FERTIG WENN, Stopp-Bedingung). Die Instruktion verlangt deshalb je Urteil eine Zeile mit dem Wortlaut der Regel, den Vergleichswerten und dem Ja/Nein. Für (b) heißt das: opmode ≠ 0 oder c ≥ 3, verglichen mit `_m264/_intro.txt:22-28`.
- (c) Nicht geprüft: ob die Stationsregel selbst die richtige Fortschrittsgröße ist. Das liegt beim Nutzer (OFFENE FRAGE).

**F2 – „Schrittgrenze erreicht" als „kein Wartepunkt" gelesen.**
- (a) Fehlerklasse: Kein Halt bedeutet nicht kein Warten. Ein Lauf, der bis zur Schrittgrenze läuft, kann trotzdem in einer Schleife festhängen.
- (b) Prüfung: Für jeden Vorgabe-Lauf ist der Bildtakt Pflicht, also die Eintritte in `FUN_80026C34` und `FUN_80008B9C` je 100M Schritte, ab dem letzten Kettenwechsel. Dazu eine PC-Besuchskarte dieses Abschnitts. Fällt der Bildtakt auf 0, ist das ein Wartepunkt.
- (c) Nicht geprüft: Wartestellen innerhalb von Interrupt-Handlern ohne Bildtakt-Bezug.

**F3 – Technische Vorhersage verfehlt und nicht erklärt.**
- (a) Fehlerklasse: Nur die Abweichungen der Bilanzzahlen werden erklärt, die technischen Vorhersagen fallen still weg.
- (b) Prüfung: Das Batch-Dokument führt eine Tafel „Vorhersage / Ist / Treffer ja-nein / Erklärung" mit einer Zeile je Vorhersage. Das gilt auch für den B265-Punkt 0a.3, der nachgetragen wird.
- (c) Nicht geprüft: ob die Vorhersagen vorab gut genug begründet waren.

**F4 – Modell schreibt außerhalb des eigenen Bereichs.**
- (a) Fehlerklasse: Die Auffüllung einer Attrappe überschreibt Nachbarzellen.
- (b) Prüfung: Die Instruktion verlangt eine Tafel aller Attrappen mit weniger als 4 Byte: welche Zellen die Auffüllung beschreibt, und ob diese Zellen zu einem anderen Modell gehören oder vom ROM gelesen werden. Dazu ein Abgleich der Ruhewerte von IN0–IN3 gegen die Eingabeports in MAME `hornet.cpp`, mit Fundstelle.
- (c) Nicht geprüft: die übrigen Bits von IN2 (Münze/Start) im Spielbetrieb, weil sich die Eingaben ändern.

**F5 – Eigene Lücke im Auftrag.**
- (a) Fehlerklasse: Nachrückposten 6 erlaubte „Grep-Tafel über die Kette" als Stopp-Bedingung, und der Worker nutzte die alte Kette, nicht den neuen Halt.
- (b) Prüfung: Die Stopp-Bedingung nennt ab jetzt den neuen Halt-Ort und dessen Warteflag mit Schreiber.
- (c) Nicht geprüft: nichts darüber hinaus.

<DS_INSTRUCTION>
STRANG: B
Batch 266 - Silent Scope Decomp

SOLL-KOEPFE: 0

STAND UEBERNEHMEN:
Strang B, B-Batch 37. **B265 ist KEINE Station** (ENTSCHEIDUNG (Reviewer)). Regel (b) verlangt „opmode/c über den B264-Stand hinaus". Nach der Maßnahme gilt opmode=00, c=01, e=02. c=01/e=02 gab es schon in B264 (`analysis/_m264/_intro.txt:24`). Halt-Art ist weiter Schranke (`analysis/_preflight_265.txt:32`). **Stillstandszähler 4 von 4.** Die Frage „B oder C" geht als OFFENE FRAGE an den Nutzer. B266 bleibt Strang B (ENTSCHEIDUNG (Reviewer): konkrete Warteschleife belegt, s. u.).
Vorgabe: `Hybrid-A4 900000000 | 80008BB0 | Schranke` (HEAD `cfafb34`). `--attrappen-schonen` ist Vorgabe EIN (`port/hybrid/maschine.cpp:1026-1034@072c0dc`), gemessen in `_m265/_kettenzustand.txt`.
**Neuer Wartepunkt (Reviewer-Befund):**
- Vorher wurde `FUN_80026C34` 838× betreten (900M Schritte), jetzt nur 2×: bei Schritt 257126842 (c=00/e=00) und bei 257605501 (c=01/e=01) (`_m265/_kettenzustand.txt:22-24`). Danach betritt die Hauptschleife den Opmodus-Automaten nicht mehr.
- `FUN_800089A0` ruft `FUN_80008B9C` in drei Schleifen, eine davon ist `while (Flag) { FUN_80008B9C(); }` (`analysis/f5-descr-batch61-2026-09-17.md:285-286`).
- `FUN_80008B9C` = `FUN_8000E7A0(); FUN_8002B360();`. `FUN_8002B360` arbeitet auf dem CG-Board-/DSP-Ring `[SDA(0x9C)]+0x4000/0x4001` (ebenda :284-289).
- Die Halt-PCs wandern: 400M `80023870`, 900M `80008BB0`, 1800M `80018C98` (`_m265/_lauf_1800m.txt`). `80023870` ist im Port bekannt (`port/src/input2_check.cpp:57`).
- Die Ursache ist ein Warteflag oder ein Transport, kein Opmodus-Zustand.
**Stationsregel (unverändert, präzisiert):**
- (a) Halt-Art ≠ Schranke, oder
- (b) **opmode ≠ 0 oder c ≥ 3**, oder
- (c) gewachsener Präfix gegen eine Kaltstart-Referenz (keine vorhanden).
- Jeweils durch eine Kern- oder Modelländerung, mit Vorgabe EIN und im gültigen Preflight.
**Fortschrittsmaß:**
- Zielmaß: `Anteil nativ (Schatten)` (`1658327/900000000`, `_preflight_265.txt:32`). Berichten, es steigt in der B-Phase nicht.
- **Ersatzzahlen, kein Fortschritt:** Bildtakt (Eintritte `FUN_80026C34`/`FUN_80008B9C` je 100M), Blockzahl je Bild, Halt-PC.

ARBEITSWEISE:
- Batch-Beginn nach `AGENTS.md`. `git config core.hooksPath` = `scripts/hooks` prüfen. `Get-Process hybrid_lauf,python` EINMAL notieren, nichts stoppen.
- Vorhersage-Commit `B266: Vorhersage` VOR jedem `port/`/`scripts/`-Diff. Inhalt:
  - Sollwert und Zählerdefinition je Bilanzzeile,
  - die Vorhersage, welches Flag die Schleife hält und wer es setzen soll,
  - die erwartete Wirkung der Maßnahme in **opmode/c/e und Bildtakt**.
- **Jedes Selbsturteil** (Station, Stopp-Bedingung, FERTIG WENN) steht als Zeile mit drei Teilen: Wortlaut der Regel, die verglichenen Zahlen, Ja/Nein.
- **„Schrittgrenze erreicht" ist KEINE Stopp-Bedingung und KEIN Beleg für „kein Wartepunkt".** Gültige Stopp-Bedingungen sind nur:
  - (i) Warteflag mit Adresse, Schreiber(n) und erwartetem Wert belegt, und der Schreiber hängt an Material, das nicht im Repo liegt. Nachweis per Grep auf die Adresse bzw. das Symbol über `port/`, `analysis/`, `capture/`, `mame/mame/src/`, mit Fundstellen.
  - (ii) Die Batch-Uhr hat die Umschaltschwelle erreicht. Dazu eine `Get-Date`-Zeile im Dokument.
- „Maßnahme" heißt eine Änderung unter `port/hybrid/` mit Gegenschalter, ROM-Beleg (Ghidra) und Port- oder MAME-Beleg. Rotprobe mit dem Gegenschalter. Je Maßnahme ein eigener Commit.
- Nach einem Preflight sind weitere Arbeiten erlaubt (R13bf). Danach folgt ein neuer Preflight, der letzte gilt.
- Läufe über 20M Schritte tragen `--wanduhr-grenze` ≤ 1500. Läufe, Preflight und `port_build` laufen blockierend mit `timeout=1800000`. Verboten: `Start-Process`, `Wait-Process`, Hintergrund, Warteschleifen.
- Rohausgaben über 20 MB heißen `*_roh.txt` und werden komprimiert gesichert.
- Belege als `Datei:Zeile@commit`. Preflight als einzige Zeile `python -u scripts/preflight.py before *> analysis/_preflight_266.txt`.

TEIL 0 - Klein:
0a. Vorhersage-Commit.
0b. Ankerkopf berichtigen (eigener Commit):
- Stationszeile: „B265: Station **nein** — Regel (b) nicht erfüllt: opmode 00, c 01 (B264 schon c 02, `_m264/_intro.txt:22-28`)".
- „Stillstandszähler: 4 von 4 – Frage B oder C an den Nutzer fällig".
- `ENTSCHEIDUNG (Reviewer): B266 bleibt B` mit Begründung.
- In `**Offene Entscheidung:**` diesen Posten wörtlich eintragen:
  `**(1) NEU:** Strang B ist seit vier Batches ohne echten Boot-Fortschritt - soll B266 noch den Hybrid-Boot weitertreiben (A) oder ab sofort wieder Koepfe nativ portiert werden (B)? (Vorschlag: A fuer B266, ohne Station ab B267 B. bei A: der belegte naechste Engpass (Warteschleife der Hauptschleife) wird angegangen, der Kern waechst nicht. bei B: Koepfe-Zahl waechst wieder, der Boot ruht auf dem Stand B265.)`
0c. Im Batch-Dokument B266 eine Tafel „Vorhersage / Ist / Treffer / Erklärung" anlegen. Darin auch den Nachtrag zum B265-Punkt 0a.3 („c=3, e≥8" vorhergesagt, Ist c=1, e=2). Das B265-Dokument NICHT ändern.

TEIL 1 - Wo hält die Hauptschleife?
1a. Bildtakt im Vorgabe-Lauf (900M): Eintritte in `FUN_80026C34`, `FUN_80008B9C`, `FUN_8002B360` und `80008AA0` je 100M Schritte. Dazu Aufruf und Rückkehr des 2. `FUN_80026C34`-Eintritts (257605501): kehrt er zurück, und bei welchem Schritt? Vorhandene Zähler bzw. Schalter in `hybrid_lauf.cpp` erst greppen (z. B. `erster_b9c_schritt`, `hybrid_lauf.cpp:1892@cfafb34`), nur bei Bedarf ergänzen. Ergebnis: `_m266/_bildtakt.txt`.
1b. PC-Besuchskarte ab Schritt 257605501 bis 900M, mit den 20 heißesten PCs und ihrer Funktion. Welche der drei Schleifen in `FUN_800089A0` läuft? Ghidra `decompile_function 800089A0`, Bereich `80008AA0`–`80008B98`. Ergebnis: `_m266/_besuchskarte.txt`.
1c. Warteflag bestimmen: Adresse, Lesestelle, alle Schreiber (Ghidra-Xrefs auf die Adresse), erwarteter Wert. Grep-Tafel `_m266/_flag_grep.txt` je Adresse und je Schreiberfunktion über `port/`, `analysis/`, `capture/`, `mame/mame/src/`. Läuft der Weg über den DSP-Ring `FUN_8002B360` (`+0x4000/0x4001`): was das ROM dort erwartet und was das Hybrid-Modell liefert.

TEIL 2 - Maßnahme:
2a. Die Bedingung aus 1c modellieren (Flag-Schreiber, Interrupt, Ring-Antwort, Gerätezustand): mit Gegenschalter, ROM- und Port- oder MAME-Beleg, eigener Commit. Der native Port enthält die Funktion bereits (Grep-Treffer in `port/src/`)? Dann zuerst ein Orakel wie in B265 (`scripts/m265_orakel.cpp` als Vorbild).
2b. Wirkung im Vorgabe-Lauf: Bildtakt, opmode/c/e, Blockzahl und Halt-PC vor und nach der Maßnahme. Rotprobe mit dem Gegenschalter: der Bildtakt fällt wieder auf 2.
2c. Vorgabe EIN nur nach zwei gleichen A4-Läufen unter 1500 s. Danach Vorwärmung (`scripts/m265_prewarm.py`).

TEIL 3 - Iteration (offener Posten, Übertrag aus B265):
Ablauf: nächster Wartepunkt → Bildtakt und Besuchskarte → Flag mit Schreiber → Maßnahme → Rotprobe → Commit. Weiter bis zu einer gültigen Stopp-Bedingung (ARBEITSWEISE) oder bis zur Umschaltschwelle. Ziel: opmode ≠ 0, bzw. `FUN_80025B7C`/`FUN_80017674` laufen, Blockzahl > 1.

TEIL 4 - Klassenprüfung Attrappen (klein):
Tafel `_m266/_attrappen_auffuellung.txt` über jede Attrappe in `kAttrappen` (`port/hybrid/maschine.cpp`) mit weniger als 4 Byte. Spalten: eigener Bereich, Zellen der Auffüllung, gehört die Zelle zu einem anderen Modell oder einer Attrappe, liest das ROM die Zelle (Lese-PCs aus dem Vorgabe-Lauf, sofern vorhanden). Dazu die Ruhewerte IN0–IN3 der Attrappen gegen die Eingabeports von sscope in MAME `mame/mame/src/mame/konami/hornet.cpp` (Fundstelle). Nur dokumentieren. Eine Änderung nur bei einem Befund, dann als eigene Maßnahme nach ARBEITSWEISE.

TEIL 5 - Abschluss:
- Vorwärmung blockierend, Preflight, dann `python -u scripts/m149_bilanz.py --batch 266 --from-preflight analysis/_preflight_266.txt --write-anchor` (nie durch eine Pipe).
- `python scripts/rohlauf_aufraeumen.py --komprimieren` und `python scripts/check_dateigroesse.py --getrackt`, beide als Auszug ins Dokument.
- Ankerkopf B266 mit:
  - Preflight-HEAD,
  - Stationszeile im Dreierformat (Regelwortlaut / Zahlen / Ja-Nein),
  - Stillstandszähler (Station → 0 von 4; sonst „5 B-Batches ohne Station – Frage B oder C offen"),
  - Bildtakt vorher/nachher,
  - „Nächster Schritt" mit Batch-Nummer 267.
- Memory-Export, `git status` lesen, `ghidra-mcp-notes.md` mitcommitten (Bremse > 50 Zeilen).

BATCH-ENDE:
`python -u scripts/m151_memory_sync.py export`, `git status` lesen, Commit `B266: …`. Abweichungen von der Vorhersage stehen in der Tafel aus 0c.

FERTIG WENN: (a) `_m266/_bildtakt.txt` und `_m266/_besuchskarte.txt` für den Abschnitt ab Schritt 257605501; (b) `_m266/_flag_grep.txt` mit Adresse, Schreiber(n) und erwartetem Wert des Warteflags; (c) mindestens eine Maßnahme unter `port/hybrid/` mit Gegenschalter, Rotprobe und eigenem Commit sowie Bildtakt und opmode/c/e vorher/nachher; (d) `_m266/_attrappen_auffuellung.txt`; (e) Ankerkopf mit berichtigter B265-Stationszeile und dem Posten (1) unter Offene Entscheidung; (f) gültiger Preflight, Bilanz, Aufräumen, Ankerkopf; (g) kein Batch-Ende vor der Umschaltschwelle ohne gültige Stopp-Bedingung nach ARBEITSWEISE.
STREICHREIHENFOLGE: 1. TEIL 4 über die Tafel hinaus (MAME-Abgleich), 2. TEIL 2c (Vorgabe EIN), 3. TEIL 4 ganz. NIE: Vorhersage-Commit, TEIL 0b, 0c, TEIL 1a–1c, TEIL 2a–2b, Preflight, Bilanz, Aufräumen, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. TEIL 0b/0c: FERTIG WENN Ankerkopf mit „B265: Station nein", „Stillstandszähler 4 von 4" und dem Posten (1) im Wortlaut committet ist und die Vorhersage-Tafel mit der Zeile zu B265 0a.3 im B266-Dokument steht.
2. TEIL 1a/1b: FERTIG WENN `_m266/_bildtakt.txt` (Eintritte je 100M, Rückkehr des 2. `FUN_80026C34`-Eintritts) und `_m266/_besuchskarte.txt` (die 20 heißesten PCs mit Funktion, aktive Schleife in `FUN_800089A0`) committet sind.
3. TEIL 1c: FERTIG WENN `_m266/_flag_grep.txt` Flag-Adresse, Lesestelle, alle Schreiber und den erwarteten Wert nennt, mit Grep je Bezeichner über `port/`, `analysis/`, `capture/`, `mame/mame/src/`.
4. TEIL 2a/2b: FERTIG WENN ein Commit unter `port/hybrid/` mit Gegenschalter vorliegt, dazu Rotprobe (Bildtakt fällt auf 2) sowie Bildtakt, opmode/c/e und Halt-PC vorher/nachher.
5. TEIL 3 Iteration: FERTIG WENN opmode ≠ 0 erreicht ist, oder eine gültige Stopp-Bedingung (i) mit Grep-Fundstellen vorliegt, oder eine `Get-Date`-Zeile an der Umschaltschwelle steht.
6. TEIL 4 + TEIL 5: FERTIG WENN `_m266/_attrappen_auffuellung.txt` committet ist und gültiger Preflight, Bilanz, Aufräumauszug sowie Ankerkopf mit Stationszeile im Dreierformat vorliegen.
</DS_INSTRUCTION>
