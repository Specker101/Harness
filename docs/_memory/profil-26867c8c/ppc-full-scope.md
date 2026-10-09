# PPC Full-Scope (Plan: analysis/ppc-full-scope-plan.md, 2026-08-31)

## MAME/Lua harness primitives (CONFIRMED aus lokalem Source)
- `-autoboot_script file.lua`; `emu.pause()/unpause()/step()` (step = EIN Frame, ui.cpp handler_ingame); `emu.register_periodic`.
- `cpu.state["R3"].value = n` SCHREIBBAR: PC/MSR/CR/LR/CTR/XER/R0-R31/F0-F31/SPRG0-3/SRR0/1/EVPR (luaengine 2208-2225, ppccom.cpp 816-856). → Direkter Funktionsaufruf moeglich.
- KEIN debugger-usertype in Lua (kein bp aus Lua); KEINE Lua-Input-Injektion (kein code_press). Debugger-Console: bp/wpset+Actions, fill, load, save, source, do, trace, trackpc, pcatmem.
- LR-Trap 0x80000058 (`b .`) ist als Trap UNBRAUCHBAR (ein DRC-Block, Restore nie uebernommen) — finaler Trap = illegale Instruktion in Scratch-RAM, s.u.
- emu.keypost existiert (natkeyboard), Mapping key→Input HYPOTHESIS; Fallback = Inject der gecachten Input-Globals.

## Harness-Validierung (CONFIRMED 2026-08-31, scripts/ppc_trap_harness.lua, 6/6 PASS)
- MAME 0.289. Aufruf-Primitive: Lua-Coroutine resumed in MACHINE_NOTIFY_FRAME (=Frame-Grenze) → `cpu.state["R3"].value = n` live; wird von naechster Timeslice uebernommen.
- DRC (ppcdrc.cpp): Blocks LADEN m_core->* am Block-Entry, SPEICHERN am Exit → Register-Writes wirken nur bei Block-Wechsel.
- Trap-Design (3 Iterationen): (1) `b .`-Self-Loop = ein Block → Restore NIE uebernommen (Game bleibt haengen). (2) `bctr` funktioniert nur bei CTR-erhaltenden Funktionen (memset clobbert CTR via mtctr). (3) FINAL: **Illegale Instruktion 0x00000000** als Trap → Program-Exception → Exception-Dispatch LIEST m_core->* neu → Escape = alle Register (inkl. SRR0/1) restoren. Kein Register-Dependency. 
- KEIN emu.pause() noetig; alles an Frame-Grenzen. Pro Call ~1 Frame. MSR.EE=0 (bit15) blockt IRQs (ppcdrc checkt MSR32 & MSR_EE).
- 4xx: logisch 0x8xxxxxxx → physikalisch 0x0xxxxxxx (address &= 0x7fffffff). Lua mem: PHYSIKALISCHE Adressen; CPU-Regs: LOGISCHE. Scratch = (R1&~0xF)-0x200/-0x500 (unter SP, snapshot+restore).
- PITFALL: `-seconds_to_run N` + quick.sta (emutime~163s) → Exit fast sofort (kein Freeze! exitcode 0, still). Harness exits selbst via `manager.machine:exit()`.
- Test-Funktionen identifiziert: 0x8000d1c4=strlen, 0x8000d140=word-memset (mtctr/bdnz!), 0x8000d15c=byte-memset, 0x8000d17c=memcpy, 0x8000d1ec=strncpy (Libc-Cluster 0x8000d100-300). K056800-Host-Write-Site gefunden: FUN_8000e690 → 0x7d030006.
- Einschraenkungen: blr-Return noetig; bctr-Tailcalls → statischen Nachfolger als LR; >8 Args = Stack-Args ab SP+0x38 (s. Validierung II); SRR0-Klassifikation nach Flush konsistent.

## Harness-Validierung II (CONFIRMED 2026-08-31, 16/16 PASS)
- Stack-Args: arg9 @ Entry-SP+**0x38** (Compiler-Konvention, NICHT SP+8!), arg10 @ +0x3C. Reale 9-Arg-Fn FUN_8003c30c (Tail-Call auf FUN_8003c354, schreibt Object-Record [r2+0x234]+idx*0x180) 8/8 Felder korrekt. Synthetische 10-Arg-Summe 1110 ✓.
- IRQ-Fehlerart charakterisiert: K056800-Poll (FUN_8000e6bc, busy-pollt 0x7D030000, Timeout 0x7d000) laeuft sauber mit EE=0 (Sound-CPU unabhaengig). Synthetischer IRQ-Wait-Spin: sauberer 60-Frame-Timeout (KEIN Freeze) → Unblock per Flag-Write (Memory-Writes live auch bei drehendem Block) → Trap → Exception → Escape → Spiel gesund. Harness 2 nur noetig, wenn Wartebedingung unbekannt.
- FUNDAMENTAL: DRC-Codecache NICHT kohaerent mit Speicher-Writes (Self-Modifying Code laeuft stale ohne icbi). Mapped-Register (Fastmap, v.a. r2) veralten gegenueber m_core-Writes → Lua-Restore reicht nicht. MITIGATION (im Harness drin): automatischer icbi-Flush-Call VOR jeder Injektion (code_flush_cache → drcuml reset → Fastmap + Cache leer), 1 Frame Kosten. SRR0 danach konsistent (Trap-Adresse statt Stale 0xFFF80704).
- LESSON: synthetische PPC-Opcodes NIE von Hand — Encoding-Fallen: or rD/rS-Vertauschung, Basisreg 0x63/0x62, **bc: BD in Bits16-29, AA=Bit30, LK=Bit31** (falsch = beql +4095 → Sprung aus RAM → Exception). Immer Python-Assembler + unidasm (MAME-Referenz, `unidasm file -arch powerpc -basepc 0x...`).

## Harness-Hardening (CONFIRMED 2026-08-31, 19/19 PASS)
- Strukturell erzwungen: (1) icbi-Flush UNKONDITIONAL vor jedem Call in
  ppc_trap_core.lua; (2) ppc_synth_blocks.py assembliert + verifiziert
  JEDEN Block per unidasm-Subprocess (zeilengenau) → Manifest
  capture/ppc_synth_manifest.lua; Lua-Core hat KEINE Raw-Byte-API
  (case.code → UNVERIFIED-CODE-REJECTED, Selbsttest drin); (3)
  Default-Timeout 60 Frames/Call, laut, unblock→escape→emergency→
  HARDFAIL-Abbruch. Pipeline: scripts/ppc_harness_run.ps1 (Manifest-Regen
  = Schritt 1, Exit-Code aus ppc_harness_result.txt). Doku:
  analysis/ppc-trap-harness-hardening.md. ppc_asm.py: Labels statt
  Hand-BD; unidasm-Formate empirisch (icbi-Quirk "icbi 0,r0" ohne
  r-Prefix; Imms UPPER, Targets lower hex). Verifier fing beim Erstlauf
  2 echte Bugs (X-form or-Feldordnung, BD-Mathe).
- NEUER CONFIRMED-Fund: Trap-Wort VOR dem Flush schreiben (Spiel-IRQs
  clobbern Trap-Zelle SP-0x500 zwischen Cases; flush-first ⇒ Stale-Exec,
  R1 kaputt, args9-Fail srr0=0).
- SIDE-EFFECT-BARRIERE (CONFIRMED 2026-09-15, Muster, kein Workaround):
  Fn mit Geraete-Schreibzugriff (mmio 0x780C0000/3 CG-Kommando, shr16
  0x78000000 Shared-RAM, host_w 0x7D03xxxx Sound) ist per Trap-Call
  HOECHSTENS EINMAL rufbar; 2. Aufruf = HARDFAIL. Faelle: FUN_8002d644
  (E), FUN_8000c608 + FUN_8000c2b4 (C). VOR Aufnahme pruefen (Inventory
  mmio_refs!). Doku: analysis/ppc-trap-harness-hardening.md §8.
- MAME-WATCHPOINTS (CONFIRMED 2026-09-15): Action-Form
  `wpd <addr>::dsp1,<len>,<type>,<cond>,{ logerror "TAG %08X %08X\n",wpaddr,wpdata ; g }`
  → Adresse+Wert ALLER Zugriffe in capture/error.log (-log). printf in der
  Action bleibt headless unsichtbar. temp-gated `saved`-Snapshots sind
  verworfen (halten die Emulation an → PPC/SHARC-Timeslice-Scheduling
  verzerrt: 10 statt 2,86 Mio. Treffer im selben Fenster).
- GHIDRA-PROGRAMMWAHL (2026-09-15): ROM-Adressen 0x8000xxxx funktionierten
  mit program="830d01.27p.main.bin"; "830d01.27p.be.bin" → Function not
  found. Vor Nutzung kurz verifizieren.
- BATCH 20 (2026-09-16, CONFIRMED): (a) SCRATCH/FRAME-KOLLISION — Scratch
  (R1-0x200) und Trap (R1-0x500) werden von jedem Callee mit Frame >= 0x200
  ueberschrieben (FUN_80049afc ~0x240 wird von beiden Szenengraph-Fn gerufen,
  auch bei Sofort-Return! FUN_8002b000 hat einen 4-KiB-Stackring). Rezept:
  case.regs setzt R1 := R1-0x600, Region [R1-0x1800,R1-0x600) in prepare
  sichern, in cleanup zurueckschreiben (beide Suites damit 0 Fehler).
  (b) MODELLE in Lua: `>>` ist LOGISCH (Negative werden riesig positiv) →
  `v // 2^n` benutzen (arithmetischer Shift); war Ursache von 27 FAILs.
  (c) Pruefdisziplin: erst Pruefregel anzweifeln, dann Modell; bei
  Ghidra-Term-Modellen mit wiederverwendeten Variablen (uVar17, undefined6)
  auf modellfreie Invarianten umstellen (gemessene ROM-Referenzmatrizen +
  exakte Vorzeichen-Permutationsprodukte bei 90°-Vielfachen).
  (d) Suites: scripts/ppc_trap_suite_archcore.lua (78 Cases, 78/78 PASS:
  Q14-Mathe-Bibliothek), scripts/ppc_trap_suite_scenegraph.lua (15 Cases,
  15/15 PASS: Kind = Eltern (x) lokal, Winkel-Roundtrip); Offline-Modell
  scripts/archcore_model.py (0 Ghidra/0 MAME).
  (e) MESSFAKTEN: FUN_80020f7c = floor(sqrt(rohes Argument)), KEINE Q14-Wurzel;
  FUN_8001b7b8 = sat(x>>15,+-0x4000), FUN_8001b7d8 = sat(x>>14) (keine
  Rundung); FUN_800210c8 = (a*b+c*d)>>14; sin-Tabelle Q14 (45° = 0x2D41);
  atan2-Vollkreis 0x10000; FUN_8001d800/1d880 wenden die Matrix SPALTENWEISE
  an (out_i = sum_j m[j][i]*v_j); 8001e62c = Linksprodukt; Live: 8004992c
  0x0 Aufrufe, 80049c48 10 850 (Elternzeiger ueberall 0), 8001e62c 206 167
  aus FUN_80049afc; Knoten-Matrixpool ab 0x803A0000, Stride 0x64, Matrix +0x1C.
  Doku: analysis/batch20-arch-core-verification-2026-09-16.md.


## Inventar
- 1611 Funktionen (Ghidra live); _listfunc_raw.json 1610 Adressen. Regionen: 8000:169, 8001:247, 8002:210, 8003:186, 8004:250, 8005:207, 8006:119, 8007:149, 8008:73.
- TIER-0 INVENTAR (CONFIRMED 2026-08-31): scripts/PpcInventory.java →
  analysis/_ppc_inventory.json (caller/callee/mmio/sda2/global_writes/
  ptr_refs_from); classify → _ppc_inventory_classified.json + Report
  (Bucket A=76 B=58 C=22 D=20 E=4 F=1305 G=126, total 1611).
  Run-Rezept: scripts/ppc_inventory_headless.cmd (analyzeHeadless -process
  OHNE führenden Slash; Java-API: KEIN RefType.isReadWrite, KEIN
  Reference.getRegister — opObjects liefert Register+Scalar; Scalar ist
  sign-extended; PITFALL: Select-Object -First killt die Upstream-Pipe →
  immer -Last; relative Pfade verboten).
- BEFUND: nur 3 r2-Store-Instruktionen im ganzen Programm (SDA2 fast nur
  Read; Writes via Pointer) — global_writes-Detektion daher limitiert.
- DRC-COVERAGE-HOOK (CONFIRMED): SSC_COVERAGE env + ppcdrc.cpp-Markierung
  in code_compile_block (Block wird genau bei Erreichen kompiliert,
  Blocks linear → komplette Instruktions-Coverage); Dump in hornet_state::
  device_stop (machine_stop existiert NICHT in driver_device!). Header
  native struct = 16B (magic6+pad2+base+size LE). Ergebnis:
  **915/1611 observed, 696 unobserved** (Boot+Attract+Gameplay-Replay).
- RAM-EXTENTS (CONFIRMED via Debugger-memdump, scripts/ppc_memdump.dbg →
  capture/ppc_memdump.log, analysis/_ppc_ram_map.md): EINZIGES writable
  RAM = 4MiB workram phys 0-0x3FFFFF / logisch 0x80000000-0x803FFFFF;
  0x7e/0x7f = ROM. sysreg READ 0x7d000000, WRITE 0x7d010000
  (asymmetrisch!). RTC 0x7d020000.
- TIER-1 VERTIKALSLICE (CONFIRMED 24/24, ppc_tier1_run.ps1 +
  ppc_trap_suite_tier1.lua, Doku ppc-tier1-vertical-slice.md):
  G=FUN_80020c80 = signed Sine 16-bit Winkel, Amplitude 0x4000,
  Table [[r2+0x108]]+0x2104 (42 Caller); D=FUN_8000c6b4 CG-Notify
  (mfdcr/mtdcr save-restore, Schatten [r2+0x20]+0xB=(alt&0xCF)|(p2<<4),
  Mailbox **[r2+4], Flag [r2+8]+8); E=FUN_8000e690 stb 0/1@0x7D030006
  (host_w(6)=Mute, WRITE-ONLY im Modell → Verifikation via
  TEMP-SSC-K056800-Hook describe_context, Wrapper greppt Pflicht).
  Runner-Refactor: ppc_trap_suite.lua (Harness-Suite 19/19 re-verifiziert).
  LESSON: Readback-Annahmen erst gegen MAME-Modell pruefen.
- G-BATCH (CONFIRMED 22/22, ppc_trap_suite_gbatch.lua + generischer
  Wrapper ppc_suite_run.ps1 -Suite <name>):
  FUN_80015294=LCG state'=state*0x41C64E6D+0x3039, ret=(state'>>16)&0x7FFF,
  Zelle **[r2+0xA8]; FUN_8003aecc=List-Walker next@+0x60 → n-ter
  Nachfolger oder 0 (n<1→head, head=0→0); FUN_800109fc=Record-Feld-
  Setter, idx=*base SIGNIERT (lbz+extsb), Ziel base+idx*0xC+8, stb,
  Base [r2+0x54]=0x800AF4E8; FUN_8003c750=Gate+Ringpuffer-Call
  FUN_8000eb88(param<<16) gdw bitB==0 (Byte[[r2+0x240]+8]&0xF Bit1),
  +0x20 gdw param>>8==1&&bitA==0 (Byte[[r2+0x14]+0x48]>>0x14 Bit3),
  Ring [[r2+0x24]] Entry +0x14+idx*4, idx+1&0x3F@+0x115.
  FUN_8000005c=Indirekt-Thunk ueber r11 → NICHT harness-rufbar.
  LESSON: Suite-Erwartungen = Testcode — 3 Erstlauf-Fails waren
  Index-Bugs im Lua-Skript, Funktionen waren korrekt.
- BUCKET-D INPUT (CONFIRMED 12/12, ppc_trap_suite_dinput.lua, Doku
  ppc-tier1-vertical-slice.md §7):
  FUN_8003e840=Cursor-Integrator: Gate=signiertes Byte [input+0x16] (0→
  Return), Word=lhz [[r2+0xb0]]+0x18, Zellen [state+0x6FC]=X/[state+0x6FE]=Y
  (s16). CR-Kette: rlwinm r3,r0,28,0xF=rotl28=rotr4 → r3=Word-Bits 4-7
  (NIBBLE 1, NICHT High-Nibble!); mtcrf 0x01,r3→CR7=Nibble1; mcrf→CR0;
  mtcrf 0x01,r0→CR7=Nibble0. ALLE 4 Branches BO=0x04 = branch-if-bit==0
  (KEIN CTR-Pfad — CTR-Hypothese widerlegt!): bit4→Y+=0x50, bit3→Y-=0x50,
  bit6→X+=0x50, bit5→(bclr frueher Return bei 0 sonst) X-=0x50; addic -0x50
  = Subtraktion. FUN_80008bc8=DIP-Decoder dsw@0x7D000004→Input-Struct.
  FUN_8000ce14=Gun-Setter: idx0 exakt (X=s16(in+0x1E)+c0*0x10); idx!=0:
  CG-Regs 0x74000020/22 = K056800-HW-Regs, Zellen = BYTESWAPPED Readbacks
  (X=0x4DFD=swap(-0x2B3), Y=0x90FE=swap(-0x170)), r3=-0x170 CONFIRMED.
- HARNESS-LESSONS Bucket-D (strukturell): (1) Input-Wort-Zelle wird vom
  Spiel ASYNCHRON aktualisiert → Caller-BLOCK injiziert Wort/Gate selbst
  (R8/R10, lwz+sth/stb direkt vor bl) = deterministisch. (2) Post-Trap-
  Zell-Observation ist handler-kontaminiert (Exception-Handler schreibt
  Cursor-Zellen im Trap-Spin weiter, Byte-Swaps) → Caller kopiert Zellen
  nach Rueckkehr in Scratch (Snapshot handler-frei). (3) Assembler-Fallen
  (unidasm fing alle): mtspr/mfspr SPR-Feld = 5-Bit-Haelften GETAUSCHT
  (compute_spr); b/bl LI = 24-bit signed; b/bl-Encoder hatte <<2-Bug.
  (4) Core code_restore 0x20→0x3F (Caller bis 15 Insns); Validierung
  19/19 re-verifiziert. cur_caller-Block @0x803E1000 (abs, 60B).
- BUCKET-E SOUND (CONFIRMED 4/4 + Log-Grep, ppc_trap_suite_ebatch.lua +
  ppc_ebatch_run.ps1, Doku §8): FUN_8002d798=Sound-Kommando-Sender:
  host_w(1/2/3)=param>>16/8/0, **[[r2+0x1F4]]=host_r(0)-Readback,
  host_w(0)=param>>24, host_w(7)=0x10 (Kick); r3=0x10 nach Return
  (Compiler recycelt r3 fuer Kick-stb). FUN_8002d644=Kommando-Queue
  NICHT harness-rufbar (FUN_800115bc=Bytecode-Interpreter mit
  Format-String-Dispatch ueber FUN_8000005c=r11-Thunk, ungebundene
  Seiteneffekte). MAME-Hook k056800 host_w jetzt fuer ALLE Offsets
  (vorher nur case 6), Tier1 24/24 re-verifiziert.
- E-LESSON: host_r(0/1)=m_snd_to_host_regs sind LIVE (Sound-CPU laeuft
  im Flush-Fenster weiter) — Snapshot-Vergleiche der Readback-Zelle
  schlagen fehl; MMIO-Write-Verifikation nur mit PC-Attribution +
  kollisionsfreien Parametern (0xDEADBEEF).
- MMIO-Anker: SHARC 0x78000000/0x780C0000, Sysreg 0x7D010000, CG 0x74000000 (sites s. decompressed-ppc-analysis.md §5). K056800-Host 0x7D030000 (PPC-Site noch NICHT gefunden → lis r3,0x7d03 suchen). EEPROM 0x7D040004 (lan_eeprom 93C46), X76F041.
- Runtime: r2=0x800ADA5C, frame-struct 0x800AE310, state-struct 0x800B3C28.
- RENDERING-PHASE-D FERTIG (2026-08-31): analysis/ppc-command-stream-interface.md
  = Interface-Spezifikation (Projektziel-Deliverable): physisches Protokoll
  (0x78000000, 64KB, 16-Bit, Terminator 0, Cursor [frame+0x18], 2×/Frame),
  Opcode-Vokabular-Tabelle, Produzenten-Kette, Render-Liste = semantische
  Eingabe {word0, word1, len(Bytes), blockptr}, SHARC-Konsumenten-Vertrag,
  Optionen A=Stream-Konsum (empfohlen, PoC 8/8 Frames existiert) /
  B=Record-Konsum / C=Renderer (abgelehnt). Offen: Bank-Parität-Detail,
  2×0x3A-Semantik, bank==1-Zweig FUN_800180b4.
- REKALIBRIERUNG 2026-08-31 (analysis/effort-recalibration-2026-08-31.md):
  Ist-Kosten/Funktion: G-Klasse ~0.5-0.75h, E-Klasse ~0.75-1h, D-Klasse
  2-3h erstmalig (~40-50% Einmal-Infra, marginal jetzt 1-1.5h).
  D war halb Pech (3 konfundierte Hypothesen), halb strukturell:
  (1) BO/BI-Encoding (unidasm-Mnemonics luegen bei BO=0x04 - Rohfelder
  dekodieren!), (2) Live-State-Races (async Input-Zellen), (3) Handler-
  Kontamination, (4) Byte-Swap-Zellen (CG/K056800-Readbacks).
  ~70-80% Rest = einfach, ~5-10% tragen Faktor 1-4.
  Voller Tier-0-Rollout ~550-900h (4-6 Monate) - Grobschaetzung war
  Faktor 20-40 daneben. Gezielt (C+D-Rest+Top-30 G) ~80-120h.
  EMPFEHLUNG: kein voller Rollout; Nahziel = Stream-Konsument-Prototyp
  (Option A), dann bedarfsgetrieben batchen (C zuerst - Shared-RAM lesbar).
  E-Bucket FERTIG (4/4), D 4/20, G ~6/126.
- STREAM-KONSUMENT-NAHZIEL (analysis/stream-consumer-proto-plan.md):
  Anforderungen definiert; Bucket-C-Bedarf GESCHLOSSEN; B1 = FALL A
  CONFIRMED (offline, 2026-08-31): Pointer-Tabelle 0x01400000 statisch
  (Boot-Befuellung), Eintraege = interne SRAM-Slots (0x29E0F+0x14n,
  20-Wort-Bloecke), keine SHARC-Stores/DMA-Writes auf die Region,
  Dumps LE (MAME-saved = LE!), Slot7 = Dreieck-1-Block (0x37C0).
  GO: schlanker Konsument = Stream je Frame + einmaliger SRAM-Dump +
  statische Tabelle.
- SCHRITT 4 FERTIG (2026-08-31, poc/stream_consumer/main.cpp, g++/kein
  MAME): Walk der 7556 Worte, Frame 1 = Worte 0-0x24E, 28/28 Dreiecke,
  Slots 3x0x37C0 + 25x0x37DA (zweiter Emitter = Schritt 5). SMOKE 19/19:
  Vertex-Register BYTEGENAU vs MAME-Log, fstart/fd DERIVED (Toleranz,
  PoC-Konvention). Lektionen: (1) Wortverbrauch = SHARC-Handler-Disasm,
  NICHT PPC-Emissionszaehlung (0x01=7+Dispatch, 0x04=4+Dispatch,
  0x18=6+Dispatch auf 7., 0x00=Handshake-KEIN-Stop). (2) 0x18-Handler =
  0x20329, NICHT 0x2018A (das ist 0x08). (3) 0x0B/0x0C/0x0D = Redirects
  (0 Daten, Wort = naechster Dispatch). (4) Frame-Ende = erstes Wort
  ausserhalb der 256er-Dispatch-Tabelle (0x0208@0x24F); Capture =
  Fenster-Snapshot mit Folge-Frames (naechster 0x0002@658). (5)
  Dispatch-Tabelle = Capture-Zeit-File + aktueller SRAM-Dump identisch
  fuer gepruefte Eintraege. Details: analysis/stream-consumer-proto-plan.md
  §5. Naechster Schritt = Schritt 5 (Transform+Emit generalisieren:
  Matrix aus 0x03-Handler-DM(I7)-Writes, S/T/W/Alpha-Quellen, Vertex-
  Auswahl, 0x37DA-Emitter; offen: 0x3D/4E/4F/5F/68-Semantik, fog).
- BATCH B (2026-08-31) — BOUNDARY ERREICHT, bewusst gestoppt:
  B1: Opcodes 0x08=2, 0x68=variabel 2+2*w2 (DO-Loop), 0x10=15,
  0x5D=Objekt-Opcode (Index->Slot-Emitter) — in scripts/stream_inventory.py
  + C++-Walker portiert, Regression 19/19 OK. 8-Frame-Walks reichen bis
  Wort ~1236 (Blocker: 0x66/0x1D = Objekt-Emitter-Semantik).
  B2: Ground-Truth extrahiert (scripts/sharc_burst_extract.py ->
  analysis/_frame2942_bursts.json; Frame #2942 = Bursts 1-28, Linien
  1220139-1220829 im 2,24-GB-Log error-gameplay-20260828-021306.log).
  BEFUND: 0x37DA-Emitter = Vertex-Batch-Loop + verknuepfte
  Vertex-Deskriptoren + CALL 0x220D1 Sub-Emitter + Kontext — KEINE kleine
  Portierung -> Renderer-Phasen-Arbeit. 28/28-Go-1 und 8-Frame-Vollstand
  = Renderer-Phase; Go-2-Logs = MAME-Lauf (Ruecksprache noetig).
  Werkzeuge: scripts/sharc_consume_extract.py (Handler-Read-Zaehler,
  Loops/M2 manuell), scripts/stream_inventory.py (Frame-Walk-Inventar).
- BEWEIS-PHASE ABGESCHLOSSEN (2026-08-31):
  analysis/nahziel-proof-closure.md = Deliverable (Kette CONFIRMED,
  Grenzen: Go-1 formal 3/28, fstart/fd DERIVED, Frame->Burst-Zuordnung =
  HYPOTHESIS). analysis/renderer-phase-proposal.md = PROPOSAL (erstes
  Ziel 28/28 Frame #2942 via 0x37DA-Pipeline, R1-R3 geschaetzt 2-5
  Sessions, offline validierbar) — Start NUR nach bewusster Freigabe.
  Go-2-Logs weiterhin MAME-Lauf -> Ruecksprache. Ground-Truth:
  analysis/_frame2942_bursts.json (48 Bursts, Liniennummern).
- LOG-FRAGE GELOEST (2026-08-31, offline, KEIN MAME noetig):
  Gameplay-Log capture/error-gameplay-20260828-021306.log (2139 MB) =
  BEIDES: 5.218.218 cgboard_dsp_shared_w_ppc-Zeilen (PPC-Stream, Pattern
  wie scripts/sharc_triangle1_extract.py v2) + 1.164.759
  VOODOO.REG-Dreieck-Bursts, erste ab Zeile 1220139 (= Frame #2942).
  Die 8 scope_session04-Frames haben KEINE Voodoo-Ground-Truth
  (error_poc_f*.log/error_poc_prev*.log = nur SHARC-RAM-Zeilen) -> nur
  fuer DIESE waere MAME-Neulauf noetig. Empfehlung: Go-2-Frameset =
  8 Frames aus dem Gameplay-Log (R2: Segmentierung via 0x0002-Marker-
  Writes + Burst-Extraktion je Frame).
- RENDERER-PHASE LAEUFT (Freigabe 2026-08-31, Option 1):
  R2 FERTIG (scripts/f2942_segment.py -> analysis/_f2942_segment.json +
  _f2942_gt28.json + _f2942_rawtrace.txt): Pro Frame 28 IDX-Reads
  (0x20DD7) + 181 Bursts = ~181 Objekte (28 via 0x56 + ~153 andere
  Opcodes), jedes Objekt = 1 Burst. Marker-Reads (PC 0x200A0, off 0) =
  Poll-Loop, KEINE Frame-Grenzen (~5180 Zeilen/Frame). Burst#1 @1220140
  = Objekt#24 (0x56@0x225, idx7, 0x37C0, 344.0, PoC-verifiziert).
  R1a (analysis/renderer-phase-r1a-emittermap.md): Emitter-Map =
  0x37DA-Loop -> Cache 0x283D7, Deskriptor-Walk (MRF/MRB,
  {18:9,12:6,0:12}) -> CALL 0x220D1 (Dreieck-Setup: RECIPS/FIX, Y-Sort,
  Rasterizer-Block 0x29DF0), Burst-Writer 0x24A28 (I3=0x2480022,
  fstartA=0x437F0000, Matrix-Transform + Clip + FIX->FLOAT + S/T).
  WICHTIG: Objekt-Emit = {Setup-Flush: fbzMode=0x3F, zaColor=0x40,
  color1=0x38, fogColor=0x37, fogMode=0x3B, alphaMode=0x3E,
  fbzColorPath=0x3A + Clip/Textur} + {19-Reg-Burst} — Setup-Werte =
  bytegenau im Walker-State (CONFIRMED via Roh-Trace).
- FRAME-TAIL-FUND (2026-09-01, CONFIRMED): Nach Wort 0x249 (Handshake)
  enden die SHARC-Reads — keine weiteren Stream-Reads; die restlichen
  Bursts kommen aus dem gecachten Objektbestand. Frame #2942 = KALTSTART
  (nur 7 der 28 Objekte emittieren: idx {7,15} = 344-Gruppe = Log-Bursts
  #1-7); steady-state = 181 Bursts = 28 Stream-Objekte + 153 gecachte
  aus dem Comm-Ingest. Go-1-Vertrag = NUR die 28 Stream-0x56-Objekte
  (wie definiert). SRAM-Kontext: 0x437F0000 (255.0) @0x8270/0x10270/
  0x18270; Objekt-Records (Stride 0xC) @0x97D3+ mit {i1,i2,x,y,z=176.0}.
  R1b: scripts/r1b_proto.py Stufe 1 (Voll-Walk = stoppt korrekt @0x24E);
  naechstes: Burst-Timing je Objekt (warum idx15 emittiert, 33-37 nicht),
  dann Prototyp-Mathematik vs warmen Frame.
- WARMER FRAME (2026-09-01, CONFIRMED): Erst KOMPLETTER Stream-Walk
  (28 IDX-Reads), DANN Burst-Flush (181 = Render-Liste = 153 gecachte
  + 28 Stream-Objekte). Stream-Bursts = per Vertex-Wert in der
  Flush-Phase identifizierbar. FEHLENDER BAUSTEIN = 0x18-DELTA-SEMANTIK
  (Handler 0x20329 schreibt DM(-0x0F/-0x0E/-0x0B,I7) = Objekt-Positionen
  im I7-Kontext; Konsument ignoriert Deltas bisher -> nur Kaltstart-
  Objekt 22 korrekt). R1b = Delta-Modell + Emit-Math + R3-Zuordnung
  per Vertex-Wert.
- R1B MODELL BESTAETIGT (2026-09-01, scripts/r1b_emit.py PASS):
  0x18-Payload = 3x s32-Paare {dx,dy,dz} (erstes Wort=HIGH): dx =
  500er-Gitter {-3000..3000}, dy {0,625}, dz 5000er {-25000..20000} =
  Objekt-Gitterpositionen. Kumulativ; 0x18 nutzt EIGENEN Objekt-Raum-
  Matrix-Satz (kleine Skalen), Emitter laedt Bildschirm-Matrix separat
  (PoC-Loesung). Kaltstart: 3 idx-7-Emits = exakt 344-Referenz
  (vx 43AC/43FC/43FC, vy 4357/4357/438AC800). Bei Objekt 22: Σdx≈-299
  (kumulativ ≈ Zentrum) -> erklaert den 19/19-Pass strukturell.
  Offen: warme-Frame-Skalen + idx-15/33-37-Emitter.
- WARM-MATRIX-BEFUND (2026-09-01): Warm-Stream (analysis/_warm_stream.txt,
  Bank-Snapshot @1224142 via f2942_segment.py SNAP_LINE) = identisch zum
  Kaltstart AUSSER 3. 0x03-Viewport: warm {01A8,00F4,0054,0040,F85A,F85D}
  vs kalt {0100,00C0,0100,00C0,E90C,E917}. 0x03-Handler (0x2012A,
  analysis/_h03.txt) = Viewport→Matrix: F6=w3/|w5|, F7=w4/|w6| (Newton),
  SCALB/LOGB, I7-Block, Clip-Regs 0x2400046/47. Warm-Flush
  (analysis/_warm_bursts.json, 180): 21 grosse Dreiecke (Span 160) =
  Stream-Objekte, y = Billboard-Zeilen 184..300. NAECHSTES: Warm-Matrix
  loesen + Viewport→Matrix-Formel (2 Datenpunkte).
- KOMPLETTBILD (2026-09-01): Stream = STATISCH (Kalt/Warm-Diff = 0);
  Animation = COMM-KANAL: cgboard_dsp_comm_w_ppc (PC 0x8001B728),
  2 u32/Frame ({0x3403,0x3003}->{0x3503,0x3103} = Zaehler),
  ingestiert vom 0x00-Handshake (0x200AA). Konsument braucht Stream +
  Slots + Comm-Werte/Frame (aus dem Log). idx-15-Mesh = ueberlappend
  {dx@hi,dy@lo,z@hi_{n+1}*2^-F13}; 6 Vertices; Loop-Count + F13 offen,
  Brute-Force gegen 344 schlug fehl. OFFEN R1b-Rest: Mesh-Emit-Semantik
  + F13 + Comm→Matrix-Pfad; dann R3 (28/28) + Go-2.
- MESH-ANALYSE TIEFER (2026-09-01, scripts/r1b_mesh.py + r1b_mesh2.py):
  Affine Loesung: Sxx=160/1875, Syy=62.4375/2500, Perm (1,0,3) —
  aber reine Diagonalform unmoeglich (zwei 215.125-Ziele brauchen
  gleiches dy, Mesh hat {-1875,-1250}). SHARC-Form mit F4/F6-Shear +
  F13-Grid (0-23) = KEINE exakte Loesung. Iterations-Spur: It.1 =
  {w2.hi,w2.lo,w3.hi}; It.2 = {w3.lo,w4.hi,w4.lo} (237EE-237F3) —
  Word-Verzehr 1.5/Vertex exakt zu verifizieren. Naechster Schritt:
  0x37DA-Loop (237E1-237FE) Instruktion-fuer-Instruktion durchspielen.
- VERTEX-CACHE = WELTKOORDINATEN (2026-09-01, CONFIRMED): Cache @SRAM
  0x83D7, 12-Wort-Eintraege {x,y,z,w,i1,i2,...} mit w = 16/z
  (0.000321 = 16/49878.69) = perspektivische Division. Pipeline
  komplett: Mesh (Slots) -> Welt-Cache (0x83D7) -> Projektion
  (0x03-Matrix + w) -> FIX (0x220D1) -> Burst (0x24A28). Offene
  numerische Schritte: (1) Projektions-Form sx = F8 + (x/z)*F7 + ...,
  Fokal ~7512 (160/Δ(x/z)); (2) Cache-Objekt-Zuordnung (12-Wort-
  Stride); (3) FIX-Skala R4 = (R15-1)*4, R15-Quelle; (4) Comm→Matrix
  (0x200AA-Ingest). R3/Go-2 = blockiert auf (1)-(4).
- RENDERER-PHASE LAEUFT (Freigabe 2026-08-31, Option 1):
  R2 FERTIG (scripts/f2942_segment.py -> analysis/_f2942_segment.json +
  _f2942_gt28.json): Pro Frame 28 IDX-Reads (0x20DD7) + 181 Bursts =
  ~181 Objekte (28 via 0x56 + ~153 andere Opcodes), jedes Objekt = 1
  Burst. Marker-Reads (PC 0x200A0, off 0) = Poll-Loop, KEINE
  Frame-Grenzen (~5180 Zeilen/Frame). Burst#1 @1220140 = Objekt#24
  (0x56@0x225, idx7, 0x37C0, 344.0, PoC-verifiziert). 0x56-IDX-Folge
  stimmt exakt mit dem Stream-File. R1a: 0x220D1 = Dreieck-Setup
  (RECIPS/FIX-Kanten, Y-Sort, Params -> 0x29DF0), Disasm
  analysis/_subemit220d1.txt. Offen: 0x37DA-Deskriptor-Loop-Port +
  28/28-Abgleich (Alignment: 0x56-Bursts = Teilmenge der 181).
- EMULATOR-PFAD GESTOPPT + MOTHBALLED (2026-09-01, bewusste
  Entscheidung nach Scope-Review): scripts/sharc_emu.py + walk_driver.py
  → mothballed/ (FROZEN, README dort). Alle Emulator-basierten
  Aussagen = HYPOTHESIS/nicht verifiziert (der Walk lief gegen den
  UNGEPAARTEN Stream-File-Frame #2942; die Dumps = ein warmes
  Capture-Frame mit Viewports FEB4/FE45/FE45 + idx 2112 — gepaart
  nur mit shared_at_index7.bin, nicht mit dem Stream-File).
  BLEIBT als Disasm/Dump-Analyse (ohne Emulator-Nachweis):
  0x03-Handler-Struktur (cx/cy·16, 16·w4/w5, hx/|w4|, Quadrate+1),
  Adressen I7=0x28220, I6=0x28263, Dispatch 0x28283, Hauptschleife
  0x20098 (I4=0x400000), 0x37DA-Mesh = Gleit-Tripel (1.5 Worte/
  Vertex), idx-15 = Rechteck (±1875,±1250,z=0), 0x01-Handler-Format.
  Fortsetzung = SEMANTISCHER PFAD (per-Objekt-Solves wie r1b_emit.py),
  neu bewertet: analysis/renderer-phase-reassessment-2026-09-01.md.
- Schaetzung: Tier0 2-3d, Tier1 5-10d, Tier2 10-20d, Tier3 30-60+d → gesamt 8-14 Wochen; erst Vertikal-Slice, dann Funktionen/Tag re-baselinen.
- B1/B3/B6-ZUWEISUNG (2026-09-15, scripts/coldwin_trace.py, analysis/r1b-b1b3b6-assignment.md): CONFIRMED via PC-Spur (0x20DD7/0x20329-Reads = Stream-Wort-Indizes 0x210-0x246): Emission = FLUSH NACH WALK (B3-B6 nach letztem Read @1220230); B5+B6 = idx-15#3 (2 Dreiecke), B0-B4 = erste 5 Kommandos, idx-15#1/#2 = 1 Dreieck; Setup-Flush direkt nach idx-7-Read. STRONG: 0x18 verschiebt per-Objekt y-dominant (dz·F15-Kopplung). HYPOTHESIS offen: B1/B3-Mittelvertizes (344,237.625)-Provenienz + B6-Skalen — bewusst NICHT verfolgt (Verlockungs-Flags dokumentiert). Ghidra-Tools in dieser Session user-deaktiviert (0 Calls, Logging-Wrapper in tools/ghidra-mcp/python/bridge_mcp_ghidra/server.py bereit).
- 0x18-MATRIX HERLEITUNG (2026-09-15, analysis/r1b-018-matrix-derivation.md) — STATUS: BATCH ABGESCHLOSSEN; Messwert VERWORFEN (Lauf war V4 Pro Max statt Flash 4.1; 12.8 min/16 Calls NICHT als Referenz nutzen). CONFIRMED SHARC-Disasm (capture/sharc_disasm_20260829.txt): 0x18-Handler 0x20329 setzt F7:=F15, M018=[[F15,F4,F15],[F5,F15,F15],[F6,F15,F6]] auf (dx,dy,dz)→F8/F9/F10 — dz·F15 UND dy·F15 koppeln auf F8 UND F9; Kernel A=Sub (0x2030e), B=Add (0x2031e). CONFIRMED Ghidra (main.bin): FUN_8001adb0 = 0x18-Emitter (7 Halbworte, 11 Caller); FUN_8002e950 = 344-Gruppen-Produzent (Grids 1500/5000/10000 + Records [r2+0x218]+0x84+12i + KONSTANTE (0,0x271=625,0) je idx-15; kein statischer Caller); FUN_80016db0 = Walker ([r2+0xf8]+0xea54+8i→FUN_8001a968). STRONG: B2/B3-Shift +22.5 = dy·F15 (KORREKTUR: dy nicht dz!), F15=9/250=0.036; Höhen 999/16/998/16/64/16 = x.4-Festkomma. MESSUNG: MCP-Bridge per-Turn-Gating ("disabled by user" trotz check_tools=callable) → Fallback = HTTP-API desselben Servers via scripts/ghidra_http.ps1 (loggt gleiches jsonl, via=http-fallback): 12 Calls, 112/3019 chars/4, ~2s Serverzeit, Wall-Clock 12.8 min. OFFEN (Flag): Per-Objekt-F15-Evolution = Generalisierung.


- BATCH 2026-09-15 (Auftrag: vollstaendige Decompilation/nativ,
  Variante 2 vom Tisch; Renderer-Phase = Option D; KEIN Sprung auf alle
  27 Objekte). Zwei getrennte Berichte:
  analysis/bucket-c-pilot-report-2026-09-15.md +
  analysis/dpilot-report-2026-09-15.md (Detail:
  analysis/bucket-c-pilot-and-dpilot-2026-09-15.md).
  BUCKET-C-PILOT: Suite ppc_trap_suite_cbatch 8/8 PASS. FUN_8001b644 =
  *(u32*)(B+0x18)=0x78000000 (Stream-Cursor-Reset; B=**(r2+4)=0x800AE310).
  FUN_8000c654 = (mmio_u8(0x780C0003) ^ u8(B+0x24)) & 0xC0.
  FUN_8000c608 = Schatten-Toggles B+0x24^=0x80 / B+0x26^=0x100, dann
  0x780C0003=p1, 0x780C0000=u16(B+0x26). FUN_8000c2b4 = Download-Header
  (u16(B+0x26)&=0xFEFF, 0x780C0000=u16(B+0x26), 0x78000000/02=hi/lo(p1),
  04/06=hi/lo(p2), 0x7800000C=0, dann FUN_8000b51c(0xF,5)).
  FUN_8000b51c=c608+b484; FUN_8000b484=Handshake-Warteschleife (Bit7 von
  Schatten^0x780C0003). TEMPO: 4 Funktionen/~9 min (~2,2 min/Fn) inkl.
  aller Iterationen -> alte Rekalibrierung Faktor 15-40 zu hoch.
  SIDE-EFFECT-BARRIERE (CONFIRMED): c608/c2b4 schicken Kommandos ans
  CG-Board; 1 Aufruf toleriert, ab dem 2. HARDFAIL -> c2b4 nicht
  harness-rufbar (statisch belegt, wie FUN_8002d644).
  D-PILOT: Objekttyp-Taxonomie CONFIRMED via scripts/dpilot_stream_scan.py:
  Blockwort0>>16 = Emitter-Selector, GENAU 7 Emitter (0x37C0=0x237C0,
  0x37DA=0x237DA bekannt; 0x32B0=0x232B0 25 Slots, 0x22FE 16, 0x22E9 10,
  0x3527=0x23527 1 Slot, 0x3B97 1); idx 34/35 = nur Groessen von 0x37DA.
  Neue Familie (0x232B0/0x23527) = Cache-Basis 0x283D4, 2x16-Bit-SE; alte
  Familie Cache-Basis 0x283D7; beide schreiben dieselben 12-Wort-Records.
  WATCHPOINT-REZEPT (CONFIRMED, Tempo-Kern): `-state quick` OHNE
  `-playback` startet im Gameplay -> `wpd 0x283D4::dsp1,4,w,1,"saved
  <f>,0x20000::dsp1,0x40000; ...; wpclear; quit"` trifft in 1,2 s;
  Voll-Replay (7973 Frames) braucht ~2,5 min UND enthielt Index 187 nicht.
  Deterministisch: 2 Laeufe = byte-identische Dumps (SHA256 gleich).
  PITFALL: Watchpoint-Action nur in der erprobten Form; printf/wpaddr/
  Kommas -> "too many parameters for command". PITFALL: mmio_u8(0x780C0003)
  ist LIVE (toggelt 0x80/0x00 pro Frame) -> keine differentiellen Checks
  ueber Cases. OFFEN (naechster Schritt): Feldzuordnung der 12-Wort-Records
  (2. Dump nach dem Emit), Matrix-Quelle (Wire-WP auf DM(-0x0F,I7)),
  Log-Zuordnung (gleicher Lauf mit -log).
- STANDORTBESTIMMUNG 2026-09-15 (Konsolidierung, keine neue Analyse):
  (1) TEMPO-Re-Baseline: Vollzyklus (Auswahl→Ghidra-Lesen→Harness-Erwartungen→MAME-Verifikation→Doku)
  fuer EINE kleine, saubere Funktion = 112 s (FUN_80013d80, nur Lesen) bzw. 114 s
  (FUN_80013f88, 2 Ghidra-Calls/416 Tok-in/3-3 PASS). Alte Rekalibrierung
  (effort-recalibration-2026-08-31.md) rechnete G-Klasse 0,5-0,75 h, D 1-1,5 h
  je Funktion → geziehlter Rollout 80-120 h. Neu: ~2-4 min/Funktion ⇒ Faktor
  ~10-15. CAVEAT: n=1 je Klasse, Betonung "klein + sauber", chars/4-Token
  unterschaetzen 2-4x; gilt NICHT automatisch fuer D-Schwergewichte
  (FUN_80025478 1324 B, FUN_80022fa4 1004 B) oder F. Status STRONG INFERENCE.
  (2) BUCKET-ZAEHLUNG INKONSISTENT (CONFIRMED): die Rekalibrierungs-Tabelle
  benutzt menschliche Buckets, _ppc_inventory_classified.json andere:
  FUN_8003e840=G (nicht D), FUN_80008bc8=B, FUN_8000ce14=F. Classifier-D (20)
  hat bisher 3 dokumentierte: FUN_8000c6b4, FUN_80013d80, FUN_80013f88.
  Vor jeder Rollout-Aussage Bucket-Definition benennen (Classifier vs. Doku).
  (3) Naechster Batch (Vorschlag, nicht gestartet): Bucket-C-Pilot, 4 kleine
  observed-Funktionen: FUN_8000c654 (36 B/1 Caller), FUN_8000c608 (76 B/2),
  FUN_8000c2b4 (88 B/9), FUN_8001b644 (20 B/2) — alle 0x780C0000/0x78000000
  (lesbarer Shared-RAM ⇒ Verifikation sauber, anders als write-only 0x7D01).
- BATCH 11 = BUCKET-C-REST FERTIG (2026-09-16, bucket-c-rest-2026-09-15.md §5):
  4 große C-Funktionen (ab90/b128/8d0c/8f3c) = CG-Board-BRING-UP, kein Renderpfad.
  FUN_80008cd0 = LCG x*0x5D588B65+0x19660D (Doppelschritt je 0xFE); b8dc/b838/b96c =
  16/32/8-Bit-LCG-Muster-Write, b6cc/b5d8 = Verify (Byte-Lane-Maske), Signatur
  (addr,count,&state,xor,stride); cb40 = WDT-Kick 0x7D010006=0x80 nach jedem Wort.
  0x74000032 (16-Bit) = K037122-Reg 0x30 Bits 0-15 = Char-RAM-Bank; 0x74020000-3FFFF
  Tile-RAM; 0x74040000-7FFFF Char-Fenster (8 Bänke). 0x780C0000: Bit24 Shared-Bank,
  Bit28 DSP-Reset (0=aktiv), Bit29 K033906-Reg-Select; 0x780C0002 Bit22 enable_3d.
  KORREKTUR Bucket-C §1: "Bit8 = Download-Modus" = Bank-Select, "Bit12 = ?" = DSP-Reset.
  HÖHEPUNKT: FUN_8000ab90 = Voodoo-Erkennung über Proxy-PCI (c2b4 = Write/Adresse,
  c30c = Read, Kommandos 0xF/0xE, Quittung b484/b51c): PCI-ID 0x0001121A/0x0002121A
  (3Dfx-Vendor 0x121A, Dev 1|2) → *(s16*)(B+0x28) = Voodoo-Typ → Frame-Treiber
  FUN_80016758 wählt 0xFF076000 (Typ 1) / 0xFF080000 (sonst); Zellgröße 64×16 vs 32×32;
  Voodoo2-Zweig testet PCI-Reg 0x14 mit 0xF47C6451 (MAME-kommentiert!). Fehlercodes
  stufenindiziert 0x10000000|Stufe bzw. 0x2X000000. Werkzeug: scripts/ghidra_dump.ps1
  (HTTP-Batch-Dump). read_memory ist AUSSERHALB des 713368-B-Abbilds (>0x800AE297)
  unzuverlässig (SDA-Slots nur zur Laufzeit prüfen).
- BATCH 12 = BUCKET D FERTIG (2026-09-16, analysis/bucket-d-2026-09-16.md):
  D+E vollstaendig (24/24; E war schon 4/4). 16 D-Funktionen in ~4 min,
  29 Ghidra-Calls/25,3k chars/~6,3k est.tok, 0 MAME-Laeufe (Barriere).
  tools: ghidra_dump.ps1 loggt jetzt selbst in mcp_call_sizes.jsonl (via=http-fallback).
  MMIO: 0x7D000000-4 = IO-Ports 0-3 (Input/ADC/DIP), 0x7D010000/01 = 7-Seg,
  0x7D010002 = ADC12138#2 (GQ830-PWB, nur sscope: CS b4/CONV b3/DI b5/SCLK b7),
  0x7D010003 = Sysreg0 (LAMP0-3/JVSTXEN; JVSTXEN b3 vs b4 je IN2&3 -> deckt
  MAME-Kommentar), 0x7D010004 = Sysreg1 (SNDRES b7/COMRES b6/COINRQ b5,b4 +
  ADC b0-b3; X76F041 nur in hornet_x76/NBA -> bei sscope ADC-Zweig),
  0x7D010005 = Sound-Control = serielles Lautstaerke-Schieberegister
  (e588/e60c = Taktprimitive, e9dc = Setter 0..0x1E -> *0x3F/0x1E),
  0x7D010006 WDT, 0x7D010007 CG-Control (b5/4 = CG-Board-ID schaltet m_cg_view).
  NEU CONFIRMED: 0x40000000-0x4000000F = PPC403GA-interner SPU (MAME ppccom.cpp:322
  internal_ppc4xx; +0 LINE_STATUS/+2 HANDSHAKE/+4,5 BAUD_H,L/+6 CONTROL/+7 RX_CMD/
  +8 TX_CMD/+9 BUFFER). Loest HYPOTHESIS 9 aus bucket-d-fun80013d80.md auf: die
  13xxx-Kette = SERIELLER Transfer (TX 0xF0 = Bit7+Op3 = DMA-Kanal 3, passt zu
  mfdcr DMADA3). FUN_80067bb8 = JVS-SPU-Init (divisor 0x70800/baud-1, 0x70800 =
  7.3728MHz/16; Caller = 19200 Baud) + JVSTXEN-Bit.
  FUN_80022fa4/23420 = ADC-Bit-Bang (Kanaele aus [[r2+0x12C]]+7/+0xF;
  sscope-Ports ANALOG1/2 = Gun Yaw/Pitch, MAME-Callback m_analog[ch]).
  FUN_8000cf44 = K037122-ID-Test (5x 0x74000016&0x3FF, Mehrheit; MAME konstant
  0x3FA, Schwelle >0x3F9 passt). Schatten: [r2+0x20]+7/8/9/0xB = Spiegel von
  0x7D010003/4/5/7. BARRIERE verschaerft: gilt fuer Protokoll-/Kommando-Register
  (CG/Shared/Sound-Mailbox/ADC/SPU/WDT), NICHT fuer reine Zustands-Ausgaberegister
  (7-Seg/Lampen/Sound-Control) -> deren Effekt nur ueber RAM-Schatten oder
  Log-Hook pruefbar (Register write-only).
- BATCH 13 = BUCKET A FERTIG (2026-09-16, analysis/bucket-a-2026-09-16.md):
  39 Luecken (29 GAP + 10 THIN) von 76 A-Funktionen; Differenzliste zuerst
  (scripts/a_gap_census.py + a_diff_list.py -> analysis/_a_diff_list.txt).
  LESSON: Differenzliste NIE gegen nur EIN Dokument - 15 von 39 hatten eine
  zweite Quelle (plan/interface/native-poc/graphics-pipeline).
  State-Struct (0x800B3C28) CONFIRMED: +0/+2 Display-Breite/Hoehe
  (0x200/0x300, 0x180/0xEC; Umschaltung ueber SDA *(r2+0xC)), +4 Modusflag
  (1 live / 0 deferred), +5..+0xB Tabellenzaehler (0xFF = -1 Sentinel),
  +0xC Record-Zaehler, +0x10 gecachtes Objektwort, +0x14/+0x18 Cursor-Slots,
  +0xECD4 Records (Stride 0x10), Queues: 1 @+0xc01c, 2 @+0xd820, 3 @+0xea24.
  FUN_80017674/8001758c = RECORD-BUILDER der Render-Liste: word0=Cache,
  blockptr=state+0x18 (frueherer CURSOR-Stand), len=Cursor-Delta ->
  Bloecke liegen IM Kommandostrom, keine Content-Daten; Sortkey =
  (objptr-0x80000000)>>4 | Gruppe<<29 | 0x10000000; nur bei state+4==0.
  FUN_8001a054/8001a074 = Cursor-/Bank-Swap (frame+0x18 <-> +0x1C).
  Dirty-Queues komplett: Q1-Drain 16cd8 (Budget 0x4000) -> 0x61/0x62-Emitter
  b108 (+19530 46er-Format-Tabelle mit ASCII-Feldern, 194f0/194a8/195fc);
  Q2-Drain 16be4 (Budget 0x20000, Schaetzer 19888) -> 197c4 -> b4d4/190bc
  (0x42/0x44-Block, Deskriptor-Tabelle [r2+0x100], Stride 0x24);
  Q3-PRODUCER = FUN_80018734 (4-Slot-Ring @0xea24, Stride 8).
  Emitter-Vokabular +17: 0x06 (17a8c, Tabelle 0xEC68 Stride 0xC, Zaehler +0xB),
  0x07 (17c5c, 0xEC4C, +9) - beide Auto-Registrierung durch den Emitter selbst;
  0x0B (b050/b09c), 0x10 (1af38/ab90), 0x17 (adf4), 0x42/0x44 (190bc),
  0x5C/0x5D (ac68/a9a8), 0x5F/0x60 (18844 - setzt Dirty-Flag 0xea49!),
  0x61/0x62 (b108), 0x63/0x64 (a8f4), 0x65/0x66 (a82c). Paar-Konvention:
  sel<0x200 -> Opcode, sonst Opcode+1 + sel-0x200.
  Alle 39 schreiben den Shared-RAM-Stream -> §8-Barriere, 0 MAME-Laeufe.
  TEMPO: 5,4 s/Funktion (41 Ghidra-Calls, 40,3k chars, 3,5 min).
- BATCH 16 = BUCKET F1 FERTIG (2026-09-16, analysis/bucket-f1-2026-09-16.md):
  31 F-Caller von FUN_80017674/8001758c, ALLE 31 Luecken (0 DOC/24 THIN/7 GAP;
  die "37-Renderer"-Liste in ppc-rendering-pipeline-plan.md §3.5 ist KEIN
  Doku-Beleg). 39 Ghidra-Calls (via=http-fallback), 57,6k chars, 8,9s, 0 MAME.
  KERN: (1) FUN_80017674(z) - Argument = GRUPPEN-z und wird zum Sortkey
  (z+0x80000000)>>4|Gruppe<<29|0x10000000 (22/26 Caller bit-identisch zum
  vorausgehenden b09c/b050/adf4-z); len=0 -> Zaehler-Rollback (state+0xC, Init
  0xFFFF); Sortkey nur wenn (objword>>0x19&7)!=0. FUN_8001758c(recptr,UNUSED,
  objidx,mode) - Sortkey aus *(recptr+8). (2) state+4 = Modus-Schalter
  Bau(0)/Live(1); Schreiber FUN_80016850(Init 1), 800188a8(->1),
  80018950(->Argument); Builder sind No-Ops bei state+4!=0; 80018950 wirkt NUR
  bei state+0x14!=0 (sonst No-Op inkl. Modusflag, Modus bleibt alt) -> Idiom der
  Renderer-Familie: 18950(p) -> Emission -> 188a8(); nur p=0 aktiviert den Bau.
  (3) BAU->STROM GESCHLOSSEN (STRONG INFERENCE): Fenster-Tabelle state+0xEA54
  (8-Byte {Anfang,Ende}, Index state+5, Dedupe) <- 800188a8/80018950, gelesen von
  Walker FUN_80016db0 -> FUN_8001a968(start,end-start). (4) KLAMMER-ZENSUS (alle
  29 Caller von 80018950 gelesen): 4x 18950(0) = Bau (80018b00 Frame-Setup,
  8003d974, 8003da68, 80044a98) vs. 26x 18950(1) = Live -> Record-Bau nur in den
  3 Spans 8003d974/8003da68/80044a98; Auslöser = FUN_8003cf0c -> FUN_8003e8e0
  (einziger externer Caller der Hubs 8003d718/8003d974/8003da68), Bank-0-
  Durchlauf, Gate bit21 von [[r2+0x220]]+8. 80018b00 = Frame-Aufbau (Bau-Klammer
  um 80021b40-Kamera + ColorPath-Grundzustand), 80018c3c = Commit (188a8() +
  Walker). Slot-Array [[r2+0x234]] Stride 0x180 (8003d974: param_1*0x180).
  (5) HUD-Schicht:
  FUN_8004721c = Text (19 Caller, ASCII->Index-Tabelle [r2+0x648]+0x20),
  FUN_80047108 = Zahl mit Blank-Unterdrueckung (9 Caller; FUN_8003b974 =
  Dezimalstellen-Packer, FUN_80011560/115bc = Zahl->Text). Objekt-Index-Tabellen:
  [r2+0x298], [r2+0x620]/[0x628], [r2+0x174] (Halbwortpaare, 2. Haelfte +0x800),
  [r2+0x638] (Slot Stride 0x28, Feld +8). Skripte: f1_gap_census.py/f1_diff_list.py.
- BATCH 14 (2026-09-16), zwei Teile:
  (1) BANK/CURSOR GEMESSEN (analysis/bank-cursor-measurement-2026-09-16.md):
  0x78010000 = PUFFERGRENZE, keine Bank (MAME map 0x78000000-0x7800ffff;
  FUN_8001b62c = 0x78010000 - cursor). frame+0x18 = aktiver Schreibzeiger
  (Bau-Phase RAM-Pointer, Emissionsfenster 0x78000000), frame+0x1C =
  Live-Strom-Zeiger; Paar FUN_8001a054 (aus 800188a8) / FUN_8001a074 (aus
  80018950) = Fenster auf/zu. ECHTER BANK-SCHALTER = FUN_8000d08c(bank):
  [r2+0xC]=bank&1 (Display 0x200/0x180 vs 0x300/0xEC), [r2+0xF8]=state_base +
  bank*0x10CD4 (GETRENNTE State-Structs), [r2+0x28]=base2+bank*0x1265C.
  Gemessen: Frame-Kontexte 0x800AE310/0x800AE34C (d0x3C), States 0x800B3C28/
  0x800C48FC (d0x10CD4); Bau-Flaeche beginnt bei state+0x1C (== gemessenes R).
  main (800089a0): Bank-Reihenfolge **1 dann 0** je Frame.
  (2) BUCKET B FERTIG (analysis/bucket-b-2026-09-16.md): 58 Fn = 2 DOC +
  12 THIN + 44 GAP -> 56 Luecken gelesen (57 Ghidra-Calls, 45,7k chars,
  ~11,4k est.Tok, 12 s, 0 MAME-Laeufe). Boot-Kette main -> FUN_8000ca48 ->
  FUN_800163c8 (Tile-RAM-Muster + Zeichensatz + SPU-DMA) -> FUN_80016758.
  0x80023xxx = JVS-/POST-Fehleranzeige + HALT-Schleifen; 0x80025xxx/0x80026xxx
  = Menue-Statemachines (Jump-Tables [[r2+0x830]]+0x1A0/+0x308 + [r2+0x834]);
  FUN_80025b7c wartet auf Leerlauf der drei Dirty-Queues (+0xc01c/+0xd820/
  +0xea24) -> Klammer zu Batch 13.
  WERKZEUG-LEKTIONEN: (a) bpset <addr>[,<cond>][,{<action>}] - Action an
  3. Stelle, `bpset a,{..}` = stille Condition und feuert NIE; (b) PPC-Daten-
  Watchpoints greifen beim PPC403-DRC NICHT (logisch+physisch getestet) ->
  Breakpoints + logerror mit r3/r4/r5/lr/pc nutzen (funktioniert); (c) `-log`
  UEBERSCHREIBT capture/error.log bei JEDEM Lauf; (d) K037122-Reg 5: ROM wartet
  auf 0x03F7, MAME liefert konstant 0x03FA (k037122.cpp:247) -> Poll laeuft in
  den Timeout (nur POST-/Fehlerpfade).
- BATCH 17 = BAU->STROM CONFIRMED (2026-09-16, analysis/batch17-bau-strom-measurement-2026-09-16.md,
  4 MAME-Laeufe `-state quick -seconds_to_run 166` = 101 Frames, Breakpoints + logerror):
  Transport ist **FUN_80016e34** (Render-Listen-Replay; lr 0x80016F6C), gerufen von
  FUN_80016968 (Szenen-Walker, schreibt 0x0002-Framemarker) <- FUN_80018c3c <- main;
  je Eintrag der Liste `state+0xECD4+i*0x10` (ent = r30; Format {+0 word0/Objektwort mit
  Gruppe bits29-31, +4 Sortkey, +8 HIGH-Halbwort = len, +0xC = blockptr in der Bau-Flaeche})
  wird `FUN_8001a968(blockptr, len)` in den Strom kopiert: 14988 Kopien/1.147.168 B,
  ALLE dst in 0x78000000-0x7800FFFF, src ab Staging-Basis 0x800B3C44/0x800C4918,
  Inhalt 520/520 identisch (Kreuzvergleich Lauf1 Ziel vs Lauf2 Quelle). Listenlaenge
  36 (Bank1)/116 (Bank0), Liste @ 0x803FF760. Bau-Klammern (18950(0) in 8003da68/
  8003d974/80044a98) schieben Staging-Cursor state+0x1C vorwaerts (Bank0 0x23E4+0x8A B).
  KORREKTUR zu F1 4.2: Fenster-Tabelle state+0xEA54/Walker FUN_80016db0 kopiert den
  LIVE-Block (202 Kopien = 1/Bank/Frame; Dedupe verschmilzt benachbarte Bereiche ->
  nur 1 Slot), NICHT die F1-Records. 18950 schreibt Slot-Start nur bei eingehendem
  state+4!=0, 188a8 Slot-Ende nur bei state+4!=0.
  DEBUGGER-LEKTIONEN: (a) d@/w@/b@ brauchen DOPPELTE Indirektion (state=*(*(r2+0xF8)),
  frame=*(*(r2+4)); *(r2+0xF8)=0x800FA288 ist eine Zellenadresse, Inhalt = State-Basis
  0x800B3C28/0x800C48FC); einfache Indirektion liefert plausiblen Muell (stiller Fehler).
  (b) Zwei bpset auf dieselbe Adresse: nur der erste loggt (`g` ueberspringt den zweiten).
  (c) `-seconds_to_run N` = ABSOLUTE Emu-Zeit (quick.sta ~163 s) -> N=3 = 1 Frame.
  (d) `lr` attribuiert nur am Funktions-EINTRITT den Aufrufer.
- BATCH 18 = BUCKET F2 FERTIG (2026-09-16, analysis/bucket-f2-2026-09-16.md):
  F2 = Frontier Tiefe 1 ab A/B/C/D/E ohne F1 = 81 Fn/3914 Insn/49 observed;
  10 DOC (8 davon nur Familienzeilen -> Lektion 54) / 46 THIN / 25 GAP;
  81 Ghidra-Calls (HTTP-Dump), 74,8k chars, 18 s, 0 MAME-Laeufe.
  ARCH-CORE: FUN_8000a110 = CG-Proxy-Mikrointerpreter (Opcode = obere 4 Bit; 0x2 Write
  c2b4 / 0x3 Write-0 / 0x5 Read c30c / 0x6 N-Read / 0x7 a07c / 0x1 a32c / 0x8 9ff8 /
  0x9 9f60 / 0xA NOP / 0x0 Ende; Rueckgabe Fehler|Blockindex) -> die 0x22../0x32../0x12..
  Wortlisten in B/C sind EINE Sprache; FUN_8000be40 = Bring-up-Tor mit Stufenkette
  ab90->ab0c->a7f4->a110 + 2 Block-Uploads b048; FUN_800101a0 = Bank-State-Fresh-Init
  (beide Baenke via d08c; 0x10x0x10 Tabellen Stride 0x84); Text-Ausgabe 80010580/10704
  (+115bc, Slot-Array *(r2+0x54) Stride 0xC) + Reset 80010ec0; Bus-Erkennung 800140c4
  (Ping 1..0x1F, Echo 01/01) + 800141c0 + 80014030; RTC M48T58 0x7D021FF8-FF
  (80013698 lesen/pruefen, 80013598 stellen, BCD 800151c8/15250, Datumsindex 80083858);
  Muenz-Zeitfenster-Statistik 80083968 (Histogramm ueber 0x11 Einwuerfe, Median 80083cbc);
  ROM-Summe 800253a0 (0x80000 Dwords ab 0x7F000000 + WDT-Kick), POST-HALT 80025440;
  K037122: 80009e68 (Scroll/Konfig) 80009ec0 (Blocktransfer-Setup 0x74000054=0x446)
  8000f7e4 (Tile-Clear) 8000fcf8/8000fd7c (Glyph-Upload/Tabellen+Ready-Bits);
  Relokationstabelle 0x80026000 (8005d6f0) + Modulpatcher 8005d440; Mini-Libc 8000d2c8
  (strncmp), 80016380 (Nibble->Hex), LZ-Decompressor 80009c14 (Ring 0x1000, WDT).
- BATCH 19 = F3+F4 FERTIG (2026-09-16, analysis/bucket-f3f4-2026-09-16.md):
  F3 = F mit >=5 Aufrufern (43 Fn/3140 Insn), F4 = F mit MMIO (10 Fn/511 Insn);
  Ueberlappung VORHER rechnen (scripts/f3_gap_census.py): F3&F1=2, F3&F2=6,
  F4&F2=6 (nicht 5!) -> NEU = 39 Fn/2813 Insn/36 obs; DOC 1 (8000cf44 in
  bucket-d schon CONFIRMED) / THIN 4 / GAP 34 -> 38 Luecken; 39 Ghidra-Calls,
  56,5k chars, 8,75 s, 0 MAME-Laeufe (keine MMIO-Harness-Faehigkeit).
  KERN: Q14-Festkomma-Mathe (FUN_80020c80 sin/cos, 800209f0 atan2, 80020b84
  Umkehr, 80020f7c isqrt, 800210c8 MAC, 8001d880/8001d800 Matrix*Vektor,
  8001b7b8/b7d8 Rundung; 1.0=0x4000, Vollkreis 0x10000, 0x4000 = +90 Grad --
  ACHTUNG: 0x4000 ist in dieser ROM doppeldeutig Q14-1.0 UND 90 Grad);
  Szenengraph: Eltern +0xE4, Weltmatrix +0x4C, Weltpos +0x40/44/48,
  Kind = Eltern*lokal (8001efe8 lokal, 8001e62c Produkt, 8001dd78 Winkel
  zurueck) in 8004992c/80049c48; FUN_80080248 = ColorPath-Flag-Diff ->
  A-Emitter 80017714/80017f58; SDA(0x304) = Objekttyp-Tabelle Stride 0xC
  {Zeigerarray, Bitmaskenarray, Anzahl} (Schreiber F2 8005d884, Leser
  8004fc60); SDA(0x300) = Slot-Tabelle Stride 0x5C; FUN_80037258 = Slot-Pool
  (0x20-Stride, First-Free sonst LRU ueber Feld +1) + Deskriptorfabriken
  80031590 (0x23)/80032828 (0x21); FUN_8002ad2c = Bank-Dirty-Queue-Test
  (2-Bit-Maske, CONFIRMED gegen Batch-14-Notiz); Textkette
  80010580/80010704 -> FUN_800115bc (printf-Formatter: + 0 Breite .Praez l
  f X x b c d s u) -> 80011064/80010fe0/80010f54/80011160/800111d8/800112dc/
  80011214 -> FUN_8000005c (Zeichen-Emitter; F2 fuehrte es als r11-Thunk ->
  Rolle nur HYPOTHESIS); Glyph-Satz SDA(0x28)+0xB51C+idx*0xC, +5 = Breite
  (80043388 x F2 8000fcf8), Pool Stride 0x844/Zeile 0x104, Ready-Bits +0x840;
  Sound-Vokabular FUN_8003c6f0(0xF101/0xF110/0xF118/0xF120xxxx) + 8005643c
  Block, 8003aa2c = Punkte-Zaehler (Einheitenwert*Menge*Multiplikator, x2 Bonus);
  Optionswort *(SDA(0x14)+0x4C) (Bits 10-12/14-15/24/29-31) +
  *(short*)(SDA(0x14)+4); 80014fb4 = Char-RAM-Ausgabe 0x74027C00 (0x0A CR/LF,
  0x0D CR), 8000ee34 = Glyph-/Tile-Expansion 0x74040000 (Nibble vs. Kopie),
  8000ceac = Spielerpositions-Upload 0x74000036/20/22; LZSS #2 = 8002b000;
  8000cf44 = 5x 0x74000016&0x3FF Mehrheit (deckt bucket-d).
  Sektion "11 harness-faehige Rechenfunktionen" im Bericht §5 = erste
  belastbare Harness-Liste aus F.

- BATCH 20 = SAMMELVERIFIKATION <ARCH-CORE> (2026-09-16, analysis/batch20-arch-core-verification-2026-09-16.md):
  Q14-Mathe 78/78 PASS (scripts/ppc_trap_suite_archcore.lua), Szenengraph 15/15
  (ppc_trap_suite_scenegraph.lua); 5 Ghidra-Calls/3,0k chars, 6 MAME-Laeufe.
  KORREKTUR 1: 80020f7c = floor(sqrt(rohes Argument)), KEIN Q14-isqrt (9/9 gemessen).
  KORREKTUR 2: 8001d800/8001d880 wenden die Matrix SPALTENWEISE an (out_i = sum_j m[j][i]*v_j).
  Rundungsregel zu: 8001b7b8 = sat(x>>15,+-0x4000), b7d8 = sat(x>>14) - keine Rundung.
  8001e62c = R (x) m (LINKSprodukt, Diskriminator-Case) = "Kind = Eltern (x) lokal";
  8001f80c = R (x) m; beide strukturell CONFIRMED, Term-Modell registergenau offen
  (scripts/archcore_model.py als Werkzeug, 0 Ghidra/0 MAME). 8002b000-LZ-Format exakt.
  HARNESS-LEKTIONEN: (59) Lua-`>>` = LOGISCHER Shift -> in ROM-Modellen `v // 2^n`;
  (60) Scratch R1-0x200 kollidiert mit Callee-Frames >=0x200 (80049afc ~0x240,
  8002b000 ~0x1010) -> R1 := R1-0x600 + Regions-Snapshot/Restore; (61) erst die
  Pruefregel anzweifeln, dann das Modell; (62) Ghidra-Term-Modelle mit wiederverwendeten
  Variablen (uVar17/undefined6) unzuverlaessig; (63) d@(r3+0xE4) genuegt bei Zeiger im Reg.
  LIVE-PFAD (wichtigste Lektion, "theoretisch moeglich != genutzt"): -state quick,
  4 Breakpoints, ~10 s Wall: FUN_8004992c = 0 Aufrufe; FUN_80049c48 = 10 850 Aufrufe
  (10 distinkte Objekte, Gates 0x00080007/0x00280007), Elternzeiger +0xE4 in ALLEN
  10 850 Aufrufen = 0 -> Eltern-Pfad verifiziert, aber im Messfenster INAKTIV (nur
  Wurzelpfad); FUN_8001efe8 11 984 (lr 0x80049CB4 = Wurzelpfad, 0x8003C4D8 = 8003c474);
  FUN_8001e62c = 206 167 Aufrufe, Aufrufer DURCHGEHEND lr=0x80049B84 = Knotenkette
  FUN_80049afc; Matrixziele im Pool ab 0x803A0000, Stride 0x64 (Matrix +0x1C,
  Weltpos +0x10/14/18). => fuer den Port ist der live genutzte Transformpfad die
  (noch unverifizierte) Knotenkette, NICHT der Szenengraph-Elternpfad.
- BATCH 21 = KONSOLIDIERUNG (2026-09-16, 0 Ghidra/0 MAME): Gesamtstand-Dokument
  analysis/native-port-status-2026-09-16.md (Einstieg "was haengt zusammen";
  Anker bleibt r1b-workstream.md). Kern darin: CONFIRMED-Bausteine (Voodoo-Pipeline
  inkl. Live-GL pixelgenau, SHARC-Interpreter/Dispatch 0x28283, PPC-MMIO D+E 24/24,
  Kern-Schicht + PoC 17 Frames, Q14-Konventionen, Szenengraph), der tatsaechlich
  genutzte Pfad (Listen-Replay 80016968->80016e34->8001a968; Record-Bau nur bei
  state+4==0; 37 Direkt-Renderer im Billboard-Frame inaktiv; Familie 2 fuellt nur
  die Rohstufe) und die Luecken: L1 0x8004xxxx (239 Fn/170 obs) + Knotenkette
  80049afc, L2 F5 (337 Fn/14 409 Insn ohne Caller, Sprungtabelle 80029f50),
  L3 SHARC Indizes >=2048/Emitter 0x37DA/fstart-fd DERIVED, L4 Daten-Content-Seite
  (Blockherkunft, tex_tbl=[r2+0x104]=0x8008F1A0, 0x8017D000/0x80390000), L5 HYPOTHESIS-Liste.
- BATCH 22 = L1 KNOTENKETTE VERIFIZIERT (2026-09-16, analysis/nodechain-49afc-verification-2026-09-16.md):
  FUN_80049afc(obj,depth) = DFS ueber Kette obj+0xF8. Record 0x64 B, Pool 0x803A0000-0x803B8FFF
  (1024 Records, Cursor SDA(0x464), used-Byte +0, Allokator FUN_80062b94 First-Fit/Wrap, Init 80062d8c),
  Ketten = zusammenhaengende 27-Record-Bloecke (Abstand 0xA8C), next @+0x60.
  Flags: +1; Bit1=0 -> Abstieg, Bit0=1 -> Push (merkt Basis-Matrix UND Position), Bit0=0 ohne
  Abstieg -> Pop (stellt beide wieder her); Bit2/3/7 in 49afc wirkungslos; Bit4 -> Einzelwinkelpfad.
  Felder: +2/+4/+6 s16 Winkel a1/a2/a3 (Q14), +0xA s16 Vorschub, +0x10/14/18 s32 Weltpos,
  +0x1C..0x2D 3x3 s16 Matrix (El. +0x22/24/26 = Richtungsachse), +0x30/40/50 3 Anhang-Slots.
  Matrix: node+0x1C = R(a1,a2,a3) (x) Basis via 8001e62c (Basis = obj+0x4C bzw. Vorgaenger+0x1C)
  = DASSELBE Linksprodukt wie die Szenengraph-Regel; bei Flags-Bit4 stattdessen 80020100(Basis,a3)
  (Live 86800 = 8/Kette; Bit4 => immer a1=a2=0, Bauer setzt es). Pos: += (Betrag * EIGENE
  Matrixachse) >> 14 (arithmetisch). Herkunft: 80062a4c -> 80062b1c -> {800625f4 Deskriptor ueber
  SDA(0x300) Slot Stride 0x5C: +0x14 Deskriptorptr {+4 Anzahl,+0xC s16-Vorschubtbl,+0x10 3xs16
  Winkeltbl}, +0xC Flags-Bytetabelle, +0x42/44/46 Indizes in SDA(0x3F4)} + 80062430 (Bau) +
  80062328 (lauf 0x108/0x10C/0x10E/0x110/0x112/0x18). Builder live 0x (Ketten einmalig beim
  Erscheinen). Live: 10850 Kettenlaeufe (dep=FFFFFFFF, 4992c/49c48), 10 Objekte, 27 Knoten/Kette,
  292950 Besuche = 206150 e62c + 86800 20100 (erklaert Batch-20-Messwert 206167). Suite
  ppc_trap_suite_nodechain 17/17 PASS (Knoten unterhalb des Callee-Frames bei R1-0xE00).
  AUFWAND: 40 Ghidra-Calls/30,7k chars/6,0s, 7 MAME-Laeufe, 0 MAME-Neulaeufe fuer die Suite.
  NEUE REGELN: (64) 0 Treffer = erst Messung, wenn Breakpoint im Skript DIESES Laufs steht und die
  Logdatei DIESES Laufs ausgewertet wird (sonst falscher "toter Zweig"); (65) mtcrf FXM fuellt das
  CR-Feld aus den UNTEREN 4 Bit (MAME ppcdrc.cpp, CR-Bits MSB-first) -> "rlwinm r0,r24,0x1c,0x1c,0x1f;
  mtcrf 0x1,r0" testet Flags-Bit4; (66) r31 = zweiter Kanal: Tiefe=(r31-r1-0x40)/0x10; (67) MAME
  "dump <file>,<addr>,<len>,<width>" laeuft headless (logisch=physisch); (68) Treiber loggt jeden
  Shared-RAM-Zugriff -> error.log ~20 MB/s Emu-Zeit (37 s ~= 720 MB), nur per Regex auf eigene
  Praefixe auswerten.


- BATCH 23 = F5 GEFILTERT (2026-09-17, analysis/f5-veneer-filter-2026-09-17.md,
  scripts/f5_filter3.py -> analysis/_f5_filter.txt): F5 = Bucket F + callers==[]
  = 337. Filter (0 Ghidra): (a) ruft live-heiss {80049c48,80062a4c,80016e34,
  8001a968,8001b108,8003cf0c} = 2 Fn (FUN_8007bf00, FUN_80048edc); (b) ptr_refs_from
  != leer = 60; Ueberlappung 0 => 62 (18,4%). Ganzes Programm: nur 77/1611 Fn
  haben ueberhaupt einen Daten-Zeiger-Slot, 60 davon sind F5.
  STRUKTUR: (i) 12-Byte-Deskriptor-Records {code_ptr, 0x800ADA5C (=r2!), 0} in
  0x800ACB2C-0x800AD9F0/0x800ADF38-0x800AE290, Stride 0xC; indiziert ueber
  Zeigerarrays 0x800AA380 / 0x800AA680 (Index 6 -> 0x800AD600, Querprobe via
  get_xrefs_to); 0x800AD060 = Default-Record. (ii) SDA-Zellen >= r2 (0x800ADA5C)
  halten BASISADRESSEN relativer Sprungtabellen: Ziel = [SDA(x+4)] +
  *(int*)([SDA(x)] + idx*4 + off) - verifiziert an FUN_8007C760 (11 Eintraege,
  Offsets 0x54..0x7C Stride 8 -> Stubs 0x8007C7B4+, Sprung bei 0x8007C7B0),
  FUN_80077C98 (Basis 0x80076E80, Tabelle 0x8008B018), FUN_8006C27C (Basis
  0x80068B80, Tabelle 0x8008ABBC) und 80029F50 (Basis [SDA(0x1C8)]=0x800291F8,
  Tabelle 0x80087158, 6 Ziele 0x80029FE4+8n). Ghidra saugt die 8-Byte-Stubs in
  den Dispatcher-Body ("No function found" fuer 0x8007C7B4/0x80077CE4/0x8006C484/
  0x80029FE4) => unsichtbar, 0 Caller. "0 Caller" = "indirekt aufgerufen".
  INHALT (16 von 62 gelesen, 46 offen): FUN_8007bf00/FUN_80048edc schreiben via
  FUN_8003849c (Deskriptor [SDA(0x224)]+idx*4+0x10, out = s16(+0x10)+s16(+0x16) /
  s16(+0x12)+s16(+0x18)) ZIELWINKEL direkt in Knoten +2/+4 der L1-Kette obj+0xF8
  (FUN_8003aecc(obj+0xF8,n)) und rufen dann 80049c48 => Verbindung Veneer ->
  Kettenwinkel -> Weltmatrix. 4 Kandidaten = Modellauswahl-Idiom
  (s16(obj+4)>>8 -> Index -> FUN_8004FC54/FUN_8004FC60 (Objekttyp-Tabelle
  SDA(0x304)) + Szenenupdate 8004992C, Zufall via LCG 80015294; Flags nach
  obj+0x14C). FUN_8006c6b4 nutzt 14. Kettenknoten (FUN_8003aecc(obj+0xF8,0xE))
  + Physikblock obj+0x208..0x238. Zustandsautomaten: FUN_80049da0 (3 Phasen,
  Rueckgabe 0/1, liest obj+0x14C-Bitfeld), FUN_80072540 (Distanz +-0x32 +
  Historienkopie +0x153/155/157), FUN_8003c7b4 = ZWEITER Bank-0-Umschalter
  (FUN_8000d08c(0), Gate s16([r2+0x14]+4)==1, 0x57-Countdown), FUN_8007c760
  (11 Zustaende), FUN_80077c98. FUN_80048dd8 = Huelle nach 0x8004xxxx (gestoppt).
  PITFALLS: (70) rom/830d01.27p ist KOMPRIMIERT -> Bytes nur via Ghidra/read_memory
  (78/78 Mismatch bei Datei-Offset=addr-0x80000000); Abbild 830d01.27p.main.bin
  (0x80000000-0x800AE297). (71) ptr_refs_from ist UNTERGRENZE (nur erkannte
  Funktions-Eintritte; 0x800AD03C -> 0x80072328 unerkannt). (73) Programmwahl je
  Serverstart pruefen: be.bin -> "No function found", korrekt load_program_from_project
  + switch_program auf main.bin. (74) read_memory innerhalb des Images zuverlaessig;
  get_xrefs_to <slot> = Tabellenkonsument; GET /mcp/schema = 215 Tool-Endpoints.
- REGEL (65) PRAEZISIERT (2026-09-17, mame/src/devices/cpu/powerpc/ppcdrc.cpp:4339-4348):
  CR32(reg) = uml::mem(&m_core->cr[reg]); fuer mtcrf 0x1,rS gilt CR7 := rS & 0xF
  (Feldbit0=LT <- rS-Bit28, EQ <- Bit30, SO <- Bit31). Damit testet `bne cr7`
  rS-Bit1 (0x2) und `bns cr7` rS-Bit0 (0x1) - per Disassembly von FUN_8007bf9c
  verifiziert (Ghidras "& 0xf) >> 1 & 1" bzw. "& 1" sind dort korrekt). Die alte
  Formulierung "rlwinm r0,rS,0x1c,0x1c,0x1f; mtcrf 0x1,r0 testet Flags-Bit4" ist
  damit noch NICHT widerlegt, aber neu herzuleiten (offen).

- BATCH 31 = EMITTER-VIELFALT DER TEXTUR-SETUPS GEKLAERT (2026-09-17,
  analysis/texpath-batch31-emitter-diversity-2026-09-17.md): *LEDGER* (gleiches Fenster,
  bpset-Emissionen vs. SSC_TEXREG-Writes): Setups(:voodoo0) = 0x56/0x57 (FUN_8001B0D0)
  + 0x5C/0x5D (FUN_8001A9A8) + 0x65/0x66 (FUN_8001A82C), -str 80 (360 F, 104 699 Setups)
  = +0,31 % (blockweise <=0,54 %) = 46,3/37,5/16,5 %. 0x18/0x17/0x10/0x37/0x63-64
  = 0 Setups. WIDERLEGT: 0x800648C8 (Objekt-Event-Handler; 'li 0x65' = Wert 101,
  sth r5,0xE(r24)) und FUN_8006C81C (Aktor-Init; 0x66 = Modell-Id an FUN_8004FC60/
  SDA(0x304)) = je 0 Aufrufe; ebenso FUN_8000A380/A42C (0; CG-Proxy-Clients des Bring-up:
  FUN_8000A110({0x23400001,4,0x224802c0,0x14261a01,..}) + FUN_8000b51c(0xA|0xB,60000)
  = fester textureMode 0x14261A01; KEIN HUD-Fall). FUN_80019458 = Patch-HELFER mit genau
  EINEM Caller FUN_8001B108 (0x61/0x62-Emitter), patcht KOPIEN (nicht 0x65/0x66-Records)
  => eigenstaendige 2. Record-Quelle mit eingebetteter Textursektion (texCount =
  (*(u16*)(FUN_80019530(src)-4))/6), aber nur 2 730 Records = 0,30 %. FUN_8001A8F4
  (0x63/0x64, 6-B-Records) = 396 Aufrufe = 0,04 %, kein Setup. VOLLINVENTAR: Stream-Emitter
  = Funktionen mit SDA(4) (96), Bibliothek 0x8001A7B4-0x8001B658 komplett gelesen; NUR
  0x65/0x66 + 0x61/0x62 tragen 12-B-Textursaetze. -str 260 (898 388 Setups): dieselben
  3 Typen = 112,5 % => ~11 % KONSUMLUECKE (szenenabhaengig: 0 % frueh, 8,7 % bei -str 220),
  Ursache HYPOTHESIS (Culling/untexturiert/nicht recycelte Bloecke); normierte Emission
  62,4/28,1/9,6/0,3 %. A82C schreibt in die STAGING-Flaeche (RAM-Dump: 48 Records in den
  recycelten Bloecken = 48 A82C-Aufrufe des Frames). SHARC-Adressierung: regnum =
  Wort-Offset & 0xFF (MAME BIT(offset,0,8)) => 0x24802C0/2C1/2C3 = textureMode/tLOD/
  texBaseAddr; SHARC-PC am Register-Write attributiert KEINE Opcodes (~60 Stellen,
  Top = Kopien EINES Helfers mit Werten aus DM(I2,M1)). OFFEN: 11-%-Luecke,
  Wertequelle der Draw-getriebenen Setups (DSP/CG-Bank 0x3600000-0x37fffff),
  [SDA(0x180)] feldweise, 146 Bit12=0-Setups, 19 textureMode-Werte ohne PPC-Pendant.
  Werkzeuge: scripts/m31d_ledger.txt, m31c_stage_dump.txt, m31c_reconstruct.py,
  m31e_opcode_attr.py, m31b_correlate2.py; TEMP-Flag LOG_TEXREGS wieder false
  (Logzeile hat jetzt zusaetzlich pc=%08X).
- BATCH 25 = L4 0x8004xxxx GEZAEHLT (2026-09-17, analysis/l4-texture-path-2026-09-17.md):
  METHODE (wiederverwendbar!): EIN Lauf mit 250 bpset (ein BP je Ghidra-Funktionseintritt,
  Action `logerror "Q4 %08X %08X\n",pc,lr ; g`) -> Python zaehlt Zeilen je Adresse,
  `lr-4` = Aufrufstelle. MAME hat KEIN Breakpoint-Limit (breakpoint_set alloziert
  dynamisch); 337k Treffer = 66 s Wall + 685 MB Log (`-log` loggt zusaetzlich jeden
  [:konppc]-Shared-RAM-Zugriff, ~10 MB/s Emu). Werkzeuge: scripts/l4_census.py,
  l4_counts.py, l4_diff_list.py, l4_cold_clusters.py, l4_hot_profile.py,
  l4_descr_probe.py, l4_disasm.py, l4_track_parse.py, l4_count_run.ps1.
  Sanity: Per-Frame-Fn = exakt 101 Eintritte (Fenster -str 166); 80049C48 b = 10850
  (deckt Batch 20); 8004992C = 0 in beiden Fenstern.
  ZAHLEN: 239 Bucket-F-Fn in 0x8004xxxx -> 75 heiss / 8 warm / 156 kalt
  (250 Fenster-Fn: 82/8/160; 160 in BEIDEN Fenstern kalt, nur 5 kippen).
  60 von 82 heissen ohne jede Doku-Nennung; 30 gelesen. 91 der 160 Kalten sind
  DRC-observed ("verifiziert, aber ungenutzt" quantifiziert).
  BEFUNDE: (a) Region = AKTOR-/MODELL-UPDATE + Render-State-Bruecke, NICHT Textur:
  0 MMIO-Refs in ALLEN 250 Fn, kein Callee aus Textur-/Transportpfad
  (0x8008F1A0, 80016DB0/AA0, 80016E34, 8001A968, 8001B108) -> Texturpfad liegt
  woanders (Kandidat 0x8009EAxx/0x8009FDxx-Veneers + Content-Loader).
  (b) FUN_8004E17C (141189, heisseste) = Winkel-Lerp mit Vollkreis-Korrektur
  (Gewicht/16, 0x1000=90 grd Q14), 3x je Kettenknoten aus FUN_8004E068.
  (c) FUN_8004DF30 = Animationsmotor: Records 24 B aus SDA(0x30C): +4 Gewicht 0..16
  (live 11 = mitten im Crossfade), +6 Schritt, +8/+A Keyframe-Basen, +C = 27 Knoten,
  +A-+8 = 108 = 27*4 -> CROSSFADE zweier 27-Knoten-Saetze (deckt Batch 22 exakt),
  Keyframe = 4 s16 {Vorschub,a1,a2,a3} je Knoten (SDA(0x310)).
  Animationstabellen in RAM: SDA(0x30C)=0x80100200, SDA(0x310)=0x80100380.
  (d) Heissester TREIBER = Ghidra-GAP-Fn 0x8004A28C (1244 B/311 Insn) ueber
  Deskriptor-Slot 0x800AD60C; Zwilling 0x800AD060 -> 0x8004A288 = nur `blr`
  (Default = kein Update). "0 Caller" kann also FEHLENDE GHIDRA-FUNKTION heissen.
  Darin: `bl 0x8000005c` mit r11=[obj+0x164]/[obj+0x168] = Objekt-Methoden-Dispatch.
  (e) ColorPath: FUN_80047014 (State-Wort-Diff gegen SDA(0x2A0)) -> 80044500
  (Wort -> Pending-Record aus SDA(0x288)) + 8004449C/44440/443EC -> A-Emitter
  80017714/80017C5C; getrieben von FUN_800807F4 (0x8008xxxx! = 80080814 = 8008090C,
  EINE Fn): 64 Slots Stride 0x34C, Layer-Maske, 16x/Frame -> Batch-24-Label
  "0x8008xxxx = Menue/HUD" ist ZU ENG.
  (f) 4 heisse Fn mit 0 statischen Callern (8004312C, 80049EB4, 8004B3E8, 8004B5A4),
  alle lr-4 in Gaps. SDA(0x5E0)/SDA(0x5E4) = 0x8008AD98/0x80049DA0 = Sprungtabelle
  + Basis (Batch-23-Mechanik bestaetigt).
  NEUE REGELN: (81) BP-Zaehlung skaliert; (82) Zaehlung sieht nur EINTRITTE ->
  jedes heisse lr-4 auf "Funktions-Start?" pruefen; (83) mmio_refs==[] ueber eine
  ganze Region = hartes Negativ-Kriterium; (84) bl 0x8000005c + r11 = Methoden-
  Dispatch; (85) read_memory-Chunks 0x400 lesen den Deskriptor-Block (327 Records);
  (86) Animationszustands-Record (24 B) + Crossfade-Struktur.
- BATCH 26 = AKTOR-UPDATE-WURZEL + OBJEKT-METHODEN-DISPATCH (2026-09-17,
  analysis/l4-actor-update-root-2026-09-17.md): 1 MAME-Lauf (7,7 s/101 Frames),
  2 create_function (FUN_8004a28c 1248 B, FUN_800705a0 224 B), ~11 Ghidra-Calls.
  (a) FUN_8004A28C = generischer Aktor-Update-Handler: Flags +0x14c/+0x14 ->
  Methoden-Slot A (+0x164) -> Sub-Gates -> Zitterbewegung (+0x1d0 Zaehler, 3x LCG
  80015294, Basis +0x1c4/1c8/1cc) -> PHASENMASCHINE +0x16c 0..4 (0=8004B650,
  1=8004B5A4, 2=8004B3E8, 3=80049EB4, 4=80049DA0; Rueckgabe 1 => Reset) ->
  Slot B (+0x168) -> Tail (8003aecc n=7/0xC, 8004FAA0, 80049C48, 800498EC,
  8003AFFC/8003AFA0, 800201F8 90 grd fuer Knoten 0x13/0x14). Live: 1010 Eintritte
  /101 Frames = 10 Aktoren x 1; Phasen 0/1/2/3 = 224/374/208/204, Phase 4 NIE.
  Erklaert alle lr-4-Gaps aus Batch 25 (8004A4B4/A4CC/A4E4/A5A4/A5B0).
  (b) FUN_8000005c (5 Instn) = `lwz r0,0(r11)` / `stw r2,0x14(r1)` (AUFRUFER-Frame!)
  / `mtspr CTR,r0` / `lwz r2,4(r11)` / `bctr` = DESKRIPTOR-FERNGRIFF {entry, r2}.
  Erklaert JEDES `lwz r2,0x14(r1)` nach so einem bl. Live: [obj+0x164] =
  0x800AD138 -> {0x800705A0, 0x800ADA5C} bei 5 der 10 Aktoren, sonst Default
  0x800AD060 -> {0x8004A288 (=blr), 0x800ADA5C}; r2-Feld = exakt r2.
  => Die 327-Record-Tabelle (Batch 24) = FERNGRIFF-TABELLE, Feld +4 = SDA-Basis;
  Objekte zeigen +0x164/+0x168 DIREKT auf Records => Objekt-Methoden-Dispatch
  CONFIRMED (Flag-Bit3 korreliert 505/505); Slot B (Bit4) live nie ausgeloest.
  (c) FUN_80080528/80080668 = AKTOR -> RECORD: Aufrufer FUN_800807F4 (64 Slots,
  Layer-Maske) ruft je Slot 80047014 + Aktor-Draw, Modus = (RenderState>>10)&3,
  z = slot+0x68; Sub-Teil-Kette (Stride 0x10, Kopf obj+0x30+idx*0x10, Kette +0xC,
  +1 Laenge/+2 ID/+8 Block) -> 0x65/0x66 (8001A82C, count=len/24, 0x14261000-Patch)
  + 0x5C (8001A9A8) bzw. 80021308 (Matrix*Vektor + 8001758C = 0x56-Record) ->
  80017674(z). STAGING-CURSOR = [frame+0x18] CONFIRMED (beide Emitter).
  (d) FUN_800705A0 (Gap, nur per Deskriptor erreichbar) = Ereignis-/Zustandsarmer,
  ruft FUN_8004C438(obj,4,3) => der Batch-24-"Modusautomat" IST verdrahtet;
  "kalt" = Gate (Bit13(+0x14) & +0x27f==0) nie erfuellt (Korrektur zu Batch 25 2.2).
  (e) Rest-Count: 60 heiss-und-undokumentiert - 29 gelesen = 31 offen, davon 3 mit
  duenner Rolle => 28 ohne Rolle, alle in der 1-2x/Frame-Record-Produzenten-Klasse
  (Caller-Hubs 8003D718/8003D974/8003DA68/8003CF0C/8003E8E0) => als FAMILIE mit
  einem Template abarbeitbar, kein neuer Suchpfad noetig.
  NEUE REGELN: (87) Deskriptor-Ferngriff + r2-Reload; (88) Deskriptor = {entry,r2,0}
  (Stride 0xC), +4 immer 0x800ADA5C; (89) Gap-Fn sind per bpset MESSBAR, aber erst
  nach create_function im Inventar -> Zaehlung wiederholen; (90) "kalt" != "unbenutzt"
  (Gate nie erfuellt vs. Pfad inaktiv trennen); (91) Staging-Cursor = [frame+0x18].
- BATCH 27 = L4-FAMILIE ABGESCHLOSSEN (2026-09-17,
  analysis/l4-family-batch27-2026-09-17.md): die 28 heiss-und-undokumentierten
  L4-Fn sind KEINE Record-Produzenten der Bau-Spanne, sondern 3 disjunkte
  Klassen: H(16) HUD-/Overlay-DIREKTEMITTER unter 8003D718 (=18950(1)=LIVE),
  W(7) Wert-/Zustandsautomaten unter 8003CF0C (kein Fenster) + 80046D38
  (einziger in einer Bau-Klammer), D(5) Meldungs-Overlay-SKRIPTMASCHINE unter
  8004312C <- Gap 0x800845AC (Zustandsblock [SDA(0x280)] = Batch-19-Block zu
  80043388; 8004226C = 8-fach-, 80042874 = 6-fach-Dispatch; 80042E1C =
  Byte-Skript-Interpreter). L4-HEISS (82 Fn) ist damit ZU; L4-gesamt nicht
  (156 kalt + Texturpfad unangetastet). Werkzeuge: scripts/l4_family_triage.py
  (0 Ghidra: 82 heiss / 60 ohne Doku / 29 gelesen / 3 duenn / 28 ohne Rolle),
  scripts/l4_family_dump.py (HTTP-Batchdump).
  KERNREGELN: (92) state+4 = EMITTER-MODUS, nicht Freigabe: Live(!=0) =>
  80017714/80017BBC/80017C5C/80017F58/80017DF0 schreiben JE KANAL einen Record
  direkt in [frame+0x18]; Bau(==0) => dieselben Fn schreiben NICHTS, nur Dedupe
  (+0xEC33/+0xEC4A4C/+0xEC54/+0xEA94+idx*0x34) + Index-Bits in state+0x10,
  Sammelrecord von 80017674/8001758c. (93) relative Sprungtabellen haben ZWEI
  SDA-Zellen: Tabellenzelle (Offset-Array im Image) + BASISZELLE, die auf CODE
  zeigt (SDA(0x274)=0x80088220 +0x344/+0x364 mit Basis SDA(0x278)=0x80042130;
  SDA(0x284)+0x93C mit Basis SDA(0x634)=0x800435B8) => d@(r2+off) liefert eine
  Funktionsadresse. (94) Sprungtabelle auf ASCII pruefen (0x49424D20 "IBM ",
  0x536B6970 "Skip by " => Tabelle kuerzer als das Gate). (95) SDA-Aufloesung:
  EIN bpset mit EINER Action = 32 Zellen/Lauf (1,7 s). (96) HUD-Labels/-Layout
  sind statische IMAGE-Daten: SDA(0x284)=0x800885A8 (Textbausteine, u.a.
  "%02u'%02u\"%02u" = mm'ss", "%08u", "TIME EXTEND", "WAIT", "NOW RELOADING"),
  SDA(0x288)=0x8009D6C8 (HUD-Layout: Pointerarrays, s16-Versatztabelle +0x10,
  Positionen, 8-Stufen-Farbrampe +0x68). (97) ERST die Hub-Koerper lesen, dann
  die Familie. (98) FUN_8004785C(&Dauer,&t) = Q8-Rampenschritt (t += 0x100/Dauer);
  FUN_8000F1E0 = Char-Pool-Zeilenmarkierung (KEIN Sound-Event).
  ANIMATIONSKETTE GESCHLOSSEN: 8004FC60 (Objekttyp-Selektor SDA(0x304)) ->
  8004F5A4 (Slot, 16x0x18) / 8004F3C8 (Keyframes aus Knotenkette) ->
  SDA(0x30C)=0x80100200 / SDA(0x310)=0x80100380 -> 8004DF30 (Motor) ->
  8004E068/8004E17C (Winkel-Lerp) -> Knoten +2/+4 -> 80049AFC.
  80044440 = ColorPath-"nur bei Aenderung"-Bruecke (SDA(0x29C)/SDA(0x2A0) =
  Parallelstrukturen +0x20). TEXTUR-ANSATZPUNKT (nur vermerkt):
  [SDA(0x104)] = 0x8008F1A0 (tex_tbl) wird von 80017714 (+p3*4) und
  80017F58 (+0x24+p*2) als Modus-/Attributtabelle gelesen.
  KORREKTUR Batch 28: 0x8008F1A0 ist eine 0x28-B-State-Encoding-Tabelle
  (alphaMode 0x09/0x0E, fbzMode 3/7, fogMode 0/1; nur 4 Leser 80017714/
  80017958/80017D80/80017F58, schreibfrei) = KEIN Texturpfad; 0x8009EAxx/
  0x8009FDxx = Eintraege #22/#75 der Slot-Tabelle SDA(0x300)=0x8009E218
  (Stride 0x5C); "Content-Loader" fuer 0x80100200/0x80100380 existiert nicht
  (Anim-Tabellen, Autoren 8004F5A4/8004F3C8/8004E068).
- BATCH 29 = TEXTURPFAD GEFUNDEN (2026-09-17, analysis/texpath-batch29-2026-09-17.md):
  (a) FUN_8001A82C (0x65/0x66) liest Quell-Raster **12 Byte** (nicht 24; der
  Emitter schreitet 0x18 und nimmt jeden 2. Record = raw-Zwilling):
  +0x00 u32 textureMode (Bits 0-11 Format/Filter; Bit12 = "fertig"),
  +0x04 u16 (tLOD hi, &0xFFF7), +0x06 s16 tLOD, +0x08 u32 Texturbasis
  (+0x40000 wenn Bit12 clear); Patch (mode & 0xC0000FFF)|0x14261000 = exakt
  die tc/tca-Combine-Bits des dokumentierten 0x14261A87; **count = len/12**
  (Korrektur zu "len/24"); Kopf {0x65|0x66, id, count}, id>=0x200 => 0x66.
  Live quick.sta: 3939 Aufrufe/101 Frames (39/Frame, lr immer 0x800805EC =
  FUN_80080528), len immer 12, IDs 0x49E-0x4A7, 20 Bloecke Stride 0x50 in
  0x80394240-0x80395300 (2 Inhalte), emittiert textureMode 0x14261AC7,
  tLOD 0x104, Basis 0x20067080.
  (b) HERKUNFT CONFIRMED: Records = gestreamte Modell-Asset-Daten.
  FUN_8002946C (Szenen-Ladeschritt, [SDA(0x180)]+idx*0x10-Eintrag) ->
  FUN_80029958 (residente RAM-Adresse oder 0x803C1000) / FUN_800299F4 ->
  FUN_80029D0C (Zielcursor [SDA(0x18C)], Pool endet 0x803A0000 = Knotenpool-
  Basis) -> Queue FUN_8002B394 (Ring 16, ctx=[SDA(0x9C)], {+0x4004 src,
  +0x4008 dst}) -> Frame-Tick FUN_80008B9C -> FUN_8002B360 -> FUN_8002B13C
  (src = desc+0xC, size = desc+8) -> **FUN_8002B20C = LZSS** (4-KB-Fenster
  &0xFFF, 0xff00-Escape, len>=3, max 0x100 B/Aufruf, Pruefsumme +0x408C).
  Beweis: Schreib-WP auf 0x80390000 (0x10000) = 27 014 Treffer im State d.sta,
  Writer-PC 0x8002B320 (LZSS-Ausgabestelle); Relocator-Gap 0x80029A50 fuellt
  SDA(0x1B4)-Eintraege (+8 = Blockzeiger, +0 = id) und addiert
  (([SDA(0x180)]+idx*0x10 +8)>>3) auf das +0x04-Dword jeden Records ab
  Record 1. FUN_800633A0 (2. Emitter-Aufrufer, Modellpfad, in quick.sta kalt)
  liest rec=[SDA(0x1B4)]+idx*0x10: id=rec[0], B=rec[2], count=s16(B+4),
  C=u32(B), Block=B+8+sub*24*C, len=12*C.
  (c) ROM-QUELLE: Ladeliste ROM-Offset 0x1F6000 (Alias 0xFFFF6000), Kopf
  {+0 Listenoffset 0xC, +4 Verzeichnisoffset 0x400}, 12-B-Eintraege ab
  0x1F600C {Name-Offset, Flag, Ziel}: Flag 0 = Asset resident in RAM
  0x80180000-0x80246000 (Namen system/weapons(2)/effect/game/Ficon/zako01/
  car(1,2)/heri1,2/boss/tero/boss4/baseman/last/player/HGIRLS1-4/citizen...),
  Flag 1 = LZ-Block bei ROM 0xFF18xxxx. Demo-Assets: 0x800299F4 laedt nach
  0x803C1000 (0x2F000).
  (d) ZAEHLLAUF (Auftragspunkt 3): **im quick.sta-Szenario ist der Quellpfad
  KOMPLETT KALT** (0 Treffer fuer alle 10 Kettenziele, 0 Schreibzugriffe im
  Pool) bei 39 Emitter-Aufrufen/Frame; im State d.sta heiss (LZSS 27 014
  Writes, FUN_80062B1C 1x, FUN_80062430 1x, Emitter 96 288).
  (e) Negativ: Recordwerte weder im Image (search_byte_patterns) noch im
  rekonstruierten Daten-ROM noch im rohen 830d01.27p => erst durch
  Dekompression+Relokation entstanden.
  OFFEN: SHARC-Konsum der 0x65/0x66-Records (letzter Abschnitt), Bedeutung
  +0x40000/Bit12 (raw vs cooked), [SDA(0x180)]-Feld +8 = Texturbasis,
  ROM-Ladeliste komplett auslesen + Assets offline dekomprimieren.

## DEKODIER-REGELN (R154/R155, Batch 93 - gegen Ghidra + Live-Dump geprueft)
- **R154 `rlwinm`-Maske = PPC-Bits MB..ME** (Bit 0 = MSB, ueber das Wortende
  laufend). "Ein Bit loeschen" = `rlwinm rA,rS,0,32-k,30-k` loescht **LSB-Bit k**
  (Formel in Batch 94 korrigiert, s. R159):
  `(0x1F,0x1D)`->0x2, `(0x1E,0x1C)`->0x4, `(0x1D,0x1B)`->0x8, `(0x1B,0x19)`->0x20,
  `(0x1B,0x17)`->0xE0, `(0x10,0x0E)`->0x10000. Rechtsbuendiges Lesen verschiebt
  JEDEN Bittest um eins (Fehler in Batch 92 an `FUN_80084038`).
- **R155 Zweigrichtung an den Mnemonics festmachen**: `bc 12,BI` = Zweig bei
  GESETZTEM CR-Bit (`beq` = `bc 12,2`), `bc 4,BI` = bei genulltem (`bne`).
  Ghidra druckt es direkt (z.B. `4182002c beq`); R143 formulierte es umgekehrt.
  Gegenprobe: `addic.` + `bc 4,0/4,1`-Zaehlschleifen muessen enden (1-2 Runden).
- **mtcrf 0x1,rS** -> CR7 := **niedriges** Nibble; CR7.SO = rS-Bit 0, CR7.LT =
  Bit 3. **mtcrf 0x80** -> CR0 := niedriges Nibble (CR0.SO = Bit 0).
- Der `mtcrf`-Trick der Zustandsautomaten: `rlwinm rX,rS,SH,MB,ME` + `mtcrf 0x1`
  testet das Nibble ueber CR7-Bits (LT = hoechstes, SO = niedrigstes).

## DEKODIER-REGELN (R159-R164, Batch 94 - gegen Ghidra + Live-Dump geprueft)
- **R159 (KORREKTUR der R154-FORMEL):** "ein Bit loeschen" ist
  `rlwinm rA,rS,0,32-k,30-k` (nicht `...,k-2`) und loescht LSB-Bit k.
  Beispiele: `(0x1F,0x1D)`->0x2, `(0x1E,0x1C)`->0x4, `(0x1D,0x1B)`->0x8,
  `(0x1B,0x19)`->0x20, `(0x1B,0x17)`->0xE0, `(0x10,0x0E)`->0x10000,
  `(0x3,0x1)`->0x20000000, `(0x9,0x7)`->0x800000, `(0x12,0x10)`->0x4000.
- **R160 (Nibble-Test):** `rlwinm rX,rS,SH,0x1C,0x1F` = `(rS >> (32-SH)) & 0xF`;
  `bc ..,28` (CR7.LT) testet dann **Wortbit `35-SH`** (SH=20 -> Bit 15,
  SH=12 -> Bit 23, SH=28 -> Bit 7), `bc ..,31` (SO) testet Wortbit `32-SH`.
  Wer das Nibble als Bitnummer liest, testet ein Nachbarbit.
- **R161:** ein Zweig, der sein Ergebnis NICHT setzt, gibt das **eingehende r3**
  zurueck (Registerrest) - gemessene Eingabe, im Port explizit als Parameter
  bauen (FUN_8003EE2C, Zaehler >= 2).
- **R162:** `0x60000001` ist `ori r0,r0,1` und KEIN `nop` (`0x60000000`) - der
  Projektdecoder druckt beide als "nop" (2. Fall nach P121b; Stelle 0x8003D0E0).
- **R163:** der CR-Mitschrieb in `scripts/m88_mode.annotate` ist SEQUENZIELL und
  nennt ueber Spruenge hinweg die falsche CR-Quelle (0x8003D018) - jeden `bc`
  gegen die erreichbaren Pfade pruefen.
- **R164:** eine Sprungtafel gehoert der Funktion, die sie liest; die Basis
  `[SDA(0x26C)] = 0x8003EAA0` ist der Anfang der FUNKTIONSFAMILIE (Tafeln
  `[SDA(0x268)]+0x854` = FUN_8003EB44, `+0x870` = FUN_80041F54).
- **R147 verscharft:** wer eine ueber Haken gefahrene Funktion baut, stellt im
  SELBEN Batch die Anker um (sonst zementiert die Regression die Ersatzregel).

## BATCH 95 (2026-09-21, Missionsebene) - Regeln
- **R165** eine Tafel kann ueber `Zelle + Versatz` erreichbar sein (Missionstafel
  0x800A03C8 = [SDA(0x398)]+0x20; eine Wortsuche findet NICHTS und beweist nichts).
- **R166** den Index eines Zustandshelfers bis zur DEFINITION verfolgen: `li r4,0`
  bei 0x80041D04 laeuft 9 Instruktionen spaeter UND ueber einen Zweig in
  `bl state_inc` (0x80041E0C) - ein Zensus "zwei Instruktionen davor" oder
  "nur `stb ...,0`" findet den Schreiber von Byte 0 == 1 nicht.
- **R167** beim Bauen verschieben sich Zahl UND Position der Mitschriebzeilen;
  Reihenfolgeanker muessen Position und Gesamtzahl pruefen.
- **R168** `mtcrf 0x1` + `bc ..,31/30/29/28` = Argument-Bit 0/1/2/3 - **2 und 3
  tragen beide CR7.EQ**; wer "Argument == 2" mit EQ gleichsetzt, uebersieht den
  Wertesatz des Aufrufers 3.
- **R169** ein ungepruefter Index ist eine gemessene Eigenschaft: nachbilden und
  im Port gezaehlt ablehnen (Nullvektor).
- **R164 verschaerft** Tafel und BASIS koennen in fremden Funktionskoerpern der
  Familie liegen ([SDA(0x580)] = 0x800532C8 ist 16 B gross).
- Details: /memories/repo/missionsebene.md, analysis/port-batch95-missionsebene-2026-09-21.md.

## BATCH 94 (2026-09-21, Ergebnisweg) - Kernfakten
- Kette (je genau 1 Rufer): Schleifenzustand 5 -> FUN_8003CF0C -> FUN_80041E6C
  -> FUN_8003EAA0 -> FUN_8003EB44. Gebaut: FUN_8003CF0C (Abbau), FUN_8003E748
  (Stufenwert), FUN_8003E840, FUN_80041E28/38 (s16-Tafel), FUN_80041F54
  (Phasensetzer) - Inhalt in `port/game_result.*`, `port::result`.
- Zellen: Bildschirmblock [SDA(0x260)] = 0x800FF948 (200 B), s16-Tafel
  [SDA(0x264)] = 0x800FFA10 (folgt unmittelbar), Tafeln [SDA(0x268)] = 0x80087930,
  Basis [SDA(0x26C)] = 0x8003EAA0, Arbeitsobjekt [SDA(0x270)],
  Stufenwerttafel [SDA(0x6D4)] = 0x800AB490 (6 Byte je Zeile ab +0x20).
- Abbau-Rueckgabe = `Flags & 4` des Objektfelds; Tore: Bit 23, Bit 12, Bit 14
  (Ergebnisweg); Bit 3 -> Bit 29 gespiegelt; Schluss immer FUN_8003E8E0.
- Offen: Phasenwahl (FUN_8005471C(5)/FUN_8005A5A4(1), Missionsinhalte 0x8005xxxx),
  zweiter Verteiler FUN_80041E48 (1 -> FUN_8003FBF4, 5 -> FUN_8003EFAC),
  Byte 0 == 1 (Rumpfeinstieg) wird von keiner Stelle geschrieben.
- Stand: Regression 32 Frames + 131 Anker, 0 Fehler; Ghidra 2085 unveraendert.

