# Missionsebene (Batch 95, CONFIRMED aus Rohworten)

# Batch 106: DER R148-VERDRAHTUNGS-BATCH (CONFIRMED, 2026-09-22)

- **Kein Bau** - 17 Hakenstellen in sechs Modulen verdrahtet:
  `mission_content.cpp` 4 (0x80030164 -> `m6_rand_aim`, 0x8003019C ->
  `cell_640_init`, 0x8006447C/0x800654E0 -> `result::tbl_read`),
  `mission_script.cpp` 3 (0x80058010/0x80057D4C -> `counter_scale`,
  0x8005803C -> `flag_blk_init`), `mission34_family.cpp` 4 (0x80064E70/EB4 ->
  `msg_arm`, 0x80065364/7C -> `snd_pair_init`), `mission2_family.cpp` 3
  (0x80063B94/0x80063E20/0x80063FE8 -> `flow::sound_wire`),
  `mission_services.cpp` 1 (0x8003B5F0 -> `sound_wire`),
  `mission_helpers.cpp` 2 (0x800434E4 -> `sound_wire`, 0x80043504 ->
  `sound_id`).
- **R214:** der Hakenzensus war zu klein - das Muster `\bh[0-9]?\(` uebersieht
  **`hk(`**; 15 -> **18** Stellen (sechstes Modul `mission_helpers.cpp`).
  **R215:** die 18. (0x800434B8) bleibt Haken, weil `FUN_8000F1E0` =
  `OpMode::pool_fill_rect` **klassengebunden** ist.
- **Anker (R194):** (118) 15/15, (121) 41/41, (125) 14/14, (130) 4/4,
  (133) 14/14, (134) 10/10; `content-ui` M2 **Haken 3 -> 2** (der Haken stand
  als Bedingung und wurde auch im Nichttreffer-Fall gezaehlt). Zwei neue
  Regressionsanker `wire106-family-anker`/`wire106-m34-anker`.
  **Regression 32 + 175 Anker, 0 Fehler**; 45/45 Modi Exit 0.

- **Missionstafel 0x800A03C8**, 7 Eintraege (Deskriptoren 94..100 des Pools
  0x800ACB08), **kein Bildwort zeigt darauf**: sie ist `[SDA(0x398)] = 0x800A03A8` **+0x20** (R165).
  0..6 = FUN_8005A5A4 (Phase 1), FUN_80063648, FUN_80064348, FUN_80064F4C,
  FUN_80065454, FUN_8005471C (Phase 5), FUN_8002FEE8.
- **Missionslaeufer FUN_80058C7C** (128 B) = Glied 12 der 25 Aufrufe des
  Szenenabbaus (0x8003D068). **Zwei Slots** (Schritt 132) ab `[SDA(0x524)] = 0x80126998`:
  Tor = u16 `+0x0C` Bit 0, Index = s16 `+0x0A`, Ziel = Tafel[Index] ueber
  Trampolin FUN_8000005C mit dem **Slot als r3**. **Kein Schrankentest.**
  Slot-Felder: +0 Zustand, +0x0E Zeitgeber, +0x16/18 x/y, +0x1E/0x20 Wert,
  +0x28 Haltezaehler, +0x40 Missionsflags, +0x5C, +0x78 Eintrittszaehler.
  Live: Slot 0 Zustand 1, Index 0, Tor 0x0007 (Mission 0 laeuft).
- **Phasenwahl (CONFIRMED):** FUN_8005471C Slot-Zustand 2 (0x80054B48) -> Tor
  FUN_80060938() = `(s8)*([SDA(0x444)]+0x70)`; bei 0 -> `li r3,5` +
  FUN_80041F54 (0x80054B78) + `obj+8 |= 0x4100` + `Slot+0x40 |= 4`.
  FUN_8005A5A4 Slot-Zustand 2, Ereignis (0x8005AA44) -> `li r3,1` +
  FUN_80041F54 + `obj+8 |= 0x4000`. **Beide setzen Bit 14** = das Tor, das der
  Abbau FUN_8003CF0C prueft.
- **Byte 0 == 1 des Bildschirmrumpfs schreibt FUN_80041CCC** (der gemeinsame
  Vorschub, 348 B): bei `Block[1] == 2` laeuft `li r4,0` (0x80041D04) in
  `state_inc(Block,0)` (0x80041E0C). Stufen: Block[1] 0 -> 1 -> 2.
  Argument-Nibble (R168): Bit 0 = Einzelweg/dreistufig, Bit 1 (CR7.EQ, das 2
  UND 3 tragen) = Wertesatz (+0x0E = 29). Text "select" = [SDA(0x268)]+0x84C.
- **Umfang:** 13 Missionsfunktionen = **10308 B / 2577 Instruktionen**
  (2 Waehler allein 4756 B); 5 Vorschubziele = 544 B / 136 Instruktionen.
  Gebaut: FUN_80058C7C + FUN_80041CCC (476 B / 117 Insn).
- **Port:** `port/src/mission_script.cpp` (`port::mission::run_slots`),
  `result::screen_advance` in game_result.cpp, `flow::call_desc` oeffentlich;
  Anker (114)-(116) in mission_check.cpp; Modi `mission`/`mission-ui`.
- **Ghidra 2085 unveraendert**, Regression 32 + 134 Anker = 0 Fehler (Batch 95).

# Batch 96: DIE ZWEI PHASENWAEHLER (CONFIRMED)

- **Groesse (R170):** die Inventarspalte `size` ist der analysierte Rumpf, `ext`
  die echte Grenze. FUN_8005A5A4 = **2644 B / 661 Insn**, FUN_8005471C =
  **3344 B / 836 Insn** (zusammen 5988 B / 1497; 95 nannte 4756/1189).
  **Die Sprungtafeln zeigen hinter `size`** (T2[0]=0x8005AEBC, T3[33]=0x800553B0).
- **Aufbau:** Zustandsmaschen ueber `Slot+0x00` (0 Init, 1 Hauptlauf, 2 Ausstieg,
  3/4 Fremdinhalte). Hauptlauf: Zeitgeber `Slot+0x0E`; >0 -> herunterzaehlen +
  Laufzeitverteiler, sonst Abschnittsverteiler ueber den Typ.
- **Aufzeichnung = 8 Byte** bei `Zelle + obj+0x72*8 + Versatz`
  (M0 `[SDA(0x39C)]`=0x800A0418 +0x80; M5 `[SDA(0x374)]`=0x8009FFD8 +0xF8):
  +0 s16 Typ, +2 s16 Startzeitgeber, +4 s16 Ereigniszeitgeber, +6 u8 Kennung,
  +7 u8 Flaggen (Bit0/1), +0x0A s16 Sprungzeitgeber. Live 123/123 + 82/82 gleich.
- **Vier Sprungtafeln:** T1 `[SDA(0x3A0)]`=0x800893A8 +0x10 (14, Typ 0..13);
  T2 +0x54 (41, **Index** obj+0x72); T3 `[SDA(0x378)]`=0x800891D0 +0x1C (34,
  **Typ-2**); T4 +0xB4 (34, **Typ-1**). Basen `[SDA(0x490)]`=0x80059D08 (M0),
  `[SDA(0x580)]`=0x800532C8 (M5); Ziel = Basis + Tafelwort.
- **Phasen:** Phase 1 = M0 Typ 7 (T1[7] 0x8005A8A4), 3 Stufen ueber
  `Slot+0x3C` (Bit idx) und `Slot+0x40` Bit 0/1 -> `FUN_80041F54(1)` +
  `obj+8 |= 0x4000`. Phase 5 = M5 Typ 2 (T3[0] 0x80054B48) hinter
  `FUN_80060938()` (Block+0x70) -> `FUN_80041F54(5)` + `obj+8 |= 0x4100` +
  `Slot+0x40 |= 4`. **Der ausgelieferte Datenstand traegt keinen Typ 2.**
- **Ereigniskette 1:1 gebaut:** event_advance FUN_80057FD8 (obj+0x72+1),
  event_fire FUN_80058244 (**Rueckgabe 0/1/2**), stage_set/-goto/-scan,
  cursor_tick FUN_80059BC8, list_test FUN_80058C38, flag_or6 FUN_80057BD8,
  obj_slots_reset/-clear FUN_80058BD8/0x80058C0C (vier 20-B-Saetze bei obj+0x1C),
  obj_index_clear FUN_80058680, fuenf Zeiger-Winzlinge.
- **Verdrahtet (R147):** `flow::call_desc` faehrt kFnMission0/kFnMission5 direkt;
  `mission::block_gate70` hat drei echte Rufer (0x80054B68/0x80054CDC/0x8005ACBC).
- **Regeln:** R170 (size != ext), **R171** (`slw rX,rY,rZ` = `rY << rZ`, Ziel ist
  der ZWEITE Register), R172 (mtcrf-Feld: CRf <- Wertbits 31-4f..28-4f, LT=Bit3,
  GT=2, EQ=1, SO=0), R173 (Zustandsfeld ist ein BYTE), R174 (event_fire 0/1/2),
  R175 (Bau verschiebt Reihenfolgeanker: (110)(g) jetzt relativ, 34 Zeilen).
- **Port:** `mission0_step`/`mission5_step` in mission_script.cpp; Anker
  (117)-(119) in mission_check.cpp; `mission_step_words.inc`; Werkzeug
  `scripts/m96_mission.py`. **Regression 32 + 136 Anker = 0 Fehler**, Ghidra 2085.
- **Rest:** 76 der 97 Ziele der zwei Waehler = 11748 B / 2937 Insn als Haken.

# Batch 97: DIE FUENF DESKRIPTOR-INHALTE (CONFIRMED)

- **Es sind die Tafeleintraege [1][2][3][4][6]** der Missionstafel; jeder
  Tafeleintrag ist ein **Zeiger auf einen 12-B-Deskriptor** `{fn, r2=0x800ADA5C, 0}`.
  **Sie haengen an KEINEM Waehler-Verteiler, KEINER Sprungtafel und haben 0
  `bl`-Aufrufer** — nur das Trampolin aus FUN_80058C7C. Tafel[7] = Terminator 0,
  Tafel[8] = 0x00000102 (DATEN).
- **Groessen (R170/R177):** 692 B (M1 FUN_80063648), **2424 B** (M2 FUN_80064348;
  Inventar-`size` 712!), 896 B (M3 FUN_80064F4C), 980 B (M4 FUN_80065454),
  820 B (M6 FUN_8002FEE8) = **5812 B / 1453 Insn**. **Das erste `bclr` kann ein
  Sprungverteiler sein** (M2: `mtspr LR,r3` + `bclr` bei 0x80064608).
- **Rahmen:** `obj+0x78 += 1`, `Zustand = (s8)Slot+0`; Aufzeichnung
  `Zelle + idx*8 + Versatz` mit **0x30/0xC8/0x4C/0x40/0x20**; Zellen
  `[SDA(0x498)]`, `[SDA(0x4A0)]`, `[SDA(0x4E8)]`, `[SDA(0x4F4)]`, `[SDA(0x770)]`;
  Ausstieg 0x49C/0x4E0/0x4F0/0x504/0x77C; Schluss FUN_80057ACC + FUN_80057C48.
- **Besonderheiten:** nur M1 hat den Typ an `rec+0` (die anderen verteilen ueber
  den **Index**); **M2 = ACHT Zustaende** (8er Tafel `[SDA(0x4D8)]`, 16er
  INDEX-Tafel bei `+0x20` mit Schranke **11**, Eintraege 12..15 sind Textbytes);
  M2 nutzt den **`r22`-Registerrest** (0 Schreibstellen; Port uebergibt
  `Slot+0x40`, zaehlt `residue_r22`); **M6 liest den Index aus `obj+0x74`**
  (Typ an rec+0x20).
- **`Slot+0x44/48/50/5C/60` tragen INDIZES, keine Zeiger** (R178, FUN_80058C38
  vergleicht mit `[SDA(0x384)]`).
- **0x981 = 0x800 | 0x181** (R182, M3 0x80065134: `(obj+8|0x981) & ~0x800`).
- **Port:** `port/src/mission_content.cpp` (mission1..mission6_step,
  `cursor_mask_set` = FUN_800599E4), `mission_content_check.cpp` (Anker 120-123),
  `mission_content_words.inc`; Modi `content`/`content-ui`. `flow::call_desc`
  faehrt die fuenf; `mission::call_hook`/`abort_gate` sind oeffentlich.
  **Regression 32 + 139 Anker = 0 Fehler**, Ghidra 2085.
- **Rest:** 52 Ziele der fuenf Inhalte = 8712 B (Inventar; M2-Familie
  0x80063900..0x80064348 = **2632 B** als groesster Block); vereinigt mit den
  Waehler-Zielen 118 offen / 17252 B. **`FUN_800584A4` und `FUN_80043388` sind
  jetzt direkte Ziele** (Einrichtungspfade aller Inhalte) -> naechster Schritt.

# Batch 98: DIE ZWEI ERREICHBAREN HELFER (CONFIRMED)

- **FUN_800584A4 = Listenaufloeser, 280 B / 70 Insn** (0x800584A4..0x800585BC);
  die Inventar-`size` 440 B zaehlt eine **Bruderfunktion** (0x800585BC, 88 B)
  und vier Sprung-Winzlinge auf FUN_80057880 mit (R170 3. Anwendung).
  Liste `{s16 kennung; s16 schluessel}` (Ende kennung<0) -> `obj+0x44 +
  4*kennung` = Index der 32-Byte-Aufzeichnung mit Feld **+6 == schluessel**
  (oder -1). **Start = arr[kennung_der_LETZTEN_frueheren_gleichen] + 1** ->
  zwei Kennungen mit gleichem Schluessel bekommen VERSCHIEDENE Plaetze.
- **Zwei Stufen zur Tafel:** `[SDA(0x330)]` = 0x801024B8 (8-B-Saetze),
  **`[SDA(0x334)]` = 0x80102538 = ZEIGER auf die Indexzelle** (R183!),
  Satz 0 +4 -> **0x800A3C90 (IM BILD)**, Sentinel bei Feld +0 < 0 (Index 33).
- **FUN_80043388 = Meldungsausloeser, 560 B / 140 Insn.** Block `[SDA(0x280)]`
  = 0x800FFA28 (3 Unterstrukturen +0/+0x14/+0x34): Monotonie-Tor
  `id <= (s16)(Block+4)`; 0x45-Sonderfall `(*(cfg+0x4C)>>14)&3` (1 -> 0x46);
  drei Wege aus Vorzeichen `[SDA(0x240)]+0x10` + Flaggentafel `[SDA(0x27C)]`
  = **0x8009D468 (IM BILD)**; Textzeiger 2-stufig ueber RAM-Tafel 0x8017D000
  (B = *(0x8017D000) = 0x12E0 = Abstand der Versatztafel); Terminal
  FUN_80042E08 (`Block+10 = Block+4 = -1`, `Block+0 = 0xFF`);
  Beschreibung {+0 Zust, +1 Phase, +2 46-len, +3 len+2, +4 id, +6 Groessenindex
  (8, bei ((cfg+0x4C>>10)&7)!=0 -> 6), +8 12, +10 Ereignis, +0x10 Textzeiger};
  len = FUN_800421AC(text) * (u8)*(*(*[SDA(0x28)])+0xB521+12*idx), min 6.
- **Mitgebaut:** FUN_80043378 (4 Insn, "Meldung offen?"), FUN_80042E08 (5).
- **Live-Beleg:** `Slot+0x44` = 31 30 -1 0 -1 0 -1 -1 (= M0-Liste 0x800A0420
  gegen 0x800A3C90); Live-Block `FF 00 28 08 FFFF 0006 000C FFFF 0000 8017D207`
  vollstaendig erklaert (0x75094400 -> Index 6; +0x10 = Cursor von FUN_80042E1C).
- **Verdrahtet (R147):** 8 Stellen (mission_content M1/M2/M3/M4,
  mission_script M0(2)/M5, game_flow 0x47/0x45); `kFnStageSet` -> `kFnMsgTrigger`.
- **Vom Anker gefundener Portfehler:** M2-Einrichtung las die zwei
  Ausgabezellen als Halbwort und VERTAUSCHT (`[SDA(0x4D4)]` <- Slot+0x54,
  `[SDA(0x4D0)]` <- Slot+0x5C, je `(u16)(u32)`; R184/R185). Zusatz (R186): die
  Indextafel ueberdeckt bei den Kennungen 4/6 die Felder +0x54/+0x5C.
- **Regeln:** R183 (Zelle = Zeiger auf die Datenzelle), R184 (lwz+sth = niedriges
  Halbwort), R185 (Store-Reihenfolge entscheidet), R186 (Bau aendert den
  Datenstand der Rufer), R187 (Abbild wirft bei Zugriff ausserhalb ->
  `contains` + zaehlen), R188 (Feld mit zwei Schreibern: Funktion + Abspieler).
- **Port:** `port/src/mission_helpers.cpp` + `.h`, `mission_helpers_check.cpp` +
  `.h` (Anker **123-126**), `mission_helpers_words.inc`, Werkzeug
  `scripts/m98_helpers.py`, Modi `helpers`/`helpers-ui`.
  **Regression 32 + 143 Anker = 0 Fehler**, Ghidra 2085.
- **Rest:** 60 Ziele der fuenf Inhalte = 7712 B / 1928 Insn (Inventar);
  Waehler 74 / 10748 B; vereinigt 116 / 16252 B. **Naechster Batch: M2-Familie**
  (13 Koepfe, 2000 B Inventar / 2632 B Spanne, Einstieg FUN_80063900).

# Batch 99: DIE MISSION-2-FAMILIE (CONFIRMED)

- **ES SIND 15 KOEPFE, nicht 13** (R170 4. Anwendung): der Block
  `0x80063900..0x80064294` = **2452 B / 613 Insn**; die Aufgabenliste nennt nur
  13 (2000 B = Summe der Inventareintraege). Es fehlen **`FUN_80064014`
  (292 B)** und **`FUN_80064138` (160 B)** — beide **nur INNERHALB** der Familie
  erreichbar. Die R170-Warnung der Aufgabe (E48/D1C groesser als `size`) trifft
  **nicht** zu: beide enden exakt am Inventarende, keine Sprungtafel darueber.
  Nachbarn: `0x800638F8` = `bclr` (Ende M1), `0x800638FC` = EIN Nullwort,
  `0x80064294` = naechster Funktionsanfang (`lwz r6,[SDA(0x4A4)]`).
- **Batch 97 hatte im M2-Zustand 2 DREI Aufrufe ausgelassen**:
  `0x800645B4` (E48), `0x800645B8` (D1C), `0x800645C0` (BC8). Der Zeitgeber wird
  bei **0x800645C4** gelesen (der Kommentar `//800645B4` war falsch).
- **Die Familie = Speicherseite einer Zielauswahl:** Kandidaten `[SDA(0x4A4)]`
  (Satz), `0x4A8` (Anzahl), `0x4AC` (16 Objektzeiger), `0x4B0` (16 Art-Bytes);
  Auswahl `0x4B8` (zwei Objekte), `0x4BC` (Distanzquadrate), `0x4C4` (Art),
  `0x4C0` (Umlaufzeiger 0..3), `0x4B4` (gesperrt), `0x4C8` (Tausch),
  `0x4CC` (3er-Differenz); Anzeige `0x400` = `{s16 n; u32 Basis}`.
- **Tor der Zielauswahl: `cfg+0x48` Wertbit 7 = 0x01000000** (R191: `mtcrf 0x40`
  -> CR1 aus den Wertbits 4..7, `bc 4,7` = CR1.SO; Ghidras `(x>>24)&1` ist
  dasselbe Bit). **Live `0x29800000` -> das Bit ist GESETZT, das Tor steht AUF.**
- **`FUN_8006394C` liefert 0/1/2** (0 = Bit stand schon, 1 = gerade geruestet,
  2 = Block `[SDA(0x234)]+0x62C` belegt); der Rufer springt bei `!= 0` nach
  **0x80064924** (`bc 4,2` = FUN_80057ACC + Schluss) — **nur bei 0 laeuft der
  Typ-Ruf FUN_80063900**. Der **Rueckgabewert entscheidet also den Ablauf.**
- **`Slot+0x78` ist eine KENNUNG** fuer `FUN_80057C20` (`Slot+0x44+4*kennung`),
  kein Zaehler (Werte -1/2/3 = Listenindizes; R190).
- **`lswi`/`stswi` NB = 0 kopiert 32 Byte** (R189; NB IST der Byte-Zaehler).
  Die zwei Nachlaufzaehler kopieren 32 B auf den Stapel und wuerfeln
  `(((290|29)*rng)>>15) + 145|130`; `FUN_80062784(Puffer)` liest bis +0x1C.
- **Distanzquadrat `FUN_80064138`:** -1/0 fuer obj == 0 oder Komponente >=
  **25000** (|v|>>2), **1** wenn `obj+0x14` Bit 0 fehlt, sonst Summe der
  Quadrate aus `+0x60/+0x64/+0x68`.
- **R147-Effekt (gemessen):** der Bau entfernt 13 Ziele/2000 B und oeffnet
  **7 NEUE Ziele / 1276 B** (FUN_80057DA0 64, 57C20 40, 58080 272, 5B86C 180,
  3B50C 256, 62784 60, 209F0 404). Netto -724 B. **Die zwei Waehler bleiben
  unberuehrt** (74/97 offen).
- **Schnittstelle (R193):** `FlowCall::args`/`StepCallItem::args` = **5** Stellen
  (`FUN_8005B86C` liest r3..r7), `h5`-Haken; `StepTrace::add`/`call_hook` 5.
- **Regeln:** R189 (lswi NB = Bytes), R190 (Slot+0x78 = Kennung), R191 (mtcrf
  0x40 = CR1 aus Bits 4..7), R192 (Bitnummer != Wertmaske), R193 (5 Stellen),
  R194 (ein Hakenstandard ist ein Sollwert — alte Anker TEILEN).
- **Port:** `port/src/mission2_family.cpp` + `.h`, `mission2_family_check.cpp` +
  `.h` (Anker **127-131**), `mission2_family_words.inc` (18 Zellen + 613 Woerter
  + 19 Proben), Werkzeug `scripts/m99_family.py`, Modi `family`/`family-ui`.
  **Regression 32 + 148 Anker = 0 Fehler**, Ghidra **2085** unveraendert.
- **Rest:** fuenf Inhalte **47 offen = 5712 B / 1428**; Waehler **74 = 10748 B**;
  vereinigt **103 von 141 = 14252 B / 3563**. **Naechster Batch: M3/M4-Familie**
  (0x80064CC0..0x800653D8, 1024 B) + die 7 neu sichtbaren Ziele
  (`FUN_800209F0` 404 B und `FUN_80058080` 272 B sind die groessten).


# Batch 100: DIE M3/M4-FAMILIE + DIE SIEBEN ZIELE (CONFIRMED)

- **ES SIND 8 KOEPFE / 1040 B / 260 Insn** (R170 5. Anwendung; die Aufgabe sagt
  "ca. 1024 B"). Die sieben genannten = 916 B / 229 Insn:
  FUN_80064CC0 (80, obj_slots_reset + Block+8|=4 + state_inc(slot,0)),
  FUN_80064D10 (140, Satzschleifer), FUN_80064D9C (88, Wertzeile),
  FUN_80064DF4 (220, M3-Balkensatz), FUN_80064ED0 (124, Flaggentor, **nur
  intern gerufen**), FUN_800652D0 (208, M4-Balkensatz), FUN_800653A0 (56,
  Zaehler) + **FUN_800653D8 (124, M4-Helfer) HINTER dem Bereichsende**.
  `bl`-Scan: genau **2** `bl` auf 0x800653D8 (0x80065598, 0x800656E0, beide M4)
  + Rueckfall `b` aus 0x800653D0. **Der M3-Inhalt FUN_80064F4C (896 B Inventar)
  liegt MITTEN im Block** (`bclr` 0x800652C8, ein Nullwort bis 0x800652D0).
- **Die sieben Ziele (1276 B / 319 Insn):** FUN_80057C20 (40), FUN_80057DA0 (64),
  FUN_80062784 (60), FUN_8005B86C (180), FUN_8003B50C (256), FUN_80058080 (272),
  FUN_800209F0 (404) + die zwei Winzlinge FUN_80020B44 (8) / FUN_80020B4C (60)
  **innerhalb** des atan-Inventars (0x80020B84, R288).
- **Satztafel `[SDA(0x4E4)] = 0x800A97B0`**: fuenf 4-B-Saetze
  `03090202 1C0A0400 02080101 2C0B0803 2D0C1004` (Live-Dump byte-identisch).
  **`[SDA(0x4F4)] = 0x800A9860` fuehrt ZUGLEICH die M4-Aufzeichnungen
  (+0x40+8*idx) UND die Zaehlerschwellen (+2*c = 10/320/690/1024).**
  `[SDA(0x4F8)] = 0x800A9918` traegt 0x0E — **der Ruf bekommt den ZEIGER** (R198).
- **FUN_80064D10 schreibt die Rueckgabe von FUN_80058410 IN DIE LISTE**
  (`stwx r3,r28,r26`); **FUN_80064D9C liest `Satzanfang+3`** (`addic r30,r0,-1`
  + `lbzu r3,4(r30)`: Update VOR dem Laden) und reicht den Registerrest
  `4*index` nur weiter, wenn die Schleife **nicht** lief (R161).
- **FUN_80064DF4 braucht `mcrf cr6,cr1` (0x80064E44): CR6 = KOPIE von CR1**
  (R195; `crand` ist XO=257). Zweige: Abfrage 0 -> Balkensatz(5,Liste[0],-2048,
  0,2500); 1 -> bei Block+0x78>=5 FUN_800588C8(0x105) + Block+8 &= 0xFFFFF67E +
  cursor_arm(29,29) + cursor_mask_set(-17,0); **3 -> nur bei Block+0x78==5**.
  M4 (FUN_800652D0): 0 -> Balkensatz(6,slot+0x54,-4096,0,3000) +
  FUN_8005B854(slot+0x58) + FUN_800478D8([SDA(0x4F4)]+8,4); 1 -> &= 0xFFFFF67E +
  FUN_800478D8([SDA(0x478)]+0x40,4); 2 -> |= 0x981; 3 -> nichts.
- **FUN_800653A0:** `lha` Block+0x74 (Vorzeichen!), Schwelle s16 aus
  `[SDA(0x4F4)]+2*c` gegen Block+0x78; schreibt IMMER `c+1`, Rueckfall nur bei
  `c == 3` (`bclr 4,2` nach `cmpwi cr0,r0,3` — `addic` clobbert CR0 nicht, R176).
- **FUN_800209F0 = atan2 in 0x10000 = 360 Grad**, `0x4000` = 90 Grad. Tafel
  `[SDA(0x108)] = 0x8008F1C8` = **65 Bloecke zu 130 B** `{u16 Basis; u8 Delta[128]}`;
  **Block 64 = Basis 0x2000** (Grenze fuer |x|==|y|). Normalisierung: CTR=13 +
  ein Schritt danach, verdoppelt bis 2^30, ist **wertgleich** zum direkten Weg.
  Zweigentscheidung `|y| < |x|` **unsigned** (`cmpl`), Quadranten aus den
  Vorzeichen von x/y.
- **FUN_8003B50C (Wire):** `extsh` auf den Winkel (0xA000 -> -24576), Magie
  `mulhw 0xC003000D + addc + srawi 12` = `trunc(v/5461)`, Betrag auf +-127,
  Guete `((v1-c)*0x80)/(d-c)` auf 0..127, **`d == c` -> keine Division, Guete 0**.
  Analytische Sollwerte: `0x0005007F` und `0x0005407F`.
- **FUN_80058080 = 0/1/2/3** (0 gefeuert, 1 auf -1, 2 nichts, **3 war schon -1**
  = Registerrest `li r3,3`, der fruehe Ausstieg ueberspringt `cursor_tick`;
  R161). Pruefreihenfolge: **Eintrag<0 -> 3, dann Phasen `ctx[0x10]`, `ctx[0x12]`,
  dann Vergleich mit c.**
- **R197 (Portfehler, vom Anker gefunden):** FUN_8005B86C liest
  `[SDA(0x3AC)][a+0x14]` mit `lbz` **und `extsb`** (0x8005B8E8) -> im Port `s8`
  (0xD9 -> -39 -> Hakenarg `0xFFFFFFD9`).
- **R147-Effekt (gemessen, scripts/m100_effect.py):** -7 Ziele / -916 B weg,
  **+15 Ziele / +1588 B** neu sichtbar (3 schon gebaut + echt gerufen:
  FUN_8000D140/FUN_80020F7C/FUN_8003C6F0; 11 Haken = 1100 B, davon **8 voellig
  neu** = 848 B: 3C17C/44910/44948/449C4/58410/5B854/620D8/62124). **Saldo +672 B.**
- **Regeln:** R195 (mcrf = CR-Kopie), **R196** (`&fp->member` mit fp==nullptr ist
  KEINE Nullpruefung -> `svc_of()`; ein Ersetzungslauf traf auch den Rumpf des
  neuen Helfers -> Selbstaufruf, Anker wurden rot), R197 (lbz+extsb = s8),
  R198 (`lwz rX,[SDA(n)]` = Zeiger, nicht Inhalt).
- **Port:** `mission34_family.{h,cpp}`, `mission_services.{h,cpp}`,
  `mission34_check.{h,cpp}` (Anker **132-136**), `mission34_words.inc`
  (10 Zellen + 579 Woerter + 35 Proben + 8 Grenzfaelle), Werkzeuge
  `scripts/m100_m34.py` / `m100_effect.py`, Modi `m34`/`m34-ui`.
  **Regression 32 + 154 Anker = 0 Fehler**; **39 von 51** Selbsttest-Modi Exit 0;
  Ghidra **2085** unveraendert.
- **Rest:** fuenf Inhalte **40 offen = 4796 B / 1199 Insn**; Waehler **74 = 10748 B
  / 2687** (unveraendert); vereinigt **96 von 141 = 13336 B / 3334**. Die vier
  grossen Helfer (FUN_80053CAC 444, FUN_80054038 828, FUN_800723D8 360,
  FUN_80051F64 284) **unveraendert offen** (nur ueber M0/M5).

# Batch 101: DIE BLATT-/ZELLENFAMILIE DER FUENF INHALTE (CONFIRMED)

- **33 Koepfe / 2140 B / 535 Insn gebaut** = **18 der 40** offenen Ziele aus
  Batch 100 **+ 15 durch sie neu sichtbare**. **Die 40 sind in EINEM Batch
  NICHT schliessbar** (der Rest ist die Ablauf-/Flussfamilie).
- **Rest: 22 Ziele / 3244 B / 811 Insn** (40 -> 22). Davon **vier schon
  anderswo gebaut** = R148-Kandidaten: `FUN_80015294`=`port::Prng`,
  `FUN_800373A8`=`paket_d`, `FUN_8003C6F0`/`FUN_8003C750`=Audio.
- **R170 sechste Anwendung:** alle 40 Ziele stimmen aufs Byte mit dem naechsten
  Kopf, **aber DREI Inventareintraege fassen ZWEI Koepfe**: `FUN_80038358`
  (272+**52** = `FUN_80038468`), `FUN_80057E88` (156+**180** = `FUN_80057F24`),
  `FUN_800588C8` (84+**28** = `FUN_80058920`). **Der `bl`-Scan ueber ALLE
  Inventarfunktionen entscheidet:** `FUN_80058920` (Rufer `FUN_8005CE08`) und
  `FUN_80057BA8` (Rufer `FUN_80057BD8`, GEBAUT) **leben**; `FUN_80038468` und
  `FUN_80057F24` haben **0 Rufer** -> HYPOTHESIS toter Code, **nicht gebaut**.
- **Der Inhalt der gebauten 33 (drei Gruppen):** A Zellen/Blatt (20:
  `panel_flag_*`, `wire_word_clear`, `cell_640/624`, `obj8_mask_or`,
  `cursor_word6`, `snd_pair_reset`, `snd_block_ptr`, `snd_rec_set`,
  `list_next_idx`, `seq_state`, `pool_push`, `cat_slot_store`, `obj_mask_two`,
  `obj_cell_clear_a/b`, `obj_pair_clear_a/b`, `view_copy`),
  B Liste/Slot (8: `slot_make` -> **GEBAUTER Slotallokator `FUN_80037258`**,
  `m4_pair_make`, `m4_six_make`, `rec_pack`, `panel_toggle`, `obj_present`,
  `tbl_search`, `msg_arm`), C M1/M6 (5: `m1_leave_b`, `m1_bar`, `m6_rand_aim`,
  `m6_state_a/b`).
- **Tragende Befunde:** `FUN_8003B4E8` hat **DREI** Argumente; `FUN_8005B154`
  rechnet `(u32)v >= 1 ? 1 : 0` (`addic`+`subfe`), Tor = **CR1.SO =
  0x01000000**; `FUN_80057968` loescht **genau Wertbit 22** (`rlwinm ...0x17,
  0x15` mit **ME<MB**, R200); `FUN_800579CC` schreibt `ori 0x200` und
  `snd_block_ptr([SDA(0x398)])` = der **Inhalt**; `FUN_800626E4` vergleicht
  **unsigned**, liest das Byte **`extsb`** und liefert die **Anzahl**;
  `flag_or6` -> `rec_pack` benutzt das **stehen gebliebene r3** (Slotadresse).
- **Anker 137-140** (`mission_content_helpers_check.cpp`): 21 Zellen +
  **535 Befehlsworte** (Generator `scripts/m101_words.py` fahrt SELBST die
  R170-Probe), 12 Grenzfaelle, **26 Wirkungsfaelle**, 2 Spuren. Modi
  **`helpers101`**/**`helpers101-ui`**.
- **Verdrahtung (R147): 19 Stellen** in `mission_content.cpp` + `flag_or6` in
  `mission_script.cpp`. **Neun Inhaltsanker** von Hakenzahl auf WIRKUNG
  umgestellt (R194) + eine UI-Zeile (M2: 6 -> 4 Haken).
- **Regeln:** **R199** (Store-Paar ueber REGISTER entscheiden),
  **R200** (`rlwinm` mit ME < MB laeuft herum), **R201** (Ruferlosigkeit =
  Bauentscheidung, dokumentieren statt bauen).
- **Regression 32 Frames + 159 Anker = 0 Fehler** (vorher 154);
  **41 von 53** Modi Exit 0 (dieselben 12 bekannten Ausnahmen);
  Ghidra 2085 unveraendert (0 Schreibzugriffe).
- **NICHT bauen:** `FUN_8005E280` (LZSS-Fenster **0xFF1C0000**, ausserhalb des
  4-MB-Abbilds). **Offen:** die Ablauf-/Flussfamilie (`FUN_80057ACC`,
  `FUN_80057C48`, `FUN_80057E88`, `FUN_80058B00`, `FUN_8005B0EC`,
  `FUN_80056730`, `FUN_80058190`, `FUN_80063418`, `FUN_800634DC`,
  `FUN_800635BC`, `FUN_8002FD90`, `FUN_8002FE30`, `FUN_800478D8`,
  `FUN_80047D30`, `FUN_800496AC`, `FUN_80058354`, `FUN_8005893C`) = 1-2 Batches.

# Batch 102: DIE ABLAUF-/FLUSSFAMILIE DER FUENF INHALTE (CONFIRMED)

- **30 Koepfe / 3288 B / 822 Befehlsworte gebaut** = **12 der 22** offenen Ziele
  + **18 neu sichtbare** Helfer; dazu **4 per R148 uebernommen** (604 B, nicht
  dupliziert). **Vier Gruppen:** Rechenkerne (packed_digits/digits_into/
  counter_scale/clear_pair/lerp_word), Zellen-/Blattdienste (fmt_store/
  cell_store/cell_word2/bar_or8/cell_ptr_call/list_or/seq_test/bar_f32/
  bar_int/std_numbers), Klang (snd_blend_copy/snd_pair_init/snd_gate/
  m1_snd_gate/rec_write), Ablauf (view_init/view_tail/content_tail/content_exit/
  reset_blk/flag_blk_init/m6_enter/m1_leave_a/m1_advance/m1_leave_c).
- **Rest: 6 Ziele / 984 B / 246 Insn** (22 -> 6). Offen: `FUN_8002FE30` 184,
  `FUN_800496AC` 112, `FUN_80057E88` 336, `FUN_80058190` 180, `FUN_8005893C` 72
  + unbaubar `FUN_8005E280`. **Caller gemessen (`m102_flow.py callers`):**
  2FE30 3x/496AC 1x/57E88 7x/5E280 1x aus **M6 FUN_8002FEE8 (GEBAUT)**;
  58190 aus M4 FUN_80065454 + im M2-Rumpf; 5893C u.a. aus 2FE30/58190.
  → Bau **nur gemeinsam mit der Verdrahtung** (R147).
- **R170 7. Anwendung:** alle 22 Ziele Delta +0; **drei Doppeleintraege**:
  `FUN_800487D0` 96 B + **`FUN_80048830` 88 B**, `FUN_8003B974` 60 B +
  **`FUN_8003B9B4` 172 B**, `FUN_8002B000` 232 B + 4 B Nullwort. Die zwei echten
  Geschwister haben **0 Rufer** → HYPOTHESIS toter Code, nicht gebaut (R201),
  Anker `kFnDeadA`/`kFnDeadB`.
- **R202 (NEU): der `bl`-Scan ist KEIN Abschluss** — Sprungbefehle **ohne LK**
  (`b`/`bc`) sind **Tail-Aufrufe** und unsichtbar. Beleg: `FUN_8004780C` endet
  `b 0x80047C10` → **`FUN_80047C10` (56 B) fehlte in Batch 101**. Werkzeug:
  `branch_target_any()` (op16/op18 unabhaengig vom LK) + ganzen-Bild-Scan.
  **Abschluss der Familie: 48 Knoten / 7156 B / 1789 Insn.**
- **Tragende Befunde:** `content_exit` (FUN_80057C48) = Aufzeichnungsverteiler
  (Typ 2 → `sound_wire(0xF1010200)`, Typ 3 → gebautes `FUN_80043388`,
  Typ 0 → `0x541 << 16`); **Filter vergleicht WORT `obj+0x78` (`lwz`) mit
  HALBWORT `rec+2` (`lha`)**; `m1_snd_gate` = **zweiteiliges Tor** (Wertbit 24
  in `cfg+0x4C` = 0x01000000 **und** `s16([SDA(0x3A4)]) == 1`) → Zelle 2/255/0;
  `m1_leave_c` = 2 Wire-Rufe + obj_present + event_advance + `ctx+8 |= 0x981` +
  `ctx+0x7E = 1`, **danach** m1_snd_gate (Reihenfolge = Verhalten);
  `counter_scale` teilt vorzeichenbehaftet (`srawi; addze`);
  `snd_blend_copy` kopiert 16 B (`lswi ...,16`) + 6 B (`lswi ...,6`) (R189).
- **Verdrahtung (R147): 16 Regeln / 53 Stellen** in `mission_content.cpp`
  (`scripts/m102_wire.py`, Treffer einzeln nachgezaehlt).
  **R148-Saum NEU (R193, additiv):** `FlowHooks::audio_id`/`audio_wire`/
  `audio_trigger_user`/`panel_setup`/`panel_user` — mit Motor echt, ohne Motor
  gezaehlter Rueckfall. Auch echt gerufen: `port::Prng`, `paket_d`.
- **Anker 141-145** (`mission_flow_check.cpp`, `kScr = 0x803E2000`):
  31/31 ROM-Wortanker (Pruefsumme **8FF0F7B0** ueber 3288 B), 23/23 Rechenkerne,
  9/9 Zellen, 6/6 R148-Wirkung (leerer `AudioEngine`), 6/6 Ablaeufe.
  Modi `flow`/`flow-ui`. **36 Hakenzahl-Anker auf WIRKUNG umgestellt (R194,
  8. Anwendung)**, zwei Stellen lesen jetzt `flow_stats().last_fn/last_args`
  bzw. `prev_fn/prev_args`; M2-UI-Zeile 4 → 3 Haken.
  **Regression 32 + 161 Anker = 0 Fehler**; Ghidra 2085 (0 Schreibzugriffe).
- **Eigene Fehler:** (a) `bl`-Scan fuer vollstaendig gehalten (→ R202);
  (b) **Null-Deref nach der Verdrahtung** (`log.first(0x80058B00u)->args[3]`)
  → `0xC0000005` im `content`-Modus **ohne Ausgabe**, nur mit temporaeren
  `stderr`-Fallmarken (`m102_marker.py`) lokalisierbar; (c) **Namensfalle**:
  lokaler Helfer `sound_id` verdeckte `mission::sound_id` → Selbstaufruf
  (umbenannt `sound_id_tracked`); (d) zwei eigene Prueffaelle zu streng
  (Halbwort statt Wort; Torszelle durch Vorschritt geleert) — nicht der Bau war
  falsch; (e) Wortzahl 769 → richtig **822**; (f) **R200-Prosa** nennt
  0x400000, richtig ist **0x200**.
- **Waehler M0/M5 unveraendert offen** (74 / 10748 B / 2687).


# Batch 103: DIE FUENF-INHALTE-GRUPPE ABGESCHLOSSEN (CONFIRMED)

- **ELF Koepfe / 1880 B / 393 Insn** (R202 erste Werkzeuganwendung:
  `scripts/m103_close.py closure`, `branch_target_any` op16/op18 ohne LK):
  die fuenf genannten + FUN_8002A7A8, 8002AA9C, 80058A9C, 80058984, 80066330,
  80027280. **Fuenf Inhalte damit 0 baubare offene Ziele**; `FUN_8005E280`
  (100 B) bleibt **unbaubar** (LZSS-Fenster 0xFF1C0000).
- **R203/R204/R205/R206:** im D-Form-Befehl ist **RA = 0 die Konstante 0**;
  ein kleines `addic` auf ein Zeigerregister ist eine **Flagge**; Feldlayout nur
  ueber Speicherzugriff **und** Vor-Basierung (`{u16 Flagge; u16 Schluessel;
  u32 Zeiger}` bei `cfg+0x87C`); ein Registerrest ist ein Sollwert.
- **Tonsaum:** `FlowHooks::audio_id`/`audio_wire` = die ECHTE Audio-Implementierung
  mit Motor, sonst gezaehlter Rueckfall.

# Batch 104: R202 RUECKWAERTS + REPARIERTE WAEHLER-LISTE + ERSTER WAEHLER-KOPF

- **Werkzeuge:** `scripts/m104_built.py` (batches/check/buildstate/tails/sanity/
  voter/beweis/gebaut/hooksuspect/nachzuegler), `scripts/m104_voter.py`
  (check/words/dis). **Der Bauzustand = drei Quellen** (Bau-Listen 96..104,
  gemessene Grenzen R170/R177, Port-Quellen `*.cpp`/`*.h`; `.inc` ist
  **untauglich** als Bau-Liste!): 236 Adressen, alle in den Quellen benannt.
- **R202 rueckwaerts ueber 228 Koepfe: 6** Tail-Aufrufe auf gebaute Ziele,
  **2** auf ein nicht abgebildetes (`FUN_8003C6C4`), **0** in Luecken.
  Der echte Treffer: `state_set`/`state_inc` (Batch 92) springen per `b` bei
  **0x8003C6A8/0x8003C6C0** auf den **gemeinsamen Rumpf FUN_8003C6C4** (44 B,
  nullt `ctx+first..ctx+7`, Rueckkehr ohne Nullung bei `first >= 8`) →
  repariert als **`state_zero_tail`** + 9 Rohwortanker + 5 Verhaltensfaelle.
  `FUN_8003C6C4` hat **zwei `bl`-Rufer in UNGEBAUTEM Code** (0x800522F0,
  0x800679DC) - im Waehler-Batch gebraucht.
- **Waehler-Liste (gemessen, 97 Ziele): 44 gebaut / 53 als Haken offen =
  7980 B / 1995 Insn** (dokumentiert waren 72/10496/2624). Ursachen: die
  damalige Baumenge war **familien-lokal** (R210) und **neun** Eintraege waren
  **Haken** (0x8003C17C, 800432C0, 80044910/48/C4, 80058410, 8005B854,
  800620D8, 80062124; R208).
- **Die Waehler-Gruppe ist KEIN Batch:** Huelle der 97 Ziele = **214 Knoten /
  38276 B / 9569 Insn** (33236 B nicht gebaut). Gemessener Schnitt: 105
  {535B4,53CAC} 3244/811; 106 {54038} 2828/707; 107 {723D8,51F64,59D7C}
  2692/673; 108-109 {5389C} 12448/3112; 110-111 {59EA4} 11392/2848.
- **Gebaut: `FUN_80059D7C`** (296 B / 74 Insn, T2[20..23] von M0, **eine**
  Rufstelle 0x8005AF7C, alle 8 Ziele gebaut): Ruestbit `slot+0x40` Bit 7 (R160)
  -> `view_init([SDA(0x39C)]+0x2C, 58)`; `rec_write(0,0,*(u32)(slot+0x5C),
  [SDA(0x3A0)])` (**r4 des Rufers wird NICHT gelesen, R209**); Zaehler
  `slot+0x38` 0/1/>1 -> Listenzweig (`list_test` -> obj+8 |= 0x81, obj_present,
  Ton 0xF11B0100, Zaehler 14) / Feuerweg (`m1_snd_gate`, `cell_640_init`,
  `stage_goto(slot,0x18,...)`, obj+8 |= 0x981, obj+0x7E = 1/2) / herunterzaehlen.
  Anker **(151)** 78/78, **(152)** 5/5, **(153)** 1/1 (Verdrahtung, Wirkung).
- **15 R148-NACHZUEGLER offen** (Hakenstellen in GEBAUTEN Rufern): 0x8002FDF4,
  0x80045E10, 0x80041E38 (2x), 0x800476A0, 0x80056730 (2x), 0x800478D8 (2x),
  0x800588C8 (2x), 0x800109FC (2x) - muessen im Waehler-Batch verdrahtet UND
  die Hakenzahl-Anker (117)-(119) umgestellt werden (R167/R194).
- **R211:** ein Nullwort am Rumpfende ist **Ausrichtung** (FUN_8005B86C).
- **Regression 32 + 169 Anker = 0 Fehler**; 26/28 argumentfreie Selbsttest-Modi
  Exit 0 (`frame`/`abi-call` brauchen Dump/Argument).

# Batch 105: DIE WAEHLER-FAMILIE, ZWEITER SCHNITT (CONFIRMED)

- **R212 (NEU, wichtig fuer ALLE weiteren Schnitte): die Inventarspalte `insn`
  IST die gemessene Koerperlaenge in Instruktionen**; `size` ist nur der Abstand
  zum naechsten Kopf und fasst bei Bedarf MEHRERE Koepfe zusammen. Belege:
  FUN_8002A7A8 200/25, FUN_800584A4 440/70, FUN_800487D0 184/24,
  FUN_800723D8 360/**6**. **Kehrseite: die Spalte ist oft LEER** (36 der 97
  Waehlerziele) - dort bleibt nur `size` oder ein Messlauf.
  Werkzeug: `scripts/m105_voter.py body`/`heads` (sucht verdeckte Koepfe:
  Innenziele mit Rufstellen von AUSSERHALB).
- **Zehn Koepfe / 396 Insn / 1584 B gebaut:** FUN_800723D8 (6, Zustandsbytes
  `[SDA(0x578)]+0x49/4A`), **FUN_800723F0 (84, verdeckter Kopf** im Eintrag
  FUN_800723D8, `bl` von 0x80079C88), FUN_80051F64 (71, Satzaufbau aus
  `[SDA(0x330)]`+Index `(s16)(*[SDA(0x220)]+4)`), FUN_8001DD78 (54, drei
  Winkel aus einem Vektor, 3 Zweige), FUN_8003B058 (36, aushängen + Winkel),
  FUN_8003BD64 (41, `dst+0` Neigung / `dst+2` = -Gier / `dst+4` = 0),
  FUN_800522B0 (24, Slot), FUN_80052310 (52, **Ring** 32 a 124 B),
  FUN_800210C8 (13, Q14-Doppelprodukt), FUN_80020B84 (15, **Arkuskosinus**).
  FNV-1a `7784BF74`, 0 Nullwoerter.
- **R213 (NEU): "gleicher Bau" != "gleiche Semantik".** 0x80020B4C (14 Insn)
  und 0x80020B84 (15 Insn) haben 9/14 Worte gleich, aber die
  **atan2-Argumente sind vertauscht**: 0x80020B4C = Arkussinus
  (`mission::angle_asin`), 0x80020B84 = Arkuskosinus. Ein Wortzahl-Vergleich
  haette den falschen Winkel gebaut; Werkzeug `m105_voter.py pair`.
- **R183 erneut:** `[SDA(0x344)]` = **Zeiger auf die Zeigerzelle** (0x801034C0 =
  Ende der Satztafel 0x80102540 + 32*124) - die Zelle nicht als Wert lesen.
  **R201:** die zwei Geschwister 0x8001DE50/0x8001DF28 im Eintrag FUN_8001DD78
  haben 0 Zweig-Rufer UND 0 Wortverweise -> nicht gebaut, verankert.
- **R148:** TrigTable::cos_quad, flow::state_zero_tail, angle_atan2,
  HitLayer::isqrt16, AssetLookup gerufen; FUN_8000D140 lokal als `word_fill`
  (klassengebundenes `OpMode::word_set`).
- **Verdrahtung (R147/R194):** M5-Haken 0x8005480C -> `state_stub`,
  0x80054B3C (Typ 10 = T3-Index 8) -> `setup_records`; Hakenzahl-Sollwert (118h)
  auf Wirkung. **Die 15 R148-Nachzuegler sind NICHT mitgenommen** (Messung:
  keiner ihrer Rufer in diesem Baustein; 5 Module) -> eigener Verdrahtungs-Batch.
- **R207 rueckwaerts ueber 240 Koepfe: (a) 8 / (b) 0 / (c) 0** - Liste (b)
  erstmals leer. Anker **154** 421/421, **155** 17/17, **156** 5/5, **157** 2/2;
  Modus `voter`; **Regression 32 + 173 Anker = 0 Fehler**.
- **Rest (R212): 46 gebaut / 5324 B / 1331 Insn, 51 offen / 7416 B / 1854 Insn**
  (36 ohne `insn` -> Mischzahl). Naechster Schnitt FUN_80054038 (19 Knoten,
  `insn` fehlt); **FUN_8005389C hat `insn` 194 = 776 B > `size` 676 B**
  (R177/R212: Rumpf ueber `size` hinaus).
- **Pruefstands-Regel:** ein Anker-Sandkasten muss die **Schreibweite** der
  geprueften Funktion beruecksichtigen (FUN_800723F0 schreibt bis `obj+0x1B2`;
  der erste Sandkasten lag bei `obj+0x1A4` und der Rumpf ueberschrieb sich
  selbst - R196-Klasse).

# Batch 158: DIE FUENF TYPPFAD-NAEHTE (Scheibe A, CONFIRMED)

- **T3-Typzuordnung GEMESSEN** (Werkzeug `scripts/m158_t3map.py`,
  Belege `analysis/_m158/`): der Typwert ist in T3 ein **reiner INDEX**
  (`k = Typ - 2`, Tafel `[SDA(0x378)]+0x1C`, Basis `[SDA(0x580)]`) - es gibt
  **KEINE Vergleichskette** ueber den Typ; nur `Typ <= 1` (Vorschritt) und
  `k > 33` (out_of_range). Tafel BILD == LIVE. **Typ 8 -> 0x800549C8,
  Typ 9 -> 0x80054A28, Typ 10 -> 0x80054A58, Typ 2 -> 0x80054B48.**
- **Warum `type = 8` in B157 den Pfad NICHT erreichte:** Feld/Offset/Lesebreite
  sind RICHTIG (`lha r4,248(r26)` @0x8005486C = s16 bei `rec+0`). Es waren die
  **zwei Tore IM Pfad**: (1) `bl FUN_80058244` -> Rueckgabe MUSS **0** sein
  (Bit `1<<idx` in `Slot+0x3C` gesetzt), (2) `ctx+0x12 != 0`. Dazu die
  Vorbedingung davor: `Slot+0x0E == 0` (sonst T4) und `Slot+0 == 1`.
- **Geteilte Zellen (R386 praezisiert):** der T3-Pfadlauf aendert obj+0x70/0x72,
  obj+0x78, obj+8, obj+0x488, Slot+0x0C, Slot+0x40, `blk+0x13C`, zwei
  Listen-/Szenenzellen - **NICHT `cfg+0x4C`**. Der B157-Befund `622 = 9 statt 10`
  kommt aus der **Vorbedingung `ctx+0x12` (= `ph` in `FUN_80056730`)**:
  `a(idx=0)=271`, `b(ph=2)=log+0x1C=234` -> `t=968` -> `q=9`. Die B157-Prosa
  "cfg/F-Log beruehrt" ist damit **berichtigt**.
- **Sandkasten (Anker (118p)):** ganze 4-MB-Vollkopie NACH der Vorbereitung,
  Diff je Pfad (MESSUNG statt Behauptung), danach wortgleiche Rueckstellung
  (`be32`-Vergleich). Wirkungsnachweis: `wired` 2/1/1/1, `count_of(Ziel)==0`,
  `content_helper_stats()`/`flow_stats()` zaehlen; Anker (118) **16/16**.
- **R385 bestaetigt:** `80054B0C` hat ZWEI Argumente (r3 = r4 = 0x11170) -
  Beleg `blk+0x13C = 0x11170` im Lauf.
- **Noch GEZAEHLT:** `80054AE4` (`FUN_8005CC54`, Szene-Kette) - eigener
  Nachweis (B159); die uebrigen T3/T4-Naehte der 19er-Scheibe B bleiben offen.
