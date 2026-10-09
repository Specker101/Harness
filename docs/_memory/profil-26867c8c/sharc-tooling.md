# SHARC (ADSP-21062) Tooling & Extraction — verifiziert 2026-08-29

## Boot-Mechanik CONFIRMED (sharc-decompilation-plan.md §4.4)
- 1. Reset: Boot-DMA (8/48-Packing, dtype=1-Override!) liest leeres Shared-RAM → Stub=NOPs (Werte echt 0, Log-Bug gefixt).
- PPC lädt Stub (Byte-Strom, Offsets 0x0-0x5FF) + Programm-Payload (0x600+) ins Shared-RAM, released Reset (Komm-Bit28) → 2. Boot-DMA (Kontext `(no context)`, NICHT "(reset phase)") → 256-Instruktions-Stub nach 0x20000-0x200FF.
- Stub-Loader (PC 0x20063) kopiert Payload-Triples (erstes Wort → Bits 47:32) → PM 0x20040+. Entry 0x20004.
- A UND B sind CODE (B=Daten-Hypothese WIDERLEGT): 3392/3392 + 3413/3413 Triple-Match vs SRAM-Dump; 100% gültige Opcodes.

## Extraktion (2/3 Pfade fertig, byte-identisch)
- Dumps: Debugger-Watchpoints `wpd <addr>::dsp1,<len>,<typ>,1,"saved ...::dsp1; wpclear; go"` (KOMMAS nötig; `bp 0x20004::dsp1` feuert NIE — DRC). `saved 0x20000::dsp1,0x40000`=m_blocks[0] 1MB, `0x30000::dsp1`=m_blocks[1].
- PM-Formel: rel=addr-0x20000 (RELATIV!), slot=rel>>12, base=(rel&0xfff)+(slot>>1)*0x3000; even: (blk[base]<<16)|(blk[base+0x1000]>>16). → capture\sharc_pm_voodoo_20260829.bin (unidasm-Format 8B-LE).
- Log-Pfad: capture\boot_20260829_194618.log (57MB, wertegefixt) → sharc_upload_{0040,2800}_*.bin.
- Save-State-Pfad TOT (anonymous timers). Git-Recovery: 1,33GB-Gameplay-Log aus ac896cf via `cmd /c "git show ... > file"` (PS-Redirect = UTF-16!).

## Main-Loop (analysis/sharc-main-loop-analysis.md, 2026-08-29)
- HAUPT-SCHLEIFE = Opcode-Interpreter: 0x20DFB-0x20E00 (I4=Cursor DM(0x28240), R0=DM(I4,M1)=Opcode, I14=DM(0x28283,I0), JUMP(M8,I14)); Rückkehr 0x20E01 (Restore+Next).
- Dispatch-Tabelle DM(0x28283): 256 Einträge Opcode→Handler. Setup-Familie 0x20784-0x207E2 (CONFIRMED via Code+Log): 0x37=color0, 0x38=color1, 0x39=chromaKey, 0x3A=fbzColorPath, 0x3B=fogMode (1 WORT!), 0x3C=fogColor, 0x3D=fogTable(32 Werte), 0x3E=alphaMode, 0x3F=fbzMode, 0x40=zaColor. 0x56=Dreieck(0x20DD6), 0x68=textureMode(0x20C7A), 0x6C+=Upload-B.
- Objekt-Record im Stream: {0x0D,0x0C,0x18,6 Worte(3×32bit-Deltas),0x56,INDEX,0x3F} — 0x18-Handler liest 7. Wort=naechster Opcode; 0x56: INDEX→Pointer-Tabelle 0x01400000+DMA6→embedded 0x20000+high16(block[0]).
- PoC (poc/sharc_native_poc): 26/26 PASS für Dreieck 1. KORREKTUR: fdSdX=ΔS·RECIPS(u-Extent), fdTdY=ΔT·RECIPS(v-Extent) (ZWEI Reziproken, Listing 0x209F4/0x20A3B). fvertex-Bits: Cy=0x438AC800 (277.5625).
- RAM-Verifikation (Replay scope_session04 + wpd 0x1400007::dsp1): Pointer-Tabelle 0x1400000 = interne-SRAM-Adressen (entry[7]=0x29EC6, Blöcke 20 Worte). REALER Block: {selector:16,param:16}(0x37C0→Emitter 0x237C0), 4 Vertizes als 3×10-bit-SE (±465,±345,z=15) = Template-Quad; mappt mit sx=160/930, sy=62.4375/690, O=(424,246.34375) EXAKT auf Dreieck 1. ECHTES Format = lokale Packs+Matrix, NICHT absolute x.4 (PoC-Block war korrekte Umkehrung). S/T-Quelle = Kontext/Stream (nicht im Block lokalisiert). Dumps: sharcdumps\{sram,ram1400000,shared}_at_index7.bin. B1-GESCHLOSSEN (2026-08-31): Dumps sind LITTLE-ENDIAN (MAME saved = LE!); Tabelle statisch (0 Diff über 2 Momente, 1024 Einträge), Einträge = SRAM-Slots 0x29E0F+0x14n (20-Wort-Blöcke), Slot7=0x37C0-Block; KEINE Stores/DMA auf 0x1400000 im ganzen Programm → Fall A (Boot-Befüllung). Go für schlanken Konsument: Stream + SRAM-Dump + statische Tabelle.
- PoC-Update (echtes Format): Block-Unpack FEXT-3×10-bit + Matrix F4-F10 (F4=0, F5=160/930, F6=0, F7=62.4375/690, F8=424-15·F7, F9=215.125+330·F7, F13=0); x=F8+a·F5+b·F4+c·F7, y=F9+a·F6+b·F7+c·F7 (Emitter 0x237C0, 0x237CA-D3). Vertex-Auswahl Dreieck 1 = Blockworte +3,+5,+4 (Auswahl-Mechanik offen). ERGEBNIS weiterhin 26/26 PASS, bit-exakt. S/T/Alpha/W bewusst NICHT weiterverfolgt.
- Voodoo-Setup-Registeradressen: 0x02400051=color0(0x144), 52=color1, 4D=chromaKey, 41=fbzColorPath(0x104), 42=fogMode(0x108), 4B=fogColor(0x12C), 58=fogTable(0x160), 43=alphaMode(0x10C), 44=fbzMode(0x110), 4C=zaColor(0x130).
- Frame-Setup = Vektor 0x2001C → 0x20098 (I4=0x400000, Wort0=Opcode, Diagnose-Kopie, Heartbeat 0x7FF2=0xEEE0/1/6).
- Vertex-Pfad: 0x20CFF = Float-Matrix-Transform (16-bit-Variante 0x20CFF, 32-bit 0x20D05/46/48); Koeffizienten F4-F7+F8-F10 aus DM(0x00..04,I7); F14=DM(0x10,I6)=Skala; out=7 Worte/Vertex (R8/R9/R10/R15/R5/R6/R4) via DM(I3,M1).
- **DMA6 = EMPFANGS-DMA** (TRAN=0): 0x20D4A/0x20DD7 = Pointer-Tabellen-Lookup 0x01400000+R0 (Stream-Wort=Index) → EI6=I4(Block), II6=R14(SRAM), EC6/C6=R2, DMAC6=0→Enable; Poll DM(0x37) BTST 6 (2×). NICHT der Voodoo-Schreiber!
- **DMA7 = Voodoo-Burst** (STRONG INFERENCE): Handler 0x209D4/0x20A1D bauen Chain im SRAM 0x29DF0 (I2), DM(0x1D)=DMAC7, DM(0x4B)=CP7, IRPTL-0x20000-Frame-Sync; RECIPS+Newton = W-Kehrwert.
- **Emitter direkt**: 0x24A1F (3×10-Bit-SE-Pack/Stream-Wort FEXT 20:10/10:10/0:10; fstartA-Default=0x437F0000=255.0) & 0x222B3 (Extents F±F15). I3=0x02480022=fvertexAx, +0x1B..1E=fstartW/fdWdX/fdWdY/ftriangleCMD(0x02480040). Voodoo-Regnum = untere 8 Adressbits, s_register_table[regnum] (Byte regnum*4).
- 0x20968-Handler (Opcode 0x48-4B): 12er-DO, Wortpaar-Assembly R1=R1 OR R0<<16 → I1=0x024802xx = nccTable-Uploads.
- Stream-Wortpaare: 32-bit-Werte als {high16,low16} (z.B. fbzColorPath 0x0D426831 = 0x0D42,0x6831 CONFIRMED in Log).
- Kommandowort-Formen: (1) Opcode 0-FF, (2) High-Wort = Handler-Adresse (FEXT 16:16 + BSET 17), (3) 0x1400000-RAM-Zugriff (Opcode 0x60).
- Verifikation Frame#2942: 0x3F×34/frame (fbzMode/Objekt), 0x56×28 (Dreiecke) — strukturell bestätigt.

## Registerdatei + Record-Laufzeitfelder (CONFIRMED 2026-09-18, Batch 70)
- **SHARC hat EINE Registerdatei:** `#define REG(x) (m_core->r[x].r)` (MAME sharcops.hxx:30) + `union SHARC_REG { int32_t r; float f; }` (sharc.h) ⇒ **R3 und F3 sind dasselbe Register**. `DM(..)=R3` nach `F3=...` speichert den FLOAT. Es gibt (und braucht) **keinen F→R-Transfer** — die alte "Ganzzahl vs. IEEE"-Diskrepanz war ein Artefakt der Annahme getrennter Baenke.
- **`+6` (fstartW) = `16*recip(|+5|)`**, aber NICHT IEEE: SHARC `RECIPS` (128er-Mantissentabelle, MAME compute.hxx `recips_mantissa_lookup`) + Newton mit **weitergereichtem Residuum** (F12=F0*F12). IEEE-Division trifft nur 12/22 Records, je 1 ULP daneben. C++ braucht `volatile`-Rundungssperre (GCC `-ffp-contract=fast` = FMA-Kontraktion ⇒ 17/22).
- **`+9`/`+10` = `s16(hi16/lo16 EINES 32-Bit-Deskriptorworts)/16`** (DSD-Teil, Listing ~0x2236B: FEXT 16:16/0:16 (SE) + `FLOAT BY R7=-4`); Tabelle `MR1B + idx12`, **Stride M1 = 1**. `+11` = rohe 1:1-Kopie eines Objektworts.
- **Programmfeld-Kopf ist selbstbeschreibend:** `MR1B = I4 + hi16(W)`, `I4' = MR1B + lo16(W)`; `I4` setzt der **Dispatcher**, nicht der Handler.
- **Block-Layout DMA (`index >= 512`):** `w0`={handler,param}, `w1`=Kopielaenge, `w2`={a|?}, Nutzlast ab `w3`. Solche Bloecke liegen im **privaten RAM-Fenster** (ram1400000-Dump), NICHT im SRAM → erst dort suchen.

## MAME-Debugger: Speicher-Schreiben & Conditions (CONFIRMED 2026-09-15, inj-trigger-2026-09-15.md)
- `saved`/`filld`/`loadd` → **Data-Space** (4 B/Adresse, = SRAM/Shared). `fill`/`load` → **Program-Space** (8 B/Adresse) → es landen nur 16 Bit. Fuer Patches IMMER `loadd`/`filld` + `saved`-Roundtrip.
- Blanke Zahlen sind **HEX** (`,16` = 22 Adressen).
- Watchpoint-*Condition* wird mit dem **SHARC-PC** ausgewertet (exakte Partition R32+R37+OTH==ALL), `pc` in der `logerror`-**Action** ist der **PPC-PC** → PC-Ranges sind kein Typidentifikator.
- State wird VOR dem `-debugscript` geladen → Patches im Script ueberleben ins Gameplay (Read-WP bestaetigt).
- `-log` loggt jede SHARC-Shared-RAM-Read mit SHARC-PC → Dispatch sichtbar: `(020DD7) … = <index>` (0x56-Pfad), `(020D4A)` anderer Pfad.
- Rezept erzwungener Trigger: Hot-Slot-Block patchen (`w0 = {selector:16|param:16}`, Handler = 0x20000+selector) → normale Dispatch-Maschinerie ruft den Handler mit praepariertem Block.
- **FENSTER IST KEIN OBJEKTMASS** (CONFIRMED 2026-09-15): `wpd <a>::dsp1,24,w` = HEX 36 Woerter = genau 3 Records → hat die halbe Emission abgeschnitten und "genau 3 Records, unabhaengig von count" vorgetaeuscht. Fensterlaenge immer ≫ erwartete Emission; Fensterkante im Ergebnis mitpruefen.
- **Count-Semantik Familie 2 (CONFIRMED, inj-trigger §9)**: alle 4 Handler (237C0/237DA/232B0/23527) lesen als erstes Wort `w1` (I4 = Block+1): `R14 = DM(I4,M1)`, `R2 = FEXT R14 BY 16:16`, `LCNTR = R2, DO(..)` → Zaehler = `w1.high16`; `w1.low16 = 0xFFFF` = konstantes Fuellwort (in ALLEN realen Bloecken). Emission = 8 Stores/Block (Offsets +6,+0,+1,+2,+12,+18,+13,+14 ab Basis 0x283D4, I0-Schritt 24) = 2 Records; Records = Vertices = 2*(a+1), Stores = 8*(a+1), max Addr = 0x283D4+24a+18. Gemessen a=1/2/3/5 → 4/6/8/12. `param` (w0.lo) und `w1.lo` wirkungslos. a=0 = Endlosschleifen-Kandidat (MAME: CURLCNTR=0 unterlaeuft), real a∈{1,3,4,5}.
- **Reale Bloecke (sram_at_cacheD4.bin, Offset=(addr-0x20000)*4)**: `w1={a|0xFFFF}`; Payload-Laenge = 3*(a+1) Woerter (1,5 Woerter/Vertex): 0x29F0C a=1 → 6 Woerter, 0x29E0F a=4 → 15 ✓, 0x29EEE a=5 → 18 ✓. Tools `scripts/inj_real_blocks.py`, `inj_payload_len.py`.
- **Matrix-Herkunft neuer Typen (CONFIRMED 2026-09-15)**: Read-WP `0x28220::dsp1,0xC` feuert IM Emit-Moment direkt nach dem Vertex-Loop (MATX-Zeilen zwischen den F2A-Zeilen) → fester I7-Kontext 0x28220, gleiche Quelle wie 0x37DA. Vertex-Loop selbst matrixfrei (direkter FLOAT-Store).
- Tools: `scripts/inj_count_probe.py` (Varianten+Scripts), `inj_cnt_run.ps1` (MAME), `inj_count_analyze.py` (Muster-Matcher, wertunabhaengig). Tempo: 7 Laeufe ≈ 19 s Wall-Clock.

## Record-Scratch-Pipeline & Konsumenten (CONFIRMED 2026-09-15, family2-consumer-2026-09-15.md)
- **Record-Konsument = Walk/DMA6-Stufe im PC-Bereich 0x20000-0x21fff** (dort wird DMA6 per IOP programmiert: II6=0x40, IM6=0x41, C6=0x42, CP6=0x43, EI6=0x45, EC6=0x47 — Sites 0x2008a/b, 0x20bef, 0x20cb1, 0x20d5f, 0x20da7, 0x20dee). Sie liest **nur `+3/+4/+5`** (+6/+8).
- **Rohfelder `+0/+1/+2` sind handler-lokal**: Cross-Range-Test ueber feine PC-Buckets (2 Laeufe) → 100 % der Reads stammen aus demselben PC-Bereich, der geschrieben hat (0 Cross-Faelle). Reihenfolge pro Vertex: W012 → R012 → W345 → R345-Buendel.
- **Kein PPC-Zugriff auf den Record moeglich**: 0x283D4 = SHARC-interner DM (adsp21062 data_2m/4m); PPC-Karte hat nur 0x78000000 (Shared-RAM) + 0x780c0000 (Komm); 0x74000000 = k037122. Wertetest im Shared-RAM: 0 Treffer.
- **F2-Bereich im Normalbetrieb** (0x23200-0x236FF): schreibt ueberwiegend `+0/+1/+2/+6` (+9/10/11), gelegentlich auch `+3/+4/+5`; Cross-Range-Konsum seiner Werte nur fuer `+3`/`+5`. Der synthetisch getriggerte 0x32B0 fuellt nur die Rohstufe → **deshalb** nichts an Voodoo (kein Hinweis auf Fremdzweck).

## MAME-Debugger: Watchpoint-Rezepte (CONFIRMED 2026-09-15)
- **Fenstermarker**: `wpd <slot>::dsp1,1,r,temp0==2,{ … ; wpclear ; quit }` + `wpd <slot>::dsp1,1,r,temp0<2,{ temp0++ ; … ; g }`. Selbstbau (`temp0==0` armieren, `temp0>=1` beenden) schliesst das Fenster beim SELBEN Read (Aktion laeuft vor der Bedingung des naechsten WPs) → Fensterlaenge 0.
- **Kommentare im Debugscript: `//`** (debugcon.cpp process_source_file), NICHT `#`.
- **Zaehler-Budgets unzuverlaessig** (`tempN<X` + `tempN++` lieferte 1280 statt 500 Zeilen) → Fenster immer ueber ein Ereignis schliessen (WP-Aktion mit `quit`).
- **Wert-Watchpoint-Bereich**: Voodoo-Registerblock = `0x2400000,0x100` (Wertetest nur dort); ein Wertetest ueber das ganze 4-MB-Voodoo-Fenster trifft Texturspeicher (0x2480xxx). Negativtests mit Positivkontrolle (alle Writes im Fenster zaehlen).
- **Read-WP als Konsumentennachweis**: Read-Taps feuern auf CPU- *und* DMA-Zugriffe; Zaehlung „Reads je PC-Bucket x Feldindex" (Feld = (addr-0x283D4)%12) plus Vergleich wpdata mit dem letzten Write je Feld = Cross-Range-Konsum.

## Voodoo-Register-Ground-Truth (CONFIRMED 2026-09-15, record-field-labels-2026-09-15.md)
- **TEMP-REGTRACE** in `voodoo.cpp::map_register_w`: env `SSC_REGTRACE=<max Zeilen>` → Zeile `[:voodoo0] SSCREG <regnum> <name> <value> <ctx> (<pc>)`. Inert ohne die Variable. Rebuild nur voodoo.cpp+Link (28 s, KEIN REGENIE). **2026-09-15 ZURÜCKGEBAUT** (3 Stellen: Kopf-Block `s_regtrace_budget`/`regtrace_active`, Aufruf in `map_register_w`, `#include <cstdlib>`); beide Bäume danach byte-identisch (sha1 90edc4124199, 150309 B), kein Rebuild nötig (inert).
- **Der `pc` im Register-Log ist NICHT der Schreiber**: die FLOAT-Register kommen per **DMA-Burst** (DMA7-Kette); an den geloggten PCs steht in der Disassembly kein Voodoo-Write. Reihenfolge der Writes ist auswertbar, der PC nicht.
- **Dreiecks-Signatur**: pro Dreieck genau 19 FLOAT-Register in fester Ordnung (fvertexAx..Cy, fstartA, fdAdX/Y, fstartS/T/W + Gradienten, ftriangleCMD). Keine fstartR/G/B, keine Integer-Farbgradienten → Farbe ueber color0/color1 + fbzColorPath.
- **I7-Kontext 0x28220 ist pro Objekt** (Adresse fest, Werte wechseln) — §9.4 inj-trigger meint nur die Adresse.
- **Differenzrezept am REALEN Block**: Originalblock aus `sram_at_cacheD4.bin` laden (`loadd ...,0x29F0C::dsp1,0x14`), genau EIN Payload-Halbwort um +0x200 verschieben, SSCREG-Trace diffen (`scripts/inj_diff_make.py` + `inj_diff_delta.py`). 13 Laeufe ≈ 36 s.
- **Ergebnis Feldlabels**: `+0/+1/+2` = Quellkoordinate des Vertex (3 Haelften = 1 Vertex, jede Haelfte bewegt genau eine Ecke in x UND y) = CONFIRMED; `+6` = 16/|z| CONFIRMED; `+11` = Alpha 0..255 -> fstartA (108 eindeutige Korrelationstreffer) STRONG; `+8`/`+10` = 16-Bit-SE-Felder aus einem Tabellenwortpaar (Disasm 0x23360-0x23366) STRONG; `+3/+4/+5` = Transform-Ergebnis (View-Space) STRONG; `+9` OFFEN.
- **Familie 2 emittiert selbst NICHT** (2026-09-15 weiter geklaert, `family2-consumer-2026-09-15.md`): der 0x32B0-Handler schreibt nur +0/+1/+2/+6 (+9/+10/+11 fuer manche Records) + Matrix-Zustand 0x28206-0x28212/0x2823F, KEINE Voodoo-Register, KEINE DMA/IOP-Programmierung; seine Werte werden nie zurueckgelesen (3046 Record-Reads im Fenster, 0 Injektionstreffer) und erscheinen nie im Shared-RAM (PPC-sichtbar) oder im Voodoo-Registerblock.
- **Record-Cache 0x283D4 wird in ALLEN 12 Feldern gelesen** (Read-WP-Histogramm; Spitzen bei +6 und +8) → echtes Per-Vertex-Struct.
- `-log`-Zeilen tragen ein Geraetepraefix (`[:voodoo0] ...`) → Grep ohne `^`-Anker.

## Transformationsstufe Familie 2 (CONFIRMED 2026-09-15, family2-xform-trigger-2026-09-15.md)
- **Transformroutine = PC 0x23502..0x2350C** (RTS bei 0x2350A, Delay-Slot 0x2350B!): liest Matrix aus I7 (0x28220 ff.), schreibt `+6` (0x23504), `+3` (0x23507), `+4` (0x2350B), `+5` (0x2350C) auf `DM(off,I2)`. Aufruf indirekt: `I8 = 0x00023502` (gesetzt 0x23299/0x232E2 in der 0x32B0-Route) + `IF EQ, CALL (M8,I8)` (0x2330A, 0x2332A, 0x23364, ..., 0x234F0).
- **Altes Tag-Fenster [0x232B0,0x23400) schloss 0x23502..0x2350C aus** → "0x32B0 schreibt kein +3/+4/+5" war ein FENSTER-ARTEFAKT.
- **Zwei Stufen**: (a) Roh-Fuellstufe (PC 0x232B0-0x232E4, immer, 8 Stores/Block = 2 Records, `+6`-Guard `FFFFFFFF` + `+0/+1/+2`); (b) Walk (PC 0x232E4-0x23320, schreibt `+9/+10/+11`) + Transformroutine (TRW).
- **AUSLOESER der zweiten Stufe = Block-Schwanz `+16..+21`** (Slot ist 22 Woerter, Ende vor Nachbarblock): F2-Folge `5006C001 00000000 000001FF 200AC000 800EC003 8012C002` ⇒ TRW laeuft; F1-Folge `400EC002 00000000 0012C000 8006C003 800AC001 00000000` ⇒ TRW entfaellt. Ausgeschlossen per Differenztest: Selektor, `param` (w0.lo), Payload-Werte, Deskriptorpaar `+8/+9` (in BEIDEN Familien `00030004 08241CC7`).
- **Read-Probe**: Roh-Fuell liest `+16`; Walk liest `+17..+21` und springt im positiven Fall auf `+16` ZURUECK (Iteration, dann Wiederholung); im negativen Fall einmalige Folge ohne Ruecksprung; der Dispatcher (PC<0x23000) liest `+9/+10/+11` nur im positiven Fall.
- **Payload-Abhaengigkeit ist das Messinstrument**: gleicher Block, nur Payload geaendert ⇒ TRW-Werte aendern sich (beweist: die Stufe transformiert UNSER Objekt, nicht ein Fremdobjekt, das den Record-Cache direkt danach wiederverwendet).
- **Echte 0x32B0-Bloecke im Dump**: 75 Kandidaten (`w1.lo==0xFFFF`), z.B. 0x2AC0F (a=1), 0x2ABD4 (a=5), 0x2B15D (a=4); 0x3527: 9 (0x2CB80). Die 0x37DA/0x37C0-Suche aus Batch 4-6 hatte sie nicht erfasst.
- **Emit-Freigabe** haengt an Software-Flags in USTAT1 (`BIT SET/TEST 0x100/0x400/0x700`, 0x232FF/0x234F5) + `CALL 0x220D1` — nicht am Selektor.
- Neu: `scripts/sharc_flow.py` (cf/all/reach/entries auf der unidasm-Liste), `inj_xform_make.py`, `inj_xform_swap_make.py`, `inj_xform_probe_make.py`, `inj_xform_run.ps1`, `inj_xform_analyze.py`.

## Objektblock-Layout & Programmfeld (CONFIRMED 2026-09-15, Batch 8)
- **Offset-Regel (735/738 Bloecke, 99,6%):** `prog_off = hoff + 1 + (w[hoff]>>16) + (w[hoff]&0xFFFF)`,
  `hoff = 2 + Payload-Laenge` (= Adresse des 4-Wort-Kopfes). Disasm-Beweis: 0x232D8-0x232DE
  (`R0=I4; R2=FEXT R14 BY 16:16; R13=FEXT R14 BY 0:16; R0+=R2; R1=R0+R13; I4=R1`).
  Die alte Formel `2+L+8` ist ein **a=1-Sonderfall** (dort hi+lo=7). Werkzeug
  `scripts/f2_blocklayout_rule.py`, `f2_progfield_census.py`.
- Programmfeld-Offsets real: 0x29F0C/a1=+16 · 0x2A83E/a3=+28 · 0x2B15D/a4=+25 · 0x2AC26/a4=+29 ·
  0x29E0F/a4=+42 · 0x2ABD4/a5=+35 · 0x2CB80/3527 a5=+36 · 0x29E4E/37C0 a3=+14.
- **Programmfeld = 0-terminierte Kommandoliste.** Interpreter PC 0x232E4 ff. ist eine feste
  Kette von Stufenbloecken (I14 = naechster Block); Wortwert 0 ⇒ `IF SZ, JUMP (M8,I10)` = Ende
  (nur dieses Wort wird noch gelesen). Kopfwort + 2 Operanden (Konsum gated ueber **bit30**;
  2. Operand = 3x10-Bit-Tripel, `FEXT 20:10/10:10/0:10` @0x232F1). Zyklenzahl folgt der
  Liste, NICHT dem count-Feld — exakte Regel siehe Batch-9-Abschnitt unten (KORRIGIERT).
- Feldrollen (Wort-Differential, 26 Laeufe, `inj_prog_*`): `bit30` Kopf = **Aktiv-Bit**
  (0 ⇒ 0 Zyklen, alle Woerter werden trotzdem gelesen); `bit28` Kopf / `bit29` Element = Modus
  (jeweils −1 Zyklus, Werte verschieben sich); `idx9` = Datenquellen-Index; `idx12`, `f6`,
  `bit31` in dieser Messung **wirkungslos**; `+17` wirkungslos, `+18`=0 ⇒ 0 Zyklen.
  Nullsetzen von `+19`/`+20`/`+21` ⇒ 1/2/3 Zyklen + Reads enden dort.
- Zwei Kopf-Formen: `low16=0xC00y` (f6=44) und `0xF00y` (f6=63, 15 Bloecke). Familie **0x3B97
  (3 Bloecke) folgt der Regel nicht** (`w[+11]=5007DAD6` ist selbst ein Kommando).
- **WIDERLEGT in Batch 9** (s. u.): "bit28=0 ∧ idx9=3 zusammen ⇒ 0 Zyklen" war ein Artefakt
  einer 6-Wort-Variante. Nur-Kopf-Patch ⇒ 3 Zyklen. 0 Zyklen nur bei F1-Kopf + F1-Elementen.
- Messfenster-Konvention: Fenster = 1. Read Blockkopf armiert / 3. schliesst (bleibt ~30k
  Ereignisse offen!) → Auswertung auf **erstes Dispatch-Fenster ab erstem BLKR** begrenzen
  (a=1: 64, a>1: 480 Ereignisse). Injektionsfenster 45 Woerter mit **verbatim-Fuellung** aus
  dem Dump (sonst Nachbar-Slots 0x29F22/0x29F38 zerstoert); Roundtrip bit-exakt gegen Batch 7.
- Pointer-Tabelle 0x1400000 = flaches Array: Index 10 → 0x29F0C, 11 → 0x29F22, 146 → 0x2ABD4,
  147 → 0x2AC0F; Slot 0 = 0x29E0F (auch Indizes 312-318).

## Weitere Watchpoint-Fallstricke (CONFIRMED 2026-09-15, Batch 7)
- **Nicht aufloesbares Symbol in der logerror-ACTION ⇒ stummer WP-Ausfall**: `logerror "…%08X",wpaddr,wpdata,ustat1` schreibt KEINE Zeile (Fehler nur auf der unsichtbaren Debugger-Konsole) → der Tag sieht wie "0 Ereignisse" aus, waehrend symbolfreie WPs normal feuern. Actions nur mit `wpaddr`/`wpdata`; Registerzustand ueber *Conditions*.
- **Tag-Zeilen beginnen am Zeilenanfang** — Zaehlmuster mit fuehrendem Leerzeichen treffen nicht; Auswertung in Python ueber den ersten Token.
- **Runner-Schleifen brechen frueh ab**: `inj_xform_run.ps1 <mehrere Varianten>` beendet nach der ersten Variante (Write-Error im foreach); einzeln aufrufen. Der im Runner mitgezaehlte Tag-Report ist unbrauchbar.
- Injektionslaenge fuer Slot 0x29F0C: **0x16 (22 Woerter)** — erst damit ist der Schwanz `+16..+21` Teil der Injektion (0x10 war zu kurz).

## Batch 66: Koeffizientenquelle der Transform-Matrix (MESSUNG)
- Der I7-Block `0x28220` im Dump `sram_at_index7.bin` trägt an `+0x12/+0x13` **4096 = 0x100<<4** und
  **3072 = 0x0C0<<4** (= die Werte des **kalten** {03}-Pakets `w3=0x0100`, `w4=0x00C0`), an
  `+0x14/+0x16` `-7088`, `+0x15/+0x17` `443`, an `+0x1A..+0x1D` `0.5779/1.3339/0.4334/1.1878`;
  I6+0x0A = **16**, I7+0x1E = **-16** (beide als `R3 = DM(0x0A,I6)`, `R0 = DM(0x1E,I7)` im 0x03-Handler).
- Die im PoC gelösten Transformkoeffizienten (`160/930`, `62.4375/690`, Bits `43D35243`/`4374FC86`)
  kommen im **gesamten** Dump **nicht** vor ⇒ sie werden zur Laufzeit gerechnet (HYPOTHESIS: Handler
  `0x2012A`–`0x20151`, LOGB/SCALB/RECIPS+Newton). Beleg: `analysis/_m66_ctx.txt`.
- Workspace-Kopie der Dumps: `capture/sharcdumps/{sram_at_index7.bin,ram1400000_at_index7.bin}`
  (nicht versioniert); DM-Wortindex = `addr - 0x20000`, alles LE.

## Batch 68: Record-/Unpacker-Familie (CONFIRMED, Port)
- **Familie = 23 Kopien, kein Unterprogramm:** Dispatch-Verzeichnis hat 23 Dreiergruppen
  {B, B+0x17, B+0x2E}. B = 3x16-Bit (1,5 Worte/Vertex, N = 2(a+1)), B+0x17 = 3x10-Bit
  (1 Wort/Vertex, N = a+1), B+0x2E = Wiedereintritt ohne Vertex-Schleife. 0x7F/0x81 sind die
  direkten Emitter (0x24A1C/0x24A1D), KEINE Unpacker. Werkzeug `scripts/m68_family_table.py`.
- **Blocklayout (2 Faelle):** Index < 512 = Direktpfad (SRAM), Kopf `{handler|param}`,
  Zaehler in `w1 = {a|0xFFFF}`, Nutzlast ab `w2`. Index >= 512 = DMA-Pfad (privates RAM),
  `w1` = Nutzlaenge der Kopie, Zaehler in `w2`, Nutzlast ab `w3` (Dispatcher 0x20DD6:
  EI6=I4=block+2, C6=EC6=w1, I4=II6=DM(0x28209)).
- **Record-Pool 0x283D4:** 12 Worte je Vertex, `+0/+1/+2` = Quellkoordinaten als f32.
  BIT-EXAKT gegen den Dump nachgewiesen (Block Index 1037/DM 0x14032CA, a=10, 22 Vertizes,
  0 Abweichungen). Weiteres Feld: `+6` = Guard 0xFFFFFFFF im 0x56-Pfad; `+3..+5` Transform,
  `+7/+8` Ganzzahlen, `+9/+10/+11` S/T/W-artig (Teil 3).
- **Emissionsregel = Strip** (Glide/D3D: `(v0,v1,v2),(v1,v3,v2),...`); B00 ist das ZWEITE
  Strip-Dreieck des 4-Vertex-Blocks (STRONG INFERENCE; 56 Dreiecke vs. 48 GT-Bursts).
- **DM-Adressraum ist EINES:** SRAM 0x20000+ UND privates RAM 0x01400000+ (derselbe Dump wie
  die Zeigertabelle). Nur ein Fenster lesen = Daten faelschlich "nicht auflösbar" (82 Faelle).
- Auftraege sind `0x56`/`0x57`/`0x5D` (bei `0x5D` steht der Index im 16. Nutzlastwort).
- Port: `port/sharc_records.*`, Modus `port_gl.exe glown` (Port-eigenes Frame, 2999 Dreiecke),
  Anker-Abschnitt 8 in `vertex_check.cpp`. Regression 32 Frames + 7 Anker.

## Batch 69: Der 19-Register-Burst (S/T/W/Alpha) — Datensatz und Anker
- **Kettenpuffer DM 0x29DF0** = Ausgabepuffer der Emitter (I2/I3-Basis) und **im Dump der
  Registerwert-Satz des ZULETZT emittierten Dreiecks**: +0x00..+0x05 = Bildkoordinaten A,B,C
  (f32, Pixel); +0x12..+0x1D = die 12 FLOAT-Register in Reihenfolge
  `fstartA,fdAdX,fdAdY,fstartS,fdSdX,fdSdY,fstartT,fdTdX,fdTdY,fstartW,fdWdX,fdWdY`;
  **+0x1E = 1/det (Rechenkern, KEIN Register)**; +0x06..+0x0E (9 Worte) blieben im Dump 0.
- **Record -> Register (CONFIRMED, bit-exakt 10/12 + 2 Nullvorzeichen):**
  `k=+6=16/|z|`; `fvertexXx/Xy = +7/16`,`+8/16`; `fstartW=k`; `fstartA=+11` (1:1-Kopie);
  `fstartS=+9*k`, `fstartT=+10*k`; Gradienten = baryzentrische Gradienten der W-skalierten
  Größen (`V*k` bzw. `V*W`) über Pixelkoordinaten; `fdAd*`/`fdWd*` = 0 bei gleichem Wert.
- **19-Register-Signatur (CONFIRMED, echte Spur):** genau diese 19 Namen, alle gleich häufig
  (Frame #2942: 73/74 Dreiecke vollständig, Reihenfolge 73/73, 444/444 Koords x.4-quantisiert,
  fstartA 0..255, fstartW in (0,1), ftriangleCMD 66 verschiedene Werte = Kommandowort).
- **OFFEN:** Producer der Kettenworte (DMA7-Handler 0x52-0x55 schreiben Ganzzahlen, Dump hat
  IEEE; **kein F→R-Transfer im ISA**, FPACK/MANT 0× im Programm) und die QUELLE der Felder
  +6/+9/+10/+11 (F2-Walk-/DSD-Stufe; +9 dort HYPOTHESIS).
- Referenzwerte erster B00-Dreieck aus der Spur: A=(344,215.125) B=(504,215.125)
  C=(504,277.5625), S=0.080314 T=0.075852 W=0.000296 A=214.578857.

## Tooling
- Ghidra: kein SHARC-Modul. unidasm.exe GEBAUT: `make -j16 TOOLS=1 REGENIE=1` OHNE SUBTARGET (mit SUBTARGET: Fehler); danach sscope-Rebuilds brauchen `SUBTARGET=sscope REGENIE=1`. Listing: `cmd /c unidasm ... > file` (PowerShell-`>` = UTF-16-Falle!).
- Eigene Bereichs-/DM-Werkzeuge: `scripts/m69_dis.py <start> <end>` (Listing-Ausschnitt),
  `scripts/m69_dm.py <addr> <count>` (SRAM-Dump, LE-u32, Index=addr-0x20000).
- **Voodoo-Registerspur als Zweitanker**: `analysis/_f2942_rawtrace.txt` (Frame #2942, Zeilen
  `VOODOO.REG:<name>(chip) write = <wert>`; NEGATIVE Werte mit erfassen!),
  Auswertung `scripts/m69_regtrace_probe.py`. Die Spiel-Logs sind 2,2 GB -> immer das
  extrahierte Fenster benutzen.
- MAME-Debugger: watchpoints ok, bp auf dsp1 unzuverlässig.
- konppc.cpp: Log-Bug GEFIXT + VERBOSE(LOG_ALL) aktiv (beide Bäume).

## Kommando-Semantik / Zyklus-Modell (CONFIRMED 2026-09-16, Batch 9, `analysis/cmd-semantics-2026-09-16.md`)
- **Vokabel im Dump klein (Begrenzung haelt):** 8 Flag-Kombis (b31|b30|b29|b28), `f6 ∈ {44,63}`
  (44 = C-Form, weil 0x2C ⇒ Bits 12-15 = 0xC ⇒ `low16 = 0xC00y` mit y=idx12!), `idx12 ∈ 0..0x12`,
  `idx9 ∈ 1..17`. 735 Kopfwoerter/37 Werte, 3510 Listenwoerter/89 Identitaeten (ohne idx9).
  735/735 Koepfe haben **bit30=1**; 99 Listenelemente haben ebenfalls bit30=1 (eigene 2 Operanden).
- **ZYKLEN = Anzahl VERSCHIEDENER `idx9` in der Liste** (Reihenfolge = erster Auftritt; Kopf zaehlt
  nur bei `bit28=1`, weil der bit28=0-Zweig ab 0x23319 kein `FEXT R13 BY 18:9` hat).
  Jeder zaehlende Aufruf schreibt 4 Record-Woerter: Felder `+6`,`+3`,`+4`,`+5`.
  "1 Kommando = 1 Zyklus" gilt nur bei lauter verschiedenen idx9. Bestaetigt a=1 (0x2AC0F: 4)
  und a=4 (**0x2B15D: 9 vorhergesagt, 9 gemessen**, TRW=36; 18 Kommandos, 9 distinct idx9).
- **bit28** (nur mit bit30=1 wirksam) schaltet den EIGENEN Aufruf des Kopfes ab (Werte = v2v3v4)
  und die 3 DSD-Writes (`+9/+10/+11`); **bit31** und **idx12** wirkungslos.
- **Wert eines Aufrufs = f(idx9)** (blocklokal; belegt: Kopf mit idx9 1→3 liefert den Wert des
  Elements mit idx9=3, Reihenfolge v3,v2,v4). **idx9-Duplikat ⇒ kein Aufruf.**
- **OFFEN:** (a) geaenderte Element-Flags an `+19` (b29→0 / alle Flags 0 / b31) entfernen den
  **letzten** Aufruf (3 Varianten identisch) → Abbruchbedingung (Kandidaten 0x232FC IF GE,
  0x2331E IF LT, 0x23310/USTAT1 0x100, 0x2330C `BTST R13 BY R7` mit `R7 = DM(0x0B,I6)`);
  (b) F1-Kopf + F1-Elemente zusammen ⇒ 0 Zyklen (F1-Kopf allein 3, F1-Elemente allein 2);
  (c) F-Form f6=63 (15 Bloecke); (d) 0x3B97.
- **Fallstrick 27:** `idx9` (Bits 18-26, `+0x40000` je Schritt) nicht mit `idx12` (Bits 0-11,
  `+0x001`) verwechseln — "idx9 1→3" ist `0x400EC001`/`0x500EC001`, NICHT `0x...C003`.
  **Fallstrick 28:** `f6 ∉ {44,63}` in einem geparsten Kommando = Liste ueber ihr Ende hinaus
  gelaufen (30 von 4245 Woertern; auffaellig auch `idx12` = 0x400/0xC00).
- Tools: `scripts/f2_cmd_census.py` (Vokabel/Flag-Statistik), `f2_cycle_model.py` (Modell +
  Gegenprobe), `f2_cycle_model_candidates.py` (Bloeke, deren Liste komplett ins 45-Wort-Fenster
  passt: 660/735, a>=2 nur 174, in der F2-Route nur 0x2B15D), `inj_prog_probe_make.py`,
  `inj_prog_probe_analyze.py` (Zyklen = TRW/4, Aufrufwerte, Feldsequenz).
  Tempo: a=1-Lauf 4,5 s; a=4-Lauf (0x2B15D) 104 s / 493 MB Log.
- **GEKLAERT 2026-09-16 (Batch 10, Instruction-Trace):** Die "vorzeitige Abbruchbedingung"
  ist das `bit29`-Gate `0x23374 BTST R13 BY 29` + `0x23375 IF SZ, JUMP (0x23379) (DB)`:
  es UEBERSPRINGT den LT-Zweig `0x23378 IF LT, JUMP (0x23359)` (Ruecksprung in die eigene
  Zweithaelfte = der *zusaetzliche* Deskriptor+Transformaufruf). `bit29=0` ⇒ Gate genommen
  ⇒ eine Zweithaelfte-Ausfuehrung samt Aufruf fehlt (15→12 Deskriptor-Writes, 16→12 TRW;
  fensterstabil = echter Verlust). Wirkung **nur am ERSTEN Listenelement** (b29 auf Element 2/3
  aendert nichts). `0x232FC IF GE` (Vollpfad) und `0x23310`/USTAT1-Tore (Emit-Handshake) sind
  NICHT die Ursache. Aufrufpfad dynamisch bestaetigt: `0x2330A IF EQ, CALL (M8,I8)` -> 0x23502,
  Rueckkehr 0x2330D. Record-Slot = f(idx9) (Transformziele wandern 12 Woerter je Aufruf).
- **Instrument Instruction-Trace:** `trace <abs-pfad-ohne-leerzeichen>,dsp1,noloop` in der
  ARMENDEN WP-Action starten, `trace off,dsp1` in der schliessenden ⇒ kompletter
  Kontrollfluss im Messfenster (beginnt exakt am Armierungs-Read). Ohne `noloop` kollabiert
  MAMEs Loop-Erkennung die gesuchten Wiederholungen. Datei gross (47-s-Fenster = 257 MB) ->
  nur den Dateianfang streamen. Skripte: `f2_walk_trace_probe_make.py`, `inj_wtr_run.ps1`,
  `wtr_analyze.py`, `wtr_dispatch.py`, `wtr_seq.py`, `wtr_filter2.py`, `wtr_window_check.py`.
- **SHARC-Flags/Delay-Slots (CONFIRMED, MAME-Core + Trace):** `BTST Rx BY n` setzt SZ **nur**
  wenn das getestete Bit 0 ist (`SET_FLAG_SZ(x) => if (x==0) astat |= SZ`, nie loeschen) -
  "SZ gesetzt" = "Bit war 0"; `BIT TEST` setzt dagegen BTF/TF auf den Bitwert (`IF NOT TF` =
  positive Abfrage). Verzoegerte Branches `(DB)` haben **ZWEI** Delay-Slots: bei
  `0x2330A IF EQ, CALL (M8,I8) (DB)` laufen 0x2330B+0x2330C vor der Transformroutine
  (Rueckkehr 0x2330D) -> Erklaerung der Log-Reihenfolge "Deskriptor-Trio, dann TRW-Quartett";
  `RTS (DB)` @0x2350A -> 0x2350B/0x2350C sind die Stores +4/+5.
- **Interpreter/Kommando-Mechanismus gilt als abgeschlossen** (Stand 2026-09-16): CONFIRMED
  sind Liste/Flags/Gates/Aufrufzahl/Aufrufpfad/Record-Slot; HYPOTHESIS bleiben f6=63 (15 Bloecke),
  Familie 0x3B97 (3), `p_f1tail`-Interaktion (0 Zyklen; plausibel: alle Kommandos b28=0+b29=0),
  op2-Tripel-Semantik, F1/F1c-Route, idx12-Rolle, `R7 = DM(0x0B,I6)` (STRONG: R7=30),
  Record-Feld +9.

## Voodoo-Texturregister-Trace + Offline-Konstantenscan (2026-09-17, Batch 30)
- `LOG_TEXREGS` in `voodoo.h` (Flag + Block in `register_table_entry::write`): loggt NUR
  textureMode/tLOD/texBaseAddr(_1/_2/_3_8) als `[:voodooX] SSC_TEXREG :voodooX <name> <wert>`,
  Wert **vor** der Registermaske. Rebuild = nur voodoo.cpp+Link (~40 s); Stand: false.
- Registerbreite: `REGISTER_ENTRY(texBaseAddr,…,19,…)` ⇒ Maske **0x7FFFF**; mit
  `m_baseshift 3`/`m_basemask 0xfffff` (Defaults) = **4 MB TMU-RAM** ⇒ Bit 18 (+0x40000)
  = oberstes Adressbit = **+2 MB**. Ungemasktes Log ⇒ Feldbreite direkt ablesbar.
- Debugger-`logerror` kann Speicher lesen: `d@(r4+8)`, `w@(r4+4)` (express.cpp,
  `validate_number_parameter`) ⇒ BP-Actions feldweise loggen.
- `-log` zeigt auch mit geladenem State `Soft reset` + `(reset phase)` (Reset vor State-Load)
  ⇒ State nur per PC-`logerror`+`save` im Scriptkopf pruefen (`scripts/m30_state_probe.txt`).
- PowerShell `>` schreibt **UTF-16LE** ⇒ extrahierte Logs mit Encoding-Erkennung lesen.
- Offline-Konstantenscan: `rom/build/830d01.27p.main.bin` = BE-Abbild ab 0x80000000,
  16-Bit-Immediates in Bytes **[2..3]**; Funktion per `_ppc_inventory.json` (`addr`+`size`).
  Fingerabdruecke: `mulli 0x5556` (Emitter-Geschwister), `lis`/`addic`-Paar = `0x1426xxxx`,
  `li 0x65/0x66`.

## Batch 71: Die dritte Matrixzeile / Transformstruktur (CONFIRMED 2026-09-18)
- **Die Transformausgabe `(a,b,c) -> (+3,+4,+5)` ist eine STARRE Transformation** (orthonormal + Translation), f32-exakt: auf der Record-Gruppe {16..21} des Blocks `0x14032CA` Rest 0.0025 (Fit auf 5) / 0.0054 (out-of-sample), Zeilenlaengen 1+-2.9e-5, |Skalarprodukt| 1.7e-4. ⇒ **Die dritte Zeile ist NICHT frei: `z = x_zeile × y_zeile`** (nur bei vollstaendigen ersten beiden Zeilen bilden!).
- **`+5` IST die SICHTTIEFE (CONFIRMED):** `+7/16 = 256 - 443*(+3)/(+5)`, `+8/16 = 192 - 443*(+4)/(+5)`, 22/22 Records, Rest <= 1/32 = genau die x.4-Quantisierung. Zentren (256,192) = Bildmitte 512x384, **Brennweite 443**.
- **Der Block traegt MEHRERE Matrizen:** nur {16..21} teilt eine; die 4er-Gruppen 0..15 sind **koplanar** ⇒ affiner Fit unterbestimmt (wilde Koeffizienten sind KEIN Gegenbeweis). Eine gemeinsame Zeile scheitert auch mit freien Gruppen-Offsets (Paare 1859.5, Quads 3096.4) ⇒ **Matrix PRO GRUPPE/OBJEKT fuehren**, nicht pro Frame/Block.
- **Es gibt eine gespeicherte Rotationsmatrix** (orthonormale 3x3-f32). **KORRIGIERT in Batch 72:** die Adresse ist DM **0x29C67**, NICHT `0x04719C` (die Batch-71-Artefakte `_m71_ortho_*`/`_m71_stored_matrix`/`_m71_coef_find` haben `0x20000 + 4*index` etikettiert statt `0x20000 + index`; die *Indizes* waren richtig, nur die Adresse um Faktor 4 zu hoch). Die "drei identischen Kopien" sind ein **Dump-Alias** (Periode 0x8000 Worte), KEINE drei Speicherplätze. Sie ist in **allen 48 Orientierungen** widerlegt (Transponierte x Zeilen-/Spaltenpermutation x Vorzeichen; beste Spanne 813.8 gegen 0.0048 der gemessenen Zeile).
- **Transformspiegel 0x22585 (Herleitung):** Dual-Op-Ketten lesen den Stand VOR der Instruktion; `F12` wird in JEDER Instruktion neu belegt und jede `F11`-Kette addiert den *vorigen* Wert. Ergebnis: `+3=F8+F0*F15+F1*F4+F2*F7`, `+4=F9+F0*F5+F1*F7+F2*F7`, `+5=F10+F0*F6+F1*F7+F2*F7`. `F0/F1/F2` sind NICHT die Rohkoordinaten (der Handler schreibt sie in 0x231E-0x2330 selbst fort).
- **Handlereintritte:** `0x222FE` = 16-Bit-Familie (Record-Pool `I0=0x283D4`, Schreibtakt 24 Worte = 2 Records, Guard `R12-1` in `+6`), `0x222E9` = 10-Bit, `0x222E0` = ohne Vertex-Schleife.
- **Port (Batch 71):** `MatrixState` hat `z1/z2/z3` (dritte Zeile) + `x_c`/`y_c`/`xy_rows_complete` (c-Spalte; der historische `f7`-Platzhalter ist Default); `apply()` nutzt die dritte Zeile NUR bei `z_row_valid` (sonst bit-identisch); `complete_z_row` (Kreuzprodukt + Orthonormalitaetsprobe), `measured_anchor_group_matrix()` = gemessene Gruppe {16..21}; `measured_344_matrix()` wird abgelehnt. Anker `vertex_check.cpp` Abschnitt (11), Regression `zrow-anker`.

## Batch 72: Herkunft der Gruppen-/Objektmatrix (MESSUNG 2026-09-18, 2b-II Teil 6)
- **Dump-Adressregel (CONFIRMED, zweimal unabhaengig):** Datei-u32-Index = **`DM-Adresse - 0x20000`** (4 B je DM-Wort), Fenster 0x20000..0x2FFFF (2 Mbit = ADSP-21062). Gegenprobe: Record-Pool 0x283D4 und Chain-Buffer 0x29DF0 liegen genau dort. **Fallstrick: `0x20000 + 4*index` ist FALSCH.**
- **Dump-Alias (CONFIRMED):** ab DM 0x30000 wiederholt der Dump den Block 0x28000 — `0x28000 == 0x30000 == 0x38000` ueber 0x8000 Worte, **0 Abweichungen**. Alle "identischen Kopien" (Record-Pool, Matrix) sind dieser Alias, KEINE Speichervielfalt.
- **I7 ist EINE feste Adresse:** `I7 = 0x28220` wird im ganzen Programm nur in der Boot-Init gesetzt (0x20043/0x2005F). Der Block ist der Transform-/Sichtkontext.
- **Projektionskonstanten im I7-Kontext (WERTE schon Batch 66, `_m66_ctx.txt`; B72 bindet sie an die Projektion):** `DM 0x28232 = 4096.0` (=256*16), `0x28233 = 3072.0` (=192*16), `0x28234 = -7088.0` (=-16*443), `0x28235 = 443.0` (Brennweite), `0x28236/0x28237` = zweite Kopie des Paares. Projektion **22/22** mit GELESENEN Konstanten (max |d| = 0.4873 in x.4 < 0.5).
- **Die Matrixkoeffizienten sind NICHT auffindbar (gemessen, exhaustiv):** 0 Treffer fuer alle 12 gefitteten Koeffizienten der Gruppe {16..21} in BEIDEN DM-Fenstern (Wortgleichheit) **und** 0 Treffer als 32-Bit-Immediat im Programmkode. Auch `443.0` ist im Kode 0x — 443 steht nur als Datum im Kontext. ⇒ Matrix ist **pro Objekt zur Laufzeit gefuehrt**, Quelle offen; der Port fuehrt sie als deklarierten Eingang.
- **Es gibt im Programm KEINEN Float-Laden aus dem Speicher in F4..F10** (`F4 = DM(...)` 0x): Koeffizienten gelangen nur als **Rohworte** (`R7 = DM(k,I7)`) oder als Registerwert in die Rechenkerne.
- **Die Umgebung der gespeicherten 3x3 ist Arbeitsfeld, keine Tabelle:** 12-Wort-Slots ab 0x29BC8 (3 Koordinaten + 2 Link-Zeiger + Record-Zeiger), geschrieben von 0x20E71 ff. (`I3=0x29BE0`, `I2=0x29BD4`, `I1=0x29BC8`); `DM(0x29BCD/0x29BD9/0x29BE5) = Record-Zeiger` (je 180 Referenzen).
- **Port (Batch 72):** `port/include/port/sharc_context.h` + `port/src/sharc_context.cpp` (`read_projection_context`, `project_x4`, `read_stored_rotation_matrix`, `stored_rotation_matrix_is_group_matrix` = Ablehnung, `dm_canonical_address`); Anker `vertex_check.cpp` **Abschnitt (12)**; Regression **`ctx-anker`** (44 Faelle). Bild unveraendert (0/196608 Pixel).
- **PIL-freier Bildvergleich:** `scripts/m72_frame_compare.py` (liest PPM P6 und PNG 8-Bit/Filter 0-4 mit reiner stdlib; `m71_frame_compare.py` scheitert hier an `ModuleNotFoundError: PIL`).

## Batch 73: Die Gruppen-/Objektmatrix ist STROMNUTZLAST (CONFIRMED 2026-09-18, 2b-II Teil 7)
- **Der Dispatcher setzt F4..F10 NICHT** (gemessen): `0x20D4A/0x20D92/0x20DD7/0x20CE1-Familie/0x20DFB` schreiben nur `R7/R12/R13/R14`. Der Register-Restore-Epilog `0x20E01..0x20E18` (liest `R8..R4` aus einem 12-Wort-Record, schreibt Record-Worte 7..11 nach `DM(0x28220..0x28224)`) hat **genau einen** Setzer: `0x20D42` = Vertex-Kommando `0x20CFF`; der Blockdispatch kehrt ueber `0x20DFB` zurueck und stellt nichts. `DM(0x28220..0x28224)` = Spill-/Arbeitsfenster (151 Schreibstellen), KEIN Matrixspeicher.
- **Dispatch-Tabelle `DM(0x28283)` (aus dem Dump gelesen) = Opcode -> Handler-Adresse.** Opcodes `0x0B..0x16` = **Upload-/Transform-Gruppe**: 0x0B=0x201DD (Praefix), 0x0C=0x201E6 (Record schreiben), 0x0D=0x201FB (Restore), 0x0E=0x20211 (Negieren), 0x0F=0x2021C, **0x10=0x20223 (Matrix-Upload)**, 0x11=0x2023F, 0x12=0x20246, 0x13=0x20262, 0x14=0x20269, 0x15=0x202A4, 0x16=0x202DD.
- **Opcode 0x10 (15 Nutzworte) = 3x32-Bit-Translation (HIGH-Wort zuerst) + 9 x s16 Q15.** Skala `2^(DM(0x10,I6))`, Dump: `DM(0x28273) = -15` **2^-15**. Zielregister der Reihe nach `F15, F5, F6, F4` + `c0..c4` (= `DM(0x28220..0x28224)`); der Kern `0x20D0C..0x20D14` bildet die Zeilen `(s0,s3,s6)`, `(s1,s4,s7)`, `(s2,s5,s8)` => **SPALTENWEISE** `M[i][j] = s[3j+i]`. Weitere Kontextwerte: `DM(0x28282) = 512` (Indexgrenze), `DM(0x2827B) = 0x28283` (Tabelle, selbstreferenziell), `I6 = 0x28263`.
- **Anker:** `capture/poc_ref_stream.txt` **@Wort 3936** = `t=(-9438,961,-49175)`, `s=(-24032,-3422,22007|0,32379,5031|-22276,3689,-23750)` = die in Batch 71 GEFITTETE Matrix der Gruppe {16..21} (Block `0x14032CA`) => **Fit ist CONFIRMED** (9 Koeffizienten max |d| 5.77e-06 = Q15-Raster; Translation 9.77e-04, rel. 2.5e-08). Blockauftrag `0x57 Index=1039` folgt **genau 16 Worte** spaeter.
- **Regel:** die zuletzt hochgeladene Matrix gilt fuer den naechsten Blockauftrag. 16 Stroeme: 1532 Uploads, 2809 Blockauftraege, 956 mit Upload genau 16 Worte davor; 4596 Normen in `0.99983..1.00007`, |dot| <= 1.6e-04. Varianten `0x0F/0x11..0x16` kommen 0x vor (gezaehlt).
- **Deskriptortabelle (Teil B, implementiert):** `MR1B = I4 + hi16(W)` (**ohne SE**), `I4' = MR1B + lo16(W)`, Eintrag `= MR1B + idx12*M1` (`idx12 = FEXT K BY 0:12`, `M1 = 1`), `+9 = s16(hi)/16`, `+10 = s16(lo)/16`. Dichtebeleg: 4 Deskriptorwoerter der Records 4..7 auf `0x1419727..0x141972A` (Stride 1) in `ram1400000_at_index7.bin`. **OFFEN:** Zeigerstart `I4` fuer die Port-eigenen Bloecke — Kandidat `DM(0x28209) = 0x2ED6E` (DMA-Kopie-Ziel), aber `0x1419727` ist von dort mit UNSIGNIERTEM 16-Bit-Offset nicht erreichbar. Live-Rezept: `bp 0x2236c::dsp1` + Registerdump.
- **Port (Batch 73):** `port/sharc_matrix_upload.{h,cpp}` (`decode_matrix_upload`, `matrix_upload_to_state` setzt `xy_rows_complete` UND `z_row_valid`, `measured_anchor_matrix_upload`), `port/sharc_program_field.{h,cpp}` (`descriptor_index/table_base/field_next/lookup`), `sharc_consumer`: `MatrixUploadSink` + `StreamMatrixSource` (+ Zensus `matrix_uploads`, `blocks_with_stream_matrix`), Anker `vertex_check.cpp` Abschnitte (13)/(14), GL-Modus **`glmatrix`**: **2997 Dreiecke, W-Kanal 2997** (vorher 20), 216/217 Bloecke mit Strom-Matrix; `glown` unveraendert. Regression 32 Frames + 14 Anker = 46, 0 Fehler.
- **Bild-Vergleich der beiden Matrixquellen:** `scripts/m73_frame_compare.py` (196608/196608 Pixel — beabsichtigt, dokumentiert).

## Tooling-Fallstricke (2026-09-18)
- `py <script>.py` und `py -c "import PIL"` koennen UNTERSCHIEDLICH aufloesen: hier fand `py -c` PIL 10.3.0, `py scripts\x.py` meldete `ModuleNotFoundError: No module named 'PIL'`. Workaround: den Interpreter direkt aufrufen — `& "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe" scripts\x.py`.
- Bildvergleich nach Port-Eingriffen: `scripts/m71_frame_compare.py` (PPM -> PNG, Pixel-Diff gegen die Batch-PNGs).

- Ergebnis Batch 30: Textur-Setup = genau 3 Register, **1:1 verbatim** aus dem
  0x65/0x66-Record; der Emitter `FUN_8001A82C` liefert nur **10,7 %** der Voodoo-Setups.