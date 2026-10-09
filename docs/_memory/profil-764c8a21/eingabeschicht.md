# Eingabeschicht des Ports (Stand Batch 91, 2026-09-21)

## Batch 91 NACHTRAG (gleicher Tag, nach Sitzungsunterbrechung) - KORREKTUREN ZUM BLOCK UNTEN
- **Zwei Auftragspunkte waren OFFEN und sind jetzt zu:** (a) **Anker (100)** fuer
  `FUN_80028918` (7 Rohworte, 4 Zellen + Nachbarn) und `FUN_800284D8` (12 Rohworte,
  13 Verhaltensfaelle) - beide hatten NUR mitgezaehlt gelaufen; (b) **Verdrahtung** der
  Menueeintraege 6/7: `frame_io` -> `io_check_b`, `frame_gun_check` -> `gun_b`,
  (a) ueber `io_record_init`/`gun_init_a`; `kGapIo = ""` (Eintrag 6 inhaltlich
  vollstaendig 8 -> 9), `kGapGun` nennt nur noch die Szene `FUN_80028614`.
  Neuer Port-Code: `TextLayer::value_text` (Senke fuer fertige Zeichenketten),
  Bruecken `family_text`/`family_call`/`family_ready`, acht `ScreenStats`-Zaehler.
- **Drei Korrekturen (CONFIRMED):** `FUN_8001634C` setzt den Terminator als
  **LETZTES BYTE** (`TextLayer::clear_lines` war ein Byte zu spaet - betraf alle
  (a)-Inits, bei HOME traf `00 FF` den 64-B-Textpuffer); `FUN_80028918` = **28 B /
  7 Instruktionen** (nicht 280/70 - die Inventarzeile umfasst ZWEI Funktionen;
  Ghidra: `Body 80028918-80028933`); das I/O-CHECK-Ende haengt an `cfg+0x32` (nur
  **Bit 2** traegt es, R141) - "TEST+0x64" war die Port-Naeherung.
- **Regression 32 Frames + 122 Anker = 0 Fehler**; Modus `input` endet jetzt mit
  10 statt 11 von 20 Eintraegen (GUN CHECK faehrt die gebauten Zustaende).
  Ghidra **2085** (0 Schreibzugriffe); Kopf **0x80028934 fehlt Ghidra** (bewusst
  nicht angelegt). Neue Regeln **R146** (Terminator = Byte-Store am Pufferende),
  **R147** (Lueckentext/`content_complete` ist eine Aussage ueber den Bauzustand -
  bauen UND verdrahten im selben Batch), **R148** (gleicher `constexpr`-Name in zwei
  Kopfstuecken = Landmine -> adoptieren statt duplizieren).
- **Der Block unten ist der Stand VOR dem Nachtrag** (120 Anker, Luecken offen,
  280 B fuer `FUN_80028918`).

## Batch 91: GUN CHECK-FAMILIE + DER SCHREIBER VON io+0x18/io+0x3A (Kurzfassung)
- **Massstab:** 16 Funktionskoepfe, **5552 B / 1388 Instruktionen** (Auftrag
  schaetzte ~550 - Faktor 2,5; die Familie enthaelt ZWEI Bildschirme).
  Gebaut 1195; die **Szene `FUN_80028614`** (772 B) nur gezaehlt (Auftrag:
  "Logik, nicht die Bildschirmdarstellung").
- **Neu:** `port/gun_check.{h,cpp}` (`gun_b` = FUN_80028E98, `gun_sub` =
  800282C0, `gun_adjust` = 800284D8, `q16_ratio` = 80020BC0, `gun_view` =
  80028A30, `gun_record_filter` = 80028934, `io_check_setup` = 80028024,
  **`io_bar_simple`/`io_bar_state`** = 80027EE0/80027BD8, Texte, elf
  Ressourcen, `clear_block_ff` = 8001634C), `port/src/gun_family_check.cpp`
  (Anker **94-98** + Live-Sonde), Werkzeug `scripts/m91_gun.py`,
  erzeugte `gun_words.inc` (328 Stellen) / `gun_expect.inc`,
  Modi **`gun-check`**/**`gun-check-ui`**. Kontext `[SDA(0x170)]` = 0x800FA588.
- **DER SCHREIBER VON io+0x18/io+0x3A IST GEFUNDEN** (loest R140):
  die Zellen sind die **Ausgabefelder +8** der zwei **34-B-Panelhistoriesaetze**
  (`io+0x18 = io+0x10+8`, `io+0x3A = io+0x32+8`, Schritt **0x22** = Zellschritt
  der Anzeige). Geschrieben von der **dritten Stufe von `FUN_80023864`**
  (ROM-Wort **0x80023988** = `sth r0,-8(r5)`, `r5 = r3+16`): fuenf Wortpaare
  `(+8,+0x12) … (+0x10,+0x1A)`, Maske M aus **`aux+6`** (0 -> 0xFFFF, sonst
  0xC000): `A_k = (A_k & ~M) | (M & B_k)`, `B_k = B_k & ~M`. Geloescht von
  `FUN_80023998` (34 B nullen + acht 0xF2), gerufen von `FUN_8002382C`
  (GUN VOLUME). **NICHT** in der GUN CHECK-Familie.
- **Live-Dump als zweite Quelle:** Satz A `+0x10` = `F2x8 | 0000 FFFF 0000 0000
  0000` (= Bild eines Aufrufs mit Wert 0), Satz B Zaehler `07 07 F2 F2 F2 F2
  F2 F2` + `+8` = **0x0003** = dasselbe Panelwort B.
- **Korrekturen:** `panel_history` (B86) war **unvollstaendig** (dritte Stufe
  fehlte -> nachgetragen, [44] 8/8); der Umschalter hatte die **umgekehrte
  Polaritaet** ([90] 12/12); `io_check_display`/`io_check_b` riefen die vier
  Balken bzw. `FUN_80028024` nicht.
- **Regression 32 Frames + 120 Anker = 0 Fehler**; Ghidra 2085 unveraendert;
  0 MAME-Laeufe. **Rest:** 30 Konsumentenfunktionen, 6 gebaut / **24 offen**
  (13 584 B / 3396 Instruktionen) -> 6-8 Batches; eine ohne Inventareintrag
  (Lesestelle 0x800402E0).
- **Neue Regeln:** **R142** `rlwinm`-Masken wirken AN ORT UND STELLE (nicht
  rechtsbuendig; `slw/srw/sraw/srawi` erscheinen im Listing vertauscht),
  **R143** `bc 4,30` = "wenn CR7.EQ GESETZT" (= Bit 13), **R144** "kein
  Schreiber ueber `[SDA(0xB0)]`" beweist nichts (Satzzeiger!), zweite Quelle
  noetig, **R145** der Zaehler muss sagen, was gedruckt wird.
- **Naechster Schritt:** die Demo-/Skriptkette um `[SDA(0x240)]`
  (`FUN_8003DED0`/`FUN_8003EB44`/`FUN_8003F43C`/`FUN_8003F860`/`FUN_80084038`).

## Batch 90: DIE SPIELSEITE - EINGABESCHICHT IST FERTIG (Kurzfassung)
- **Neu:** `port/game_input.{h,cpp}` (`abort_gate`/`abort_gate_ram`, `q16_axis`,
  `read_check_rows`, `io_check_display`, `io_check_b`, `io_check_exit`,
  `consumer_map`, `abort_sites`), `port/game_check.{h,cpp}` (Anker 89-93),
  erzeugte `port/src/game_words.inc` + `game_expect.inc`, Werkzeuge
  `scripts/m90_game.py` (census/roles/q16/callers/dis/words/model/rest) und
  `m90_doku.py`; Modi **`game-input`**/**`game-input-ui`**.
- **Zensus (KORREKTUR 87 -> 66):** 51 Lesestellen von io+0x1C in 31
  Inventarfunktionen + 15 ausserhalb; **29** `andi. rS,rS,0x0084`
  (27 mit Bedienwort-Laden davor) im ganzen Bild; 5 Stellen io+0x18;
  8 Q16-Stellen. Regel **R138**: Zensus braucht die FUNKTIONSGRENZE und das
  Verwerfen abgeleiteter Basisregister (Batch 86/87 suchten nur bis `blr`).
- **Abbruchgate (27 Stellen):** `[SDA(0x240)]+0x14 == 0x1D`, `+0x10 < 0`,
  `io+0x1C & 0x0084`; 0x80 = START1 (MAME hornet IN0), 0x04 = Gun Trigger
  (sscope). Die 0x84-Maske steht auch auf io+0x18 (in FUN_800235F8, gebaut).
- **Q16-Kern:** `mulli 9102` (io+0x5C) / `7018` (io+0x70) + `srawi 16`
  = `floor(Wert*Faktor/65536)`; exhaustiv 131072/131072 geprueft. Die zwei
  anderen „Q16-Leser" (82BA0/833B8, Batch 89) rechnen mit SCHIEBUNGEN.
- **I/O CHECK:** `FUN_800279C8` zeigt 6 Zeilen aus der Tafel `[SDA(0x15C)]`
  (Zeilen 27/53, Spalten 13/15/17, Masken 0004/2000/8000/0080/4000/8000;
  Zelle = `io+0x18+0x22*k`, Zeilenbyte Feld +2 (+8), Spalte Feld +3 (+13),
  Index +4, Maske Halbwort +6); Zeilenzahl 6, im Zweig `cfg+4==0 && aux+0x19==0`
  -> 5. Bittests: io+0x18 Bit 7 -> io+0x54; (io+0x1C Bit 13 UND io+0x18 Bit 14)
  -> Vergleichszelle `[SDA(0x164)]` ^= 1 + io+0x56 = +-1.
  `FUN_800281C8` (b): Phase io+0x00 (0 -> FUN_80028024 + Phase 1), Rueckgabe 1
  = `(cfg+0x32 & 0x64) != 0 && ((cfg+0x32>>4)&0xF) == 0`.
- **Panelwoerter haben KEINEN direkten Leser** (kein Zugriff auf io+0x2C/0x4E
  ueber SDA 0xAC/0xB0/0xB4) - ihre Bits wirken ueber Historienzellen + io+0x1C.
- **GELOEST in Batch 91:** der Schreiber von io+0x18/io+0x3A ist die dritte
  Stufe der Panelhistorie `FUN_80023864` (s. Block oben) - die Zeilen hier
  waren der offene Stand VOR Batch 91. Weiter offen: Zeile 53 liegt
  ueber `kRows=0x30` (HYPOTHESIS: 64 Zeilen); der Spielablauf = 24 Funktionen
  / 13 584 B / 3396 Instruktionen ist vermessen, NICHT gebaut.
- **Regression 32 Frames + 114 Anker = 146, 0 Fehler**; 21 Modi Exit 0;
  Ghidra 2085 unveraendert (0 Aufrufe); 0 MAME-Laeufe.
- **Neue Regeln:** R138 (s.o.), **R139** Tafelfeld ueber die Befehlsfolge
  zuordnen, **R140** ein passender Live-Wert beweist keinen Schreiber,
  **R141** `andi.`+`crorc` = zusammengesetzte Bedingung (Zahl = CR-BIT-Nummer,
  BT=2 = CR0.EQ).
- **Naechster Schritt:** GUN CHECK-Familie (FUN_80028E98/80028A30/800282C0/
  80028918/80027BD8/80027EE0, ~550 Insn) + FUN_80028024 (420 B).

## Batch 88d-1: Der Grafik-/Ladeteil der Nutzlast (Kurzfassung)
- **Ausfuehrlich in `/memories/repo/ladeteil.md`** (Warteschlange 1:1, LZSS
  bit-exakt, Arbeitsobjekt/Zellpool **gebaut**, Bankzeichner + EC80,
  Sprite-Ausgabe, Anker (76)-(80), P124-P127).
- **Kern:** `FUN_8000D314` = `strcmp` gegen `[SDA(0x1B0)]` ("LZ "/"FDC\0");
  `FUN_8000D140` zaehlt **Woerter** (0x400 = 0x1000 B Fenster). Die Pumpe
  laeuft in Happen (Startgroesse 0x100, Ende an der Steuerbyte-Grenze,
  **signed**), der Standalone kuerzt **nicht** (laesst das letzte Match aus).
- **Das Arbeitsobjekt** (live `capture/m31_ram4mb.bin`): `0x800AEDC0 ->
  0x800D55D0`; Zellpool +0x8458 (Stride 0x104, Dirty-Wort `Zeile+0x104`),
  Bankliste +0xB51C (15 x 12), Sprite-Raster +0x1C, Bitmap +0xE5DC,
  Meshtabelle +0xE65C. **Bankanker 15/15 == Live-Dump** (Belegung 0x1B58).
- **Rahmengedometrie** der Eingabeschirme (in Batch 89 gezaehlt) ist zu:
  `(s16)*(obj+0xE65C+2v) | 0x80000`, `v = (s16)*(obj+0xB570)`.
- **Pool-Antwort:** dieser Teil ist der **Schreiber** (44 Zugriffe auf
  `[SDA(0x28)]`), der **Konsument** (Zellcode -> Pixel) liegt ausserhalb
  (Dirty-Woerter im Live-Dump groesstenteils 0). Ablage jetzt ECHT.
- **Regression 32 Frames + 101 Anker = 133, 0 Fehler**; 20 Modi Exit 0;
  Ghidra **2085 unveraendert** (6 Dekompilationen, 0 `create_function`).

## Batch 89: Die Texteingabe HOME PAGE ADDRESS / PASSWORD (Kurzfassung)
- **Neu:** `port/src/opmode_entry.cpp` (751 Zeilen), `opmode.h` Abschnitt **5c**, `text_layer`
  `centered(which=4)`, `service_screens` (**`kGapHome`/`kGapPassword` sind ZU**), Anker
  **(71)-(75)** in `opmode_check.*`, Werkzeuge `scripts/m89_input.py` + `m89_anchor.py`.
- **Antwort 1: das PASSWORD ist ein TAGESCODE** (KEIN Fortsetzungs-/Fortschritts-/Profilcode).
  8 Zeichen aus 32 (`GHJK01234DEF7LMN89ACPQRVWXST56UY`, 5 Bit; **nur 6 gepackt** - Pos. 3+6
  Fuellzeichen), XOR mit LCG-Strom (`0x41C65B1B`/`0x12C13`, Startwert `Ordinal ^ 0x19`),
  6-Nibble-Pruefsumme in den unteren 6 Bit, XOR `0x15DEBEEF`, Nutzlast = **Auswahl 0..3 +
  Tagesordnungszahl = TAGE SEIT 1970-01-01** (NICHT Tag im Jahr). Gueltig: heute **±2 Tage**
  oder die **Meisterdaten 1970-03-22** (Index 1) / **1997-07-22** (Index 2). Wirkung: Uhr/
  Buchhaltung + Muenzsatz zurueck (`FUN_80015ED4`/`FUN_80083FB4`), Index 2 zusaetzlich
  `coin[0] |= 0x80`. **Kein Level/Score/Profil.**
- **Antwort 2: HOME PAGE ADDRESS ist ein EDITIERBARES Textfeld** (keine Kontaktanzeige):
  `cfg+0x8A4`, 64 B (max. 48 Zeichen), Werkstext `http://www.konami.co.jp` (`0x80086128`),
  Ablage `FUN_8000D768` -> NVRAM-Block **0x80 UND +0x5D0**, Pruefsumme = **16-B-Wortsumme**
  der ersten 62 Zeichen (`FUN_800134D4`).
- **Mechanik:** `entry_cell` (`FUN_80082BA0`=`833B8`): `x = 31 - ((v<<5)&0x07FFFFFF)/32768`,
  `y = 23 - ((3v<<3)&0x0FFFFFFF)/32768`, Klemme `[0,63]`/`[0,47]`; Zelle -> Reihe/Spalte mit
  Sonderfall **Spalte >= 14 UND Reihe 6 -> Spalte 14** (`crnand`, op 19). Vorrat = **druckbarer
  ASCII in 7 Reihen x 15 Zeichen** (`x = 8+3i`, `y = 4r+14`; TAB leer; `SP`/`BS`/`" SET"`/
  `" END"` eine Zeile tiefer) - **die Vorvermessung "3-Spalten-Zifferneingabe" war FALSCH**.
  Cursorkasten 4 (bzw. 7) x 5, Zellwort 4/15; Cursorzeichen `0x7F`/`0x20` aus `[SDA(0x18)]+0xC`
  Bit 3. Ereignisse im niedrigen Nibble von `cfg+0x30`: Bit 1 Ruecktaste, Bit 2 Commit,
  **Bit 3 Abbruch**; Tor `andi. r8,r8,0x64`.
- **Zellen:** `[SDA(0x7A0)]` HOME (Phase `+0xC`, 64-B-Puffer `+0x1C`, Laenge `+0`, Reihe `+4`,
  Spalte `+8` = 1), `[SDA(0x7AC)]` PASSWORD (9-B-Puffer `+0x10`, Laenge `+4`, Phase `+0x1C`,
  Zaehler `+0x3A` = **58 Bilder**), `[SDA(0x7A8)]`/`[SDA(0x7B4)]` = **7 Zeiger in die
  Textbloecke** (`0x8008C7D0`/`0x8008C8C0`), `[SDA(0x7B8)]` = Monatstage + **Alphabet ab +0x18**,
  `[SDA(0x7BC)]` = LCG-Zustand, `[SDA(0x70)]+4` = Schlusszeile (`PRESS START BUTTON = EXIT`).
- **Anker:** (71) 182/182 Woerter, (72) 21 Zellfaelle, (73) 51 Codefamilie-Faelle,
  (74) HOME/PASSWORD-Verhalten + NVRAM-Rundlauf, (75) Spur; **Regression 32 Frames + 98 Anker
  = 130, 0 Fehler**; **20 Modi Exit 0**; Ghidra **2085 unveraendert** (0 Aufrufe).
- **Neue Regeln:** **P121a** das **SPR-Feld ist gespiegelt**
  (`SPR = ((x>>16)&0x1F)<<5 | ((x>>11)&0x1F)`). **P121b** ein **`nop`-Test muss ALLE Quellfelder
  pruefen** (`0x60000080` = `ori r0,r0,0x80`, sonst bleibt `coin[0] |= 0x80` unsichtbar).
  **P122** ein Datum wird als **Ordnungszahl** verglichen. **P123** die **(a)-Init eines
  Phasenschirms muss BYTE-genau** sein (Zeilen statt Bytes treffen die Phasenzelle).
- **Eigene Fehler:** `date_ordinal` als "Tag im Jahr" (3/4 Codes ungueltig); eine
  Klemmungserwartung verdreht (`io+0x70 = -32768` -> `y = 47`); `char_index` mit SDA-Offset als
  Adresse; Namenskollision `kPwCountdown` -> `kPwWait`; zwei veraltete Regression-Erwartungen
  (6 -> 8, 13 -> 11); zwei Dekodierluecken des eigenen Werkzeugs (P121a/b); halbfertiger Anker
  (`s.set_rtc`).
- **Eigenheiten, 1:1:** `FUN_80013880` liefert **29 Tage fuer JEDEN Monat**, wenn
  `(Jahr & 3) != 0` (gedrehte Schaltjahrrichtung); zwei unerreichbare Zweige
  (`li r31,3` @0x800831C0, Kopf-Ruecksprung @0x8008319C); Index 1 UND 2 zeigen dieselbe
  Meldung `SUCCESSFUL` (`0x8008C96C`).

## Batch 88c: Die Tagesbuchhaltung des Muenzsatzes (Kurzfassung)
- **Neu:** `OpMode::daily_bookkeeping` (`FUN_80083968`, 213 Woerter), `daily_hist_select`
  (`FUN_80083CBC`, 36 Woerter), `daily_hist_bin` = **`((v+1) mod 24) >> 1`** (`mulhwu 0xAAAAAAAB`),
  `daily_window_mod` = **`x mod 24`** (`mulhw 0x2AAAAAAB` + `srawi 2` + Vorzeichenkorrektur),
  `coin_days_buffer` (`FUN_80083D4C` mit 7-B-Puffer: **Byte +2 = STUNDE**), `DailyPath`/`DailyEvent`.
  `coin_read()` ruft die Tagesbuchhaltung **wirklich** (vorher nur gezaehlt).
- **Ablauf:** zwei **Tore** (Tageszahl 0 / Tag == `coin+0x14` -> Rueckkehr OHNE Aenderung);
  **Pfad A** (Flags Bit 0: Stunde hinter dem Fenster -> Zaehler **+1 als Byte**, ab **14**
  `Flags |= 0x40`; sonst -1, bei 0 `Flags &= ~1`; Tag wird IMMER gespeichert);
  **Pfad B** (Flags Bit 1 UND **unsigned** Abstand >= 7 -> `Flags |= 1`, Zaehler := 7;
  Tag KLEINER als gespeichert greift trotzdem); **Pfad C** (18-B-Historie in 17 Schritten
  schieben, `coin[1]` = Stunde, zwei Zaehlungen, Fenster `(2i+21)/(2i+3) mod 24` =
  **immer 6 Stunden**, `Flags |= 2` bzw. `&= ~2`); Ende immer `FUN_80083DE8`.
- **Waehler `FUN_80083CBC`:** Groesstes/Zweitgroesstes der **12** Zellen (2 + 10), liefert den
  Index **nur bei Abstand >= 7**, sonst -1 (Feld 12 Byte auf dem Stapel, nicht 36).
- **Zaehlstuecke (P119):** `CTR = 7` mit `bdz` VOR dem Rumpf = **6** Runden (`coin[1..6]`),
  dann `coin[7]`, dann `coin[8]`, dann die Nachzaehlschleife `coin[9..18]` mit der Schranke
  `cmpwi cr7,r10,0x12` **im Vergleich**.
- **Anker 67-70** (81/81 Woerter, 12/12 Verhaltensfaelle + 3 Rechenkernanker mit
  **256/256** Bytes und **24/24** Fensterwerten + 6/6 Waehlerfaellen, sichtbare Spur);
  **Regression 32 Frames + 95 Anker = 127, 0 Fehler**; **20 Modi Exit 0**;
  **Ghidra 2085 unveraendert (0 Aufrufe)**; Werkzeug `scripts/m88c_daily.py` **NEU**
  (Analyse + Gegenproben + **unabhaengiges Modell** + Wortanker).
- **Neue Regeln:** **P117** die **op-19-CR-Logik** und die **CTR-Zweige** (`bc 16/18` =
  `bdnz`/`bdz`, lesen KEIN CR) gehoeren in den Dekoder - die Schleifenbedingung
  "Rueckgabe == -1 UND Zaehler < 18" ist `crnand 6,0,28` + `bc 4,6` (`scripts/m88_mode.py`
  erweitert). **P118** magische Divisionen **rechnen**, nicht deuten. **P119** Histogramm in
  Stuecken. **P120** Messprotokoll in JEDEM Zweig fuellen (sonst meldet der Anker Vorgabewerte).
- **Eigene Fehler:** Aufzeichnung nur im C-Pfad (6/15 Faelle fehlgeschlagen); eine Modell-Erwartung
  falsch ("Historie 1..18 + Stunde 9" ergibt KEIN Fenster); zwei Fallnamen passten nicht zur
  Eingabe; Editierfehler zerschoss eine Kommentarzeile in `opmode.h`.
- **Port-Entscheidung:** der ungeschuetzte Histogrammindex (`Byte >> 1` ohne Schranke) wird
  gezaehlt (`daily_bin_overflow`), der Schreibvorgang entfaellt.
- **Offen:** **88d** (1-2), **89** (**1,5-2**, jetzt MIT den fuenf Nachbarfunktionen
  `FUN_80083630` 424 B / `FUN_800837D8` 68 B / `FUN_80083820` 44 B / `FUN_8008384C` 12 B /
  `FUN_80083FA0` 20 B - HOME-PAGE/PASSWORD-Familie, STRONG INFERENCE aus der Aufrufkette;
  `0x8008344C..0x80083630` = PASSWORD-(b)-Handler, im Inventar **keine Funktion**), **90** (1-2)
  => **4-6,5**.

## Batch 88b-2: Die Bildschirmzeichner (Kurzfassung)
- **Neu:** `port/opmode_screens.cpp` - `status_screen` (FUN_80026538, "BACKUP DATA
  INITIAL-COMPLETE": Tor `cfg+0x2C == 0` -> 1; **Popcount der LSBs** der fuenf Flagsbytes
  `[SDA(0x150)]+0xA4+12i` -> Grundzeile `(0x2D-2n)/2 = 22-n`; Titel (18,y), Deskriptortexte
  (+8) als "%s" zentriert, Schlusszeile (19,y+2); Schritt 1 wartet auf **IN2 Bit 4**),
  `error_screen` (0x80026240: **Popcount `cfg+0x00 & 0x1F`** -> `20-n`; x=23; je GESETZTEM Bit
  der Text; Schlusszeilen x=9/0x16; Schritt+1 in **cfg+0x1E**), `menu_description`
  (FUN_80026B7C: eigener Unterschritt **cfg+0x20**; Satz `+0x54+6*Schritt` = 3 s16
  {Index,Bank,Kennung}; Bank `0x80370000+*(u32*)(0x80370000+4*Bank)`; Kennung 0xFFFF ->
  FUN_8000FC60 ueber `0xFF0A0C00`, sonst FCB0; **11 Zeichnungen, Abschluss im 12.**),
  `queue_enqueue`/`queue_reset` (FUN_8002B394/B3BC: Ring **16 x 8 B {Quelle,Ziel}** bei
  `[SDA(0x9C)]+0x4004`, Schreibindex +0x4000, Nibble-Wrap; **Groessenparameter wird NICHT
  uebergeben**), Zellrechnung (`pool_dirty_mask` = FUN_8000EC58, `pool_set_cell` = FUN_8000F928).
- **Der Wartebit ist 0x2000 (Bit 13)**, nicht 0x200 (Korrektur zu 88b): `rlwinm rX,rY,20,0x1C,0x1F`
  + `mtcrf` -> CR7 = `(rY>>12)&0xF`, LT = hoechstes, SO = niedrigstes -> EQ = Bit 13.
- **Zeichenzellen-Pool:** Ziel = `**[SDA(0x28)]` (Arbeitsobjekt, im Bild 0; 50+ Zugriffe im ganzen
  Bild, u. a. Bank +0xB51C, Meshtabellen +0x12670, Kopf +0xB534). Zeile r: `+0x8458 + 0x104*r`,
  Zelle c: `+4+4*c`, **Dirty-Wort eine Zeile versetzt** (Zeilenanfang+0x104);
  Dirty `|= 1 << (c>>1)`. **Rechnung gebaut, Ablage gezaehlt** (die Schirme laufen ueber die
  Textschicht; vollstaendig hiesse: Arbeitsobjekt + Konsument der Dirty-Bits).
- **Anker 63-66** (106/106 Woerter, 14/14 Faelle, Tabellen/Texte, Spur);
  **Regression 32 Frames + 91 Anker = 123, 0 Fehler**; 19 Modi Exit 0; **Ghidra 2075 -> 2085**
  (10 `create_function` auf Adressen, die Ghidra nicht kannte: 0x80026240/6394/6538/26B7C/
  0FF8C/0F988 + 0x80026804/26A78/269C8/26A10; danach `save_program`).
- **Neue Regeln:** **P112** auch `rlwinm`/`rlwimi` setzen CR0 (Rc = LSB; der Projektdecoder
  druckt den Punkt nicht - `scripts/m88_mode.py` kennt es jetzt). **P113** Nibble-Bits kommen aus
  der CR-Ziehung (LT = hoechstes) -> Wartebit 0x2000. **P114** ROM-Alias `0xFF000000+X` und Bild
  `0x80000000+X` sind dieselben Bytes (sonst `PortFault`). **P115** ein Parameter, den die
  Funktion in der ERSTEN Anweisung ueberschreibt, ist kein Parameter. **P116** der Schritt eines
  Unterbildschirms haengt an der Aufrufkonvention (Handler `&cfg+0x1E` -> Unterbildschirm liest
  `cfg+0x20`; Handlerrumpf selbst `cfg+0x1E`).
- **Offen:** **88d** Grafik-/Ladeteil (Abarbeiter `FUN_8002B0F0`/B13C/B20C + LZSS/DEFLATE,
  Bankzeichner FCB0/FC60/FF8C, FUN_8000F988, Ablage des Zellenpools; 1-2), **88c** (0,5-1),
  **89** (1-1,5), **90** (1-2) => **3,5-6,5**.

## Batch 88b-1: Die Nutzlast der Bedienmaschine (Kurzfassung)
- **Neu:** `port/opmode_payload.cpp` - `ui_mask` (FUN_800260FC), `menu_cursor` (25E1C),
  `menu_list` (25F08), `row_box` (260AC), `text_len` (0D1C4), `date_ordinal`/Schaltjahr/
  Monatstage (83858/8394C/8390C), `coin_days`/`read`/`write`/`reset`/`error`
  (83D4C/83E18/83DE8/83FB4/83EBC), `init_steps` (26718), `init_dispatch` (261C4, **18** Handler),
  `prep_dispatch` (267B0, **12**), `bank_setup` (26DF4). `call_payload` ruft sie WIRKLICH.
- **Zellen:** `cfg+0x1C` Phase, **`cfg+0x1E` Schritt** beider Dispatcher, `cfg+0x20`
  Unterschritt. Muenzsatz: NVRAM **0xC0** (32 B) + `[SDA(0x7C0)] = 0x80129A00`
  (Flags, 18-B-Historie, Tag u16, Stundenfenster, Zaehler); `[SDA(0x7C4)]` = Stundenpaare,
  `[SDA(0x7B8)]` = Monatstage, `[SDA(0x830)]` = Texte, `[SDA(0x834)]` = 0x800259A8
  (Basis der Offset-Sprungtabellen).
- **Der Muenzsatz ist KEIN Credit-Zaehler** - er ist die Spielzeit-/Datumsbuchhaltung.
  Muenzeingaenge liest der ROM direkt aus IN2 (Bit 7/6/5/4 = COIN1/COIN2/SERVICE1/TEST).
- **Anker 57-62** (141/141 Woerter, 24/24 Faelle, 46/46 Tabellenwoerter, Spur);
  **Regression 32 Frames + 87 Anker = 119, 0 Fehler**; 18 Modi Exit 0; Ghidra 2075 (0 Aufrufe
  mit Nebenwirkung; 9 Dekompilationen).
- **Neue Regeln:** P106 Tabellenlaenge steht im CODE (nicht im Speicherbild - hinter der
  18er-Tabelle steht ASCII "BACKUP DATA ERROR"), P107 Endaufruf = Rueckgabewert des Handlers
  ist der des Dispatchers, P108 drei Zaehler aus "&(Zelle davor), lies +2", P109 die Uhr
  verwirft Daten > 29 (`FUN_80013880` liefert 29 bei (Jahr & 3) != 0), P110 Endlosschleife
  des Originals = Zustand (zaehlen, nicht haengen), P111 `count()` != Aufrufzaehler (`at()`).
  P102-Verscharfung: `FUN_80016330` braucht auch fuer `cfg+0x1E` einen Waechter (`cfg+0x1F`).
- **Offen:** **88b-2** die Bildschirmzeichner (FUN_80026538, Fehlerschirm 0x80026240,
  FUN_80026B7C, ROM-/Szenenlader des 12er-Dispatchers, Pool 8000F928; 1-2 Batches),
  **88c** Tagesbuchhaltung (FUN_80083968 + FUN_80083CBC; 0,5-1), **89** Texteingabe (1-1,5),
  **90** Spielseite (1-2) => **3,5-6,5 Batches**.

## Die vier Eingabequellen des Originals (CONFIRMED, Zensus `scripts/m86_input_surface.py`)
- **MMIO-Lesefenster 0x7D000000..0x7D0000FF**: im ganzen Bild werden nur **5 Bytes** gelesen:
  0x7D000000 IN0, 0x7D000001 IN1, 0x7D000002 IN2 (je Bild durch `FUN_8002379C`; IN2 auch
  `FUN_8000CA7C`/`80013A88`/`80013D80`/`80013F88`/`FUN_80025CDC`/`FUN_80067BB8`),
  0x7D000003 Port 3 (`FUN_80022FA4`/`FUN_80023420`/`FUN_80013F70`), 0x7D000004 **DIP**
  (`FUN_80008BC8`, nur beim Start -> fuellt Aux `[SDA(0x18)]` = 0x800AEC60).
- **I/O-Struktur `[SDA(0xB0)]` = 0x800B3928**: `io+0x1C` -> `cfg+0x30` (Bedienwort, **66 Lesestellen** - Batch 90, R138; die 87 aus B86/87 war falsch),
  `io+0x18` -> `cfg+0x32` (5), Panelrohwerte `io+0x2C`/`io+0x4E`, Waffenzustand `io+0x54..+0x58`.
  **KORREKTUR B91:** `io+0x18`/`io+0x3A` sind NICHT die Programmstores der Eingabe,
  sondern die **Ausgabefelder +8** der zwei 34-B-Panelhistoriesaetze (io+0x10/io+0x32),
  geschrieben von der dritten Stufe der Panelhistorie `FUN_80023864`.
  **Korrektur B87:** `io+0x68`/`io+0x7C` sind die
  **Differenzen** roh-minus-roh(4 Bilder zuvor), NICHT die Rohwerte.
- **Waffen-/Panelpfad** `FUN_80023A8C` (Bildschleife `FUN_80008668` @0x800086F8): `8002379C` (Panel),
  `800236EC` (Lampe), `800235F8` (Status), bedingt (`bcl`, Gate `extsb([SDA(0x18)]+6)==0`) `FUN_80022EA0`.
- **Wandler**: Kommandofolgen als Daten in `[SDA(0x12C)]` = 0x80086430 (+0 = `0F 0A 8D 0E 00`,
  +8 = `08 C0 C0 8D 0E 00` = Statusblock, +0x10 = `0F 8D 0E 00 80 C0 90 D0 A0 E0 B0 F0 80 00` = Achsen).

## Gemessene Semantik
- Panelwoerter: `W1 = ~IN0 | (IN2.3==0 ? 0x8000) | (IN2.1==0 ? 0x4000) | (IN2.0==0 ? 0x2000)`,
  `W2 = ~IN1 | (IN2.2==0 ? 0x8000)` — **IN2 = NIEDRIGES Nibble** (nicht 7/6/5/4, B82-Prosa war falsch);
  die `ori` werden uebersprungen, wenn das Bit 1 ist (ACTIVE_LOW).
- `FUN_80023864(Basis, Wert)`: Historie +0x1C/+0x1E/+0x20; `+0x16` steigende Flanke (2 Bilder),
  `+0x18` fallende Flanke, `+0x12`/`+0x14` "jemals", `+0x1A` Schieber; 8 Bitzaehler (+0x00..+0x07),
  Parkplatz **0xF2 (-14)** -> erste Schiebung beim 14. gesetzten Bild, danach alle 8.
  **DRITTE STUFE (Batch 91):** danach fuenf Wortpaare `(+8,+0x12) … (+0x10,+0x1A)` mit der
  Maske aus `aux+6` (0 -> 0xFFFF = ganzes Wort wandert, sonst 0xC000 = nur die zwei oberen
  Bits). Die Felder `+8` sind die Zellen `io+0x18`/`io+0x3A` der I/O-CHECK-Anzeige; nach
  jedem Aufruf ist `+0x1A` null und das Schieberwort steht in `+0x10`.
  Batch 86 hatte diese Stufe ausgelassen (Korrektur Batch 91).
- `FUN_800235F8`: Mode = `(cfg+0x4C>>12)&3`, Zustand `io+0x56`; `io+0x57`/`io+0x58`;
  Preset 1739, Zeitgeber **1740**, Achsenschwelle **64** (exakt 64 stellt nicht zurueck).
- **P95: `addic` (Opcode 12) setzt CR0 NICHT** (nur `addic.`, Opcode 13; MAME `ppcfe.cpp`).
  Die Zweige lesen das CR0 eines frueheren `and.`/`extsb.` (mit P83 kombinieren: Rc-Punkt fehlt im Listing).
  Belegte Faelle: `FUN_80023864` (CR0 aus `and.`), `FUN_800235F8` (CR0 aus `extsb.` von io+0x56),
  `FUN_80026C34` (CR0 aus `extsb.` von cfg+0x1A -> Zweig "Modus 0 = aus dem DIP lesen"),
  `FUN_80022EA0` (CR0 aus `subfc.` bzw. der EINEN `addic.` bei 0x80022F40).
- **P98: die Decodergaps sind Semantikgaps** - `lhax`/`sthx` (indizierte X-Form) und `addze`
  druckt `scripts/m78_dis.py` als `.long`; die indizierten Zugriffe sind der EINZIGE Weg der
  Wandlerwerte in den Puffer. **P99: Test VOR Inkrement = n+1 Runden** (Kanalruecklauf in
  `FUN_80022FA4` laeuft dreimal, r24 = -1/0/1). **P100: Geraetesemantik braucht zwei Quellen.**
  Ausserdem: `rlwinm rS,28,0x1C,0x1F` = `(rS >> 4) & 0xF` (Rechtsdrehung um 4!).

## Analogauswertung (Batch 87, CONFIRMED)
- Saetze in **20-B-Schritten ab `io+0x5A`** (NICHT ab io+0x54): +0x00 roh, +0x02 **Q16-Quotient**
  (4 Konsumenten: FUN_80028A30/80056C60/80082BA0/800833B8, `mulli 9102`/`7018`), +0x04/+0x06/+0x08
  4-Tap-Register, +0x0A aeltester Rohwert (Vorwert), +0x0C geglaettet, +0x0E **Differenz** ->
  io+0x68/io+0x7C, +0x10 Teiler, +0x12 Nullpunkt. Belege: Zensus (auch absolute Adressen) +
  `memset(io+0x5A,0,20)` in `FUN_80023390` (= Satz 0!).
- `io+0x6A/6C/7E/80` haben **keinen Schreiber** -> Schnittstellenzellen (P81); Port-Vorgabe
  0x1000 (Vollausschlag) / 0x800 (Nullpunkt) via `PORT_ADC_SPAN`/`PORT_ADC_ZERO`.
- `FUN_80022FA4`: Konfiguration `0F 8D 0E` (MAME: User/Vorzeichen/Akquisitionszeit!) + **3** Kanalrunden
  CH0/CH1/CH2 (Muster `80 C0 90`), 12 DO-Bits je Kanal, Abtastung NACH der Steigflanke ->
  Pufferwert `2*Wert | offenes DO-Bit` (0..~4095). Weiche `[SDA(0x18)]+0x15` (nicht +0xC):
  == 0 -> 0x7D010002/0x7D000001, != 0 -> 0x7D010004 (ueber Spiegel disp+8)/0x7D000003.
- `FUN_80022EA0`: 4-Tap-Mittel mit **Abschneiden zur Null** (`srawi`+`addze`), toter `mullw`
  (laeuft nur bei r8 == 0), Q16 `((s16)(v-Nullpunkt)<<16)/Teiler` mit Klemmen, Teiler 0 -> Port 0.

## Port-Module (Batch 86/87)
- `port/input_layer.{h,cpp}`: `BoardInputs` (+ `adc[8]`, `adc_span[2]`, `adc_zero[2]`),
  `InputKeyMap`/`HostKeyState` (Umgebung `PORT_INPUT_<NAME>`, `PORT_AIM_STEP`,
  `PORT_ADC_SPAN`/`PORT_ADC_ZERO`), `board_inputs_from_host`, `InputLayer::frame`
  (Rohsicht -> io+0x1C/+0x18 -> Originalhook `FUN_80026C34`; fuellt die 4 Schnittstellenzellen),
  `mmio_read`/`mmio_write` mit Adresszensus, `adc_parallel()`/`adc_sysreg()`/`set_adc_channel`.
- `port/adc12138.{h,cpp}` **NEU (87)**: ADC12138-Modell woertlich nach MAME `adc1213x.cpp`.
- `port/gun_input.{h,cpp}`: `panel_read`/`panel_history`/`lamp_frame`/`gun_status_frame`,
  **`adc_sequence` (FUN_80022FA4) / `adc_evaluate` (FUN_80022EA0)** + `AdcBuffer`/Zaehler,
  `GunInput::frame` (Gate `aux+6 == 0` fahrt die ADC-Kette).
- `port/input2_check.{h,cpp}`: Anker (42)-(47), Modi `input2`/`input-map`;
  `port/adc_check.{h,cpp}` **NEU (87)**: Anker **(48)-(52)**, Modi `analog`/`analog-ui`.
- Werkzeuge: `scripts/m86_input_surface.py`, `m86_history.py`, **`m87_adc.py`** (Zensus + annotierte
  Disassembly mit Rc-Bits/CR-Quellen), **`m87_analog.py`** (unabhaengige Nachbildung des ADC-Wegs).
- `port/host_input.*` (B82) bleibt der Einzelstift-Anker (TEST-Switch) — **nie im selben Rahmen** wie `InputLayer`.

## Bedienmaschine (Batch 88, CONFIRMED) - Kurzfassung
- `FUN_80026C34` = EINZIGER Schreiber von `cfg+0x30/+0x32` + 4-Zweig-Moduswechsler ueber
  `cfg+0x1A`; Handler 0 `FUN_80025CDC`, 1 `FUN_80025C4C`, 2 `FUN_80025B7C`, 3 `FUN_800259A8`,
  je mit Unterphase in `cfg+0x1C`; aus der Bildschleife `FUN_800089A0` je Bild gerufen.
  Gebaut: `port/opmode.{h,cpp}`, Anker (53)-(56) in `port/opmode_check.*`, Modi `opmode`/`opmode-ui`.
- Zustand 0 = Boot (`FUN_80083E18`; `cfg+0x2C = !(IN2 Bit 4)`, MMIO 0x7D000002; `FUN_80026718`;
  `FUN_800261C4`; Ende -> `cfg+0x2A = 14`, `cfg+0x08 = 3`).
- Zustand 1 = Vorbereitung (`FUN_800267B0`, `FUN_8005E6D0`) + Bankfeld `(cfg+0x4C>>10)&7` nach
  **`*[SDA(0x838)]`** + `FUN_80011A3C(Feld != 0)` -> `*[SDA(0x44)]`; Zustand aus `cfg+0x08`.
- Zustand 2 = drei Dirty-Queues leer (`*(u32*)[SDA(0xF8)]` - ZEIGER AUF ZEIGER - `+0x10000`,
  Ringe `+0xC01C/+0xD820/+0xEA24`), dann `FUN_80026DF4` + `cfg+0x08 = 2`; dann Menueliste
  `FUN_80025F08` + Cursor `FUN_80025E1C`.
- Zustand 3 = Phase 0 Kopie `cfg+0x48 -> +0x58` (oder `[SDA(0xB4)]+0x10 = 1` bei Index > 14);
  Phase 1/2 (a)/(b)-Deskriptor aus dem Menuebaum ueber das Trampolin; Phase >= 3 Zellenreset +
  Bankvergleich -> 2 (gleich) / 1 (anders).
- **Menuebaum:** `[SDA(0x150)] + 0xE0 + 16*idx` = 0x80099420 = `service_menu::menu::kLongBase`,
  {Name, UI-Wort(u16), u16, (a), (b)}; 15 Eintraege I/O CHECK ... GAME MODE (Menueeintrag = idx + 6);
  zweite Lesung des Ports stimmt 15/15 (P100).
- **P101** `addic`+`subfe` = "!= 0", `addic`+`cntlzw`+`rlwinm` = "> K" (nur CA, kein CR0).
  **P102** `FUN_80016330` loescht bis Folgebyte != 0 (im leeren BSS Amoklauf -> Ausgangszustand
  stellen). **P103** `[SDA(x)]` kann Zeiger auf Zeiger sein. **P104** `bcl` ist ein Aufruf.
  **P105** Trampolinziel definiert seine Argumente selbst.

## Offen (naechste Schritte)
- **88d-2 (neu, benannt):** der **FDC-/DEFLATE-Zweig** der Nutzlast
  (`FUN_8002B3D8` + `B540`/`BA64`/`BB0C`/`BC9C`/`C034`/`C5B0`/`C5CC`/`C5D8`,
  ~1050 Instruktionen; dazu `FUN_8000F988` Freiliste, `FUN_8000EE34`
  Mesh-Ausgabe, `FUN_8000FCF8`, `FUN_8000F468`; **1-1,5 Batches**).
- **88d-1: ERLEDIGT (Batch 88d-1)** - Abarbeiter + LZSS (bit-exakt), das
  Arbeitsobjekt samt Zeichenzellen-Pool, die Bankzeichner und die
  Sprite-Ausgabe; s. `/memories/repo/ladeteil.md`. Der Zellpool ist damit
  **gebaut** (Ablage + Dirty-Woerter); der **Konsument** (Zellcode -> Pixel)
  liegt ausserhalb dieses Teils (Live-Dump: Dirty-Woerter groesstenteils 0).
- **88c: ERLEDIGT (Batch 88c)** - `FUN_80083968` + `FUN_80083CBC` 1:1 gebaut und verankert
  (s. Block oben); die Kette ist geschlossen (ein Rufer `0x80083EA4`, alle Ziele gebaut).
- **89: ERLEDIGT (Batch 89)** - beide Schirme (308-311) + die fuenf Nachbarfunktionen aus 88c
  sind 1:1 gebaut und verankert (s. Block oben). Die (a)/(b)-Adressen: HOME 0x80082CC4/0x80082C34,
  PASSWORD 0x800835C8/0x8008344C. **Offen darin nur noch gezaehlt (P73):** Rahmengedometrie,
  Glyphen-/Zellpool (`FUN_8000F2B8`/`FUN_8001F1E0`), `FUN_800133AC`, `'I'`-Praefixbytes (HYPOTHESIS).
- **90**: die Spielseite (87 Leser des Bedienworts, Konsumenten der Panelwoerter UND die vier
  Q16-Leser `io+0x5C`/`io+0x70` mit `mulli 9102`/`7018`; ferner `FUN_800279C8`, `FUN_80028238`) — 1-2.
- Klein/offen: Statusfolge `FUN_80023420` (B85) schreibt in einen eigenen Zaehler statt ins
  ADC-Modell; Vorgabewerte der Schnittstellenzellen sind HYPOTHESIS; Kanalnamen CH0/CH1 =
  Yaw/Pitch aus MAME (STRONG INFERENCE); `aux+0x10` (Zustand 3, Phase 2) Bedeutung offen;
  Live-Betrieb der Maschine aus (Nutzlast noch gezaehlt).
