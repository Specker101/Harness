# R1B-Sprungtabellen-Gruppen (Strom-/Basiszellen-Paare) — Stand Batch 58 (2026-09-17)

## Zählbasis / Audit (WICHTIG für jede neue Session)
- Funktionszahl-Soll: **2021** (Stand B58); Snapshot `analysis/_m58_funcs_after.json`, Diff `scripts/m50_audit.py`.
  **Achtung:** `m50_audit.py <out>` schreibt relativ zum **Workspace-Root** ⇒ Zielpfad immer `analysis/...`.
  Nach `create_function` **und** nach `disassemble_bytes` **mit** Zuwachs: `GET /save_program`.
  Ausgaben nie per `Select-Object -First N` kappen (BrokenPipe ⇒ Datei fehlt).
- **Pool-Stand B58:** streng **268/327 = 82,0 %** (offen 59 = Paket e 43 + Paket f 16);
  kombiniert 479/628 = 76,3 %. Paket e = **Test-/Service-Modus**, siehe `test-service-modus.md`.
- **Render-Nähe nie aus der Paketbezeichnung ableiten** (Regel 338): Paket e hat 5 Render-Kern-Callees.
- Audit 1770→1779: +9 Funktionen (0 entfernt), entstanden über den **MCP-Tool-Pfad**
  (die „0 create_function"-Zeilen der Batch-Docs zählten nur den HTTP-Skriptpfad).
  Zusatz: eine l4-Anlage (`FUN_8004A28C`) war **nicht persistiert** ⇒ nach
  `create_function` immer `GET /save_program` und Zahl frisch lesen.
- Coverage-Map `SSCOV1` = 1 Byte je 32-Bit-Wort (`capture/ppc_coverage.bin`, `ppc_cov_boot.bin`).
- **Code/Daten-Grenze: 0x80085E68** (0 Funktionen ≥ 0x80090000) ⇒ Basiszellen ≥ 0x8009xxxx = Daten.

## Die 8 Gruppen (Ziel = Basis + Wort, Schranke = Länge−1, `mtspr CTR; bctr`)
| Gruppe | Zellen | Strom / Basis | n | Status |
|---|---|---|---|---|
| A | 0x56C/0x570 | 0x8008AA10 / 0x80068B80 | 14 Tab./168 | fertig (43.4) |
| B | 0x594/0x598 | 0x8008AD28 / 0x800505D8 | 12 | fertig (47) — Zielfenster/Treffer, 5 inline Körper |
| C | 0x5D8/0x5DC | 0x8008AD68**+0xC** / 0x8004BC68 | 7 | fertig (48) — Anhänge-Varianten `wep_radio` |
| D | 0x5E0/0x5E4 | 0x8008AD98 / 0x80049DA0 | 10 | fertig (48) — Schrittmaschine Treiberphase 3 |
| E | 0x5EC/0x5F0 | 0x8008ADD8 / 0x80072540 | **115 in 8 Tab.** | **fertig (49 Struktur + 50/51 Inhalt) — Modus-Schicht Kl. 35–38; Coverage 0/115** |
| F | 0x4FC/0x500 | 0x8008A048 / 0x800652D0 | 6 | **fertig (52)** — 6 Spielmodi-Anzeige; Disp. `FUN_80065454` (**Pool #98**, kein `bl`), Index = `s16([SDA(0x4F4)]+stufe*8+0x40)`, Schranke 5, 6 Inline-Körper, Coverage 0/6 |
| G | 0x50C/0x510 | 0x8008A070 / 0x80057880 | 7 | **fertig (52)** — Modus-/Zeilenwähler; Disp. `FUN_80058984`, Index = `s16([SDA(0x220)]+0x00)`, Schranke 6, 7 Inline-Körper → `s16([SDA(0x220)]+0x6E)`, Coverage 3/7 |
| H | 0x6C4/0x6C8 | 0x8008B5F0 / 0x8007ED90 | 11 | **fertig (52)** — 8 Sätze à 0x84 B (`[SDA(0x354)]+0x34`), Gate Bit0 von Satz+0, Index `s16(Satz+2)`, Schranke 0xA, 4 Handler (`FUN_8007F1AC` Blatt, `FUN_8007F138`, `FUN_8007F044`, `FUN_8007ED90`=Bodeneinschlag), Coverage 9/11 |
(0x4EC und 0x6B0 sind **Aliasse 8 B vor** einer echten Tabelle; 0x538/0x558/0x56C/0x604/0x658/0x684/0x6A8/0x700 zeigen auf **Strings** — Regel 297.)

## Gruppe E im Detail (Batch 49) — 8 Tabellen in EINEM Datensatz
Strom `0x8008ADD8`, Basis `0x80072540`; Tabellen lückenlos gepackt, Namensstrings
dazwischen (**nicht** 4-B-aligned). Die frühere „33" = 6+27 (Zählartefakt).
| Id | Versatz | n | Index | Schranke | Dispatcher |
|---|---|---|---|---|---|
| P1 | +0x000 | 6 | `s8(obj+0x156)` | 5 | `FUN_800743D4` (Modus 0x42) |
| P2 | +0x018 | 27 | `s8(obj+0x154)-0x1A` | 0x1A | `FUN_800727AC` (Modus 0x45) |
| P3 | +0x09C | 17 | `s8(obj+0x154)-4` | 0x10 | `FUN_800732C8` (Modus 0x43) |
| P4 | +0x0E0 | 9 | `s8(rec+0x0C)`, `rec=[SDA(0x5F8)][s8(obj+0x208)]+s8(obj+0x209)*0x10` | 8 | inline `@0x800735C4` (**LR**-Tail) |
| P5 | +0x104 | 6 | `s8(obj+0x154)` | 5 | `0x8007619C` (Matrix 35/2) |
| P6 | +0x11C | 7 | `s8(obj+0x154)` | 6 | `0x80075C00` |
| P7 | +0x148 | 29 | `s8(obj+0x154)` | 0x1C | `0x80075028` |
| P8 | +0x1EC | 14 | `s16([SDA(0x220)]+0x72)-0x47` | 0xD | `0x80074DE8` (Modi 0x47..0x54) |
- Globale Steuerfelder: `s16([SDA(0x220)]+0x72)` (Werteschar 0x42..0x57) und `u32(+0x78)`.
- 8 Namensstrings (Teil-/Skinnamen, Mechanik wie `wep_radio`): `leg_testLHD/RHD`,
  `black_testLHD`, `black2_testLHD/HIP/HED`, `S1_CAR10`, `S1_CARA0` →
  Container `SetB_boss4` / `SetB_last` / `SetB_st1st2` ⇒ stage-/boss-spezifisch.
- 115 Einträge → **103 distinkte Ziele**, `∩ Pool = 0`, `∩ {B,C,D} = ∅`, **kein Men-Körper**.
- **Coverage 0:** Modul `0x80072540..0x80076900` (17,3 KB) komplett kalt.

## Aktormethodenmatrix (Batch 49, CONFIRMED)
- `0x800AA380`, **40 Zeilen × 5 Spalten**; Zelle = Zeiger auf **12-B-Deskriptor** `{fn, r2=0x800ADA5C, 0}`.
- **Zeile = Klasse (`obj+5`), Spalte = Methode** (0 Registrierung/Wegpunkt, 1 Phasendispatcher,
  3 Modus-/Phasenläufer). Kontrolle: Zeile 5/6/7 Sp.1 = `FUN_80070DA4`/`FUN_80070680`/`FUN_800702A8`.
- Men-Kette = Zeilen 3–7; **E = Zeilen 35 (S1 Modus-Router `0x80076544`) und 38 (S3 `FUN_800749A0`)**.
- `SDA(0x5F8) = 0x800AA6A0` liegt direkt hinter der Matrix.

## Kernregeln der Gruppen
- Der Index kann (a) ein Datensatzbyte, (b) eine **Zufallszahl** (C: LCG `FUN_80015294`,
  `(r*7)>>15`, Gate `(r*0xFF)>>15 < param_3`) oder (c) eine **Schrittnummer** (D: `obj+0x16D`) sein.
- Körper können liegen: in Code-Gaps mit Thunks (A), **inline** (B), als **Fall-through-Kette** (D),
  als **Konstanten-Thunks auf 1 gemeinsamen Körper** (C: `li r31,K` + `b`).
- Basiszelle = **Modulanfang**; Tabellenwörter sind modul-relative Offsets (keine absoluten Zeiger).

## Typzeile `SDA(0x300)` = 0x8009E218, 79 × 0x5C (vierter Fund, Batch 48)
- `+0x00` Konstruktor · **`+0x04` Per-Frame-Treiber** · **`+0x08` Trefferzonen-Auswerter** ·
  `+0x3C` Zeiger auf die Trefferkette · `+0x18/1C/20` Skin · `+0x34` Modellname · `+0x58` Matrixbasis.
- Verteilungen identisch für die **48 Matrix-Typen** (79 = 48+18+8+3+1+1).
- Der 48er-Treiber ist `FUN_8004A28C` (Deskriptor-Slot `0x800AD60C`), verteilt per `obj+0x16C`
  auf Phase 0..4 = `8004B650 / 8004B5A4 / 8004B3E8 / 80049EB4 / 80049DA0`.

## Zählstand (Batch 53 — Gruppe A 100 %, Pool-Rest offen)

> **WARNUNG (Batch 130, R305):** die Zahl **`A–H = 211/325 Einträge, 178/284
> Körper`** ist **nicht reproduzierbar**. Sie steht als *Textkonstante* in
> `scripts/m54_cov.py` … `m57_cov.py` („A-H unveraendert") und wurde seit
> Batch 53 nur mitgeschleppt; ein Zählwerkzeug gibt es nicht mehr. Ebenso
> konventionsabhängig ist der 327er-Pool: `m53_pool.py` liefert **105/327**
> (streng, Artefaktlisten) und **143/327** (Zeilen-Credit), `m53_cov.py`
> **132/327**; die Notizen nennen daneben 176/327 (B53) und 268/327 (B58).
> **Nie als Messung zitieren, ohne die Zählbasis zu nennen.**
>
> **ENTSCHEIDUNG (Batch 131, R307):**
> (1) **A–H ist aus der Bilanz GENOMMEN.** Kein Zählwerkzeug, nicht
> reproduzierbar ⇒ es gibt keine kombinierte Zahl mit A–H mehr. Umgesetzt in
> `scripts/m54_cov.py` … `m57_cov.py` (die kombinierte Zeile addiert 211 nicht
> mehr, sondern sagt „NICHT eingerechnet (R305/R307)"), in
> `analysis/native-port-status-2026-09-17-final.md` und im Programm-Inventar.
> Die per-Gruppe-Aussagen (A = 157/157 Einträge usw.) bleiben *einzelne*
> Aussagen mit eigenem Beleg, aber ohne gemeinsamen Nenner.
> (2) **Der 327er-Pool ist NEU AUFGESETZT mit EINER Konvention: streng
> 105/327 = 32,1 %** (`scripts/m53_pool.py`, Basis = Adresse als
> Analysegegenstand mit benannter Artefaktliste; offen 222). Die Varianten
> 132/143/176/268 sind **keine** Messwerte, sondern Definitionen früherer
> Batches und werden nicht mehr zitiert.
- Funktionszahl-Soll jetzt **1832** (B53: 1825 → +7 `create_function`, Dumps diesmal +0;
  Snapshot `analysis/_m53_funcs_after.json`, Diff `scripts/m50_audit.py`).
- **Gruppe A = 100 % auf DREI Ebenen**: 157/157 Einträge, 149/149 Körper **+ 24/24 `bl`-Callees**
  (`P ∩ A-Callees = ∅`); die 2 Lücken `FUN_8006EC64` (860 B, K12 Zielsuche) und
  `FUN_8006C8D0` (432 B, K26 Box-Streuung) sind gelesen.
- A–H = **211/325** Einträge (64,9 %) bzw. **178/284** Körper (unverändert).
- **327er-Pool: ZWEI Zählungen führen** — Projektkonvention **176/327 = 53,8 %** vs. streng
  reproduzierbar **132/327 = 40,4 %** (Nenner 327, 150 Ghidra-Fn / 177 Gaps; Skripte
  `scripts/m53_pool.py` + `m53_cov.py`). Kombiniert: **387/628 (61,6 %)** bzw. **343/628 (54,6 %)**.
- **Offen: 64 Matrix-Records (101 von 428 Spawn-Records) + 158 Nicht-Matrix**
  (`0x8002xxxx` 61 UI · `0x8008xxxx` 28 UI · `0x8006xxxx` ~45 Aktor · `0x8005xxxx` 19 Treffer ·
  `0x8003xxxx` 16 Render-nah · `0x8000/1xxxx` 17 System).
- **Nächster Schritt (Empfehlung): Pakete a–d** = offene Matrix-Records (3–4 Batches, inkl. 11
  Gratis-Records aus Zwillingsgruppen) → `0x8006xxxx`-Aktor (3) → Trefferfamilie (1–2) →
  **`0x8003xxxx` Render-nahe Klasse (1, höchster Port-Wert)** ⇒ **4–6 Batches bis Port-Start**.
  UI-Pakete `0x8002xxxx`/`0x8008xxxx` (~89 Records) **dauerhaft liegen lassen**.
  Literal „100 %" = **13–16 weitere Batches** und ab Paket e/f Selbstzweck.

## B51-Befunde (CONFIRMED, Details in `analysis/f5-descr-batch51-2026-09-17.md`)
- **Die 15 E-Funktionen (Pool 217…231) bedienen VIER Matrixzeilen 35–38**:
  Z35 `[80076580, 80076544, P5, 80075FC8, 80075FAC]`, Z36 `[80075F38, P6, Ø, 80075B8C, Ø]`,
  Z37 `[80075AEC, P7, 80075024(blr), P8, Ø]`, Z38 `[80074D6C, 80074D68(blr), Ø, 800749A0, Ø]`.
- **Slot-Semantik:** S0/S1/S2 = Handler für `obj+0x152` (per Frame), **S3 (`obj+0x164`) =
  Per-Frame-Update (Gate Bit 3 von `obj+0x14C`)**, S4 = Slot B (Gate Bit 4; nur Kl. 35 aktiv).
- **Kette:** `0x80075FC8` (Kl.35 Per-Frame) → Modus → Zustand/Phase → **S1 `0x80076544` = Modus-Router**
  (0x42→`0x80073C6C`, 0x43→T3, 0x44→`0x8007310C`, 0x45→T2); **0x46 → Zustand 2 → S2 = P5**.
  Nachführer `0x800726DC`/`0x80072540`: Bodenkontakt (`FUN_8004FDD0` = Höhe über **Gruppe B**!)
  + **HP-Schwellen** (`obj+8 < 0x21` ⇒ Phase 0x32; `< 1` ⇒ Zustand 2).
- **P8 = Modusleiter der Klasse 37:** `Phase = max(Phase, K)` für Modus−0x47 ⇒
  0x47→1, 0x48→4, 0x4A→9, 0x4C→0xE, 0x4D→0x13, 0x4E→0x14, 0x4F→0x16, 0x54→0x19
  (0x49/0x4B/0x50–0x53 = Latch) ⇒ **belegte „Boss-Phasen-Progression"**.
- **`[SDA(0x5F8)]+0x2E4` = STATISCHE Teile-/Skin-Tabelle** (Stride `0x1C`, 39 Einträge + `−1`,
  `{s16 Teilindex ↔ s8(obj+0xC2), u32 Teil-Typ-ID, u8 Skin-Variante 0..3, char[0x13] Name, u32 Handle}`;
  `nude_/leg_/ladyD_/ladyD2_` × `HED HIP TNK LTH LFT RTH RFT LCF LAM LFA LHD RAM RFA RHD`
  ⇒ 16-teiliger humanoider Boss). Skript `scripts/m51_parts.py`.
- **`[SDA(0x5F4)] = 0x80126CD0`** = Missionszustand `[SDA(0x578)] = 0x80126BE0` **+0xF0**;
  `SDA(0x618)/0x61C` = dessen Unterblöcke **+0x28/+0x48** (erklärt das Fehlen direkter Schreiber);
  `SDA(0x5F4)` hat 19 Zugriffe, **alle lesend**.
- **Regel 287 ERSETZT:** `FUN_8004B650` setzt bei Phasenwechsel (`0x154 != 0x155`) `obj+0x156 = 0`
  ⇒ T1 (`FUN_800743D4`) ist **mehrfach** nutzbar.
- **Kein zweiter Lump:** `0x80073C6C…0x800743D4` = 7 echte Funktionen; `FUN_80073EB8` = 472 B;
  `0x8007421C` = geteilter Epilog von `FUN_80074090` (Posen 0xC8/0xC9/0xCA + `0x156`-Reset!).
- **Fähigkeitsfallen:** Dekompilate verschlucken Register-Argumente (`FUN_80073d98(x)`,
  `FUN_8004a984(x,7)`); `read_memory` kann kürzer antworten als angefordert.

## Regeln 280–284 (Batch 49)
- (280) Ein Strom kann **mehrere** Tabellen + eingebettete, nicht ausgerichtete Namensstrings
  enthalten ⇒ Inventar **nur** über Dispatcher-Prologe, nie durch Wörterzählen. `"IBM"` = Marker.
- (281) Dispatch ist **`mtspr CTR;bctr` ODER `mtspr LR;blr`**; Tabellenleser kann > ±0x40 von
  der Zellenladung entfernt liegen.
- (282) Methodenmatrix `0x800AA380` = 40×5, Zelle → 12-B-Deskriptor `{fn,r2,0}` (s. o.).
- (283) Modus `s16([SDA(0x220)]+0x72)` = Laufzeitzelle (RAM `0x800FEC98`), Werte 0x42..0x57.
- (284) Coverage-Index vor jeder Aussage gegenprüfen (`FUN_8004D194` = 72/72, `0x80071A68` = 26/26).

## B52-Befunde + Regeln 295–300 (Details in `analysis/f5-descr-batch52-2026-09-17.md`)
- (295) **Index kann aus einem statischen Datensatz kommen** (`[SDA(0x4F4)]+stufe*8+0x40`), inkl.
  Zweitfeldern (8-B-Record: `+00` Index, `+02` Ersatz-Countdown, `+04` Countdown→`obj+0x0E`,
  `+06` Sound, `+07` Flags: Bit0 ⇒ Globalflag 0x80).
- (296) **`s16([SDA(0x220)]+0x72)` hat zwei Wertebereiche:** klein (`0..~0x2F` Stufen/Demo-Flow;
  `FUN_80057E2C(obj,9,…)` setzt 9) **und** `0x42..0x57` (Endspiel) — Bereich nicht verallgemeinern.
- (297) **„(Strom,Basis)"-Paare sind nicht automatisch Tabellen:** Zellen zeigen auf Strings oder
  8 B vor eine echte Tabelle. Test: druckbarer Anteil + Code-Leser der Zelle + Dispatcher-Prolog.
- (298) **Tail-Aufrufe (`b`) verlieren im Dekompilat die Argumente** (Argumente am Disassembly prüfen).
- (299) `/disassemble_bytes` = **nicht lesend**: B52 +11 Funktionen (u. a. Basiszelle `0x800652D0`).
- (300) **Funktion darf mit Register-Shuffle-Kopf beginnen** (`0x8007ED0C` → `b 0x8007ED30`):
  nicht trennen; Blätter mit `blr`-Vorgänger + `bl`-Ziel dagegen immer anlegen (`0x8007F1AC`).
- F-Lump-Zerlegung: `FUN_800653D8` 2872 B → 6 Funktionen (124+980+112+344+648+664 = 2872, Regel 276).
- Statischer Block `[SDA(0x4F4)]` = `0x800A9860`: u16-Zeitschranken `{10,320,690,1024}` (Index
  `s16([SDA(0x220)]+0x74)`, in `FUN_800653A0`), 2× `5000000`; `SDA(0x51C) = 0x800A9B20` = Zeiger auf
  die 6 Modusnamen (`STORY MODE`, `SHOOTING RANGE [SCORE]/[TIME]`, `TIME ATTACK [EASY/MEDIUM/HARD]`).

## B53-Befunde + Regeln 301–307 (Details in `analysis/f5-descr-batch53-2026-09-17.md`)
- (301) **Kein Pool-Record wird je per `bl`/`bc` gerufen** (0/327 über das ganze Image) ⇒ der Pool
  ist ein **reiner Deskriptor-Fernaufruf-Pool**; Aufrufer-/Reuse-Fragen nur über Matrix `0x800AA380`,
  `SDA(0x4F4)`-Datensätze oder `[SDA(0x5F8)]`-Records.
- (302) **Alle 327 Pool-Ziele sind echte Funktionseinstiege** (310× `blr`-Vorgänger, 10× `b`,
  3× Prologmuster, 4× Null-Padding nach Exit) — **kein Inline-Körper**; 177 sind Ghidra-Gaps.
- (303) **„Gelesen" getrennt führen**: Projektkonvention (Zeilen-Credit) vs. streng (Adresse als
  Analysegegenstand); Skripte `m53_pool.py` (Zensus/Matrix/Coverage/Zwillinge) + `m53_cov.py`.
- (304) **`FUN_8003bd64` transformiert nichts** — nur `out+0` = Pitch, `out+2` = **−Yaw**.
- (305) **Pool-Records können auf die Basis relativer Sprungtabellen zeigen** (`0x80068B80/84/88`
  = `blr` = Offsets 0/4/8 von `SDA(0x570)`).
- (306) **Zwillingsvergleich nur normiert** (Sprungfelder maskieren: `b` `&0xFC000003`,
  `bc` `&0xFFFF0003`) — Skript `scripts/m53_dup.py` (`pair`/`find`/`twins`).
- (307) **Distanzschlüssel der Missionsregistrierung = `[SDA(0x578)] + 8 + mode*4`**
  (`FUN_8006EFC0` = Pool idx 147 schreibt, `FUN_8006EC64` liest das Minimum; Objekt `+0x28+mode*4`,
  **Mode = Slot-Index**).
- **Zwillingsgruppen im Pool (8 Gruppen/18 Records, 11 gratis)**: K9-S0 ≡ K28-S0 (48 B),
  **K26-S3 ≡ K24-S3 (92 B byte-identisch)**, K18-S3 ≡ K36-S3 (E-Modul, der **einzige**
  A–H↔Pool-Treffer), **K5-S3 ≡ K6-S3 bauformgleich** (gemeinsamer Kommando-Quittungshandler
  `obj+0x14c |= 2; FUN_8004C438(obj,4,3); obj+0x154 = obj+0x27D`), `0x8002CCAC/CD40/CDD4/CE68`,
  `0x8002F45C/F8CC/FA60`, `0x80050F30/5132C`, `0x80053028/530D0`, `0x80080B64/80C64`.
- **K1 komplett (37 Spawns)**: S0 `0x80072144` = Modus → 6 Teile-IDs
  (`0x72/0x85/0x86/0x88/0x90/0x91/0x92`; Modus 2 = 50 %-Münze `0x85`/`0x72`) → `obj+0x208/0x20A`,
  `obj+0x14c |= 0x2200`; S1 `0x80071FB0` = Phase 1 bindet `0x208`, Phase 2 bindet `0x20A`
  (ID `0x88` bei `s16([SDA(0x220)]+0) == 0` fest, sonst zufällig `0x88/0x89/0x8A`).
- **K9 komplett**: S0 `0x8006FE38` (`obj+0x14c |= 0xA`), S1 `0x8006FC5C`
  (**`FUN_8004FDD0(&obj+0x1C) → obj+0x20`** = Bodensetzung; Phasen 0/1/2 mit `obj+0x16c = 2/1/3`,
  Wartezeiten 58…115; Phase 3 bindet Teil `0x81`), S3 `0x8006FBD0` = Kommando-Quittung +
  `s16([SDA(0x220)]+0x72) == 0x12` ⇒ Phase 3.
- **K5-S0/K6-S0 = Angriffsketten-Init**: K5 `0x80071170` (2 Wegpunkte via
  `FUN_8004D94C(obj,obj+0x208,{0,0,0,0,0,-0x1F4},2)`, `obj+0x27D = 6`, `+0x27E = 5`,
  `obj+0x14c |= 0x8008`), K6 `0x800709C0` (3 Wegsätze `obj+0x214…0x234`, `obj+0x27D = 8`,
  `+0x27E = 7`, `obj+0x14c |= 8`).
- **Funktionsgrenzen**: `FUN_8006EC64` war 3496 B in Ghidra → **860 B** (215 Instruktionen);
  B53 legte `0x8006EFC0`, `0x8006B134`, `0x8006B514` (92 B), `0x8006BD90` (96 B),
  `0x8006D148/DCF8/DCFC` (je 4 B) an.
