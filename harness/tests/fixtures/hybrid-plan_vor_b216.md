# Plan fuer Strang B - Hybrid-Laeufer (Entscheidung A4, 2026-09-28)

**Angelegt:** Batch 208 (2026-09-28), erster B-Batch. **Grundlage:** Nutzerentscheidung
A4 (Option B, Hybrid-Laeufer als Pruef-Fahrzeug), Ankerblock B207
(`analysis/r1b-workstream.md`), Zielsatz in `AGENTS.md`/`readme.md`.

**Was der Hybrid-Laeufer ist.** Ein Testgeruest, das das ORIGINAL-ROM dort ausfuehrt, wo
noch kein gepruefter nativer Kopf steht. Er ist **kein Liefergegenstand**; der Zielzustand
bleibt ein eigenstaendiges natives Programm. Fortschritt wird an dem **schrumpfenden Anteil
interpretierten Codes** gemessen, nicht an der Existenz des Geruests.

## Kennzeichnungsregel (verbindlich)

Jede Datei unter `port/hybrid/` traegt als **Kopfkommentar** die Zeile

    // Hybrid-Geruest, im Port zu ersetzen

Hardware-Modelle (Speicherkarte, MMIO, Zeitgeber, Eingabe) tragen zusaetzlich an ihrer
Definition die Marke `Hybrid-Geruest, im Port zu ersetzen`. Kein Ton. Eingabe als Attrappe
(kein Spielbarkeitsziel). Static-Recompilation ist **vertagt**.

## Die fuenf Schritte

Jeder Schritt hat ein eigenes `FERTIG WENN` und eine **Gegenprobe** (eine zweite,
unabhaengige Messung, die den Schritt widerlegen koennte).

### Schritt 1 - Kern (B208)

Der C++-Befehlskern `port/hybrid/ppc_kern.{h,cpp}` bildet **genau** die Semantik des
Wortinterpreters `scripts/m114_matrix.py` ab: dieselben modellierten Formen, dieselben
Rc-/OE-Regeln, dieselbe **laute Ablehnung** (`EXC …`) bei nicht modellierten Formen und
Steuerbits. **Keine zweite Semantik:** fehlt eine Form, wird sie in BEIDEN Welten
nachgezogen, mit Befehlstest-Probe.

- **FERTIG WENN:** die Schritt-Differenz `kern_diff.exe` gegen die aufgezeichnete
  Schrittdatei (TEIL 2c) ergibt **0 Abweichungen**, und die Formenliste des C++-Kerns
  (`_m208/_formen_cpp.txt`) ist **zeichengleich** mit der mechanisch aus Python erzeugten
  Liste (`_m208/_formen_python.txt`).
- **ERLEDIGT (B209), und die Formulierung ist HERABGESTUFT (Nutzerauflage zu M208-2):
  "bewiesen" heisst hier "Python-gleich (Schritt-Differenz) + ISA-Orakel X/Y".**
  X/Y = 93994/93994 ausgefuehrte Schritte (Stichprobe jeder 10. der Schrittdatei) in
  der unabhaengigen dritten Welt Unicorn/QEMU-PPC32, **0 Abweichungen** ueber alle
  Register, CR, CA, LR, CTR, Schreibwerte und Speicherbytes (`_m209/_isa_orakel.txt`).
  **Nicht** freigesprochen sind die 110 Zufallsschritte, die Unicorn ablehnt
  (`UC_ERR_EXCEPTION`, Orakelluecke) und die beiden gefundenen gemeinsamen
  Referenzfehler (`slw` schreibt das Quellregister, `branch_taken` zaehlt das CTR bei
  BO 0..3/8..11 nicht herunter) - sie sind in B209 **nur dokumentiert**, die Korrektur
  gehoert in den C-Batch.
- **Gegenprobe:** eine Form im C++-Kern mutieren (z. B. das CA von `subfc` umdrehen) →
  die Differenz wird **ROT**; danach Ruecknahme. Zusaetzlich: ein nicht modelliertes Wort
  liefert in **beiden** Welten `EXC`.
- **Abdeckung (Queue-Auflage):** je modellierter Form wird die Zahl der geprueften
  Schritte ausgewiesen (`_m208/_formen_abdeckung.txt`). Formen mit weniger als 50
  aufgezeichneten Schritten bekommen **200 Zufallsschritte** (fester Seed, zufaellige
  GPR/CR/XER/LR/CTR, zufaellige Registerfelder im Befehlswort), Soll 0 Abweichungen.

### Schritt 2 - Maschine (B209)

Speicherkarte und MMIO als Modelle unter `port/hybrid/`, klar als Geruest markiert.

- **GEGENPROBE NEU FESTGELEGT (ENTSCHEIDUNG Reviewer B209):** die Gegenprobe ist
  **NICHT** `capture/poc_ref_boot_*.txt`. Nachgeprueft: diese Dateien tragen nur den
  Kommandostrom (`W : value : producerPC`) - keine Speicherkarte und kein MMIO.
  Die Gegenprobe ist ein **erster Lauf ab dem Einsprung des Hauptprogramms**.
  Einsprung/Anfangszustand: `analysis/decompressed-ppc-analysis.md:82`
  (`FUN_80000024`, r2 = 0x800ADABC, r1 = 0x803FFFC0); EVPR/MSR bleiben
  **HYPOTHESIS** (nicht modelliert).
- **FERTIG WENN (ERFUELLT B209):** (1) alle ausgefuehrten PCs liegen in
  `capture/ppc_cov_boot.bin` - Abweichungen werden **einzeln benannt** (B209: **3**
  PCs, der Einstiegskopf `80000024/28/2C`); (2) der erste Halt ist benannt mit
  Adresse (B209: `80008C14`, `EXC mmio (Sysreg lesen)`, MAME `hornet.cpp:957`);
  (3) **Rotprobe ROT** (Mutation der SDA2-Basis bei `8000003C` → 21 statt 36
  Schritte, Halt `80008BD8` "ausserhalb der Karte"); (4) **GESTRICHEN** (Auftrag,
  Streichreihenfolge 1): der Vergleich mit `poc_ref_boot_0.txt` - der Lauf schreibt
  **kein** Wort in den Kommandostrom. **Ab wann das moeglich wird:** sobald die
  Lueckenliste des Bootpfads (`_m209/_formen_bootpfad.txt`, 94 Formen) so weit
  geschlossen ist, dass der Lauf die MMIO-Zugriffe hinter `80008C14` uebersteht und
  die Kommandostrom-Schreiber erreicht - ein Ergebnis des Boot-Schritts.
- **Fortschrittsmass (neu, ersetzt die B208-Zahl):** **54 von 148 Formen
  (15039 von 18165 Woertern) des Bootpfads** sind modelliert
  (`_m209/_formen_bootpfad.txt`, Zensus **nur ueber ausgefuehrte Adressen** - die
  B208-Zahl "139867 von 178342" mischt Code und Daten, Aussensicht M208-4).

- **WARNUNG (B213, Reviewer-Befund): das Adressfilter-Mass ist UNGUELTIG.**
  Die B212-Zeile `Hybrid-Lauf 215 | 800138F0 | MMIO | 28/407 | 0` und
  `_m212/_fpu_boot.txt` **28/407** benutzen einen **ADRESSFILTER** (nur
  `PC < 80008AA0`) statt eines **Wegmasses** - Belege:
  `port/hybrid/hybrid_lauf.cpp:281-303` (Coverage-Zaehlung mit der Schwelle
  `80008AA0`) und `scripts/m212_boot_census.py:43,61` (dieselbe Schwelle).
  **Beide Zahlen sind als Fortschritts- bzw. FPU-Mass bis B214 UNGUELTIG**
  (die FPU-Neuschaetzung ebenso). Korrektur in B214: **Wegmass = distinkte
  ausgefuehrte PCs ∩ Karte / alle Kartenzellen** plus
  "Hauptschleife erreicht ja/nein".
- **KORREKTUR B214 EINGETRETEN (2026-09-29, `_m214/_wegmass.txt`):** das
  Wegmass steht in `port/hybrid/hybrid_lauf.cpp` (Zeile `Wegmass`), der
  Adressfilter steht nur noch als ausdruecklich **UNGUELTIGER** Wert in der
  Ausgabe. Rotprobe ROT: ein konstruierter PC unterhalb `80008AA0`, der NICHT
  in der Karte liegt (`80000004`), erhoeht die Auftragsfassung des alten Masses
  (28/407 -> 29/407), das neue Wegmass NICHT (276/42599). Die Preflight-Zeile
  `Hybrid-Lauf` traegt jetzt `Schritte | Halt-PC | Halt-Art | Wegmass |
  Hauptschleife ja/nein`.

### Stand der B-Schritte (B214)

- **Halt-Kette (gemessen, je mit Rotprobe):** Lauf 1 `80008C14`
  (Sysreg lesen) -> Lauf 2 `80011EC0` (Sysreg schreiben) -> Halt 3
  `8000CABC` (Sysreg IN2) -> Halt 4 `800138F0` (**RTC/NVRAM M48T58**,
  TEIL 3 B214) -> **Halt 5 `80013394`** (Wort `7C632910` = `subfe r3,r3,r5`,
  Opcode 31 XO 136).
- **Wegmass:** vorher (am RTC-Halt) **212 / 42599**, nach dem RTC-Geruest
  **276 / 42599** (532 Schritte, 276 distinkte PCs). Hauptschleife
  `80008AA0` **nicht** erreicht.
- **RTC/NVRAM-Geruest (TEIL 3, `port/hybrid/maschine.cpp`):** 8192 Byte aus
  der Aufnahme `capture/nvram/sscope/m48t58`, byteweise an `0x7D020000`
  gelegt (M48T58, `timekpr.cpp:151-165`); RTC-Register `0x1FF8..0x1FFF`.
  Rotprobe ROT: Attrappe abgeschaltet -> Halt wieder `800138F0`.
  Beleg `_m214/_rtc.txt`.
- **Naechster Halt ist FORMENARBEIT, nicht Hardware:** `subfe` (XO 136) fehlt
  im Kern - und damit in `m114_matrix` UND `ppc_kern.cpp` (gemeinsame Basis).
  Der naechste B-Schritt muss beide Welten zugleich erweitern (R532-Klasse).
- **UNGUELTIG (B215 F1):** die B214-Aussage "der Lauf laeuft ueber die
  Warteschleife `FUN_8000EC08` hinaus" ist **widerlegt**. Belegt war nur der
  Wegmass-Anstieg 442 -> 448 (Zeitbasis); der Halt-PC liegt in BEIDEN Faellen
  INNERHALB der Warteschleife (`8000845C`/`80008460` in `FUN_80008448`), und
  die 6 Zellen der `--pcs`-Differenz MIT/OHNE TB liegen ALLE in `FUN_8000CB40`
  - also INNERHALB der Schleife, nicht dahinter (B215 Paragraph 1c, Beleg
  `_m215/_warteschleife.txt`).

### Schritt 2b - Kontrollfluss/Supervisor (NEU, ENTSCHIEDEN (Nutzer, 2026-09-28))

**Zwischen "Maschine" und "kHeads-Uebernahme/Boot"** kommt ein eigener Schritt.
**TEIL 1 IST IN B211 GEBAUT (2026-09-28) - mit eigenem FERTIG WENN, s. u.**
Inhalt: `blr` ueber LR, `bctr`/`bcctr`, `sc`/`rfi`, `mtmsr`/`mfmsr`,
`mtspr`/`mfspr`, **Decrementer bzw. VBL-Interrupt**, **FPU-Anteil im Bootpfad** -
mit eigenem FERTIG WENN und eigener Gegenprobe (**ISA-Orakel aus TEIL 1 plus
Coverage**). In B209 **nur geplant, nicht gebaut**; haelt Lauf 1 an einer solchen
Stelle, ist das der **erwartete** erste Halt und wird so benannt. (B209 hielt an
einer MMIO-Stelle, nicht an einer Kontrollfluss-Stelle.)

**FERTIG WENN (TEIL 1, B211 - ERFUELLT 2026-09-28):**
(1) **Laufmodus in BEIDEN Welten** mit derselben Semantik gebaut:
`scripts/m114_matrix.py` (`Machine.run_step` + SPR-Tafel) und
`port/hybrid/ppc_kern.cpp` (`Maschine::run_step` + `spr_lesen`/`spr_schreiben`).
`bl`/`bcl` setzen LR und springen; `bclr` springt nach LR, `bcctr` nach CTR
(**mit den zwei unteren Bits = 0**); `mfspr`/`mtspr` ueber die Tafel
(LR, CTR, XER, DSISR, DAR, DEC, SDR1, SRR0/1, SPRG0-3, TBL/TBU, EAR, PVR,
EVPR, HID0/1, MMCR0/1, IABR/DABR); `mfmsr`/`mtmsr`, `sc` (laut abgelehnt),
`rfi`. Eine **nicht modellierte SPR-Nummer** loest `EXC spr <n>` aus.
(2) **Gegenprobe:** 9600 Pflicht-Zufallsvektoren (Seed 211; 200 je Form x
BO-Klasse x LK, bei `bc` auch AA) durch DREI Welten (Python, C++-Kern,
Unicorn/QEMU-PPC32) - **0 echte Abweichungen** in GPR/CR/LR/CTR und Ziel;
1201 Vektoren als **Orakelluecke** benannt (R542: Unicorn bricht bei `bcctr`
mit BO2 = 0 und genommenem Zweig ab). Beleg
`analysis/_m211/_zweig_klasse.txt`; Rotprobe der Maske **ROT**
(`_zweig_rotprobe.txt`, 1148 von 9600).
(3) **Der FUNKTIONSMODUS bleibt unveraendert:** `vergl alle` **78 Koepfe /
2795 Faelle / 0 Abweichungen** nach der Korrektur; die Schrittdatei
(SHA-256 `8621058c…`) stimmt mit dem C++-Kern auf **937375 Saetze / 0
Abweichungen** ueberein.
(4) **BEFUND F3 (gemeinsamer Referenzfehler, in BEIDEN Welten behoben):**
`bclr`/`bcctr` muessen das Zweigziel mit den zwei unteren Bits = 0 bilden
(ISA Buch 1 Kap. 2.4.3, gemessen gegen Unicorn) - beide Welten sprangen auf
das unmaskierte Register. Unsichtbar bei `blr`, weil LR = pc+4 ausgerichtet
ist.
**NICHT IN B211:** Decrementer/VBL-Interrupt und der FPU-Anteil im Bootpfad
(B212); `sc` ist gebaut, aber jede Ausnahmebehandlung fehlt noch.
**Bedarf je B-Schritt (HYPOTHESIS):** der Laufmodus war der groessere
Brocken; die Interrupts brauchen zusaetzlich eine Ausnahme-Zustellung
(SRR0/1, MSR-Bits) und den Decrementer - nach der Messung von B211
(107 Schritte bis zum ersten MMIO-Halt, vier Halts benannt) ist B212
ueberwiegend Hardware-Attrappen-Arbeit, keine Formenarbeit.

### Budget-Nachtrag (ENTSCHEIDEN (Nutzer, 2026-09-28))

"hoechstens 20" und "Abbruch nach 10" zaehlen **B-Batches, nicht Kalender-Batches**;
nach Lauf 1 schaetzt der Plan den Bedarf je B-Schritt **neu** (HYPOTHESIS).
Offene Frage aus B208 beantwortet: die "21 Referenzstroeme" waren eine
Harness-Zaehlung; **es gilt die gezaehlte Zahl 20**.

### Schritt 3 - kHeads-Uebernahme

**Einhaengepunkt ist `port/include/port/host_registry.h`** (`HostRegistry::has`/`find`).
Statt `UnimplementedFunction` interpretiert der Kern (Rueckfall); registrierte Koepfe
laufen **nativ**. Es wird ein **Zaehler fuer den interpretierten Anteil** gefuehrt
(Aufrufe und Instruktionen).

- **FERTIG WENN:** ein bereits eingebundener Kopf (`8003C17C` = `voter::leaves2::rel_matrix`)
  laeuft ueber `has()` nativ, ein NICHT gebautes Ziel laeuft ueber den Kern, und der
  Zaehler fuer den interpretierten Anteil ist **kleiner** als ohne Registrierung
  (Differenz gemessen, nicht geschaetzt).
- **Gegenprobe:** Registrierung des Kopfes entfernen → der Zaehler steigt um genau die
  Aufrufe dieses Kopfes (Ruecknahme danach).

### Schritt 4 - Boot bis zur Hauptschleife

Der Kern fuehrt das ROM ueber den Ladepfad bis in die Hauptschleife (ohne Ton, Eingabe
als Attrappe).

- **FERTIG WENN:** der Lauf erreicht die Hauptschleife (PC-Bereich der Hauptschleife,
  belegt durch eine Rumpfadresse) und deckt sich mit den 20 Referenzstroemen
  `capture/poc_ref_*.txt` (gemessen am 2026-09-28: **20** Dateien; der Auftrag nennt 21 -
  die Zahl 21 ist NICHT belegt und wird hier als offener Punkt gefuehrt).
- **Gegenprobe:** ein Wort im Startpfad mutieren → der Lauf erreicht die Hauptschleife
  nachweislich NICHT (Ruecknahme danach).

### Schritt 5 - Erstes Attract-Bild

Erstes Attract-Bild ohne Ton; Ausgabe gegen die eingefrorenen Referenzen.

**NEU GEFASST (B215, Nutzernachricht vom 2026-09-29 14:02).** Die alte Fassung
stiess sich auf die Coverage-Karten `analysis/_m175/_cover_*.txt` und
`analysis/_m176/_cover_*` - **dieses Kriterium ist GESTRICHEN.** Eine
Coverage-Karte sagt, welche Woerter GELESEN wurden; sie sagt nicht, ob der
Kommandostrom stimmt.

- **HAUPTMASS (B215):** der erzeugte **Kommandostrom** ist **halbwortgenau
  gleich** dem aufgezeichneten Referenzstrom `capture/poc_ref_boot_0..3.txt`
  (4 Dateien). Verglichen wird Wort fuer Wort (Halbwort = `W : value :
  producerPC`, s. `poc/stream_consumer/main.cpp`), Soll **0 Abweichungen**.
  Das ist dasselbe Mass, das Schritt 4 schon fuer den Bootpfad fuehrt.
- **Bildbeweis:** `poc/stream_consumer` erzeugt aus dem Strom die
  Voodoo-Registersequenz, `poc/gl_frame` zeichnet daraus ein Bild; das Bild
  wird gegen einen **MAME-Dump** gehalten (`SSC_GL_SNAP_FRAMES`).
  **Der Dump liegt im Repo NICHT vor** → er ist ein **Aufnahmebedarf** (Posten
  fuer den Nutzer), kein stiller Freispruch. Bis er da ist, gilt als
  Bildbeweis nur der Selbstvergleich `poc/gl_frame` gegen die eingefrorenen
  `analysis/_gl_ref_hashes.txt` (SHA-256).
- **GL-Anker sind Waechter, nicht Mass:** die 9 GL-Anker des Harness
  (`REG GL-Anker` 9/9, `REG GL-Referenz` 9/9) bleiben als **Waechter** gefuehrt
  und werden im Preflight weiter geprueft. Sie sind **nicht** der RenderSink
  und **kein** Fortschrittsmass.
- **FERTIG WENN:** (1) der Kommandostrom ist halbwortgenau gleich den vier
  `poc_ref_boot_*`-Stroemen (0 Abweichungen), UND (2) der Bildbeweis steht -
  entweder gegen den MAME-Dump `SSC_GL_SNAP_FRAMES` oder, solange der fehlt,
  gegen `_gl_ref_hashes.txt` mit ausdruecklichem Vermerk. Die Zahl der dafuer
  interpretierten Instruktionen ist gemessen und faellt gegenueber Schritt 4.
- **Gegenprobe:** ein Wort im Bildweg mutieren → das Bild weicht ab (Ruecknahme
  danach). Zusaetzlich: ein Wort im Stromweg mutieren → der Stromvergleich wird
  rot.

### Vorarbeiten, auf die der Plan aufbaut

**NEU (B215, Nutzernachricht vom 2026-09-29 14:02).** Der Plan baut auf fuenf
Dingen, die es **schon gibt**. Ihre Existenz wurde in B215 geprueft; kuenftige
Plaene nennen ihre Vorarbeiten genauso - **mit Pfad und Pruefung**, nicht als
Annahme.

| # | Vorarbeit | Pfad | Existenz (B215 geprueft) |
|---|---|---|---|
| 1 | die vier Boot-Referenzstroeme (Hauptmass Schritt 5) | `capture/poc_ref_boot_0.txt` .. `_3.txt` | ja (4 Dateien) |
| 2 | die Wegmass-Karte | `capture/ppc_cov_boot.bin` | ja |
| 3 | der Konsument des Kommandostroms | `poc/stream_consumer/main.cpp` | ja |
| 4 | der Bildbeweis-Rahmen | `poc/gl_frame.cpp` | ja |
| 5 | die GL-Waechter-Hashes | `analysis/_gl_ref_hashes.txt` | ja |
| - | **fehlt:** MAME-Bilddump `SSC_GL_SNAP_FRAMES` | - | **Aufnahmebedarf** |

**Regel fuer kuenftige Plaene:** jeder Planabschnitt nennt die Vorarbeiten, auf
die er sich stuetzt, mit Pfad; und je Vorarbeit steht dabei, ob sie **gemessen
existiert** oder **fehlt**. Eine Vorarbeit, die nur im Kopf des Autors
existiert, ist keine.

## Vormerkung fuer B210 (woertlich, aus dem B209-Auftrag)

**B210 = C-Batch. Bahnabdeckung wird Pflichtgroesse: "verifiziert" heisst
100 % Bloecke ODER jede Luecke einzeln begruendet, sonst "gebaut, teilgeprueft".
Neue Bilanzzeile "Bahnabdeckung (Koepfe 100 % / Bloecke gesamt)". Fallfabrik
fuer die 23 Koepfe unter 100 %, schlechteste zuerst (`80056684` 3/15,
`80017A8C` 4/14, `8008579C` 3/10, `80062C78` 7/18). Dazu A1 und A2 sowie die
Korrekturen aus dem ISA-Orakel.**

Die **Korrekturen aus dem ISA-Orakel** (B209, nur Befunde): `m114_matrix.py:472-474`
`slw` schreibt das QUELLregister (ISA: das Feld 11-15 ist das Ziel) - 190 von 200
Zufallsschritten rot, **67 `slw`-Woerter im Hauptprogramm mit RA != RT**; und
`branch_taken` zaehlt das CTR bei BO 0..3/8..11 nicht herunter (MAME
`ppcdrc.cpp:2678-2682`). Beide sitzen in der **gemeinsamen Basis** beider Welten
(also auch in `port/hybrid/ppc_kern.cpp`) - nach der Korrektur ist **jeder der 78
C-Koepfe neu zu vergleichen** und die Schrittdatei neu zu erzeugen.

## Budget

- **Hoechstens 20 Batches** bis zum Meilenstein ("ROM bootet bis zum ersten Attract-Bild,
  ohne Ton, Eingabe als Attrappe").
- **Abbruch nach 10 Batches ohne Boot bis zur Hauptschleife** (Zaehlung ab B208 =
  B-Batch 1). Bei Abbruch wird der Stand dokumentiert, das Geruest bleibt liegen; die
  Arbeit faellt an Strang C zurueck.
- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer):** B208 B, B209 B, B210 C
  (A1 MEM-Varianten + A2-Altposten + Paket E), danach wieder 2:1.
  **Nachtrag B212 (Fortschreibung):** B211 B, B212 B, B213 C.
  **Neuschaetzung je B-Schritt (B214 ERSETZT, R556):** die alte Fassung
  ("Bootpfad bis zur Hauptschleife umfasst **407** (UNGUELTIG (R556)) distinkte
  Coverage-Woerter; Lauf 3 erreicht davon **22** (5,4 %))" ist **UNGUELTIG
  (R556)** - sie beruht auf dem Adressfilter `PC < 80008AA0` und einem Nenner,
  der nur einen Ausschnitt der Karte ist (`_m214/_wegmass.txt`).
  **Neue Schaetzung (HYPOTHESIS, Rechenweg in `_m214/_spr_dcr_fpu.txt`):** die
  Karte hat **42599** Woerter; davon **1483** SPR-/DCR-Zugriffe (3,48 %) und
  **0** FPU-Woerter. Daraus: (a) SPR/DCR-Attrappen 1-2 B-Schritte,
  (b) FPU 0-4 B-Schritte (im Kartengebiet heute 0 Woerter). Zusammen mit der
  gemessenen Halt-Kette (s. "Stand der B-Schritte") ergibt das **4-6 weitere
  B-Schritte** bis zur Hauptschleife - HYPOTHESIS, kein Messwert.

## Ausdrueckliche Nicht-Ziele

- Kein Ton, keine Eingabe (Attrappe), kein Spielbarkeitsziel.
- Static-Recompilation **vertagt** (readme.md, "Later").
- `port/hybrid/` liegt **ausserhalb des Standardbaus**: das `Makefile` baut
  `SOURCES := $(filter-out $(SRC_DIR)/render_gl.cpp,$(wildcard $(SRC_DIR)/*.cpp))`,
  also nur `port/src/*.cpp` (nicht rekursiv) - die Hybridquellen aendern die
  Bilanzzeilen des Standardbaus damit nicht. Eigenes Ziel `hybrid`.
