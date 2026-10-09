# Bauliste & R216 (Stand: Batch 134, 2026-09-23)

## Batch 134 (aktuell)
- **Auftrag (Nutzer):** Vorpruefung (R207/R216/P100/R222) + messen vor dem
  Bauen + `8005A238` (36) / `8005A46C` (37) / `8005A360` (67) + danach
  `FUN_8005471c` (schliesst die R147-Luecke aus B131); Pflicht-Bilanz oben im
  Anker mitfuehren; Doku in allen vier Ablagen + Memory; „Eigene Fehler".
- **ERGEBNIS:** die **GEMEINSAME** Huelle der drei ist **GESCHLOSSEN** (VOLL 14
  Knoten = 3 Ziele + 11 GEBAUTE Unterbaukoepfe; BAU 8; offen 3;
  **Aussenkontakt 0, Haken 0, GAP 0**); Einzelhullen 7/1, 5/1, 8/1; R222
  beidseitig **144/148/268 B == 36/37/67 Insn**, lueckenfrei bis zum naechsten
  Inventarkopf -> KEIN `MEASURED_END`/`RANGES`.
- **GEBAUT:** +3 Koepfe -> **18 Koepfe / 382 Worte / 1528 B** in
  `port/voter_leaves2.{h,cpp}`; `_words.inc` FNV-1a **`A832F198`**;
  `_expect.inc` **52 Faelle**; **`pair_tone40`** (`8005A238`), **`term_scan`**
  (`8005A46C`), **`term_step`** (`8005A360`); Modus `vleaf` unveraendert (78).
- **R147 an FUENF neuen Stellen** (alle im GEBAUTEN M0-Waehler
  `mission0_step`): `0x8005ACAC`+`0x8005AE18` -> `pair_tone40`,
  `0x8005AEBC`+`0x8005AEDC` -> `term_scan`, `0x8005AECC` -> `term_step`;
  die 6. Rufstelle `0x8005A1C4` liegt in der offenen `FUN_8005A17C`.
- **B131-VERDIKT KORRIGIERT:** „R147-Verdrahtung UNMOEGLICH" fuer `hundreds3`
  war falsch - `0x80054B58` liegt in `FUN_8005471c`, aber der WIRT steht als
  **Dok-Kopf (R216-C)** im Port (`mission5_step`), genau der Beleg, mit dem
  B132/B133 in `mission0_step` verdrahtet haben. **`hundreds3` faehrt jetzt
  ECHT.**
- **`FUN_8005471c`: 1:1-Bau ist KEIN Ein-Batch-Auftrag.** Huelle VOLL **304
  Knoten / 38 offen / 2569 Insn**, BAU 99/22/**2101 Insn** (Blocker `8005C408`
  215, `8005C820` 269, `800688D4` 147, `800535B4` 125, `8005C168` 108).
  **Zusätzlich R222-Grenzfehler (R284-Klasse):** Inventarspanne **2428 B**,
  Rumpf **3344 B / 836 Insn** (916 B zu klein) -> Grenze `8005471C ->
  8005542C` in **BEIDEN** Tafeln (`m111_core.MEASURED_END` UND
  `m104_built.RANGES`).
- **R317 (fremder, GEBAUTER Code):** die R315-Klasse hat **vier** weitere
  Stellen - `0x8005AA00`, `0x80054B5C`, `0x80054B94`, `0x80054C04` (16-Bit-
  Verkurzung vor `stw` nullte die obere Haelfte von `slot+0x40`, still);
  behoben, zwei davon neu verankert.
- **Anker:** (230) 2/2, (231) **52/52**, (232) **19/19**, (233) **24/24**;
  neue Zeile `vleaf-b134-anker`; `vleaf-anker`/`vleaf-woerter-anker` nachgezogen
  (R194/R298); Regression **32 + 255, 0 Fehler**.
- **Zahlen:** R207 rueckw. **564** vor / **567** nach dem Bau (29/0/0); `check`
  567/0; `sanity` 0; `nachzuegler` 76/30 (**3/2**); R216 A 217 -> **220** (R306:
  `B134_HEADS` zuerst), B **83**, C **85**, D **643/129**; Waehler-Gruppe 82/15
  -> **85/12**; Huelle (A) **111/33**; Huelle (B) **282/50** (offen 1711 Insn +
  **416 B** size-nur); nur-Unterbau 38/1302 (B) / 21/837 (A); Inventar (R308,
  2026-09-23) S1 **1648** (79,5 %) / Rest **424**; Modi **78**.
- **Eigene Fehler (zehn):** R319 (Werkzeugfehler CR0 bei ungepunktetem `extsb`);
  Hakenzeile beim Verdrahten **mitkopiert** statt ersetzt; `beh_install` nullte
  `[SDA(0x240)]` nach der Zellenliste (alle 6 neuen Faelle gaben 0); Typ-12-Fall
  zweimal gefahren -> `phase`-Parameter; `kFnStageScan` angenommen statt geprueft;
  R222-Indizes 32/33 statt **48/49**; Sollwert `000400C0` statt **`0004000C`**
  (R320); R297 (PowerShell-`\"` in `python -c`); zwei Klammerfehler im Anker;
  (l3)-Sollwert „Zaehler 2" falsch, weil `stage_scan` denselben Zaehler nullt
  (R321).

## Batch 133 (Archiv)
- **Auftrag:** Vorpruefung (R207 rueckw., R216 A-D einzeln, P100 inkl.
  Ruf-Argumente, R222 beidseitig) + **erst die Huelle messen**, dann der
  kleinste verbleibende Kandidat MIT `insn`-Substanz (`8003B184`, 30 Insn);
  ausserdem die **Pflicht-Bilanz** aus B129 nachliefern/aufraeumen.
- **ERGEBNIS:** Huelle **GESCHLOSSEN** (VOLL 6 Knoten = Ziel + fuenf GEBAUTE
  Unterbaukoepfe; BAU 2; offen 1; **Aussenkontakt 0**); R222 beidseitig
  **120 B == 30 Insn**, lueckenfrei bis `8003B1FC` -> KEIN
  `MEASURED_END`/`RANGES`. **GEBAUT:** 15. Kopf in
  `port/voter_leaves2.{h,cpp}` = **`fach_expire(ram, arg)`** (Zwilling von
  `flags64`: gleiches 0x34C-Raster, `CR7.SO` = Bit 0; bei Bit 0 UND signiert
  `s16(+0x06) <= arg` wird `voter::obj_teardown` gerufen; Rueckgabe
  `[SDA(0x358)] + 0x34C*64`); `_words.inc` **242 Worte / 968 B**, FNV-1a
  **`82BC51B0`**, `_expect.inc` **40 Faelle**, Modus `vleaf` unveraendert.
- **R147 VERDRAHTET:** die EINZIGE Rufstelle `0x8005A920` ist die Hakenzeile
  des **M0-Typs 7** (`0x8005A8A4`, `bits & mask` UND `!(slot+0x40 & 1)`);
  `kFachArg = 5` (Rohwort `li r3,0x5` @0x8005A91C). Wirkung: Fach 0
  (Fahnenwort 1) ist danach **0**, `voter_block_stats().teardown == 1`.
- **Anker:** (230) 2/2, (231) **40/40**, (232) **13/13**, (233) **14/14**;
  neue Zeile `vleaf-b133-anker`; Regression **32 + 254, 0 Fehler**.
- Zahlen: R207 rueckw. **563** vor / **564** nach dem Bau (29/0/0); `check`
  564/0; `sanity` 0; `nachzuegler` **77/31 (3/2)**; R216 A 216 -> **217**
  (R306 beachtet: `B133_HEADS` zuerst); B **83**, C **85**, D **643/129**;
  Waehler-Gruppe 81/16 -> **82/15**; Huelle (A) 108/37 -> **108/36** (R316);
  Huelle (B) 278/54 -> **279/53** (offen 1711 Insn + **976 B** size-nur);
  nur-Unterbau 38/1302; Inventar (R308, 2026-09-23) S1 **1648** / Rest **424**;
  Modi **78**.
- **FEHLERFUNDE:** **R314** eigener Werkzeugfehler (16-Bit-Verschiebungen nicht
  vorzeichenverlaengert; LR-Rettung brach zusammen; 33 Altfaelle blieben
  byte-identisch); **R315** fremder Portfehler im GEBAUTEN M0-Typ-7-Zweig
  (`static_cast<u16>` vor `write32` nullte die obere Haelfte von `slot+0x40`);
  **R316** Huelle mit `stop = gebaut` ist nicht monoton.
- **PFLICHT-BILANZ:** die Tabelle aus B129 war im Anker **stehengeblieben**
  (nicht gestrichen); sie steht jetzt **oben direkt unter dem Kopf-Block** und
  ist im Batch-Doc §7 nachgeliefert (B129 | kumuliert 130-132 | heute).
- **Eigene Fehler (vier):** R314 selbst; das Zweitmodell pruefte `s32(s16)`
  statt 16-Bit-Verlaengerung (2000/2000 „Abweichungen" bei RICHTIGEM
  Interpreter); Sollwert-Tippfehler im (232)-Anker (`0xBFC1FFF0` statt
  `0xBF81FFF0`); die `_m130_*.txt`-Belege erneut ueberschrieben (B132-Staende
  vorher nach `_m132_*.txt` gerettet).

## Batch 131 (Archiv)
- **Auftrag:** Vorpruefung (R207 rueckw., R216 A-D einzeln, P100 inkl.
  Ruf-Argumente, R222 beidseitig) + **erst die Huelle messen**, dann der in B130
  offen gelassene Kandidat `80054574` (27 Insn); klaeren, ob `8005ABE0`
  (M0 Typ 8) zur Huelle gehoert; drei Altmessungen aufraeumen.
- **ERGEBNIS:** `80054574` Huelle **VOLL == BAU == 1 Knoten** (offen 1),
  **Aussenkontakt 0**, **0 gerufene Ziele** (BLATT), R222 beidseitig **108 B ==
  27 Insn**, lueckenfrei bis `800545E0` -> KEIN `MEASURED_END`/`RANGES`.
  **GEBAUT:** 13. Kopf in `port/voter_leaves2.{h,cpp}` (`hundreds3`),
  `voter_leaves2_words.inc` **13 Koepfe / 183 Worte / 732 B**, FNV-1a
  **`D20D7494`**, `_expect.inc` **+6 Faelle**, Modus `vleaf` (unveraendert).
  Rueckgabe `(([[SDA(0x234)]+0x6A4]/100) mod 10) mod 3` (Magic 0x51EB851F /
  0x66666667 / 0x55555556; `rlwinm rX,rX,1,31,31` = VORZEICHEN, nicht Bit 30).
- **R147-Verdrahtung UNMOEGLICH:** die einzige Rufstelle `80054B58` liegt in
  `FUN_8005471c` (**nicht gebaut**). Nur ueber ROM-Adresse (R216-A) belegt.
- **`8005ABE0` (M0 Typ 8): NICHT Teil der Huelle.** Es ist der `bl 0x80038014`
  (B130-Kopf `half_clear`); `T1[8] = 8005ABC8` ist eine **T1-MARKE** (kein Kopf,
  R309/Regel 288). Tor `cmpwi cr1,r3,0` + `bc 4,6` -> laeuft nur bei r3 == 0,
  und `event_fire` ist 0 genau dann, wenn Bit `(idx&31)` in `slot+0x3C` schon
  steht. **Jetzt WIRKLICH gefahren** (Ereignisbit belegt statt umgangen).
  Werkzeug `scripts/m130_ast.py gate` -> `analysis/_m131_gate.txt`.
- **Anker:** (230) 2/2, (231) **27/27**, (232) **7/7**, (233) **12/12**;
  neue Zeile `vleaf-b131-anker`; Regression **32 + 252, 0 Fehler**.
- Zahlen: R207 rueckw. **561** vor / **562** nach dem Bau (29/0/0); `check`
  562/0; `sanity` 0; `nachzuegler` 76/30 -> **77/31 (3/2)**; R216 A 214 ->
  **215** (+1), B **83**, C **85**, D **129** (R306 beachtet: `B131_HEADS`
  zuerst); Waehler-Gruppe 79/18 -> **80/17**; Huelle (A) 106/39 -> **107/38**;
  Huelle (B) 276/56 -> **277/55** (offen **1711 Insn + 1212 B** size-nur);
  nur-Unterbau 38/1302; Modi **78**.
- **Aufraeumarbeiten:** (a) Programm-Inventar im Dokument korrigiert (Kasten
  ueber §3.1: B60 1392/680 | B130 1642/430 | **B131 1648/424**, R308);
  (b) **A-H aus der Bilanz genommen** (`m54_cov.py`..`m57_cov.py` addieren 211
  nicht mehr, R307); (c) **327er-Pool streng `105/327`** als EINE Konvention
  (`m53_pool.py`).
- **Eigene Fehler (vier):** `srawi`-Feldlage im Interpreter vertauscht (still
  falsch, X=100 -> -1 statt 1); B130-Belege `_m130_hull.txt`/`_m130_span.txt`
  ueberschrieben; erster `magic_div`-Entwurf fehlerhaft (`i64` fehlt);
  `cmd_gate` nannte die T1-Marke erst "Rumpf".

## Batch 130 (Archiv)
- **Auftrag:** von den 29 offenen Waehler-Zielen das mit der kleinsten/am
  leichtesten abschliessbaren Huelle **erst messen, dann bauen**.
- **ERGEBNIS:** **11 Ziele** haben eine GESCHLOSSENE Huelle (genau EIN offener
  Knoten, Aussenkontakt 0, jedes gerufene Ziel GEBAUT), 3..22 GEMESSENE Insn.
  GEBAUT: **12 Koepfe / 156 Insn** (`port/voter_leaves2.{h,cpp}`,
  `voter_leaves2_words.inc` 156 Worte/624 B, **FNV-1a `B7DAD4DD`**,
  Modus **`vleaf`**), Werkzeuge `scripts/m130_ast.py`
  (`hulls|hull|span|sites|deps|dis|words|built|raw|cells|gen`) und
  `scripts/m130_ref.py` (R219, 21 Faelle, **2x2000 Zufallsproben 0 Abw.**).
- **Verdrahtet (R147, 12 Stellen)** in `mission_script.cpp`: `80054804`,
  `80054CEC`, `80054D70`, `80054EB4` (beide Wege), `80054FE4`,
  `80055010/18`, `800550B8`, `8005AC30`, `8005ACB4`, `8005AFB0`,
  `8005ABE0`. **Nicht gefahren:** `8005ABE0` (M0 Typ 8, `event_fire != 0`).
- **Anker:** (230) 2/2, (231) 21/21, (232) 5/5, (233) 11/11; **fuenf neue
  Ankerzeilen** in `port_regression.py`; Regression **32 + 251, 0 Fehler**.
- Zahlen: R207 rueckw. **549** (28/0/0) vor / **561** (29/0/0) nach dem Bau;
  ABI 202 -> **214** (+12); Modulkopf **83**, Dok-Kopf **85**; Waehler-Gruppe
  68/29 -> **79/18**; Huelle (A) 99/50 -> **106/39**; Huelle (B) 265/67 ->
  **276/56** (offen 1767 -> **1711 Insn** + 1320 B size-nur; Delta 156 =
  56 + 400/4 = genau die 12 Koepfe); nur-Unterbau 38/1302 unveraendert;
  Modi **78**.
- **R303** `state_inc` = BYTE-Schritt **plus** Rumpf `0x8003C6C4` (nullt
  `idx+1..7`, Rueckkehr bei `idx+1 >= 8`).
- **R304** M0 Typ 9/10/11 haengen am **T1**-Verteiler (`tab+0x10`), nicht am
  T2-Index-Verteiler (`tab+0x54`); der T2-Weg laeuft nur bei `Zeiger > 0`,
  sonst still in `default` -> **0 Hakenstellen OHNE Fehler**.
- **R305** Altmessungen (A-H 211/325, Pool 176/132, Inventar 1392) haben teils
  **keine reproduzierbare Zaehlbasis** (A-H: Textkonstante in
  `m54_cov.py`..`m57_cov.py`; Pool heute 105/132/143; Inventar neu **1642**).
- **R306** R216-Zaehler A/B/C/D zaehlen nur Adressen **ausserhalb** der
  Bau-Liste -> der Batch muss seine Koepfe **zuerst** in
  `m104_built.BATCH_LISTS` eintragen (sonst C 85 -> 96, B 83 -> 85, D 72 -> 64).

## Batch 128 (Archiv)
- **Auftrag:** Vorpruefung (R207 rueckw., R216 A-D, P100 inkl. Ruf-Argumente,
  R222 beidseitig) + **erst die echte Huelle messen**, dann der 2a-Kern
  (`800294E0`, `800297A0`, `80029958`, `80029D0C`, `8005865C`, `800545E0`).
- **ERGEBNIS:** der **2a-Kern ist VOLLSTAENDIG** — Closure `80029F50` liefert
  jetzt **1 Knoten / 0 offen**; die acht Nachbarn sind GEBAUT: 8002946C,
  800294E0, 8002967C, 800297A0, 80029958, 800299F4, 80029D0C, 8002A488
  (**405 GEMESSENE Insn**). Das **Batch-111-„unbaubar" ist WIDERLEGT**.
- **DER FUND (R293, CONFIRMED):** `0xFF000000 + X` ist die **ROM-SICHT** des
  Abbilds (ROM-Offset X = Datei-Offset X in `rom/build/830d01.27p.be.bin`).
  Die fuenf Zellen (`0xFF1F6000/6004/CA00/CA04/CA08`) tragen genau die
  erwarteten Verzeichnis-/Listen-Offsets — **Probe 6/6** (`_m128_romprobe.txt`).
- **Weg:** RAM-Spiegel `port/rom_alias.{h,cpp}` (`kRomAliasBase 0xFF000000`,
  `kAliasLo 0xFF1C0000`, `kAliasSize 0x60000`) statt zweitem Lesekanal (R148:
  `byte_cmp`/`list_find8/12` arbeiten so unveraendert mit).
- **Neu:** `port/voter_core2a.{h,cpp}` (Modul `core2a`, 8 Koepfe),
  `voter_core2a_words.inc` (`kCore2aSda[6]`, `kCore2aRomCells[5]`,
  `kCore2aWords[405]`), `voter_core2a_check.{h,cpp}`; Host-Anschluss
  `Core2Host::core2a` (R193 additiv; ohne Wirt gezaehlter Haken R215);
  Modus **`core2a`**. Verdrahtet: `cr1_w18_zero` -> `aux_ring_push`, drei
  Tafelziele -> `board_setup`/`aux_load`/`aux_distribute` (R147).
- **Anker:** (222) 416/416, (223) 21/21, (224) 8/8, (225) 9/9; Regression
  `core2a-anker`, `core2a-grenzen-anker`, `core2a-wire-anker`.
- Zahlen: offen **81 -> 73 Knoten / 2266 -> 1861 Insn** (−405); GEBAUT (B)
  251 -> **259**; Huelle (A) **96**/56 unveraendert; Waehler-Gruppe 65/32;
  R207 **543** (27/0/0), `check` 543/0, `sanity` 0; **ABI 188 -> 196**;
  Modulkopf **88 -> 83** (fuenf der acht), Dok-Header 87 unveraendert;
  Regression **32 + 241, 0 Fehler**; **76 Modi**.
- **GEMESSEN OFFEN (`B128_OPEN`):** `8005865C` (4-Insn-Rumpf / 36-B-Spanne,
  verdeckter Nachbar `8005866C`, Tail -> offen `80057880`) und `800545E0`
  (34 Insn, ruft offen `8006269C`/`80054668`) — **nicht** gebaut.
- Boot-Huelle `800089A0`: **abgeschlossen, leere Menge** — kein Bauauftrag.

## Batch 126
- **Auftrag:** den in B125 benannten **verdeckten Weg** `8001573C` messen, bauen
  und den Haken `kFnShowCall` ECHT verdrahten.
- **Erst GEMESSEN** (`scripts/m126_hidden.py hull/span/sites/deps/dis/boot`,
  Belege `analysis/_m126_*.txt`): die ECHTE Huelle ist **6 offene Knoten /
  300 GEMESSENE Insn** (2+138+68+59+23+10), **Aussenkontakt 1** (Trampolin
  `8000005C`, R235, gerufen von der GEBAUTEN Wurzel `800115BC`), **kein** Ziel
  der 97er-Liste. **R222: 6/6 Spannen == Rumpf**, kein verdeckter Nachbar in
  einer der sechs Spannen -> kein `RANGES`/`MEASURED_END`-Eintrag.
  **R284 erneut:** `insn`-Spalte fehlt fuer 3 Knoten = **208 der 300 Insn**
  (Spalte nennt 92) -> im Anker als Sollwert gefuehrt.
- **Gebaut + verdrahtet**: `port::show` (`slot_show.{h,cpp}`, Modus
  **`slotshow`**, `_words.inc` FNV-1a `F04B8867`); in `game_flow.cpp` fahren
  BEIDE Stellen (0x8008444C/0x80084580) `show::show_call` (R193 additiv,
  ohne Wirt bleibt der gezaehlte Haken). **Zwei** der acht uebrigen
  Rufstellen der Formatierer-Wurzel (`0x800107D8`, `0x8001159C`) laufen mit.
- **Anker**: (218) 329/329, (219) 7/7, (220) 8/8, (221) 5/5;
  Regressionseintraege `slotshow-anker`, `slotshow-grenzen-anker`,
  `slotshow-wire-anker`.
- **TRAGENDER BEFUND (R148-Klasse, CONFIRMED):** der „Anzeigeslot-Satz" IST
  der **Zielsatz `[SDA(0xB4)]`** (`game_flow.h` `kSdaAim`): der Kopf liest je
  Satz i `s16` bei `+0x0E/+0x10/+0x12` ab `[SDA]+4+0x0E*i` = `+0x12/+0x14/+0x16`
  des Satzes 0 — **feldgenau dieselben Zellen** wie das GEBAUTE
  `flow::aim_value`/`aim_sum` (Batch 92). -> `[SDA(0xB4)]` ist **kein offener
  Punkt mehr** (11 Batches ohne Beleg beendet).
- **Zusatzauftrag Boot `800089A0`:** 237 Knoten / 191 offen / 11219 GEMESSENE
  Insn, davon **92 % Hardware-/OS-Naht** (159/10362) und nur **8 % RAM**
  (32/857) -> **kein Durchbau**, erst die 857 Insn einzeln pruefen
  (`_m126_boot.txt`).
- Zahlen: Waehler-Gruppe **65/32**, 2a-Kern **1/8** unveraendert; ehrliche
  Gesamtzahl **81 offen / 2266 Insn / 1884 B (nur-size) / GEBAUT in (A) 96**;
  Huelle (B) **332**; R207 **535** (27/0/0), `check` 535/0, `sanity` 0;
  ABI **188**; Regression **32 + 238, 0 Fehler**; Modi **75**.
- **Ghidra gemessen 2090** (get_metadata + `list_functions` = 2090 Zeilen);
  die Dokumente fuehren 2085 = **Altkopie**. Der verdeckte Stub `0x80015734`
  ist auch nach meinem `dis`-Lauf **keine** Funktion (Gegenbeleg zur
  `disassemble_bytes`-Regel).
- Neue Regeln **R285** (zweistufige Zelle im Sandkasten; `W+0xB568` muss im
  Abbild liegen), **R286** (`"%c%d"`+Satzbuchstabe macht Zeichen, Akkumulator
  und Auswahlweg sichtbar), **R287** (Fuellschleife ersetzt durch Leerzeichen
  GLEICHER Laenge), **R288** (stub-Tail wird dem Kopf seiner Spanne
  zugeschlagen).
- **Naechster Schnitt**: die 857 RAM-Insn des Boots; die sechs uebrigen
  Wurzel-Rufstellen; die Vielrufer `80010704` (117)/`8000D1C4` (26)/
  `80011560` (9); Vektor-Kopf `0x80000500`; `800535B4`/`8005382C`, 0x8005Cxxx.

## Batch 122 (Archiv)
- **Auftrag:** den Strang `800115BC` angehen. **Erst GEMESSEN** (`scripts/m122_scan.py`):
  volle Huelle **58 Knoten / 43 offen / 1273 Insn** (Trampolin `8000005C` + drei
  Host-Modelle), und `parts` zeigt: **22 der 43** Einzelhuellen = derselbe Block
  -> **kein Ein-Batch-Schnitt**.
- **Gebaut + verdrahtet**: der **geschlossene Teilbaum** = die
  **TEXT-FORMIERER-FAMILIE** (`text_format.{h,cpp}`, Modus **`textfmt`**,
  `scripts/m122_text.py`): **12 Koepfe / 672 GEMESSENE Insn** (`800115BC` 288,
  `80011064` 63, `800112DC` 53, `80011214` 50, `80010F54` 35, `800114D4` 34,
  `80010FE0` 33, `80011160` 30, `800113B0` 25, `80011414` 23, `80011474` 23,
  `800111D8` 15); `deps` = **0 offene Ziele**.
- **VERDRAHTET (R147/R194)**: `bl 0x800115BC` @ **0x80010678** in `FUN_80010580`
  (68 Insn, GEBAUT) - die **einzige** der neun Rufstellen in gebautem Code;
  `TextLayer::format_text` faehrt `text::format`, der **STAND-IN (R235) ist
  ersetzt**. Die acht uebrigen Stellen liegen in offenen Koepfen (Nachzuegler).
- **Anker**: (202) 693/693 Worte, (203) 33/33 Verhalten (6 Faelle rufen die drei
  Ziffernwerfer ueber ihre **ROM-ADRESSE**), (204) 14/14 Grenzen, (205) 4/4
  Verdrahtung; **Regressionsanker**: `textfmt-anker`, `textfmt-ziffern-anker`,
  `textfmt-grenzen-anker`, `textfmt-wire-anker`.
- **Sollerwartungen** aus dem unabhaengigen Wortinterpreter `scripts/m122_ref.py`
  (R219): `0x2000` -> `0.50000`, `0x186A0` -> `6.10351`, `0xFFFFFFFF` -> `-0.00006`.
- Zahlen: Waehler-Gruppe **65/32**, 2a-Kern **28/8** (unveraendert - Unterbau);
  ehrliche Gesamtzahl **113 offen / 2868 Insn / 3220 B (nur-size) / GEBAUT 277**;
  Huelle (B) 390; R207 **507** (25/0/0), `check` 507/0, `sanity` 0; ABI **161**;
  Regression **32 + 220, 0 Fehler**; Modi **72**; Ghidra **2085**.
- **R265**: der Parserzeiger wird **vor** der Verzweigung erhoeht
  (`8001162C`) - sonst Endlosschleife bei Klartext ohne `%`. **R266**: die
  Ziffernfenster bekommen den **Basiszeiger als Argument** (`state+0x18`,
  Bruch bei `state+0x1E`). **R267**: Ghidras `rlwinm`-**Maske** kann falsch sein
  -> aus den BYTES rechnen. **R268**: der `l`-Modifikator ist **wirkungslos**
  (beide Zweige instruktionsgleich). **R269**: der Wirt muss `'\n'` durchlassen.
  **R270**: `%s` fuellt HINTEN und schneidet bei der Breite ab (LINKS-buendig).
- **CONFIRMED `[SDA(0x44)]`:** EINE Zelle, EINE Invariante - `FUN_80011A3C`
  schreibt `bank != 0` (Rufer `FUN_80026C34`, GEBAUT; `bank = (obj+0x4C>>10)&7`),
  `FUN_80011A48` (`mission::wide_char`) liest `== 0` = Zwei-Byte-Modus AN.
  **`[SDA(0xB4)]`: siebter Batch ohne Beleg.**
- **Naechster Schnitt**: die acht uebrigen Rufstellen der Wurzel; die neun
  `0x80057E2C`-Stellen (Auftragspunkt 5, nicht erreicht); die 31 uebrigen offenen
  Knoten des Strangs; dann `800535B4`/`8005382C` (rufen in die Textkette).

## Batch 121 (Archiv)
- **Gebaut + verdrahtet**: `port::voter::ramp_set` (FUN_80053178, 84 Insn) +
  `shot_prep` (FUN_80053CAC, 111 Insn, ZIEL der 97er-Liste) in
  `voter_hit.{h,cpp}`; Anker `voter_hit_check.{h,cpp}`, Modus **`hitramp`**,
  Werkzeug `scripts/m121_hit.py` (`words|check|deps|win`).
- **(198) 203/203 Worte, (199) 10/10 Verhalten, (200) 4/4 Grenzen,
  (201) 1/1 Verdrahtung**; Stelle **0x80054FDC** (M5, **T3**-Fall Typ 26 =
  Falladresse 0x80054FD4) faehrt `shot_prep` (Wirkung: prep_calls 1, Haken 0).
- **R215**: Satz im **genullten** Scratch `kRampRay` (0x803E0900),
  Ausgabezeiger `kRampOut`; Wirt ueber `flow::FlowHooks::hit_layer`
  (R193 additiv, Muster `core2`); ohne Wirt gezaehlt.
- **R216 dir.1**: beide per `reg.add` (`register_hit_ramp_host`), real
  einghaengt in `hit_check.cpp`; ABI **147 -> 149**; `m121_doc4.py verdikt`.
- **ADOPTION (R234)**: `80023A8C` (14 Insn, `gun_input.cpp` `GunInput::frame`)
  war 1:1 gebaut, in keiner Liste, **in** der Huelle -> `B121-adopt`.
- **CONFIRMED PORTFEHLER (121 gefunden+behoben)**: in FUN_80023A8C ruft
  `bc BO=4,BI=2,0x80022EA0` (LK=1) die Wandlerfolge bei
  `[SDA(0x018)]+6 != 0`; der Port rief bei **== 0** (invertiert). Spuren
  (`dump_analog`, `dump_gun_input`) + Prueffall (51) oeffnen das Tor jetzt
  ausdruecklich (`aux+6 = 1`); 2 Regression-Erwartungen mitgezogen (R194):
  Gate-Text, `Schieber A=0000 -> 0004`.
- Zahlen: Waehler-Gruppe **65/32**, 2a-Kern **28/8**; ehrliche Gesamtzahl
  **125 offen / 3540 Insn / 3220 B (nur-size) / GEBAUT 265**; Huelle (B) 390;
  R207 **495** (25/0/0), `check` 495/0; Regression **32 + 216, 0 Fehler**;
  ABI **149**; Ghidra **2085**.
- **GEMELDET, nicht verdrahtet**: `0x80057E2C` ist GEBAUT
  (`mission::stage_goto`), wird in `mission_script.cpp` aber an **neun**
  Stellen als gezaehlter Haken gefahren (R147-Luecke).
- **R261** Dokumentkopf der 4. Quelle nur in `.cpp` **ohne** `_check`.
  **R262** RAM-Strahlsatz braucht genullten Scratch. **R263** nach
  `m104_built.py`-Aenderungen **Listenlaenge + R207** pruefen (eigener
  Zeilenumbruch-Fehler, `B120_HEADS` 13 -> 12). **R264** bei Torpfaden die
  **Wirkung** messen, nicht "Feld unveraendert" (Vorstufe `step_e0` schreibt
  selbst).
- **Naechster Schnitt**: `800115BC` (102 Knoten / 1562 Insn); dann die neun
  `80057E2C`-Stellen; `800535B4`/`8005382C`, `800267B0` (243, R254), 0x8005Cxxx.

## Batch 120 (Archiv)
- **Gebaut + verdrahtet**: `port::voter::MsgKranz` (`voter_msg.{h,cpp}`) =
  **13 Koepfe / 355 gemessene Insn** des Abfrage-/Balkensatz-Kranzes der M0/M5-
  Waehler (`800432C0` Sichtsetzer 46, `80053F3C` 39, `8005A00C` 37, `8005A0A0`
  36, `80053EB0` 35, `80042A80` 32, `80042130` 31, `80053FD8` 24, `8000EC58` 10,
  `80042A70` 4, `800432B0` 4, `8005B848` 3, `80060CC8` 54).
- **Elf Hakenstellen**, fuenf in **fremden** gebauten Koepfen (`game_flow.cpp`
  0x8003CC4C, `mission_services.cpp` 0x8005B8EC = Balkensatz, `mission_script.cpp`
  0x80057E50/0x80057D58/0x80054F38/0x80055280/0x80055104/0x80054D50/0x8005AD04/
  0x8005AF18/0x8005AF70). Eigener Fund: 0x8005AF18/0x8005AF70 nehmen r3 = **Slot**.
- **R216**: alle 13 per `reg.add` im ERSTEN Durchlauf → ABI (**A**) 134 → **147**,
  0 ohne Bau-Liste; `0x800432C0` ist aus `HOOK_CORRECTIONS` **entfernt**.
- **Anker**: Modus `vmsg` — (194) 378/378 Worte, (195) 26/26, (196) 4/4,
  (197) 8/8 Verdrahtung; Generator/Pruefer `scripts/m120_msg.py`
  (`words|check|deps|win`).
- Zahlen: Waehler-Gruppe **64/33** (9052 B / 2263 Insn), 2a-Kern 28/8; ehrliche
  Gesamtzahl **128 offen / 3554 Insn / 4000 B / GEBAUT 262 / Unterbau 95**;
  Huelle (B) **390**; Huelle (A) **157** (offen 59); R207 **492** (25/0/0),
  `check` 492/0; Regression **32 + 214 Anker**; Modi **55/64**; Ghidra **2085**.
- **Naechster Schnitt (benannt)**: `80053CAC` (111) + `80053178` (84) +
  `80053EB0` (35, schon gebaut) — `80053178` reicht einen 4-Eintraege-Rampensatz
  in die HitLayer-Kette und braucht die byte-genaue Kopplung (R215). Danach
  `800115BC` (Huelle **102 Knoten / 1562 Insn** — Trampolin + vier Host-Modelle),
  `800535B4` (119) / `8005382C` (113), `800267B0` (Rumpf **243**, R254), 0x8005Cxxx.

## Batch 117-119 (Archiv)
- B117: `port::scr` (86 Insn, Modus `screens`), B118: Textmass/`8000FF8C`,
  B119: T4-Kranz des M5-Waehlers (**elf** Koepfe / 457 Insn, Modus `t4`);
  Waehler-Gruppe damals 53/44 → 60/37.

## Batch 117 (Archiv)
- **Vierte Belegquelle EINZELN abgearbeitet (R234/R236)**: Werkzeug
  `scripts/m117_pass.py` (`cand|body|p100|deps`); entscheidend ist `deps` =
  **Ziel-Vergleich ROM <-> Port**. **43 Aufnahmen** (FDC 9, Eintrags-/Datums-
  familie 18, Textkette 6, `gun_volume` 9, Einzelfund `8000EDCC`), **4
  Ablehnungen mit Beleg**: `8000D5E8` (nur HALBER Rumpf - die B116-Behauptung
  "1:1" war falsch), `8000D6B0` (halb, `800133AC` gezaehlt),
  `80010704`/`800107F0` (Stand-in `800115BC`), `80011B34` (Haken `8000F468`).
- **Gebaut**: `port::scr` = Ausgeber-Familie um `FUN_80053534` (32 / `800378D0`
  38 / `80037968` 15 / `800378CC` 1 = **86 Insn**); Anker Modus `screens`
  (187) 131/131 Worte, (188) 4/4, (189) 3/3; Generator `scripts/m117_words.py`.
  **VERDRAHTET** an der einzigen ROM-Rufstelle `bl 0x80053534` @ `0x800553AC`
  (M5-T4-Verteiler, Fall `0x8005537C`, Tafel-Typ 33).
- Zahlen: Waehler-Gruppe **53/44** (7164 B / 1791 Insn), 2a-Kern **28/8**;
  ehrliche Gesamtzahl **152 offen / 16508 B / 4127 Insn** (Unterbau **108**);
  R207 **462** (22/0/0); Regression **32+207, 0 Fehler**; Modi **55/67**;
  Ghidra **2085**.
- Offen: `8000D5E8`/`8000D6B0` (fehlende Pfade), Sprite-Ausgeber
  `8000FD7C`/`8000FE78`/`8000FF8C` (lesen Zellenbytes **+4..+7** statt der
  Quellbytes **+0..+3**), verdeckte Nachbarn `800379A4` (20 Insn, Typ 0x28) und
  `800379F4` (23 Insn, Typ 0x27; Rufer `0x8007A544`).

## Batch 116 (Archiv)
- Gebaut: `voter_select.{h,cpp}` (FUN_800155D0/15A10/15A34, 37 Insn) +
  `Bookkeeping::commit_block2` (FUN_80016124, R207-(b)-Schliessung).
- Anker: Modus `select` (184-186); Werkzeug `scripts/m116_pass.py`
  (`words|check|hand|cases|probe|doc4`).
- Verdrahtung (R147) **nicht moeglich** (alle Rufer ungebaut).

## Der Buchfuehrungsfehler (CONFIRMED, Batch 115)
`B104.built_all()` + `C103.built_set()` sind eine **handgepflegte** Liste. Ganze
Portmodule, die vor Batch 96 gebaut wurden (Batchn 64/81/85/88/91), stehen
**nicht** darin - die "ehrliche Gesamtzahl" (`m112_ast.py ast`) hat deshalb
**zu hoch** gezaehlt.

**77 Koepfe** sind 1:1 gebaut und standen in KEINER Liste, davon **20 in der
Huelle** (-20 Knoten / -838 Insn / -3352 B in Batch 115).
Beispiele: komplette `render_transport`-Kette (80016968/16E34/16FCC/171E0/
1A968/18C90/1B6FC), `HitLayer` (80052710 hit_core, 800517B8, 80052B08,
8005547C, 80050BC4, 8005132C, 80050F30, 80048CE8), PaketD D-262..D-275,
OpMode-Zustaende 0-3 (80025CDC/80025C4C/80025B7C/800259A8), `bookkeeping`
(80015A48/15B24/15C78/15D30/15CD8/15D60/15E24/15ED4/15F30/15FF0/16154/
161A8/161B4/161FC), `blockstore` (8000D140/D15C/D17C/D1A0/DEE8/DFCC/E090),
`rtc` (80013698/80013880), `display_bank` 8000C6B4, `gun_check` 80020BC0.

## Die drei Bauquellen fuer R216 Richtung 1 (Reihenfolge = Staerke)
1. **`reg.add` (ABI)** - `constexpr PpcAddr <name> = 0x<adresse>` + `reg.add(<name>, "FUN_<adresse> ...")`.
   Strengster Beleg: gebaut UND per ROM-Adresse aufrufbar. 119 Adressen im Port.
2. **Modulkopf "1:1"** - Zeile mit `1:1|Rohinstruktionen` und die Adresse im
   Umfeld von ~8 Zeilen (in `rtc.cpp` stehen sie in VERSCHIEDENEN Zeilen).
3. **Moduldokumentkopf** `// FUN_<adresse> - <Rolle>` - belegt, dass das Modul
   den Kopf implementiert, auch ohne das Wort "gebaut".
Werkzeug: `scripts/m115_pass.py abi|impl|doc|r216raw|r222|p100|sel`.
**Regel R229: eine Belegquelle darf NICHT durch den Filter einer anderen
laufen** - die Zeilen-Vorfilterung der Batches 113/114 hatte die ABI-Faelle
komplett verschluckt.
4. **Vierte Quelle** `// FUN_<adresse>` + 1:1-Umfeld (`scripts/m116_pass.py doc4`):
   Batch 117 hat sie **einzeln** abgearbeitet (184 -> **143** Adressen ausserhalb
   der Liste); Aufnahmekriterium **R236** (Hardware-/Zeitpfade und nicht
   zurueckkehrende Fallen duerfen gezaehlt/weggelassen werden, ein fehlender
   funktionaler Pfad oder Stand-in nicht).

## Nicht adoptieren
* **Host-Modelle** (R215): `80008448` (timebase), `8000CB40` (wdt_kick).
* **Stand-ins** (R235): `800115BC` (Text-Formatter "die Untermenge"),
  `8000F468`/`8000F928` (Zeichenzellen-Pool "NICHT portiert").
* **Halbe Ruempfe** (R148/R236): `8000D5E8`, `8000D6B0`, `8000FD7C` (Batch 117
  einzeln belegt).
* **Tail-Sprung ins Leere** (R148/R232): `800160A0` -> `80016124` (gebaut).

## Nach jeder Adoptionswelle
**Drei** POST-Laeufe (R242): R207 erneut (`m104_built.py tails`) **und**
`check`/`sanity` **und** die Quellenzahlen - die Zahl der geprueften Koepfe
waechst mit jeder Adoption (415 -> 457 -> 462).

