# Decoder-Regeln (R-Nummern) — Silent Scope Decomp

Kurz-Nachschlagewerk der Regeln, die KEIN Werkzeug automatisch prüft.
Volltext: `analysis/port-batch1xx-*.md`, `analysis/port-implementation-log.md`.

## R361-R363 + B150/B149 (Batch 150, 2026-09-24) - M0-NAEHTE VERDRAHTET
- **R361 (R324-Klasse, eigener Fehler):** SDA-Zellen, die der Port als **BASEN**
  benutzt (`r = *(SDA x)`, Schreibziel `r + stride*i`), brauchen **getrennte,
  ausreichend grosse** Bereiche. Meine erste Fassung legte `base28`/`base92`/
  `base120` (`0x428`/`0x42C`/`0x430`) und den Satz `0x434` 0x40 B auseinander;
  die 28-B-Zeilen (`cell418` 0..26) liefen ueber die 92-B-Basis und
  ueberschrieben `rec+0x0C` (= `n2` der Naht `8005D3B0`) -> Anker meldete
  "Rahmenpuffer-Saetze 0" bei sechs geschriebenen Halbworten.
- **R362:** in der Ruestung eines Tafel-Verteilers muessen **Tabellenzeile UND
  Abschnitt** gleich sein - der Verteiler liest die Zeile ueber den Abschnitt
  (`t2 = base + *(tab + kTab0Run + 4*idx)`). Zeile 4 bei Abschnitt 0 = Naht
  laeuft gar nicht (Hakenstellen 0).
- **R363 (IN-PLACE):** eine gebaute Kette, die ihren entpackten Satz **in place**
  verschiebt (vier Kopfworte + jeder != 0 gesetzte Tafeleintrag `+0x803C0000`,
  Rohworte `8005c19c..8005c224`), darf NICHT gegen die reine
  Dekompressionsreferenz gemessen werden: reine Dekompression **separat**
  bytegenau gegen `m33_lzss.py`, Mutationsspur **regelweise** (jede Abweichung
  genau `+0x803C0000`).
- **R360-Ergaenzung:** die Bilanz ist nur idempotent, wenn der Vorgaenger aus
  der **MENGE** der Schnappschuesse kommt (`pick_prev`), nicht aus `last`.
- **R229/R340 (wieder):** R216 B **91 -> 85** - sechs Neben-Funde
  (`4BFFF45D`/`4BFFF44D`/`4BFFE419`/`8005AEC4`/`8005AED4`/`80055414`, alle
  0 B, keine Funktionen) fallen weg, weil ihr Belegzeilen-Umfeld den Marker
  `1:1|Rohinstruktionen` verloren hat. Zahl haengt am MUSTER.
- **B150 - VERDRAHTET:** `FlowHooks::lzss` (R193 additiv) + `Runtime::owner` +
  `lzss::ensure()` (EINMAL je Abbild, R148), Anschluss im Spielaufbau
  (`service_screens.cpp` `gameflow_hooks`). Die zwei Naehte
  `0x8005AEC4`/`0x8005AED4` in `mission0_step` fahren `wire_a320()` ->
  `a320_latch(ram, slot, h.lzss->frame, &aux, nullptr)` (Fahne Bit 8 +
  `cc94_setup` -> `c168_step` -> `aebc_unpack` -> `c408_step`) und zaehlen
  `StepStats::wired`; ohne Wirt der gezaehlte Haken (R215). Argumente:
  `8005a5b8 addi r26,r3,0`, keine r3-Schreibstelle auf dem Pfad, hinter jedem
  Ruf `387a0000`; Rahmenpuffer `lzss::kFrameBuf` = `0x803E0E00`.
  **Validierung:** reine Dekompression BYTEGENAU vs m33 (`stt` idx 11, 668 B,
  FNV `A7683275`, Summe `0000525C`), Kettenlauf (Haken 0/0, Kopf gefahren 1/1,
  wired 1/1, Rahmenpuffer 6x `FFFF`), Mutation 10 Woerter genau `+803C0000`,
  beide Naehte identisch `D185ABAD`. `0x80055414` bleibt GEZAEHLT (R280).
  Waechter (233) **53/53**; preflight before+after SAUBER (R207 **601**
  (29/0/0), check **601/10726/0**, R216 **254-85-86-680-129**),
  Regression **32 + 266 / 0**, `m145_expectdiff` 0, `m144_check` **46/46**;
  Modi 79, `voter_leaves2` unveraendert 53 Koepfe / 2146 Worte / 8584 B.
- **TEIL 1 B150:** Bilanz idempotent (2x `--batch 150` byteidentisch);
  `m60_inventar` schliesst `*bilanz*` im ERZEUGER aus (**87 -> 86** Dateien);
  Log-Ueberschrift geprueft (kein Duplikat: `99f942c` = eine `## 95.`, `82c9743`
  fuegt genau `+## 96.`; die Abschnittsnummern springen aber: `## 90.` = B141,
  `## 91.` = B144); `lzss_host_expect.inc` referenz-unabhaengig (Werte aus
  `m33_lzss.py`, neue R359-Invariante `own < size` => Abbruch, `refs`
  reproduziert die Tafel byteidentisch).
- **Offen:** 251-Insn-Zuschnitt (schaltet `0x80055414` frei, R350),
  `FUN_8005471C`, `0x8003E360` (R280), `FUN_8007D968` (74), R330.

## B148 (Batch 148, 2026-09-24) - DIE 97er-GRUPPE IST GESCHLOSSEN
- **B148 - GEBAUT (44 Insn):** `8005A320` (**16**, Fahne `slot+0x40` Bit 8
  (0x100) via `mtcrf 0x4` + `60000100`=`ori r0,r0,0x100` (R162); Kurzepilog
  `8005A358` bei gesetztem Bit, sonst setzen + `8005CC94`) + `8005382C`
  (**28**, `rlwinm 28,0x1C,0x1F`+`mtcrf 0x1` = CR7.SO 0x10 / EQ 0x20; je Bit
  EIN Ruf, Rueckgabe-Tor loescht das Bit). `voter_leaves2` **53 Koepfe /
  2146 Worte / 8584 B / FNV-1a `37880B20`**; Anker (230) 2/2, (231)
  **159/159**, (232) 54/54, (233) **50/50**; R207 **601** (29/0/0), check
  601/10720/0, nachzuegler **83/35 (3/2)**; R216 A **254** / B 91 / C 86 /
  D 680-129; Regression **32 + 264, 0 Fehler**; **Waehler-Gruppe 97/0**;
  Huelle (A) **97 Knoten 97/0** (R316: schrumpft von 106), (B) **332,
  311/21** (2276 B = 569 Insn).
- **R342-Klasse (wieder, eigener Fall):** die `rlwinm`-Maske im Quelltext ist
  die **MSB-Bitnummer** - `rlwinm rX,rS,0,0x1C,0x1A` loescht **Wertbit 4**
  (nicht Bit 27), `0,0x1B,0x19` loescht **Wertbit 5**; MSB-Bit j = Wertbit
  31-j. Damit ist `8005382C` symmetrisch ("das getestete Bit wird geloescht").
- **R215 (wieder):** ein UNGEBAUTES Rufziel wird gezaehlt und liefert 0 - das
  Rueckgabe-Tor faellt dann NICHT (die Fahnenbits bleiben stehen). Die Faelle
  B/C messen genau das.
- **R280 (wieder):** Haken auf ein GEBAUTES Ziel in einem UNGEZAEHLTEN Rufer
  sind fuer die Sonde unsichtbar -> (233) nennt Hakenstellen + Kopfgefahren +
  die ROM-WORTE (`4BFFF45D`/`4BFFF44D`/`4BFFE419`, `48014F9D`/`480143E1`).
- **R271/R275 (wieder, Entscheidung):** die GEMESSENE Grenze
  `800688D4 -> 80068AB0` (Inventarspanne 147 Insn fasst den verdeckten Kopf
  28 Insn; R356b 588-112=476 B = 119 Insn) wurde **NICHT** eingetragen - sie
  gehoert in den Bau-Batch.
- **R316 (wieder):** die Huelle mit `stop = gebaut` ist NICHT monoton.
- **Naechster Schritt:** der GEMESSENE **251-Insn-Zuschnitt**
  (`8005382C` 28 + `800687EC` 46 + `80067C50` 6 + `800688D4` 119 + verdeckt
  `80068AB0` 28 + `80068B20` 24). Seine Sprungtafel ist aufgeloest:
  `[SDA(0x558)]=0x8008A470` + `0x554`, Codebasis `[SDA(0x55C)]=0x80067C50`;
  die sieben Summen `0xCDC/0xCF8/0xD30/0xD54/0xD9C/0xDCC/0xE14` treffen die
  Rumpfeingaenge `0x8006892C/948/980/9A4/9EC/A1C/A64`. Er braucht EINEN 16-B-
  Scratchplatz (Vorschlag `0x803E0D00`, frei zwischen `kShowBuf` 0x803E0C00
  und 0x803E2000).
- **KEINE neue echte Verdrahtung:** `0x8005AEC4`/`0x8005AED4` (in
  `mission0_step`) brauchen Laufzeit-Rahmenpuffer + LZSS-Wirt;
  `0x80055414` (im `tail` von `mission5_step`) braucht den 251-Insn-Zuschnitt.
  **`FUN_8005471C` ist KEIN gebauter Wirt geworden.**
- **Auflage erfuellt:** B148 hat **kein neues Werkzeug** gebraucht (alles mit
  `m130_ast.py`/`m142_seams.py`/`m112_ast.py`/`m104_built.py`/`m145_*`).

## R358 + B147 (Batch 147, 2026-09-24)
- **R358 — die P100-ARGUMENTprobe wertet kleine negative Immediates NICHT als
  Adresse.** Band `0xFFFF0000..0xFFFFFFFF` (`NEG_IMM_LO` in `m114_pass.py`):
  die R260-Beispiele `0xFFFF8000`/`0xFFFFF67E`/`0xFFFFFC18` und `li r3,-1`
  (Satzindex von `8005C168`) sind Indizes, keine Zeiger. Die
  `P100-Selbstprobe` (`cmd_p100_sel`) hat jetzt VIER Woerter und belegt BEIDE
  Richtungen (negatives Immediate kein Fund, `80AB0000` bleibt einer).
- **R347b-Ergaenzung (gemessen):** einen Rahmenpuffer, den die Kette SELBST
  **schreibt**, bevor sie ihn liest (`800523E0` -> `8005C408` `lhax r0,r17,r10`),
  muss ein Fall NICHT initialisieren - beide Welten lesen ihren eigenen Puffer.
  Die Adresse der neuen Kette ist `0xFFFFFC20` (`8005CC54` -64 B + `8005C168`
  -80 B = 0x90 unter `0xFFFFFCB0`).
- **R342 (wieder, eigener Fall):** ein s16 an einer NICHT 4-aligned Adresse
  (`base+6`) liegt in der NIEDRIGEN Haelfte des Wortes bei `base+4`.
- **B147 — GEBAUT (30 Insn):** `8005CC54` (**16**, `c318_store(Tafel+440)` ->
  `[SDA(0x438)]` **doppelt** dereferenziert -> `c168_step(-1, ...)` ->
  `voter::setup_records`) + `8005CC94` (**14**, Versatz **456**, ohne den
  letzten Ruf). Rueckgabe = REGISTERREST des letzten Rufs (R161).
  `voter_leaves2` **51 Koepfe / 2102 Worte / 8408 B / FNV-1a `0F8A7E01`**;
  Anker (230) 2/2, (231) **154/154**, (232) **54/54**, (233) **48/48**;
  R207 **599** (29/0/0), check 599/10689/0, nachzuegler **80/33 (3/2)**;
  R216 A **252** / B 85 / C 86 / D 678-129; Regression **32 + 263, 0 Fehler**;
  Waehler-Gruppe **95/2** (offen nur `8005382C` 28, `8005A320` 16).
- **R161 im WIRT:** `voter::setup_records` (FUN_80051F64) war `void` und gibt
  jetzt `u32` zurueck (Registersatz Stelle fuer Stelle); der Reihenfolge nach
  steht `bl 0x8002AAF8` VOR dem ersten `rec`-Zugriff. `void -> u32` bewegt
  keinen Anker (`m145_expectdiff.py` 0 Abweichungen).
- **Die drei verbliebenen Naehte** (`80054AE4`/`80054C5C` -> CC54 in
  FUN_8005471C; `8005A620` -> CC94 in FUN_8005A5A4) sind jetzt "Haken auf ein
  GEBAUTES Ziel" und bleiben GEZAEHLT (Stand-INS als Wirte, Rahmenpuffer +
  LZSS-Wirt fehlen der Laufzeit, kein freier Scratch bei 0x803E0000 ff.).
  Anker (233) haelt sie fest.
- **R222-Klasse (Fremdfund):** die B146-Zeile "(B) 305 / 25" ist um 2 zu klein
  - die archivierte Messung (`git show HEAD:analysis/_m112_ast.txt`) sagt
  **307 / 25** (307+25 = 332 = die Knotenzahl).
- **Werkzeuge (neu):** `scripts/m147_cc.py` (`dis`/`words`/`deps`/`sites`/
  `span`/`sda`/`inner`/`inv`/`win`), `scripts/m147_open.py` (schreibt nichts),
  `scripts/m147_anker.py` (Anker-Datei per Marker), `scripts/m147_log.py`
  (Log-Abschnitt). Alle Belegwerkzeuge stehen in `m144_outguard.TOOLS`
  (43/43; `m146_b1a.py` fehlte in der B146-Liste und ist nachgetragen).

## R356b/R357 + B146 (Batch 146, 2026-09-24)
- **R356b — R222 muss die Spanne ZERLEGEN, wenn der Inventareintrag einen
  registrierten verdeckten Kopf MITMISST.** `8005C820` hat eine Inventarzeile,
  aber die zaehlt `8005CB48` (67 Insn) mit: 1076 B Spanne gegen 808 B Rumpf.
  Regel jetzt: `Spanne - Summe(registrierte verdeckte Ruempfe) == gemessener
  Rumpf` (1076 - 268 = 808). Gilt NUR fuer Koepfe aus `m103_close.HIDDEN_SPANS`;
  ohne registrierten verdeckten Kopf wortgleich wie vorher (R340). `hidsum`
  VOR den Anzeigezeilen rechnen (sonst UnboundLocalError in `cmd_span`).
- **R357 — Namenseintraege der 32-B/12-B-Satzkette tragen als Wort 0 einen
  OFFSET relativ `0x803C0000`.** Der Wirt `c168` addiert ihn selbst; Testfaelle
  muessen ihn VORHER abziehen (`rel(A_STR)`), sonst liest der Interpreter weit
  ausserhalb (`PortFault read8 @0x0065EC80`).
- **R347 (wieder, DRITTER Fall):** `run_case` INNERHALB eines Sandkasten-Blocks
  ruft `beh_install`/`beh_cells` und **verstellt die SDA-Zellen** des
  WL-Sandkastens (Folge: `mission5_step` las einen Nullzeiger). Neuen Block in
  `WlSand zh; zh.enter(ram); ... zh.leave(ram);` legen.
- **R215 (praezisiert): "die Naht faellt aus der Zaehlliste"** heisst: der
  gezahlte **Stub** + sein `STUB_FACTORY`-Eintrag fallen weg (-> `WATCH`), der
  `seam_hit`-Beleg am Rufort BLEIBT (sonst verliert man den Rufstellennachweis).
- **Nullzeiger-Degeneration (R211-Klasse):** `byte_cmp` mit Nullzeiger laesst
  Port ("Guard: gleich") und Interpreter ("0 != 'A'") nur ZUFAELLIG
  uebereinstimmen -> Testfaelle brauchen ECHTE Zeiger/Zeichenketten.
- **B146 — Schnitt (1a) GEBAUT (275 Insn):** `8005C820` (**202**, 12-fach-Tafel
  auf FUENF Koerper) + verdeckter `8005CB48` (**67**, Satzaufbau + drei ECHTE
  Rufe `80060DC4`/`8005C318`/`8005C168`) + `8005C318` (**6**, Zeigerziel + s16).
  Naht ECHT: `0x8005C6E8` (`48000139`) im gebauten `c408_step` -> `row_emit`
  (R194). `voter_leaves2` **49 Koepfe / 2072 Worte / 8288 B / FNV-1a
  `7135EEE6`**; Anker (230) 2/2, (231) **150/150**, (232) **51/51**, (233)
  **46/46**; R207 **597** (a 29/b 0/c 0), `check` 597/10666/0; R216 A **250** /
  B 84 / C 86 / D 676-129; Regression **32 + 262, 0 Fehler**; Modi 78.
- **SDA-Zellen (1a):** `[0x418]` = `0x80113AE0` (Zeigerzelle), `[0x438]` =
  `0x80126630` (Ziel `c318_store`), `[0x43C]` = `0x800894A0` (Sprungtafel),
  `[0x440]` = `0x8005C0E0` (Codebasis; Ziel = `Codebasis + [0xB4 + 4*idx]`),
  `[0x220]`, `[0x234]`, `[0x240]`, `[0x3CC]`. `cb48_build` liest
  `p438 = rd32(0x438)` und `src = rd32(p438)` — DOPPELT, weil `8005C318` die
  Zelle unmittelbar vorher schreibt.
- **Werkzeug (neu):** `scripts/m146_b1a.py` (`cells`/`bodies`/`span`/`words`/
  `sites`/`deps`/`model`; Belege `analysis/_m146_*.txt`).
- **Naechster Schritt:** offene Knoten `8005CC94` (14 Insn) und `8005CC54`
  (64 B, `size`-nur) hinter `8005CB48`.

## R356 + B145 (Batch 145, 2026-09-24)
- **R356 — R222 muss "KEIN Inventareintrag" von "Spanne vorhanden" unterscheiden.**
  Fuer einen VERDECKTEN Kopf (keine CSV-Zeile) verglich die alte Regel die Zahl 0
  gegen den gemessenen Rumpf und meldete `NEIN, -884 B` (`80060DC4`; die 884 kamen
  aus der Spanne von `80060DA0`). Neu (`m130_ast.py cmd_span`): kein CSV-Eintrag,
  aber Rumpf in `m111_core.MEASURED_END` -> gegen die **gemessene** Grenze pruefen
  ("Spanne == Rumpf: ja" + "R356: kein Inventareintrag, Rumpf GEMESSEN"); der
  Bereich hinter dem Rumpf gilt nur dann als FREMDER BLOCK, wenn ihn kein anderer
  Knoten mit gemessenem Rumpf deckt. **Voraussetzung: der verdeckte Kopf ist ein
  echter KNOTEN** (`m103_close.HIDDEN_SPANS`). Kriterien fuer Koepfe MIT
  Inventareintrag bleiben unveraendert (R340).
- **R271/R275 — WIRKUNG GEMESSEN (B145):** die fuenf Grenzen als Knoten
  (`8005C820->8005CB48`, `8005CB48->8005CC54` 67, `80060DA0->80060DC4`,
  `80060DC4->8006110C` 210, `8006110C->80061138` 11) in `HIDDEN_SPANS` +
  `MEASURED_END` + `RANGES`. Effekt: (a) `80060DA0` (Inventar 920 B, Rumpf 36 B)
  meldet seine zwei verdeckten Nachbarn IN der Spanne; (b) `8005C820` hat in
  `m112_ast.py ast` jetzt **202** Insn statt der alten Heuristik **21** -> volle
  Waehler-Huelle (B) **654 -> 835 offene Insn** bei denselben **27** Knoten. Das
  ist die Abschaffung einer STILLEN Verkleinerung, kein Rueckschritt.
- **R219 — zwei Opcode-Luecken (neu, ergaenzt):** `stwx` (**XO 151**) und
  `sthx` (**XO 407**) fehlten im Wortinterpreter; Bruchstellen `8006101C` bzw.
  `80060FA0` (Meldung "op31 xo=151 nicht modelliert", R342). MAME `ppcfe`
  `STWX`/`STHX`: EA = rA + rB, `sthx` nur die NIEDRIGEN 16 Bit.
- **R342-Klasse (Big-Endian-Halbwort):** das Halbwort an Adresse `a` ist die
  **HOHE** Haelfte (`(w >> 16) & 0xFFFF`) - `w & 0xFFFF` verschob im neuen
  Messwerkzeug ALLE Kettenzeiger um 2 B.
- **R347 (wieder, ZWEITER Fall):** neuer Datenspiegel erst auf `kSb+0x1C000` ->
  das LETZTE Wort der Cos-Viertelwelle (`kSbTrigTb + 0x8000`) wurde geloescht
  (Faelle 72/73/101/102/105..108 rot). Fix `kVl2DataOff = 0x1C004` /
  `kVl2KtOff = 0x1EC84`; **Anker (232) RECHNET die Nichtueberschneidung jetzt
  nach**. Neuen Sandkasten immer gegen die bestehenden rechnen.
- **R340 (wieder): Anker mit einer ZAHL waechst mit dem Bau.** `vleaf-b135-anker`
  forderte "R216-A: 43 Koepfe" -> nach B145 sind es **46**; nachziehen ist
  VERSCHAERFUNG (kein Abschwaechen), Grund ins Batch-Doc. Werkzeug fuer die
  Suche: `scripts/m145_anchorcheck.py <anker>` (nennt die fehlende Sollzeile).
- **R310 (wieder):** `port_selftest.exe` braucht `C:\Users\Arcade\msys64\ucrt64\bin`
  im `PATH`; ohne ihn Exit **`0xC0000135`** (`STATUS_DLL_NOT_FOUND`) und JEDE
  Ankerzeile "fehlt" - sieht wie ein Inhaltsfehler aus, ist keiner.
- **R297 (wieder):** ein `// ----`-Kommentar ohne Leerzeichen am Zeilenende
  verschmilzt die FOLGENDE Zeile in den Kommentar (drei Syntaxfehler in B145).
  Namensraum-Falle: `mission::kSdaObjBlk` (nicht `mission_script::`).
- **B145 — Schnitt (1b) GEBAUT (233 Insn):** `80060DC4` (**210**, verdeckter
  8-fach-Verteiler + 6-B-Kette) + `8006110C` (**11**, verdeckt, vier Zeigerfelder)
  + Wirt `80060B60` (**12**). Verdrahtet INNEN: `0x80060E40 -> 80060B60`
  (ROM-Wort `4BFFFD21`), drei aeussere Rufstellen bleiben Naehte (`8005CC20` in
  (1a), `8005D1B0`, `8003E5B8`). `voter_leaves2` **46 Koepfe / 1797 Worte /
  7188 B / FNV-1a `65D0FED8`**; Anker (230) 2/2, (231) **135/135**, (232)
  **48/48**, (233) **45/45**; R207 **594** (a 29/b 0/c 0), `check` 594/10510/0,
  nachzuegler 77/31; R216 A **247** / B 84 / C 86 / D 673-129; Regression
  **32 + 261, 0 Fehler**; Modi 78.
- **SDA-Zellen des Schnitts (1b):** `[0x400]` = `0x80113538` (Laufzeit-
  Kopiertafel, im Bild NICHT vorhanden), `[0x444]` = `0x80126638` (Zielsatz),
  `[0x448]` = `0x800A5FD8` (Datenbasis, IM Bild), `[0x44C]` = `0x80089D88`
  (Sprungtafel, 8 Eintraege), `[0x450]` = `0x8005ED10` (Codebasis).
  **Kette:** 6-B-Satz `+0` s16 Zaehler, `+2` s16 Kopftafelzeile, `+4` u8 Fahne
  (SO 1/EQ 2/GT 4/LT 8), `+5` u8 0; Ende `Zaehler == -1`; die Fahne wird VOR
  JEDER Stufe neu gelesen. Beruehrt (2. Modell): **0x286C B** von 0x2C80 B.
- **Naechster Schritt:** **(1a)** `8005C820` (202) + verdeckter `8005CB48` (67) +
  `8005C318` (6) = **275 Insn**; dann `8005C6E8 -> 8005C820` im GEBAUTEN
  `c408_step` verdrahten und die Naht `kSeamRowEmit` aus der Zahlliste nehmen.
- **Werkzeuge (neu):** `scripts/m145_b1b.py` (`cells`/`chains`/`span`/`words`/
  `sites`/`model`, Belege `analysis/_m145_*.txt`), `scripts/m145_expectdiff.py`
  (Tafeln gegen HEAD), `scripts/m145_anchorcheck.py` (fehlende Sollzeile).

## R355 + B144 (Batch 144, 2026-09-24)
- **R355 — Belegdateien werden NIE STILL ueberschrieben** (ersetzt die Praxis aus
  R334, das dreimal verletzt wurde). Jeder Schreibvorgang auf `analysis/` laeuft
  ueber `scripts/evidence.py`: `EV.target(name)` / `EV.guard(pfad)` sichern den
  **Altstand** vorher nummeriert nach `analysis/_archiv/<stamm>.<NNN>.<hash8><ext>`
  (Dedupe ueber den Inhalt, einmal je Prozess/Datei, Zeile in `MANIFEST.txt`),
  oder `--out <verzeichnis>` / `EV_OUT` verlangt einen **ausdruecklichen
  Ausgabepfad** (dann kein Archiv). Pfade ausserhalb `analysis/` (Quellcode)
  gehen unveraendert durch. **Kein Vorher-Kopieren von Hand mehr** —
  `preflight.py` kopiert nichts mehr nach `_pf_prev/`. `analysis/_archiv/` ist
  in `.gitignore`. Werkzeuge: `scripts/m144_outguard.py {list|dry|apply}` (38
  Werkzeuge umgestellt, 4 mit Grund ausgenommen), `scripts/m144_check.py`
  (Abnahme: 38/38 kompilieren, 0 ungeschuetzte Schreibwege).
  Neue Belegwerkzeuge: `def _out(name): return EV.target(name)` + Import.
- **B144 — nichts gebaut, Zuschnitt gemessen:** (1a) `8005C820` **202** +
  verdeckter `8005CB48` **67** + `8005C318` **6** = **275 Insn** (AussK 0 / GAP 0);
  (1b) `80060DC4` **210** + verdeckter `8006110C` **11** = **221 Insn** (AussK 1:
  `80060B60` 12 Insn); beide zusammen 496, mit Wirt **508** -> **kein Einzelbatch**.
  **Reihenfolge: (1b) VOR (1a)** — `8005CB48` RUFT `80060DC4` (@8005CC20).
  **B143-Zahl korrigiert:** `80060DC4` = **210** (nicht 209).
- **Sprungtafeln AUFGELOEST** (`scripts/m144_cells.py`, RAM-Dump
  `capture/m31_ram4mb.bin`, r2 = `0x800ADA5C`, Offset = Adresse − 0x80000000):
  `8005C820`: `[SDA(0x43C)]=0x800894A0` + Codebasis `[SDA(0x440)]=0x8005C0E0`,
  12 Indizes -> Koerper `8005C860` (0,11), `8005C8F8` (1), `8005C990` (2),
  `8005CA28` (3), `8005CAC0` (4..10). `80060DC4`: `[SDA(0x44C)]=0x80089D88` +
  `[SDA(0x450)]=0x8005ED10`, 8 Indizes -> `80060E6C/E8C/EAC/ECC/EE4/F04/F24/F3C`.
  Weitere Zellen: `0x444` = Zielsatz `0x80126638`, `0x400` = `0x80113538`,
  `0x418` = Zaehler `0x80113AE0`.
- **R271/R275 als ENTSCHEIDUNG:** eine gemessene Grenze fuer einen VERDECKTEN
  Kopf in `m111_core.MEASURED_END` verkleinert jede Huellenmessung **still**
  (der Kopf ist kein KNOTEN und faellt ganz aus der Zaehlung) -> sie gehoert in
  den BAU-Batch, zusammen mit **R356** (R222-Regel fuer Koepfe OHNE
  Inventareintrag; heute meldet R222 fuer `80060DC4` „NEIN, -884 B").
- **R297 (wieder):** `python - c "pass"` startet eine REPL und schluckt alle
  Folgebefehle; `Add-Content` schreibt CRLF in eine LF-Datei.

## R346-R349 + B141-Zahlen (Batch 141, 2026-09-24)
- **R346 — der PLATTENSTAND ist die Wahrheit.** (a) `git checkout -- <datei>` holt den
  **INDEX**-Stand; bei gestagten Dateien ist der viel aelter als die Arbeitsfassung —
  so verschwanden `B140_HEADS` UND die B139-`VERDICTS`-Registry aus
  `scripts/m104_built.py`. (b) Der **Editor-Schreibweg kann stumm ins Leere laufen**
  (die Aenderung war im Editor sichtbar, auf der Platte 0 Treffer) -> nach JEDER
  Aenderung `io.open(...)`/Zeichenzahl/Suchbegriff pruefen und notfalls mit einem
  Python-Skript schreiben (R297-Muster). Aufgedeckt hat den Registry-Verlust der
  **Preflight** (fehlende `R207`-Zeilen), nicht der Anker.
- **R347 — ein neuer Daten-Sandkasten darf bestehende Daten NICHT ueberlappen.**
  Die B141-Faelle luden bei `kSb+0x1B000`; die Trigonometrietafel endet bei
  `kSbTrigTb + 0x8000` = `kSb+0x1C000` -> Fall 72/73 rot. Fix: Daten nach
  `kSb+0x1DA00..0x1ED00`, und die Nicht-Ueberlappung ist jetzt eine **Vorprobe in (232)**.
- **R348 — `rlwinm rX,rS,28,28,31` holt das HOHE Nibble** (Linksrotation + Maske der
  niederen Wortbits = `(v>>4)&0xF`). Das niedere zu lesen setzte das Flag `11` zu oft
  (Fall 108 `[DIFF]` `+0x1E00C: 05030B00 statt 05030000`). Richtig: Bit 5 (`0x20`) des Bytes.
- **R349 — ein Naht-Stub zaehlt die Argumente ab `r3`**, aber das ROM kann einen
  gerufenen Kopf mit **`r4`/`r5`** beliefern: `8005C820` liest `15(r3)` = den 92-B-Satz
  -> `nargs` muss **3** sein (war 2). Ein falscher `nargs`-Wert erzeugt Sollwerte aus
  den falschen Registern (still, weil die Zahl der Rufe stimmt).
- **R347b — der Rahmenpuffer (`r1+64`) liegt in den zwei Welten auf VERSCHIEDENEN
  Adressen** (`0xFFFFFCB0` direkt, `0xFFFFFC60` ueber den Aufbau) -> der Naht-Vergleich
  bildet JEDEN Stapelwert auf den Portpuffer ab (und nur diesen).
- **R161 (wieder):** der Bauer gibt den **Registerrest `r3`** zurueck (Fall 107 `[RUECK]`);
  jede r3-schreibende Stelle mitfuehren, `void`-Kopfrufe -> `r3 = 0` + `residue++`.
- **B141 — die Szene-Satzkette ist GEBAUT:** `8005C408` (215) + `8005C168` (108) als
  zwei neue Koepfe in `port/voter_leaves2.{h,cpp}` -> **35 Koepfe / 1351 Worte / 5404 B
  (FNV-1a `EFE73A6E`)**; Faelle **101..108**; Anker (230) 2/2, (231) **109/109**,
  (232) **40/40**, (233) **39/39**; Regression **32 + 259, 0 Fehler**.
  **R147:** die EINZIGE Rufstelle `0x8005C2DC` liegt IM gebauten Aufbau (R216-A-Zaehler:
  `c408_step` **2**, `c168_step` 1); die vier Aufbau-Rufstellen (`8005CC3C/CC78/CCB8/CD98`)
  liegen im UNGEBAUTEN `8005CCCC`.
  **Acht Nahtziele GEZAEHLT (R215, 464 Insn):** `8005248C` 11, `800523E0` 43, `8005C7AC` 29,
  `8005C764` 18, `8005C820` 269, `8002AEBC` 22 (LZSS-Fenster `0xFF1C2000`), `8005D3B0` 36,
  `8005C330` 36 — **Wirkung fehlt** (nur Ruf/Zahl/Argumente sind gefroren).
  **R233-Ergaenzung:** `8005C330` wird als **bedingter Tail** gerufen (`bcl 4,4` @8005C2F0)
  - ein Zensus nur ueber Opcode 18 uebersieht sie.
- **B141-Zahlen (R308, 2026-09-24):** `preflight before`+`after 8005C408 8005C168`
  **SAUBER (0 Befunde)**; R207 **583** (a 29/b 0/c 0), `check` 583/10276/0, `sanity` 583/0,
  `nachzuegler` 77/31 (3/2); R216 **A 236** / B 84 / C 86 / D 662-129; Waehler-Gruppe
  **93/4** (unveraendert); Huelle (A) **99/9** (108 Knoten, R316 nicht monoton),
  (B) **297/35** (332 Knoten, 865 Insn + 64 B), Unterbau (B) 31/807, (A) 5/110;
  Strang A/B je 0 offen; Pool 105/327 = 32,1 %; Inventar S1-DOKU **1659 (80,1 %)** von
  2072; Modi **78** (die zwei Koepfe laufen im bestehenden `vleaf`).


## R340/R341/R338/R342 + B139-Zahlen (Batch 139, 2026-09-24)
- **R340 — das Urteil gehoert dem MODUL.** Die Abnahmekriterien lagen bis B138
  als Regex + feste Schwellen in `scripts/preflight.py`. Jetzt: `scripts/verdict.py`
  (`Verdict(key,value,ok,text,detail)`, `capture`, `record`, `one`,
  `run_module`) + pro Modul eine Tafel `JUDGE` (der TEXT-Weg schreibt sein
  Urteil hinein) + `VERDICTS = [(key, fn)]` (Registry). Die Schwelle steht im
  Modul: `m104_built` (`tails`: hits/gaps == 0; `check`: miss == 0; `sanity`:
  bad == 0; `nachzuegler`: `ok = None`), `m115/m116` (A-D: `ok = None`),
  `m114` (P100: `not mem and not arg`), `m130` (R222: Spanne == Rumpf UND kein
  fremder Block), `port_regression` (`failures == 0`). `preflight.py` liest nur
  noch; neue REGEL = ein `VERDICTS`-Eintrag, neue GRUPPE = ein Eintrag in
  `CHECK_MODULES`. `ok = None` heisst **Meldung** (kein Kriterium).
  Pruefwerkzeug: `scripts/m139_verdict.py {parallel|capture|compare}`.
- **R341 — der Parallellauf hat einen echten Fehler der alten Fassung
  gefunden:** `_line(txt, hex)` traf fuer `P100 8005C168` die
  KOPFKOMMENTAR-Zeile des Moduls (`# Positivkontrolle: ...`) statt der
  Ergebniszeile. **Regel: die ERGEBNISZEILE treffen, nicht die erste Zeile mit
  der Adresse.** Ergebnis des Laufs: 15 Zeilen, 14 Urteile gleich, 1 bewusste
  Anzeigekorrektur (`R207 nachzuegler` `OK` -> `Meldung`); alle elf
  Modul-Ausgaben byte-gleich.
- **R338 — Stub in gebautem Code: MESSEN, dann ENTFERNEN.** `state_inc`
  (`FUN_8003C6AC`) war gestubbt; mit `stbx`/`stbu` im Interpreter laeuft der
  rohe ROM-Rumpf. Gleichheit 42/42 im Wertebereich; `_m130_ref.txt` aendert sich
  nur in `Stub-Rufe` + Schrittzahl (20->48/43->69/34->60), die Erwartungstafel
  ist byte-gleich.
- **R342 — neuer Rumpf ZUERST gegen den Interpreter fahren**
  (`scripts/m139_int.py probe`): `800535B4` brauchte `lhax` (XO 343); vorher
  2 Abbrueche, nachher 17/17 Wege.
- **R336 zum DRITTEN Mal:** `lha rX,d(rA)` liest die HOEHE Haelfte; Byte bei
  `+1` = `(v << 16)` im Wort bei `+0`. Falsch gesetzt laufen ALLE Wege den
  v=0-Zweig und die Probe meldet trotzdem 0 Abbrueche.
- **B139-Zahlen (R308, 2026-09-24):** R207 rueckw. **580** (29/0/0), `check`
  580/0, `sanity` 0, `nachzuegler` **77/31 (3/2)**; R216 **A 233** (R330-Wart)
  / B 84 / C 86 / D 659-129; Regression **32 + 258, 0 Fehler**; Waehler-Gruppe
  **92/5**; Huelle (A) 128 Knoten **107/21** (848 Insn + 64 B); (B) 332 Knoten
  **294/38** (1313 Insn + 64 B); Unterbau (B) 33/1130, (A) 16/665; Pool
  105/327; Inventar **S1 1650** / Rest 424; Modi 78 - **alles unveraendert**,
  weil in B139 KEIN Kopf gebaut wurde.
- **Vermessen, NICHT gebaut (naechster Batch):** `800535B4` (125, Huelle
  GESCHLOSSEN: BAU 8 Knoten/offen 1, alle 7 Rufziele gebaut, Rufstelle
  `0x800553C8` = Hakenzeile in der gebauten `mission_script.cpp` M5
  `state == 4` -> R147 schliesst zugleich `msg_index`-Stelle `0x80053690`);
  `8005C408` (215, BAU 20/12, 4 offene Rufziele, einzige Rufstelle
  `0x8005C2DC` IN `8005C168`); `8005C168` (108, 4 Rufstellen in ungebauten
  Koepfen); `FUN_8007D968` (296) + `8007D9B8`.

## R333/R335/R336/R339 + R326-Ergaenzung (Batch 138, 2026-09-24)
- **R333 (fest):** der BESITZER einer Rufstelle ist die Werkzeugantwort
  `innerhalb(FUN_...)` (`m130_ast.py sites`). B136s „ausserhalb jedes
  Inventarkopfes“ war FALSCH: `80046028` in `FUN_8004601C` (in B138 GEBAUT),
  `8007D9B8` in `FUN_8007D968` (296 Insn, offen).
- **R335:** der Fallschalter des Verhaltensankers (231) ist der **Index in
  `m130_ref.HEADS`** — neue Koepfe NUR HINTEN anfuegen; ein falscher `case`
  laeuft gegen einen fremden Kopf und liefert PLAUSIBLE Werte.
- **R336:** die NIEDERE Wort-Haelfte ist das Halbwort bei +2 (der Zeitgeber
  `slot+0x0E` liegt in der LOW-Haelfte von `+0x0C`); Fallwert in der hohen
  Haelfte -> der Rumpf liest 0 (falscher Zweig, plausible Rueckgaben).
- **R339:** die Missionsmaschine `FUN_8003DF3C` haengt an `[SDA(0x254)]`
  (Tafel) + `[SDA(0x258)]` (Basis) — NICHT an den M0-Zellen `0x3A0`/`0x490`.
- **R326-Ergaenzung → in B139 ERLEDIGT (R338):** `stbx` (XO 215) **und**
  `stbu` (Op 39) sind im Interpreter; der Hand-Stub `fx_state_inc` ist aus
  BEIDEN Stub-Tafeln entfernt (Anker faehrt den rohen ROM-Rumpf von
  `FUN_8003C6AC`). Gleichheit GEMESSEN (`scripts/m139_stbx.py`): 78 Faelle,
  `idx 0..7` 42/42 identisch, `idx < 0` Abweichung (Stub `u32(idx)+1` vs.
  ROM-Vorzeichen); `voter_leaves2_expect.inc` danach **byte-gleich** (1298
  Zeilen). Benannte Rest-Luecken: `stbux` (XO 247), `lbzu` (Op 33).
- **R194/R316 (wieder):** jede neue Verdrahtung bewegt die Zaehler FREMDER
  Anker — `hud_labels` 1 -> 2 und `msg_index` 1 -> 2 (R216-A-Kette), im
  game-flow-M3-Fall drei Anzeigeschalter. Messen und nachziehen.
- **R161:** `std_numbers` ist im Port `void`; das ROM laesst den Rest des
  letzten Wire-Rufs stehen -> `kStdNumbersRest = 1` + `Vl2Stats::residue`.
- **B138-Zahlen (R308, 2026-09-24):** R207 rueckw. **580** (29/0/0), `check`
  580/0, `sanity` 0, `nachzuegler` **77/31 (3/2)**; R216 **A 233** (R330-Wart:
  um 1 zu klein, richtig 234) / B 84 / C 86 / D 659-129; Regression
  **32 + 258, 0 Fehler**; Anker vleaf **(230) 2/2, (231) 90/90, (232) 31/31,
  (233) 38/38**, FNV-1a **`0A0682B4`**, 32 Koepfe / 903 Worte / 3612 B;
  Waehler-Gruppe **92/5**; (A) 128 Knoten 107/21; (B) 332, 294/38 (offen
  1313 Insn + 64 B); Unterbau (B) 33/1130, (A) 16/665; Pool 105/327;
  Inventar **S1 1650** / Rest 424; Modi 78.

## R317–R321 (Batch 134, 2026-09-23)
- **R317 — die R315-Klasse hat VIER weitere Stellen.** Die R315-Pruefung
  (`static_cast<u16>`/16-Bit-Verkurzung vor einem `write32`) ist im GEBAUTEN
  Code noch an `0x8005AA00`, `0x80054B5C`, `0x80054B94`, `0x80054C04` gewesen
  (obere Haelfte von `slot+0x40` wurde genullt, **still**). Regel: **jeder**
  `static_cast<u16>` vor einem `write32` auf ein ROM-Feld ist verdaechtig.
- **R318 — `scripts/m130_ref.py` fuehrt ZWEI Stub-Tafeln**; die innere in
  `case_list()` ist **TOT**. Ein dort eingetragener Stub wirkt **lautlos nicht**
  (der Fehler ist nur ueber einen fehlgeschlagenen Fall zu sehen).
- **R319 — `extsb` setzt CR0 nur gepunktet.** Der eigene Wortinterpreter setzte
  CR0 bei JEDEM `extsb`; das ROM nur bei `extsb.` (Rc-Bit, `w & 1`). In
  `FUN_8005A46C` ueberschrieb das ungepunktete `extsb r4,r4` (0x8005A498) den
  CR0-Wert von `extsb. r0,r0` (0x8005A490), das Abbruch-Tor kippte und der Rumpf
  lief **nie**. Fix: `if w & 1: self.cr_cmp(0, ...)`.
- **R320 — dieselbe CR7-Pruefung zieht VERSCHIEDENE Wortbits.** MIT
  `rlwinm rX,rS,28,0x1C,0x1F` ist CR7.GT **Wertbit 6 = 0x40**; OHNE `rlwinm`
  (nur `mtcrf 0x1`) ist CR7.GT **Wertbit 2 = 0x4** und CR7.LT **Wertbit 3 =
  0x8** — genau die `kNib7*`-Zahlen. Sollwert-Arithmetik („0xC ist 0x40") ist
  die Fehlerquelle (B134: `000400C0` statt `0004000C`).
- **R321 — ein gerufener Kopf kann das Feld zuruecksetzen, das der Anker
  pruefen will.** `stage_scan` nullt `obj+0x74` — denselben Zaehler, den
  `term_step` fuehrt. **Fall trennen** (Tor zu / Tor offen) statt den Sollwert
  abschwaechen.
- **B134-Messwerte (R308, 2026-09-23):** R207 rueckw. 567 (29/0/0), `check`
  567/0, `sanity` 0, `nachzuegler` 76/30 (3/2); R216 A **220** / B 83 / C 85 /
  D 643 (129 ausserhalb); Waehler-Gruppe **85/12**; Huelle (A) **111/33**;
  volle Huelle (B) **282/50** (1711 Insn + 416 B size-nur); nur-Unterbau 38/1302
  (B) / 21/837 (A); Inventar S1 **1648** (79,5 %) / Rest 424; Modi **78**;
  Anker (230) 2/2, (231) 52/52, (232) 19/19, (233) 24/24; Regression 32 + 255.

## R293–R298 (Batch 128, 2026-09-23)
- **R293 — `0xFF000000 + X` ist die ROM-SICHT des Abbilds** (kein MMIO, keine
  "unbaubare" Adresse). ROM-Offset `X` = **Datei-Offset** `X` in
  `rom/build/830d01.27p.be.bin` (2 MiB). Die fuenf Zellen `0xFF1F6000`,
  `0xFF1F6004`, `0xFF1FCA00`, `0xFF1FCA04`, `0xFF1FCA08` tragen die
  erwarteten Verzeichnis-/Listen-Offsets — **Probe 6/6**
  (`analysis/_m128_romprobe.txt`). Das Hauptbild hat dort **0**.
  → Das Batch-111-Verdikt "2a-Kern-Nachbarn unbaubar (P100)" ist **WIDERLEGT**.
- **R294 — Zelle und Basis liegen an VERSCHIEDENEN Alias-Adressen**
  (`0x1FCA08 → Basis 0x1FCA00`; `0x1F6004 → Basis 0x1F6000`). Ein Mappen nur
  der Zelle liefert 0. `win_cell_base(cell, basealias, ...)` mappt beide.
- **R295 — Zell-Tiefe ist pro Zelle zu messen.** `[SDA(0x17C)]`, `[SDA(0x18C)]`,
  `[SDA(0x1A0)]` sind **EINE** Stufe (der Zellwert IST die Adresse), `[SDA(0x178)]`
  und `[SDA(0x180)]` sind zwei. Zwei Stufen im Sandkasten = Anker findet 0.
- **R296 — 12-Byte-Liste:** der Slot traegt `[0]` Namens-Offset, `[4]` Belegung,
  `[8]` Rueckgabewert. Der Vergleich liefert einen **INDEX**; der Leser rechnet
  `base + 12*idx` (nicht `base + off`).
- **R297 — PowerShell-Escape ist der Backtick**, nicht `\`. Sonst landet die
  Zeile in der Fortsetzungsabfrage (`>>`). Fuer Textsuche `grep_search` oder
  Python-Skripte nehmen.
- **R298 — Anker-/Messzeilen IMMER drucken.** `port_regression.py` liest
  **stdout**, nicht den Exit-Code; Detailzeilen nur bei Fehler = unsichtbarer
  Anker. Hausform: `add_line(rep.<sec>_lines, "  (NNN) NAME: %u/%u", ok, n)`.
- **R289 erneut:** `voter_core2.cpp` und `voter_core2a_check.cpp` trugen
  UTF-8-BOM → entfernt. Vor jedem Bau auf BOM pruefen.

## R217 — `addic` mit RA = 0 benutzt **r0** (KORREKTUR von R203/R204, Batch 108)
- **R203 galt zu weit.** Die Konstante-0-Regel fuer `RA = 0` gilt nur fuer
  `addi`/`addis` (op 14/15) und fuer die D-Form-**Speicher**zugriffe
  (`lwz`/`stw`/`sth`/... → Adresse 0).
- `addic`/`addic.` (op 12/13) und `subfic` (op 8) mit RA = 0 lesen **GPR0**.
- Belege: MAME `ppcdrc.cpp` (`ADDI/ADDIS = R32Z(ra)`, `ADDIC/SUBFIC = R32(ra)`);
  Ghidra-Decompilate von FUN_8000F76C (`iVar4 + 0x8458`), FUN_80029DBC (`-0x10`),
  FUN_8002A1D4 (`sVar1 + 1`); Haenge-Beweis `0x8002A2AC addic r8,r0,0` nach
  `li r0,6` + `mtspr CTR,r8`.
- **Tragweite:** 1202 solcher Stellen im Bild, **87 in gebauten Koepfen**
  (`analysis/_m108_ra0_census.txt`, `_m108_ra0_built.txt`).
- **R204** ("`addic r0,0,1` ist eine Flagge") ist damit falsch: in FUN_80027280
  (0x80027448) ist es ein **Zaehler**.
- **ERLEDIGT (Batch 109):** Modell (`m103_model.py` op 12/13) **und** Port
  (`mission_tail.cpp` `slot_rank`) korrigiert; das Rangfeld ist eine **Zaehlung
  ueber NEUN Plaetze** (8 Saetze + `cfg+0x842` = der `value`), entschieden mit
  `scripts/m109_rank.py` (19/19; jede Flaggenformel faellt durch).

## R212 — die Inventarspalte `insn` ist die Koerperlaenge, aber nicht immer
- `insn` IST die gemessene Koerperlaenge; `size` ist der Abstand zum naechsten
  Inventarkopf (kann MEHRERE Koepfe fassen).
- **Zweite Richtung (Batch 108):** `insn` kann auch **zu GROSS** sein — springt
  eine Wurzel per `b` in einen Nachbarkopf, zaehlt die Spalte ihn mit
  (`FUN_8005389C`: 194 = 169 + 25 fuer `FUN_80053B40`).
  Gegenprobe: eigener `stmw`-Prolog + eigener `bclr` des Nachbarn.

## R162 — `0x6000000x` ist **kein** `nop`
- `0x60000002` = `ori r0,r0,2`, `0x60000040` = `ori r0,r0,0x40`,
  `0x60000004` = `ori r0,r0,4`. Der Projektdecoder druckt sie als `nop`.

## R216 — Bauzustand: ZWEI Werkzeugquellen vergleichen
- `scripts/m103_close.py closure` rechnet gegen `m101_content.built_set()`,
  `scripts/m104_built.py` fuehrt eine **gepflegte** Bau-Liste. Die Mengen
  unterscheiden sich (Batch 108: **40** Adressen) — vor jedem Bau **beide**.
- Ein Kopf kann einen 1:1-Bau haben und trotzdem als "offen" gefuehrt werden
  (`OpMode::pool_clear_all` = FUN_8000F76C, klassengebunden): dann ueber den
  **vorhandenen Saum** adoptieren (`flow::FlowHooks::pool_clear`), nicht neu bauen.
- **Batch 109 (dritter Fall in Folge):** 2 von 36 Kern-Knoten waren schon gebaut
  (`8000D314` `voter::byte_cmp`, `80018734` `voter::ring_append`, Batch 108) —
  die `closure` fuehrte sie als **offen**.

## R221 — ein Kommentar ist kein Beleg fuer den Code (Batch 109)
- `ring_append` trug woertlich `P = *[SDA(0xF8)]` im Kopf — der Code las die
  Zelle **einstufig**. Die Kette gehoert in den **Anker** (hier: Gegenprobe mit
  einer falschen Zeigerzelle), nicht in einen Kommentar.

## R207 — der Tail-Scan ist PFLICHT, rueckwaerts und nach dem Bau
- `python scripts/m104_built.py tails` — erwartet: (a) >0 · **(b) 0** · (c) 0.
- Batch 108: 256 Koepfe vor / **270** nach dem Bau; Batch 109: **270** vor und
  nach (baut keinen ROM-Kopf), (b) blieb leer. `check` 270/0, `sanity` 270/0,
  `nachzuegler` 1/1 (0x800434B8, klassengebunden).

## R194 — Hakenzahl-Sollwerte im SELBEN Batch auf Wirkung umstellen
- Wird ein Haken durch einen gebauten Kopf ersetzt, prueft der Anker die
  **Wirkung** (Zaehler des neuen Moduls) **plus** die Gegenprobe "kein Haken
  mehr". Keinen Sollwert abschwaechen.

## Schleifen mit Bedingung am KOPF und Zweig am FUSS
- Laufen **einmal mehr** als die naive Lesart (CR0 wird am Kopf gesetzt, der
  Zweig testet es nach dem Rumpf): `FUN_8000F76C` leert `n+1` Zeilen.
- **R220 (Batch 109, am Befehl-fuer-Befehl-Modell bewiesen):** entscheidend ist
  die **Lage des Rumpfes** — steht er zwischen Bedingungs-Auswertung und
  Rueckzweig, laeuft er **einmal mehr**, auch wenn der Zweig auf den `cmp`
  selbst zielt. **Messprobe: n = 0** (do-while ⇒ 1 Durchlauf, "genau n" ⇒ 0).
  Werkzeug: `scripts/m109_poolrow.py` (emuliert 0x8000F76C..0x8000F7E0).
- **Fehler, den ich dabei gemacht habe:** den Rueckzweig als Vor-Pruefung
  gelesen und beide Portfassungen falsch "korrigiert" — erst die n=0-Probe
  hat es gezeigt. Der Fehler sass in `OpMode::pool_clear_all` (`r < rows` = n).

## R218 — Dereferenzierungstiefe einer SDA-Zelle PRO ZELLE messen (Batch 109)
- Muster fuer eine **Zeigerzelle** (zwei Stufen): `lwz rX,off(r2)` und kurz
  darauf `lwz rX,0(rX)` ohne Zwischenschreiber. Werkzeug:
  `python scripts/m109_deref.py <start> <ende>` (zielgerichtet je Kopf+Zelle;
  der ganz-Bild-Scan hat viele Fehlalarme).
- Gemessen (Kranz Batch 108/109): **0x28** und **0xF8** = Zeigerzellen
  (`[SDA(0x28)] = 0x800AEDC0 → *Zelle = obj`; `[SDA(0xF8)] = 0x800FA288`),
  alle uebrigen (0x34, 0x178, 0x180, 0x184, 0x188…0x19C, 0x1A0, 0x1A4, 0x1B4,
  0x220, 0x234, 0x288, 0x550, 0x558, 0x62C, 0x648) = Wertzellen.
- **Ein Sandkasten in der Port-Konvention kann den Fehler nicht sehen** — die
  Kette gehoert als **Gegenprobe** in den Anker (R221).
- **Offen:** Audit der uebrigen gebauten Module (Verdacht: Zellen, deren
  Live-Wert ausserhalb der Bilddatei liegt, sind Zeigerzellen).

## R219 — "Zaehlung oder Flagge" gegen das Modell entscheiden (Batch 109)
- Ein Pruefstand, der **dieselbe Regel** wie der Port benutzt, ist
  **kreuz-korreliert** und liefert falsche Gruens (hier 14/14 mit falscher
  Formel; `m103_model.py` trug die R203-Lesart wie der Port).
- Die Fallliste muss die Bauarten **trennen**: alle 14 alten Rangfaelle hatten
  Sollwerte 0/1 und konnten Zaehlung und Flagge nicht unterscheiden.
  Gegenprobe: **gibt es einen Fall mit Sollwert > 1?**
- **ERGAENZUNG (Batch 110):** widersprechen sich Herleitung und Dekompilat bei
  EINEM Bit, entscheidet ein **Kalibrierfall** mit schon verankerter Semantik.
  Konkret: meine Herleitung aus `rlwinm r0,r0,20,28,31` + `mtcrf 0x1` + `bc 12,31`
  (FUN_80019458) ergab Bit 11; derselbe Bau in FUN_8002B000 (LZSS, bit-exakt
  verankert) liefert nach dieser Herleitung NICHT das richtige Bit -> Herleitung
  falsch, **Bit 12 (0x1000)** gilt (Dekompilat + 4 Batchdokumente).
  Und: **ein Datenbeleg muss zur richtigen Funktion gehoeren** - der Rohdatensatz
  0x08241AC7 (gepatcht zu 0x14261AC7) hat Bit 11 UND Bit 12 gesetzt und stammt
  deshalb von der zweiten 0x14261000-Stelle `FUN_8001A82C`, nicht von 0x80019458.

## R222 — eine `size`-Spanne kann einen FREMDEN Block enthalten (Batch 110)
- Die Rumpflaenge wird **gemessen** (Ghidra `disassemble_function` + Rohworte),
  nicht aus der Inventarspanne abgeleitet. **Dritte Auspraegung dieser Richtung:**
  `FUN_800080A8` hat **2** Instruktionen, die 232-B-Spanne fasst **28 fremde
  Zwei-Befehl-Stubs** (0x800080B0..0x8000818C, `mtdcr`/`mfdcr`-Klasse + `blr`),
  die Ghidra **nicht** als Funktionen fuehrt. Zweite Probe: das Rumpfende hat ein
  eigenes `blr`/`bclr` (R211: 4-B-Nullwort danach).
- Folge in Batch 110: die 2a-1-Vormessung "275 Insn" war **217**.

## R223 — ein flacher Pruefstand kann eine zu flache Kette nicht sehen (Batch 110)
- `dump_overlay.cpp` schreibt `d.state` **direkt in die Zelle** `r2+0xF8`; damit
  teilt der Pruefstand die flache Konvention des Moduls und kann den Fehler
  nicht aufdecken (R219-Klasse). Die Kette gehoert (wie R221) **in den Anker**.

## OFFENER FUND (Batch 110, nicht behoben): `render_transport::state_at()` flach
- `u32_at(sda_+0x0F8)` = **eine Stufe zu flach**; der ROM nutzt `*(*(r2+0xF8))`
  (38 Stellen im Bereich 0x80016968..0x80018D00), und die port-eigenen Module
  `display_bank`, `paket_d_check`, `slot_check` bauen die Kette **zweistufig**.
- Live-Beleg (`capture/m31_ram4mb.bin`, Rohbytes): `[SDA(0xF8)] @0x800ADB54 =
  0x800FA288` -> `*(0x800FA288) = 0x800B3C28` -> `*(0x800B3C28) = 0x02000180`
  = 512x384 (state+0 = Anzeigegroesse).
- Rezept: `state_at()` auf `u32_at(u32_at(sda_+0x0F8))` **und** `dump_overlay`
  (Zustandszeiger in die Zelle) in EINEM Zug, dann die 32 Frame-Anker.

## R224/R225 — X-Form-Quelle und `bt`/`bf` (Batch 114, im Wortinterpreter belegt)
- **R224:** `rlwinm`, `srawi`, `or/ori/andi.` lesen die **Quelle aus dem
  RS-Feld = RT-Position**, das Ziel aus RA. Wer `R[ra]` als Quelle nimmt,
  dreht jede Flaggenpruefung um (`rlwinm r0,r24,28,0x1C,0x1F` + `mtcrf 0x1,r0`
  + `bc 4,31` = Test von Bit 4 des Registers 24).
- **R225:** `bc` mit BO = 12 (0b01100) = **bt**, BO = 4 = **bf**, BO = 20 =
  immer. Die Unterscheidung haengt an **Bit 0x08**; ein Vergleich `bo & 0x14`
  dreht bt und bf um (aus `bltlr` wird `bgelr`).
- **R227:** Ghidras `subic rD,rA,n` ist `addic rD,rA,-n` (op 12) — Rohworte
  `337BFFFF` (`r27-1`), `33FFFFF0` (`r31-16`); kein eigenes Kommando.
- **R226:** bekommt ein Ruf eine **Adresse** als erstes Argument
  (`addic r3,<obj>,0x114`), schreibt er dorthin (Ergebnis **ersetzt** die alte
  Belegung); ein Port mit lokalem Registerfeld verliert das Ergebnis.
- **R228:** "Richtungsfelder" koennen IM Matrixfeld liegen
  (`+0x22/+0x24/+0x26` in `+0x1C..+0x2D`).
- **Generator-Disziplin:** nach jeder Tabellen-/Formelaenderung **beide**
  Generatormodi laufen lassen (`words` UND `cases`) — eine veraltete `.inc`
  sieht wie ein Portfehler aus.

## R233/R234/R235 — Belegquellen und Werkzeugfallen (Batch 116)
- **R233:** die Inventarspalte `callers` ist **keine** Rufstellenliste
  (`800155D0`: Spalte 0, Bild 1). Ruf-/Sprungstellen mit **Vollbild-Scan** der
  `b`/`bl` im ROM-Bild messen (op 18, `li = ((x & 0x3FFFFFC) ^ 0x2000000) - 0x2000000`).
- **R234:** die **vierte Belegquelle** (Moduldokumentkopf `// FUN_<adresse> - <Rolle>`
  **plus** Umfeld mit „Rohworte/CONFIRMED/1:1“) ist **CONFIRMED** als Fundstelle
  weiterer 1:1-Bauten (`m116_pass.py doc4`) — aber **einzeln** pruefen, nicht gruppenweise.
- **R235:** ein **Stand-in** („die Untermenge“) ist kein 1:1-Bau (`800115BC`);
  ein Modul, das seinen Kopf 1:1 nennt, schliesst Nachbarn nicht ein (`8000F468`).
- **R229 gilt fuer jeden Marker:** „1:1|Rohinstruktionen“ allein uebersieht
  „Rohworte … CONFIRMED“ (FDC-Familie in `opmode_load.cpp`).
- **R224:** Rohwort-Dekodierung per Hand ist fehleranfaellig (`7C601814` =
  `addc r3,r0,r3`); im Zweifel `disassemble_bytes`.

## Vierte Belegquelle: bestaetigte Fundstellen (Batch 116, verifiziert)
`OpMode::fdc_block_stored` = FUN_8002BB0C (FDC-Familie, 9 Koepfe/1188 Insn),
`CfgBlock::load_factory_defaults` = **8000D5E8** (B114 hatte ihn falsch als
„nur Kommentare“ gefuehrt), Eintrags-/Datumsfamilie (`opmode_entry`/`payload`,
9 Koepfe), Textkette (6; `800115BC` Stand-in), `gun_volume` (6).
**Nicht adoptiert** (Einzelpruefung offen) — ehrliche Zahl dort = Obergrenze.

## R216 — die zweite Bau-Quelle fuehrt HAKEN als gebaut (Batch 114)
- `m101_content.built_set()` zieht die **neun** Adressen aus
  `m104_built.HOOK_CORRECTIONS` (Batch 104) **nicht** ab; der Vereinigungssatz
  gilt damit fuer neun Haken als "gebaut" — sie schneiden als vermeintlicher
  Rand die Huelle ab. Werkzeuge `m113_pick.py`/`m114_pass.py` bereinigen ihn.
- **Zehnter Fall:** `800599B8` (`mission_script::cursor_zero`, 4 Insn) steht in
  der zweiten Quelle als gebaut, in der gepflegten Liste nicht — er ist
  **wirklich gebaut** (Batch 114 adoptiert).
- **Breitenprobe (neu):** `m114_pass.py r216` indexiert alle Port-Quellen
  einmalig und prueft **jeden** Inventarkopf in beide Richtungen. Sie liefert
  **Fehltreffer** ueber die String-Literale von Hakenrufen
  (`h0(h, st, 0x…u, 0x8005CC54u, "FUN_8005CC54");`) und ueber Kommentare ohne
  `(`; Einstufung einzeln mit Belegzeile (R208).
- **Richtung-1-Fund Batch 114:** 21 Koepfe 1:1 gebaut, in keiner Liste (7 in
  der Huelle = 537 Insn); **nicht** adoptiert: klassengebunden
  (`8000CB40` `OpMode::wdt_kick`, `80008448` `OpMode::timebase`, R215).

## R216 — vierter Fall in Folge (Batch 110), und die 2a-Zahlen
- Von den zehn 2a-1-Knoten waren **vier** schon gebaut (`FUN_8001A054`
  `cursor_save`, `FUN_8002B000` `lzss_block`, `FUN_8002B394` `queue_enqueue`,
  `FUN_80017958` **nur halb** = nur Pfad 1; der zweite Pfad ist in Batch 110
  ergaenzt). **„Gebaut" heisst „alle Pfade des Rumpfes".**
- 2a-Kern (`closure 80029F50`): **36 Knoten**, nach Batch 110 **12 gebaut /
  24 offen** (17 mit `insn` = 681 Insn); darunter sind **mindestens drei schon
  gebaut** (`80017D80` `fbz_mode`, `80017DF0` `fbz_mode_bit`, `8001A074`
  `cursor_restore`) - die Zahl ist eine **Obergrenze**. Liste:
  `analysis/_m110_rest.txt`. Waehler-Gruppe unveraendert **52/45**.

## R244-R247 — Batch 118 (Textmass, Sprite-Ausgeber)
- **R244:** `FUN_800421AC` zaehlt **ZEILEN**, nicht Zeichen: einzige Erhoehung
  an `0x0A` (`80042210`), Abschnittsende an `0x0C` (`80042214`), Ergebnis =
  **Maximum** der Abschnitte; **leerer Text -> 1**, Zeiger 0 -> 0. Der Port
  nannte ihn bis B117 "Textlaenge"; Portname `mission::text_lines`.
- **R245:** in der Sprite-Zelle liegen die **Quellbytes bei Zelle+0..+3**
  (r,g,b,alpha), die **Farbe bei Zelle+4**. Wer `(Zelle-4)+4` adressiert
  (`lbz r3,0x4(r12)`), liest `+0`. `sprite_grid_color`/`sprite_label` lasen
  `+4..+7` = das **alte Farbwort** (in B118 korrigiert).
- **R246:** die **Alpha-Quelle** von `FUN_8000FF8C` ist **`Seitenbasis +
  Reihe*8`** (`lbzx r12,r11,r6`, `8001001C/20`) — die **erste Reihe einer
  Seite ist die ALPHA-ZEILE** (Reihe 0 -> Alpha 0). Nicht `Reihenbasis+Reihe*8`.
- **R247:** `scripts/m111_core.py unbaubar` (P100) misst **SPANNEN**, nicht
  Ruempfe: `8000FE78` meldet 151 statt **69** Insn, `80011A48` 12 statt **11**
  (4-B-Nullwort, R211). Laengen immer aus dem gemessenen Rumpf (R222);
  Grenzen in `m104_built.RANGES` fuehren.
- **B118-Zahlen:** Waehler-Gruppe **53/44** (unveraendert), ehrliche Gesamtzahl
  **148 offen / 3936 Insn / Unterbau 104 / GEBAUT 242**, Huelle (A) **169**;
  R207 **466**; Regression **32 + 208 Anker**; Modi **55/67**; Ghidra **2085**.
- **Anker-Namen:** `helpers-rom-anker` (jetzt 9 Zellen / 269 Woerter / 69
  Proben), **`helpers-textmass-anker`** (neu), `opmode-ladeteil-fall-anker`
  (jetzt 14/14 Faelle).

## R254-R260 — Batch 120 (Abfrage-/Balkensatz-Kranz der M0/M5-Waehler)
- **R254:** die Inventarspalte `insn` kann **zu klein** sein UND die `size`-Spanne
  einen **verdeckten Nachbarn** tragen — `FUN_800267B0`: Spalte 30, gemessener
  Rumpf **243** (`0x800267B0..0x80026B7C`, zwei Ruecklaeufe), Spanne 1156 B mit
  eigenem Prolog bei `0x80026B84`. Beide Grenzen fuehren
  (`m111_core.MEASURED_END`) — die Linie R249/R212 bekommt damit ihre vierte
  Auspraegung.
- **R255:** der **Slot-Schluessel IST die Objektkennung**: `slot + 4*a + 0x44`
  (Abfrage) ist **dieselbe Zelle** wie das Slotfeld, das der Kopf als `index` an
  den Balkensatz reicht (R218-Klasse: ein Sandkasten sieht das nicht).
- **R256:** **Rueckgabe 2 der Einrichtungsabfrage ist der OR-Zweig**
  (`obj+8 |= 0x981`), Rueckgabe 1 **loescht**; der Name der Abfrage beschreibt
  nicht die Wirkung beim Aufrufer.
- **R257:** das Tor `[SDA(0x220)]+8` Bit 23 entscheidet den „Eintrag auf -1“-Weg
  und ist **dasselbe Wort** wie `obj+8`.
- **R258:** die T3-Tafel zeigt auf das **Gehaeuse** des Falles
  (`0x80054D34`, nicht die Rufadresse `0x80054D50`) — R240-Klasse, dritter Fall.
  Waehler-Verteiler: **T3 laeuft nur bei Zeitgeber <= 0, T4 nur bei > 0** (R259).
- **R260:** **negative Immediates** (`0xFFFF8000`, `0xFFFFF67E`, `0xFFFFFC18`)
  meldet die P100-Argumentprobe als „Adressen“ — Fehltreffer; Positivkontrolle
  `8005C168` zeigt den Unterschied.
- **B120-Zahlen:** Waehler-Gruppe **64/33** (aus 60/37), ehrliche Gesamtzahl
  **128 offen / 3554 Insn / 4000 B (nur `size`) / GEBAUT 262 / Unterbau 95**;
  Huelle (B) **390**; Huelle (A) **157 Knoten, offen 59** (B119-Doku nannte 169 —
  die gepflegte Bau-Liste/R207 479→**492** ist die harte Basis); ABI (A) **147**;
  R207 `check` **492/0**; Regression **32 + 214 Anker**; Modi **55/64**;
  Ghidra **2085**.
- **Anker-Namen:** `vmsg-anker` (378 Woerter), `vmsg-wire-anker`,
  `vmsg-grenzen-anker`; Modus `vmsg`; Werkzeug `scripts/m120_msg.py`.
- **Lehre (R194):** ein verdrahteter Haken wird zum Wirkungs-Anker (`v == nullptr`
  **und** `msg_stats().view_calls == 1`) — sonst bleibt der Anker gruen, obwohl
  nur noch der Haken laeuft.

## R271-R274 — Batch 123 (K037122-/VBI-/Commit-Kette)

- **R271 (DER FUND):** eine **Inventarspanne um einen Host-/Trampolin-Kopf ist
  eine Huellen-FALLE** und sie ist **stumm** (R207 (b) bleibt leer).
  `8000005C` (Deskriptor-Trampolin): Spanne **32684 B**, Rumpf **5 Insn**
  (`lwz r0,0(r11)`/`stw r2,0x14(r1)`/`mtspr CTR,r0`/`lwz r2,4(r11)`/`bcctr`),
  danach 4-B-Nullwort bei `0x80000070`. Wirkung: Huelle des Strangs `800115BC`
  58/43 statt **14/13**; volle Waehler-Huelle (B) 390/113/2868 Insn statt
  **332/85/2289**; (A) 152/57 unveraendert (der Trampolin wird in (A) nicht
  erreicht). Fix: `8000005C: 0x80000070` in `m111_core.MEASURED_END` **und**
  `m104_built.RANGES`; `m112_ast.closure_all` von `C103.true_end` auf
  `C111.body_end` umgestellt. Belege `analysis/_m123_trampfix.txt`,
  `_m123_hullB.txt`, `_m123_strand.txt`, `_m123_parts.txt`.
- **R272 (eigener Fehler):** ein Pruefwert, der durch eine ROM-Maske laeuft, ist
  nicht der Wert — `0x400 & 0x3FF = 0`, der Wartezweig von `FUN_800100D4` lief
  leer (R260-Klasse, zweite Auspraegung).
- **R273 (eigener Fehler):** der Anker-Sandkasten setzte Zustands- **und**
  Frame-Zelle EINSTUFG auf → `PortFault: read32 ausserhalb RAM @ 0x14/0x1C`;
  beide Ketten sind ZWEISTUFIG (R218/R223).
- **R274 (Metrik-Hygiene):** eine benannte `name = 0x…;`-Konstante, die ein
  Anker in `reg.add` haengt, zaehlt in der ABI-Sonde (`m115_pass.py abi`) als
  Bau-Beleg — Nicht-ROM-Adressen als **Zahl** eintragen.
- **Eigene Fehler des neuen Wortinterpreters** (`scripts/m123_ref.py`, R219):
  (a) `addi`/`li` mit `RA == 0` nimmt die **Konstante 0** — R217 gilt NUR fuer
  `addic`/`subfic`; (b) `bdz`/`bdnz` haengen an **BO-Bit 0x02** (BO 16 =
  `bdnz`, BO 18 = `bdz`), nicht an 0x08. Beide erst durch die **Zufallsprobe
  gegen das Regelmodell** gefunden (1774 bzw. 319 Abweichungen, danach 0/2000).
- **B123-Zahlen:** Waehler-Gruppe **65/32** und der Bau **±0** (die sechs
  Koepfe liegen ausserhalb beider Huellen); ehrliche Gesamtzahl **85 offen /
  2289 Insn / 1884 B (nur `size`) / GEBAUT 283**; Huelle (B) **332**, (A)
  **152/95/57**; R207 **513** (25/0/0); ABI **167**; Regression **32 + 224**;
  Modi **73**; 2a-Kern **1/8** (die Zahl 28/8 ist ueberholt — die Wurzel
  `80029F50` ist seit Batch 112 gebaut, die Closure schneidet dort ab; mit und
  ohne die neue Grenze identisch gemessen).
- **Anker-Namen:** `fcom-anker`, `fcom-status-anker`, `fcom-grenzen-anker`,
  `fcom-wire-anker`; Modus `fcom`; Werkzeuge `scripts/m123_commit.py`,
  `m123_strand.py`, `m123_probe.py`, `m123_ref.py`.
- **Offen:** die **neun** `0x80057E2C`-Stellen in `mission_script.cpp`
  (Auftragspunkt 5 aus 122 UND 123, zweimal nicht erreicht), die acht uebrigen
  Rufstellen der Formatierer-Wurzel, die Rufer `80008668`/`80008828`/`800089A0`;
  **`[SDA(0xB4)]`: achter Batch ohne Beleg**.

## R275-R280 — Batch 124 (VBI-Eingang der Kette)

- **R275 (DER FUND):** eine **4-Insn-HELFERFAMILIE in EINER Inventarspanne**
  ist die R271-Falle in neuer Besetzung. `FUN_800084C4`: Spanne **176 B**,
  Rumpf **4 Insn**; darunter **zwoelf** verdeckte Helfer derselben Bauart
  (`mfdcr EXIER` / Maske / `mtdcr EXIER` / `blr`, `0x800084D4..0x80008584`),
  **vier** mit Rufstellen — alle in OFFENEN `0x80013xxx`-Koepfen. Dazu
  `FUN_80023AF0`: Spanne 128 B, Rumpf 124 B + **4-B-NULLWORT** (R211).
  Grenzen in `RANGES` **und** `MEASURED_END`.
  **Also: an JEDEM neuen Kandidaten die Spanne gegen den Rumpf pruefen.**
- **R276 (eigener Fehler, R272 zum ZWEITEN Mal):** ein Pruefwert, der durch
  eine ROM-Maske laeuft, ist nicht der Wert — `0x400 & 0x3FF = 0`; richtig ist
  `0x3FA..0x3FF`.
- **R277:** `cmpwi` ist **SIGNIERT** — `0xFFFFFFFF` („keine Mehrheit") ist
  **nicht** `> 0x3F9`. Port: `(i32)status > 0x3F9`.
- **R278 (eigener Fehler):** den **Namensraum eines Wirts NICHT aus dem
  Praefix** schliessen: `dbk::DisplayBank` gibt es nicht — die Klasse liegt in
  `port`, `dbk` traegt nur die Konstanten (Bau brach mit
  „'DisplayBank' in namespace 'port::dbk' does not name a type").
- **R279:** die Zeitgeber-Ladungen an den `0x80057E2C`-Stellen sind **`lha`**
  (signiert); `read16` ist wirkungsgleich (nur das halbe Wort wird gespeichert),
  aber nicht exakt → `read_s16`.
- **R280:** ein Haken auf ein **gebautes** Ziel in einem **UNGEBAUTEN**
  Inventarkopf gilt der Nachzuegler-Sonde (`m104_built.py nachzuegler`) als
  „(b) erwartet" — eine offene Verdrahtung bleibt dadurch **unsichtbar**.
- **R147/R148:** greift ein neuer Kopf in einen bereits gebauten Wirt, wird der
  Wirt **ECHT gefahren** — und **alle** seine Zugriffe muessen mit:
  `bank_helper` macht **DREI** DCR-Zugriffe (nicht zwei), R194-Sollwert 5 → 6.
- **B124-Zahlen:** Waehler-Gruppe **65/32** und 2a-Kern **1/8** unveraendert;
  ehrliche Gesamtzahl **83 offen / 2285 Insn / 1884 B (`size`) / GEBAUT in (A)
  95**; Huelle (B) **332**; R207 **518** (25/0/0); ABI **172**; Regression
  **32 + 229**; Modi **74**; Ghidra **2085**.
- **Anker-Namen:** `vbi-anker`, `vbi-status-anker`, `vbi-lampe-anker`,
  `vbi-wire-anker`, `vbi-grenzen-anker`; Modus `vbi`; Werkzeuge
  `scripts/m124_vbi.py`, `m124_callers.py`.
- **Offen:** die acht uebrigen Rufstellen der Formatierer-Wurzel (in der
  **20-Knoten**-Huelle von `80008668`), die zwei verbleibenden Rufer als eigene
  Straenge (`80008668` 20/242, `800089A0` 197/9662), der **Vektor-Kopf
  `0x80000500`** (48 Insn, EVPR+0x500, un-inventarisiert) — ohne ihn ist die
  Verdrahtung von `80008668`/`80008828` **an der Originalstelle** nicht
  moeglich; **`[SDA(0xB4)]`: neunter Batch ohne Beleg**.

## R265-R270 — Batch 122 (Text-Formatierer-Familie `800115BC`)

- **R265 (eigener Fehler):** der Parserzeiger eines `%`-Interpreters wird im ROM
  **VOR** der Verzweigung erhoeht (`FUN_800115BC`: `8001162C addic r30,r30,1`
  **vor** `80011630 beq`) — er laeuft auf BEIDEN Wegen. Wer ihn nur im `%`-Zweig
  weiterrueckt, laeuft bei Klartext **ohne** `%` **endlos** (der eigene Anker
  starb mit `std::bad_alloc`).
- **R266 (eigener Fehler):** die Ziffernfenster bekommen ihren **Basiszeiger als
  ARGUMENT** — `addic r3,r1,0x18` fuer die Zahlen, `addic r3,r10,0x1e` fuer den
  **BRUCHTEIL** des `%f`-Pfades. Ein fest verdrahteter Fensteranfang liess die
  Bruchziffern von der Ganzzahl ueberschreiben (`0.00000` statt `0.50000`).
- **R267:** Ghidras gedruckte `rlwinm`-**Maske** kann FALSCH sein: `800110B4`
  (`0x54632834`, SH=5, MB=0, ME=26 -> Maske `0xFFFFFFE0`) erscheint im Dekompilat
  als `(v*0x20 & 0x7ffe0)`. Immer aus den **BYTES** rechnen (`rlwinm(x,sh,mb,me)`
  mit MB/ME aus dem Wort) — R224-Klasse, zweiter Fall.
- **R268:** der `l`-Modifikator ist **WIRKUNGSLOS**: der Compiler legt die Marke
  in `CR4[SO]` ab (`800115FC crxor cr4[eq]` / `80011600 creqv cr4[so]`;
  `800117F4 cror cr6[lt],cr4[so],cr4[so]`; `bge cr6` fragt ab), und an ALLEN
  sieben Abfragestellen (`8001183C/68/B4/E8/938/974/C4`) sind beide Zweige
  **instruktionsgleich**. Port: parsen, ZAEHLEN, keine Bedeutung raten.
- **R269 (eigener Fehler):** der WIRT muss `'\n'` **durchlassen** (Umbruch der
  Textmasse) und nur Bytes >= 0x80 durch `.` ersetzen (P73). Eine zu strenge
  Bytemaskierung bricht die Dialogtexte (gefunden vom
  `service-dialog-verhalten-anker`).
- **R270:** `%s` fuellt im ROM **HINTEN** (`80011368` zaehlt `count+1` bis zur
  Breite) und **SCHNEIDET** bei der Breite ab (`80011334 bge`) = **LINKS-buendig**;
  die Zahlen faellen dagegen VORNE auf (`80011290`/`800112A0`). Der ersetzte
  Stand-in richtete `%s` rechtsbuendig aus — die Portanker hatten das mit
  `trim()` verdeckt.
- **R222-Feinheit (neu):** endet ein Rumpf auf einem FREMDEN 1-Instruktions-`blr`
  (`0x80011470`/`D0`/`0x8001155C`), ist der Spannenrand schon der naechste
  Inventarkopf und das LETZTE SPANNENWORT ist der Ruecklauf -> **kein**
  `RANGES`-Eintrag (sonst meldet `sanity` != 0). Unterschied zu `0x80011A48`
  (Batch 118), wo hinter dem Ruecklauf ein 4-B-NULLWORT stand.
- **B122-Zahlen:** Waehler-Gruppe **65/32**, 2a-Kern **28/8** (unveraendert);
  ehrliche Gesamtzahl **113 offen / 2868 Insn / 3220 B (nur `size`) / GEBAUT 277**;
  Huelle (B) **390**; R207 **507** (25/0/0); ABI **161**; Regression **32 + 220**;
  Modi **72**; Ghidra **2085**.
- **Anker-Namen:** `textfmt-anker`, `textfmt-ziffern-anker`,
  `textfmt-grenzen-anker`, `textfmt-wire-anker`; Modus `textfmt`; Werkzeuge
  `scripts/m122_scan.py`, `m122_text.py`, `m122_ref.py` (unabhaengiger
  Wortinterpreter, R219).

## R285-R288 — Batch 126 (verdeckter Weg `8001573C` -> `800152B8`)

- **R285 (eigener Werkzeugfehler, im ersten Ankerlauf gefunden):** ein Pruefwert
  fuer eine **ZWEISTUFIGE Zelle** (R218) muss auch die **zweite Stufe** setzen.
  Der Sandkasten schrieb `[SDA(0x28)] = W`; der Kopf liest `W = *(*(r2+0x28))`,
  fand **0** und griff auf `0 + 0xB568` (ausserhalb des Abbilds) zu — vier
  Verhaltensfaelle fielen um, die Diagnose war `no_bus != 0`. **Zusatzregel:**
  `W + 0xB568` muss **im Abbild** liegen (der Anker legt W nach `0x803F4000`).
- **R286:** bei Formatstrecken macht `"%c%d"` + ein Buchstabe je Satz
  **Zeichen, Akkumulator UND Auswahlweg** in EINER Ausgabe lesbar
  (`" 10"`..`" 13"`) — ohne diesen Trick sind die drei Auswahlwege nur ueber
  Umwege unterscheidbar.
- **R287:** die Fuellschleife von `FUN_80012A94` (`stbu` + Probe auf das
  NAECHSTE Byte) **verlaengert nicht** — sie ersetzt die Zeichenkette durch
  **Leerzeichen GLEICHER Laenge** (Terminator bleibt stehen).
- **R288:** ein `stub`-Tail (`0x80015738`) wird vom Vollbildzensus dem
  Inventarkopf seiner **Spanne** zugeschlagen (`8001572C`) — Rufstellenzahlen
  immer mit der Spanne des Nachbarn lesen (R201/R222-Linie, vierte Auspraegung).
- **CONFIRMED [SDA(0xB4)]:** der „Anzeigeslot-Satz" von Batch 124/125 IST der
  **Zielsatz** `game_flow.h::kSdaAim` („Zielsaetze, Schritt 14"): der neue Kopf
  liest je Satz i `s16` bei `+0x0E/+0x10/+0x12` ab `[SDA]+4+0x0E*i` =
  `+0x12/+0x14/+0x16` von Satz 0 — feldgenau dieselben Zellen wie das GEBAUTE
  `flow::aim_value` (`+0x12`) und `flow::aim_sum` (`+0x14`+`+0x16`). Der
  Akkumulator des Kopfs ist die Summe der zwei Kanal-Zielwerte.
- **Metrik:** die Ghidra-Funktionszahl wird ab B126 **gemessen**
  (`GET /list_functions?limit=5000`, Zeilen mit `" at "`), nicht kopiert:
  **2090** (Dokumente fuehren 2085 = Altkopie). `disassemble_bytes` in einem
  Code-Gap hat hier **keine** Funktion angelegt (Stub `0x80015734` bleibt
  funktionslos) — Gegenbeleg zur pauschalen Batch-77-Regel.

## R281-R284 — Batch 125 (Bildtakt-Geber `80008668`)

- **R281 (eigener Fehler — R219-Klasse):** ein Pruefwert fuer ein **Bitanlegen**
  darf das Bit NICHT enthalten. Mein MSR-Fall startete mit `0xA000` (enthaelt
  `0x8000`), erwartete `0xA800` und verdaechtigte lange das Modul — erst die
  **Literalprobe** `0xA000 | 0x8000 = 0xA000` zeigte den Denkfehler.
  **Regel: jeden Verdacht zuerst gegen einen LITERALWERT rechnen.**
- **R282 (DER FUND, R148):** `[SDA(0x0B0)]` ist das **E/A-OBJEKT**
  (`input_layer.h`: `0x800B3928`, `+0x1C` -> **`cfg+0x30`** = das
  **EINGABEWORT**). `FUN_80015630` liest dort sein „Blinkfeld"
  (`+0x1C + idx*0x22`, Bits 15..12) — fuer **Slot 0 ist das das Eingabewort**;
  die Waffeneingabe faehrt dieselbe Zelle. Dieselbe Zelle traegt `+0x57`
  (Lampenquelle, Batch 124). Ein Pruefwert dort wird vom Abfragepfad
  **genullt**.
- **R283:** ein **Blinkzaehler und eine Abzugszelle koennen DIESELBE Zelle
  sein** (`row + gate*0x0E + 0`): die Blinkstufe erhoeht sie um 1, die
  Auswahl (`select_apply`) braucht danach **eine Runde mehr** (Sollwert 3
  statt 2). Sollwerte aus der **Reihenfolge** der Rufe ableiten.
- **R284 (R271/R275, dritte Auspraegung):** eine Huellenmessung ueber die
  **Inventarspanne** eines Kopfs mit **verdecktem Nachbarn** zieht fremde
  Zweige herein (`8001572C`: Spanne 16 B, Rumpf 2 Insn, dahinter der Stub
  `0x80015734` -> +6 Knoten/298 Insn aus dem Weg `0x8001573C` -> `800152B8`).
  **Zusaetzlich** kann die `insn`-Basis eine **Untergrenze** sein (acht Knoten
  ohne Spalte: 238 Basis gegen **577 GEMESSEN**). Immer Rumpf gegen Spanne
  JEDES Knotens stellen.
- **B125-Zahlen:** Waehler-Gruppe **65/32** und 2a-Kern **1/8** unveraendert
  (nur `80011EAC` liegt in der vollen Huelle (B)); ehrliche Gesamtzahl
  **82 offen / 2276 Insn / 1884 B (`size`) / GEBAUT in (A) 95**; Huelle (B)
  **332**; R207 **529** (26/0/0); ABI **183**; Regression **32 + 235**;
  Modi **74** (mit `tick`); Ghidra **2085**.
- **Anker-Namen:** `tick-anker`, `tick-motor-anker`, `tick-lampe-anker`,
  `tick-slot-anker`, `tick-grenzen-anker`, `tick-wire-anker`; Modus `tick`;
  Werkzeug `scripts/m125_tick.py` (`dis`/`words`/`check`/`deps`/`stub`/`hull`).
- **Offen:** der verdeckte Weg `8001573C` + `800152B8`/`80012A94`/`80010704`/
  `80011560`/`8000D1C4` (eigener Strang, Haken `kFnShowCall` in
  `game_flow.cpp`), Boot-Rufer `800089A0` (197/9662), Vektor-Kopf `0x80000500`;
  **`[SDA(0xB4)]`: zehnter Batch ohne Beleg.**

## R290-R292 — Batch 127 (Einzelpruefung der 857 RAM-Insn der Boot-Huelle)

- **R290 (eigener Werkzeugfehler, DER FUND, behoben):** eine Vorwaertsanalyse
  darf ein Register **NUR** loeschen, wenn das Feld nachweislich ein
  Zielregister ist. `m111_core.const_flow` loeschte `const[rt]` fuer jede nicht
  erkannte Instruktion — auch fuer `cmp`/`cmpl` (op 31 XO 0/32),
  `cmpi`/`cmpli` (op 10/11, Bits 21..25 = **BF**), `bc`/`b`/`bclr`
  (op 16/18/19, **BO/LI**), `sc` (17) und Gleitkomma (59/63, **FRT**).
  Bei `BF == 0` bzw. passenden LI-Bits traf es **r0**; mit **R217**
  (`addic` mit `RA = 0` liest **r0**) verlor `lis r0,0x7400` +
  `addic r5,r0,-0x4070` seine Basis — `sth r7,0x4090(r5)` nach **`0x74000020`**
  galt als „nur RAM". Falle ist **stumm**. Fix in der **Bibliothek**
  (`_NO_RT`/`_no_rt`), Tragweite gemessen: **12 von 2072** Koepfen gewinnen
  IO-Treffer (`8000CA7C`, `8000CE14`, `8000E690`, `8000E6BC`, `80012984`,
  `80013A88`, `80022FA4`, `8002403C`, `80025478`, `8002D644`, `80038358`,
  `8005E280`) — nur **1** Klassenwechsel. Boot-Huelle: H **160/10400**,
  R **31/819 (7 %)**, vorher 32/857 (8 %).
- **R291 (eigener Fehler):** eine **Spanne ist keine Rumpflaenge**.
  `m111_core.body_end` liefert ohne `MEASURED_END`-Eintrag die Strecke bis zum
  naechsten Inventarkopf — fuer `80018D4C` **220 Insn**, obwohl der Kopf ein
  **1-Insn-Thunk** ist (`b 0x80016758`, `insn`-Spalte = 1). `split` zeigt
  **20 Segmente / 19 verdeckte Koepfe** darunter. Regel: vor jeder Klassen-/
  Schnittgroesse die Spanne mit `m127_bootram.py split` absuchen
  (R271/R275/R284 — hier in eigener Sache).
- **R292:** **0 direkte Zweigziele** im Vollbild sind kein Beweis, aber der
  Regelfall fuer toten Code (`80010B30`, `80010BA4`, `80010C90`) — als
  **HYPOTHESIS** fuehren und **nicht bauen** (ein `bctr` waere unsichtbar);
  wie der Stub `0x80015734` aus Batch 125.
- **Zweiter Kandidat (die sechs uebrigen Rufstellen der Formatierer-Wurzel
  `800115BC`) ist KEIN R147-Stand** — drei unabhaengige Gruende:
  (a) **`800107F0` hat einen Eigentuemer**: `TextLayer::text_at_cursor`
  (`port/src/text_layer.cpp:269`, P73), gefahren vom GEBAUTEN `FUN_8003C9FC`
  (`paket_d.cpp`); ein 1:1-Bau waere ein **zweiter Wert fuer dieselbe
  ROM-Adresse** (R148) und braucht eine Eigentuemer-Entscheidung.
  (b) **drei Koepfe mit 0 Rufstellen** (`80010B30` 29, `80010BA4` 59,
  `80010C90` 21). (c) **`80010C90` zieht zwei Koepfe OHNE Inventareintrag**
  herein (`80010390`, `80011BD8`). Bleibt: die **drei erreichbaren** Koepfe
  `80010690` (29) + `800107F0` (21) + `80010A20` (68) = **118 Insn**
  (Zellen `[SDA(0x54)]` Textring, `[SDA(0x58)]` Ausgabekette, **`[SDA(0x5c)]`
  im Port noch unbenannt**).
- **Klasse-R-Insn der Boot-Huelle sind generischer Unterbau** (PRNG
  `80008CD0` = LCG mit `0x5D588B65`/`0x0019660D`, `strcmp` `8000D2C8`,
  Shift-JIS-Scanner `80013918`, Binaer-/Hex-/Dezimal-ASCII
  `80014258`/`80014284`/`800142B4`, Sortier-Einfuegen `800174DC`,
  Byte→16-Bit-Weitung `80011C70`, Helferblock `80008058`) — **0 von 31**
  Knoten sind fuer M0/M5 relevant (nicht in Huelle B, keine 97er-Ziele).
  Ehrliche Zahl der Knoten-Insn: **600 in 30 Koepfen** (857 − 38 − 219).
- **Buchfuehrungskorrektur:** die R216-Modulkopf-Zahl aus Batch 126 (**87**)
  war **eins zu niedrig** — gemessen **88** (zwei Adresszeilen stammen aus
  `slot_show.cpp`).
- **B127-Zahlen:** kein Bau, deshalb ehrliche Gesamtzahl unveraendert
  **81 offen / 2266 Insn / 1884 B (`size`) / GEBAUT in (A) 96**; Huelle (B)
  **332**; Waehler-Gruppe **65/32**; 2a-Kern **1/8**; R207 **535** (27/0/0);
  ABI **188**; Regression **32 + 238**; Modi **75**; Ghidra **2090 gemessen /
  2085 dokumentiert** (nur lesende Zugriffe).
- **Werkzeug:** `scripts/m127_bootram.py` (`list`/`cuts`/`r222`/`calls`/`dis`/
  `disall`/`cells`/`hw`/`bootfix`/`split`/`words`); Belege `analysis/_m127_*.txt`.
- **Naechster Waehler-naher Schnitt (nicht die Boot-Huelle):** der **2a-Kern**
  `800294E0` (103) / `800297A0` (38, Naht `0xFF1FCA08`) / `80029958` /
  `80029D0C` (**1 von 8 gebaut**) plus `8005865C` (36) / `800545E0` (136).

## R310-R316 — Batches 130-133 (Waehler-Huellen, Fahne 0x200, Faecher-Sweep)

- **R310 (Bau, Batch 132):** der Port baut ueber **`Makefile` +
  `mingw32-make -j16`** (inkrementell, `-MMD -MP`; Clean 13,7 s, 1 Datei
  1,06 s, Header 78 TUs 7,73 s). Zwei Windows-Fallstricke: (a) ohne Metazeichen
  startet make die Rezeptzeile **direkt, ohne Shell** -> `SHELL` festnageln und
  `msys64/usr/bin` in den PATH des Rezepts; (b) in einem **Skript** expandiert
  PowerShell 5.1 die Variable in einem mit `-` beginnenden Token nicht
  (`& $make -j$jobs` -> Option als Zeichenkette bauen).
- **R311 (Batch 132, eigener Fehler):** die **logische D-Form** ist
  `rS` = **QUELLE** (MSB 6..10), `rA` = **ZIEL** (MSB 11..15) - der
  Wortinterpreter las sie vertauscht. **Still**, weil alle bisherigen Stellen
  `rX,rX` benutzten (`oris r0,r0,8`, `ori r0,r0,2`); erst `ori r3,r30,0x200`
  trennt die Felder. Beleg: 27/27 Altfaelle byte-identisch.
- **R312 (Batch 132):** die `mtcrf`-Maske allgemein: CRM-Bit `2^k` -> **CR(7-k)**,
  Daten = Nibble der **LSB-Bits 4k..4k+3** (CRM `0x04` -> CR5, CR5.EQ = Wort-Bit
  `0x200`; CRM `0x01` -> CR7, CR7.SO = **Bit 0**).
- **R313 (Batch 132, fremdes Modul, behoben):** **R187 gilt auch fuer
  ABGELEITETE Basen** - wer eine Zelle als Basis liest, muss die **Basis** vor
  dem Zugriff mitpruefen (`counter_scale` las `ctx+0x12` ungeprueft ->
  `PortFault: read8 @ 0x12`).
- **R314 (Batch 133, eigener WERKZEUGfehler, behoben):** **16-Bit-Verschiebungen
  der D-Form sind vorzeichenrichtig** (`simm16(w)`); `s32(w & 0xFFFF)` ist
  **keine** Verlaengerung (`stwu r1,-80(r1)` rechnete `0 + 65456`). Zwei
  Batches **still**, weil kein interpretierter Kopf je einen ueber eine
  **negative** Verschiebung gespeicherten Wert **zurueckgelesen** hat; sichtbar
  erst an der LR-Rettung ueber den Stapel (`stw r0,8(r1)` / `lwz r12,0x48(r1)`)
  - die Rueckkehr brach zusammen (Rueckgabe `FFFFFFFC` statt `8028DB00`,
  100 statt 615 Schritte). Korrektur in `scripts/m130_ref.py` (12 Stellen);
  **Gegenprobe: die 33 Altfaelle der Erwartungstafel blieben byte-identisch**.
  Merksatz: ein Interpreter, dessen Speichern und Laden auf VERSCHIEDENE
  Adressen zeigt, faellt erst beim Zuruecklesen auf.
- **R315 (Batch 133, FUND in GEBAUTEM Code, behoben):** ein **`stw` schreibt
  ein VOLLES Wort** - `static_cast<u16>(fl | kNib7SO)` vor einem `write32`
  **nullt die obere Haelfte** von `slot+0x40` (ROM: `ori r5,r5,0x1` + `stw`).
  R311-Klasse: still, weil die obere Haelfte in allen bisherigen Faellen 0 war.
- **R316 (Batch 133):** eine Huelle mit **`stop = gebaut` ist NICHT monoton**:
  mit dem Bau eines Knotens koennen seine Kinder aus der Huelle **fallen**
  (`8003B334` lag in (A) nur am offenen `8003B184`) - **+1 gebaut, -1 offen,
  -1 Knoten** ist ein korrektes Delta. Nachrechnen mit `closure_all(targets,
  built)` mit/ohne den neuen Kopf in der Bau-Liste.
- **R219-Erweiterung (Batch 133):** der **Beobachter `WATCH`** in
  `m130_ref.py` fuehrt die gerufene ROM-Kette **selbst** aus (kein Stub) und
  zaehlt nur die **Eintritte** - die Rufzahl wird damit ein MESSWERT der
  ROM-Kette; das erzeugte Feld heisst `call_n_want`.
- **B133-Zahlen:** Waehler-Gruppe **82/15**; Huelle (A) **108/36**; volle
  Huelle (B) **279/53** (offen 1711 Insn + **976 B** `size`-nur); nur Unterbau
  **38/1302**; 2a-Kern 0 offen; R207 **564** (29/0/0); R216 A **217**, B 83,
  C 85, D 643/129; Inventar (R308, 2026-09-23) S1 **1648** (79,5 %) / Rest
  **424**; Modi **78**; Regression **32 + 254**.
