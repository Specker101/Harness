# PPC Native PoC — Status und Fakten (Silent Scope)

## Status (2026-08-31, Phase C3): 17 Frames + 1 Injektions-Frame byte-genau
- PoC: `poc/ppc_native/main.cpp` (g++ -O2 -std=c++20, UCRT64); Python-Modell
  `scripts/ppc_poc_model.py` bit-identisch; Doku §9+§10 in `analysis/ppc-native-poc.md`.
- Frames: 13 aus scope_session04 (0,228,237,267,301,548,850,1298,1300,1749,1772,1892,1934)
  + 4 Boot-Frames ohne State-Load (Boot 0-3, Demo count 30→217). Je nur h0-Artefakt.
- C2: Commit {1,…} = FUN_8001b658(p1,p2) via FUN_80017fe8 (state+4!=0, Gruppe+0x18).
  fogTable 2× je Frame (Grp2+Grp6 f24=1).
- C3 gezielte Jagd: s4=1 und bank=0 in ALLEN 2055 Frames (1977 Session + 78 Boot);
  Dirty-Queues q1/q2/q3 immer leer; mt-Übergänge 3↔6 ohne neue Pfade.
- INJEKTION (einziger Weg): Hook injiziert am Trigger (Walker drained erst bei
  0x80016a5c > Trigger 0x80016A0C) → echter Spielecode produziert echten Output.
  Queue 3 (FUN_80016ad8, 0x4C) CONFIRMED byte-exakt (POC_INJECT_Q3; 3 Ghidra-Fallen:
  beq@16b58=CR0 count==0, bgt cr6, rlwimi 8,31 → r7=(rotl(idx,23)|0x80000000&FF000000)|(v&FFFFFF)).
  Queue 1 (FUN_8001b108, 0x61/0x62) OFFEN: Output erzeugt ({61,sel,X=count}+Daten),
  Carry-Ketten-Math teilgeloest; Model warnt bei nicht-leerer Queue, emittiert nicht.
  Queue 2, deferred, bank1, 0x58, FUN_8001832c: offen/dokumentiert (s. §10.4).

## Laufzeit-Konstanten (CONFIRMED, Billboard-Frame)
- r2 = 0x800ADA5C (reloziert!); frame-struct = [[r2+4]] = 0x800AE310;
  state = *[r2+0xF8] = 0x800B3C28; tex_tbl = [r2+0x104] = 0x8008F1A0.
- Trigger (0x0002-Write, PC 0x80016A0C): r3=0x803FF760 (Record-Array),
  r4=117 (count), Records = Pointer auf 0x10-Bytes {word0, word1, len(u16,Bytes), blk}.

## MAME-Semantik (CONFIRMED, Fallen!)
- rlwinm-Maske: (0xFFFFFFFF>>MB)&(0xFFFFFFFF<<(31-ME)) bei MB<=ME.
- mtcrf 0x1,r3 → CR7 = r3 & 0xF (SO=bit0, EQ=bit1, GT=bit2, LT=bit3).
- Ghidra druckt bdnz (BO=0x19) fälschlich als "bso cr7".
- FUN_8001b5cc = ctz(p7) → {5, ctz}; frame+0x20 = ctz.
- log-PCs +4..+8 gegen Store.

## Workflow (reproduzierbar, Stand C2)
1. konppc.cpp (Workspace mame/mame/src/...) → Copy-Item nach C:\Users\Arcade\mamebuild.
2. Build: MSYSTEM=UCRT64 (env erben!); PATH += ucrt64/bin; make -j16 SUBTARGET=sscope NOWERROR=1.
3. Replay (CWD capture\): sscope.exe sscope -rompath <roms> -state quick -video none
   -nothrottle -log -playback scope_session04 -exit_after_playback.
   Hook TEMP-PPC-POC-MULTI: POC_TARGET=n → dump ppc_poc_input_<n>.bin + Stream-Log
   (LOGSHARED-Gate), Exit bei n+1; ohne POC_TARGET → Survey (POC-SURVEY je Frame).
4. Referenz: scripts/ppc_poc_refstream.py capture/error.log capture/poc_ref_stream_<n>.txt.
5. PoC: poc/ppc_native/ppc_poc.exe <dump> <referenz> (-o schreibt Modell-Stream).
6. Divergenz: scripts/ppc_poc_aligndiff.py / ppc_poc_window.py (PC-Attribution).
- Hook-Blöcke mit "TEMP-PPC-POC-*" / "Revert:"-Markern. ppc_poc.exe braucht
  ucrt64/bin im PATH (DLLs). Alle 5 Frame-Runs: scripts/ppc_poc_frame_run.ps1 -Idx a,b,...
- 1977 valide Trigger in scope_session04; idx→Recording-Frame: pb ≈ idx*4.03+3.
- NOTE: "Total playback frames: 7" im Dump-Modus = Teardown-Statistik nach
  schedule_exit, KEIN Desync (Survey lief 7973 Frames sauber).
- C3: Boot-Survey ohne -state via -seconds_to_run 60; Injektion via
  POC_INJECT_Q3=1 / POC_INJECT_Q1=1 (+POC_TARGET=n); Pfad-Analyse:
  scripts/ppc_poc_paths.py. Survey-Felder: s4/bank/f18/f24/q1/q2/q3/Opcode-Scan.

## Batch 62: Referenzdaten-Inventur (WICHTIG, gemessen)
- Verifizierbar sind **16 Läufe**: 13 Session-Frames (0000/0228/0237/0267/0301/0548/0850/1298/
  1300/1749/1772/1892/1934) + Boot-Frame 0 sauber + Boot-Frame 0 mit Q1-Injektion
  (`_m62_boot0_clean.bin`) + **Q3-Injektions-Frame (`_m62_boot0_q3inj.bin`)** — die letzten
  beiden sind rekonstruiert, weil `ppc_poc_input_0.bin` vom späteren Q1-Lauf überschrieben wurde.
  Rekonstruktion: (a) Q1-Kopf = Q1-Tail setzen; (b) Q3-Ring bei `state+0xea28+tail*8` füllen mit
  `{b0=0,b1=0,cnt=2}` + `ptr = rec0.rp` und `head=(tail+1)&3`. Skript: `scripts/port_regression.py`
  (`prepare_derived_dumps`). Beide gegen `poc_ref_stream_0.txt` bzw. `poc_ref_inject_0.txt` = 1 Diff.
- **Boot-Frames 1–3 haben KEINEN Referenzstrom** (`poc_ref_stream_{1,2,3}.txt` fehlen) → nur per
  MAME-Replay nachholbar. Die alte Aussage „17 Frames + 1 Injektion“ war also zu hoch.
- PoC-Kern ist nach `poc/ppc_native/ppc_core.h` gezogen (Split, Logik unverändert); die CLI bleibt.
  Beide Programme laufen über `scripts/port_regression.py` → siehe `/memories/repo/port-skeleton.md`.

## Offene Punkte
- 2x0x3A-Paket-Semantik SHARC-seitig (HYPOTHESIS).
- FUN_800180b4 bank==1 Scope-Offset-Zweig nur teilweise portiert (inaktiv im Frame).
- Phase D: Interface-Spezifikation (Stream-Konsument-Sicht).
