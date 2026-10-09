# Audio (Silent Scope / Hornet) — Batch 60

**Kernfakt: Audio liegt NICHT im PPC-Image.** Eigener Rechner (CONFIRMED aus
`mame/mame/src/mame/konami/hornet.cpp`, `ROM_START(sscope)`):

- Sound-CPU **Motorola MC68EC000 @16 MHz**, eigenes Programm-ROM **`830a08.7s`** (512 KB) — lokal in `rom/`
- Sound-Chip **Ricoh RF5C400** (PCM, 32 Kanäle), 68K-Adressraum `0x200000-0x200fff`
- Sample-ROMs **`830a09.16p` + `830a10.14p`** (je 4 MB), lokal in `rom/`
- PPC <-> Sound: **Konami K056800 (MIRAC)** Mailbox im PPC-Adressraum **`0x7D030000-0x7D03000F`**
- Sysreg `0x7D010000`: Reg 4 Bit 7 = SNDRES; Reg 5 = Sound Control (MODE/MUTE/DEEN/ATCK je Kanal)
- MAME-Referenzen lokal: `src/devices/sound/rf5c400.cpp` (18 kB), `k056800.cpp` (3,9 kB)

## PPC-Seite (CONFIRMED, Batch 60 + 61 gelesen — Batch 61 = Abschluss)

- **Mailbox-Nutzer (5, Suchmuster `lis rD,0x7D03`):** `FUN_8000E6BC` (Kommando-Sender: 4 B nach
  `0x7D030000`, Flag `0x7D030007=0x10`, Handshake-Poll Bit 7, Timeout `0x7D000`), `FUN_8000E690`
  (MIRAC-Bit `0x7D030006`), `FUN_8002403C` (Selbsttest), `FUN_8002D644` + `FUN_8002D798` (Status)
- **Treiberblock `0x8000E588-0x8000EBAF` = 13 Fn** (Batch 61 korrigiert; `FUN_8000E7F0`
  = 492-B-Lump = 52+216+224 B, `0x8000E824`/`0x8000E8FC` = Rampen L/R): Bit-Bang `E588`/`E60C`
  über **Sysreg Reg 5 `0x7D010005`** (`0x44/0x55`=MUTE=Puls runter, `0x11`=ATCK=Puls hoch),
  Delay `EC08`, Sender `E6BC`, Dequeue `E7A0`, Master-Init `E7F0`(Volumen 20/20),
  Lautstärke `E9DC`, Queue-Reset `EB40`, Cursor `EB68`, Modus `EB7C`, Append `EB88`
- **Trigger: DREI Einstiege, 208 Aufrufstellen** — `FUN_8003C750(id)` 79 Fn/132 Stellen,
  `FUN_8003C6F0(id<<16)` 31/48, `FUN_8000EB88(id<<16)` 18/28 (direkt, ohne Gate/Variante).
  Kein Rohwort-Treffer ⇒ Trigger läuft nie über das Deskriptor-Trampolin.
- **Wire-Wert = `id << 16`** (4 Byte BE nach `0x7D030000`, dann `0x7D030007=0x10` = IRQ);
  Ringpuffer **`[SDA(0x24)]+0x14`**, 64 Einträge `id<<16`, Zeiger `+0x115`/`+0x114`,
  Volumen L/R `+0x11/+0x12` (0..30), Modusbyte `+0x10` (toter Code, nur 0).
- **ID = `Gruppe<<8 | Index`**: `0x0xx` global, `0x1xx` = **BGM mit `+0x20`-Variante**,
  `0x2xx..0x8xx` SFX-Bänke, `0x9xx` = BGM-Transport (0x901/0x902). 76 distinkte IDs belegt;
  **keine ID-Tabelle im PPC** ⇒ Mapping liegt im 68K.
- **Variantenflag = `cfg+0x48` Bit 23** (+0x20 wird bei Flag **0** addiert — Batch-60-Angabe
  war invertiert); **Gate = Bit 1 von `*[SDA(0x240)]+8`** (Trigger wird verworfen).
- **Lautstärke-Quelle:** `cfg+0x48` Bits 25-29 (Default `0x29800000` ⇒ 20 = Init-Wert);
  Hardware ist ein **6-Bit-Auf/Ab-Zähler ohne Readback** ⇒ Treiber führt Istwert selbst;
  **MAME modelliert die Lautstärke nicht** (Reg 5 nur Log, K056800 Reg 4/5 nie geschrieben).
- **Für den Port: 3 Trigger-Hooks + 1 Stop-Hook + 1 Feldwert** (kein Volume-Hook).

## Konsequenz für den Port

Audio ist **kein Blocker** für den Renderer-Port. Empfehlung: RF5C400/K056800 wie MAME
**einbetten** statt 68K-Programm zu analysieren; Lautstärke (Gain) muss der Port **selbst**
machen (MAME hat sie nicht). Stufe 1 = reiner ID-Logger (3 Hooks).

Details: `analysis/f5-descr-batch61-2026-09-17.md` (Abschluss),
`analysis/programm-inventar-2026-09-17.md` §5, `analysis/port-interface.md` §5,
Skripte `scripts/m60_audio.py`, `scripts/m61_{ids,audio2}.py`.

## 68K-Seite (Batch 164 statisch gemessen, in BATCH 165 nachgemessen/korrigiert)

**Ladeforschung:** `rom/830a08.7s` ist **wortgetauscht** (`Bild[i] = Datei[i^1]`,
aus `ROM_LOAD16_WORD_SWAP` in einer 8-Bit-Region). Danach: `SSP = 0x00110000`
(RAM-Spitze), `PC = 0x00000080`, IRQ1 `0x0AE` (344,5 Hz, Rumpf `0x0FFA`),
IRQ2 `0x0C8` (Mailbox, Rumpf `0x1054`), IRQ6 `0x0E2` (Rumpf `0x1168`).
Nur **3,2 %** des 512-KB-ROMs sind Code (8466 Insn); 97 % sind Tafeln.
Werkzeug: `scripts/m164_68k.py` + `tools/m68k-venv` (capstone 5.0.6), offline.

**Der Wire-Wert ist die ID:** der PPC schickt `id << 16` ⇒ Byte 0 = **Gruppe**,
Byte 1 = **Index**. IRQ2 legt `{Gruppe,Index,reg2,reg3}` in einen **Ring**
`0x100004 + 4*idx` (256 Saetze, Schreibindex `0x100404`, Leseindex `0x100408`).
Die Hauptschleife (`0x13EE`) leert ihn in `0xE18`.

**ID-Tafel (die im PPC fehlende Zuordnung, CONFIRMED):**
`*[0x78000] = 0x78C18` Gruppentafel, `*[0x78004] = 0x78C54` (long = **10**
Gruppen), Satz **6 B** = `u16 Anzahl` + `u32 Tafelzeiger`. Klangsatz **10 B**
(B164-Lesart, in B165 **korrigiert**): `+0` Kennung (Bit 7 Flagge, Bits 0-6
**7-Bit-Wert — KEIN 0..7-Stimmenindex**, 20 verschiedene Werte gemessen),
`+1` Pegel, `+2` **u32 Zeiger auf einen NAMENStext**, `+6` **u32 Zeiger auf ein
MIDI-FILE** (`MThd`, Format 1, Division 48 bei 293 / 480 bei 24 Saetzen, Tempo-
und Taktart-Meta). Gruppen/Anzahlen: 82/54/21/10/19/83/31/9/6/3 = **318 Saetze**
(1-basierter Index). Vollstaendig: `analysis/_m164/_groups.txt`; Wiederholungs-
probe `analysis/_m165/_sets.txt` (318 Saetze, 317x `MThd`, 1 unbelegter Platz
bei Gruppe 9 Satz 3).

**Zeitliche Logik — ABLAUFMASCHINE JA, ZEIT IM STROM NEIN (B165 gemessen):**
zwei Notenspuren `0x101536`/`0x102646` (je `0x1110` B: `0x1000` B Ringpuffer +
Schreibposition `+0x1000`, Leseposition `+0x1004`, Laufwert `+0x1008`,
Akkumulator `+0x100C`), Zeigerzelle `0x103756`, **ein Byte je Aufruf** (`0x5746`,
Ruecklauf bei `0xFFF`), **schwellwertgesteuerter** Nibble-/Satz-Verteiler
(`0x8B80`: Tafeln `0x9B28`/`0x9BA0`, je 16 Eintraege `{u32 Ziel, u32
Schwellwert}` mit Schwellwerten **1/2/3/256** — ein Wertedekoder, KEINE
Notenspur im engeren Sinn); **acht Stimmenplaetze** `0x100418` (Stride `0x202`,
514 B), je 18 Unterrecords zu 18 B; **Software-Huellkurve** in `0x2A40`
(Zustand `+8`: 1 = Rampe auf, 2 = ab; Timer `+6`/`+7`; Pegel `+5`);
Tickzaehler `*[0x100000]` (344,5 Hz) — **ausserhalb** des Spurpfads.
**Wer die Spuren fuellt (CONFIRMED):** der 68K **selbst**, Byte fuer Byte aus
eigenem Rahmenstand — sechs Byte-Schreiber (`0x28B0`, `0x384E`, `0x3B46`,
`0x3C54`, `0x3D36`, `0x3E78`), INIT `0x4C1C` (Positionen 0, Laufwert 1,
Akkumulator 0x80); der Schreiber `0x3B46` kopiert ein im Rahmenpuffer gebautes
**SysEx `F0 00 7A F7`**; **nur ZWEI** Verweise auf den Mailbox-Ring `0x100004`
(beide im IRQ2-Pfad) — die Spur ist **nicht** der PPC-Strom und **nicht** eine
ROM-Kopie. **Kein Tickzugriff im Spurpfad** (B167 praezisiert: von den 12
absoluten Treffern auf `0x100000` sind **6 ein `pea`-Argument**, 3
Adress-/Basisladungen, **1 ein Schreibzugriff**, 2 die blosse **Konstante** und
**genau 1 ein echter Lesezugriff** (`0x4058`) — keine davon im Spurpfad).

**PCM-Programm-Tafel (B165, STRONG INFERENCE):** parallel zu den 318 Saetzen
liegt ab `0x7A008` eine **16-B-Tafel mit 318 Plaetzen**
(`8 mod 16`-Ausrichtung): `+0 u16` (Rolle offen), `+2 u16` = 0x40/0x80,
`+4 u32` **A**, `+8 u32` **B**, `+12 u32` fast immer `0x20`. In **303/303**
geprueften Plaetzen gilt `0 < A < B < 0x400000`; die Werte sind
**Wortadressen** in die zwei 4-MB-Sample-ROMs (MAME `rf5c400.cpp:221-251`:
`start = ((startH & 0xFF00) << 8) | startL`, `read_word((pos>>16)<<1)`).
**Keine dritte Adresse** ⇒ „Start <= Schleife <= Ende" ist fuer diesen Satztyp
**widerlegt** (0/318); die Schleife fuehrt MAME als Ruecksprung-**Abstand**
(`pos -= loop<<16`). Beleg: `analysis/_m165/_rfrec.txt`, `_rfscan.txt`.

**RF5C400:** 32 Kanalbloecke (`0x10F378` Zeiger, `0x10EF74` Spiegelrecords
32 B); Programmierer in `0x5ED8` (u. a. `0x61C4`-`0x6260`) schreibt Start/Ende/
Loop (24-Bit) und Pan (Tafel `0xA5A6`) aus dem Spiegel. **Die Effektregister
`0x20`-`0x27` werden WIRKLICH programmiert** (`0x8DF6` aus dem ROM-Block
`0x9C20`; Einzelsetzer `0x8EF4`, `0x8F42`, `0x8F60` …) — also genau die
Register, die MAME **nicht** rechnet. Sechs Mailbox-Opcodes `0xF1`..`0xF6`
(Tafel `0x0F06` → `0x4160`/`0x4262`/`0x42A8`/`0x4318`/`0x436E`/`0x43D0`) steuern
Tor/Stimme; `0x8CB8` ist ein **Leerlauf** und wird 22× als „Wartezeit" gerufen.

**Folge fuer A' (B165 verdichtet):** die **Zuordnung** ist eine statische Tafel
(portierbar) PLUS **318 echte MIDI-Dateien im ROM** (Format 1, Division 48/480,
Tempo-/Taktart-Meta) PLUS eine parallele **318er-Tafel mit Start/Ende-
Wortadressen** in die Sample-ROMs (`0x7A008`). Die **Laufzeit-Maschine** ist des
68K **eigene** Kommando-Warteschlange (zwei Ringpuffer, Verbraucher, Schwellwert-
Verteiler, acht Stimmen, Software-Huellkurve) — ein „PCM-Blob je ID" trifft den
68K nicht. **Nicht gemessen** (dafuer braucht es einen Mitschnitt): ob das Spiel
diese Wege im Betrieb **durchlaeuft** und welche Saetze es anfordert.
Belege: `analysis/port-batch164-68k-messfrage-teilregression-2026-09-26.md`
(§10 Korrekturzeilen) und
`analysis/port-batch165-banksetup-slotbytes-68k-nachmessung-2026-09-26.md` §3.

## Nutzdaten extrahiert, Noten→Sample gemessen (B166, 2026-09-26)

**Werkzeug:** `scripts/m166_audio_extract.py` (offline, importiert
`scripts/m164_68k.py`). Nutzdaten nach `build/audio_extract/` (gitignoriert),
ins Repo nur Tafeln.

**MIDI:** 317 der 318 Saetze (`MThd`; 1 unbelegter Platz Gruppe 9/3), **358 688 B**,
Format **1**, Division **48 (293) / 480 (24)**, **98 998 Ereignisse**,
**40 057 Note-On**, Noten **18..95**, 21 Tempi, 33 distinkte Namenstexte.
Laenge aus den `MThd`/`MTrk`-Chunklaengen, Gegenprobe mit eigenem SMF-Parser
(jede Chunklaenge muss exakt aufgehen).

**PCM:** 303 Bereiche der 16-B-Tafel ab `0x7A008` = **14,7 MB**.
**Die Daten sind 8-BIT** (mittlere |Differenz| ≈ 42 gegen ≈ 10 600 fuer beide
16-Bit-Deutungen), und **Feld `+2` ist der Formatcode**: `0x40` → **erstes**
Byte, `0x80` → **zweites** Byte — bewiesen mit einer **Schleifenpunkt-Probe**
(`|s[n-1]-s[n-1-C]|`, `C` = Feld `+12` = Loop-**Abstand**): 114/142 bzw. 111/140
Siege, Median 0,00 gegen 31/87. Genau MAME `TYPE_8LOW`/`TYPE_8HIGH`. Der rohe
Byte-Strom ist schlechter ⇒ **ein Byte je 16-Bit-Wort**. **Die 21 Plaetze mit
`+2 = 0x00` sind 16-BIT (B167 ENTSCHIEDEN, s. u.)** — die B166-Vermutung „wie
`8HIGH` fuehren" ist **ueberholt**.

**Noten→Sample ist eine TAFEL, keine Formel:** `*[0x7A004]` = **`0x0007D7B4`**
(4-B-Zeigerfeld), indexiert mit Stimmsatz-Feld `+0x5F` → Liste von
**8-B-Eintraegen `{u16 Note, u16 Pitch-Offset, u32 Deskriptor}`**, Ende
`byte0 = 0xFF`, Treffer gegen die **aktive Note** `+0x100D` der Spur (`0x5ED8`,
`005F66`-`005FA6`). Deskriptor aus dem 16-B-Pool ab `0x7A008`
`{Grundperiode, Format, Start, Ende, Schleife}`; `0x7AE48` =
`{0x2EE0, 0x0040, 0x174B0B, 0x181B5C, 0x151D}`. Register: Start `+4` → `0x00`/`0x01`,
Ende `+8` → `0x03`/`0x04`, Schleife `+12` → `0x04` hoch/`0x05`, Pan aus Tafel
**`0xA5A6`** → `0x06`, **Typ in Register `0x08` Bits 6-7** (`0061F0`-`00625E`).

**Umfang des zu ersetzenden Treibers (gemessen):** 42 Pfadkoepfe =
**3335 Instruktionen / 6670 B** (Kopf bis naechster Kopf = Obergrenze);
`0x5ED8` allein 752 Insn.

Belegt in `analysis/port-batch166-audio-extraktion-noten-sample-2026-09-26.md`
und `analysis/_m166/` (`_midi.txt`, `_pcm.txt`, `_loopprobe.txt`, `_heads.txt`).

## B167 (2026-09-26) — Einordnung, zwei Restfragen, Import-Rezept

**ENTSCHEIDUNG (Nutzer, 2026-09-26): der 68K-Treiber wird DEKOMPILIERT UND NATIV
PORTIERT, nicht dauerhaft emuliert.** Begruendung: der 68K spielt MIDI-Dateien
mit Tempo ab, traegt also **zeitliche Ablauflogik** — das ist der zweite Fall der
Nutzerregel vom 25.09. Der in A' geplante „schlanke Stimmen-Player" **ist** diese
native Portierung (Sequenzer, Stimmen, Huellkurve), **ohne Hall**. Die offene
Entscheidung „Player nachbauen ODER dekompilieren" ist damit **erledigt**.
`strategy: nativ portieren, nicht emulieren` — kein RF5C400-/K056800-Kern im Port.

**Speicherkarte des 68K (CONFIRMED, `hornet.cpp:1002-1012`, Zeilen belegt):**
`0x000000-0x07FFFF` ROM · `0x100000-0x10FFFF` RAM (64 KB) · `0x200000-0x200FFF`
RF5C400 · `0x300000-0x30001F` K056800 (`umask16(0x00ff)`; IRQ2 daraus,
`:1460`) · `0x480000`/`0x4C0000` Schreib-Luecken (`nopw`) · `0x500000`
Timer-Tor · `0x600000` Timer-Ack (beide **nicht lesbar**). CPU: `M68000`,
16 MHz (`:1424`); Periode **344,5 Hz** (`:1426`). Die ROM-SHA-1 stimmt mit
MAME **zeichengenau** (`2556a51e…`, `:1672`).

**Frage 1 — die 21 Saetze mit `+2 = 0x00` sind `TYPE_16` (CONFIRMED).** Der
Codepfad `0x63EC`-`0x641A` (und wortgleich `0x68A8`-`0x68D6`):
`d0 = desc[+2] | 0x10 ; d0 <<= 8 ; reg08 = (ram[+6] & 0xFF) | d0`. Mit
`TYPE_MASK = 0x00C0` (`rf5c400.cpp:37-40`) ergibt `+2 = 0x00` die Maske `0x00`
= **`TYPE_16`**; das Bit `0x10` liegt **ausserhalb** der Maske und ist **kein
Typbit**. `0x40` → `TYPE_8LOW`, `0x80` → `TYPE_8HIGH`, `0xB2F8` (14 Plaetze) →
`0xC0` = **unbelegt** (MAME: `sample = 0`). **Datenprobe:** die Schleifenprobe
allein trennt nicht (die HIGH-Lane ist bei einem 16-Bit-Sample ohnehin fast
immer stetig); die **Nullprobe** (LOW-Lane eines FREMDEN Samples einsetzen)
trennt: das 16-Bit-Wort der 21 Plaetze ist **7× stetiger** als mit fremder Lane
(Wort-Minimum 1,0 gegen 7,0; `argmin` eng bei `C0`, 88 % in {−1,0}), waehrend
dieselbe Probe bei `0x40`/`0x80` **degeneriert** (echt ≳ Null) — genau wie es die
Code-Zuordnung vorhersagt. ⇒ **Code und Daten stimmen ueberein.**

**Frage 2 — `0x26D2` ist KEIN Verteiler, sondern ein Selbsttest (CONFIRMED).**
Er ist **Rumpf** des Kopfs **`0x2684`** (`selftest_bit_dispatch`). Kette:
`IRQ2 0x1054` → `0x27C2` (Kommandobyte aus `0x300005`) → Vorprobe `0x1718`
(`d7` = 1/2) → `0x23A4` (1) bzw. `0x2684` (2) → Handler **`0x2622`**
(Muster schreiben ueber `0x8D48`) und **`0x2606`** (Probe lesen ueber `0x8CE8`).
Das Argument ist ein **Bitsetzer ueber acht 1-MB-Fenster** (`0x000000` …
`0x700000`), je gesetztem Bit **ein** Rufen. **Es gibt KEINE Tafel** — IRQ2
vergleicht in einer `cmpi`-Kette (`0xFC`/`0xFF`, dann `0xF0`/`0xFC`/`0xFE`).
**KORREKTUR an B165:** die Zelle `0x100000` wird hier als **Basis des
Arbeits-RAM** gepusht (Bit 1 des Bitsetzers), **nicht** als Tickzelle; die
Musterprobe schreibt bei `base+0x2AA`/`0x555`/`0x8080`, die Zelle selbst **nicht**.

**Umfang und Pruefstand (B167 gemessen):** 42 Pfadkoepfe; die B166-Regel ergibt
**3335 Instruktionen** (reproduziert), die feinere Kopfmenge **2727**; die
B166-Bytes „6670" sind **2 × 3335**, keine Spannensumme. **32 der 42 Koepfe sind
fuer den Port noetig; die 10 Effektkoepfe (`0x8DF6` + neun Setzer) NICHT** (Hall
bleibt weg). Pruefstand **ohne MAME**: ein **Offline-68K-Lauf** gegen die
Port-Ausgabe, verglichen wird die **Register-Schreibfolge** auf `0x200000` /
`0x300000` als `(tick, adresse, wert)` — machbar, weil der Pfad nur **45
distinkte Mnemonics** braucht.

**Import-Rezept (Import ERLEDIGT, Batch 175):** `build/m68k/830a08.7s.68k`
(gitignoriert), `language = 68000:BE:32:default` (Ghidra 12.1.2 kennt **kein**
`MC68000`; `default` = 68040.sla als Obermenge), `compiler_spec = default`,
Basisadresse 0, **wortgetauschtes Bild** (`Bild[i] = Datei[i ^ 1]`, R403; die
Datei `830a08.7s.img` selbst ist nicht ladbar). **Das Programm liegt im
Ghidra-Profil `ghidra-standard` unter dem Projektpfad `/830a08.7s.68k`** und ist
in jeder Sitzung gestellt: `get_current_program_info` meldet
`language 68000:BE:32:default`, `min_address 0`, `max_address 0x7FFFF`
(524 288 B), **`function_count` 177**, `symbol_count` 853. Der Body von
`FUN_00005ed8` ist **2770 B = 752 Insn** und deckt sich mit der Offline-Messung
(R284). Die **Schreibliste** (160 Vorgaenge) liegt in
`analysis/_m167/_writelist.txt`; der Dreiwlege-Vergleich „Planliste gegen
Ghidra“ in `analysis/_m175/_plan_vs_ghidra.txt` (94 Planlistenkoepfe: 91 als
eigene Ghidra-Funktion, 3 als Einstieg INNERHALB einer Ghidra-Funktion, 0
fehlend).

**Der Import ist damit KEINE offene Frage mehr** (die B167-Batch-Doku fuehrt ihn
noch als „blockiert“; das ist mit dem Import vom 2026-09-26 ueberholt, der
Zustand wurde nie zurueckgenommen). `load_program` bleibt trotzdem gesperrt: das
Programm **wechseln** darf der Worker nicht, das 68K-Programm ist gestellt.

Belegt in
`analysis/port-batch167-68k-import-audio-restfragen-dekompilierplan-2026-09-26.md`
und `analysis/_m167/` (`_image.txt`, `_map.txt`, `_plan.txt`, `_type0.txt`,
`_dispatch.txt`, `_writelist.txt`, `_mnemonics.txt`).

## B168 (2026-09-26) — TYPE_16 steht fest, der Prüfstand läuft, Scheibe 1 ist im Port

**TEIL 1 — die Extraktion führt die 22 Plätze mit Feld `+2 = 0x00` als `TYPE_16`
(16-Bit-Wort, little-endian).** Werkzeug `scripts/m166_audio_extract.py`,
Unterbefehl `types` (Beleg `analysis/_m168/_type16.txt`). Die **LE**-Zuordnung
ist von zwei Seiten belegt: `hornet.cpp:1678` lädt die Sample-ROMs als
`ROM_REGION16_LE`, und MAMEs `TYPE_8LOW` spielt das **niedrige** Byte
(`rf5c400.cpp:253-261`) — was die B166-Schleifenprobe mit 115/142 Siegen im
**ersten** Dateibyte bestätigt. Verteilung: **22 × `0x00` = TYPE_16 (21 mit
gültigem Paar)**, **142 × `0x40` = TYPE_8LOW**, **140 × `0x80` = TYPE_8HIGH**,
**14 × `0xC0` = unbelegt** (keine Nutzdatendatei, nichts geraten). Die einzige
Abweichung gegen B166 ist genau diese eine Zeile (B166 führte sie als `8HIGH`).
**6 Hörproben** (2 je Typ) liegen in `build/audio_extract/listen/`
(gitignoriert, R410), **44 100 Hz fest**; die Pitch-Formel ist daneben
dokumentiert (`step = ((data&0x1fff)<<(data>>13))*4`, Rate = `44100*step/65536`;
Registerwert 0x5000 ⇒ genau 44 100 Hz). Die Spalte „Rate*" des Werkzeugs ist
eine **HYPOTHESE** („Deskriptorfeld `+0` ist Register 0x02") und liefert
4 592–20 500 Hz — plausibel, aber **nicht** belegt.

> **VERMERK (Batch 170, 2026-09-26, Reviewer-Entscheidung):** Die **Voraussetzung
> dieser Spalte ist in B169 widerlegt** — das Deskriptorfeld `+0` ist **nicht**
> RF5C400-Register 0x02 (B169 §1c: `0x5332` in `0x4EB6` schreibt `d7` aus
> `jsr 0x456C`, nie `+0`). Die Spalte „Rate*" in `analysis/_m168/_wav.txt` ist
> damit **ungültig**. Sie wird **nicht verändert** (Belege werden nicht
> zurückgenommen, Projektregel) — dieser Vermerk tritt daneben.

**TEIL 2 — der Referenz-Prüfstand `scripts/m168_68k_ref.py` (TESTORAKEL).**
Er führt den **echten** 68K aus (unicorn 2.1.4, M68K, Kerntyp **M68000**), hakt
RF5C400/K056800 als **Registerdatei** an (nur Protokoll, **keine**
Chip-Emulation) und vergleicht die **Register-Schreibfolge**
`(tick, adresse, wert)`. **Lauf:** Reset → Init → Hauptschleife `0x13EE` nach
**9 981 024 Instruktionen**; der **Boot-Selbsttest bestanden** (ROM-Summe
`025897C7` selbst nachgerechnet), Ring leer, keine Abbruchbedingung.
**Vier Fälle** (Effekt `0x20B`, Jingle `0x101`, loopende BGM `0x115`,
System-SFX `0x001`): **die Gegenprobe ist in allen vier Fällen grün** —
Start/Ende/Schleife aus den Registern 0x00-0x05 stimmen mit dem
Deskriptorpool `0x7A008` überein, und der Typ in Register 0x08 stimmt mit
Feld `+2`. Für `0x101` schreibt der Treiber `0x00` (Poolplatz 90, Feld
`+2 = 0x0000`) — **die `TYPE_16`-Entscheidung ist damit auch von der
LAUFSEITE gedeckt**, nicht nur statisch. Beleg: `analysis/_m168/_ref_probe.txt`.

**TEIL 3 — Scheibe 1 (Daten und Tafeln) ist im Port.**
`port/include/port/audio68k_tables.h`, `port/src/audio68k_tables.cpp`,
`audio68k_check.h/.cpp`, drei Zeilen in `port_selftest.cpp` (Modus `audio68k`,
Modi 79 → 80). Der Lader liest `rom/830a08.7s` (gitignoriert) und wendet die
**R403-Wortumkehr im Lader** an; der Selbsttest hält die gemessenen Sollwerte
(10 Gruppen, 82/54/21/10/19/83/31/9/6/3, 318 Sätze, 317 `MThd`, Pool 303/318,
Typen 22/21/142/140/14) und zwei **FNV-1a-32** (`0x574DBA75` kanonische Tafeln,
`0x744CE84E` Bild). **Fehlt das ROM, meldet der Test FEHLER und rc 2** — kein
stilles OK. **Kein Mixer, keine Wiedergabe, kein MIDI-Abspielen, kein 68K-Kern
im Port.** Das sind die Scheiben 2-6 des Plans (B167 §4.2); die Zuordnung
„Deskriptorfeld `+0` → Register 0x02" und die Tonprobe bleiben offen.

## B169 (2026-09-26) — wer die SMF-Bytes liest, die Orakel-Spur und Scheibe 2 im Port

**DER REVIEWER-BEFUND IST BESTÄTIGT.** Der B167-Plan nannte als Scheibe 2 die
Köpfe `0xE18`, `0x4160`-`0x43D0`, `0x442C`, `0x5746`. Gemessen liest **keiner**
davon ein SMF-Byte (`analysis/_m169/_reads.txt`).

| wer liest | wo | was |
|---|---|---|
| `0x3960` (Körper `0x3ED4`-`0x4158`) | `0x3EE0`-`0x3F70`, `0x40AC`-`0x410A` | `MThd` Byte 0…13, `MTrk`-Chunkkette |
| `0x32B8` | `0x3428`, `0x3444`, `0x3478`, `0x3486`, `0x34A4` | Statusbyte, Running Status, VLQ-Delta |
| `0x2B2A` | `0x2B60`, `0x2B76` | 2 Databytes (Note) |
| `0x2C6C` | `0x2CAE`, `0x2CC4` | 2 Databytes (Control Change) |
| `0x2EF4` | `0x2F30` | 1 Databyte (Program/Aftertouch) |
| `0x2FDC` | `0x315C`, `0x3172`, `0x3234`, `0x324C`, `0x3264`, `0x31A6` | Meta-Typ, **ein** Längenbyte, Tempo 3 Bytes |

**Die Sprungtafel `0x9818`** (16 × u32) verteilt nach dem **Status-Nibbel**:
0…7 → `0x2B22` (Leerlauf), 8/9/A/E → `0x2B2A`, B → `0x2C6C`, C/D → `0x2EF4`,
F → `0x2FDC`.

**Die Mailbox-Befehle 0xF1-0xF6** sind ein Sonderpfad: Byte0 ≥ 0xF0 → Tafel
`0x0F06` **innerhalb `0xE18`** → Stubs `0x0F1E`/`0x0F4A`/`0x0F60`/`0x0F8A`/
`0x0F9E`/`0x0FC8` → `jsr $4160`/`$4262`/`$42A8`/`$4318`/`$436E`/`$43D0`
(Stimmenvergabe). Sie starten **keinen** Klangsatz (`0x3960` läuft nicht).

**Die Orakel-Spur (tickfrei)** greift bei `PC 0x3466` ab und liefert je Ereignis
`(Spur, Delta, Status, Daten1, Daten2)`. Drei Befunde, die den Nachbau erst
richtig machen: die Meta-Länge ist **ein Byte, kein VLQ** (R423); `0xFF 0x51`
liest **genau 3** Bytes; die Reihenfolge ist eine **stabile Mischung nach der
Summenzeit** (R422), nicht spurweise.

**Nicht startbare Sätze (R424):** 34 der 318 haben Satzfeld `+0 == 0` oder
Index = Gruppenzähler. Die B166-Zahlen 98 998 / 40 057 sind **reproduziert**,
zählen aber die unspielbaren mit; spielbar sind **284** mit 98 401 / 40 044.
**ENTSCHEIDUNG (Reviewer, Batch 170, 2026-09-26):** die 34 nicht startbaren
Sätze **warten auf einen Live-Mitschnitt** (nur der kann zeigen, ob der PPC sie
je über die Mailbox sendet) und werden **nicht weiter verfolgt**. Sie werden in
keinem Port-Selbsttest geführt.

**Scheibe 2 im Port:** `port/audio68k_smf.*` + `audio68k_smf_check.*`, Modus
`audio68k-smf`. Selbsttest: **29 Saetze, 29/29 mit dem Einzel-FNV der Orakel-Spur
gleich**, Kette `0x61AFECCA`, BGM `0x115` 6406/1875/1875/64. Fehlt das ROM:
sichtbarer FEHLER (rc 2). **Nicht gebaut:** Control-Change-Wirkung, Meta/SysEx-
Wirkung, Ring-Schreiber (`0x3960`-Block A), Slot-/Stimmenebene (`0x442C`,
`0x5ED8`), Tempo-Umrechnung `0x96E6` — Scheiben 3/4/6.

**Widerlegt:** „Deskriptorfeld `+0` → RF5C400-Register 0x02" (B168 §1.3). Die
Schreibstelle `0x5332` in `0x4EB6` schreibt `d7` aus `jsr 0x456C`; die vier
Probe-IDs liefern `2A30→3000`, `2A30→3000`, `2EE0→3C82`, `271E→1453`.

## Batch 171 (2026-09-26) - Scheibe 3: 3b nativ, 3a Stufe 1 (Verteiler)

**Zuschnitt (B170):** Scheibe 3 = 940 Insn, geteilt an der **RAM-Spur**
(`0x101536`/`0x102646`, je `0x1110` B): **3b QUELLE** 561 Insn (`0x2C6C` +
`0x3960`-Block A) schreibt sie, **3a KONSUMENT** 379 Insn (`0x8B80`, `0x5746`,
acht Nibbelziele) liest sie. Reihenfolge im Auftrag: **3b -> 3a**.

**Stand im Port:** 3b (`audio68k_track.*`) und 3a Stufe 1
(`audio68k_dispatch.*` = `0x5746` + `0x8B80` + Tafeln `0x9B28`/`0x9BA0`) sind
gebaut. Selbsttest `audio68k-track` (Modi 82): **F 29/29, D 29/29, W_E 25/25**;
die vier Schleifensaetze sind **benannt ausgesetzt** (Schnitt hinter der ersten
Wiederholung, +2 Byte gemessen).

**R429 (neu, gemessen):** das **VLQ-Laengenbyte** eines SysEx wird
**uebersprungen** - ROM `F0 0A 41 10 ...`, Spur `F0 41 10 ...`. Wer es
mitkopiert, bekommt je SysEx ein Byte zuviel.

**R428 (B170, im Port belegt):** der Puffer `+0x100C` wird mit dem **Zaehler**
indexiert, nicht mit 0..2. **R427:** `0x8BCE` ist **`bls`** mit dem Register als
zweitem Operanden = **Byte >= 0xF7**.

**Zwei Korrekturen an B170 Paragraph 3.2:** der Weg ">= 0xF7 ausser 0xF7"
(`0x8C82`-`0x8C92`) laeuft **NICHT** ueber `0x8C76` und setzt den Zaehler
**nicht** auf 1; `0x9928` ist **keine 256-Zeiger-Tafel**, sondern **128**
(`0x9928`-`0x9B27`) - 109 der 128 CC-Ziele zeigen auf `0x7124`, das selbst
ausserhalb 3a liegt.

**Grenze zu Scheibe 4 (Reviewer-Entscheidung c, gemessen):** `0x44F2` (38 Insn,
Move-to-Front-Verkettung `0x10EB66`+0/+4), `0x5ED8` (**752 Insn**, Nibbel 9),
`0x72B6` (302 Insn - der **einzige** Schreiber von `Spur+0x110C`; `id = 7` in
allen 411 S-Proben), `0x8884`/`0x8908`/`0x8972`/`0x89AA` (Ziele aus `0x8A26`)
und jeder Chip-Schreibzugriff `0x2000xx`. Sie werden **protokolliert, nicht
nachgebaut**. Fuer 3a Stufe 2 (S und G) laeuft das Orakel deshalb im
**Grenz-Gleichlauf** (`--skip-boundary --init3a`, Belege `_m171/_spur3s*.txt`).

**RAM-Layout 3a (gemessen, `_m171/_layout171.txt`):** `0x10EB62` Kopfzelle,
`0x10EB66` 32 Kanaele a `0x20`, `0x10EF66` Zaehler, `0x10EF74` parallele Tafel
(32 x `0x20`), `0x10375A + id*0x1400` Stimmbloecke (16 Plaetze a `0xC0` ab
`+0x52`, Schluessel `+0x60`), `id <= 8`. Der **Erstinhalt nach dem Boot ist
NICHT null** (Ketten 0..31, Kopf 0x1F) - geschrieben von `0x11A4`/`0x45D6`/
`0x4C1C`/`0x94EE`/`0x8ED8`.

## Batch 172 (2026-09-26) - Orakel-Schnitt repariert (R430), 3a Stufe 2 nativ

**R430 (neu, gemessen - eigener Fehler):** der B170/B171-Schnitt „SCHLEIFE ab
Ereignis n" lag am **ENDE** der ersten Wiederholung (`PC 0x3466`), nicht an
ihrem **Beginn** (`PC 0x341E`). Die Referenz enthielt damit ein Ereignis des
zweiten Durchgangs - in allen vier Schleifensaetzen `0x20B`/`0x702`/`0x705`/
`0x703` **genau +2 Byte** (4 Schreibzugriffe, `W-B` −10). Repariert wird das
**Orakel** (`m171_track3fg.py`: `ev_start_step`), nicht der Port. Danach sind
**alle 29 Saetze** von W_E exakt; die Aussetzung ist gegenstandslos.

**Der Nachlauf bleibt:** in `0x801`/`0x901`/`0x902` hat der Erzeuger am Ende
mehr Bytes angehaengt als der Verbraucher geholt hat (3 bzw. 2). Das ist kein
zweiter Durchgang, sondern der Rest des ersten; F/D/S/G werden ueber die
**gemessene Konsumlaenge** verglichen (Praefix-Vergleich, exakt).

**3a Stufe 2 im Port** (`port/audio68k_dispatch.*`, Modus `audio68k-track`
**erweitert**, Modi bleibt 82): die **acht Nibbelziele** (`0x5E3A`, `0x69AA`,
`0x712C`, `0x7158`, `0x71C0`, `0x7232`, `0x8A26`, `0x8AB0`) und **neun** der
**19 CC-Ziele** aus `0x9928` sind gebaut. Selbsttest: **29/29** in W_E, F, D,
S (Proben), S_V, S_Z, G_Ruf, Chip (=0), offen (=0) und S_T (Tick-Aus).

**Die CC-Tafel `0x9928` (gemessen):** **128** Eintraege (R431); **109** zeigen
auf `0x7124` = `link/unlk/rts` (Leerlauf!), **19** auf eigene Koepfe.
Aufrufer ist immer `0x712C` (`jsr 0x9928[Puffer[1]]`, `Puffer[1]` = `+0x100D`).
Gebaut sind die **neun**, die in den 29 Saetzen laufen und **nur V** schreiben
(210 Insn); die uebrigen zehn (380 Insn) sind Grenze bzw. nie erreicht und
werden **protokolliert**. **Gegenprobe gemessen:** mit `--skip-cc` aendert sich
in 26 von 29 Saetzen **nur `FNV-S_V`** - die CC-Ziele wirken ausschliesslich
auf den Stimmblock.

**Was der Port NICHT vergleicht (gemessen, Gegenprobe `--stub 0x4EB6`):**
`S_T` (Kanaltabelle) und `G_Chip` werden **je Takt** von **`0x4EB6`**
(557 Insn, gerufen aus `0x55A0` am Ende des Verteilers `0x8CAA`) geschrieben -
`0x4EB6` schreibt `T[i]+0x1A` fuer alle 32 Eintraege und **100 %** aller
49 470 Chipzugriffe. Takt ist **Scheibe 6**. Mit diesem einen Kopf abgeschaltet
bleiben S-Proben, S_V, S_Z und G_Ruf in allen 29 Saetzen gleich; nur S_T und
G_Chip aendern sich. `S_T` wird deshalb gegen den Modus **Tick-Aus**
(`--stub 0x4EB6`) geprueft.

**`Spur+0x110C` (Stimmkennung, gemessen):** einziger Schreiber ist das
Grenzziel `0x72B6` (`Puffer[2]` = `Spur+0x100E`, nur wenn `< 0x79`). Im
**Naturlauf** steht dort **7** - das dritte Byte des ersten Kopf-SysEx
`F0 00 07 F7`; im Grenz-Gleichlauf ist `0x72B6` ein `rts` ⇒ die Zelle bleibt
**0**. **UEBERHOLT (B173):** die benannte Grenzeinspeisung `kVoiceIdGrenz = 0`
ist **entfallen** — `0x72B6` ist seit Scheibe 4a gebaut und schreibt die Zelle
selbst (Rohwort `0x72E4`); der Port fuehrt sie **je Spur**
(`Slice3a::voice_id[2]`).

**Grenzrufspur im Grenz-Gleichlauf:** nur `0x5ED8` (77x, aus `0x8C36`) und die
Aufrufe in `0x8A26` nach `0x72B6` (87x) / `0x8884` (39x). **`0x44F2` wird kein
einziges Mal gerufen** - seine Rufstellen haengen alle an `T[i]+0xF == 1`, und
das Scharfbit setzt allein `0x5ED8` (ein `rts`).

**68K-Import (B173-Stand, in B175 ERLEDIGT):** in B173 zum dritten Mal blockiert
- `load_program` ist im MCP-Server nicht vorhanden (`Error: No such tool
available`), ein Versuch, `main.bin` 2087 -> 2087. **Das ist mit dem Import vom
2026-09-26 ueberholt** (Batch 175 TEIL 1a): das Programm liegt jetzt als
`/830a08.7s.68k` im Profil `ghidra-standard`, 177 Funktionen, 524 288 B. Der
68K ist **nicht mehr offline-only**; `load_program` bleibt gesperrt (kein
Programmwechsel durch den Worker). Beleg:
`analysis/_m175/_plan_vs_ghidra.txt`.

## Batch 173 (2026-09-26) - Scheibe 4 gemessen/geteilt, 4a (SysEx-/Kennungspfad) nativ

**Teilung (gemessen, `analysis/_m173/_dyn4a.txt`, `_heads4.txt`):** 4a =
`0x72B6` 302 + `0x8884` 38 + `0x8908` 35 + `0x8972` 18 + `0x89AA` 38 = **431
Insn**. Der **4a-Unterbau** (`0x45D6` 466, `0x7672` 659, `0x7FB4` 80, `0x80AC`
555, `0x8790` 87 + Hilfsziele ≈ 1847) wandert zu **4c**; `0x5ED8` (752) wird
**4c1**, `0x5BEA`+`0x442C` werden **4b**. **`0x44F2` bleibt protokolliert** -
gemessen **0 Eintritte** in den 29 Saetzen.

**R433 (gemessen, eigener Fehler):** die `rts`-Stubs gehoeren **VOR den Boot**.
unicorn (QEMU) haelt uebersetzte Bloecke im Cache; `0x45D6` + 13 Hilfsziele
laufen **im Boot** (je 9x). Nach dem Boot gepatcht bleiben **13** Chipzugriffe
stehen, vor dem Boot gepatcht sind es **0** (`_m173/_r433_cache.txt`).

**Ergebnis 4a:** Selbsttest 12 Zeilen **29/29**; W_E, F, D **unveraendert**
gegenueber dem B172-Grenz-Gleichlauf; `+0x110C` traegt jetzt den **Naturwert 7**
(Spalte `ids` 0 → 7 in allen 29 Saetzen); **G bleibt unveraendert** (der einzige
laufende Tafelzweig `0x7326` findet keinen Kanal, `0x44F2` wird 0x gerufen).

## Batch 174 (2026-09-26) - die Audio-Zeile der Pflicht-Bilanz, 4c1 (`0x5ED8`) nativ

**NUTZERWUNSCH (verbindlich, Queue):** die Pflicht-Bilanz zeigt jetzt **je Ast**
Fortschritt, Rest und Zustand. Der Audio-Ast war bisher gar nicht in der Bilanz.
**NEU im Werkzeug `scripts/m174_audio_plan.py`:** die versionierte **Planliste**
`scripts/m174_audio_plan.csv` (**94 Koepfe**: die 32 JA-Koepfe aus B167 §4.1,
korrigiert um die Befunde B169–B173) und die **Aeste-Uebersicht** (Audio 68K,
PPC-Port, Waehler-Ast, 327er-Pool, Programm-Inventar, GL-Anker, Uebergang
`FUN_8005471C`) mit Zustand, Fortschritt und Rest - Zeilen ohne messbare Groesse
stehen als **„ohne Zahl“**.

**Mechanische Baupruefung (R387):** eine Planlistenzeile mit Status `gebaut`
zaehlt nur, wenn in `port/src/audio68k_*.cpp` die Marke **`68K 0x<ADR>`** steht.
Ohne Marke meldet das Werkzeug einen **Befund** und zaehlt die Zeile **nicht**
als gebaut (39 Befunde vor dem Setzen der Marken, Beleg
`_m174/_planstats_vor_marken.txt`). Zaehlerdefinitionen im Modulkopf:
`gebaut`/`offen`/`protokolliert`/`nicht-portiert-Hall`, Summe = `gesamt`.
**Stand B174: 3056 / 7807 Insn gebaut (40 / 94 Koepfe), 2653 Insn offen.**

**4c1 gemessen (`_m174/_dyn4c1.txt`, `_hull4c1.txt`):** `0x5ED8` (752 Insn, EIN
Kopf) hat in den 29 Saetzen **77 Eintritte**; die Schreibklassen des erreichten
Pfades sind **ausschliesslich `Stapel`** (8178) - **kein** Byte nach T, P, V,
Spur oder Chip. Genau **107 der 752** Instruktionen laufen, **645 nie**.
**Die Auftragserwartung ist WIDERLEGT:** `0x456C`, `0x44F2`, `0x5BEA`, `0x442C`
und `0x8CB8` haben in den 29 Saetzen **0 Eintritte** - die Rufhuelle von `0x5ED8`
ist leer. Deshalb aendern sich **S und G durch 4c1 nicht**.

**4c1 im Port (`port/src/audio68k_dispatch.cpp` + `audio68k_track_check.cpp`):**
`exec_5ed8` bildet die **sieben erreichten** Zweigbereiche Rohwort fuer Rohwort
ab (P1 Prolog, P2 Stimmsplatz-Schleife, P3/P6 Notenlisten ueber `*[0x7A004]`/
`*[0x7A000]`, P4 Kanalsuche, P9 Weiterschalten, P10 Note-Aus). Die **drei nicht
erreichten** (P5/P7/P8 = Stimmaufbau mit `0x442C`/`0x5BEA`/`0x4EB6`) werden bei
Eintritt als **`open`** protokolliert - kein stiller Durchlauf. **Kein 68K-Kern,
kein Chip, kein Takt.** Geprueft wird der **Zweigbereichszaehler je Satz**
(`out.regions`, Sollwert `_m174/_marks4c1.txt`, 10 Eintrittsadressen), **mit
demselben Schnitt** wie die Rufspur (S-Proben-Index): ungeschnitten haette der
Port in 7 der 29 Saetze **einen Ruf mehr** (Nachlauf nach der letzten S-Probe,
gemessen). Sollwert-Tafel `port/src/audio68k_4c1_want.inc`, erzeugt von
`scripts/m174_want4c1.py` aus dem Beleg (nicht von Hand getippt).

**Neue Betriebsart des Orakels:** `m171_track3fg.py --nat4c1` (Grenz-Gleichlauf
4c1: `0x5ED8` samt gemessener Huelle natuerlich, `0x4EB6` = Scheibe 6 und der
4a-Unterbau/4c3 ein `rts`, Stubs **vor** dem Boot).

## Batch 175 (2026-09-26) — Abdeckung von 0x5ED8 in vier Betriebsarten, 4c2 nativ

**DER REVIEWER-BEFUND IST BESTAETIGT UND SCHEIBE 4c2 (`0x45D6` 466 Insn + acht
Helfer = **536 Insn**) STEHT NATIV.** Die 653 nie erreichten Instruktionen von
`0x5ED8` waren eine **Folge der Stubs**: im Grenz-Gleichlauf 4c1 laufen **99**
der 752 Instruktionen, mit `0x45D6` natural **382**. Die neuen 283 sind genau
**P7 (38) + P8 (248)**. `0x7672` aendert dagegen **nichts** (in jeder Zahl
identisch), und **P5/P3/P4 schaltet KEINE Betriebsart frei** (sie brauchen
`Platz+0x63 != 0`, also einen anderen SysEx-Deskriptor).

**Die Regel des Auftrags waehlt damit 4c2** (536 <= "rund 700"). Der neu
erreichbare Zweig P7/P8 (286 Insn) bringt die Summe auf 822 und liegt damit
ueber dem Rahmen — er wird an `0x64CE` **GEKAPPT** (Orakel `bra.w 0x69A2` = der
echte Epilog; ein nacktes `rts` fuehrt GEMESSEN in eine `UC_ERR_EXCEPTION`) und
im Port als `under`-Eintrag **BENANNT** protokolliert. **Gemessen und benannt:**
die Kaplung nimmt genau den Gewinn zurueck (382 -> 99 PCs); der Beitrag von 4c2
in den 29 Saetzen ist der **Zustand** — `FNV-S_V` aendert sich in allen 29
Saetzen — **nicht** die Abdeckung.

**Was `0x45D6` genau tut (CONFIRMED, `analysis/_m175/_dis_45D6.txt`):** es fuellt
den Stimmblock `0x10375A + id*0x1400` — Kopf, 16 Plaetze (Reihenfolge aus der
ROM-Tafel `0x9858`!) und zwei 0x52-Schleifen ausserhalb des S-Fensters. Die
Argumente sind **gemessen** (`scripts/m175_args45d6.py`): p1 = `Spur+0x110C`,
p6 = `Spur+0x1013`, p7 = `Spur+0x1014`, p8 = ein **ROM-Zeiger** aus
`Puffer[9]<<21 | Puffer[10]<<14 | Puffer[11]<<7 | Puffer[12]` (gemessen
`0x1A492`/`0x1B974`). Der **Schalter fuer P7/P8** ist `Block+0x45` (ungattert
geschrieben); der Schalter fuer P3/P4/P5 ist `Platz+0x63`, das nur im
`Deskriptor+0x19 != 0`-Zweig gesetzt wird. Der Port ist **byte-exakt** gegen das
Orakel geprueft (`scripts/m175_vdump.py`: 0 abweichende von 5120 Bytes).

**Zwei eigene Fehler, gemessen und benannt:** (1) die Platzkopien
`0x498A-0x4A44` wurden zuerst **falsch gepaart** (das siebte Paar ist
`Platz+0x66 <- Deskriptor[0x19]`, nicht `[0x1C]`; alle weiteren verschieben sich
um eins) — gefunden mit dem Spiegel-Vergleich, 12 abweichende Bytes.
(2) `scripts/m175_desc8.py` las die Platzgatter zunaechst **ohne** den Versatz
`+0x36`, den `0x4856 lea.l $36(a1),a2` setzt.

**Die Chipzugriffe der gebauten Ziele sind nicht mehr 0:** die 4c2-Helfer
schreiben den RF5C400 (`0x200040`/`0x200056`/`0x200058`/`0x20005C`/`0x20005E`/
`0x200060`/`0x200062`/`0x200064`), in drei Saetzen (`0x122`/`0x123`/`0x124`) je
8 Zugriffe. Der Sollwert des Selbsttests ist jetzt der **gemessene**
(`chip_count`/`chip_fnv`), kein gelockerter Sollwert.

**Neue Betriebsarten des Orakels:** `m171_track3fg.py --nat4c2` (4c1 + die
gebaute 0x45D6-Huelle, P7/P8 gekappt) und `m175_cover.py --mode
{nat,b4c1,b45d6,b7672,port4c2}`.

**Richtigstellung an B174:** die Zahl "107 erreichte PCs / 645 nie" ist **nicht
reproduzierbar** — dasselbe Werkzeug, dieselbe Betriebsart und derselbe Satz
ergeben **99 / 653** (dreimal gemessen). B174 fuehrt ausserdem zwei 29-Satz-
Laeufe, die sich widersprechen. Belastbar ist 99/653.

## REGEL (B176, 2026-09-26, CONFIRMED, GEMESSEN) — RF5C400-PCM ist VORZEICHEN-BETRAG

**Die PCM-Nutzdaten der beiden Sample-ROMs liegen in VORZEICHEN-BETRAG
(sign-magnitude), nicht im Zweierkomplement.** Bit 15 ist das Vorzeichen, die
Bits 0-14 sind der Betrag; `0x8000` ist die "negative Null" = **Stille**.
MAME rechnet sie beim Auslesen um (`rf5c400.cpp:267-270`):

    if ( sample & 0x8000 )        // nach der Typauswahl :250-265
    {
        sample ^= 0x7FFF;
    }

`sample ^= 0x7FFF` bildet `0x8000|m` auf `0xFFFF - m` ab, also auf
`-(m+1)` im Zweierkomplement — die Werte liegen danach symmetrisch um 0.

**Beleg (gemessen, nicht geschlossen):** `analysis/_m176/_wav_mess.txt`. Ohne
die Umwandlung liest man `0x8000` als **-32768**; im 16-Bit-Platz 90 ergibt das
einen **Gleichanteil von -11866 LSB (-8,8 dBFS)**, mit der Umwandlung **+6 LSB
(-74,4 dBFS)**. Alle sechs Hoerproben sind so gemessen (Tabelle in §B176 des
Batch-Dokuments).

**Konsequenz fuer den Mixer und fuer jede spaetere Wiedergabe im Port:** die
Umwandlung gehoert **zwischen** Typauswahl und DAC, **je Ausgabeabtastwert**,
und gilt fuer **alle drei Typen** (TYPE_16, TYPE_8LOW, TYPE_8HIGH) — sie ist
im MAME-Quelltext **nicht** typabhaengig. Der alte Weg ist als Schalter
erhalten (`m166_audio_extract.py wav --sign-mag off`), damit die A/B-Messung
reproduzierbar bleibt.

**Ebenfalls belegt und wichtig fuer spaeter:** die **Abtastrate** einer Stimme
steht in Kanalregister 0x02 (`rf5c400.cpp:550-555`) und ist **gemessen**
(`scripts/m176_rate.py`, 139 der 318 Plaetze; Beleg
`analysis/_m176/_rate_je_platz.txt`). Der B168-Weg "Deskriptorfeld +0 ist
Register 0x02" bleibt **widerlegt** (B169).

## Batch 176 (2026-09-26) — P7/P8 und 4b nativ, Hoerproben repariert

**DIE KAPLUNG IST WEG: der Zweig P7/P8 (`0x64CE`-`0x68F7`, 286 Insn) UND die
Scheibe 4b (`0x442C` 57, `0x5BEA` 189, `0x44F2` 38) LAUFEN NATIV.** `0x5ED8`
erreicht damit **382 statt 99 PCs** (von 752) — der Sollwert des Auftrags
("um 382") trifft genau. Die neuen 283 Instruktionen sind P7 (38) + P8 (248).

**Der Grenz-Gleichlauf heisst `--nat4c1full`** (mit `0x44F2` natural:
`--nat4c1full44f2`). Er ist 4c2 OHNE Kaplung, mit `0x442C`/`0x5BEA`/`0x44F2`
natural; **Tick-Aus** bleibt: `0x4EB6` (Scheibe 6) und **`0x4D90`** (97 Insn,
der Kopf, den IRQ1 `0x1028` bei JEDEM Takt ruft).

**DREI BEFUNDE, DIE DEN SCHNITT ERZWINGEN (alle gemessen):**

1. **Der P10-Rumpf (`0x695C`-`0x6990`) wird erreichbar.** Erst P8 setzt das
   Scharfbit `T[i]+0xF` (Rohwort `0x663A`); gemessen laeuft der Rumpf 45x
   (`0x8CB8` 45 Eintritte, im 4c2-Lauf 0). Er ist deshalb gebaut — sonst
   waere die Zeile "offen" des Selbsttests nicht mehr 0.
2. **`0x4D90` ist der EINZIGE ungebaute Kopf, der den Stimmblock V schreibt**
   (`analysis/_m176/_vwriters.txt`: 7408 Zugriffe in den 29 Saetzen; alle
   anderen V-Schreiber sind `0x45D6` und die sechs gebauten CC-Ziele). Bis
   B175 schrieb er auf Adresse `0x5A` (ROM, wirkungslos), weil `T[i]+0xA` 0
   war; mit gebautem P8 zeigt die Zelle auf einen Stimmplatz. **A/B gemessen:
   mit/ohne den Stub aendert sich NUR `FNV-S_V`** (und damit FNV-S und die
   Kette) — W, W_E, F, D, S-Zahl, G_Ruf und G_Chip bleiben zeichengleich.
3. **`Slice3a` fuehrt EINEN Kettenblock** `0x10EB5E`-`0x10F373` (statt `t`,
   `p` und der Zelle `0x10EF72`): `0x442C` kann mit dem T-Index **32**
   aufgerufen werden (P7 findet nichts, `0x6548 moveq #$20,d0`), und
   `T[32] = 0x10EF66` **ueberlappt** Kettenzaehler, `0x10EF6A`, `0x10EF6E`,
   `0x10EF72` und den ANFANG der parallelen Tafel.

**GEMESSEN (29 Saetze):** `0x442C` 39, `0x5BEA` 39, `0x44F2` **21** Eintritte
(im 4c2-Lauf 0/0/0); das Argument an `0x442C` ist 36x `0x20` und 3x `0`, die
Rueckgabe `d7` **immer 0**; das Byte Stimmplatz+0x70 ist **immer 0x40**.
**Unveraendert bleiben W, W_E, W_V, F und D** (je Satz zeichengleich zum
4c2-Lauf: W 9315 Zugriffe / 27033 B, W_E 3542, F 1764, D 407);
**`FNV-S_T` aendert sich, `FNV-S_V` NICHT** (mit Tick-Aus), `FNV-S_Z` bleibt;
**`G_Ruf` 199 -> 220, `G_Chip` 0 -> 1119**; die Zweigbereiche P7/P8 werden 39;
das Unterbau-Protokoll hat **93 Aufrufe in 28 Saetzen** (die Kaplung `0x64CE`
faellt weg, `0x68DE > 0x4EB6` kommt hinzu).

**A/B `0x44F2` gestubbt gegen natural: KEIN Unterschied** — Abdeckung,
Zweigbereiche, Unterbau-Protokoll und alle Spuren zeichengleich. `0x44F2` ist
deshalb gebaut (21 Eintritte) und wird gegen die `44f2`-Fassung geprueft.

**Die Hoerproben sind repariert (CONFIRMED):** `0x8000` ist im RF5C400-PCM die
"negative Null" = Stille (s. die Regel oben). Ohne die Umwandlung liest man
-32768 und bekommt im Platz 90 einen Gleichanteil von -8,8 dBFS — das war das
"sehr verrauschte" der Nutzerprobe. Mit der Umwandlung: -74,4 dBFS bei allen
sechs Proben (`analysis/_m176/_wav_mess.txt`). Die **Abtastrate** kommt jetzt
aus dem Orakel-Register (`0x3000` -> 22050 Hz fuer Platz 90, `0x0B9C` ->
8000 Hz fuer Platz 0). **Widerlegt** ist die Hypothese "48 dB zu leise / WAV-Kopf
falsch": die MAME-Verschiebung war angewandt (RMS -3,7 bis -6,7 dBFS), und die
Kopfpruefung ist bei allen Dateien OK. **Bestaetigt** ist die Kuerze (0,075-0,23 s
bei den vier 8-Bit-Proben -> je eine `_x8`-Fassung).

## REGEL (B177, 2026-09-26, GEMESSEN) — der TAKT ist eine ZAHL, und der Rundlaufzaehler gehoert zum Startzustand

**CONFIRMED.** Seit B177 ist der Takt im Port nachgebildet (Scheibe 6a:
`0x55A0` Verteilerschluss, `0x4EB6` Chip-Ausgabe je Kanal, `0x456C`
Huellkurve, `0x4D90` IRQ1-Taktkopf). Vier Regeln, die dabei gemessen wurden:

1. **Takt = Zelle `0x100000`.** Der IRQ1-Rumpf (`0x0FFA`) schiebt den Wert der
   Zelle als Argument auf den Stapel (`0x1026`) und stellt sie erst NACH den
   drei Rufen weiter (`0x1042 addq.l #1,(a1)`) — die Taktphase beginnt also mit
   der 0, wenn man die Zelle vorher nullt. Keine Wanduhr.
2. **`0x4EB6` schreibt den Chip UND die parallele Tafel P**
   (`0x10EF74 + idx*0x20`) — jeder Wert geht zweimal raus (wie bei `0x5BEA`).
   Er LIEST den Chip nie. Chipadresse = `0x200800 + idx*0x40`.
3. **`0x4D90` schreibt je nach `takt & 3` in den Stimmplatz (Modi 0/1) oder in
   die Kanaltabelle (Modi 2/3)** — Modi 2/3 schreiben `T[i]+0x18` herunter und
   `T[i]+0x16` hoch; sie beruehren V nicht.
4. **DER RUNDLAUFZAEHLER `0x10EB5A` IST TEIL DES STARTZUSTANDS.** `0x55A0`
   stellt ihn bei JEDEM Takt weiter; nach einem Rumpflauf von `used` Takten
   steht er auf `used mod 32`. Mit 0 statt z. B. 26 beginnt die Taktfolge beim
   FALSCHEN Kanal: die Chip-ZAHL stimmt, `S_V` stimmt, aber `S_T` und die
   Chip-WERTE nicht. `set_init3a` nullt die Zelle — der Rumpf bewegt sie
   danach wieder.
5. **Ein Kanal ohne Stimmplatz hat `T[i]+0xA` = 0.** Dann liest und schreibt
   der Treiber die ROM-Stellen `0x56`/`0x58`/`0x5A`/`0x6D` — der Taktpruefstand
   fuehrt dafuer ein kleines, VERAENDERLICHES Abbild der ersten 256 ROM-Bytes.

**Der Vergleichsgegenstand ist die Chip-Schreibfolge** je Satz, als
`T<takt>:<adresse>:<groesse>:<wert>;` (Takt = Zelle `0x100000`), eingeschraenkt
auf die PCs der Taktkoepfe — in der Taktphase laufen naemlich auch die
Rumpfstufen `0x8B80`/`0x3774`/`0xE18` mit, und `0xE18` ist im Port nicht
gebaut. Dazu `S_T` und `S_V` NACH der Taktfolge. Der Startzustand ist der
Zustand AM SCHNITT der vorhandenen Referenz (Chunk-Lauf), nicht am exakten
`seq_done` (`0x001`: Port `FNV-T 0xA98DF504` == Chunk, exakt waere
`0xC120953B`).

**Der Fehler, der das gekostet hat:** mit `rr0 = 0` waren Chip-Zahl und `S_V`
gruen und `S_T` rot — ein Muster, das nach einem Schreibfehler aussieht, aber
ein STARTZUSTANDSfehler war (Regel 4).

## BEFUND (B177) — P3/P4/P5 sind sehr wohl erreichbar

**CONFIRMED.** Von den **284 startbaren Saetzen** erreichen **18** die drei
Zweige `0x5F58`/`0x5FAC`/`0x6066` von `0x5ED8` (P3 1606, P4/P5 je 145
Eintritte) — **alle in Gruppe `0x01`, Index `0x02`-`0x30`**: `102 103 105 107
108 109 10B 10C 10D 10E 10F 110 111 113 114 12B 12C 130`. Die 29
Vergleichssaetze enthalten keinen davon; die 370 nie erreichten Instruktionen
von `0x5ED8` sind also eine Folge der SATZAUSWAHL, nicht der Stubs. Ein
Testsatz aus Gruppe `0x01` (z. B. `0x102`) macht sie belegbar.