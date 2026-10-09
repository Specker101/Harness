# Hybrid-Laeufer (Strang B) — Entscheidung A4, ab Batch 208 (2026-09-28)

## Was er ist
Ein **Testgeruest**, kein Liefergegenstand: das Original-ROM laeuft nur dort, wo noch
kein gepruefter nativer Kopf steht. Fortschritt = **schrumpfender Anteil
interpretierten Codes**. Ziel bleibt ein eigenstaendiges natives Programm
(Zielsatz in `AGENTS.md`/`readme.md`). Kein Ton, Eingabe als Attrappe,
Static-Recompilation vertagt.

## Plan
`analysis/hybrid-plan.md` — fuenf Schritte mit je `FERTIG WENN` + Gegenprobe:
1. **Kern** (B208, FERTIG) – `port/hybrid/ppc_kern.{h,cpp}` + `kern_diff.cpp`,
   Make-Ziel `hybrid` -> `port/build/kern_diff.exe`.
2. **Maschine** (B209, FERTIG) – `port/hybrid/maschine.{h,cpp}` (Speicherkarte +
   MMIO **mit MAME-Quelle je Bereich**, `EXC mmio` fuer alles Unbekannte) und
   `port/hybrid/hybrid_lauf.cpp`; Make-Ziel `hybrid` baut **zwei** Binaerien.
   **Die Gegenprobe ist NICHT `poc_ref_boot`** (das traegt nur den
   Kommandostrom) sondern ein **Lauf ab dem Einsprung** `80000024`
   (r2 = 0x800ADA5C, r1 = 0x803FFFC0). Lauf 1: **36 Schritte, Halt `80008C14`
   `EXC mmio (Sysreg lesen)`**; Rotprobe (SDA2-Basis bei `8000003C` mutiert)
   -> 21 Schritte, Halt `80008BD8` „ausserhalb der Karte".
2b. **Kontrollfluss/Supervisor** (NEU, ENTSCHIEDEN Nutzer 2026-09-28) – `blr`
   ueber LR, `bctr`/`bcctr`, `sc`/`rfi`, `mtmsr`/`mfmsr`, `mtspr`/`mfspr`,
   Decrementer/VBL, FPU-Anteil im Bootpfad. Gegenprobe: ISA-Orakel + Coverage.
3. **kHeads-Uebernahme** – Einhaengepunkt `port/include/port/host_registry.h`
   (`has()`/`find()`); statt `UnimplementedFunction` interpretiert der Kern.
4. **Boot** bis zur Hauptschleife.
5. **Erstes Attract-Bild.**

Budget-Nachtrag: „hoechstens 20" und „Abbruch nach 10" zaehlen **B-Batches**,
nicht Kalender-Batches. Referenzstroeme: es gilt die **gezaehlte Zahl 20**.

Budget: hoechstens **20 Batches**; **Abbruch nach 10 ohne Boot bis zur
Hauptschleife** (Zaehlung ab B208 = B-Batch 1). Mischverhaeltnis **2 B : 1 C**
(B208 B, B209 B, B210 C, danach 2:1). Kennzeichnung: Kopfkommentar
`// Hybrid-Geruest, im Port zu ersetzen` in jeder Datei unter `port/hybrid/`.

## Kernsemantik (B208, GEMESSEN)
Der Kern ist die **Kommandoschicht** von `scripts/m114_matrix.py` — nicht mehr:
* Formenliste C++ == Python: **1097 Zeilen, 0 Abweichungen** (`_m208/_formen_*.txt`).
* **Schritt-Differenz** ueber **939 932 Schritte / 902 Woerter / 0 Abweichungen**
  (`c_kopf.py schritte` -> `_m208/_schritte.bin`, 168,6 MB, **gitignoriert**,
  SHA-256 in `_m208/_schritte_sha.txt`).
* Rotprobe `subfc`-CA umgedreht -> **1096** Abweichungen, Ruecknahme -> 0.
* 1028 nicht modellierte Sondierwoerter liefern in **beiden** Welten `EXC`.
* 3800 Zufallsschritte (19 Formen x 200, Seed 208) -> 0 Abweichungen.
* **Formenzensus ROM** (`rom/build/830d01.27p.main.bin`, 178 342 Woerter):
  **57 von 248 Formen modelliert / 139 867 von 178 342 Woertern**; FPU-Formen
  (prim. Opcode 4, 48..63) getrennt: **0 von 17**. Das ist die Ausgangsgroesse
  fuer den Boot-Schritt.
* Der Kern fuehrt **keine Rufe** aus: `bl` setzt nur LR und liefert das Ziel.

## ISA-Orakel (B209, GEMESSEN) — die dritte Welt
`scripts/m209_isa_orakel.py`, eigene venv `tools/unicorn-venv` (unicorn 2.1.4,
**nicht** im Port und **nicht** im Standardbau). Es fuehrt jeden Schritt zusaetzlich
in Unicorn (QEMU-PPC32, Big Endian) aus und vergleicht GPR/CR/CA/LR/CTR,
Schreibwerte und Speicherbytes.
* **93994 ausgefuehrte Schritte (Stichprobe jeder 10.) -> 0 Abweichungen.**
  Damit heisst es nicht mehr „bewiesen", sondern **„Python-gleich
  (Schritt-Differenz) + ISA-Orakel 93994/93994"**.
* **Zwei gemeinsame Referenzfehler gefunden (NICHT behoben, Auftrag):**
  **F1** `m114_matrix.py:472-474` `slw` schreibt das **Quellregister** (ISA: Feld
  11-15 ist das Ziel) – **67 `slw`-Woerter** im ROM mit RA != RT; **F2**
  `branch_taken` zaehlt das **CTR** bei BO 0..3/8..11 nicht herunter
  (MAME `ppcdrc.cpp:2678-2682`: herunterzaehlen, wenn BO-Bit **0x04 nicht** gesetzt).
  Beide sitzen in der **gemeinsamen Basis beider Welten** – Korrektur nur mit
  Neuvergleich **aller 78 Koepfe** und neuer Schrittdatei.
* Bootpfad-Zensus **nur ueber ausgefuehrte Adressen** (ersetzt die alte
  178342-Zahl): **54 von 148 Formen / 15039 von 18165 Woertern**; Lueckenliste
  (94 Formen) in `_m209/_formen_bootpfad.txt`.

## Regeln (neu in B209)
* **R540** Die dritte Welt **sieht das CA nicht**, wenn nur die Registerbruecke
  benutzt wird: Unicorns `UC_PPC_REG_XER` ist ein **NO-OP** (Unicorn warnt selbst),
  `adde` liest es nicht. Ein Orakel ohne diese Messung vergibt **stille
  Freisprechungen**. Ausweg: `subfic`/`addic r31,r31,0` setzt CA, `addze r31,r30`
  liest es.
* **R541** Zwei Listen aus derselben Quelle werden ueber die **ZEILE** gepaart,
  nicht ueber einen Wert (Paarung ueber (Form, Wort) erfand 2 Abweichungen).
* **R542** Ein Orakel muss sagen, was es **nicht** beurteilen kann: 110 von 3800
  Zufallsschritten lehnt Unicorn ab (`UC_ERR_EXCEPTION`) -> **Orakelluecke, kein
  Freispruch**.
* **R543** Eine Schreibung ist erst durch das **Ruecklesen** belegt: der
  Schreib-Haken sieht `stmw` (op 47) nur beim **ersten** Seitenzugriff.

## Regeln (neu in B208)
* **R537** Eine Dedup nach (Wort, Vorzustand) ist bei **speicherlesenden** Formen
  nicht eindeutig — Lesewerte in den Schluessel nehmen oder im Satz mitfuehren.
* **R538** Ein **protokollierter** Schreibwert ist nicht der gespeicherte: die
  Python-Welt loggt den ROHEN Registerwert. Wer zwei Welten ueber ein Protokoll
  vergleicht, muss dessen Regel in beiden Welten gleich halten (C++ loggte zuerst
  beschnitten -> 1479 Abweichungen auf `stb`).
* **R539** Eine **Tafel** ist kein Zensus der Verdrahtung: `XO_ARITH` fuehrt
  `divw` (491), der Verteiler kennt es nicht. Formenlisten **sondieren**, nicht
  abschreiben.

## Fallstricke
* `port/hybrid/` liegt **ausserhalb des Standardbaus**: `Makefile` holt
  `$(wildcard port/src/*.cpp)` — **nicht rekursiv**. Deshalb aendern die
  Hybridquellen die Bilanzzeilen (`Modi`, `Regression`, `C Koepfe`, GL) nicht.
* `analysis/_m208/_schritte.bin` ist 168,6 MB -> `.gitignore`; nur Groesse, Anzahl
  und SHA-256 sind im Repo.
* Die Schrittdatei ist mit **little endian** geschrieben; der Kopf traegt
  `'M208STEP'` + u32 version + u32 count + u32 distinkte_woerter (der C++-Leser
  muss die Versionszelle ueberspringen — ein erster Anlauf las sie als Anzahl).
