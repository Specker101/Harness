# Objektsystem-/Dispatch-Tabellen (Batch 42, CONFIRMED, Silent Scope Decomp)

## Die drei Tabellen (r2 = 0x800ADA5C; SDA-Zelle = r2 + Offset)
- **`SDA(0x5E8)` = 0x800AA380** = Objekttyp → **5 Methoden-Deskriptoren**, Stride **0x14**,
  **genau 40 Typen**, Ende exakt 0x800AA6A0. Kopiert von `FUN_8004A76C` nach
  `obj+0x158/0x15C/0x160/0x164/0x168`. Default-Methode = `0x800AD060` = `{0x8004A288=blr, r2}`.
  `0x800AD0D8` = `{0x8004CEE0}` = Aktor-Modusautomat als geteilte Standardmethode.
- **`SDA(0x300)` = 0x8009E218** = Objekt-/Formtyp-Tabelle, Stride **0x5C**, ~80 Typen.
  `+0x3C` = Zeiger auf Teil-/Trefferliste (0x800A4A90..0x800A5Exx), `+0x40` = Größe,
  `+0x48` (s16 `+0x4A`) = **Kollisionsradius** (600/1200/2100/3500/4200). Index = `s16(obj+2)`.
- **`SDA(0x5AC)` = 0x800AA300** = 8 Sicht-/Overlay-Methodensätze × 3 Slots (+0-Sentinel);
  Konsument `FUN_80051D58` (`lwz r4,0x5ac(r2)` @ 0x80051D5C).
- **`SDA(0x220)`** = globaler Spielzustand: `+0x72` = Stage-/Szenen-Id, `+0x78` = Timeline-Zähler,
  `+0x10` = Render-State-Wort (textureMode-Basis).
- **`SDA(0x578)`** = Szenen-/Missionszustand (Zähler `+0x49`/`+0x4A`, `+8`).

## Die 327-Record-Deskriptor-Tabelle
- `[0x800ACB08, 0x800ADA5C)`, Stride 0xC, Record `{u32 Ziel, u32 r2, u32 0}` = **Methoden-POOL**,
  kein Typ-Verzeichnis. Aufruf über Far-Call-Thunk `FUN_8000005C` (lwz r0,0(r11); stw r2,0x14(r1);
  mtspr CTR,r0; lwz r2,4(r11); bctr).
- 65 Ziele waren Ghidra-Funktionen, **262 sind echte Funktions-Einstiege in Code-Gaps**
  (0x Innenraum; 261/262 blockbeendendes Vorgängerwort) → `create_function` an jedem Ziel legitim.
- Verdrahtung: 640 Referenzen → 97 Konsumenten-Arrays (`analysis/_m42_wiring.csv`).
  Gruppieren NACH Konsumenten-Array, nicht nach Adressnähe.

## Treffer-/Kollisionssystem (Batch 42, CONFIRMED)
- Kern `FUN_80052710` = Schussauswertung: Strahl gegen 12-B-Teilrecords
  `{s16 x,y,z, s16 Radius, s8 next, s8 flags, … s8 Trefferwert @+0xB}`, verkettet über
  Szenengraph-Knoten (`FUN_8003AECC(obj+0xF8, n)`), **Zerstörungsmaske `obj+0xBC`**.
  Rückgabe 0xFFFFFFFF = kein Treffer, sonst Trefferwert.
- Zweistufig: `FUN_80053028`/`FUN_800530D0` lesen `[SDA(0x300)]+Typ·0x5C+0x3C`, Deskriptor-Ferngriff;
  bei Rückgabe 0 → `FUN_80052710(ray, obj, d+0xC)`. Konvention 0 = Treffer, -1 = kein Treffer.
- `0x8005xxxx`-Familie: `FUN_8005132C`/`FUN_80050F30` Segment-vs-Box-Clip (t Q12, 6 Flächen),
  `FUN_80050C98`/`0D78`/`0E5C` Segment-Rotationen (XY/XZ/YZ-Ebene, sin/cos Q14 `>>0xe`),
  `FUN_80052B08`/`FUN_8005299C` orientierte Radiustests, `FUN_8005293C` einfacher Radiustest.
- `FUN_8005EA5C` = leerer `return`-Handler (legitimer Slot-Wert), `FUN_80068B80` = leer.

## Werkzeuge (alle offline, 0 Ghidra)
- `scripts/f5_descr_triage.py` / `f5_descr_wiring.py` / `f5_descr_group.py`
- `scripts/f5_descr_fingerprint.py` = **Offline-`bl`/SDA-Fingerabdruck** (40 Insn je Ziel; braucht
  korrekte 26-Bit-Signextendierung! `v & 0x03FFFFFC`, Vorzeichen aus Bit 25) — regionsscharf, nicht
  funktionsscharf.
- `scripts/f5_descr_classify.py`, `scripts/m42_typetable.py`, `m42_table_refs.py`, `m42_gap_create.py`
- Bilder/Artefakte: `analysis/_m42_*.{csv,txt}`, `analysis/_m42_dump{A..E}.txt`

## `SDA(0x304)` = Modell-/Objekt-Slot-Registry (Batch 44, CONFIRMED)
- **`SDA(0x304) = 0x800FFE00` (RAM!)**, Stride **0xC**, Eintrag
  `{+0 Zeigerarray (u32* je Element), +4 Bitmaskenarray, +8 Anzahl}`; **85 Slots**
  (`0x800FFE00..0x801001FC`, direkt vor `SDA(0x30C) = 0x80100200`). Zelle =
  statisches Image-Wort (`0x800ADD60`), **0 Schreibstellen**; Inhalt nur von
  **`FUN_8005D884`** geschrieben (Zaehler `SDA(0x3D0) = 0x80111254`, Name→Slot-Tabelle
  `SDA(0x3D4) = 0x80111258`, 8-B-Records, `strcmp` via `FUN_8005D738`).
- **Slot-Aufteilung disjunkt:** `0..0x4D` = Type-Slots (Reset `FUN_8005E974` nullt
  deren `+8`; Zaehler danach 7), `0x4E..0x53` = Men-Modelle (`FUN_8005E6D0`, nutzt die
  Konstante `0x3A8 = 0x4E*0xC` als Basis). `count == 0` = ungueltig; Slot 0x54 frei.
- **Index = `s16(obj+2)`** — derselbe Index wie `SDA(0x300)` (Stride 0x5C, **79 Typen**,
  endet exakt `0x8009FE7C`); `(char)*(u16*)(obj+4)` = davon **verschiedener** Raum
  (40x5-Methodenmatrix). `SDA(0x300)[typ]+0x34` = **Modellname** (statische ROM-Bindung;
  48/79 Typen gesetzt, 6 distinkte Men-Namen; nur Typ 21 = `trk0` aus Satz D).
- **9 Lesestellen** (alle `lwz …,0x304(r2)`): `8004DC20` (Tail-Call-Wrapper: Phasenoffset
  mit Skalierung eines Fremd-Slots vorrechnen → `b Funk8004DC58`), `8004DC58` (Kern),
  `8004F8C4` (Getter), `8004FC60` (Zuweisung), `8005D738` (Name→Slot), `8005D884`
  (Registrierung), `8005E6D0`/`8005E874`/`8005E974` (Men-Buendel- bzw. Name-Loader, Reset).
- **`FUN_8004FC54` = Wrapper** (`param_3 >> 4`) → `FUN_8004DC58`. **`FUN_8004FC60
  (obj, elemIdx, rowOffset, scaleNum, flags)`** setzt `obj+0x94` (Flags|1, Bit5 = Maskenbit),
  `+0x96` (Element-Index), `+0x98` (Skalierung `(u16(elem+0x10)*scaleNum)>>4`, min 1),
  `+0x9C` (Zeilen-/Phasenoffset; Default `s16(elem+0xC)*0x10-1`), `+0xA0` (Element-Zeiger);
  sonst `+0xA0 = 0` und Bit0 von `+0x94` loeschen.
- **Pose:** `FUN_8004DD18` schreibt in die Szenengraph-Knotenkette (`obj+0xF8`, Stride 0x60)
  `node+2/+4/+6 = x/−y/−z`, `node+10 = u16`; `FUN_8004F0C4` (unpacked) / `FUN_8004EF0C`
  (10-Bit-gepackt) lesen Steuerbytes (Bit0/1/3/4/5) + Animationsstrom; `FUN_8004F5A4`
  (0x18-B-Ring-Slots in `SDA(0x30C)`), `FUN_8004F3C8`/`FUN_8004F244` (Keyframes `SDA(0x310)`).
- **Element-Blockkopf (0x14 B):** `+0 rel. Offset Teilblock`, `+4 Steuerbytes`, `+8 Animation`,
  `+0xC s16 Stride`, `+0xE s16 Zeilen`, `+0x10 u16 Skalierung`, `+0x12 u16 Flags`.
  **10-Bit-Packung** (`FUN_8005D440`): `w = (z>>4 & 0xFFC) | ((x & 0xFFC0)<<16) | ((y & 0xFFC0)<<6)`
  (x = Bits 22..31, y = 12..21, z = 2..11). **Deltas:** `FUN_8005D8CC` rechnet Praefixsummen
  je Zeile und relokalisiert die `+0xC`/`+0x10`-Zeiger in-place (Flags &= ~1).
- **Set D ≠ Set B:** Set D (`objdata, trk0, st*, cst*`) = Pose-/Objektbloecke (Offsetliste +
  Blockkette); Set B (Ladeliste: `zako01, player, HGIRLS*`) = **Skin** (Kopf 0x18 +
  Teiltabelle 8 B + Namensblock + 12-B-Texturrecords + Geometrie).
- Werkzeuge Batch 44: `scripts/m44_sda304.py`, `m44_dir.py`, `m44_typetable.py`,
  `m44_setd.py`, `m44_setb.py`; Doku `analysis/f5-descr-batch44-2026-09-17.md`.

## `SDA(0x180)` = STAGE-LADELISTE + Skin-Bindung (Batch 45, CONFIRMED)
- **`SDA(0x180) = 0x800FA658`** = **Ladeliste der aktuellen Stage**: 16-B-Saetze
  `{+0x00 Name, +0x04 Ladeklasse 0..5, +0x06 Klassen-Startwert, +0x08 Klassen-Zielbasis, +0x0C}`,
  Stride **0x10**, **Kapazitaet 64** (`0x800FA658..0x800FAA58`, `SDA(0x184)` folgt exakt),
  genutzt **7..24 je Stage**; Zelle **schreibfrei** (12 Lese-, 0 Schreibstellen) — Inhalt nur
  indirekt geschrieben (`FUN_8002A188`/`A1D4` Füller, `FUN_8002A204` Reset, Loader-Phasen).
  Kopf `SDA(0x178) = 0x800FA630`: `+0 Anzahl, +2 Index, +4 Phase 0..5, +6 Stage, +8 Fortschritt,
  +0xA Schrittweite, +0xC Aux-Groesse, +0xE Transfer-Flag, +0x10 Optionswort, +0x14 Klassenwert,
  +0x18 Sprungtabellenbasis, +0x1C Container-Zieladresse`.
- **6 Ladeklassen** aus `SDA(0x1A4) = 0x8009BEB0` (+0x190/+0x188 global, +0x130/+0xA8/+0x68/+0
  = 6-Zeiger-Tabellen je Stage): 0 global (start,effect,game,weapons,weapons2,Ficon),
  1 system, **2 Charakter-/Skin-Container** (zako01,HGIRLS1,citizen,tero,boss*,player,last),
  3 Stage-Container (st11,st1st2,bluesky,st51,st21,st31,st41,st4sky,st43,st43sky),
  4 leer, 5 Overlay/UI (sway,sway0,sway1,savingw,savingd,savingp,icon). Summe 85 Namen —
  **kein** Bezug zu den 85 `SDA(0x304)`-Slots.
- **Lader = 6-PHASEN-MASCHINE** (`head+4` = Phase; Sprungtabelle `SDA(0x1C4)+0x1C0`, Basis
  `SDA(0x1C8) = 0x800291F8`; Stubs `0x80029FE4..0x8002A00C` sind in `FUN_80029F50` eingesogen,
  nur per `disassemble_bytes` sichtbar): 0 `FUN_8002946C` Name→Ziel+LZSS-Auftrag,
  1 `FUN_8002967C` Aux-Container aus Verzeichnis `0xFF1FCA00` → `0x803C0000`,
  2 `FUN_800294E0` Aux-Pakete → beide SHARC-Boards, 3 `FUN_80029394` Queue leer → Relokator,
  4 `FUN_80029224` Modell-/Texturpakete → Boards, 5 `0x800291F8` Index++/Reset.
  Fertig = `FUN_80029F50() != 0`; Baut die Liste: `FUN_8002A028(stage,flags)` ← `FUN_80059EA4`.
- **Relokator (Gap `0x80029A50`)**: `part_table_off`/`name_off` → absolute Zeiger; fuellt
  **`SDA(0x1B4) = 0x800FAAA8` = flache 16-B-Tabelle ALLER Teile (1024**, bis `SDA(0x1B8)`),
  `{+0 ID, +4 ?, +8 Blockzeiger, +0xC Globalindex}`; registriert Gruppe in
  **`SDA(0x1B8)/0x1BC/0x1C0` (je 32x4 B)** = `{1<<Klasse, ID-Basis, Containerkopf}`,
  `*SDA(0x188)` = Gruppenzaehler, `*SDA(0x190)` = naechste ID-Basis.
- **Skin-Bindung = PRAEFIX-NAMENSSUCHE** (NICHT ueber SDA(0x180)!):
  `FUN_8002AB84(name)` (17 Aufrufer) / `FUN_8002A8EC(name, 1<<Klasse)` suchen bis zum **Ende des
  Suchbegriffs** in den Teiltabellen aller registrierten Container → `Tabellenindex +
  ID-Basis[Gruppe]` = globaler Teil-ID (0 = nicht geladen). Schluessel = Praefix wie
  `S4_M0011` (in st41), `eff_aexpls17` (in effect), `K6_GA021` (in st43), `skin_test`.
- **Typ-Record liefert den Schluessel**: `[SDA(0x300)]+typ*0x5C` `+0x18` = Skin-Basisname,
  **`+0x1C`/`+0x20` = Variante 1/2** (skin_test/Sskin_test/SSskin_test; auch cindy/flex/jon/
  tiffany/spike/barbi/billy/maid/hbrond_bw…), `+0x10` = generischer Name, `+0x34` = Set-D-Modell.
  Namenspool `0x800895B0..0x80089B20` (253 Zeiger).
- **Objekt→Skin im Code**: Spawn `FUN_800495CC` → `FUN_8003ADE4(obj, knoten, SDA(0x618)[idx],
  SDA(0x61C)[idx])` schreibt globalID/localID in **3 Sub-Knoten** (`node+0x34` u32 / `node+0x32`
  u16). Aufloesen: `FUN_8002A9F0(id)` → `+0x08` Block → Sub-Block `n*0x18` (raw+cooked) →
  12-B-Texturrecord → `FUN_8001A82C` (0x65/0x66). Laufzeitwechsel nur per Skriptliste
  `FUN_80048FA8` (`(char)(obj+0x174)[obj+0x168]` → `SDA(0x16C)/0x170`, −1 = Ende).
- **4 ID-Raeume:** `obj+2` Typ (SDA(0x300) 0x5C / SDA(0x304) 0xC), `obj+4`-Lowbyte
  Methodenklasse (SDA(0x5E8) 40x5), **globaler Teil-ID** (SDA(0x1B4) 0x10), **localId**
  (container-intern, 8-B-Teiltabelle, nach Name sortiert, `{u32 localId, u32 name}`).
- Container-Kopf (Set B): `+0 0, +2 s16 Anzahl, +4 s16 Suchstart, +6 s16 Suchschritt,
  +8 -> Teiltabelle, +0x10 -> Gruppentabelle`; Beispiele: zako01 35/31-16, car2 10/7-4,
  boss4 39/31-16, st41 46/31-16, effect 177/127-64.
- Werkzeuge: `scripts/m45_{sda180,tables,refs,refs2,wholoads,namerefs,typetable2,datadump,disasm}.py`;
  Doku `analysis/f5-descr-batch45-2026-09-17.md`, Rohdaten `analysis/_m45_*.txt`.

## Phasen-Handler-Schicht der Aktor-Matrix (Batch 43.1/43.2, CONFIRMED)
- **Phasenablauf = RELATIVE Tabellen, aber der Block ist VIELBASIG**: `SDA(0x56C)=0x8008AA10`
  (Basis `SDA(0x570)=0x80068B80`), `SDA(0x594)=0x8008AD28` (Basis `SDA(0x598)=0x800505D8`),
  `SDA(0x5D8)=0x8008AD68` (Basis `SDA(0x5DC)=0x8004BC68`, 7 Eintraege ab `+0xC`),
  `SDA(0x5E0)=0x8008AD98` (Basis `SDA(0x5E4)=0x80049DA0`, 10 Schritte),
  `SDA(0x5EC)=0x8008ADD8` (Basis `SDA(0x5F0)=0x80072540`); weitere Gruppen ab `SDA(0x604)=0x8008B000`
  (Basis `SDA(0x608)=0x80076E80`), `0x614/0x658/0x684/0x6A8/0x6B0/0x6C4/0x700`.
  **Nie eine Basis fuer den ganzen Block annehmen** — Teile sind auch DATEN (`+0xEC`, `+0x100`,
  `+0x19C` gehen an `FUN_8003ACFC`).
- **Gruppe A (Basis 0x80068B80) = 14 Tabellen / 168 Eintraege / 157 distinkt / 54 mit Coverage /
  0 im 327er-Pool**: `+0x18` Kl.4 (16), `+0x58` Kl.5 (17), `+0x9C` Kl.6 (12), `+0xCC` Kl.7 (8),
  `+0x110` Kl.11 (17), `+0x154` Kl.12 (10), `+0x17C` Kl.13 (8), `+0x1C4` Kl.24 (13), `+0x1F8`
  Kl.25 (8), `+0x218` Kl.26 (6), `+0x230` Kl.27 (9), `+0x254` Kl.29/30 (13), `+0x288` Kl.29/30 (17),
  `+0x2D8` Kl.32 (14). Laenge = `cmplwi n-1` im Dispatcher.
- **Tabelleneintraege sind Thunks, ZWEI Bauformen** (Batch 43.3): Kl.5 = `addi r3,r31,0` +
  **`bl` Koerper** + `b` gemeinsamer Epilog (3 Insn); Kl.6/7 = `addi r3,r31,0` + Epilog + `b` Koerper
  (4 Insn). **Objekt in `r31`** (Kl.5/6 zusaetzlich `r29 = obj+0x208`, Kl.5 `r30 = 0`), Rahmen bleibt
  der des Dispatchers (`bctr`). **Kl.5, Kl.6 und Kl.7 teilen dieselben vier Koerper**
  (`80071A28`=D16C, `80071B30`=D7CC+D430, `80071AD0`=D334, `80071A68`=D194).
  Thunk-Erkennung nur ueber Funktionsgroesse <= 4 Insn (sonst zaehlen Rumpffunktionen wie
  `FUN_80070FE0` faelschlich als Thunks). **Klasse 3 hat KEINE Tabelle**: `FUN_80071BE8` =
  handkodierte `if`-Kette ueber `s16(obj+4)>>8` x `obj+0x154` (0/1/2), ohne `SDA(0x56C)`-Zugriff.
- **`obj+0x268…0x290` ist eine UNION** (Batch 43.3): fuer Kl.4…7 = Angriffsketten-Block
  (`0x268` Wegpunktzaehler, `0x26A/26C` Zielfilter, `0x270` Zielzeiger, `0x274` Trefferwahrsch.,
  `0x27A` Wartezeit, `0x27D` Rueckkehr-, `0x27E` Abbruchphase, `0x27F` Quittung, `0x280/281` Flags),
  vier getrennte Initialisierer (Kl.4 `FUN_80071760`, Kl.5 `FUN_80071170`, Kl.6 `FUN_800709C0`,
  Kl.7 `FUN_80070494`); **fuer Klasse 32 sind dieselben Bytes Pfadkoordinaten** (12-B-Records bis
  `obj+0x290`, `FUN_80069158`). **Feldbedeutung ist klassenabhaengig**; Kl.3 nutzt den Block nicht.
- **`obj+4` = Startphase/Variante, `obj+5` = Verhaltensklasse** (Beleg `FUN_8004A76C`:
  `obj+0x154 = (char)(u16@obj+4 >> 8)`, Methodenzeiger aus Zeile `(s8)obj+5`; `obj+0x14F` = Team =
  Szenen-Id `[SDA(0x220)]+0x72`). „Mode“ in den Zielfiltern IST die Startphase.
- **Aktor-API-Erweiterung**: `obj+0x170` = Modus-Wort (Low-Byte Wartebedingung = `FUN_8004B5A4`;
  **korrigierte Bitliste aus `FUN_8004ABA4`** (Batch 43.3): 16 Elternknoten, 17 y+Heading,
  18 Inkremente `obj+0x18c…0x19C`, 19 Abbruch statt Countdown, 20/21 Geschwindigkeit+Auto-Stop,
  22 Vektor in Heading drehen, 23 Geschwindigkeit aus Abstand, 24 Geschwindigkeit = Abstand/`obj+0x174`,
  25 Ziel = globale Entity, 28/29/30 Richtungsvarianten; **Bits 26/27 nur ueber die Sammelpruefung
  „Bits 23…27 irgendeins“ = Richtungsauswahl** — die 43.2-Zuordnung „Bit27 = Delta/Countdown“ war
  falsch nummeriert);
  `obj+0x174` = Countdown UND Schrittweite; `obj+0x1a0/1a4/1a8` Ziel, `obj+0x178/17c/180`
  Geschwindigkeit (Q7), `obj+0x34/36/38` Heading, Integrator `FUN_8004ABA4`.
  `obj+0x270` Zielzeiger, `obj+0x26A/26C` Zielfilter (Typ/Klasse/Mode), `obj+0x274`
  Wahrscheinlichkeit, `obj+0x27D/27E` Rueckkehr-/Abbruchphase, `obj+0x27F` Quittung,
  `obj+8` = Lebendbedingung (`s16 > 0`), Objektpool `[SDA(0x358)]` = 64 x `0x34C`.
- Kl.6: Wegpunkt-Records `obj+0x208 + n*0xC` (4 Stueck, Eintrittsphase 0..3 waehlt Satz),
  Per-Frame `FUN_800705A0`, Gruppe 0, Zieltfilter Typ 4 (`GunMen`).
  Kl.7: keine Wegpunkte/kein Per-Frame, Gruppe 2, Zieltfilter Klasse 6 / Mode 0.
- **Operatoren der Kette (Batch 43.3)**: `FUN_8004D430`/`D334` = Zielposition uebernehmen +
  Pose + `obj+0x170 = 0x28000000` + Countdown (`obj+0x1bc`/`0x1be`) — **keine Translation**
  (Geschwindigkeit wird auf 0 gesetzt; Bit 24 fehlt) ⇒ „ausrichten + N Bilder warten“.
  `FUN_8004D52C` = Knoten `0x1a` loesen; `FUN_8004D558` = Knoten `0x1a` an **Gruppe-C-Basis
  `SDA(0x5D8)`** binden + Alarm(4,1) + Pose `0x70`; `FUN_8004D5D4` = Pose `0x6F`;
  `FUN_8004D62C(obj,t)` = Pose-Block `0x1D2=3`, `0x186=0x1611`, `0x170=0x14000000`, `0x174=t`;
  **`FUN_8004D94C`/`D9EC` = Wegpunkt-Erzeugung**: lokale (heading-relative) Offsets werden per
  `FUN_8001C018` gedreht und zur Position addiert ⇒ `obj+0x208 + n*0xC` = **absolute Welt-Wegpunkte**.
- **Klasse 5 (Batch 43.3)**: Ph9–Ph16 = Schusskette (Pose `0x6F` → Knoten `0x1a` abhaengen →
  loesen → Rueckkehrphase `0x0E` + Alarm(4,2) → 10-Schritt-Maschine → Wegpunkt `obj+0x214` →
  `FUN_8004D62C(obj, s16(obj+0x27A))` → Wegpunkt `obj+0x208` → zurueck auf Phase 12);
  Slot 3 `FUN_80070C64` = Trefferreaktion wie Kl.6 `FUN_800705A0`; Slot 2 `FUN_80070D54`
  stellt das Heading aus dem Merker `obj+0x284/286/288` zurueck.
- **Namenfund:** `[SDA(0x5D8)] = 0x8008AD68` beginnt mit dem String **`wep_radio`** (+ 7 relative
  Offsets `0x164C…0x167C` gegen `SDA(0x5DC) = 0x8004BC68` + Tag `IBM`). `FUN_8004D558` uebergibt
  diesen Zeiger an `FUN_8003ACFC` -> `FUN_8002AB84` (Praefix-Namenssuche) ⇒ **Knoten `0x1a` =
  Skin-Teil `wep_radio`** (Klasse 5 Ph10 haengt das Funkgeraet/Waffenteil an). Die Basen der
  Gruppen B (`0x8008AD28`), D (`0x8008AD98`), E (`0x8008ADD8`) tragen keinen Namensstring.
- Werkzeuge: `scripts/m43b_{phasecov,fieldscan,sdaread,dispatchextract,phaserederive}.py`,
  `scripts/m43c_{tables,rows,fieldscan,fieldowner,funcranges,modeword,obj4,ctor_callers,bodies,poolcheck,cov}.py`;
  Doku `analysis/f5-descr-batch43-teil2-*.md`, `…-teil3-2026-09-17.md`.
- **Zaehlungen (Stand Batch 47)**: 327er-Pool **133/327**; Gruppe A **54/157 Eintraege** =
  **46/149 Koerper** (168 Eintraege → 157 distinkt → 16 Thunk-Vorkommen/15 Adressen → 149 Koerper;
  *die in 43.3 genannte „51/157" ist nicht reproduzierbar*); kombiniert
  **184/484**. Tabelleneintraege ≠ Codekoerper — beide Zahlen fuehren.
- **Coverage-Map** `capture/ppc_coverage*.bin` (`SSCOV1`) = **1 Byte pro 32-Bit-Wort**
  (Vollausfuehrung = Groesse/4). **Feldscans immer mit `ra != r2`**, sonst zaehlen SDA-Zellen mit.

## `obj+4`/`obj+5` + Typ→Klassen-Bindung (Batch 46, CONFIRMED)
- **`obj+4` (u16) wird genau einmal im Spawnpfad geschrieben: `0x8006215C sth r0,0x4(r28)`
  in `FUN_80062124`** — Wert = `u16(Spawn-Record+8)`; davor `sth r0,0x2(r28)` = Typ aus `rec+6`.
  Weitere Schreiber: `0x80084DA0` (Szenenskript, **Pool-Objekt #0** → 0), `0x80062AF0`
  (**Wiederherstellung** nach Memset in `FUN_80062A4C`). **`obj+5` hat 0 Schreibstellen**
  (Low-Byte desselben `sth`).
- **Konstruktor per Far-Call über Typtabelle `+0x00`**: `0x800621F8 lwzx r11,r9,Typ*0x5C`
  + `0x800621FC bl 0x8000005C` ⇒ **`FUN_8004A76C` hat deshalb keinen `bl`-Aufrufer**.
- **Nur die 48 Typen mit `+0x00 = 0x800ACF40` UND `+0x58 = 0x800AA380` nutzen die 40×5-Matrix**;
  die 31 anderen haben eigene Konstruktoren (idx 237 `FUN_80077C98` Fahrzeuge, 240 `FUN_8007C1EC`,
  242 `0x80048E0C` `en_trg0..6`, 245 `FUN_8007BE78`, 247 leer).
- **Keine Typ→Klassen-Tabelle:** Klasse = authorendes Feld des **Spawn-Records**
  (0x20 B): `+0 Stage, +2 dStage(-1), +4 Timeline, +5 dTimeline(-1), +6 Typ, +8 Klassenwort
  (high Startphase/low Klasse), +0xA Flags (Bit0 = weiter), +0xE/0x10/0x12 Heading,
  +0x14/0x18/0x1C Position`; Terminator `FF FF FF FF` + 28 Nullen. **439 Records / 16 Arrays**,
  Tabelle `analysis/_m46_typclass_final.csv`.
- **Kanonische Paare:** K5/K4/K13 = Typ 13 `RifleMen`; **K6 = Typ 14 `MachineGunMen` ↔
  K7 = Typ 4 `GunMen`** (beidseitiges Jagen); K3 = Typ 35 `EmptyHandMen`; K23 = Typ
  17/18/29/30/35/43; K29/30 = Typ 14/3/57; K32 = Typ 46/60 `GunMen`; K24 = Typ 44/45 `ShotGunMen`.
- **Felder der Spawnmaschine:** `FUN_8006269C(arr)` → `*(SDA(0x330)+*SDA(0x334)*8+4)`;
  `SDA(0x36C)` = Aktive-Objekt-Zeigerliste, `SDA(0x384)` = Cursor, `SDA(0x460)` = Spawn-Budget
  (`>>1` je Record); Stage-Tabelle ab `0x800A0BE8` = `{Name, Array, Stage<<16}`;
  **Objektgröße 0x34C** (`FUN_80062C78` 64×0x34C **und** `FUN_8000D140(obj,0,0xD3)` = 211 Wörter).
- Doku: `analysis/f5-descr-batch46-2026-09-17.md`, Status §13; Skripte `scripts/m46_*.py`.

## PAKET c `0x8005xxxx` = TREFFER-/KOLLISIONSSCHNITTSTELLE (Batch 56, CONFIRMED, 19/19)
- **Callee-Zensus (Regel 316): 22 distinkte Callees, 0 im Pool, 0 Render-Kern.** Einziger
  `0x8001xxxx`-Callee = `FUN_8001D788` (3x3-Festkomma-Matrix x Vektor). ⇒ Paket c ist **renderfern**
  (Paket d: 17 Render-Callees). 14 der 22 Callees liegen im eigenen Band.
- **`FUN_8000005C` = Deskriptor-Trampolin** (5 Insn, `lwz r0,0(r11); stw r2,0x14(r1); mtspr CTR,r0;
  lwz r2,4(r11); bctr`) — war als Far-Call-Thunk seit Batch 26/42 bekannt; Batch 56 belegt die
  **ABI-Rolle**. ⇒ **Aufrufer von Pool-Records vorrangig ueber DESKRIPTORadressen als Rohwoerter
  suchen** — **REGEL 301 IN BATCH 57 KORRIGIERT:** es gibt **17/327 (5,2 %) Pool-Records MIT
  direkten `bl`/`bc`-Aufrufern** (51 Stellen): idx 124 `0x8004CEE0` (Matrix **K4.S2**) 13x,
  idx 7 `0x8000F928` 18x, idx 89 `0x80041F54` 2x (C-99 `li r3,5`, C-94 `li r3,1` — disassembliert
  belegt). Doppelrolle = Methodenslot **und** geteilter Bibliotheks-Helfer ⇒ **Methodenslot ist kein
  exklusiver Aufrufweg**. Werkzeug `scripts/m57_callers.py`, Artefakt `analysis/_m57_callers.txt`.
  `idx = (desc - 0x800ACB08) / 12`.
- **Typzeile `[SDA(0x300)] = 0x8009E218`** — **KORRIGIERT in Batch 57: 79 Zeilen x 0x5C**
  (Batch 56 hatte nur die ersten 40 gesehen; letzte Zeile mit 3 gueltigen Deskriptoren = **78**,
  Tabellenende `0x8009FE7C`), **6 Methodenkombinationen** — A `90/235/236` x48 · B `237/238/239` x18 ·
  **D `242/243/244` x8** (Zeilen 49-54, 64, 72) · C `240/241/239` x3 (24, 25, **76**) ·
  **E `245/246/239` x1** (Zeile 63) · **F `247/247/248` x1** (Zeile 78). Die 48 Zeilen mit
  `+0x58 = 0x800AA380` = genau die 48 A-Zeilen (= die „48 Typen" aus Batch 46).
  **Offsetkorrektur:** `+0x40` = **NULL**; **`+0x42` = s16 Skala** (100..10000);
  `+0x4A` = **s16 Kollisionsradius** (500/1200/2100/4200); `+0x3C` = Zonenlisten-Zeiger
  (0 = keine: Zeilen **5, 27, 34, 40, 56, 66, 78**); `+0x10` = geteilter Datenzeiger `0x800895C0`;
  `+0x30` = 3 (Zaehler), `+0x38` = u32 Flagwort (z. B. `0x000B1014`).
- **Zwei Zonenformate, das Format folgt dem Auswerter** (Regel 322):
  `idx 236` (`0x80053028`) ⇒ **Kugel 12 B** `{s16 x,y,z; s16 radius; s8 knoten; s8 ?; s8 flag;
  s8 schaden}` (belegt: `addic r27,r27,0xc` @`0x8005290C`); `idx 239` (`0x80052E74`/`0x80052C7C`)
  ⇒ **AABB 16 B** `{6xs16 Box lo/hi; s8 knoten @+0xC; s8 ?; s8 flag; s8 schaden}` (belegt an
  `0x800A5380`: Box `(-499,499,198,1239,519,995)`, Schaden `0x87`). Beide Listen: **12-B-Kopf**
  (Koerperzone, Knotenindex `-1` = Terminator) ⇒ Eingaenge rufen `liste + 0xC`.
- **Trefferkern `FUN_80052710`**: Knotenkette `FUN_8003AECC(node,delta)`, `FUN_8001D800` (Punkt),
  `FUN_8001D788` (Rotation), **Zylindertest** mit `Radius = Zonenradius + s16(schuss+0x86)`,
  Distanz via **Ganzzahl-`sqrt` `FUN_80020F7C`** (Regel 323), Trefferbitmaske `*(u32*)(akteur+0xBC)`;
  Ergebnis im Schuss-Record: `+0x00` Score, `+0x7A` Flag, `+0x7C` Schaden, `+0x98` Trefferknoten;
  `-1000` = kein Treffer, `-1` = nicht ausgewertet.
- **Bitplan-Trefferauswertung `FUN_80048CE8` (Regel 324)**: `[SDA(0x2D8)]` = Zeilen a 0x10 B
  (Rechteck `+0xB0..+0xB6`, Bitmap-Offset `+0xBC`), `[SDA(0x2DC)]` = **Bitplan** (4 Bit/Pixel) →
  16er-Code aus `+0x20`; schreibt `akteur+0x162/0x164/0x166`. = **Ring-/Punktwertung**.
- **Weitere Kernbausteine** (kein Pool-Record): `FUN_800517B8` = Akteur→Kollisionskoerper (Radius je
  Typ aus `[SDA(0x324)]`), `0x80053178` = Streukegel-Variante (Box x `param3/param4+1`,
  Aufrufer `0x80053CAC`), `0x80051EBC/EC8/ED4` = 3 Thunks in EINEN Rumpf (Trefferlisten-Reset;
  32 Saetze a 0x7C ab `[SDA(0x338)]-0x7C`, Test `lha 4(r6) == 2`).
- **ZB-Zwilling:** `0x8005132C` == `0x80050F30` **255 Woerter byte-identisch** (Segment-vs-AABB-Clipper,
  Liang-Barsky `t`/0x1000, Ausgangsflaeche 0..5). G7: `0x80053028` vs `0x800530D0` nur **3 Woerter**
  (`SDA(0x590)` vs `SDA(0x584)` = zwei **Filter-Hooks** im Missionsblock `0x80126BE0+0x4C/+0x58`).
- **Coverage (Regel 317 erneut): 250/2770 = 9,0 %**, live nur 2/19 (die zwei Szenen-Zustandsmaschinen
  `0x8005A5A4` 84/661 und `0x8005471C` 166/836) ⇒ **17/19 kalt inkl. des Trefferkerns**.
- **Zaehlungen nach Batch 56:** Ghidra **1911**; Pool **205/327 = 62,7 %** (offen 122); Matrix 124/124;
  Paket c 19/19; **kombiniert 416/628 = 66,2 %**. Offen: e (0x8002xxxx 61 + 0x8008xxxx 28 = 89),
  b-Rest (0x8007xxxx 8 + 0x8006xxxx 5 + 0x8004xxxx 4 = 17), f (0x8000xxxx 10 + 0x8001xxxx 6 = 16).
  ⇒ **Batch 57 = b-Rest = letzter Analyse-Batch vor Port-Start.**
- Doku `analysis/f5-descr-batch56-2026-09-17.md`, Status §24; Skripte `scripts/m56_*.py`,
  Artefakte `analysis/_m56_*`.

## Ghidra-Session je Start
`scripts/start-ghidra-headless.ps1` → dann IMMER
`POST /load_program_from_project {"path":"/830d01.27p.main.bin"}` +
`GET /switch_program?program=830d01.27p.main.bin` (Startprogramm ist be.bin, Base 0xFFE00000!).
`read_memory` liefert nur ~16 B → in Chunks à 0x400 lesen (`scripts/m42_hexdump.py`).

## GRUPPE A DER PHASEN-SCHICHT IST FERTIG (Batch 43.4, CONFIRMED, Stand 2026-09-17)
- **14 Tabellen / 168 Eintraege / 157 distinkt / 16 Thunk-Vorkommen (15 Adressen) / 149 Koerper**
  in `SDA(0x56C)=0x8008AA10` + `SDA(0x570)=0x80068B80`; Coverage **54/157** Eintraege (34,4 %)
  bzw. **46/149** Koerper (30,9 %); kombiniert mit dem 327er-Pool (133/327) = **187/484**.
  *Achtung:* die frueher genannte „51/157" ist nicht reproduzierbar (54/157 mit beiden Karten,
  47/157 nur mit `ppc_coverage.bin`).
- **Klassen -> Offset/Reader/Index/Schranke (>Laenge):** K4 +0x18 / 0x80071460 / Phase / 0xF > 16;
  K5 +0x58 / 0x80070DA4 / 0x10 > 17; K6 +0x9C / 0x80070680 / 0xB > 12; K7 +0xCC / 0x800702A8 / 0x7 > 8;
  K11 +0x110 / 0x8006F220 / 0x10 > 17; K12 +0x154 / 0x8006E830 / 0x9 > 10; K13 +0x17C / 0x8006E330 /
  0x7 > 8; K24 +0x1C4 / 0x8006BDEC / 0xC > 13; K25 +0x1F8 / 0x8006B8DC / 0x7 > 8; K26 +0x218 /
  0x8006B594 / 0x5 > 6; K27 +0x230 / 0x8006B1DC / 0x8 > 9; **K29/30 +0x254 / 0x8006A3F8 (SLOT 0!) /
  Index `s16(obj+4)>>8` = MODUS / 0xC > 13**; K29/30 +0x288 / 0x80069E10 (Slot 1) / Phase / 0x10 > 17;
  K32 +0x2D8 / 0x80068D14 / 0xD > 14. **Die 10 Dispatcher (ausser K32) sind KEINE Ghidra-Funktionen.**
- **Modus- vs. Phasentabelle:** `lha r,0x4(obj)` + `srawi >>8` ⇒ Modus-Tabelle; `lbz r,0x154(obj)`
  ⇒ Phasentabelle. **Slot 0 = Wegpunkt-/Registrierungsschicht** (K11 registriert in
  `SDA(0x578)+0x28+modus*4` und senkt `+0x48`; K12 `+4`; K27 liest `+0`).
- **Wegpunkte:** Block `obj+0x208`, **4…8 Records à 12 B** (klassenabhaengig: K24 8, K26 5, K25 4,
  K27 6), in Slot 0 als **lokale Offsets** geschrieben und per **`FUN_8004D94C(obj, Ziel, Quelle, n)`**
  in Weltkoordinaten gedreht (in-place wenn Ziel==Quelle; K25 nimmt das Muster vom Stack).
  **Ausnahme K27 = Weltkoordinaten, ohne D94C.** Rueckkehrphasen K29/30/K32: `obj+0x290/0x291/0x292`.
- **Inhalt:** K11 = jagt **Klasse 15** (`FUN_8004D7CC(-1,0x0F,-1)`), Modell 0x96/0x9A, gespiegelte
  Posebloecke 0x97/0x98; **Kl.11 Ph9 ≡ Kl.13 Ph6** (63 Insn, Knoten 0xD + Modell 0x9A + Positionsdelta
  via `FUN_8004992C`/`FUN_800498EC`); K12 = Einzelziel + 860-B-Routine **`FUN_8006EC64`** (Timeline
  0x244/0x2D5, Rotation + Kollision); K24 = 8 Wegpunkte + Distanzminimum-Auswahl (`0x8006BEFC`);
  K25 = 3 Modus-Varianten, **kein Spawn-Record**; K26 = **Zufallsmodell 0x6E/0x66/0x67/100**
  (`FUN_8006C81C`) + 3er-Zyklus 50 % (`obj+0x268`, vgl. K6 mit 25 %); K27 = Pose-6-Satz ueber
  **`FUN_8006B4E4`** = `FUN_8004D6A0(obj,rec,0x47,0x1611,6)`; K29/30 = 13 Pfadvarianten + Schusskette
  (`FUN_8006AB4C` → `FUN_8004D5D4`/`FUN_8004D558` = Klasse-5-Operatoren), **einzige live belegte Klasse**
  (Coverage 7/17 bzw. 1/12, `ppc_cov_boot.bin`); K32 = **Duell Modus 0 ↔ Modus 1**
  (`FUN_8004D7CC(-1,0x20,anderer_modus)`; Spawn-Daten: Typ 46 = Modus 0, Typ 60 = Modus 1).
- **Aktionssaetze** `(Zaehlwert, Tag, Pose)`: `(0x0E,0x8D3,4)`, `(0x0E,0x469,4)`, `(0x2F,0x1611,7)`,
  `(0x47,0x1611,6)`, `(0x47,0x1A7B,7)`, `(0x17,0xD3D,6)`. **Posen** liegen als `sth` auf `obj+0x1D2`.
- **Phasen-Tails sind Epiloge** (nicht als Koerper zaehlen): `0x8006F9EC`, `0x8006EBD8`, `0x8006E680`,
  `0x8006B3BC`, `0x8006B790`, `0x8006A3E4`, `0x8006A774`, `0x80069138` (+ „Phase++/Phase setzen"-
  Bloecke `0x8006A3F0`, `0x8006BA24`, `0x8006B640`).
- **Port:** 0/115 Handler 1:1; nur drei kleine 1:1-Helfer (`0x8006F6E4`/`0x8006E570`,
  `0x8006BEFC` = Naechster Wegpunkt, `0x8006A9F0` = Bahn-Interpolation) + Tabellen.
- Skripte `scripts/m43d_*.py`, Artefakte `analysis/_m43d_*.txt`/`_m43d_dis.json`,
  Doku `analysis/f5-descr-batch43-teil4-2026-09-17.md`, Status §14.

## GRUPPE B IST FERTIG: DIE ZIELFENSTER-/TREFFER-SCHICHT (Batch 47, CONFIRMED, Stand 2026-09-17)
- **Tabelle:** Strom `SDA(0x594) = 0x8008AD28`, Basis `SDA(0x598) = 0x800505D8`,
  Ziel = Basis + Wort, **12 Eintraege** (Wort `+0x30` = ASCII `"IBM "` = Stromende!),
  **Index = `param_3 & 0xF`**, **Schranke `< 0xC`**, Dispatch `mtspr CTR; bctr` in
  **`FUN_80051B8C`** (460 B). **Die 5 Koerper liegen INLINE im Dispatcher**
  (`0x80051BCC`, `0x80051BE8`, `0x80051C44`, `0x80051C9C`, `0x80051CF4`) ⇒ **keine Thunks**.
- **12 Eintraege → 5 Koerper:** {0,1,2,3,11} → Basiskoerper (nur ein Far-Call, der Box-Clip),
  4 → Rotationsvariante 1, 5 → Variante 2 (`FUN_80050D78`), 6 → Variante 3 (`FUN_80050C98`),
  {7,8,9,10} → Volltransform (`FUN_80050BC4`). 93 Instruktionen; Erfolg immer = 2. Aufruf ≠ 0.
- **Indexquelle:** `FUN_8005194C` (3 Schleifenebenen, live):
  `lbz r3,0xF(r19)` mit `r19 = *(r17+4) + s16(obj+0x26)*0x5C`;
  `r17 = *(SDA(0x330) + *(SDA(0x334))*8)` = Szenen-Deskriptor
  `{+0 Segmenttabelle 0x1C, +4 0x5C-Tabelle, +8 Objektarray 0x78, +0x10 Anzahl}`.
  Treffer schreibt in den **Trefferrekord** (`param_1`): `+0x00 = t (Q12)`, `+0x78 = s16`,
  `+0x82 = 1`, `+0x7C/+0x7E` = 2 Bytes aus `Segment+0x1A/+0x1B`, `+0x8C` = Restzahl;
  `+0x90` = Zeiger des gesperrten Satzes (Skip ⇒ kein Doppeltreffer).
- **KEIN Typtabellen-Bezug:** `SDA(0x300)+0x0F = 0` bei allen 79 Typen; im **ganzen Image**
  existiert **kein** `stb/sth/stw …,0xF(rX)`; auch keine statische 0x5C-Tabelle ⇒ der Index ist
  eine **Laufzeitstruktur** (HYPOTHESE: Zielfenster-Modus je Teil). Klaerung nur per Live-BP
  `0x80051AAC` (`r19` + `*(r17+4)` lesen).
- **Methodenmatrix:** `SDA(0x5AC…0x5C8)` = 8 Arrays à 4 Deskriptor-Zeiger (`0x800AA300…0x800AA370`,
  `[3] = NULL`) → Zielzellen `SDA(0x584…0x5A8)`; **`FUN_80051D58(Variante)`** installiert
  Variante 0/1/2. **Pro Frame zwei Scans** (`FUN_80051850`: `D58(1); 50374(); D58(0); 505D8()`),
  Variante 2 nur in `FUN_8004FDD0` (Aktor-Abfrage).
- **Die 9 Operatoren** (alle 327er-Pool-Ziele, schon Batch 42 Z. 102–109): Box-Clip
  `FUN_8005132C`/`FUN_80050F30`; Rotation `FUN_80050E5C`/`0x80050D78`/`0x80050C98`
  (Q14 sin/cos `>>0xe`); Volltransform `FUN_80050BC4` (`FUN_8001D788` je Endpunkt);
  Radius/Distanz `FUN_80052B08`/`FUN_8005293C`/`FUN_8005299C` (Reichweite `0x9C4`,
  Baender `1000000`/`0x5F5E11`). Ausgabestruktur `out`: `+0` = t, `+0xC/0xF` = 2 Punkte,
  `+2/+3/+5` (s16) = Deltas, `+0x15..0x17` = Trefferpunkt.
- **Coverage:** Eintraege **6/12**, Koerper **2/5** (Basiskoerper + Variante 2), Insn 31/93,
  Dispatcher 54/116. **Zaehlungen:** 327er **133/327**; A+B **60/169** bzw. **48/154**; kombiniert
  **193/496**. **Port:** 0/12 1:1, aber nur 9 Operatoren (~250–350 Z.) + 5 Vorlagen + 12-Byte-Tabelle.
- **Gruppeninventar (genau 8 Paare):** A `0x56C/0x570`; **B `0x594/0x598` (12)**; C `0x5D8/0x5DC`
  (7, **`+0xC`-Versatz**, Strom zeigt auf String `"wep_radio"`); D `0x5E0/0x5E4` (10, alle Ghidra-Fn);
  E `0x5EC/0x5F0` (33); namenlos `0x4FC/0x500` (6), `0x50C/0x510` (7), `0x6C4/0x6C8` (11). Die Zellen
  `0x604/0x614/0x658/0x684/0x6A8/0x6B0/0x700` sind **keine** Sprungtabellen (Namens-/Part-Listen).
- **Regeln:** (265) Gruppen = (Stromzelle, Basiszelle)-Paare; (266) Koerper koennen INLINE liegen;
  (267) C hat `+0xC`; (268) `FUN_80051D58` = Variantenschalter; (269) Far-Calls hier immer
  Deskriptor-Aufrufe (`0x800ACFC4…0x800AD090`, `{Ziel, r2=0x800ADA5C, 0}`); (270) Indexbytes ohne
  statischen Schreiber ⇒ Live-BP; (271) `FUN_80050A58` baut die aktiven Listen (`[SDA(0x31C)]`
  0x2E u16 = **0x5C B** je Objekt; `[SDA(0x32C)]` 0x42 u16 = 0x84 B).
- Werkzeuge `scripts/m47_*.py`, Artefakte `analysis/_m47_*`, Doku
  `analysis/f5-descr-batch47-2026-09-17.md`, Status §15. **Naechster Schritt: Gruppe C + D**
  (17 Eintraege, gleiche Mechanik), danach E (33).

## AKTOR-MATRIX (327er-Pool, idx 111..234): STAND NACH BATCH 54 (CONFIRMED)
- **Zaehlung (Regel 303 fortgeschrieben):** Pool **streng 165/327 = 50,5 %**, Konvention
  (Zeilen-Kredit) **170/327 = 52,0 %** - die Zahlen **konvergieren**, weil die Record-Ebene die
  Zeilen-Kreditierung ueberholt hat => **strenger Wert ist die Leitgroesse**.
  **Matrix allein 119/124 = 96,0 %**; offen nur K8.S1 `0x80070068`, K8.S2 `0x8006FE6C`,
  K31.S0 `0x80069A64`, K31.S1 `0x80069728`, K31.S3 `0x80069620` (+K21.S3 Kopf).
  **422 von 428 Spawn-Records** haben ihre Methoden gelesen. Ghidra-Stand **1853**.
- **S0-TEMPLATE (9 Koerper, je 116 B, CONFIRMED):** `FUN_8004FC54(obj, TEIL, -1, 0xC)` +
  `FUN_8004992C(obj)` + `obj+0x14C |= FLAG` + `obj+0x16D = 0; obj+0x152 = 1; obj+0x154 = 0;
  obj+0x16C = 0; obj+0x170 = 0; obj+0x174 = 0`. Nur TEIL/FLAG klassenabhaengig:
  K13.S0 `0x8006E6A0` (0x49/0x000A) == **K34.S0 `0x800768CC`** (relokiert, 2 Woerter roh diff);
  K21.S0 `0x8006D0D4` (0x02/0x1008); K18.S0 `0x8006D804` (0x82/0x1608);
  K14.S0 `0x8006E114` (0x9C/0x1208); K8.S0 `0x80070234` (0x7D/0x000A);
  K19.S0 `0x8006D5EC` (0x7D/0x0008 + `obj+0x208 = 0`); K10.S0 `0x8006FB5C` (0xD5/0x1208);
  K36.S0 `0x80075F38` (0xCE/0x1208, arg3 = 0/arg4 = 8). **Klassen teilen Modelle** (K8/K19 = 0x7D,
  K13/K34 = 0x49) => Klassenzuordnung nie aus dem Teil ableiten. Werkzeug `scripts/m54_tmpl.py`.
- **KOMMANDO-QUITTUNGSHANDLER, 7 BAUFORMEN (CONFIRMED):** Kern `if (s8(obj+0x16C) == 4) return;`
  + Kommando-Nibble `(obj+0x14>>12)&0xF` + `obj+0x152 = 1` + Phase = Rueckkehrphase +
  `obj+0x14 &= ~0xF000`. Varianten: K5.S3/K6.S3 (Vollform, Alarm `FUN_8004C438(obj,4,3)`,
  Rueckkehr `obj+0x27D`), **K4.S3 `0x80071354`** (+`obj+0x276 = (obj+0x150 & 3)-1`),
  K26.S3==K24.S3 (fest 2), **K19.S3 `0x8006D2F0`** (fest 4), **K27.S3 `0x8006B164`** (fest 2),
  **K17.S3 `0x8006D878`** (phasenabhaengig <2 -> 0, sonst 2), **K25.S3 `0x8006B878`**
  (fest 1 + Zielfilter `obj+0x26A = 10`), **K33.S3 `0x80076940`** (nur `mode == 0` + Bit 12).
- **Klassendetails:** K4.S0 `0x80071760` (712 B) = `FUN_8004C5FC(obj,0)`,
  `obj+0x1C0 = rand*(obj+0x1C0+1)>>15`, `x = ([SDA(0x14)]+0x4C>>29)&7` (Schwierigkeit, kuerzt
  Wartezeiten), `obj+0x1BC = 14`, `obj+0x1BE = 29 + (58*(8-x)>>3)`, obj+0x276/278/27A Wartezeiten,
  4 Wegpunkte `(0,0,0)(0,0,2500)(0,0,0)(0,0,500)` per `FUN_8004D94C(obj,obj+0x208,obj+0x208,4)`,
  **Startposition = Zufallspunkt wp0->wp1** (`t = 255*rand>>15`, Magic `0x80808081`),
  **Phase 0/1 als 50 %-Muenze** (`cntlzw((2*rand)>>15)>>5`).
  **K7.S0 `0x80070494`** (GunMen) = Zielfilter Typ -1/Klasse 6 (`obj+0x26C = 6`),
  Trefferwahrscheinlichkeit `obj+0x274 = (8-x)*4`, **Gruppe 2**.
  **K3.S0 `0x80071D80`** = Missionszaehler `mission+0x49/0x4A` + Knoten 0xE/0x14;
  K3.S1 = handkodierte Leiter (Modus 0 Gait `obj+0x180 = 0xE00`, `obj+0x174 = 0x7FFF`;
  Modus 1 Teile 0xE5 -> 0xE6).
  **K13.S3 `0x8006E188`** = Schleife ueber `mission+0x28+i*4`, `d < 250` => Phase 4, sonst
  `timeline == 0 && mode == 1` => Phase 2 (**Gegenrichtung zur Zielsuche der Klasse 12**).
  **K12.S3 `0x8006E714`** = `timeline == 0 && mode == 2` => Ph9; `obj+0x16C == 4` => Ph7;
  `obj+0x154 == 4` => **`beql FUN_8006EC64`** (also 1 `bl` + 1 bedingtes `beql`).
  **K17.S1 `0x8006D934`** (716 B) = 4-Phasen-Leiter (Posen 2/3, Tag `0x8D3`, Teile 0x2D/0x2E,
  Wartezeit `0x3A + 58*rand>>15`, Knoten 0x14 mit `[SDA(0x56C)]+0x19C`);
  **K28.S1 `0x8006AFB0`** = 4-Phasen-Leiter (Posen 3/0x81, Tag `0x469`);
  **K28.S3** = Quittung + `s16((*[SDA(0x578)])+8) <= 0` => Phase 3;
  **K32.S3 `0x80068B8C`** = Kindzustand `obj+0x29C` -> `obj+0x150 |= 0xE0`, Phasen 2/4/6/0xC;
  **K14** Teile 0x9C -> 0x9D -> 0x9E (0x7FFF); **K18** 50 % 0x82/0x83 -> 0x84 -> 0x8D;
  **K14.S3** = Positions-/Headingkopie vom Missionsobjekt (Knoten 0xD);
  **K0.S3 `0x8004A288` = `blr`** (Default-Methode `0x800AD060`); **K22.S0 == K20.S0**;
  **K10.S3** = `if (obj+0xC0 & 1) return` => Phase 1 (identisch K18.S3);
  **K15.S0** = Knoten 0x19/0x13 je `(0,-0x3C,0)`.
- **`obj+0xC0` Bit 0 = Gate "Ziel erfasst"** (K10.S3/K18.S3/K33.S3/K14.S3).
- **Coverage:** 12 von 32 Batch-54-Records live (170/2347 Woerter); K17.S1 44/179 und
  K18.S1 26/105 am staerksten => die Aufnahme enthaelt **mehr als Attract/UI + Klassen 3-7**
  (K7/K8/K14/K17/K18/K19/K25/K28 laufen).
- **Werkzeuge/Doku:** `scripts/m54_{open,twins,tmpl,cov}.py`, Artefakte `analysis/_m54_*`,
  Doku `analysis/f5-descr-batch54-2026-09-17.md`, Status §22.

## b-REST + SZENEN-SKRIPT-SCHICHT (Batch 57, CONFIRMED, 17/17) — Analysephase ist geschlossen
- **Zaehlungen:** Ghidra **1952**; **Pool streng 222/327 = 67,9 % (offen 105)**; Matrix 124/124;
  Paket c 19/19; **b-Rest 17/17**; **kombiniert 433/628 = 68,9 %**. Die **105 offenen Records sind
  exakt die zwei zurueckgestellten Pakete e (0x8002xxxx 61 + 0x8008xxxx 28) und f (0x8000xxxx 10 +
  0x8001xxxx 6)** — kein Record aus a/b/c/d ist offen.
- **b-Rest-Rollen:** idx **90 `0x8004A76C` = generischer Akteur-Konstruktor** (Kombination A, 48 Zeilen):
  setzt `+0xC0 |= 0x11`, `+0x14F = (char)[SDA(0x220)]+0x72`, `+0x154 = (s16(obj+4))>>8`,
  LCG `+0x1BC = 14..27` / `+0x1BE = 29..57`, `FUN_8004FC54(obj,1,-1,0xC)`, `FUN_8004B650` und
  **kopiert die 5 Methoden-Deskriptoren** `[[SDA(0x5E8)] + (char)typ*0x14 + i*4]` nach
  `obj+0x158/0x15C/0x160/0x164/0x168` (Slot A/B = +0x164/+0x168) ⇒ **Objektdispatch = Kopie, kein Zeiger**.
  idx **238 `0x80076EB4`** = Per-Frame-Treiber B (5-Phasen-Dispatch `s16(obj+0x152)`), idx
  **246 `0x8007BDF0`** = Treiber C, idx **245 `0x8007BE78`** = Konstruktor E (24 B),
  idx **242 `0x80048E0C`** = Konstruktor D (Typ-ID → `FUN_80048EDC(k,id,t,winkel)`),
  idx **110 `0x8004BFB4` = Methode `SDA(0x5D4)`** (nur **112 B**, nicht 1156 — Lump),
  idx **89 `0x80041F54` = Kommandofortschritt/Quittung** (6er-Sprungtabelle `[SDA(0x268)]+step*4+0x870`,
  Basis `[SDA(0x26C)]` → Tabelle `0x800881A0`/Basis `0x8003EAA0`), idx **257 `0x8006773C`** = 7-Zustands-
  Maschine (Zustand `*[SDA(0x528)]`, Tabelle `SDA(0x538)+0x274`, Basis `SDA(0x53C)`).
- **SZENEN-SKRIPT-FAMILIE (idx 94-100, Registry = 7er-Zeigerarray `0x800A03C8..0x800A03E0`):**
  idx 95 `0x80063648`, 96 `0x80064348` (8er-Sprungtabelle `SDA(0x4D8/0x4DC)`), 97 `0x80064F4C`,
  **98 `0x80065454` = der F-Dispatcher aus Batch 52** (`SDA(0x4FC)/0x500`) sind **Skript-Maschinen**;
  gemeinsames **Kontext-Layout**: `+0x00` u8 Phase (0 Setup/1 Dispatch/≥8 Ende), `+0x0C` u16 Flags,
  `+0x0E` s16 Countdown, `+0x3C` u32 Modusflags, `+0x40` u32 Flags, `+0x44`/`+0x5C` Zeiger;
  **globaler Timeline-Zaehler `[SDA(0x220)]+0x78`** wird pro Aufruf erhoeht.
  Bibliothek ~**71 Fn / 20 516 B** im Band `0x80063000..0x80068000` (nur 6 Pool-Records).
- **0x8007Exxx-Familie (idx 252/253/255/259/261) = einzige LIVE-Gruppe** (5/8 live; Zustand in
  RAM-Zellen `*[SDA(0x674/0x680/0x6A4)]`). idx **261 `0x8007E0A4`** = **HUD-/Overlay-Frame**
  (`0x8000D08C` Bank-Switch, `0x80018950`, `0x80017FE8`, `0x80017714`, `0x8004721C`, `0x800188A8`,
  `0x8003D608`) — neben dem Lump-Nachbar **`0x8004C024`** (Sprite-Recorder `0x80017674` +
  `0x8001A8F4`) die **einzigen 2 Render-Nahtstellen** des b-Rests (Rest renderfern, wie Paket c).
- **Seam (von E-P7 `FUN_80075028` / E-P8 `FUN_80074DE8` gerufen):** `0x80053408` = Praedikat
  `s8([SDA(0x220)]+0x87) >= 0`; `0x80053420` = **Objekt-Paarbildung + feste Pose** (`FUN_8003B0E8(a,b)`,
  dann `+0x2E = -363`, `+0x30 = 1445`, `+0x32 = -305`, `+0x3C = 0x8000` = 180°, `FUN_8004992C(b)`)
  ⇒ **keine Kamera**.
- **DER „NACHBAR-CLUSTER" `0x800534E4…0x8005469C` IST KEIN EIGENES PAKET:** 19 der 24 Funktionen
  werden **direkt von `0x8005471C` = C-99** gerufen, 5 von Cluster-Mitgliedern, nach aussen nur
  3 Aufrufe (2 Seam-Funktionen). 0 Render-Callees, Coverage 166/2057 = 8,1 %, live 1/27 ⇒
  **C-99-Helferwolke** (Helfer mit `strlen`/Text/Sound), **Batch 58 = nicht port-kritisch**.
- **Coverage b-Rest 82/2069 = 4,0 %, live 6/17; Zwillingssuche 0/17** (Reihe 11/38 → 0/6 → 5/19 → 0/17).
- **Werkzeuge (wiederverwendbar!):** `scripts/m57_tables.py` = **Deskriptor-Zeiger-Zensus** (alle
  Image-Woerter in `[POOL, POOL+327*12)`, gruppiert nach Laeufen → findet ALLE Besitzerstrukturen;
  640 Woerter/131 Laeufe); `m57_slots.py` (Fenster-Dumps); `m57_owners.py` (bl/bc + Rohwortsuche);
  `m57_typtab.py`; `m57_cluster.py`; `m57_cov.py`. **SDA-Zelle = Wort bei `0x800ADA5C + x`**
  (Zellblock `0x800AE020..0x800AE12C` = r2+0x5C4..0x6D0) und sie kann **Deskriptoradressen halten**
  (`SDA(0x25C)` = idx 89, `SDA(0x5D4)` = idx 110, `SDA(0x670..0x6C0)` = idx 252..261).
  Doku `analysis/f5-descr-batch57-2026-09-17.md`, Status §25.
