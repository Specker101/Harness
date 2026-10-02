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

### Stand der B-Schritte (B221, BERICHTSPUNKT)

**Halt-Kette B221 (gemessen; Rohbelege `analysis/_m221/_front_nach_senke.txt`
und `_m221/_front_nach_sync.txt`).** Die Front steht jetzt bei `80013DFC`.

| Halt-PC | Wort | Art | Schritte | Wegmass | Loesung |
|---|---|---|---|---|---|
| `80013F24` | `98830048` `stb r4,0x48(r3)` | MMIO | 108226627 | 1652/42599 | B221 TEIL 2b: die Schreibsenke ist auf den **tatsaechlich beschriebenen** Block `0x40000000-0x40000008` erweitert (`_m221/_sink_block.txt`) |
| `80013F48` | `7C0004AC` `sync 0x0` | Form | 108226640 | 1665/42599 | B221 TEIL 2c: Form `sync` (op 31, XO 598) in BEIDEN Welten gebaut (MAME `ppcdrc.cpp:4190`/`:4194` "effective no-ops") |
| `80013DFC` | `881E0040` `lbz r0,0x40(r30)` | MMIO | 108546736 | **1716/42599** | **nicht geloest - BLOCKADE**: LESEZUGRIFF auf `0x40000000`, das ROM verzweigt an `andi. r0,r0,0xf8` auf den Wert; **WIDERLEGT (B231, M230-5, s. Text unter der Tabelle)** - die Begruendung "MAME bildet den Block nirgends ab" traegt nicht |

**WIDERLEGT (B231 TEIL 4a, Reviewer-Befund M230-5):** die Zeile `80013DFC`
oben trug die Begruendung **"MAME bildet den Block nirgends ab und der
MAME-Kern fehlt in diesem Baum"**. Beides traegt **nicht**:

* der Block IST abgebildet - `mame/mame/src/devices/cpu/powerpc/ppccom.cpp:322`
  `map(0x40000000, 0x4000000f).rw(ppc4xx_spu_r, ppc4xx_spu_w)` (403GA-SPU), in
  B223 geloest (Attrappe/SPU, `port/hybrid/maschine.cpp` `kSpuBasis`);
* der MAME-Kern **fehlt nicht**: das Verhalten eines wirklich UNMAPPED-Zugriffs
  ist im Baum definiert - `mame/mame/src/emu/emumem_heun.cpp:17`
  `return this->m_space->unmap();` (`handler_entry_read_unmapped::read`, mit
  `logerror` in `:10-16`). "Fehlt in diesem Baum" war eine **falsche
  Fundstelle**, nicht ein fehlender Kern. **Regel (R584-Klasse): erst
  `analysis/`, dann `mame/` nach der ADRESSE durchsuchen, bevor ein Block fuer
  "unabgebildet" erklaert wird** - hier haette `hornet.cpp:955` (die Karte)
  genuegt.

**2 Rotproben, beide ROT** (`--senke-aus` -> Halt `80013FB4` zurueck, Wegmass
1520/42599; `--form-aus 31/598` -> Halt `80013F48` zurueck, Wegmass
1665/42599).

**Berichtspunkt:** der vollstaendige Bericht (Stand, Rest, Geruest-Anteil,
C-Rate, Optionen) steht in `analysis/bericht-b221-berichtspunkt-hybrid.md`.

### Stand der B-Schritte (B218)

**Halt-Kette B218 (gemessen; Rohbeleg `analysis/_m218/_hybrid.txt`, je Halt
eine Zeile `Halt-PC | Wort | Art | Schritte | Wegmass | Loesung | Commit`).**
Der Lauf endet jetzt an der **Schrittschranke** (20000000) in der
Zeitbasis-Warteschleife - **nicht** mehr an einem Halt:

| Halt-PC | Wort | Art | Schritte | Wegmass | Loesung |
|---|---|---|---|---|---|
| `8000C8C8` | `7C000194` `addze` | Form | 6561235 | 635/42599 | B218 TEIL 1 (Formfamilie Carry, 16 Woerter) |
| `8000C8E0` | `7EAB0430` `srw` | Form | 6561241 | 641/42599 | B218 (`srw`, XO 536) |
| `80009EF8` | `B0C540C4` `sth` | MMIO | 8580477 | 678/42599 | B218 Attrappe [5] (K037122-Registerdatei) |
| `80014764` | `900B0000` `stw` | MMIO | 11016262 | 841/42599 | B218 Attrappe [6] (SRAM + Char-RAM) |
| `80014AB0` | `7C7BB1AE` `stbx` | Form | 11062368 | 918/42599 | B218 (`stbx`, XO 215) |
| `80014848` | `7D800026` `mfcr` | Form | 12197523 | 1201/42599 | B218 (`mfcr`, XO 19) |
| `80015040` | `7C045BD6` `divw` | Form | 12197638 | 1256/42599 | B218 (`divw`, XO 491 - seit B208 in der Tafel, aber NICHT verdrahtet) |
| `8000EC3C` | - | Schranke | 20000000 | 1475/42599 | **nicht geloest**: Zeitbasis-Warteschleife `FUN_8000EC08`/`FUN_80008448` |

**7 Rotproben, alle ROT** (`--form-aus 31/202`, `31/536`, `31/215`, `31/19`,
`31/491`, `--attrappe-aus 5`, `--attrappe-aus 6`): jede abgeschaltete Loesung
stellt den alten Halt wieder her (`analysis/_m218/_hybrid.txt`, Abschnitt
ROTPROBEN).

**BEFUND (mechanisch, nicht gesucht): `divw` war seit B208 ein UNFERTIGES
WERKZEUG.** Der B208-Fund ("`divw` steht in `XO_ARITH`, ist aber NICHT
verdrahtet, `FORM 31 491 nein exc`") ist in B218 **ausgefuehrt** worden - der
ROM-Befehl `7C045BD6` = `divw r2,r4,r11` bei `80015040`. Bis dahin war der
Eintrag eine Tafel ohne Verdrahtung (R539).

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

**AUFGEHOBEN (2026-09-30, Nutzerentscheidung, wortgetreu; eingetragen B229
TEIL 0a):** die Grenze "hoechstens 20" gilt **nicht mehr**. Wortlaut:

> Vorrang hat „beides je B-Batch, Front zuerst". Die Front vergrößert A und ist
> damit Voraussetzung für ein aussagekräftiges B/A. Die Grenze „höchstens 20
> B-Batches bis zum Attract-Bild" wird aufgehoben. Ein festes Batch-Budget gibt
> es nicht mehr. Als Sicherung gilt die bestehende Stillstandserkennung: Steht
> die Front über 3 B-Batches still, geht es als OFFENE FRAGE an mich. B/A bleibt
> das Hauptmaß, zählt aber erst ab dem Weiterlauf mit nativem Zustand als nativ.

**STILLSTANDSZAEHLUNG (B229 TEIL 0a, gezaehlt):** die Front steht seit **B223**
(`Halt-PC 80013F78`) still. Gezaehlte B-Batches **ohne Bewegung**: **B225** und
**B227** (B224/B226/B228 sind C-Batches). **B229 ist der dritte B-Batch** - die
Regel greift damit in B229 (OFFENE FRAGE an den Nutzer, s. Anker).

**FORTSCHREIBUNG B238 (2026-10-02, NEU, gemessen; M236-3):** gezaehlt wird am
**ECHTEN Halt** (`900000000 | 8001684C`, 900M-Lauf) UND zusaetzlich an der
**Preflight-Front** (`200000000 | 8000844C`, 200M). Beide stehen still: der
echte Halt ist in **B233, B235, B236 und B238** unveraendert `8001684C` (B234
ist C-Batch), die Preflight-Front im Kern (echter Halt) in denselben vier
B-Batches unveraendert `8000844C`. Die Front steht also seit **B233** still -
das sind (mit B238) **vier** B-Batches ohne Bewegung; der naechste waere B240.
Eine Umdefinition der Front
(Budget 200M/900M, R600) setzt die Zaehlung NICHT zurueck.
**Sicherungsfenster (M236-3): B238 und der naechste B-Batch (planmaessig B240).**
Bewegt sich der echte Halt bis dahin nicht ueber `8001684C` hinaus, wird Strang B
ausgesetzt, bis Paket E fertig ist, und die Frage kommt erneut an den Nutzer.

**B238-Ergebnis (2026-10-02, gemessen):** das SHARC-Antwort-Geruest ist gebaut
und laeuft (Handschlag bis Index 132, Pruefsummenprobe GLEICH 0x3CC9); der
**echte Halt bleibt unveraendert `8001684C`** (`analysis/_m238/_lauf900m_an.txt`).
Die **Preflight-Front** wandert mit dem Geruest von `8000844C` auf `8000EC3C`
(200M) - das ist eine **Schranken**-Bewegung, KEIN neuer echter Halt. Fuer die
Zaehlung zaehlt der echte Halt: **B238 ohne Bewegung** (B233/B235/B236/B238).

**FORTSCHREIBUNG B240 (2026-10-02, B240 TEIL 0, gemessen):** B240 ist der
**letzte Batch im Sicherungsfenster R236-1** (Fenster = B238 + naechster
B-Batch = B240, `hybrid-plan.md:267`). Gezaehlt wird die Stillstandszahlung
**am ECHTEN Halt** (900M-Lauf, Halte-PC) UND zusaetzlich an der
**Preflight-Front** (200M) - R600/M236-3. Eine Umdefinition der Front setzt
die Zaehlung NICHT zurueck. Bewegt sich der echte Halt in B240 nicht ueber
`8001684C` hinaus, ist das Sicherungsfenster ausgeschoepft; die Frage geht an
den Nutzer (ueber den Reviewer), **ohne** dass Strang B hier ausgesetzt wird.

**STILLSTANDSZAEHLUNG B240 (2026-10-02, B240-Ende, GEMESSEN):** der **echte
Halt** ist im 900M-Lauf **unveraendert `8001684C`** (`analysis/_m240/_lauf900m_an.txt`)
- also still in B233, B235, B236, B238 und B240. Die **Preflight-Front** (200M,
Schranke) wandert mit dem neuen SHARC-Lese-Modell von `8000EC3C` auf
`8000CB6C` (`analysis/_m240/_probe200m_antwort.txt`) - eine
**Schranken**-Bewegung, kein neuer echter Halt. Das **Sicherungsfenster R236-1
(B238 + B240) ist damit ausgeschoepft**: die Frage geht an den Nutzer (ueber
den Reviewer). Strang B ist nach Nutzerregel R236-1 ausgesetzt, bis Paket E
fertig ist.

**B241-Nachtrag (2026-10-02, B241 TEIL 0a, wortgetreu):** Sicherungsfenster
R236-1 ausgeschöpft: echter Halt 8001684C nach B238 und B240 unverändert
(`_m240/_lauf900m_an.txt`); Strang B ruht bis Paket E fertig, Frage an den
Nutzer gestellt (Review B240).

**NUTZERENTSCHEID R236-1 (2026-10-02 00:09, Option A, wortgetreu):**
> B238 bildet die SHARC-Antwortfolge aus dem MAME-Mitschnitt
> (capture/boot_20260829_194618.log) als Hybrid-Gerüst nach: gekennzeichnet
> "im Port durch den nativen SHARC-Code zu ersetzen", ROM-Stelle und Mitschnitt
> als Quelle, Gegenprobe "Gerüst aus = alter Halt 8001684C". Vorher prüfen, ob
> die Antworten vom gesendeten Inhalt abhängen (Prüfsumme FUN_8000c3a8). Wenn
> ja, die Folge nicht blind abspielen, sondern belegen, dass PPC-Daten und
> Mitschnitt übereinstimmen, oder die Abhängigkeit als Befund melden. Sicherung:
> Bewegt sich der echte Halt nach B238 und dem darauf folgenden B-Batch nicht
> über 8001684C hinaus, wird Strang B ausgesetzt, bis Paket E fertig ist, und
> die Frage kommt erneut an mich. Diese Grenze nicht durch Umdefinieren der
> Front umgehen.

**NUTZERENTSCHEID M236-3 (wortgetreu):**
> Die Stillstandszählung in hybrid-plan.md wird je B-Batch fortgeschrieben,
> gemessen am ECHTEN Halt (900M-Lauf bzw. Lauf bis zum Halt) und zusätzlich an
> der Preflight-Front. Eine Umdefinition der Front (R600, Budget 200M/900M) setzt
> die Zählung nicht zurück. Der aktuelle Stand gilt als erfüllt: B233, B235 und
> B236 ohne Bewegung des echten Halts. Die Sicherung aus R236-1 ersetzt für die
> nächsten zwei B-Batches die Eskalation; danach gilt wieder die Regel "3
> B-Batches still -> Frage an mich".

### Schritt 3 - kHeads-Uebernahme

**REIHENFOLGE DER B-SCHRITTE (B216 TEIL 4c, M214-4):**
1. **Schritt 2b Teil 2** wird als **Teil von Schritt 4** gefuehrt (Kontrollfluss/
   Supervisor ist Voraussetzung des Bootlaufs, kein eigener Meilenstein).
2. **Schritt 3 (kHeads-Uebernahme) ist VERSCHOBEN** - er laeuft erst, wenn der
   Bootlauf steht (der interpretierte Anteil ist ohne ihn messbar, und ein
   nativ laufender Kopf ohne Bootpfad bewegt den Meilenstein nicht).
   **Nachtrag B223: fuer EINEN geprueften Kopf vorgezogen (Reviewer).** Ohne
   Einhängepunkt bleibt R583 dauerhaft 0, die Messgroesse misst dann nur sich
   selbst; der Hybrid-Laeufer hat bis B222 **keinen** Einhängepunkt
   (Grep `HostRegistry` in `port/hybrid/` leer).
3. Das Feld **B-SCHRITT** eines Batch-Dokuments nennt den Schritt, an dessen
   **FERTIG WENN** gearbeitet wird - heute **Schritt 4**.

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

- **Mischverhaeltnis 1 B : 1 C (gueltige Regel, AB B222, NUTZERENTSCHEIDUNG
  R221-1, 2026-09-30, wortgetreu): "1 B : 1 C".** Dies ist die ERSTE
  `Mischverhaeltnis`-Stelle (Aussensicht M224-5). Praezisierung (1): vor dem
  Anbinden wird GEMESSEN (rein lesend), welche fertigen Koepfe auf den
  ausgefuehrten PCs des Hybrid-Laufs liegen. Praezisierung (2): Strang C baut
  Paket E zu Ende, danach gilt "ausgefuehrt zuerst". Die weiter unten
  stehende 2:1-Zeile ist **UEBERHOLT (bis B221)** und bleibt nur als Historie
  stehen.
  **Praezisierung (3) - NUTZERENTSCHEIDUNG 2026-10-01 (B231, wortgetreu):**
  "Ab dem nächsten C-Batch bitte abwechseln: ein C-Batch mit Köpfen aus den
  ausgeführten Funktionen (A), der nächste C-Batch mit Köpfen aus Paket E, bis
  Paket E fertig ist. Innerhalb eines Batches nicht mischen. B230 kann wie
  geplant laufen (zählt als A-Batch)." **Folge: B230 = A-Batch; B232 ist ein
  Paket-E-Batch, B234 wieder A usw., bis Paket E fertig ist.**
  (Damit ist Praezisierung (2) "Strang C baut Paket E zu Ende" **ABGELOEST** -
  es wird NICHT mehr am Stueck gebaut, sondern abwechselnd.) **NUTZERVORGABE zu R583 (2026-09-30, wortgetreu):** "Hauptmass fuer
  Strang B ist der **Anteil der ausgeführten Funktionen, die nativ laufen und
  referenzgleich geprueft sind**. Jede Funktion zaehlt einmal, gleich wie oft
  sie laeuft. Der Anteil der Schritte bleibt **Nebenzahl zum Priorisieren**
  (heisse Funktionen, Warteschleifen). Zusaetzlich der **Gesamtstand**:
  portierte und gepruefte Funktionen von allen Funktionen des Programms."
- **Referenzbeweis ohne Schatten (NUTZERENTSCHEIDUNG 2026-10-01 22:12 UTC,
  wortgetreu; eingetragen B237 TEIL 0):** "Ein bitgleicher Hash ohne Schatten
  ist kein Pflichtkriterium. Referenzbeweis sind (1) KOPFWEIT/B/A und (2) ein
  Lauf ohne Schatten mit gleichem Kopfsatz, der denselben ECHTEN Halt erreicht,
  mit gleicher Funktionsmenge und gleicher Reihenfolge der ERSTEN Eintritte.
  Prüfung (2) läuft einmal je B-Batch, nicht im Preflight. R593/R596 ruhen."
- **Hoechstens 20 Batches** bis zum Meilenstein ("ROM bootet bis zum ersten Attract-Bild,
  ohne Ton, Eingabe als Attrappe"). **AUFGEHOBEN (2026-09-30,
  Nutzerentscheidung, wortgetreu; eingetragen B229 TEIL 0a):** "Die Grenze
  „höchstens 20 B-Batches bis zum Attract-Bild" wird aufgehoben. Ein festes
  Batch-Budget gibt es nicht mehr." Vorrang hat „beides je B-Batch, Front
  zuerst"; Sicherung ist die Stillstandserkennung (Front über 3 B-Batches
  ohne Bewegung -> OFFENE FRAGE an den Nutzer; Zaehlung s. Budget-Nachtrag).
- **Abbruch nach 10 Batches ohne Boot bis zur Hauptschleife** (Zaehlung ab B208 =
  B-Batch 1). Bei Abbruch wird der Stand dokumentiert, das Geruest bleibt liegen; die
  Arbeit faellt an Strang C zurueck.
  **NUTZERVORGABE 2026-09-29 (wortgetreu, B216 TEIL 4a):** "Grenze 10 B-Batches ohne
  Hauptschleife ist kein automatischer Abbruch, sondern ein Berichtspunkt: Stand,
  geschaetzter Rest bis zur Hauptschleife, Anteil Hardware-Geruest vs. echte Pruefung
  portierter Funktionen; dann entscheidet der Nutzer." Das B-Batch 10 ist nach dem
  Mischverhaeltnis 2:1 ab B217 voraussichtlich **B221** (B217 B, B218 B, B219 C,
  B220 B, B221 B = 10. B-Batch). **(2:1-Zeile UEBERHOLT (bis B221).)**
- **Mischverhaeltnis 2 B : 1 C (ENTSCHEIDUNG Reviewer) - UEBERHOLT (bis B221);**
  gueltig ab B222 ist 1 B : 1 C (s. o.). B208 B, B209 B, B210 C
  (A1 MEM-Varianten + A2-Altposten + Paket E), danach wieder 2:1.
  **AB B222 GILT 1 B : 1 C (NUTZERENTSCHEIDUNG R221-1, 2026-09-30,
  wortgetreu):** "1 B : 1 C". Praezisierung (1): vor dem Anbinden wird
  GEMESSEN (rein lesend), welche fertigen Koepfe auf den ausgefuehrten PCs des
  Hybrid-Laufs liegen. Praezisierung (2): Strang C baut Paket E zu Ende, danach
  gilt "ausgefuehrt zuerst". **Messgroesse fuer Strang B ist ab jetzt der
  ANTEIL NATIVER KOEPFE AN DEN AUSGEFUEHRTEN SCHRITTEN (neue Regel R583)** -
  Wegmass und geloeste Halte sind nur noch Nebenzahlen. **Erste Messung
  (B222, `analysis/_m222/_schnittmenge.txt`): 0 von 91 C-Koepfen und 0 der
  Paket-E-Blaetter liegen auf den 1716 ausgefuehrten PCs; 9 der uebrigen
  616 Bau-Listen-Eintraege haben ihren Einstieg ausgefuehrt eingeholt -
  der Anteil nativer Koepfe ist damit 0.**
  **Nachtrag B212 (Fortschreibung):** B211 B, B212 B, B213 C.
  **Nachtrag B216 (Fortschreibung, TEIL 4b):** **B214 B, B215 B, B216 C**; ab B217
  wieder 2:1 (B217 B, B218 B, B219 C, B220 B, B221 B = 10. B-Batch).
  **Nachtrag B217 (Fortschreibung):** **B217 B** (7. B-Batch).
  **Nachtrag B218 (Fortschreibung):** **B218 B** (8. B-Batch).
  **Nachtrag B219 (Fortschreibung):** **B219 C** (C-Batch: Zaehlerdefinition
  `C verifiziert`, fuenf Paket-E-Koepfe, Paket-E-Neumessung).
  **Nachtrag B220 (Fortschreibung):** **B220 B** (9. B-Batch: Hybrid-Front-Zeile
  mit 20M-Nebenzeile, Schreibsenke `0x40000000`, Attrappe-[4]-Lesezaehler, Halt
  `80013FB4` geloest, Halt `80013ABC` als Blockade belegt).
  **Nachtrag B222 (Fortschreibung):** **B222 C** - erstes Batch nach der
  Nutzerentscheidung R221-1 (1 B : 1 C). Inhalt: Werkzeugauftraege
  (`_mem_ziele` ohne GPR-Loeschung bei op 16/18/19, Profil-Umleitung ueber
  `EV_OUT`, die zwei neuen Preflight-Zeilen `Profile reproduzierbar` und
  `Bauliste ⊆ Registry`, `R391-Reihenfolge` -> `R391 Commit-Reihenfolge`) und
  zwei Paket-E-Blaetter (`8003BB2C`, `8003D308`); `port/hybrid/` blieb
  unangetastet. Belege: `analysis/port-batch222-c-mem-ziele-und-paket-e-2026-09-30.md`.
  **Nachtrag B221 (Fortschreibung):** **B221 B (10. B-Batch, BERICHTSPUNKT)**
  (Stand/Rest/Geruest-Anteil, Attrappe [4] auf MAMEs `0x00800000`, Halt
  `80013F24` ueber die erweiterte Schreibsenke geloest, Halt `80013F48`
  (`sync`, 31/598) geloest, neue Front `80013DFC` als **Blockade** belegt -
  ein LESEZUGRIFF auf `0x40000000` braucht eine Entscheidung). Bericht:
  `analysis/bericht-b221-berichtspunkt-hybrid.md`.
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

### Neuschaetzung der B-Schritte (B217, TEIL 1; Vorlage fuer B221)

**OHNE SPR 8/9 als Fortschrittsmass.** Grundlage sind das **Wegmass**, die
**distinkten MMIO-Adressen**, die **Warteschleifen** und die **Halt-Kette**.
**Paket f (Boot/IO, hardwarespezifisch) ist GETRENNT ausgewiesen** (Nutzergabe:
der hardwareabhaengige Teil ist auf dem PC ersetzbar und nachrangig).

| Schritt | Restumfang gemessen | Einheit | Batches geschaetzt | Paket f |
|---|---|---|---|---|
| **Schritt 2b Teil 2** (Kontrollfluss/Supervisor) | Kontrollfluss steht (B211); seitdem **0** Halte an Kontrollfluss-Stellen - die offenen Formen sind ARITHMETIK (`subfe` B214, `addze` B217) | Halte | **0** (Formenarbeit laeuft IN Schritt 4) | nein |
| **Schritt 4** (Boot bis Hauptschleife) | **635/42599** = **1,49 %** der Karte; **7** geloeste Halte; **43** distinkte MMIO-Adressen beruehrt; **1483** SPR-/DCR-Woerter (3,48 %) | Kartenzellen-PCs / Halte / MMIO-Adressen | **3-5 weitere B-Batches** (HYPOTHESIS) | **ja** (Halte 1-4, 6 sind MMIO) |
| **Paket f** (MMIO/Boot-IO) - GETRENNT | **10** Kartenbereiche, davon **5** mit Attrappe, **5** ohne (Voodoo-CG, SHARC-Shared, K056800, Daten-ROM, Programm-ROM); **1483** SPR-/DCR-Woerter (3,48 %) | Bereiche / Woerter | **2-4** (HYPOTHESIS) | **ja** |
| **Schritt 5** (erstes Attract-Bild) | **4** Boot-Referenzstroeme (Hauptmass) von **20** vorhandenen; 9 GL-Waechter; MAME-Bilddump fehlt | Stroeme | **2-3** (HYPOTHESIS) | nein |
| **Schritt 3** (kHeads-Uebernahme) | **9** eingebunden / **22** nur geprueft / **55** nicht erreichbar | Koepfe | **verschoben** (erst nach Schritt 4) | nein |

**RECHENZEILEN JE SCHAETZZELLE (B218 TEIL 3, Befund F1).** Quelle der Reihe:
`analysis/_m218/_schaetzreihe.txt` (erzeugt von
`scripts/m218_schaetzreihe.py`: je B-Batch B208-B218 die Spalten Halt-PC, Art,
Schritte, Wegmass, geloeste Halte, davon MMIO; die ersten vier Spalten
MECHANISCH aus der jeweiligen `_m<k>/_hybrid.txt`, die Zuordnung "geloeste
Halte" mit Quelle je Zeile). **Median geloeste Halte/B-Batch = 1** (Messwerte
B209=0, B211=1, B212=1, B214=1, B215=1, B217=1, B218=7), **Median
MMIO-Halte/B-Batch = 1**.

* **Schritt 2b Teil 2, Zelle "0":** Rechenzeile *Halte an
  Kontrollfluss-Stellen je B-Batch = 0* (kein gemessener Halt der Kette
  80008C14 -> 8000EC3C war eine Kontrollfluss-Stelle; der Kontrollfluss steht
  seit B211) => 0 B-Batches. **Die Reihe traegt die Zelle.**
* **Schritt 4, Zelle "3-5 weitere B-Batches":** Rechenzeile *Median geloeste
  Halte/B-Batch = 1 => bei 3-5 weiteren B-Batches sind 3-5 Halte zu erwarten*;
  GEMESSEN ist aber, dass EIN Batch **7** Halte loesen kann (B218) - die Rate
  ist **nicht stabil**, und der Lauf endet jetzt an der **Schrittschranke**,
  nicht an einem Halt (die Zahl der Rest-Halte ist unbekannt).
  => **nicht ableitbar**; die Zelle bleibt HYPOTHESIS.
* **Paket f, Zelle "2-4":** Rechenzeile *offene Kartenbereiche ohne Attrappe /
  Median MMIO-Halte je B-Batch = 5 / 1 = **5,0 Batches*** (gezaehlt aus
  `port/hybrid/maschine.cpp`: 10 Bereiche, 5 mit Attrappe, 5 ohne -
  SHARC-Shared, K056800 Host, Daten-ROM, Programm-ROM, Programm-ROM-Spiegel).
  **Obergrenze:** darunter sind 3 ROM-/Datenbereiche, die keine Attrappe im
  Sinne der Halte brauchen. Die Rechnung liegt **ueber** der Zelle
  ("2-4 ist damit zu niedrig geschaetzt").
  **KORREKTUR B234 (Reviewer-Befund B234-1):** der SHARC-Shared-Bereich ist
  **nicht "belegte Fehlstelle"**, sondern **Modell nicht gebaut, Ausloeser
  ungemessen**. Das Protokoll ist im ROM-Code belegt
  (`bucket-c-rest-2026-09-15.md:62,67`: `FUN_8000b3c4` ACK-Handschlag, max.
  6 Versuche; `FUN_8000c3a8` Pruefsumme ueber 0x380x6 Woerter mit 0x80
  Sendeversuchen); ungemessen ist der **Rueckgabecode von `FUN_8000be40`**
  (`--trace` leistet die Messung). **ENTSCHEIDUNG (Reviewer): ein aus dem
  ROM-Code abgeleitetes Protokollmodell ist als Hybrid-Geruest zulaessig,
  wenn ROM-Stelle und Analysedokument genannt sind; die MAME-Quelle ist
  NICHT Pflicht, wo MAME konstruktionsbedingt keine hat.**
* **Schritt 5, Zelle "2-3":** die Reihe fuehrt **keine** Spalte zu
  Referenzstroemen oder Bildern => **nicht ableitbar**.

**HINWEIS: diese Reihe und ihre Rechenzeilen sind die VORLAGE fuer den
Berichtspunkt B221** (10. B-Batch); dort werden sie neu gemessen.
**AUSGEFUEHRT in B221:** die Neumessung steht in
`analysis/_m221/_schaetzreihe.txt@HEAD` (B208-B220), die Zelle-fuer-Zelle-
Neurechnung in `analysis/bericht-b221-berichtspunkt-hybrid.md@HEAD`, Abschnitt
b). Ergebnis: Schritt 2b Teil 2 traegt die Zelle weiter (`0`, Rechenzeile steht);
Schritt 4 und Schritt 5 sind **nicht ableitbar**; Paket f ergibt als
Obergrenze **5,0** Batches (die Zelle "2-4" ist damit **zu niedrig**).

### C-RATE - ZWEI RATEN NEBENEINANDER (B222, M221-5)

Ab B222 stehen **zwei** C-Raten nebeneinander, jede mit ihrer Definition - die
Zahlen sind nicht austauschbar (R387):

1. **Median der Zuwaechse der Kopf-Batches.** Zuwaechse der Zeile `C Koepfe`
   zwischen den Kopf-Batches: B198 17, B199 +28, B203 +14, B204 +5, B205 +9,
   B206 +5, B207 +0, B216 +7, B219 +5, B220 +1, B222 +2 (93 Koepfe).
   **Median der Zuwaechse = 5** (geordnet 0,1,2,5,5,5,7,9,14,28).
   Die frueher genannte "5-6" (B221) war der Mittelwert ueber die Zuwaechse
   inklusive der zwei Ausreisser; der MEDIAN ist **5**.
2. **Mittel ueber ALLE C-Batches.** Bezugsmenge = **alle Batches, die das
   Mischverhaeltnis als C fuehrt** (Abschnitt "Mischverhaeltnis", Nachträge):
   B198, B199, B203, B204, B205, B206, B207, B210, B213, B216, B219, B222 =
   **12 Batches**. Zuwachs der Zeile `C Koepfe` gegen den vorigen C-Batch,
   fehlende Koepfe = 0: B198 17, B199 +28, B203 +14, B204 +5, B205 +9,
   B206 +5, B207 +0, B210 +0 (Werkzeug), B213 +0, B216 +7, B219 +5,
   B222 +2 = **74**.
   **Mittel = 74 / 12 = 6,2 Koepfe je C-Batch.** (Der Median ueber dieselben
   12 Werte ist 5.) Die Bezugsmenge ist damit BENANNT, nicht geschaetzt.

**BEIDE Definitionen stehen hier; welche im Bericht zitiert wird, muss
dazugesagt werden.** Die B221-Angabe "5-6 C-Batches bis Paket E" ist eine
HYPOTHESIS und bezieht sich auf Rate 1 (Median).

### C-Rate fuer den Berichtspunkt B221 (Nachtrag B219, TEIL 4 / M218-6)

Der Bericht B221 enthaelt **auch die C-Rate** - drei getrennte Angaben, damit
die Zahl eine Definition hat (R387):

1. **Koepfe je C-Batch (gemessene Reihe).** `C Koepfe` aus der Preflight-Zeile
   (`c_kopf.py vergl alle`): B198 17, B199 45, B203 59, B204 64, B205 73,
   B206 78, B207 78, B216 85, **B219 90 Koepfe / 4833 Faelle / 0 Abweichungen**
   (`analysis/_m219/_c_kopf_lauf.txt@HEAD`), **B220/B221 91 Koepfe / 4860 Faelle
   / 0 Abweichungen** (`analysis/_preflight_220.txt@09065c3`, Zeile `C Koepfe`).
2. **Restvorrat.** `python scripts/c_kopf.py paket_e` (B219 TEIL 2):
   **Paket E offen 26 Koepfe / 2114 Insn**, davon echte Koepfe 22 / 2055 Insn,
   Blaetter 8 / 790 Insn - Quelle `analysis/_m219/_c_paket_e_vorher.txt@HEAD`
   und `_c_paket_e_nachher.txt@HEAD` (beide Messungen gleich; der Zaehler liest
   ROM + Bau-Listen, NICHT `port/`). **Die B208-Ist-Spalte 38/2674 ist damit
   UEBERHOLT**, ebenso die Harness-Nachrechnung "28 offen" - sie ist
   **widerlegt** (26 bzw. 22).
3. **Anteil Paket f GETRENNT.** Der 68K-Treiber-Audio-Rest (Paket f) steht in
   derselben Messung: **gebaut 4627 / 7959 Insn (58 / 97 Koepfe), OFFEN 1808
   Insn** - er zaehlt NICHT in die Paket-E-Zahl oben.

**Quellen je Zahl.** Wegmass `635/42599`, Schritte `6561235`, MMIO-Adressen
`43` - jeweils `analysis/_m217/_hybrid.txt@HEAD` (Rohausgabe
`port/build/hybrid_lauf.exe`) und `port/hybrid/hybrid_lauf.cpp` (Zaehler
`MMIO-Adressen`). Halt-Kette (7 Halte) - `analysis/hybrid-plan.md` "Stand der
B-Schritte" plus der B217-Halt `8000C8C8`. Kartenbereiche `10`/Attrappen `5` -
`port/hybrid/maschine.cpp` (`kMmio`/`kAttrappen`). SPR/DCR `1483` (3,48 %) und
FPU `0` - `analysis/_m214/_spr_dcr_fpu.txt@<B214>` (Zensus ueber die ganze
Karte). C Einbindung `9/22/55` - `analysis/_preflight_216.txt@82fe927`
(Zeile `C Einbindung`). Referenzstroeme `20` (4 boot + 2 inject + 14 stream) -
`capture/poc_ref_*.txt`. **Alle Batches-Schaetzungen sind HYPOTHESIS, kein
Messwert.** Diese Tafel ist die **Vorlage fuer den Berichtspunkt B221** (10.
B-Batch: Stand, Rest bis zur Hauptschleife, Anteil Hardware-Geruest vs. echte
Pruefung; Nutzerentscheid M208-5).

### Paket-E-Stand (feste Zeile, B220 / M219-3)

Paket E offen: **22 Koepfe / 1849 Insn** (Stand B222,
`analysis/_m222/_c_paket_e_nachher.txt@HEAD`); davon echte Koepfe **18 / 1790
Insn**, Blaetter **6 / 1059 Insn**. Vorgeschichte: B219 26/2114 -> B220 baute
`80055D28` (103 Insn) -> B222 baute `8005B3E0` (37), `8003BB2C` (21) und
`8003D308` (104). Die Zeile wird je C-Batch fortgeschrieben; die Messung liest
ROM + Bau-Listen, NICHT `port/`.

### Front der Halt-Kette (B220)

**B220 faehrt die Hauptzeile mit `--schritte 200000000`** (`scripts/m212_zeilen.py`,
`LAUF_FRONT`); die Vorgabe-Reihe (20M) laeuft als eigene Nebenzeile
`Hybrid-Lauf 20M` weiter. **Grund (R571/R572):** die 20M-Zeile endete in der
Zeitbasis-Warteschleife an der EIGENEN Schranke - eine Schranke ist kein Halt,
sie zeigt die Front nicht.

| Halt-PC | Wort | Art | Schritte | Wegmass | Loesung |
|---|---|---|---|---|---|
| `80013FB4` | `98030044` `stb r0,0x44(r3)` | MMIO (`0x40000004`) | 108226495 | 1520/42599 | B220 TEIL 2a Schreibsenke `0x40000000` (Wirkung UNBEKANNT, R573); Rotprobe `--senke-aus` ROT |
| `80013ABC` | `99070000` `stb r8,0x0(r7)` | MMIO (physisches RAM `0x000AF560`) | 108226554 | 1579/42599 | **BLOCKADE**: die MMU-Uebersetzung logisch `0x80000000+n` -> physisch `n` fehlt (MAME `hornet.cpp:950`); Entscheidung Freigabe vs. Alias offen |

**Zwei neue Preflight-Zeilen (B220):** `Hybrid-Senke` (Schreibzugriffe
`0x40000000`, Wirkung UNBEKANNT) und `Hybrid-Attrappe4` (Lesezugriffe
`0x780C0000-0x780C0003`; Antwort 0 gegen MAME `0x00800000`,
`mame/mame/src/mame/konami/konppc.cpp:76`/`:156`). Der Vergleichslauf mit der
MAME-Antwort aendert Front, Schrittzahl und Wegmass **nicht** (Rohbeleg
`_m220/_attr4_vergleich.txt`).

## Ausdrueckliche Nicht-Ziele

- Kein Ton, keine Eingabe (Attrappe), kein Spielbarkeitsziel.
- Static-Recompilation **vertagt** (readme.md, "Later").
- `port/hybrid/` liegt **ausserhalb des Standardbaus**: das `Makefile` baut
  `SOURCES := $(filter-out $(SRC_DIR)/render_gl.cpp,$(wildcard $(SRC_DIR)/*.cpp))`,
  also nur `port/src/*.cpp` (nicht rekursiv) - die Hybridquellen aendern die
  Bilanzzeilen des Standardbaus damit nicht. Eigenes Ziel `hybrid`.
