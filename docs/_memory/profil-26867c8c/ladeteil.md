# Grafik-/Ladeteil (Batch 88d-1, 2026-09-21)

## Der Abarbeiter der Kopier-Warteschlange (CONFIRMED)
- `FUN_8002B360` (Bildtakt) -> leer wenn `Schreibindex == Leseindex` UND
  `Restbytes <= 0` (Kombi `cror 26,5,5` + `crandc 2,2,5`); sonst bei
  Restbytes > 0 `FUN_8002B0F0` (Methode: 0 = LZSS `B20C`, 1 = FDC `C640`),
  sonst `FUN_8002B13C` (Auftrag aus dem Ring).
- `FUN_8002B13C`: `strcmp` (`FUN_8000D314`) gegen die **Magic-Tabelle
  `[SDA(0x1B0)]`** = "LZ " (`4C5A2000`) / "FDC\0" (`46444300`); LZSS-Zweig
  nullt das Fenster mit `FUN_8000D140(ctx,0,0x400)` = **0x400 WOERTER**
  (= 0x1000 B!), setzt `+0x4086 = 0xFEE`, `+0x4084 = 0`. Dann Leseindex+1,
  `+0x4094 = desc+0xC`, `+0x4098 = dst`, `+0x4088 = desc[2]`, `+0x408C = 0`,
  `+0x4090 = desc[1]`.
- `FUN_8002B20C` (LZSS): `want = min(rest,0x100)`, `base = rest - want`,
  `chunk = want` (**signed!**), Schleife `while (base + chunk > 0)`;
  Abbruch NACH einem Token nur wenn `chunk <= 0` UND Bit 8 des
  Steuerregisters 0 (`bc 12,23` @0x8002B344). Zellwert am Ende = `base+chunk`.
  Match-Kuerzung nur wenn `chunk < 0 && base+chunk < 0`.
- `FUN_8002B000` (Standalone, eigenes 0x1000-Stapelfenster, Start 0xFEE):
  Literal `rest--`, Match `rest -= len` dann `bc 12,1` -> ein Match, das die
  Restlaenge erreicht/ueberschreitet, wird **ausgelassen** (kein Kuerzen).

## Das Arbeitsobjekt `[[SDA(0x28)]]` (live: capture/m31_ram4mb.bin)
- `[SDA(0x28)] = 0x800AEDC0` -> `*[SDA(0x28)] = 0x800D55D0`; im Bild steht 0.
- `+0x04` Zeilenzahl (47) · `+0x08` Flussbit · `+0x0C` Zeiger · `+0x12` u16 ·
  `+0x14` u16 Bankbelegung (live 0x1B58) · `+0x16` u16 · `+0x18` Meshzeiger.
- `+0x1C` **Sprite-Raster**: 16 Seiten a 0x844 (16 Reihen a 0x84, 16 Zellen
  a 8 B, Reihenmarke +0x80, Seitenbits u16 bei +0x840).
- `+0x8458` **Zellpool**: Zeile r = +0x104*r, Zelle c = Zeile+4+4*c (64),
  **Dirty-Wort = Zeile+0x104** (eine Zeile versetzt); F928:
  `Dirty |= 1 << ((Spalte>>1)&0x3F)`, Zellwort bei +4*Spalte.
- `+0xB51C` **Bankliste** 15 x 12 {u16 Belegung, u16 Groesse, u32 Nutzlast,
  u32 ROM} · `+0xB5DC` Eintragsliste · `+0xE5DC` Bitmap (31 Worte) ·
  `+0xE65C` Meshtabelle (je gesetztem Bit 8 u16).
- **Rahmengedometrie** der Eingabeschirme = `(s16)*(obj+0xE65C+2v) | 0x80000`
  mit `v = (s16)*(obj+0xB570)` (0x80082A0C..38).
- Der Teil **beschreibt** den Zellpool; der Konsument (Zellcode -> Pixel)
  liegt ausserhalb (Live-Dump: Dirty-Woerter groesstenteils 0).

## Port-Module (Batch 88d-1)
- `port/src/opmode_load.cpp` (queue_tick/dispatch/dequeue, lzss_pump/block,
  word_set, str_cmp, work_*, pool_clear_all/pool_set_cell_direct/
  pool_fill_rect/cell_rect_store/frame_geometry_word, bank_draw_*/bank_commit,
  sprite_color/grid_color/label/draw), `opmode.h` **5d**,
  `opmode_load_check.{h,cpp}` **NEU** (Anker (76)-(80), `dump_load_ui`),
  `text_layer` Poolhaken (`set_pool_hooks`), `port_selftest.cpp` druckt die
  Spur in `service-ui`.
- Werkzeuge: `scripts/m88d_load.py` (Disassembly/Zensus), `m88d_pool.py`
  (Objektzensus + Live-Auswertung), `m88d_anchor.py` (Wortanker + Modell),
  `scripts/m88d_workstream.py` (Doku-Helfer).
- Modi/Anker: `port_selftest opmode` -> `[76] 80/80`, `[77]-[79] 12/12`;
  Regression **32 Frames + 101 Anker = 133, 0 Fehler**; 20 Modi Exit 0.

## Anker-Kernwerte
- Container (ROM-Datei `rom/build/830d01.27p.be.bin`, Offset 0x1000):
  Magic `4C5A2000`, Groesse **713368**, Pruefsumme **0x0321F4C4**.
- Standalone: 0 Abweichungen zur Bilddatei; Pumpe: **2642 Aufrufe**, Summe ==
  Kopf, 0 Abweichungen. Bankanker: 15/15 Saetze == Live-Dump, Belegung 0x1B58.
- Farbwandlung EDCC (Tabellenwert n=0x1F, den=0xFF): `00FE18CF` (Alpha 0xFF),
  `00FE0000` (Alpha 0).

## Regeln (neu)
- **P124** Happenzaehler im ROM ist **signed** (`cmpwi`) - als `u32` laeuft
  die Pumpe in EINEM Aufruf durch (Fehler nur an der Aufrufzahl sichtbar).
- **P125** "maximal N Byte je Aufruf" = Startgroesse des Happens.
- **P126** Dekoder-Anker braucht Groesse + Pruefsumme + Bytevergleich, die
  Referenz aus einer **Datei** (frueher gelaufene Anker schreiben ins
  RAM-Abbild: an +0x8CADB 1 Byte Abweichung gemessen).
- **P127** die Funktionsgrenze steht im Rohwort (`0x8000FE78` und `0xFF8C`
  sind ZWEI Funktionen; das Inventar fuehrte sie als eine).

## FDC-/DEFLATE-Zweig (Batch 88d-2, 2026-09-21) - GEBAUT, bit-exakt
- Neun Funktionen: `B3D8` (Pumpe: BFINAL/BTYPE, give-back, Flush),
  `B540` dynamic, `BA64` fixed, `BB0C` stored, `BC9C` Symbole+LZ-Kopie,
  `C034` Tabellenbauer, `C5B0`/`C5CC` Allokator (ACHT-B-Einheiten,
  Zeiger = Block+4), `C5D8` Flush.
- Eintraege 8 B `{op,bits,val,next}`: 16 Literal, 15 Blockende, 0..13
  Extrabits (val = Basiswert), 16+curr Verweis (next), 99 ungueltig.
  `len_extra[29]/[30] = 0x63` in der ROM-Statiktafel = die Markierung.
- EIN FDC-Auftrag = EIN Aufruf (ganzer Container); LZSS dagegen 2642 Happen.
- **R128** Artefakt `_m88d_dis.txt` druckt `srw/slw/sraw` als (rS,rA,rB) -
  PPC meint (rA,rS,rB): woertlich genommen dreht JEDER Bitpufferschritt.
- **R129** Bitpuffer: `if (bits<cond_k) lade ((cnt_k-bits)>>3)+1` mit ZWEI
  Zaehlern je Aufrufstelle (cond_k/cnt_k, Unterschied 1).
- **R132** ein Test braucht eine Zusatzbedingung auf den PFAD (mein
  synthetischer fixed-Block bestand ueber den dynamic-Zweig).
- Messung: Werkzeug 12/12 Container bit-exakt (2 374 684 B); Port-Anker
  (81) 122 Woerter / (82) 4 Container + 4 Resident-Buendel (Ziele aus
  [SDA(0x150)]+0x18: 0x80180000/0x80198000/0x801F2100/0x80260000,
  1 896 744 B) / (83) stored+fixed+BTYPE 3. Zellpool: **0** Zellen - die
  BankTABELLEN liegen im BILD, der Zweig liefert BuendelDATEN.
- Offen: die 6 kleinen FDC-Aliase `FF08A000..FF08D200` (kein Ziel in der
  Tabelle); die **Breitenregel** der Untertabellen (Port weitet auf
  max_len-drop; ROM nutzt eine Stufenkette, Rahmen nur 9488/8800 B).

## Die vier Restfunktionen (Batch 88d-3, 2026-09-21) - GEBAUT, Anker (84)-(88)
- `FUN_8000F468` **Zeichenkasten** (193 Insn): SCHREIBT Zellwoerter in den Pool.
  `e = obj+0xB51C+12*index`; `mask = FUN_8000EC58(x, *(u8*)(e+4))` (**Rueckgabe
  in r3**, R134); `count = *(u8*)(e+5)`, `breite = *(u16*)(e+6)`,
  `tab = *(u32*)(e+8)`, `innen = *(u8*)(e+4)`, `mesh = obj+0xE65C+2*(s16)*(e+0)`.
  Je Zeile k, je Spalte i = 1..innen-1 EIN Element (u8 wenn breite <= 0x100,
  sonst u16): Wert != 0 -> `Zelle(x+i-1, y+k) = (s16)mesh[geom+Wert] |
  ((param_4 & 0x1F) << 17)`; danach `Dirty-Wort (y+1+k) |= mask`.
  Bankeintrag-Felder: **+0 s16 geom, +4 u8 Spalten, +5 u8 Zeilen, +6 u16
  Breite/Kennung, +8 u32 Tabelle** (dieselben Bytes, die EC80 als
  {Belegung, Groesse} schreibt).
- `FUN_8000F988` **freigeben** (182 Insn): `index < 0` -> Bereich
  `[geom2+groesse2, Belegung)` + Groessenfelder 3..15 nullen; **`index < 3`
  ist WIRKUNGSLOS** (0x8000F9A0 `bc 12,4`); `len <= 0` Rueckkehr. Sonst:
  Eintragsring (Suchwert `(s8)e[0]*0x800 + (s16)e[2]`, Treffer -> `e[0] = 0xFF`,
  `r9` **je Durchlauf** auf 0), Bitmap-Bits FREI, Bankliste `geom -= len` fuer
  `geom >= Ende`, Messtabelle um `len` nach vorn, Ausgabestand `-= len`.
- `FUN_8000EE34` **Messtabelle ausgeben** (143 Insn): EIN Eintrag je Aufruf in
  das **K037122-Char-RAM**. `pos = (obj+0x14 >> 6) & 0x3FF` = **Bits 6..15 des
  WORTES = obj+0x16** (R135!); `zaehler = obj+0x18 >> 22`; gleich -> FERTIG
  (Seitenbits -> obj+8 0/1, obj+0xC = [SDA(0x34)]/[SDA(0x30)], Rueckgabe 1).
  Sonst Position +1, `e = obj+0xB5DC+12*pos`; `(s8)e[0] < 0` -> ueberspringen;
  `0x74000032 = e[0] & 0x1F`; `Basis = 0x74040000 + (s16)e[2]*0x80`;
  `e[8] == 0` -> KOPIE (8 Byte je Zeile an die **ungeraden** Byteplaetze),
  sonst 1-Bit-Expansion ueber die 2-B-Tabelle `e[8]` (MSB zuerst, CR7-Ziehung).
- `FUN_8000FCF8` (33 Insn): wie FCB0 + `EC80` + Ausgabe **bis fertig**,
  dazwischen `FUN_8000CB40` = **Watchdog** (Zeitbasis `FUN_80008448`,
  Fenster 0x1F400, Kickbyte 0x80 auf `0x7D010006`, Zelle `[SDA(0x118)]`).
- **KORREKTUREN am Gebauten:** (1) `EC80` hat ein **Budget** (je Bit 8 von der
  gerundeten Groesse abziehen, bei negativem Rest die Suche beenden);
  (2) der **Messtabellen-Cursor** rueckt **+8 Halbwoerter je Bit** vor
  (Zaehler IN der Acht-Schleife) - Live-Dump-Gegenprobe: die Messtabelle ist
  die Identitaet `mesh[i] = i`; (3) der **Ausgabestand** steht in
  `obj+0x16` (Live: 0xDAC0 -> (>>6)&0x3FF = 875 == Ringzaehler).
- Eintragsring: 1024 Plaetze a 12 B (`0xB5DC..0xE5DC`), Erzeugerindex
  `obj+0x18 >> 22`, Verbraucherindex `obj+0x16`.
- Anker: (84) 46 Wortanker · (85) Zeichenkasten (Zellen + Dirty) · (86) Freigabe
  inkl. Sonderfaelle · (87) Ausgabe beide Zweige **bit-exakt** gegen die
  Bildbytes · (88) FCF8 + Watchdog. **Regression 32 Frames + 109 Anker = 141,
  0 Fehler**; 20 Modi Exit 0; Ghidra 2085.
- **Der Zellpool-Konsument ist der K037122 selbst** (Tile-/Char-Generator,
  MAME `k037122.cpp`: `bank = m_reg[0x30/4] & 7`) - Hardware wie die Voodoo.
  Zu ersetzende Schnittstelle: Bankreg `0x74000032` + Char-RAM
  `0x74040000..0x7407FFFF` (+ Tile-RAM `0x74020000..0x7403FFFF`, aus anderen
  Funktionen beschrieben).
- Neue Regeln: **R134** ein Aufruf ueberschreibt r3 (Rueckgabe statt Argument);
  **R135** `lwz` + `rlwinm 26,0x16,0x1F` meint das ZWEITE Halbwort;
  **R136** ein Zaehler INNERHALB einer Schleife zaehlt anders als davor;
  **R137** ein "wirkungslos"-Zweig gehoert ins Szenario.
- Werkzeug: `scripts/m88d3_rest.py` (korrigierte Disassembly + unabhaengiges
  Modell + Szenarien + erzeugte `port/src/opmode_rest_words.inc` /
  `opmode_rest_expect.inc`), `scripts/m88d3_doku.py` (Doku-Helfer).
- Naechster Schritt: **90 Spielseite** (87 Leser von `io+0x1C`, Panelwoerter,
  vier Q16-Leser `FUN_800279C8`/`FUN_80028238`) - danach ist die Eingabeschicht
  fertig.
