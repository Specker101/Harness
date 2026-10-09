# Silent Scope ROM-Asset-Ebene (Batch 33, CONFIRMED)

- **Ladeliste** ROM `0x1F6000` (Alias `0xFFFF6000`): Kopf `{0x0C, 0x400, 0, 0x28C}`;
  54 12-B-Records ab `0x1F600C` `{name_off, flag, ziel}`, Ende `name_off==0`.
  **Namensbasis = `0x1F600C`** (nicht 0x1F6000!). Flag 0 = residente RAM-Adresse
  (`0x80180000..0x80245FA4`, 29 Stueck, `baseman`/`last` aliasen auf `0x801DD14C`),
  Flag 1 = LZ-Container `0xFF000000+offset` (`0x184000..0x1B6000`, 25 Stueck).
- **Vier Container-Saetze** (104 gueltige, 1 510 944 B dekomprimiert):
  A = Ladeliste Flag1 (25), C = Tabelle `0x1C2000` (13, `st11..st10`),
  B = Verzeichnis `0x1F6400` (8-B-Records `{name_off, container_off}` rel. Basis,
  54 = alle Ladelisten-Namen), D = 11 Container ohne Tabelle (`0x1D009C..0x1F56EC`,
  u. a. globales Texturnamen-Lexikon `0x1D009C` mit 1661 Namen).
- **LZSS** (`FUN_8002B20C`): 0x1000-Fenster, Startindex 0xFEE, LSB-first-Steuerbits
  (8 Token/Byte, Nachladen wenn Bit 8 == 0), Literal 1 B, Match
  `offset=((b1&0xF0)<<4)|b0` / `len=(b1&0xF)+3`, max 0x100 Ausgabebytes je Aufruf,
  Pruefsumme = 32-B-Summe, KEINE Escape-/Endcodes (Ende nur ueber `desc[2]`).
  Kopf = Deskriptor `{Magic "LZ " = 0x4C5A2000, Pruefsumme, Groesse}`.
  **Zweites Format `FDC` (Magic 0x46444300)** = Methode 1 `FUN_8002B3D8` =
  **DEFLATE (RFC1951)**: Bit0=BFINAL/Bits1-2=BTYPE, LSB-first-Huffman
  (bit-gespiegelte kanonische Codes), stored/fixed/dynamic + RFC-Tabellen;
  Kopf `{magic, 32-B-Summe, Groesse}`, Daten ab +0xC; Statiktabellen in RAM
  `0x8009C1F0` (SDA 0x1AC). Offline `scripts/m34_fdc.py` -> 12/12 Groesse+Summe.
  **NUR `rom/build/830d01.27p.be.bin` lesen** (Rohdatei 16-Bit-word-swapped!).
- **Resident-Bundel**: Tabelle RAM `0x80099340` = 6 kleine FDC-Aliase
  (`FF08A000/AA00/B400/BE00/C800/D200`) + 4 Records `{dst, FDC-src, Allokation}`
  + 0-Terminator: `0x80180000<-0xFF178000`, `0x80198000<-0x100000`,
  `0x801F2100<-0x13A000`, `0x80260000<-0x0A2000`.
  ⇒ Flag-0-Assets liegen NICHT roh im ROM (0/29 Proben), nur als FDC/LZ.
- **Resident-Format**: `{u32 offset, u32 size}`-Tabelle + N Bloecke je `2*size`
  (lueckenlos, letzte Grenze = Slice-Ende) = Geometrie + 12-B-Texturrecords
  (`raw`/`cooked`-Paare). **Keine Pixel darin** (0 bildartige Fenster;
  0 Treffer fuer Live-TMU-Dumps mit 4-KB-Proben in allen Quellen).
- **Texturen**: `texBase` = TMU-Adresse (`(texBase & 0xFFFFF) << 3` + LOD-Kette
  +0x20000/+0x8000/+0x2000/+0x800), KEIN ROM-Offset; Format = textureMode
  Bits 8-11 (10 = RGB565, 16 bpp, keine Palette); tLOD 0x104 -> LOD4 -> 16x16
  Texel (512 B), LE, keine Swizzle. Pixelquelle = **CG-Textur-ROM**
  (`830a13/830a14` 32-Bit-interleaved = `rom/build/datarom_uad.bin`, 8 MB).
  Ein Paar verifiziert: texBase 0x042400 <-> CG-ROM 0x3C511C (16x16 RGB565).

## Textur-Upload (Batch 35, CONFIRMED)
- **SHARC-Opcode 0x42 (PM 0x207F6) / 0x43 (PM 0x207F8)** = Texturregister setzen
  + Block aus CG-ROM ins TMU laden. 14-Wort-Kommando im Shared-RAM-Strom:
  `{textureMode, tLOD, texBase, src, dst, stride, rows-1|cols<<8, Modus, next}`
  (u32-Werte high-Wort zuerst). Registerziele 0xC0/0xC1/0xC3 =
  textureMode/tLOD/texBaseAddr (voodoo_regs.h 0x300/0x304/0x30C /4).
- **KEINE Formel/Tabelle** texBase->ROM (3 Suchen in allen Quellen: 0 Treffer).
- `src` = Fenster-Offset: **Dateioffset = 4*src** (CONFIRMED Batch 36; `src` ist eine
  **Word**-Adresse im 2-M-Wort-Fenster `0x3600000`; NICHT `src` und NICHT `src+0x3600000`).
- `dst` = 0x2600000 + (tmu<<19)+(lod<<15)+(y<<7)+x; Zeilenschritt 128 Dwords;
  Texturbasis kommt aus dem Register texBaseAddr.
- **Modus 1 ("Unpack") = Pool-Kompression einer ganzen LOD-Ebene (Batch 37, CONFIRMED,
  `scripts/m37_unpack.py`)**: Kopfwort `H` (32 Bit) = Poolgroesse in **16-Bit-Texeln**,
  `m6 = H/2` = Poolgroesse in **32-Bit-Woertern** (Clamp: `H==0 -> 0x80`, `H>0x100 -> 0`);
  Pool ab `src+1`, Steuerwortstrom ab `src+1+m6`. Steuerwort = 4 Byte-Gruppen MSB-first,
  je Gruppe `flag = b&1` (0 = oberes Halbwort des Poolworts -> ror16, 1 = unteres),
  `Index = b>>1` (7 Bit); alle 2 Iterationen ein neues Steuerwort; Ausgabewort
  `(A<<16)|B`; Zeilenschritt 128 Woerter. **Selbsttest:** `maxIndex == m6-1`,
  `2*cols == W_lod`, `rows == H_lod`. 4/4 Boot-Bloecke + 29 Gameplay-Bloecke ok,
  **byte-identisch im Live-TMU auf der Vorhersageadresse** (87/87 Dumps).
- **texBase-Relokation (Batch 37, CONFIRMED): `FUN_80019458`** (Caller `FUN_8001B108`):
  `raw (mode Bit12==0) -> base += param_5 + 0x40000`; `cooked -> base += param_4`;
  dazu `*tlod &= 0xFFF7FFFF`. Die **`Q31 P`-Logzeilen** (`d@(r3),d@(r4),d@(r5),r6,r7`,
  BP auf 0x80019458, siehe `scripts/m31_emitter_probe.txt:10`) liefern die Werte VOR
  dem Patch -> 53 unabh. Treffer auf bekannte Upload-`texBase`.
- **`0x1FFFxxxx` (zako01/HGIRLS/citizen/amefoot) sind Seiten-INDIZES, keine Adressen:**
  `0x1FFFC000 + k*0x1000`, k=0..3. TMU-Adresse erst nach Relokation
  (`(texBase & 0x7FFFF) << 3`, 19 Bit baseshift 3). `zako01.bin`/`HGIRLS1.bin`/
  `citizen2.bin` haben **identische** Slot-Werte UND identische Record-Reihenfolge
  (`[12,12,13,13,14,14,15,15]`) -> Modell-Identifikation braucht einen Namens-BP.
- Modus (w12): 0 = Direktkopie (Woerter ab `src`, **kein Kopfwort**), 1 = Unpack,
  **>=2 = LZSS** (~78 % aller Bloecke). **LZSS REGISTERGENAU NACHGEBAUT + VERIFIZIERT
  (Batch 36, `scripts/m36_lzss.py`)**: Kopf = **32-Bit-Wort** an `src` = Ausgabelaenge
  in BYTES (== `4*rows*cols`); Daten ab `src+4`; Fenster 0x1000 (1 Byte je 32-Bit-Wort!)
  @0x143F000, Startindex 0xFEE, Steuerbyte LSB-first (Nachladen bei Bit 8 == 0),
  **Bit 1 = Literal, 0 = Match**, `off = b0 | ((b1&0xF0)<<4)` (12 Bit), `len = (b1&0x0F)+3`
  (M3 = 3, M0 = 0 aus dem Boot-Stub 0x20053/0x20056). Ausgabe: 4 Bytes -> 1 Wort
  `(a<<24)|(b<<16)|(c<<8)|d`; Zielbyte = `lodoffset[lod] + bpp*(tt*W_lod+ts) + 2*bpp*stride*x`,
  Zeilenschritt `bpp*W_lod` (das `0x80`-Dword-Inkrement des Handlers ergibt das,
  weil `cols*2*bpp*stride == bpp*W_lod` gilt -> Bloecke liegen **linear** im TMU).
  Beweis: 119/119 Bloecke selbstkonsistent (Ende wortgenau vor dem naechsten Block),
  **17 Bloecke byte-genau in den Live-TMU-Dumps** `capture/tmu0_ram_*.bin`, und der
  **rekonstruierte TMU** (`rom/build/tmu_boot_rebuilt.bin`) ist bei **12
  (texBase,LOD)-Paaren ebenenweise byte-identisch** mit den Dumps (inkl. einer
  kompletten 131072-B-LOD0-Ebene); Extraktion: 825 LOD-Ebenen + 850 PNGs.
- **CG-ROM-Dateioffset = `4*src`** (Fenster `map(0x3600000,0x37fffff).bankr` = 2 M
  **Word**-Adressen fuer 8 MB datarom). SHARC-DM-Wort = **little-endian** aus 4
  Dateibytes; der Bitreader (`ROT BY 8` = `std::rotl` = LINKSrotation, Delay-Slots
  0x2089B/0x2089C) liefert die Bytes **MSB-first** ⇒ der komprimierte Strom laeuft
  **innerhalb jeder 4-Byte-Gruppe rueckwaerts zur Datei**.
- **`DM(Mm,Ii)` = Prae-Modify OHNE Update** (Adresse = Ii+Mm, Ii unveraendert,
  MAME sharcdrc Klasse |010| u=BIT(44)==0); nur `DM(Ii,Mm)` ist Post-Modify.
- Ablage: TMU-Byteoffset = `(texBase & 0xFFFFF) << 3` + LOD-Kette
  (`lodoffset[n] = lodoffset[n-1] + ((wmask>>(n-1))+1)*((hmask>>(n-1))+1) << bppscale`,
  wmask/hmask = 0xFF ggf. `>>= lod_aspect`, bppscale = format>>3) + `(bpp*(tt*((wmask>>lod)+1)+ts)) & ~3`
  mit lod = BIT(dst,15,4), tt = BIT(dst,7,8), ts = (dst<<1)&0xFF. Werkzeug
  `scripts/m36_cgtmu.py build` -> `rom/build/tmu_boot_rebuilt.bin` + `rom/build/cgtex/*.bin`,
  `m36_texpng.py` -> PNGs in `analysis/cgtex_png/`.
- **Kommandos offline lesbar**: `-log` enthaelt jede SHARC-Shared-RAM-Lesung mit
  PC+Wert (`[:konppc] ':dspN' (PC) dsp_shared_ram_r_sharc: (board N) AAAA = VVVV`).
  Tool `scripts/m35_upload_inv3.py <log> <csv>`; Gruppierung ueber PC-Neustart
  (Feldindex 0), NICHT ueber Adresslaeufe (Adressen laufen ueber Kommandogrenzen
  weiter!). Nur `board 0` lesen. Ergebnis Boot/Attract-Szene: 152 Kommandos
  (`analysis/_m35_boot_uploads.csv`).
- **Modell-Container-`texBase` != Laufzeit-TMU-Adresse**: zako01/citizen/HGIRLS
  tragen 0x1FFFC000+k*0x1000 (vor-assignierte Slots); Schnittmenge mit echten
  Upload-texBase = leer (nur 0x0). Loader vergibt Slots szenenweise.
- **zako01 NICHT extrahierbar** (Test-Modell, Namen `*_test*`); die einzige
  5-Slot-Gruppe (texBase 0x5C000..0x60000, tLOD 0x104, Format 10) ist `car`
  (Polizeiauto, sichtbar in analysis/fdc_tex/set_5C000_teil*.png).
  **Batch 36:** in ALLEN Upload-CSVs (Boot 152/Survey 152/Mainmenu 28) 0 Treffer
  fuer `texBase = 0x1FFFxxxx`; Namensstaemme `skin_test*`/`k_test` nur in
  Namens-/Lexikontabellen, in keinem Kommandostrom. Nach dem LZSS-Nachbau fehlt
  fuer zako01 nur die Laufzeit-`texBase`-Zuordnung (1 Lauf `-log` ab Boot).
- `capture/tmu0_ram_<base>_lodN.bin` = **4-MB-Momentaufnahmen** des TMU;
  256x128-Schnitte sind kohaerent (Slot-Inhalte szenenabhaengig!).
  Tools `scripts/m35_tmu_cut.py`, `m35_tmu_scan.py`.
- `rom/build/datarom_uad.bin` = 830a14 (low 16) + 830a13 (high 16) je 32-Bit-Wort
  (verifiziert, `scripts/m35_cgrom_verify.py`).
- **Modell-Container** (51 der 54 Set-B-Container): Kopf `{n, u16, u16,
  part_table_off, 0, group_table_off, 0}`; Teiltabelle `{part_id, name_off}`;
  Namen; Gruppen-Offset-Tabelle; Gruppen `{u32 1, u16 pair_count, u16 0}` +
  `pair_count x 24 B` als `{raw 12 B, cooked 12 B}`; Record =
  `{u32 textureMode, u16 lod_hi, s16 tLOD, u32 texBase}` mit
  `cooked = raw | (1<<12)` und Laufzeit-Patch `(mode & 0xC0000FFF) | 0x14261000`.
  `texBase` = Voodoo-TMU-**Adresse** (`lodoffset = (texBase & 0xFFFFF) << 3`
  + LOD-Kette; dreifach belegt in `analysis/voodoo-texture-and-blend.md` A.4),
  NICHT RAM-Pool und NICHT ROM-Offset.

## Batch 44: Modell-/Skin-Pfad (CONFIRMED, offline)
- **Drei Namensverzeichnisse derselben Form** `{u32 name_off, u32 container_off}`
  (8-B-Records, selbst-relativ, Terminator `name_off == 0`):
  Satz C `0x1C2000` (13: `st11..st10`), **Satz D `0x1D0000`** (11: `objdata, trk0,
  st11, st21, st43, cst11, cst21, cst41, cst43, chtp, ctitle`; Σ 312 820 B),
  Satz B `0x1F6400` = **`0xFF1F6000 + *(u32*)0xFF1F6004`** (54 Ladelisten-Namen).
  ⇒ Batch-33-„Satz D wird von keiner Tabelle referenziert" ist **widerlegt**
  (Konsumenten: `FUN_8005D98C` (hart `0xFF1D0000`), `FUN_8005E480`, `FUN_8005E2E4`;
  Satz B: `FUN_80029D0C` (Stride 8) und `FUN_80029958`/`FUN_8002ADD8` (Ladeliste Stride 0xC)).
- **Vier Ladebereiche:** `0x80350000` = Satz-D-Registryobjekte (`*SDA(0x3DC)`),
  **`0x80390000` = Skin-/Modellarbeitsbereich** (`*SDA(0x18C)`/`*SDA(0x198)`, gesetzt in
  `FUN_8002A204`), `0x803C0000` = Satz-D-Overlay (`FUN_8005E2E4`), `0x803C1000` =
  Skin-Container (`FUN_800299F4`, Grenze `0x803A0000`) ⇒ offener Punkt `0x80390000` **zu**.
- **zako01 offline nachgerechnet** (`rom/build/setd/SetB_zako01.bin`, Groesse+Pruefsumme ok):
  Kopf `{n=0x23 (35 Teile), 0x1F0010, part_table_off=0x18, 0, group_table_off=0x30C, 0}`;
  Teiltabelle 8 B (`part_id`,`name_off`); Namensblock `zako01_test<TNK|LAM|LFA|LHD|RAM|RFA|
  RHD|HIP|LTH|LCF|LFT|RTH|RCF|RFT|HED>`; Gruppenkopf ab `+0x398` `{u32 1, u16 pair_count=5,
  u16 0}` + Paare à 24 B `{mode, tLOD, texBase}` raw+cooked (220× texBase `0x1FFFC000+k·0x1000`,
  139× `mode 0x0AC7`) ⇒ deckt `rom-asset-layer.md` (Kopf-/Gruppenformat) exakt.
- **Set D = `objdata`-Format** (kein Skin): Element-Offsetliste (0-terminiert, selbst-relativ)
  + Blockkette; `trk0` (Typ 21): `[0x0C, 0x1CB0, 0]`, je Block Teilblock `{n Teile, +0xC
  u16-Array, +0x10 s16[3]-Array}` — Element 0 endet exakt am Anfang von Element 1.
- Werkzeuge: `scripts/m44_setd.py` (Verzeichnisse+Entpacken+Blockkette), `m44_setb.py`
  (Skin-Records), `m44_dir.py`, `m44_typetable.py`; Zielordner `rom/build/setd/`.

## Textur-ReLOKATION + Modell-Attribution (Batch 38, CONFIRMED)
- **`param_4 == param_5`** (3582/3582 `Q31 P`-Zeilen) ⇒ **EIN** Parameter `P` je
  Ladevorgang: `raw -> texBase + P + 0x40000`, `cooked -> texBase + P`
  (Unterschied = Bit 18 = obere TMU-Haelfte). `P` kommt aus dem **Queue-1-Eintrag**
  `{u16 sel,u16 len,u32 p,u32 q,u32 r}` @`state+0xC020` (Stride 0x10, 0x180 Slots,
  Drain `FUN_80016cd8` -> `FUN_8001b108`) — **nicht** aus Ladeliste/FDC/Modell.
- **Namensquelle ohne Breakpoint:** 29 Ladelisten-`dest` (Flag 0) + 4 Buendelbasen
  (`0x80180000<-0x178000`, `0x80198000<-0x100000`, `0x801F2100<-0x13A000`,
  `0x80260000<-0x0A2000`) ⇒ `Bündeloffset -> Assetname`. zako01 @0x100000+0,
  HGIRLS1+citizen2+citizen3 @0x13A000.
- **Modell-Fingerabdruck = Seiten-MULTIMENGE** der Run-Records (distinkte Slots
  UND Record-Reihenfolge sind ueber die Familie identisch!):
  zako01 `{0:2,C:52,D:2,E:10,F:4}`, HGIRLS1 `{0:14,C:52,D:2,E:2,F:2}`,
  citizen2 `{0:6,C:52,D:2,E:4}`.
- **zako01 AUFGELOEST:** `P=0x20000` ⇒ Seiten `0x5C000..0x60000` (raw, tLOD 0x104,
  LOD4 = 16x16) — PNGs liegen vor. HGIRLS1 = `P=0x28480` ⇒ `0x64480..0x69480`.
  citizen2 in dieser Szene **nicht geladen**. **Keine Live-Aufnahme mehr noetig.**
- **Teil-Ebene:** der RAM-Block hat **einen** Texturrecord je Teil, **in
  Teiltabellen-Reihenfolge** (Paarzahl == `n`; geprueft zako01/citizen2/HGIRLS1)
  ⇒ `analysis/_m38_partmap.csv` = Teilname -> Laufzeit-texBase -> PNG.
  zako01: 26 Teile -> 0x5C000, 5 -> 0x5E000, 2 -> 0x5F000, 1 -> 0x5D000.
  (zako01 UND citizen2 sind Sammel-Container mit mehreren Figurnamen.)
- 12 Modelle zugeordnet (zako01, HGIRLS1, player, tero, terro0, boss3, game,
  effect, weapons, weapons2, Ficon, heri2; `car`/`heri1` ambivalent):
  **92 distinct Laufzeit-texBase, 49 upload-bestaetigt, 579/2019 PNGs (28,7 %)
  benannt**. Container-Basis (352): 10 benannt — Set-B-Container tragen die
  Records meist NICHT (die liegen in den residenten Buendeln).
- **Teiltabelle = 8 Byte** `{u32 part_id, u32 name_off}` (Batch 33-37 lasen 4 B);
  **Gruppentabelle indexgleich mit Teiltabelle**.
- **Regel:** die 6-Arg-Probe (`m31b_emitter_probe.txt`) ist um ein Feld verschoben
  (`d@(0x800ada60)` zuerst) — 5-Arg-Auswertung erzeugt Phantom-`P`-Paare.

## Run→Modell-Attribution, korrigiert (Batch 39, CONFIRMED)
- **Record-Layout = `{u32 mode, u32 (lod_hi<<16)|tLOD, u32 texBase}`** (Batch 33-38
  lasen nur die unteren 16 Bit des zweiten Worts). `lod_hi` ∈ {0x00,0x20,0x30,0x40}.
- **Vollstaendige Modusmenge:** `(mode & 0xFFF) ∈ {0x0C7,0x2C7,0x507,0x547,0x587,
  0x5C7,0xA07,0xA47,0xA87,0xAC7,0xC07,0xC47,0xC87,0xCC7}` **und**
  `mode >> 16 ∈ {0x0000,0x0402,0x0824}`. `m38_match.MODES` enthaelt
  **Rauschmodi** (`0x107/0x207/0x307/0x487/0x4C7/0x607`) und fehlende echte Modi.
- **Familienfilter `tb == 0x2000` verwerfen ist ein Bug** (erzeugte die
  `car`/`heri1`-Ambiguitaet). `car` = 12 Teile `{0x0:2, 0x2000:10}`,
  `heri1` = 2 Teile `{0x0:2}`; beide in Szene `m29_b31b/b31d` **nicht geladen**.
- **Matchregel:** `R == C` (normalisierter Schluessel `(mode&0xFFF, tid, tb&MASK)`)
  oder `R == 2 × C_raw`; Runs gegen **alle** Container (Set A/B/D) pruefen.
- **Set-A-Container = Datenkopie** (`assets/0x18…`, Ladeliste Flag 1:
  `dest == 0xFF000000 + ROM-Offset`); Set-B (`0x1F….bin`) = Teiltabelle/Namen.
  Zuordnung 39: `tittle`=0x184000/P=0x8000, `htp`=0x187B64/P=0, `start`=0x18BAB4/P=0,
  `story`=0x18BD0C/P=0, `sway`=0x18B370/P=0x33000, `sway1`=0x18BA30/P=0x38000,
  `st41`=0x1A4000/P=0, `stt`=0x1B6000/P=0 (+ `zako01, HGIRLS1, player, tero,
  terro0, boss3, game, effect, weapons, weapons2, Ficon` aus den RAM-Bloecken).
  ⇒ **19 Modelle**, PNG-Abdeckung **1760/2019 = 87,2 %** (same-scene 1366 = 67,7 %).
- **Prinzipiell offen:** `bluesky/redsky/st4sky/st43sky` sind **record-identisch**
  (unaufloesbar ohne Szene/BP); Stage-`P` (`st11…st51`) braucht die Stage-Szene.
- Werkzeuge: `scripts/m39_final.py` (Kern), `m39_names.py`, `m39_partmap.py`,
  `m39_pguess.py`, `m39_stats.py`; Bericht
  `analysis/cgrom-attrib-batch39-2026-09-17.md`.

## Validierungspass (Batch 40, CONFIRMED — Korrekturen!)
- `analysis/cgrom-attrib-batch40-2026-09-17.md` = Korrektur-/Validierungsbericht;
  Kopfzahlen (19 Modelle, 306/160/103, 1760/2019, 90/349) **bestaetigt**; 0 MAME/Rebuild/Ghidra.
- **Teilnamen-Bug (Batch 38/39) behoben:** Teilindex ist der **Paar**-Index ueber die
  Dateioffsets (raw/cooked-Reihenfolge wechselt je Quelle: RC **und** CR). Neue Spalten
  `part_index`/`part_name_conf`; Namen nur bei `0 <= Paare-n <= 1` ⇒ real nur
  Ficon/HGIRLS1/weapons2/zako01. `_m38_partmap.csv` = massgebliche Teil-Ebene.
- **`P=0x8000` der 7 Charakter-Modelle ist WIDERLEGT:** kein Run matcht
  citizen/citizen2/citizen3/HGIRLS2/HGIRLS3/amefoot/sway0 ⇒ in dieser Szene **nicht
  geladen**; Heuristik an **5/11** Modellen mit exaktem P falsch (tittle 0x0, sway
  0x28480, sway1 0x8000, zako01 0x8000, HGIRLS1 0x8000). `pguess.best_P` **nie** als
  Zuordnung benutzen — verbindlich nur `R == C` / `R == 2 x C_raw`.
- **Set-B-Gruppentabelle = Kandidatenseiten-Liste** (`pc` ∈ {0,2,3,5,6}, nie 1; Seiten
  `0x1FFFC000…0x1FFFF000`); die *gewaehlte* Seite steht nur im RAM-Block ⇒ Teil->Seite ist
  Loader-Allokation. Block enthaelt Nicht-Teil-Records (`tid …30030C`, `tb=0`,
  `tb=0x2600`) ⇒ `Paare == n` nie exakt.
- **`lod_hi` ∈ {0x00,0x20,0x30,0x40,0x50}**; **Set-A != Set-B im Inhalt** (Set-A =
  Record-Strom, Set-B = Teil-/Namen-Container, oft 0 Records); Runmap hat jetzt `run_index`.
- **Neue unabhaengige Messlatte:** `analysis/_m30_texreg_lines.txt` (2,76 Mio.
  `SSC_TEXREG`-Zeilen, UTF-16) = **gezeichnete** `texBaseAddr` der Szene: 189 distinct
  (voodoo0), nur **131 = 69 %** namentlich erklaert, **58 offen** (13 upload-bestaetigt).
  Tools `scripts/m40_validate.py`, `m40_texreg.py`, `m40_drawn.py`, `m40_logscan.py`.
- **Log-Inventar hart:** alle 177 Logs >= 1 MB gescannt — `Q31 P` nur in `m29_b31b`/
  `m29_b31d` (**eine** Szene), Upload-Reads in 12 Logs (**zwei** Szenen: Boot + State `d`);
  `error-gameplay-*`/`error-mainmenu-*` degeneriert (alle Reads `0x00020037`); nur **1
  ROM-Satz**, **2** Savestates (`d.sta`, `quick.sta`), `sharcdumps` = Programmfeld-Dumps.
  ⇒ ohne neue Aufnahme ist nichts mehr zu holen.
- **Kuenftiger Lauf:** `analysis/live-run-anleitung-2026-09-17.md` +
  `scripts/m40_run_probe.txt` (Probe + **Namens-BP** `0x80029958`/`0x8002af14`, `%s`
  funktioniert) + `scripts/m40_evalrun.py <log> <tag>` = Ein-Kommando-Auswertung.

## Konsolidierung (Batch 41, 0 Laeufe — Doku-Bereinigung)
- **Zwei Quoten nie vermischen (Regel 186):** `1760/2019 = 87,2 %` = **PNG**-Quote
  (extrahierte Bilder); `131/190 = 69 %` = **Szenen**-Quote (gezeichnete Texturen aus
  `_m30_texreg_lines.txt`). 175 benannte Adressen werden nie gezeichnet, 58 gezeichnete
  sind unbenannt ⇒ **69 % ist die ehrliche Zahl**.
- **`P=0x8000` der 7 Charakter-Modelle (citizen*/HGIRLS2/3/amefoot/sway0) steht nirgends
  mehr ohne Widerlegungshinweis** (Batch-39-Doc Titel/Kurzantwort/§4.1, Statusdokument,
  Live-Anleitung, Workstream-Block). Sie sind in der Szene **nicht geladen**.
- Statusdokument `analysis/native-port-status-2026-09-17-final.md` hat jetzt
  **§0 „Ist-Zustand“** (Erstleser) + **§5 Nachtrag Batch 41**.
- **Live-Anleitung geprueft = unveraendert gueltig** (neuer §1.1); nur die *Begruendung*
  fuer Gruppe (3) ist jetzt Szenen-/Namenslogik (STRONG INFERENCE).
- **Kern-Texturpfad architektonisch abgeschlossen** (LZSS/Unpack/FDC/Upload/Relokation/
  Attribution CONFIRMED); offen ist nur Asset-Vollstaendigkeit.

## Log-Inventar (Batch 37, vollstaendig)
- Nur **12 von 77** `.log`/`.txt` mit SHARC-Lesespur haben Upload-Handler-Reads
  (`(0207F9)` board 0): `error_boot_f0..f3` (152, doppelt gelesen), `poc_boot_survey`
  (152), `log_prog_b_a5_2ABD4`/`log_prog_v_a4_2B15D` (152 = Boot-Kopien),
  **`m29_b30d2` = `m29_b31d` (146, NEU)**, **`m29_b31b` (102, NEU, Teilmenge)**,
  **`m29_d1` (23, NEU, Teilmenge)**, `error-mainmenu` (86) und `error-gameplay` (365)
  = **degeneriert** (konstanter Wert `0x00020037`), `error.log`/`poc_survey`/alle
  `error_poc_*`/`error_inject_*`/`error_pc2942*`/`m29_b31e,f,q`/`l4_*`/`nc_*` = 0.
- Union echter Kommandos: **207** (Boot 152 + 55 neu), distinct `texBase` **173**
  (134 Boot + 39 neu), LOD-Ebenen 831+1165, PNGs 854+1165.
- `Q31 P`-Zeilen gibt es **nur** in `m29_b31d` (3582; 1428 mit `0x1FFFxxxx`) und
  `m29_b31b` (2730, 6-Arg-Probe = um ein Feld verschoben!).

## Werkzeuge
- `python scripts/m38_reloc_map.py cache|runs|match|map <log>` — Q31-P-Cache
  (5-/6-Arg-korrekt), Runs (konstantes `P`), Run↔Container-Treffer.
- `python scripts/m38_blockmulti.py <q31p_cache>` — **Seiten-Multimengen-Vergleich
  Run ↔ residenter RAM-Block** (= Modell-Attribution); `m38_bundle_attr.py` =
  Bündeloffset→Assetname; `m38_final.py` = Endauswertung + `_m38_*.csv`;
  `m38_stats.py` = Endstatistik (Basis 352/2019).
- `python scripts/m37_upload_census.py <log> <csv>` — **robuste Kommandorekonstruktion**
  (byteweise, mehrere Treffer/Zeile, Adresskontinuitaet + Wertvarianz `>2` — sonst
  entstehen Phantom-Kommandos aus DSP-Handshake-Reads).
- `python scripts/m37_scene_extract.py <csv>...` — Szenen-TMU (alle 3 Modi) + LOD/PNG.
- `python scripts/m37_dumpverify.py <csv>...` — **vollstaendiger Footprint-Vergleich**
  gegen ALLE `capture/tmu0_ram_*.bin` (531 Kommandos byte-genau in Batch 37).
- `python scripts/m37_unpack.py [csv]` — Modus-1-Modell + Live-TMU-Validierung.
- `python scripts/m37_q31p.py <log>` / `m37_zako_reloc.py <log>` — Record-/Relokations-
  auswertung; `m37_slots.py`/`m37_slotmatch.py` — Modell<->Slot; `m37_loginv.py`,
  `m37_f9scan.py`, `m37_f9board.py` — Log-Inventar; `m37_progress.py`, `m37_names_stats.py`.
- `python scripts/m36_lzss.py [csv]` — **SHARC-CG-ROM-LZSS registergenau**
  (`sharc_decompress`), prueft alle LZSS-Kommandos (Kopf, Laenge, Blockgrenze).
- `python scripts/m36_cgtmu.py build [csv]` — virtueller TMU (`rom/build/tmu_boot_rebuilt.bin`)
  + Blockexport (`rom/build/cgtex/*.bin`); `m36_texpng.py` -> PNGs (`analysis/cgtex_png/`).
- `python scripts/m36_tmu_full.py` / `m36_tmu_verify.py` / `m36_hdrprobe2.py` —
  Validierung gegen `capture/tmu0_ram_*_lod*.bin` (Live-TMU) bzw. Kopf-/Abbildungsbeweise.
- `python scripts/m35_upload_inv3.py <log> <csv> [budget_mb]` — **Upload-Kommandos
  aus einem `-log` rekonstruieren** (152 in `analysis/_m35_boot_uploads.csv`).
- `python scripts/m35_texbase_intersect.py` — Container-texBase vs. Upload-texBase.
- `python scripts/m35_tmu_cut.py <dump> <base> [w] [h] [png]` / `m35_tmu_scan.py`
  — Texturen aus 4-MB-TMU-Dumps schneiden/suchen.
- `python scripts/m35_cgrom_verify.py` — CG-ROM-Interleave beweisen.
- `python scripts/m35_zako_records.py <container>` — 12-B-Texturrecords im Klartext.
- `python scripts/m34_fdc.py dump|scan|verify|extract` — **FDC** (DEFLATE-Variante).
- `python scripts/m34_texextract.py render <cg-offset>|pairs` — Textur im
  zako01-Format (16x16 RGB565 LE) rendern; `m34_texwhere.py`/`m34_texlong.py`
  = Pixelquellen-Suche (negativ), `m34_report_data.py` = Belegdaten.
- `python scripts/m33_lzss.py verify|extract <dir>` — Container pruefen/auspacken.
- `python scripts/m33_assets.py list|csv|names|extract|records`
- `python scripts/m33_model_dump.py <file|--all>` — Modellstruktur drucken.
- `python scripts/m33_resident_probe.py` — Flag-0-Rohablage-Test.
- `python scripts/m33_summary.py` — Satzbilanz. `scripts/m33_romscan.py` — ROM-Scan.
- Ergebnis: `rom/build/assets/` (104 Dateien `0xOFFSET_Name.bin`),
  `analysis/_m33_*.csv|txt`, Bericht `analysis/romloader-lzss-batch33-2026-09-17.md`.
