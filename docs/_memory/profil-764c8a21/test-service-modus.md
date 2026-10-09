# Paket e/f = Test-/Service-Modus (Stand Batch 84, 2026-09-20) — SCHRITT 5 TEIL A/B/C (C-2 VOLLSTAENDIG) /D GEBAUT + TESTMODE

## Batch 84: Der RANKING-Erzeuger (5-C-2 abgeschlossen)
- **`FUN_80026E70` = 548 B / 137 Woerter** (`0x80026E70..0x80027094`) — „~2,1 KB“ war der
  Abstand zur naechsten Funktion. Fuellt 6 Saetze: **0/1** (100 B, Zeilen 12 B: `u32=Quelle-1000k`,
  `u8=Quelle-5k`, `u8=(7-k)/2`, Name ab +6; Quellen = die zwei 16-B-Records IN der Tabelle `+0x20/+0x24`)
  und **2..5** (452 B, Zeilen 56 B: 24 u16 `=29*(Summe+2k)`, +48 = Kopie von +46, +50 = Quelle-5k,
  +51 = `(7-k)/2`, Name ab +52; Quellen `+0x28..+0x34`). Je Satz **8 Zeilen + 4-B-Pruefsumme, gefuellt 7**.
- **Pruefsumme setzt der SCHREIBER** (`FUN_80027898`: `bl FUN_8000E190` @0x8002792C, `stwx r3,r30,r31`
  = `Satz[len-4]` @0x80027934, DANN NVRAM-Kopie) — **P88**: B83 hatte ihn auf die reine Kopie verkuerzt.
- **Namenswahl:** `v=18*rng()`, Index `(v>>15)&0x1FFFF` (**0..17**), Bitmaske `1<<Index`, Retry solange
  `used & Bit`; `used` **je Satz** zurueckgesetzt ⇒ kein **INDEX** zweimal (Name darf doppelt sein:
  Tabelle hat 18 Zeiger, Index 17 = Index 1 = "Y.F").
- **`FUN_80015294` = globaler LCG** (`0x41C64E6D`/`0x3039`, `(x>>16)&0x7FFF`), Zustand in
  `[SDA(0xA8)]+0 = 0x8008E220` (Startwert **1**), **186 Aufrufstellen** ⇒ Port-Schicht `port/prng.{h,cpp}`
  (`Prng::next/set_state`). Deterministisch ⇒ bit-exakte Anker (Seed 1: Block0 "Y.S K.I Y.K Y.F YSH KOB SAI",
  Endzustand 0x8398A68D).
- **P86/P87 (Werkzeugfallen):** `slw`/`srw`/`sraw` druckt der Projekt-Disassembler als (RS,RA,RB) — das
  **Ziel ist der ZWEITE** Operand; `srawi` **schreibt CA** (→ `addze` danach = Division durch 2 mit
  Abschneiden zur Null; CA des `subfic` davor ist wirkungslos). **P89:** Nachbildungen muessen ihren
  Ausgang aus dem MODELL lesen (eigener Fehler in `m84_ranking_action.py`, der Anker fand ihn).
- Regression **32 Frames + 63 Anker = 95, 0 Fehler**; Ghidra 2075. Doku `port-batch84-ranking-inhalt-2026-09-20.md`,
  Log §28, Status §52, `port-interface.md` §9.22.

## Batch 82: Testmode-Tastenzugang + 5-C-2-Messung
- **Der Schalterweg (CONFIRMED):** `[SDA(0xB0)] = 0x800B3928` ist die I/O-Statusstruktur;
  **Wort 1 = `+0x1C` -> `cfg+0x30`**, Wort 2 = `+0x18` -> `cfg+0x32`. Einziger Schreiber
  `FUN_80026C34` (`806200B0`, `A063001C`, `B07F0030`). **TEST-Switch = Bit 7 (`0x0080`)**.
- **NEU GEMESSEN:** **0 Instruktionen von 178534** schreiben `io+0x18/+0x1C`
  (drei Storeformen geprueft: fester Versatz, ueber addi/addic/addis abgeleitete Basis,
  indiziert) — Nachbarzellen tragen **27** Stores (Gegenprobe). ⇒ Hardware-Eingang.
  Werkzeug `scripts/m82_io_census.py`, Anker `port_selftest input` Abschnitt (27).
- **Port:** `port/host_input.{h,cpp}` (`HostInput::frame` = Taste -> io+0x1C ->
  Originalhook -> cfg+0x30; `HostInputConfig` mit Taste/Bit/`Hold`|`Toggle`;
  Umgebung `PORT_TEST_SWITCH_KEY`/`_BIT`/`_MODE`; `ScriptedKeyboard` + `Win32Keyboard`
  ueber `GetAsyncKeyState` = echtes Loslassen, ohne Fenster). Modi **`input`**,
  **`testmode`**, **`testmode-live [s]`**. Host-Pflicht: `frame()` **je Bild**.
- **Messwerte:** SCREEN CHECK (Eintrag 8) endet in 2 Bildern mit Taste, 0/3 ohne;
  COLOR CHECK im dritten Zustand; **13 von 20** Menueeintraegen enden mit der Taste
  (5 Ausnahmen = Einzelaufruf-Eintraege 1-5 ohne `(b)`); fremdes Bit `0x0100` ->
  **kein** Menue endet mehr. Regression **32 Frames + 55 Anker = 87, 0 Fehler**.
- **5-C-2 (gemessen, NICHT gebaut):** SCOPE DATA (`FUN_8000CD8C`, Pool 38) hat in seiner
  eigenen Funktion **keine** Anzeige (Blockvergleich `FUN_8000E090`/Commit `DFCC`/2x4-Byte-
  Kopie `FUN_8000CCEC`). **RANKING DATA (Pool 35/36) benutzt die BEREITS PORTIERTE
  Dialogkette** (`FUN_80016330` Text, `FUN_8000DB98` Ja/Nein, `FUN_8000DA80` Meldung mit
  Aktionsdeskriptor `[SDA(0x158)] = 0x800ACCB8` = Pool 36). Zustandsautomat `FUN_800277B8`
  (`s8(ctx+2)`: 1 = Text, 2 = Dialog -> Antwort `!=0` -> Zustand++). Texte:
  `0x80086BF4` "DO YOU WANT RECORD DATA CLEAR ? [     /    ]", `0x80086C24`
  "NO MODIFY RECORD DATA", `0x80086C00` "RECORD DATA CLEAR ? [     /    ]";
  Zeigertabelle `[SDA(0x154)] = 0x80099510` (+0x3C/+0x40). Blocksatzgroessen
  **452 B** (Indizes 0/1, Basis `cfg+0x68+28*idx`) und **100 B** (Index 2).
  ⇒ naechster 5-C-2-Schritt ohne neue Analyse. Die drei anderen Datenschirme = 5-E.
- **Regeln P80** (Zensus braucht drei Storeformen + Gegenprobe), **P81** (Zelle ohne
  Schreiber = Schnittstelle, keine Variable), **P82** (Tastendruck != Schalter; Toggle
  noetig, aber Default `hold` und als Port-Entscheidung dokumentiert).
- **Offen:** allgemeine Eingabeschicht — **seit Batch 86 begonnen** (Oberflaeche + Waffenpfad,
  s. `/memories/repo/eingabeschicht.md`); offen bleiben 87 (Analogauswertung), 88 (Moduswechsler
  in `FUN_80026C34`), 89 (Texteingabe HOME/PASSWORD), 90 (Spielseite).

*(Archiv Batch 79 — ueberholt:)*

## Batch 79: die 20 Bildschirmrahmen (Teil C-1) — Dateien/Messwerte
- `port/service_screens.{h,cpp}`: **Tabelle aller 20 Menueeintraege** (`ScreenDef`:
  (a)/(b), Zustandszelle mit **Breite**/Offset, Zeilen-/Sprungtabellenzellen,
  Zustandszahl, Gap-Text) + **14 Zustandsautomaten** + `ServiceScreens`
  (build/binden/run, `MenuSession` 1:1). Klassen `ScreenKind`:
  SingleCall (Eintraege 1-5, nur (a)), OptionsPage1/2, CoinOptions, ScopeAdjust,
  Factory, Chain2 (I/O, COLOR, SCREEN, HOME), Chain4 (MASK ROM, C.G.),
  Password, JumpTable (GUN, BOOK, GAME MODE).
- **Zustandszellen (SDA/Offset/Breite):** SOUND `0x24/+0/s8`, GAME OPTIONS
  `0x210/+0/s8` (+0x10 s8, +0x11 u8), COIN `0xB4/+0/s8`, SCOPE `0x1D4/+4/s8`,
  I/O + SCREEN/COLOR `0xB0/+0/s8` bzw. `0x1D0|0x1F0/+0/u32`, MASK ROM
  `0x1F4/+8/u32`, C.G. `0x200/+4/u32`, GUN `0x170/+0xC/s8`, BOOK `0x788/+4/s8`,
  HOME `0x7A0/+0xC/s8`, PASSWORD `0x7AC/+0x1C/s8` (+0 u32 Bildzaehler),
  GAME MODE `0x240/+0/u8`, FACTORY `0xE8/+0/s8`.
- **Sprungtabellen:** SCOPE `[SDA(0x1D8)]+0x84` Basis `[SDA(0x1E0)]` 0x11
  (nur 0/1/2/3/8 belegt); BOOK `[SDA(0x78C)]+0x248` Basis `[SDA(0x794)]` 0x19;
  GUN `[SDA(0x168)]+0x17C` Basis `[SDA(0x16C)]` 0x19; GAME MODE `[SDA(0x7C8)]`
  Basis `[SDA(0x7CC)]` 6.
- **4 Bildschirme inhaltlich vollstaendig:** SOUND OPTIONS (8 Zeilen),
  GAME OPTIONS (16 Zeilen + Anzeige-Init), COIN OPTIONS (7 von 9 Zeilen; Titel
  `[SDA(0x784)]+0x24` bei (0x1A,3)), SCOPE (7/7 Zeilen; Titel
  `[SDA(0x1D8)]+0x58` bei (0x16,3)). Neue sichtbare Seiten in `service-ui`.
- **P71 (KORREKTUR von P65):** Die Zaehlerzeilen **wrappen** (v==MAX -> 0 bzw.
  v==0 -> MAX), sie klemmen NICHT. Batch 77 hatte die `bc`-Polaritaet verdreht:
  **`bc 12,BI` springt, wenn das CR-Bit 1 ist; `bc 4,BI`, wenn es 0 ist.**
  `RowEdit::CounterClamp` heisst jetzt `CounterRange`.
- **P72:** Der dritte Parameter von `FUN_8000DCEC` ist die **ZEILENZAHL** (nur im
  Abbruchzweig als `FUN_8000DDD4(r5,1,-1)` benutzt), nicht `sound_id`.
- **P73:** Zaehlschritt-Regel fuer nicht portierte Inhalte: zaehlen, Zustand
  stehen lassen, Ende nur ueber den TEST-Switch.
- Weiter gemessen: `*([SDA(0xB0)]+0x56) = 1` = "Bildschirm aktiv" (**I/O-Zelle**,
  nicht cfg+0x56); COIN-Zeile **286** = `0x800809DC` (`ExitZero`, `" EXIT "`);
  GAME OPTIONS faellt von Zustand 0 durch 1 hindurch (`0,2,2`); I/O CHECK endet
  nur bei TEST **und** `0x64`; COLOR CHECK prueft TEST erst im dritten Bild.
- **Regression 32 Frames + 42 Anker = 74, 0 Fehler.** Ghidra 2075 (22 Dekompilate).

*(Archiv Batch 77 — ueberholt, nur zur Nachvollziehbarkeit:)*
# Paket e/f = Test-/Service-Modus (Stand Batch 77) — PORT-SCHRITT 5, TEIL A GEBAUT

## Batch 77: Servicemenue als Portmechanik (Dateien/Messwerte)
- `port/service_menu.{h,cpp}`: `read_menu_table` liest die Tabelle **aus dem Bild** und
  prueft die Satzform am Inhalt. **GEMESSEN:** Eintraege 1-5 = Stride **0x0C** ab
  `0x800993E0` `{desc_a, flags, name}`; Eintraege 6-20 = Stride **0x10** ab `0x80099420`
  `{name, flags, desc_a, desc_b}`; Nullwort bei `0x8009941C`. Eintrag 5 = idx 39 fn
  `0x80023AC4`. Flags breiter als ein Byte (0x00820000/0x08420000/0x00160000).
- `port/service_rows.{h,cpp}`: **37 Zeilenspezifikationen** (Wort/Shift/Maske/Bauform/
  Offsets) + 1:1-Zeilenmechanik + **Zeilendispatcher FUN_8000DCEC** (Zeilen sind
  **4-B-Zeigerarrays** auf Pool-Deskriptoren; Kursor = `cfg+0x2B` i8; Abbruchzweig
  `input & 0x64` faehrt die Zeile mit **r4 = 0**; Rueckgabe 1 -> Scroll 0) + FUN_8000DDD4.
- Pruefanker `port_selftest service` (Exit 0): 37/37 ROM-Wortanker, 17/17 Verhalten.
- **P65 (wichtig): Das Inkrement der Zaehlerzeilen KLEMMT am Maximum** (idx 63/64/77/83) —
  das Ghidra-Dekompilat zeigt faelschlich einen Wrap (`cmpwi cr1,rX,MAX; beq <Schreibpfad>`
  steht VOR dem `addic`). idx 80 ist die Ausnahme (echter Zyklus 0<->1).
- **P66:** Feldrueckschreibung ist `rlwimi rWort,rFeld,SHIFT,MB,ME` (SHIFT = Feldlage).
- **P67:** Gate-Zuordnung: `[SDA(0x18)]+0x1A` nur idx 77; idx 82/83 pruefen Profil {0,3,4}.
- **Offen:** Text-/Node-Schicht, Speicherdialog (`FUN_8000D980`-Kette), 20 Bildschirmrahmen,
  COIN-Zeilentabelle (Halter `FUN_80080928`), Paket-d-Emitter. Rest Schritt 5: 5-6 Batches.

# (Archiv) Paket e/f = Test-/Service-Modus (Stand Batch 59, 2026-09-17) — PAKET e KOMPLETT

## Kernfakt
Paket e (89 Pool-Records) ist der **komplette Konami-Servicemodus** + Textschicht.
**89/89 gelesen** (Batch 59). Paket f (16 Records) = Konfig-Datenverwaltung + Boot/IO;
davon gelesen: idx 34/37/38/306/307, offen: 12 Boot-/IO-Records (nicht port-blockierend).

## Menue-Tabelle / Bildschirm-Vertrag
- Menue-Tabelle `0x800993E0`, 20 Eintraege, Felder = Pool-Deskriptoradressen.
- `(a)` = Init (Zustandszelle 0, `FUN_8001634c(buf,8)`), `(b)` = Frame, Rueckgabe 0/1,
  Abbruch ueber **`cfg+0x30` Bit 7**.
- Zeilen-Tabellen: `SDA(0x1DC)` = 7 = **SCOPE SCREEN ADJUST** (UP/DOWN/LEFT/RIGHT/
  DEFAULT SETTINGS/SAVE AND EXIT/EXIT — Labels in `SDA(0x1D8)+0xC8..+0x10C`);
  `SDA(0x208)` = 8 + `[SDA(0x208)]+0xE0` = 16 (Options-Seiten);
  `SDA(0x790)` = 12 Deskriptoren (Book-Keeping-Zeilen inkl. Uhr), `+0x48` = 8-B-Saetze
  (INCOME DATA of LAST 7 DAYS / PLAY DATA SUMMARY / COIN SLOT1|2 ... 52 WEEKS/WEEK).
- 6 Familien der 43 Batch-59-Records: Buchhaltung/Ranking (19/20/23/24/25/26/29/31/32/35/36),
  SCOPE-ADJUST-Zeilen (47-54), Sequenz idx 100 (9er-Sprungtabelle), COIN-Zeilen (278-302),
  Book-Keeping-Zeilen + Uhr (289/292/293/294), Boot-/Rechte-Sequenz (316-325).

## Konfigurationsblock [SDA(0x14)] — siehe /memories/repo/config-modell.md

## Zahlen (Batch 59)
- Pool streng **315/327 = 96,3 %** (offen 12 = nur Paket f); Paket e **89/89 = 100 %**;
  Paket f 4/16; **kombiniert 526/628 = 83,8 %**; Ghidra 2072 Funktionen.
- Coverage Paket e **4,9 %** (241/4906); die 43 neuen **7,0 %** (11 Live-Records:
  idx 278/279/283/284/285/292/293/294/321/322/323 — die Batch-58-Restliste);
  Options-Zeilen kalt; Paket f 0/215.
- Render-Kontakt **14/89** (NICHT 51/89 — Batch-58-Zahl war Spannen-Artefakt);
  Textschicht `0x80016330` x9 / `0x8001634C` x6; Record-Bau-API nur in idx 43 + 276.
- 10 direkte Pool-zu-Pool-`bl`-Aufrufe (idx 35->36, 43->42, 279->280/281, 321->250/251,
  326->313/314, 311->304, 64->7) — Pool-Records rufen sich also AUCH direkt.
- Zeilen-Handler-Template (28 Insn) traegt Options-, SCOPE-ADJUST- und COIN-Zeilen
  (imm 0.964, z. B. idx 52 == 69 == 87 == 285).
- Stubs: idx 27/28 = 4-B-`blr`; idx 299-302 = 8-B-`li r3,X; b` (Registrierungsplatzhalter).

## Port
Wertetabellen 1:1, cfg-Struktur + Default-Profile 1:1, Bitfeld-/Default-Semantik 1:1,
**ein** Hook fuer das Eingabewort (Schreiber `FUN_80026C40`), Menue-UI nachbauen,
Selbsttests optional (MASK ROM/C.G. BOARD auf PC sinnlos).
Naechster Schritt: `analysis/config-interface.md` (cfg + defaults[5][4] + Bitfeldkarte +
Eingabewort-Mapping + Menue-/Zeilendaten), dann Port-Start.
