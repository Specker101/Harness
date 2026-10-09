# Port-Gerüst (port/) — Batches 62–88d, Schritte 0/1/2/3/4 + 5A/5B/5C-1/5C-2/5D/5E + 2b-I + Grammatik + Record-Familie + S/T/W/Alpha + Matrix + Textur + Farbe + Audio + Textschicht + Paket-d + Testmode-Zugang + Ranking + NVRAM + Datenschirme + Eingabeschicht (Teil 1) + Analogauswertung + Bedienmaschine + Texteingabe + Grafik-/Ladeteil + 2a-Kern (128, ROM-Spiegel) + Listenkoerper/Sperrsonde/Slot-Aufloesung (129)

## Batch 156: R284 an der Quelle, R376 umgesetzt, Teilbau-Klaerung (2026-09-25)
- **R284 an der DATENQUELLE, fuer die SPANNENLAENGE** (praezisiert): von
  `FUN_8005471C` ist die Inventarspanne `size` **2428 B**, der Rumpf **3344 B**
  (-916 B); die Zelle `insn` ist dabei **LEER** (nicht 607). Korrigiert in
  `m103_close.spans()` (**R222 liest DIESE Tafel**) UND `m105_voter.insn_table()`:
  `max(Inventarspanne, MEASURED_END)`, **nie verkleinern**. Zensus: genau EIN von
  49 Faellen; die R356b-Zerlegung `800688D4` 588-112=476 bleibt unberuehrt.
  Vorhersage VORHER schriftlich, danach gemessen: **alle** 11 Zufuhrwerkzeuge
  byteidentisch (Vergleich ueber `analysis/_archiv/`), `R222` kippt auf `ja`.
- **R376 umgesetzt:** `m104_built.py nachzuegler` schreibt seinen Beleg selbst
  (`EV.write`, quiet; `m144_outguard.TOOLS` 49 -> 50), Konsolentext byteidentisch.
- **R378: EIN TEILWEISE GEBAUTER KOPF IST NICHT ABBILDAR.** Ein Kopf hat **EIN**
  gemessenes Ende (`MEASURED_END`/`RANGES`), die Bau-Menge ist **mengenbasiert**.
  Probe mit Teilende `80054B9C`: R222 `NEIN, +1276 B`, Stranghuelle **305 -> 134
  Knoten**, `GAP 0 -> 7`, **548 Insn fallen STILL heraus**, `sanity` blind,
  P100 statisch. **Fortschritt an einem Dok-Kopf (R216-C) laeuft ueber NAeHTE**
  (B150/B152: Ziel direkt fahren, Hook 0, Kopf gefahren 1, Anker bewusst
  umbauen) - eine "Scheibe" ist eine **Nahtliste**, kein Adressbereich.
  `mission5_step` (= FUN_8005471C) hat schon 5 verdrahtete Stellen
  (`0x80054804`, `0x80054EB4`, `0x80055414`).
- **R379:** dieselbe Groesse an zwei Stellen gerechnet = zweimal pruefen
  (`m130_ast span` las `a + size`, `m130_ast hull` `naechster Kopf - Adresse`).
- **Blockade benannt (B156 baut nichts):** die drei (a)-Zeilen
  `80068A78 -> 8000F1E0` / `80068B50/68 -> 8000FE78` sind **OpMode-Methoden**
  (klassengebunden); `FlowHooks` hat **kein** OpMode-Feld, `lzss::Runtime::opmode`
  setzt nur der Pruefstand -> bleiben GEZAEHLT (R215). Wirt-Muster:
  `slot_show.cpp` `h.pool_rect`.
- **R380 (eigener Fund, VORBESTEHEND): die GL-Referenz ist NICHT reproduzierbar.**
  `analysis/_gl_ref_hashes.txt` fordert fuer `glsetup` stdout `6f6aea5c…`, aber
  jede Lauf-Fassung liefert `aa5610e5…` (6x `glsetup`, 4x `glcolor`, alle
  `GALLIUM_*`-Varianten LEER/DRIVER/VEC128/CAPS_sse2/CAPS_sse4.1/CAPS_nosse,
  LF/CRLF/PPM-Pfad-Formen) - **und B155s eigener Beleg**
  `analysis/_m155/_glsetup_probe.txt` liefert denselben Wert wie heute. Die
  **`.ppm`-Hashes stimmen 9/9**. Folge: `REG GL-Referenz 0/9` +
  `REG regression 9 Fehler` (= genau diese neun), `REG GL-Anker` **9/9 OK**.
  **Nicht blind neu stempeln** (Ursache offen; B155 §1d widerspricht: dort war
  `+CAPS` 9/9 anders, heute `LEER == +CAPS`). Vorschlag: Matrix mit der finalen
  Fassung neu messen, dann bewusst neu schreiben - oder Vergleich auf `.ppm`
  stuetzen (R375).



## Batch 155: GL-Umgebung festgeschrieben + Laufprotokoll aus Git (2026-09-25)
- **Test-GL ist Mesa/llvmpipe auf ALLEN Rechnern** (R373): `scripts/setup_mesa.ps1`
  (festes Archiv `mesa3d-26.2.1-release-mingw.7z`, SHA-256 im Skript, idempotent,
  `-Check`/`-Force`, Werkzeugordner `%LOCALAPPDATA%\ss_tools`) legt
  `opengl32.dll` + `libgallium_wgl.dll` nach `port/build/` (gitignoriert,
  je RDP-Rechner einmal).
- Der Harness (`GL_ENV_PIN`) setzt fuer JEDEN GL-Lauf `GALLIUM_DRIVER=llvmpipe`,
  `LP_NATIVE_VECTOR_WIDTH=128`, `GALLIUM_OVERRIDE_CPU_CAPS=sse2` und prueft
  `GL_RENDERER` VOR den Faellen; falscher Renderer, fehlendes Binaer oder
  stehende Vorpruefung (15 s ohne CPU-Zeit, R372) → alle 9 Faelle
  `GL-UMGEBUNG` = FEHLER, **kein Einzellauf**; je Fall 30 s Stillstand + 60 s hart.
  GEMESSEN: die CPU-Caps-Variable ist die tragende (9/9 Ausgaben anders, die
  `.ppm`-Bilder ueber alle Varianten gleich); LP_VECTOR_WIDTH: 128 ↔ 256 Bits.
- `analysis/_gl_ref_hashes.txt` ist die **versionierte** Referenz (SHA-256 je
  Modus + PPM, erzeugt nur mit `--write-gl-ref`); der Harness vergleicht bei
  jedem Lauf → eigenes Urteil `REG GL-Referenz`.
- **Laufprotokoll bleibt aus Git** (R375): 13 `*_regression_anker.csv` + neun
  GL-`.ppm` per `git rm --cached` + `.gitignore`; die eingefrorenen `.png` sind
  die Referenzbilder.
- **Batch-Ende (R374):** GENAU EIN `preflight.py before *> datei.txt`, danach
  `m149_bilanz.py --batch N --from-preflight datei --write-anchor` (gleicher HEAD,
  Datei juenger als port/+scripts/+Makefile, sonst Abbruch; danach nichts mehr
  unter `scripts/` aendern). Fallstrick (R377): den Uebernahme-Pfad VORHER mit
  einer frisch gestempelten Kopie probefahren.
- Fallstrick: `*>` schreibt in PowerShell 5.1 **UTF-16LE**; ein getrackter Beleg,
  den KEIN Werkzeug schreibt, veraltet still (R376, `_m104_nachzuegler.txt`).


## Batch 143: die LZSS-Naht `8002AEBC` mit dem ROM-Alias als Wirt (2026-09-24)
- **Ein Kopf / 22 GEMESSENE Insn** in `port/voter_leaves2.{h,cpp}`:
  `aebc_unpack(ram, Vl2AuxHost{core2, alias, opmode}, window, key, heap)`
  = `list_find8(Fenster, Schluessel)` + `lzss_block(Satz+12, *(Satz+8), Ziel)`.
  Modul jetzt **43 Koepfe / 1564 Worte / 6256 B**, FNV-1a **`2A55E5B8`**;
  Anker (230) 2/2, (231) 122/122, (232) 44/44, (233) 44/44;
  Regression **32 + 260, 0 Fehler** (+ `vleaf-b143-anker`).
- **DER WIRT IST DER ROM-ALIAS** (`port/rom_alias.h`): das erste Argument ist
  das **LZSS-Fenster `0xFF1C2000`** (R293, ausserhalb des Abbilds). Ohne
  Spiegel fasst der Kopf **keinen** Speicher an (R215: Ausgang "kein Eintrag",
  Rueckgabe `Fenster - 8`) - deshalb bleiben die Faelle 101..121 unveraendert.
- **DAS FENSTER IST EINE DATENQUELLE (gemessen, `scripts/m143_window.py`):**
  13 Eintraege `st11`..`st10` ab 0x1C2000 (8-B-Liste: `+0` Name-Offset, `+4`
  Container-Offset, Ende = Name-Offset 0); Container-Signatur `0x4C5A2000`,
  `+8` = entpackte Laenge, `+12` = Tokenstrom. Eintrag 0 = Container
  `0x1C20B0`, **9548 B**, FNV-1a **`B934C1B0`**, Kopfwoerter
  `0x14/0x580/0x790/0x1264/0x8A` = die vier Blockzeiger + Zahl, die
  `c168_step` danach liest. Deckung **0x9086** -> 0x10000 B Spiegel genuegen.
- **R352:** `AliasMirror.base` gehoert zu `kAliasLo` (0xFF1C0000), das Fenster
  liegt `+0x2000` - Fenster-Offsets brauchen den Fensteranfang (erster Fehler:
  Signatur `4FC8484F` statt `4C5A2000`). **R353:** Teilspiegel nur mit
  gemessener Deckung. **R354:** Stub in gebautem Code nur mit belegter
  Gleichheit + Anker fuer den echten Pfad + bit-gleicher `expect.inc`.
- **R222 fuenfte Auspraegung (CONFIRMED):** die Inventarspanne ist keine
  Rumpflaenge - `8005C820` ist **202** Insn (nicht 269; `bclr` @8005CB44, dort
  beginnt der VERDECKTE Kopf `8005CB48` = 67 Insn, der `80060DC4`/`8005C318`/
  `8005C168` ruft); `80060DC4` ist **209** Insn (nicht 221) + verdeckter
  Nachbar `8006110C` (11 Insn). Naechster Schnitt: **275 (1a) + 220 (1b)**.
- **Eigene Fehler:** zwei Koordinatensysteme verwechselt (R352), Spalten des
  eigenen Werkzeugs verwechselt (`list` = absolute Adresse, `cover` = roher
  Offset), B142-Belege durch feste Werkzeug-Dateinamen ueberschrieben (R334).

## Batch 141: die Szene-Satzkette `8005C408`/`8005C168` (2026-09-24)
- **Zwei Koepfe / 323 GEMESSENE Insn** in `port/voter_leaves2.{h,cpp}`: `c408_step`
  (`8005C408`, 215 Insn, der Bauer: je 32-B-Eintrag ein 120-B-Satz, je 14-B-Eintrag ein
  92-B-Satz) und `c168_step` (`8005C168`, 108 Insn, der Aufbau: LZSS-Naht `8002AEBC` mit
  dem Fenster `0xFF1C2000`, vier Blockzeiger IN PLACE um `+0x803C0000`, Satz bauen,
  `*[SDA(0x330)] = Satz`). Modul jetzt **35 Koepfe / 1351 Worte / 5404 B**, FNV-1a
  **`EFE73A6E`**, **109 Faelle** (101..108 neu); Anker (230) 2/2, (231) 109/109,
  (232) 40/40, (233) 39/39; Regression **32 + 259, 0 Fehler**.
- **R147:** die EINZIGE Rufstelle `0x8005C2DC` liegt IM Rumpf des gebauten Aufbaus
  (`c408_step` zaehlt im R216-A-Anker **2** - einmal direkt, einmal aus dem Aufbau);
  die vier Aufbau-Rufstellen (`8005CC3C/CC78/CCB8/CD98`) liegen im UNGEBAUTEN `8005CCCC`.
- **Acht Nahtziele GEZAEHLT (R215, 464 Insn):** `8005248C` 11, `800523E0` 43,
  `8005C7AC` 29, `8005C764` 18, `8005C820` 269 (liest `15(r3)` = den 92-B-Satz ->
  `nargs` 3!), `8002AEBC` 22, `8005D3B0` 36, `8005C330` 36 (**bedingter Tail**
  `bcl 4,4` @8005C2F0). **Wirkung fehlt** - gefroren sind Ruf, Zahl und Argumente.
- **Feste Konstanten (R293):** der Hilfsblock `0x803C0000` (12 `addis`-Stellen im Aufbau,
  fuenf Woerter: vier Zeiger + Anzahl) und `lis r3,-228` @8005C17C = `0xFF1C0000`
  (+`addic 0x2000` = das LZSS-Fenster `0xFF1C2000`).
- **Sandkasten der Faelle 101..108:** Daten bei `kSb+0x1DA00..0x1ED00`
  (`kSbLoadOff`/`kSbLoadBytes`) - **NICHT** bei `0x1B000`: die Trigonometrietafel endet
  bei `kSbTrigTb + 0x8000` = `kSb+0x1C000` (R347).
- **Eigene Fehler (sechs):** R347 (Tafel-Ueberlappung, Fall 72/73), R348 (Nibble),
  R349 (`nargs` 2 statt 3), Rahmenpuffer-Adresse als feste Adresse verglichen,
  `return 0` statt Registerrest (Fall 107), Registry-Verlust durch `git checkout` (R346).
- **Naechster Schnitt:** die acht Naehte einzeln (`8005C820` 269 zuerst);
  `FUN_8007D968` (74 Insn) ist **nicht** gebaut (Huelle nicht geschlossen: 87 Knoten /
  offen 40 / Aussenkontakt 28 / GAP 12).

## Batch 138: die drei Koepfe `8004601C`/`80047DDC`/`80059EA4` (2026-09-24)
- **Drei Koepfe / 117 GEMESSENE Insn** in `port/voter_leaves2.{h,cpp}`:
  `result_step` (11, `hud_labels` + `[SDA(0x640)]` nullen, Rueckgabe = die
  ZELLADRESSE), `msg_index` (16, Suche `s16([SDA(0x62C)]+2)` in DREI Halbworten
  ab `[SDA(0x630)]`, Rueckgabe 0/1/2/3), `slot_state_step` (90, vier
  Zustandswege `v = s8(slot+1)` ueber sechs GEBAUTE Koepfe). Modul jetzt
  **32 Koepfe / 903 Worte / 3612 B**, FNV-1a `0A0682B4`, **90 Faelle**;
  Anker (230) 2/2, (231) 90/90, (232) 31/31, (233) 38/38; Regression
  **32 + 258, 0 Fehler** (+ `vleaf-b138-anker`).
- **R147 an FUENF Stellen geschlossen:** `80046028` (im neuen Kopf), die zwei
  Haken `0x8003E224`/`0x8003E380` (`game_flow.cpp` -> `result_step`), die
  inneren `0x80059EEC` (`msg_index`) und `80059F4C` (`scene_switch(1,4)`).
  **Naht:** `voter::core_site` kennt jetzt `0x80059F84` (core2-Anker 5/5).
- **Neue Zelle** `leaves2::kSdaMsgList = 0x630` (DREIERliste); am Bild gemessen
  (`capture/m31_ram4mb.bin`): `[SDA(0x630)] = 0x800AB0D0` mit 0000/0080/00FF…
  (R324-Klasse: fehlt sie im Anker, findet die Suche NIE etwas).
- **R161:** `std_numbers` ist `void` -> `kStdNumbersRest = 1` + `residue`.
- **Vorprobe-Werkzeug** `scripts/m138_int.py` (`probe` 21 Faelle / `dis`).
  Befund: **keine** Interpreter-Erweiterung noetig (`cmp` X-Form war da);
  **`stbx`** (op 31 XO 215) fehlt im Interpreter (benannt, gestubbt).
- **R333 fest:** `80046028` in `FUN_8004601C` (jetzt gebaut), `8007D9B8` in
  `FUN_8007D968` (296 Insn, offen) - B136s „ausserhalb jedes Inventarkopfes“
  war falsch.
- **Eigene Fehler:** R335 (Fallschalter = `HEADS`-Index; 5 Faelle gegen den
  falschen Kopf), R336 (Zeitgeber in der falschen Wort-Haelfte), R339 (M0-Tafel
  statt Missionszellen `0x254`/`0x258`), geratene Rufstellenzahl 1 (gemessen 5),
  Kettensummen (`hud_labels`/`msg_index` je 2), vier fehlende
  `flow::`-Qualifizierungen.
- Zahlen (2026-09-24): R207 **580** (29/0/0), `nachzuegler` 77/31 (3/2);
  R216 **A 233 / B 84 / C 86 / D 659-129**; Waehler-Gruppe **92/5**;
  (A) 128 Knoten/107-21; (B) 332/294-38 (1313 Insn + 64 B); Pool 105/327;
  Inventar S1 **1650**/Rest 424; Modi 78; Ghidra unbenutzt.
- **Naechste Ziele:** `FUN_8007D968` (296, letzte R147-Stelle `8007D9B8`);
  die vier offenen `msg_index`-Rufstellen (`FUN_800474C8`, `FUN_80047E38` x2,
  `FUN_800535B4`); dann `800535B4` (125), `8005C408` (215), `8005C168` (108).


## Batch 137: `scripts/preflight.py` (Sammel-Pruefer) + R330 (2026-09-24)
- **`scripts/preflight.py` (NEU, STANDARDWEG ab jetzt):** Vorflug/Nachflug in EINEM
  Aufruf - `python scripts/preflight.py before` bzw. `after <hex>...`.
  **Implementiert KEINE Prueflogik**: importiert `m104_built`/`m115_pass`/`m116_pass`/
  `m114_pass`/`m130_ast`/`port_regression` und ruft deren Funktionen
  (`cmd_tails|check|sanity|nachzuegler`, `cmd_abi|impl|doc`, `doc4`, `cmd_p100`,
  `cmd_span`, `main`); Zahlen aus deren Ausgabe. Exit 0 = sauber, 2 = Befunde.
  Belege werden vorher nach `analysis/_pf_prev/` gesichert, `--raw` -> `_pf_raw/`.
  Verifiziert gegen die Altmethode (identische Werte in beiden Modi); Laufzeit 7,5 s.
- **R330 (CONFIRMED):** `m115_pass.abi_map()` loest den **Kurznamen** auf ->
  B136s zweites `kFnViewSet` (0x80048A74) verdraengt die aeltere Adresse
  **0x800432C0** (`voter_msg.cpp:584`) -> **R216-A +7 statt +8; die B135-Zahl 223
  war RICHTIG** (richtig waere 231). 6 mehrdeutige Namen unter den reg.add-Namen:
  `kClip kFnCommit kFnDispatch kFnRecInit kFnSlotLoop kFnViewSet`. Der Defekt ist in
  `cmd_abi` als Warnblock sichtbar gemacht; die Zahl bleibt **ungeglaettet** (ein
  include-genauer Aufloeser ergibt 234). Werkzeug: `scripts/m137_r330.py probe`.
- **B136s "ausserhalb jedes Inventarkopfes" ist WIDERLEGT:** `80046028` liegt in
  **`FUN_8004601C`** (11 Insn, BAU-Huelle 2 Knoten/offen 1, ruft nur `hud_labels`;
  zwei gezaehlte Haken `kFnResult4` in `game_flow.cpp:1191/1270`) und `8007D9B8` in
  **`FUN_8007D968`** (296 Insn). Beleg: `m130_ast.py sites` -> `innerhalb(FUN_...)`.
- **Gebaut wurde in B137 NICHTS**; vermessen UND zerlegt sind `FUN_80059EA4` (90 Insn,
  BAU-Huelle 8 Knoten/offen 2, enthaelt die R147-Stelle `80059F4C` = `scene_switch(1,4)`)
  und `FUN_80047DDC` (16 Insn, Dreierlisten-Index) - Bauplan in
  `analysis/port-batch137-preflight-r330-2026-09-24.md` §5.
- Zahlen (2026-09-24): R207 **577 (29/0/0)**, `check`/`sanity` 0, `nachzuegler`
  76/30 (3/2); R216 **A 230 / B 84 / C 86 / D 656-129**; Regression **32 + 257, 0 Fehler**;
  Waehler-Gruppe **91/6**; Huelle (A) 131 Knoten/108-23; (B) 292/40 (1419 Insn + 64 B);
  Pool 105/327; Inventar S1 **1649**/Rest 424; Modi 78.
- **R334** Blockgrenzen mit `(?m)^== ` verankern (nicht auf `"== "` trennen - die Zeile
  `Spanne == Rumpf: ja` zerschneidet sich selbst). Nie stdout auf die Ausgabedatei
  eines Werkzeugs umleiten (`Set-Content` ueberschrieb `_m130_hulls.txt`).


## Batch 136: die vier Ziele `80045F64`/`8002A028`/`80038030`/`80048A74` + ihre vier Unterbauknoten (2026-09-24)
- **Acht Koepfe / 292 GEMESSENE Insn** in `port/voter_leaves2.{h,cpp}`:
  `hud_labels` (`80045F64`, 46), `scene_switch` (`8002A028`, 52),
  `scene_copy` (`800298F8`, 21), `ctx_store` (`8002994C`, 3),
  `slot_renew` (`80038030`, 20), `record_build` (`80032828`, 60),
  `view_set` (`80048A74`, 18), `view_project` (`8003C354`, 72). Modul jetzt
  **29 Koepfe / 786 Worte / 3144 B**, FNV-1a **`0C632796`**, **74 Faelle**;
  Anker (230) 2/2, (231) 74/74, (232) 25/25, (233) 34/34, `vleaf-b136-anker`
  16/16; Regression **32 + 257, 0 Fehler**.
- **Muster (neu):** jedes Ziel bringt **genau seinen** offenen Unterbauknoten
  mit -> vier Ziele = acht Koepfe. `80045F64` hat die groesste Huelle
  (24 Knoten), aber nur 2 offen (Ziel + Trampolin `8000005C`).
- **R147 an SECHS Stellen:** `0x8005A6C4` -> `slot_renew`, `0x8005A9AC` ->
  `scene_switch`, `0x8005AA9C` -> `view_set`, `0x8005ABBC` + `0x80054C1C` ->
  `hud_labels`, `0x8003E154` (`game_flow.cpp`) -> `scene_switch`.
  **Drei offen (benannt):** `80059F4C` (in der offenen `FUN_80059EA4`) und
  `80046028`/`8007D9B8` (**ausserhalb jedes Inventarkopfes**, "kein Kopf").
- **R327 (eigener Fehler, vom WORTINTERPRETER gefunden):** `lwzu`/`stwu`
  **inkrementieren VOR** dem Zugriff - `scene_copy` liest `src + 0x298`, nicht
  `+0x294`; der erste Bau verschob **alle sechs Woerter um eins** (still).
- **R326 (Werkzeug zuerst, R219):** neue Ruempfe brauchen im Interpreter
  **CA-Feld** (Carry) + `addze` (XO 202), `mullw` (235), `divw` (491),
  `extsh` (922), `sthu` (Op 45), `subfic` (Op 8). Semantik **gegen MAME**
  `mame/mame/src/devices/cpu/powerpc/ppcdrc.cpp` geprueft.
- **Namensraum-Falle:** `namespace port { namespace text { class TextLayer; } }`
  erzeugt einen **zweiten unvollstaendigen Typ** (Fehlerbild "incomplete type"
  in einer fremden Datei). `TextLayer` lebt in **`port`**, nicht `port::text`.
- **R215:** `80045F64` ist das einzige der acht mit WIRT-Bedarf (Textschicht +
  Anzeigeschalter); ohne Wirte **zaehlen** (`Vl2Stats::wire_missing`).
  Rueckgabe `kHudColB` (0x2E), wenn die Phase-0-Zeile nicht laeuft (R161).
- **R187:** `scene_switch` liest die vier Satz-Zeiger **mit** Schranken
  (ROM hat keine) -> `PortFault read32 ausserhalb RAM @ 0x80D62430` war der
  Beweis; `s.guard++` zaehlt.
- **Zahlen:** R207 rueckwaerts **577** (29/0/0), `check` 0, `sanity` 0,
  `nachzuegler` 76/30 (3/2); R216 A **230**, B **84**, C **86**, D **656/129**
  (**A +7 statt +8 = offene Messnotiz**, nicht geglaettet: jede neue Adresse
  steht genau einmal in der `abi`-Liste, `voter_leaves2.cpp` traegt 29 = 21+8,
  keine Adresse verloren); Waehler-Gruppe **91/6**; Huelle (A) **131 Knoten /
  108/23**; VOLLE Huelle (B) **292/40** (offen 1419 Insn + 64 B size-nur),
  Unterbau offen (B) **34/1146** / (A) **17/681**; Strang A/B unveraendert;
  Platte `B129_PLATE` **0/6**; Pool **105/327**; Inventar (R308, 2026-09-24)
  S1 **1648** / Rest 424; Modi **78**; Ghidra **unbenutzt**.
- **Beleg-Falle (wieder):** `m130_ast.py`/`m130_ref.py` schreiben **feste**
  Dateinamen -> die B130/B133/B135-Belege in `analysis/_m130_*.txt` sind
  **ueberschrieben** (falscher Kommentar `_m136_*.txt` in `voter_leaves2.h`
  korrigiert). Vor jedem Lauf Altbelege wegsichern.
- **Naechste Ziele:** groesster offener Knoten `8005C408` (215), `800535B4`
  (125), `8005C168` (108), `80059EA4` (90, Ziel), `80010A20` (68),
  `80062124` (62), `8000F7E4` (60); `FUN_8005471C` bleibt Hintergrundstrang.

## Batch 135: der R317-Systemscan + Waehler-Ziele 18/19 + Unterbau `8003C17C` (2026-09-24)
- **DER R317-SYSTEMSCAN IST GEFAHREN UND SAUBER** (`scripts/m135_r317.py`,
  6 Ordnungen ueber 4727 Store-Aufrufe in `port/src`+`port/include`: **0 neue
  Fundstellen**) + unabhaengige ROM-Breiten-Gegenprobe
  (`scripts/m135_storewidth.py`; D-/X-Form gegen `mame/mame/src/devices/cpu/
  powerpc/ppcfe.cpp` geprueft: 0x24 STW, 0x2C STH, XO 407 sthx -> **575 passend,
  2 erklaerte Scheintreffer**). Die R315/R317-Klasse ist damit im GEBAUTEN Port
  **geschlossen** - nicht nur zufaellige Einzelfunde.
- **Drei Koepfe / 112 GEMESSENE Insn** in `port/voter_leaves2.{h,cpp}`:
  `rec_index_step` (`8005A500`, 41), `phase_pair_gate` (`8005A17C`, 47),
  `rel_matrix` (`8003C17C`, 24). Modul jetzt **21 Koepfe / 494 Worte / 1976 B**,
  FNV-1a **`7112BEB7`**, **63 Faelle**; Anker (230) 2/2, (231) 63/63,
  (232) 25/25, (233) 29/29; Regression **32 + 256, 0 Fehler**.
- **R147 an FUENF Stellen:** `0x8005AF08`/`0x8005AF10`/`0x8005AF00`/
  `0x8005ACF4` (im GEBAUTEN M0-Waehler) + `0x8003B530` in
  `mission::event_value` -> `rel_matrix`; damit ist die **sechste Rufstelle
  `0x8005A1C4`** des B134-Blocks geschlossen. **R194:** `mission34_check`,
  `mission2_family_check`, `voter_block_check` mitgezogen (die alten Wire-Werte
  bleiben ueber die analytische Q14-Identitaet erhalten).
- **Signatur nachgezogen:** `mission::event_value` gibt jetzt `u32` (das ROM
  laesst `r3` am Rumpfende stehen = Rueckgabe des Wire-Rufs `0x8003C6F0`).
- **Neue Regeln:** **R322** `extsb`/`extsh` sind die AUSNAHME der X-Form -
  **Ziel = rA (Bits 11..15), Quelle = rS (Bits 6..10)**; der Wortinterpreter
  `m130_ref.py` hatte vertauscht (seit B130 still, weil `rX,rX` es verdeckt;
  `extsb. r0,r3` deckte es auf; B133-Faelle 33/36..39 neu gerechnet, XOR-Form
  XO 954 braucht `cr_cmp(0, ra, 0)`). **R323** `lhau` (Op 43) fehlte.
  **R324** `[SDA(0x5D0)]` (16-Halbwort-Tafel von `FUN_8004C588`,
  `kSbTab5D0 = SB+0x0F00`) muss im Anker installiert sein, sonst schreiben die
  Raender auf 0x00..0x1E (= LR-Rettungsplatz -> "ROM-Adresse ausserhalb").
  **R325** (Fund in fremdem, GEBAUTEM Code) `fill_gap_words` (`voter_block.cpp`)
  laeuft fuer **`0 <= idx < 4`** (`bclr 12,0,0` bei idx<0, `bclr 4,4,0` bei
  NOT CR1.LT), NICHT `idx == 4` -> `kGapSink` -> `kGapLimit`, Anker (5) angepasst.
  **R162** erneut getroffen: `0x60000981` ist `ori r0,r0,0x981` (kein `nop`);
  Reihenfolge `stage_scan(...)` DANN `obj+8 |= 0x981`.
- **Zahlen:** R207 rueckwaerts **569** (29/0/0), `check` 569/0, `sanity` 0,
  `nachzuegler` 76/30 (3/2); R216 EINZELN A **223**, B **84**, C **86**,
  D **648/129**; Waehler-Gruppe **87/10**; Huelle (A) **141 Knoten, 110/31**;
  volle Huelle (B) **332 Knoten, 284/48** (offen 1711 Insn + 64 B size-nur);
  Pool **105/327**; Inventar (R308, 2026-09-24) S1 **1648** / Rest 424;
  Modi **78**; Ghidra **2085** (in diesem Batch NICHT benutzt).
- **Naechste Ziele (gemessen, nicht gebaut):** `80045F64` 2/51, `8002A028` 3/76,
  `80038030` 2/80, `80048A74` 2/90 (enth. offen `8003C354` 72); `8005A320`
  24/1131, `8005CC94` 23/1115. `FUN_8005471C` bleibt Hintergrundstrang
  (22 offene Randknoten: `8005C408` 215, `8005C820` 269, `800688D4` 147, ...).
- **Werkzeuge NEU:** `scripts/m135_r317.py` (Modi `scan|narrow|w32|w32narrow|
  w32ident|localflow|localflow2|castflow|fieldflow|retflow`), `scripts/
  m135_storewidth.py` (`calib|check|strict`).


## Batch 132: das dreizehnte Waehler-Ziel + der inkrementelle Bau (2026-09-23)
- **BAU AB JETZT: `make -j16`** (Makefile im Projektroot, `mingw32-make` 4.4.1,
  R310). Clean 13,7 s / 0 Fehler+Warnungen; inkrementell nach 1 Datei 1,06 s;
  Header-Probe 78/78 TUs in 7,73 s (`-MMD -MP`). `scripts/port_build.ps1 -Port`
  ruft `make`; PoC und `-Gl` bleiben unveraendert (PORT_RENDER_GL steht auch in
  port_selftest.cpp -> GL-Objekte nicht teilbar).
- **Zwei Windows-Fallstricke (stehen als Kommentar im Makefile):** (a) ohne
  Metazeichen startet make die Rezeptzeile DIREKT ohne Shell -> `SHELL`
  festnageln UND `msys64/usr/bin` vorne in den PATH des Rezepts; (b) in einem
  SKRIPT expandiert PS 5.1 die Variable in einem `-`-Token nicht
  (`& $make -j$jobs` -> `$jopt = "-j" + $jobs`).
- **14. Kopf `80059D08`** (29 Insn, M0-Typ-4-Fahne) in `voter_leaves2.{h,cpp}`:
  `flag_slot_200(ram, slot, st)`; `w = *(u32*)(slot+0x40)` (`mission::kSlotFlags`),
  `blk = [SDA(0x234)]`, Zaehler `+0x6A4`, `s16 +0x6FA`; setzt `w | 0x200` und
  ruft nur bei `s16 == 0` `mission::counter_scale(ram, 10, 0)` (GEBAUT, R148).
  **Rueckgabe NICHT konstant** (Zellwert / s16 / Fahnenwort).
  Dateien: `voter_leaves2_words.inc` (**212 Worte / 848 B**, FNV-1a `2F00BAD1`),
  `voter_leaves2_expect.inc` (33 Faelle); Anker (230) 2/2, (231) 33/33,
  (232) 10/10, (233) 13/13; Regression **32 + 253**.
- **R147 gelungen:** die einzige Rufstelle `0x8005A7E0` liegt im GEBAUTEN
  `FUN_8005A5A4` (mission_script.cpp, M0-T1-Fall "Typ 4"); `r3` = durchgereichter
  Slot (der T1-Verteiler 0x8005A710..38 schreibt r3 nicht an).
- **R311:** die logische D-Form ist `rS` = QUELLE (MSB 6..10), `rA` = ZIEL
  (MSB 11..15) - der Wortinterpreter `m130_ref.py` hatte sie vertauscht (nur
  sichtbar, wenn die Register verschieden sind; `rX,rX` verdeckt es). Dazu
  fehlten `stmw`/`lmw` (Opcode 47/46).
- **R312:** `mtcrf` allgemein - CRM-Bit `2^k` -> `CR(7-k)`, Nibble = LSB-Bits
  `4k..4k+3` (CRM 0x04 -> CR5, CR5.EQ = Wort-Bit 0x200).
- **R313:** R187 gilt auch fuer ABGELEITETE Basen; `mission_flow::counter_scale`
  las `ctx+0x12` ungeprueft (`read8 @ 0x12`) - Schranke ergaenzt.
- **Zahlen:** Waehler-Gruppe 81/16, Huelle (A) 108/37, (B) 278/54 (offen
  1711 Insn + 1096 B size-only), Unterbau 38/1302, R207 563 (29/0/0),
  R216 A 216 / B 83 / C 85, Modi 78, Pool 105/327 (R307), Inventar S1 1648.


## Batch 129: die zwei gemessenen Huellen stehen (2026-09-23)
- **6 Koepfe / 135 GEMESSENE Insn** in `port/include/port/mission_list.h`,
  `port/src/mission_list.cpp` (Namensraum `port::mission::list`) +
  `mission_list_words.inc` (135 + 45 Plattworte, 11 SDA-Zellen) +
  `mission_list_check.{h,cpp}` (**Anker 226-229**: 2/2, 14/14, 7/7, 3/3,
  FNV-1a `BAE17DDE`), Modus **`mlist`**,
  Werkzeug `scripts/m129_hull.py` (`plate|hull|span|sites|deps|dis|words`).
- **Strang A** `80057880` (58, Blatt, 6 Tail-Rufer) + `8005865C` (4,
  Inventarkopf, 2 `bl`) = 62 Insn; **Strang B** `800545E0` (34) +
  `8006269C` (17) + `80062660` (15, VERDECKT) + `80054668` (7) = 73 Insn.
  Beide Huellen **geschlossen (Aussenkontakt 0)**.
- **Grenzkorrektur (eigener Fehler B128, R271):** `8005865C -> 8005866C` und
  `800584A4 -> 800585BC` fehlten in `m111_core.MEASURED_END`; jetzt in BEIDEN
  Tafeln (+ die zehn Plattengrenzen).
- **Wortinterpreter `scripts/m129_ref.py`** (R219) fand **R299**:
  `rlwinm rX,rX,16,0,0xF` = `(v & 0xFFFF) << 16`, NICHT `v & 0xFFFF0000`.
  **R300** mtspr-SPR-Feld ist geswappt. **R301** Modellregister 32-Bit-maskieren.
  **R302** verdeckter Nachbar in der Spanne erzeugt Schein-Aussenkontakt.
- **R147/R148 in ZEHN Stellen** (Sperrsonde 2, Synthesezelle 3, Slot-Aufloesung
  4, `cursor_zero` 1 - letztere war seit Batch 96 gebaut).
- **Zahlen:** Waehler-Gruppe **68/29**, 2a-Kern **1/0** (9/9), ehrliche
  Gesamtzahl **67 offen / 1767 Insn** ((B) 265 gebaut / 67 offen), (A) 99/50,
  R207 **549** (28/0/0), ABI **202**, Modulkopf 83, Dok 85, Regression
  **32 + 246**, **77 Modi**. **B129_PLATE** (nicht gebaut, 0 Rufstellen):
  `0x800585BC` + Thunks `0x80058614/1C/34/48/6C`.

## BILANZ-PFLICHT ab Batch 129 (im Anker `analysis/r1b-workstream.md`)
Jeder Batch nennt JEDEN getrackten Ast einzeln: **2a-Kern** (9/9, 0 offen),
**Waehler-Gruppe** (97 Ziele), **Waehler-Ast (B)** volle Huelle,
**(A)** Rand-Huelle, **Unterbau (B)**, die **Straenge A/B** dieses Batches,
**B129_PLATE**, **Sprungtabellen-Gruppen A-H** (B49-58), **327er-Pool**
(B53/58), **Programm-Inventar** (B60) - je mit Quelle.

## Batch 128: der 2a-Kern ist vollstaendig (2026-09-23)
- **8 Koepfe / 405 GEMESSENE Insn** (`8002946C` 29, `800294E0` 103,
  `8002967C` 73, `800297A0` 38, `80029958` 39, `800299F4` 23, `80029D0C` 44,
  `8002A488` 56) in `port/include/port/voter_core2a.h`,
  `port/src/voter_core2a.cpp` (Namensraum `port::voter::core2a`) +
  `voter_core2a_words.inc` (`kCore2aSda[6]`, `kCore2aRomCells[5]`,
  `kCore2aWords[405]`) + `voter_core2a_check.{h,cpp}` (**Anker 222-225**:
  416/416, 21/21, 8/8, 9/9), Modus **`core2a`**,
  Werkzeug `scripts/m128_core2a.py` (Modi `hull|span|norm|sites|deps|dis|words|romprobe`).
- **DAS ZWEITE MODUL IST DER ROM-SPIEGEL:** `port/include/port/rom_alias.h`,
  `port/src/rom_alias.cpp` (`install_alias_mirror(be_bin, ram, dest)` /
  `reset_alias_mirror`; `kRomAliasBase 0xFF000000`, `kAliasLo 0xFF1C0000`,
  `kAliasHi 0xFF220000`, `kAliasSize 0x60000`). **Sinn:** die acht lesen
  `0xFF1Fxxxx` = ROM-SICHT; der Spiegel legt das 2-MiB-ROM dorthin, damit die
  schon gebauten Koepfe `byte_cmp`/`list_find8`/`list_find12` **unveraendert**
  mitarbeiten (R148 — kein zweiter Lesekanal).
- **Host-Anschluss:** `Core2Host::core2a` (`const core2a::Core2aHost*`), additive
  Regel R193; `Core2aHost { const Core2Host* core2; AliasMirror alias;
  opmode::OpMode* opmode; }`. Ohne Wirt bleibt jeder der vier Wege ein
  **gezaehlter Haken** (R215).
- **R147-Verdrahtung** in `port/src/voter_core2.cpp`: `cr1_w18_zero` →
  `core2a::aux_ring_push`; die drei Tafelziele → `board_setup` / `aux_load` /
  `aux_distribute` (mit `++s.d_case_new`, ohne Hakenzaehler).
- **Sandkasten** (Anker): Spiegelbasis `kMirrorBase 0x80200000`, `kBankCell
  0x803D0000`, `kCtx 0x803D0100`, `kSetWord 0x803D0300` (**1 Stufe**),
  `kSatTab 0x803D0400`, `kCursorCell 0x803D0600` (1), `kClassTab 0x803D0800`
  (1), `kJmpCell 0x803D0A00`, `kCursor 0x803D0C80`, `kFlushDst 0x803D0C90`,
  `kQueueBlk 0x803D1000` (fuer `sda(0x09C)`).
- **Zahlen:** offen **73 Knoten / 1861 Insn** (GEBAUT (B) 259, (A) 96/56);
  R207 **543** (27/0/0); ABI **196**; Modulkopf **88 -> 83**, Dok-Header 87;
  Regression **32 + 241**; **76 Modi**; Closure `80029F50` **geschlossen
  (1 Knoten / 0 offen)**.
- **GEMESSEN OFFEN (nicht gebaut, `B128_OPEN`):** `8005865C` (4-Insn-Rumpf /
  36-B-Spanne, verdeckter Nachbar `8005866C`, Tail → offen `80057880`),
  `800545E0` (34 Insn, ruft offen `8006269C`/`80054668`).

## Batch 125: Bildtakt-Geber + Anzeigeslot-Schleife (2026-09-23)
- **11 Koepfe / 238 GEMESSENE Insn** (`80008668` 56 Bildtakt-Geber,
  `80015744` 44 Slot-Schleife, `800154E0` 42, `80015630` 39, `80015588` 18,
  `80011DB4` 10, `80015704` 10, `80011EAC` 9, `80008474` 4, `800084A4` 4,
  `8001572C` 2) in `port/include/port/image_tick.h`, `port/src/image_tick.cpp`
  (Namensraum `port::tick`) + `image_tick_words.inc` (FNV-1a **4BDFB2E4**) +
  `image_tick_check.{h,cpp}` (Anker **214-217**: 300/300, 10/10, 14/14, 4/4),
  Modus **`tick`**, Werkzeug `scripts/m125_tick.py`.
- **DIE VORPRUEFUNG HAT DIE HUELLE DES VORBATCHES ZWEIFACH WIDERLEGT:**
  (i) acht der achtzehn offenen Knoten haben **keine `insn`-Spalte** (Basis
  238, GEMESSEN **577**); (ii) die Spannenkante von `8001572C` fuehrt durch den
  **verdeckten 2-Insn-Stub `0x80015734`** (0 Rufstellen) und zieht 6 Knoten /
  298 Insn aus dem Weg `0x8001573C` -> `800152B8` herein. Gemessene Huelle:
  **13 Knoten / 272 Insn** = 11 Koepfe + Host-Modelle `80008448` (Zeitbasis) /
  `8000CB40` (Watchdog, R215). Grenze in `RANGES` **und** `MEASURED_END`.
- **R147:** der Kopf faehrt `frame::cg_switch`/`vbi_commit`, `DisplayBank::
  switch_to`, `GunInput::frame`, `Bookkeeping::{tick,add_amount}`,
  `voter::sel::select_apply` und `AudioEngine::host_append` (Wire 0x902) ECHT;
  ohne Wirt GEZAEHLT (R215). **R282:** `[SDA(0x0B0)]` = E/A-OBJEKT, Slot-0-
  Blinkfeld = `cfg+0x30` = das **Eingabewort**. **R283:** Blinkzaehler `p4+0`
  IST die Abzugszelle desselben Slots. **R281:** Pruefwert fuer Bitanlegen darf
  das Bit nicht enthalten (`0xA000` hat `0x8000`).
- **Zahlen:** Waehler-Gruppe **65/32**, 2a-Kern **1/8** unveraendert (nur
  `80011EAC` in (B)); ehrliche Gesamtzahl **82 offen / 2276 Insn / 1884 B**;
  GEBAUT (A) 95, (B) 332; R207 **529** (26/0/0); ABI **183**;
  Regression **32 + 235, 0 Fehler**.

## Batch 119: T4-Kranz des M5-Waehlers (2026-09-23)
- **12 Koepfe / 457 GEMESSENE Insn** (2b-Wurzel `8005389C` 169, `800537A8` 33,
  `80053C2C` 32, `80053BA4` 34, `8005469C` 32, `8005542C` 20, `8005625C` 24,
  Satzaufbau `80037D10` 28 + `80037D90` 16, Satzbauer `80030E48` 53, Namenswort
  `8002A624` 12, **verdeckter Nachbar `80037D80` 4**) in `port/src/voter_t4.{h,cpp}`
  + `voter_t4_words.inc` + `voter_t4_check.{h,cpp}` (Anker **190-193**: 471/471,
  14/14, 4/4, 12/12), Modus **`t4`**, Werkzeug `scripts/m119_t4.py`.
- **R147:** ALLE **elf** Hakenstellen des GEBAUTEN T4-Verteilers `FUN_8005471C`
  (`mission_script.cpp`, 0x80055288..0x800553C0) sind ersetzt; `core2` ohne Wirt
  bleibt gezaehlter Haken (R215). **R216-Richtung 1 nachgezogen:** alle 12 Koepfe
  per `reg.add` (A: 122 -> 134).
- **Zahlen:** Waehler-Gruppe **53/44 -> 60/37**; ehrliche Gesamtzahl (Huelle B,
  korrigiertes Werkzeug!) **152 -> 141 offen / 4090 -> 3735 Insn / 5088 -> 4696 B
  (nur size)**, Unterbau 104, GEBAUT 238 -> 249; Regression **32 + 211 Anker**;
  Modi **55/64**; R207 **479** (12·0·0); Ghidra **2085**.
- **EIGENER WERKZEUGFEHLER (behoben, wichtig fuer alte Zahlen):**
  `m112_ast.built_all_set()` legte `C103.built_set()` ungefiltert dazu -> die vier
  `B104.HOOK_CORRECTIONS` IN der Huelle galten als gebaut; **alle** Zahlen dieses
  Werkzeugs seit Batch 113 waren **4 Knoten / 151 Insn** zu guenstig. Der
  Vorher-Wert nach B118 ist **152 / 4090 / 5088**, nicht 148/3936/5216.
- **R248** zwei Zustandsbytes: `slot+0` = Zustand des Inhalts (Verteiler),
  `slot+1` = eigener Zustand der 2b-Wurzel (`lbz r5,0x1(r29)`). **R249** die
  `insn`-Spalte kann ZU GROSS sein (`8005389C`: 194 statt 169) -> Rumpfende in
  `RANGES`/`MEASURED_END`. **R250** die Namensaufloeseebene ist LAUFZEITdaten
  (`[SDA(0x188/0x1B4/0x1BC/0x1C0)]` -> 0x800FAA64/0x800FAAA8/0x800FEB28/
  0x800FEBA8 liegen oberhalb des main.bin-Abbilds; erst `capture/m31_ram4mb.bin`
  traegt sie, Tafelkopf 0x80390000) -> Anker baut sie synthetisch (`prime_asset`).
  **R251** `slot_word4` = Zwischenzelle, Quellzeiger = `*(u32*)(W+4)`, Kennung
  fuer `+0x1C2` = `entry(idx)`. **R252** `state_inc(slot,n)` ERHOEHT um n.
- **`8000FF8C`** (82 Insn) hat einen EIGENEN Kopf (Spanne von `8000FE78` zerfaellt
  luecken-/nullwortfrei in 69 + 82) -> `B119_ADOPTED`, einzige Rufstelle
  `bl 0x80026924` in der offenen `800267B0`.
- **Anker-Praxis:** Prueffall-Sandkasten braucht die Aufloeseebene als
  synthetische Tafel (Zellen 0x188/0x1B4/0x1BC/0x1C0 umbiegen); T3-Weg braucht
  `slot+0x3C` Bit, `ctx+0x12 >= 2` und `slot+0x40 & 0x400`.

## Batch 113: Satzketten-/Effekt-Record-Familie des Waehler-Astes (2026-09-22)
- **9 neue Koepfe / 453 GEMESSENE Insn** (Eintritt `80062A4C`, Aufbau-Verteiler
  `80062B1C`, Zeilenleser `800625F4`, Satzkette `80062430`, Teilebindung
  `80062328`, Ringbelegung `80062B94`, Ausgabe `800632E4`, Kettenglieder
  `8003B1FC`, Flagge `800599D4`) in `port/src/voter_records.{h,cpp}` +
  `voter_records_check.{h,cpp}` (Anker **178-180**: 466/466 Worte, 12/12, 5/5),
  `voter_records_words.inc` (FNV-1a **8D1B111F**), Modus **`records`**.
- **Die ehrliche Gesamtzahl sinkt:** offen **209 -> 197 Knoten**, **6664 -> 6149
  Insn** (26656 -> 24596 B), Unterbau offen **164 -> 152**; die 12 Knoten/515
  Insn = 9 neue (453) + 3 Adoptionen (62). Waehler-Gruppe **52/45 (Delta +0)**,
  2a-Kern **28/8**; Regression **32 + 202 Anker, 0 Fehler**; **52/64** Modi Exit
  0; R207 **308** (12·**0**·0); Ghidra **2085**.
- **R216 Richtung 1 (4 Funde):** `8001D788`/`8001D800`/`8003AECC`/`80020F7C`
  waren als `HitLayer::{matrix_apply,point_transform,node_chain,isqrt16}` GEBAUT,
  aber in keiner Bau-Liste -> `B113-adopt`. Ebenso implementiert, aber offen:
  `8000C6B4`, `8000EC58` (OpMode), `8000EDCC`, `8000FD7C`.
- **R147 ehrlich offen:** ALLE Rufstellen der neun Koepfe liegen in ungebauten
  Koepfen (`80062124` = gezaehlter Haken; `8003AD74`, `8003ADE4`, `8007A4A0`).
- **Neue Regeln:** R219-Ergaenzung (`mtcrf 0x80` = CR0 mit dem HOECHSTEN Nibble ->
  `blt` = Vorzeichentest; nur CRM 0x01 ist die niedrige Nibble in CR7);
  **P100-Grenze** (verfolgt keine Ruf-Argumente: `8005C168` schickt `0xFF1C2000`
  an `FUN_8002AEB C` = LZSS-Fenster); R222 dritte Richtung (`8005C820`: `insn`
  21 zu klein, `size` 269 zu gross, gemessen 202 = Verteiler + Inline-Koerper);
  Ring-/Kornsuche testet `cur + 100*k`; Zeiger-Stapel-Falle (genullt werden die
  ZULETZT eingetragenen Ziele); Sandkasten muss die Schreibweite kennen (844 B
  Fuellung!); Regressionsanker brauchen dauerhaft gedruckte Werte.
- **Werkzeug NEU:** `scripts/m113_pick.py` (`cands`/`scan`/`scanreq`/`pick`/
  `req`/`callers`/`union`/`words`) + `scripts/m113_anker.py`.

## Batch 112: Waehler-Ast ehrlich gemessen + 2a-3 (2026-09-22)
- **Die ehrliche Groesse des offenen Waehler-Astes** (`scripts/m112_ast.py ast`):
  **volle Huelle** (durch die gebauten Knoten hindurch) = **390 Knoten, 181 gebaut /
  209 offen = 26656 B (6664 Insn) + 5588 B (42x nur `size`)**; davon **164 offene
  Knoten = 79 % NUR UNTERBAU** (nie in der 97er-Liste, 23532+2352 B, 5883 Insn).
  Huelle „bis zum gebauten Rand" (Batch-104-Mass) = 179 Knoten / 92 offen — sie
  SCHRUMPFT mit jedem Bau; **nicht** als „wie viel fehlt" lesen.
- **Fuenf neue Koepfe / 353 gemessene Insn:** `port/src/voter_core2.{h,cpp}` +
  `_check.{h,cpp}` (Anker **174-177**: 395/395, 16/16, 5/5, 5/5),
  `voter_core2_words.inc` (FNV-1a 9D186BDD), Modus **`core2`**. Verteiler
  80029F50 / Satzschritt 80029394 / Relokation+Slottafel 80029A50 /
  Listensuche Schritt 12+8 (8002ADD8, 8002AF14). Wirt `Core2Host{win,bank,ring,leaves}`.
- **CONFIRMED:** Sprungtafel bei `[SDA(0x1C4)]+0x1C0 = 0x80087158`, Eintraege =
  **Offsets relativ zu `[SDA(0x1C8)] = 0x800291F8`**; **Eintrag 5 unerreichbar**
  (idx == 5 -> bank_dirty-Weg); Slottafel-Felder **unterschiedlich indiziert**
  (P rueckwaerts -> +0x00, Q/R/S vorwaerts -> +0x04/+0x08/+0x0C).
- **Verdrahtung (R147/R194):** `GunHooks`/`FlowHooks` additiv `core2`/`core2_stats`;
  4 der 15 Rufstellen echt (0x80028F74 GunB, 0x8003E0D8 + 0x80084108, 0x80041D90).
  GunB Zustand 2 mit Wirt: 1 Ruf + Zustand 2 -> 8 (gemessen). Die zwei Schirmmodi
  setzen den Wirt noch nicht (R215-Luecke).
- **Regression 32 Frames + 199 Anker, 0 Fehler**; 51/63 Modi Exit 0;
  R207 296 Koepfe (12·0·0); Waehler-Gruppe 52/45; **2a-Kern 28 gebaut / 8 Haken**.
- **Fallstricke:** (a) Sandkastenbereiche duerfen sich nicht ueberlappen
  (`clear_area(kC2List,0x600)` loeschte Satz-/Halbsatztafel); (b) `[SDA(0x1C8)]`
  ist EINE Stufe (keine Zeigerzelle); (c) im R-Lauf steht `r5 += 0x10` NACH dem
  Eintrag; (d) das P-Feld ist 0-basiert (Schleife liest rueckwaerts);
  (e) `reloc_rows` zaehlt R+Q+S; (f) Zaehler erst nach `Core2Stats{}` lesen;
  (g) `slice_step` kopiert `[SDA(0x188)]` NACH dem Relokationslauf (Wert = idx+1);
  (h) **R148-Landmine**: `kSdaRingCtx` war in `voter_leaves.h` UND `voter_ring.h`
  definiert (Uebersetzungsfehler bei Doppel-Include) — Doppeldefinition entfernt;
  `kSdaSlotTab` gehoert `voter_family.h` -> hier `kSdaIdxTab` adoptiert.
- **R222 zweite Richtung:** die `insn`-Spalte kann zu KLEIN sein (`80029F50`:
  43 statt 54). **R201:** drei „Luecken" = sechs Koepfe mit 0 Rufstellen (Haken).

## Batch 111: R223 behoben + die Paket-/Fensterhelfer des 2a-Kerns (2026-09-22)
- **R223 behoben (beide Haelften in EINEM Zug):** `render_transport::state_at()` =
  `u32_at(u32_at(sda_+0x0F8))`; `overlay_dump()` schreibt die Basis in die
  **Zeigerzelle** (`write32(read32(r2+0xF8), d.state)`). Gegenprobe in
  `render_check.cpp::probe_state_chain()` (Bildzelle 0x800FA288 ist NICHT die
  Basis; FLACH aufgesetzt → `state_at()` liefert die Basis NICHT) +
  Regressionsanker `stateketten-anker`. **Rueckfall-Simulation gefahren:**
  flache Fassung → 0/19 Faelle, Exit 2.
- **Acht neue Koepfe / 383 GEMESSENE Insn:** `port/src/voter_windows.{h,cpp}` +
  `_check.{h,cpp}` (Anker **170-173**: 461/461 Wortproben, 19/19, 5/5, 3/3),
  `voter_windows_words.inc` (FNV-1a **631BEE7D**), Modus **`windows`**.
  Ring 1 (800187F4) / Ring 2 (80018780) / Paket 0x5F/0x60 (80018844) /
  texBase (80019888) / Fenster OEFFNEN (800188A8) / SCHLIESSEN (80018950) /
  Bankflush (80029838) / Streifenausgabe (80029224). Wirt = `WindowHost{rt,bank,
  gate}` (R215: ohne Wirt wird GEZAEHLT). `MsrGate::write` gibt den Registerrest
  zurueck (R161).
- **Verdrahtung (R147/R194):** `GunHooks::win/win_stats`; die vier ROM-Stellen
  0x80028B88/0x80028CBC (FUN_80028A30) + 0x80028EB4/0x80028F00 (FUN_80028E98)
  rufen `voter::window_site` → echten Kopf; GUN-CHECK-Anker `[101] 2/2`
  (25/25/50 Pakete, 0 Wirt-Fehler). Die uebrigen 42 Rufer sind ungebaut.
- **Regression 32 Frames + 193 Anker, 0 Fehler**; 50/50 argumentfreie Modi;
  R207 291 Koepfe (12·0·0); Waehler-Gruppe 52/45; **2a-Kern 23 gebaut / 13 offen**.
- **Wiederkehrende Fallstricke (aus eigenen Fehlern):**
  (a) `RenderTransport` in einer neuen Umgebung braucht IMMER `set_sda`, sonst
  `frame_at()` → Fault `read32 @ 0x00000004`; (b) `lhzu`-Halbwort ist die HOHE
  Haelfte des Wortes dort (big-endian); (c) `TransportRecorderSink` nummeriert
  RELATIV zum ersten Paket; (d) `namespace voter` INNERHALB `port::gun` deckt
  `port::voter` zu (Vorwaertsdeklaration auf `port`-Ebene); (e) die Slottafeln
  liegen 8 Byte auseinander (+0xEA50 vergleichen / +0xEA54 schreiben /
  +0xEA58 oeffnen).
- **P100-Vorprobe (neu):** `scripts/m111_core.py unbaubar` verfolgt
  `lis`+`addi/addic/ori` und meldet Speicherzugriffe ausserhalb 0x80000000..
  0x803FFFFF - Positivkontrollen `FUN_8005E280`/`FUN_800297A0`; sieben 2a-Knoten
  (800294E0/8002967C/800297A0/80029958/800299F4/80029D0C/8002A488) sind
  **unbaubar** (0xFF1Fxxxx) und in `m104_built.KNOWN_HOOKS` benannt.
- **R219 geloest:** `mtcrf 0x1,r0` füllt CR7 mit `LT,GT,EQ,SO = Bit 3,2,1,0`;
  `bso cr7` testet das NIEDERSTE Bit der Gruppe → `rlwinm ...,20,28,31` + `bso`
  = **Bit 12** in FUN_80019458 (Batch 110 hatte recht).

## Batch 106: Der R148-Verdrahtungs-Batch (2026-09-22)
- **Gebaut wurde NICHTS** - 17 Hakenstellen in **sechs** Modulen verdrahtet
  (mission_content 4, mission_script 3, mission34_family 4, mission2_family 3,
  mission_services 1, mission_helpers 2), die 18. bleibt benannter Haken.
- **R214 (NEU):** der Hakenzensus war zu klein - `\bh[0-9]?\(` uebersieht
  **`hk(`** (lokaler Weiterreicher in 4 Modulen) -> 15 waren in Wahrheit 18.
  Zensus braucht die vollstaendige Namensliste UND eine Positivkontrolle.
- **R215 (NEU):** R148-Adoption ist nicht immer moeglich - klassengebundene
  Koepfe (`FUN_8000F1E0` = `OpMode::pool_fill_rect`) bleiben **benannte
  Haken** (wie `word_fill` fuer `OpMode::word_set`).
- **R194-Ergaenzung:** ein Haken als **Bedingung** wird auch im
  Nichttreffer-Fall gezaehlt -> nach der Verdrahtung sinkt die sichtbare
  Hakenzahl (M2-UI 3 -> 2); Wirkungsfall muss BEIDE Zweige abdecken.
- Anker: (118) 15/15, (121) 41/41, (125) 14/14, (130) 4/4, (133) 14/14,
  (134) 10/10; **Regression 32 + 175 Anker, 0 Fehler**; 45/45 Modi Exit 0.
- **R207 rueckwaerts:** (a) 8 / (b) 0 / (c) 0 ueber 240 Koepfe (unveraendert).
- **Naechster Schnitt (gemessen, NICHT gebaut):** `FUN_80054038` = 19 Knoten /
  2828 B / 707 Insn; Wurzelspanne 828 B / 207 Insn, 7 `bclr`, EIN
  `stwu`-Prolog (0x80054050) -> kein verdeckter Kopf; 3 Knoten schon gebaut
  (8003C6C4/800522B0/80052310) -> **16 neu ≈ 2480 B / ~620 Insn**.

## Batch 102: Die Ablauf-/Flussfamilie der fuenf Inhalte
- **Kurzfassung in `/memories/repo/missionsebene.md`** (30 Koepfe / 3288 B /
  822 Befehlsworte; R170 7. Anwendung mit drei Doppel-Eintraegen; **R202**:
  Tail-Aufrufe sind fuer einen `bl`-Scan unsichtbar; Rest 6 Ziele / 984 B).
- **Neu:** `port/src/mission_flow.{h,cpp}`, `mission_flow_check.{h,cpp}`
  (Anker **141-145**), `mission_flow_words.inc` (erzeugt, FNV-1a 8FF0F7B0 ueber
  3288 B), Werkzeuge `scripts/m102_flow.py` (rest/closure/heads/bounds/sib/dis/
  disfam/deps/callers) / `m102_words.py` / `m102_wire.py` / `m102_anchors.py`;
  Modi **`flow`** / **`flow-ui`**.
- **Verdrahtung (R147):** 16 Regeln / **53 Stellen** in `mission_content.cpp`;
  **R148:** `port::Prng`, `paket_d`, zwei Audio-Funktionen echt (604 B, nicht
  dupliziert); neuer Saum `FlowHooks::audio_id/audio_wire/audio_trigger_user/
  panel_setup/panel_user` (additiv, R193); **36** Inhaltsanker auf Wirkung
  umgestellt (R194, 8. Anwendung) + M2-UI-Zeile 4 → 3 Haken; 2 neue
  Regressionsanker (`flow-rom-anker`, `flow-ui-anker`).
- **`FlowStats` neu:** `last_fn`/`last_args[4]` + `prev_fn`/`prev_args[4]`
  (Notenspeicher statt Hakenzeiger — ein `log.first(...)->args[…]` war nach der
  Verdrahtung ein **Null-Deref**, der den `content`-Modus ohne Ausgabe killte).
- **Regression 32 Frames + 161 Anker = 0 Fehler** (vorher 159); Ghidra 2085
  unveraendert (0 Schreibzugriffe).
- **Fallstrick:** ein lokaler Helfer `sound_id` verdeckte `mission::sound_id`
  → Selbstaufruf; der Uebersetzer warnt nicht (R148-Landmine).

## Batch 101: Die Blatt-/Zellenfamilie der fuenf Inhalte
- **Kurzfassung in `/memories/repo/missionsebene.md`** (33 Koepfe / 2140 B,
  R170 sechste Anwendung mit DREI Doppel-Eintraegen, `bl`-Scan entscheidet
  ueber die Geschwister, neue Regeln R199-R201, Rest 22 Ziele / 3244 B).
- **Neu:** `port/src/mission_content_helpers.{h,cpp}`,
  `mission_content_helpers_check.{h,cpp}` (Anker **137-140**),
  `mission_content_helpers_words.inc` (erzeugt), Werkzeuge
  `scripts/m101_content.py` / `m101_words.py` / `m101_registry.py`;
  Modi **`helpers101`** / **`helpers101-ui`**.
- **Verdrahtung (R147):** 19 Stellen in `mission_content.cpp`, `flag_or6`
  (mission_script.cpp) ruft `FUN_80057BA8` echt; **neun** Inhaltsanker
  (Hakenzahl -> Wirkung, R194) + eine UI-Zeile; 5 neue Regressionsanker.
- **Regression 32 Frames + 159 Anker = 0 Fehler** (vorher 154);
  **41 von 53** Modi Exit 0; Ghidra 2085 unveraendert.

## Batch 92: Die GAME-MODE-Kette + was `[SDA(0x240)]` ist
- **`[SDA(0x240)] = 0x800FF928` = der GLOBALE SPIELZUSTANDSBLOCK** (NICHT
  "Demo-/Skriptkette" — Batch-91-Formulierung korrigiert). 166 Lesestellen in
  ~110 Funktionen, **0 Schreibstellen ueber r2** (R152). Felder: `+8` Flagwort
  (B0 Anzeigezweig, B1 Sound-Gate, B3 Variantenbit), `+0x10` Phasenzaehler,
  `+0x0E` Optionsnibble, `+0x12` Gate, `+0x14` Stufe (`0x1D` Abbruch),
  `+0x1C` u16. Bytes 0..7 = **Zustandsvektor**.
- **Hierarchie (CONFIRMED):** Eintrag 20 GAME MODE `(a) FUN_800846D4`
  (`FUN_8000D140(ctx,0,6)` = **6 WOERTER**, nicht Bytes!) / `(b) FUN_80084038`
  (6 Zustaende, Tabelle `[SDA(0x7C8)]=0x8008C9D8`, Basis `[SDA(0x7CC)]` = die
  Funktion selbst; Zyklus 0->1->2->3->4->5->1; **Rueckgabe = Bit 13 `io+0x1C`**)
  -> `FUN_8003CAD8` (13 Zustaende, Spielschleife) -> `FUN_8003DF3C`
  (6 Zustaende, Mission) -> `FUN_8003EAA0`/`FUN_8003EB44` (Ergebnisbildschirm).
- **Neu:** `port/game_flow.{h,cpp}` (`game_mode_step`/`game_mode_init`/`seq_run`/
  `two_stage`/`state_set`/`state_inc`/`aim_value`/`aim_sum`/`aim_update`),
  `game_flow_check.cpp` (Anker **101-104**), `game_flow_words.inc`,
  `scripts/m92_demo.py`; Modi `game-flow`/`game-flow-ui`; Eintrag 20 verdrahtet
  (`kGapGameMode` zu, Ersatzregel entfernt).
- **Regression 32 Frames + 125 Anker = 0 Fehler**; Ghidra **2085** (0 Aufrufe).
- **Regeln:** **R149** `rlwinm ...,2,0x1E,0x1F` liest die zwei obersten Bits
  UMGEKEHRT (B28->2, B29->1). **R150** die SDA-Tafel liegt IM Bild (Zellen =
  ROM-Zeiger). **R151** Tabellenbasis = Funktionsanfang, eine Tabelle kann ZWEI
  Funktionen gehoeren. **R152** Schreibzensus ueber die SDA-Zelle findet nichts.
  **R153** `bl` auf ein Deskriptorziel ist KEIN Trampolinaufruf.

## Batch 91: Die GUN CHECK-Familie (Waffenkalibrierung)
- `port/gun_check.{h,cpp}` (Zustandsmaschine `FUN_80028E98`, Unterautomat,
  Stellschritt, Achsenkette inkl. Kosinustafel, Achsenfilter, Texte, elf
  Ressourcen, I/O-CHECK-Aufbau, zwei Balken), `gun_family_check.cpp` (Anker
  94-100), Modi `gun-check`/`gun-check-ui`; Konsumentenzensus
  (`m91_gun.py rest`). **Regression 32 Frames + 122 Anker, 0 Fehler.**
- **R146** ein Terminator, der wie ein WORT aussieht, ist ein **Byte-Store am
  Pufferende**; **R147** ein Lueckentext ist eine Aussage ueber den BAUZUSTAND
  (wer baut, muss im SELBEN Batch verdrahten); **R148** gleicher
  `constexpr`-Name in zwei Kopfstuecken = Landmine (adoptieren statt duplizieren).
- **R142** `rlwinm`/`rlwimi` als `(Ziel,Quelle,SH,MB,ME)`, Maske wirkt **an Ort
  und Stelle**; **R143** `bc 4,30`; **R144** "kein Schreiber ueber [SDA(x)]"
  beweist nichts; **R145** der Zaehler muss sagen, was gedruckt wird.

## Batch 90: Die Spielseite (Konsumenten des Bedienworts)
- `port/game_input.{h,cpp}` (`abort_gate`, `q16_axis`, `read_check_rows`,
  `io_check_display`, `io_check_b`, `consumer_map`), `game_check.{h,cpp}`
  (Anker 89-93); **66** Lesestellen (nicht 87, R138); Gate
  `lha 0x14([SDA(0x240)]) == 0x1D` + `(s8)+0x10 < 0` + `io+0x1C & 0x0084`.
- **R138** Zensus braucht die FUNKTIONSGRENZE und das VERWERFEN abgeleiteter
  Basisregister; **R139** ein Tafelfeld wird ueber die BEFEHLSFOLGE zugeordnet;
  **R140** ein Live-Wert, der zu einer Zelle passt, ist kein Schreiberbeweis;
  **R141** `andi.` + `crorc` ist eine ZUSAMMENGESETZTE Bedingung.

## Batch 88d-1: Der Grafik-/Ladeteil der Nutzlast
- **Kurzfassung in `/memories/repo/ladeteil.md`** (Warteschlange, LZSS 1:1,
  Arbeitsobjekt/Zellpool, Bankzeichner, Sprite-Ausgabe, Anker (76)-(80),
  Regeln P124-P127, Live-Werte, offener FDC-Zweig).
- **Neu:** `port/src/opmode_load.cpp` (Queue + LZSS + Objekt/Zellpool +
  Bankzeichner + Sprite), `opmode.h` **5d**, `opmode_load_check.{h,cpp}` **NEU**,
  `text_layer` Poolhaken, `opmode_entry/screens/payload` verdrahtet,
  `scripts/m88d_load.py`/`m88d_pool.py`/`m88d_anchor.py` **NEU**.
- **Anker:** (76) 80/80 Woerter · (77) **LZSS bit-exakt** (713368 B,
  Summe == Kopf, 0 Abweichungen zur Bilddatei; Pumpe 2642 Aufrufe) ·
  (78) Objekt/Zellpool + **Bankliste 15/15 == Live-Dump** · (79) Sprite ·
  (80) Spur. **Regression 32 Frames + 101 Anker = 133, 0 Fehler**;
  20 Modi Exit 0; Ghidra 2085 (6 Dekompilationen, 0 create_function).
- **Offen:** **88d-2** (FDC/DEFLATE ~1050 Instruktionen + F988/EE34/FCF8/
  F468; 1-1,5), **90** Spielseite (1-2) => **2-3 Batches**.

## Batch 89: Die Texteingabe HOME PAGE ADDRESS / PASSWORD
- **Kurzfassung in `/memories/repo/eingabeschicht.md`** (Tagescode, Adresstextfeld, Mechanik,
  Zellen, Anker, Regeln P121a-P123, eigene Fehler).
- **Neu:** `port/src/opmode_entry.cpp` (751 Zeilen) + `opmode.h` Abschnitt 5c,
  `text_layer.cpp` (`centered` kann **which = 4** = `[SDA(0x70)]+0x04`),
  `service_screens.{h,cpp}` (**`kGapHome`/`kGapPassword` zu**, Phase-2-Aktion echt, beide
  (a)-Inits byte-genau: HOME 64 B / PASSWORD 9 B), `opmode_check.{h,cpp}` (Anker **(71)-(75)**,
  `dump_entry_ui`), `scripts/m89_input.py` + `m89_anchor.py` **NEU**; Artefakte `_m89_*`.
- **Modi:** `opmode` (Anker (53)-(75), Exit 0) · `opmode-ui` · **`service-ui`** druckt jetzt auch
  die Seiten 9-12 (beide Eingabeschirme als Raster + Cursorkaesten + drei Pruefausgaenge).
- **Regression 32 Frames + 98 Anker = 130, 0 Fehler**; 20 Modi Exit 0; Ghidra 2085 (0 Aufrufe).
- **Offen:** **88d** Grafik-/Ladeteil (1-2), **90** Spielseite (1-2) => **2-4 Batches** (89 entfaellt).

## Batch 86: Die allgemeine Eingabeschicht, Teil 1 (Oberflaeche + Waffenpfad)
- **Kurzfassung in `/memories/repo/eingabeschicht.md`** (die vier Eingabequellen, die gemessene
  Verdrahtung, die Port-Module, P95-P97, die offenen Teilschritte 87-90).
- **Neu:** `port/input_layer.{h,cpp}` (Rohsicht + Host-Mapping + `frame()` -> Originalhook),
  `port/gun_input.{h,cpp}` (`FUN_8002379C`/`80023864`/`800236EC`/`800235F8`/`80023A8C` 1:1),
  `port/input2_check.{h,cpp}` (Anker 42-47); Modi `input2`/`input-map`;
  Werkzeuge `scripts/m86_input_surface.py`, `m86_history.py`, `m86_doku.py`.
- **Regression 32 Frames + 74 Anker = 106, 0 Fehler**; 14 Modi Exit 0; Ghidra 2075; 0 MAME-Laeufe.
- **P95** `addic` (Op 12) setzt kein CR0 (nur `addic.` Op 13; MAME ppcfe.cpp); **P96** ein
  Hardware-Bit definiert der KONSUMENT, nicht der Name; **P97** ein `bcl` ist ein Aufruf.
- Offen: **87** Analogauswertung (`FUN_80022EA0`/`22FA4`), **88** Moduswechsler in `FUN_80026C34`,
  **89** Texteingabe HOME/PASSWORD, **90** Spielseite. Schaetzung **4-6 Batches**.

## Batch 83: Port-Schritt 5 Teil C-2 — RANKING-Schirm + BLOCKSPEICHER (M48T58Y)
- **Neu:** `port/nvram.{h,cpp}` (8-KB-Hostpuffer = Fenster `0x7D020000..0x7D021FFF`;
  `nvram_read_block`=`FUN_800138D8` (NVRAM->RAM), `nvram_write_block`=`FUN_800138B0` (RAM->NVRAM),
  `nvram_block_checksum`=`FUN_8000E190`, Bytezugriffe `FUN_80013900/1390C`; alle vier addieren den
  Bias `addis rX,rY,0x7D02` auf den KLEINEN Offset — **P85**). Prüfsumme = Summe der ersten
  `len-4` Bytes, `(sum&0xFFFF)|(~sum&0xFFFF)<<16`, steht als **letztes Wort** des Blocks.
- **`port/ranking.{h,cpp}`:** `FUN_800276B8` (Leser, 256 B) = 5 Sätze: NVRAM `2272+452*i` ->
  RAM `cfg+0x68+100*i` (i<2) / `452*i-600` (i>=2), Längen **100/452**, Wächter **Bit 5** von
  `cfg+0x4C` (0 ⇒ kein Lesen), Aktion `FUN_80026E70` bei Flag ODER freiem Bit; Rückgabe = Flag.
  `FUN_80027898` (Schreiber, 304 B) = NVRAM `2976+100*idx` / `2976+200+452*(idx-2)`, Wächter
  **Bit 6**; Aufrufer (GAME OPTIONS 0x8002FC40) schreibt **6**, Leser liest **5** (**P84**).
  `FUN_800277B8` (224 B) = Automat `s8(ctx+2)`: **0** = Frage (`arg2=0`, `FUN_8000DB98` mit
  `[SDA(0x154)]+0x38`) bzw. Überspringen (`arg2=1` mit `cfg+0x2E!=0`), **1** = Meldung
  (`FUN_8000DA80` mit `[SDA(0x158)]` = Pool 36 = `FUN_80026E70`), **>=2** = fertig;
  Dialogzustand = `ctx+4`.
- **Texte:** Frage `+0x3C` = `0x80086BF4` "DO YOU WANT RECORD DATA CLEAR ? [     /    ]";
  Paar `+0x40` = `0x80086C24` "NO MODIFY RECORD DATA" / `0x80086C3C` "RECORD DATA CLEARING";
  `0x80086C00` hat **0 Referenzen** (toter Text).
- **Korrektur zu B82 (P83!):** der Projekt-Disassembler druckt bei `extsb`/`xori` **kein Rc-Bit**;
  `0x800277D0` ist `extsb.` ⇒ `bc 12,2` liest CR0 (= Zustand==0). Die B82-Lesart des Automaten war
  falsch, ebenso die Satzgrößen (richtig 100/452) und die Lesergröße (256 statt 91 B).
- **Gemessene Folge der gemeinsamen Dialogzelle:** im FRAGEdialog entfallen Meldung UND Aktion;
  im ÜBERSPRINGEN-Pfad laufen beide, Schirm fertig in **Bild 60** (1 Zeichnen + 1 Aktion + 58).
- **Anbindung:** Menüeintrag 2 (a) ruft den Leser; GAME OPTIONS Zustand 2 `clear_frame(ctx,0)`,
  Zustand >= 4 `clear_frame(ctx,1)` + 6x `records_write`. **Modi:** `ranking` (Bericht,
  Abschnitte 30-33), `service-ui` zeigt Frage/Meldung/Blocktabelle.
- **Anker:** (30) 53/53 Rohwortfelder + 7/7 Texte/Zellen + Zensus · (31) Blocktabelle 8/8 (aus den
  Rohworten gerechnet, inkl. Asymmetrie) · (32) 12/12 Verhaltensfälle · (33) UI OK.
  Regression **32 Frames + 59 Anker = 91, 0 Fehler** (vorher 87).
- **Nicht gebaut (P73):** `FUN_80026E70` (Pool 36, ~2,1 KB Inhaltserzeuger der Rangliste,
  Zufallsgeber `FUN_80015294`) — Aufruf gezählt; Wächterbit-Bedeutung ungedeutet; NVRAM-Persistenz
  (Datei) offen. **Schritt 5 ≈ 90 %; Rest 2-3 Batches** (5-C-2-Rest = die Aktion 0,5-1 · 5-E
  BOOK KEEPING/GUN VOLUME 1,5-2).

## Batch 82: Testmode-Tastenzugang (Host-Eingang)
- **Neu:** `port/host_input.{h,cpp}` (`HostInputConfig` mit Taste/Bit/`Hold`|`Toggle`;
  `host_input_config_from_env` = `PORT_TEST_SWITCH_KEY`/`_BIT`/`_MODE`; `KeyboardSource` +
  `ScriptedKeyboard` + `Win32Keyboard` (`GetAsyncKeyState`, ohne Fenster, echtes Loslassen);
  `HostInput::frame/submit`: Tastenzustand -> `[SDA(0xB0)]+0x1C` -> **Originalhook
  `FUN_80026C34`** -> `cfg+0x30`; nur das gebundene Bit wird gefahren, `io+0x18` bleibt
  unberuehrt; Zaehler; `run_switch_monitor`), `port/input_check.{h,cpp}` (Anker **27-29**,
  eigener Instruktionsdecoder, **Zensus** ueber das ganze Bild, `dump_test_mode`).
- **Modi:** `port_selftest input` (Bericht, Exit 0) · `testmode` (Skriptspur F1 -> Menue,
  `AUSGABE OK`) · `testmode-live [sekunden]` (echte Tastatur, blockiert; 317 Bilder/5 s).
  Regression: **`input-anker`**, **`testmode-anker`** (`_m82_input_report.txt`,
  `_m82_testmode_trace.txt`, `_m82_regression_anker.csv`) -> **32 Frames + 55 Anker = 87**.
- **Kernfakt:** TEST-Switch = Bit 7 des Eingabeworts (`cfg+0x30` = `[SDA(0xB0)]+0x1C`);
  **0 Stores** auf `io+0x18/+0x1C` im ganzen Bild (drei Storeformen) = Hardware-Eingang.
  Werkzeug `scripts/m82_io_census.py`. Regel **P80** (Zensus braucht drei Storeformen +
  Gegenprobe auf Nachbarzellen), **P81** (Zelle ohne Schreiber = Schnittstelle),
  **P82** (Tastendruck != Schalter, Toggle nur als Port-Entscheidung, Default `hold`).
- **Host-Pflicht:** `HostInput::frame()` **einmal je Bild** (wie `audio_host_frame()`).
- **Nicht gebaut (bewusst):** allgemeine Eingabeschicht (Gun/Trigger/Coin/Start/Richtungen,
  Frame-Loop, Fenster-/Event-Schleife) - eigenes Vorhaben 1-2 Batches; kein Menuedesign.

## Batch 81: Port-Schritt 5 Teil D-2 — SLOT-ALLOKATOR, PANEL-AUFRUFER, INHALTE, ANZEIGESCHALTER
- **Neu:** `port/slot_pool.{h,cpp}` (`FUN_80037258`: Pool `[SDA(0x6E4)] = 0x801271D0`,
  **144 Slots a 0x40 B**, vier Selektoren `1/0x12/0x16/0x1C` mit Regionen `+0/0x400/0xC00/0x1C00`,
  Zaehler 15/31/63/31 + Waechterslot; frei = erstes Halbwort 0, sonst Freigabe des Slots mit
  dem kleinsten s16 bei +2), `port/asset_lookup.{h,cpp}` (`FUN_8002AAF8`/`AB84`/`AB1C`,
  49 Aufrufstellen), `port/display_bank.{h,cpp}` (`FUN_8000D08C` + `FUN_8000C6B4`, sechs
  RAM-Wirkungen, Strides 0x10CD4/0x1265C, MMIO 0x7D010007 gezaehlt), `port/slot_check.{h,cpp}`
  (Abschnitte **23-26 = 191 Pruefungen**, Instruktionsmodell 1200 Zufallspools).
- **`port/paket_d.{h,cpp}`:** `panel_record` **korrigiert** (a4/a5 vertauscht, +0x38 Halbwort
  statt WORT, +0x3C verschoben, +0x40 Schreibzugriff ueber den Satz hinaus) und ohne
  Zielargument (holt den Slot selbst, `li r3,28` = Selektor 0x1C); `panel_setup` = `FUN_800373A8`
  (vier Quads -750/+750 und 23750/16750); `content_warning`/`content_advisory`; `display_switch`.
- **Panel-Saetze tragen bei +0x38/+0x3C die Emitterdeskriptoren D-264/D-265**
  (`[SDA(0x724)] = 0x800AD768`, `[SDA(0x728)] = 0x800AD774`).
- **`port/text_layer.{h,cpp}`:** vier Grundbefehle `FUN_800109FC/10934/1095C/107F0` +
  `box_frame` + mehrere Formatargumente (`TextArgs`).
- **Regeln P77** (Store = Offset UND Quellregister), **P78** (Dekompilat in Halbwortindizes
  verwischt Register-/Stapelargumente), **P79** (Zeigergrundzustand ist kein Fehler).
- Regression **32 Frames + 53 Anker = 85**; `paketd` 348 OK.

## Batch 80: Port-Schritt 5 Teil D-1 — PAKET-D-EMITTER + RENDER-KERN + TRIGONOMETRIE
- **Neu:** `port/trig_table.{h,cpp}` (**beide** Originaltabellen: Sinus `[SDA(0x174)]`=0x800996B0,
  **0x1400 Worte**, Periode 0x1000, ±32767; Cos-Viertelwelle `[SDA(0x108)]+0x2104`=0x800912CC Q14;
  Zugriff `idx=((w+0x4000)>>3)&0x1FFE` bzw. `q=(p>>12)&0xF; if(q&4)p=-p; idx=p&0x7FFF; if(q&8)x=-x`;
  Zähler für Zugriffe außerhalb `[-0x4000,0x3FFF]` statt Fremdspeicher-Lesen),
  `port/render_core.{h,cpp}` (**13 Kern-Funktionen** (10 waren „fehlend": 0x8001ADB0 Translation {18},
  0x8001AF38 Matrix roh {10}, 0x8001AB90 skaliert, 0x8001AC68 Trail {5C/5D}, 0x80017C5C Farbzeile {07},
  0x80022530/0x800226D0 push, 0x80022DCC pop, 0x80021F64 Winkelmatrix, 0x800213BC Clip+Draw,
  0x800213F4 Clip-Matrix, 0x80017674 Listenkopf, 0x8001758C Clip+Matrix+Draw) + **7 Helfer** (0x8002086C
  Matmul, 0x8001F80C Winkelmatrix, 0x8001D880 Mat×Vec, 0x80020974/0x80020550 Kopie/Skalierung,
  0x8001B7D8/0x8001B7B8 clamp14/15) + `register_render_core`),
  `port/paket_d.{h,cpp}` (**17 Pool-Einträge 262–275 + 313–315**, `ramp_body` 1:1, `rgb_lerp`,
  `max_stat` 0x80032918, `screen_content` (gezählt), `panel_record(dst, PanelArgs)` = Builder 0x80031590
  **mit expliziten Argumenten**, `register_host`), `port/paket_d_check.{h,cpp}` (Abschnitte 17–22 = **157 Prüfungen**).
  **Modi:** `paketd` (Exit 0) und `paketd-ui` (D-265 Paketspur: 21 Pakete/54 Worte; Kernspur 129 Halbworte).
- **Anker:** (17) Trig 22/22 · (18) Kern-Rohwortanker 40/40 · (19) Record-Wortanker+Zensus 52/52
  (D-265 40 bl, D-267 9, D-274 7, D-272 9) · (20) Kern-Verhalten 18/18 (scale_7fff 65536/65536,
  Listenkopf/„Typwort" `0x02000000|0x10000000|rotl(delta+0x80000000,28)&0x0FFFFFFF`, Farbzeile beide Modi) ·
  (21) Record-Verhalten 14/14 · (22) 10/10 Callees + 17/17 Records. **Regression 32 Frames + 49 Anker = 81, 0 Fehler.**
- **Gemessen (CONFIRMED):** Rampen `FUN_800312D4([SDA(0x6E0)]+0x528, **6**, 0x80−(s16(obj+2)&0x7F), obj+0x20)`
  und `(+0x570, **4**, 0x200−…)` — Batch-55-Prosa sagte 5/3 (**P76**: Zahl/Tabelle/Schwelle von der AUFRUFSTELLE
  vermessen). Der Rumpf-Teil testet den VORLETZTEN Eintrag, schiebt EINEN weiter (`p+=12`), testet den LETZTEN
  (`r7=r7+r8; r9=4*r7` → `r9=12*(n−1)`) ⇒ **genau n Einträge, KEIN Überlauf**; Farben aus `tab+r9+4/8`,
  num/den aus dem aktuellen Eintrag, **Nichttreffer schreibt NICHTS** (Anker mit Sentinel 0xA5A5A5A5 prüfen).
- **Regeln:** **P74** Branch-Polarität nur aus Rohworten: `bc 4,BI` springt bei CR-Bit 0, `bc 12,BI` bei 1;
  BI MSB-numeriert (CR0.LT=0, CR0.GT=1, CR0.EQ=2, CR1.GT=5, CR7.LT=28, CR7.GT=29); `mtcrf 0x01` lädt **CR7**
  aus dem NIEDRIGEN Nibble (Belege `bc 4,29`/`bclr 4,28` in FUN_80020C80). **P75** Suchbasis ≠ Zielbasis:
  Farbzeile sucht `state+0x6C4C`, schreibt `state+0xEC4C` ⇒ Zähler wächst monoton (1:1 das Original).
  **P76** geteilte Rumpf-Funktion von der Aufrufstelle messen.
- **Offen (5-D-2, 0,5–1 Batch):** Slot-Allokator `FUN_80037258` + Aufrufer `FUN_800373A8` (vier Panel-Quads
  `{0,0,0xFFFFFD12,0,0x5CC6}` / `{0,0,0x2EE,0,0x5CC6}` / `{0,0,0xFFFFFD12,0,0x416E}` / `{0,0,0x2EE,0,0x416E}`),
  Bildschirminhalt `FUN_8003C9FC`/`FUN_8003C880`, Anzeigeschalter `FUN_8000D08C`.
  **Schritt 5 ≈ 75–80 %; Rest 3–4 Batches (5-C-2 1,5–2 · 5-D-2 0,5–1 · 5-E 1 optional).**

## Batch 78: Port-Schritt 5 Teil B — SPEICHERDIALOG + TEXTSCHICHT (**Menü sichtbar**)
- **Neu:** `port/text_layer.{h,cpp}` (Textring `[SDA(0x54)]` 1:1 mit 12-B-Slots,
  printf-Untermenge `%s %u %d %c %x` + Breite + `'\n'`, Kasten `FUN_8000E408` =
  `FUN_8000F1E0(0,0x2B,0x40,4,0)`, `clear_lines`, zentrierte Zeilen, Zeichenraster
  **0x40 x 0x30**: 40 Spalten CONFIRMED aus Zeilenstride 0x104, Zeilen STRONG INFERENCE),
  `port/service_text.{h,cpp}` (`ServiceTextSink` = Brücke Zeilen→Text; Seitenaufbauten
  `FUN_8002E090` (8 Zeilen, Titel `[SDA(0x20C)]+0x44` bei (0x19,3)) / `FUN_8002ED70`
  (16 Zeilen, Titel `[SDA(0x214)]+0x148` bei (0x1A,1)), danach `centered(...2,0x2B,6)`),
  `port/service_dialog.{h,cpp}` (**Kette** D980/D3FC/D364/DE3C/D358/D52C/DB98/DA80/E440/E55C),
  `port/service_dialog_check.{h,cpp}` (Instruktionsdecoder, Abschnitte 8–11, `dump_service_ui`).
  **Modi:** `service` (Berichte) und **`service-ui`** (sichtbare Ausgabe).
- **Kette (CONFIRMED, aus DISASSEMBLY):** `FUN_8000D980` Zustand in `*(u8*)(ctx+2)`;
  0 → `(cfg+0x2E!=0)?0x10:1`; 1 → `FUN_8000D364` (Vergleich lebender Block `+0x58` vs.
  Sicherung `+0x48`, gleich → sofort fertig); 2 → `FUN_8000DB98` (Ja/Nein, `input & 0x64`,
  TEST-Switch `(input>>4)&8`, Labels `+0x1DC`/`+0x1E4` als **Adresse** verglichen);
  0x10 → `FUN_8000DA80` (Meldungsindex = **Boolean** `(cfg+0x2E!=0)`, y=0x2D, Farbe 6,
  **kein Durchfall**); dann Trampolin `[SDA(0xE4)]` → Pool-Index 14 → `FUN_8000D358`
  (`lwz r0,0x14(r2); addic r3,r0,0x58; b 0x8000D52C`) → 16 B `+0x58→+0x48` + NVRAM-Store
  `FUN_8000DEE8` (gezählt); Zeitgeber `cfg+0x34 = 0x3A` (58 Zählbilder).
- **Texte (Adressen):** `0x80086254` "YOU DID NOT SAVE.\nDO YOU WANT TO SAVE ? [ / ]",
  `0x8008628C` "NO MODIFY SETTING", `0x800862A0` "NOW SAVING",
  `0x800862AC` "DO YOU WANT ALL FACTORY SETTINGS ? [ / ]", `0x800862DC` "SURE ? [ / ]",
  `0x80086304` " YES ", `0x8008630C` " NO ", `0x800862F0` "BACKUP MEMORY ERROR" (unbenutzt).
  `[SDA(0x70)]=0x8008CEB0`: +0x00/+0x08/+0x10 = die drei Hilfetexte, +0x30.. = 5×16-B-Profilblöcke.
- **Anker (Exit 0):** (8) 65/65 ROM-Wortanker, (9) 30/30 Dialogtexte, (10) 17/17 Verhaltensfälle,
  (11) sichtbare Ausgabe OK (**37/37 Labels, 20/20 Werte, 537 Rasterzellen, 0 unbekannte Formate**).
  **Regression 32 Frames + 37 Anker = 69, 0 Fehler.** Ghidra 2075→2075.
- **Regeln:** **P68** ein Gate wird nicht doppelt geprüft (idx 82/83 hatten es einmal richtig, einmal
  invertiert ⇒ jedes Profil gesperrt; Anker muss die WIRKUNG messen); **P69** „Liste“ ist keine Form —
  8 Umschaltzeilen übergeben **Inline-Strings** (Adressarithmetik), nur idx 78 ist eine 2-Einträge-
  Zeigerliste; **P70** Dekompilat-Ausdruck zu gefaltetem Idiom gegenprüfen (`rlwinm MB=28,ME=31`
  maskiert das **niedrige** Nibble; Warnsignal = Adressüberlauf/unerreichbarer Zweig).
- **Gemessen (HYPOTHESIS):** DB98 und DA80 teilen die Zustandszelle (`state_ptr+2`); im Pfad
  „EXIT mit Änderungen“ (`cfg+0x2E==0`) entfallen Meldung+Aktion, bei `cfg+0x2E==1` laufen sie.
- **Offen:** kein Glyphen-Rendering (Zeichenzellenpool nur gezählt); 20 Bildschirmrahmen nur teils
  (2 Optionsseiten + Dialog); COIN-Zeilentabelle (Halter `FUN_80080928`); Paket-d-Emitter; NVRAM.
  **Nächster Schritt: 5-C Bildschirmrahmen (1–1,5 Batches), Rest Schritt 5 = 4–4,5 Batches.**


## Batch 77: Port-Schritt 5 Teil A — SERVICEMENUE (Mechanik + Daten)
- **Neu:** `port/service_menu.{h,cpp}` (Tabelle **aus dem Bild**, `MenuSession`, Vertrag 0/1,
  `register_menu_screens`), `port/service_rows.{h,cpp}` (**37 Zeilenspezifikationen**,
  `ServiceRowEngine::frame`, `RowListDriver` = FUN_8000DCEC + FUN_8000DDD4, 4-B-Zeilenarrays),
  `port/service_check.{h,cpp}` (Instruktionsdecoder, 7 Abschnitte). Modus **`service`**.
- **Anker (Exit 0):** (1) SDA-Anker, (2) 20/20 Namen + 30/30 Deskriptor-Indizes geprueft,
  (3) 31/31 Zeilenindizes (7er={47..53}, 8er={63..70}, 16er={73..88}, **Stride 4**),
  (4) **37/37 ROM-Wortanker** je Zeile aus den rohen Instruktionswoertern (lwz, Feld-rlwinm
  aus Shift+Maske vorhergesagt, rlwimi-Schreibmaske, Wrap-`li`, Farben 5/6, `andi. 0x98`,
  `cmpwi`-Grenzen), (5) 17/17 Verhaltensfaelle, (6) Dispatcher mit echter Bildtabelle,
  (7) Navigation. **Regression 32 Frames + 32 Anker = 64, 0 Fehler.**
- **Regeln:** **P65** Dekompilate verschlucken die Inkrementgrenze (Klemmung statt Wrap, idx
  63/64/77/83); **P66** Rueckschreibung ist `rlwimi` (SHIFT = Feldlage, MB/ME = Maske MSB);
  **P67** Gate-Zuordnung nur ueber die Instruktionsadresse pruefbar.
- **Offen:** Text-/Node-Schicht (nur `RowTextSink`-Senke + Zaehler), Speicherdialog
  (`FUN_8000D980`-Kette), 20 Bildschirmrahmen, COIN-Zeilentabelle, Paket-d-Emitter.
  → **In Batch 78 erledigt:** Textschicht + Speicherdialog (s. Block oben); offen bleiben
  20 Bildschirmrahmen, COIN-Zeilentabelle, Paket-d-Emitter.

## Batch 76: Port-Schritt 4 — AUDIO-HOOKS implementiert und verankert
- **Neu:** `port/audio.{h,cpp}` (Adressen/Offsets, `scale63`/`scale63_original` (Magic-Multiply),
  `SoundKind`/`SoundEvent`/`AudioEventMap` (75 gemessene IDs/116 Stellen), `AudioBackend` +
  `LoggingAudioBackend`, `AudioStats`, `AudioStateBlock`, **`AudioEngine`** = alle 13
  Treiberfunktionen + 3 Trigger, `audio_host_frame`), `port/audio_binding.{h,cpp}` (**15 Hooks**,
  `kAudioHookAddrs`), `port/audio_check.{h,cpp}` (Offline-Instruktionsdecoder, Trampolin-Nachweis,
  Verhaltensanker, Zellen-Rettung: `check_audio(ram, reg, engine)` — **Registry und Engine MÜSSEN
  dieselbe Instanz sein**).
- **Selbsttest-Modus `audio`** (Exit 0): (1) SDA-Anker, (2) **40/40 ROM-Wortanker**, (3) 15/15 Hooks
  + Trampolinpfad, (4) ID-Dekodierung 75/116 + Gruppen-Zensus, (5) Variante/Gate + Kontrollflussprobe,
  (6) Queue (Kursor-Alias/Modusfilter/Busy), (7) Lautstärke, (8) Logger.
- **Fakten (am ROM nachgemessen):** Variantenflag = `CR7.LT` = `cfg+0x48` Bit 23 (Flag 0 ⇒ +0x20);
  Gate = `CR7.EQ` = **Bit 1** von `*[SDA(0x240)]+8`; Nibble-Reihenfolge von MSB: **LT, GT, EQ, SO**
  (belegt: `bgt cr7` = Busy = Bit 6, `beq cr7` = Bit 1). Wire = `id << 16`; Queue-Maske 0x3F.
- **P62 (wichtig):** der Volumen-Encoder benutzt **ZWEI Zähler** (`r28` runter, `r30` hoch, genullt
  bei `0x8000EA5C`) — die Batch-61-Prosa ließ einen Zähler weiterlaufen (Ergebnis wäre 1 statt 42 Pulse).
  Der Verhaltensanker hat es beim ersten Lauf aufgedeckt. **P63:** der Modusfilter vergleicht den
  **rohen** Eintrag gegen `0x902` (in der Wire-Form unerreichbar). **P64:** Exit-Code-0-Anker finden
  solche Fehler nicht — Sollwerte nachzählen.
- **Lautstärke 1:1:** 64 Schritte runter (Maske 0xFF) + gezielt hoch (0xFF/0xF0/0x0F); 20/20 aus
  Zustand 0 ⇒ Level 42/42, state+0x11/+0x12 = 20, 318 Reg-5-Writes, 128 Klemmanläufe. Kein Readback.
- **Regression:** 32 Frames + **27 Anker** = 59, 0 Fehler; Artefakte `_m76_audio_report.txt`,
  `_m76_regression_anker.csv`. **Noch offen für Ton (außerhalb):** ID→Sample (68K `830a08.7s` + PCM-ROMs),
  RF5C400-Einbettung, Mixer-Gain. **Host-Pflicht:** `audio_host_frame()` je Frame aufrufen.

## Batch 75: Farbstufe II (2b-II Teil 9) — vier Offline-Reste geschlossen
- **Neu:** `port/voodoo_color_stage.{h,cpp}` (Bitfelder `cp_*/am_*/fm_*/bm_*` = voodoo_regs.h 1:1,
  `combine_color` (volle MAME-Gleichung), `combine_color_subset_supported` (GL-Untermenge der 10
  gemessenen Pfade), `alpha_test_pass`, `chroma_key_test` (NICHT angewandt), `fog_write`/
  `fog_decode_table`/`fog_table_blend`/`apply_fogging_table`, `compute_wfloat`, `float_to_int32/64`,
  `clamped_argb_channel`); `sharc_texture` erweitert (Formatklassen, `PaletteTable`/`palette_ncc_write`/
  `palette_load_clut_rgb`, statische Tabellen RGB332/A8/I8/AI44, `texture_texel_lookup`,
  `bilinear_filter` (Maske 0xF0!), `texture_fetch_texel`, `texture_uses_bilinear`);
  `ScreenTriangle::ColorState`; GL: **zweites Programm** (`glcolor`/`glcolorsetup`/`glcolorsample`)
  mit `texelFetch` + MAME-Ganzzahlfilter + Gleichung + Alpha-Test + Nebel, `set_palette_image`,
  `read_pixel`; Anker **Abschnitt (16)** in `vertex_check.cpp`.
- **Regel P59 (wichtig):** die Batch-64-Maske `& ~0xC00` auf 0x3A-hi war FALSCH (löschte
  `cca_subpixel_adjust`/`texture_enable`); unmaskiert 606/606 im Farbpfad-Katalog, maskiert 0/606
  (`scripts/m75_fbzcp_mask.py`). `render_sink.cpp` führt jetzt den Rohwert.
- **Regel P60/P61:** Abdeckung zählt (volle Stufe = 20 von 2997 Dreiecken, Frame 0/196608 verdeckt);
  Host-Größen ohne Opcode (Palette 0x324..0x380, chromaKey/chromaRange) werden nicht erfunden.
- **Korrektur B74:** MAME-Faktor ist `mselect+1` → `(iterA+1)/256` (nicht `iterA/256`).
- **Anker bit-exakt:** CLUT 256/256; Fog-Tabelle 64/64 Blend + 64/64 Delta gegen `capture/frame_fog.raw`;
  `glcolorsample` CPU==GPU (`0x3A3F44`). **Modi:** `port_gl.exe glcolor|glcolorsetup|glcolorsample`;
  Regression 32 Frames + 21 Anker = **53, 0 Fehler**. Rest 2b-II: **1 Live-Dump (0x2236b, R13/MR1B)
  + ~1 Batch Integration**.

## Batch 69: S/T/W/Alpha-Stufe (2b-II Teil 3) — BIT-EXAKT verankert
- **Neu:** `port/voodoo_triangle.h` (`TriangleRegs` = 18 FLOAT-Register + area2/inv_area/cmd,
  Registerordnung+Namen), `port/triangle_setup.*` (`RecordVertex`, `read_record_vertex(-s)`,
  `setup_triangle`), `SharcState::kSharcChainBase=0x29DF0`, `ScreenTriangle::regs/has_regs`,
  `ScreenVertex::{s,t,attrw,alpha}`, GL-Modus `glsetup`, Anker-Abschnitt (9).
- **Anker (bit-exakt):** DMA-KETTENPUFFER 0x29DF0 des SRAM-Dumps = Registerwerte des ZULETZT
  emittierten Dreiecks (6 Koordinaten ab +0x00, 12 FLOAT-Register ab +0x12, `1/det` bei +0x1E);
  Vertizes = Pool-Records 3/1/0 (Match über +7/16,+8/16). 12/12 Register reproduziert
  (10 bit-exakt, 2 nur `-0.0` statt `+0.0`), `1/det` bit-exakt.
- **Feldbedeutung:** `+6`=16/|z|=fstartW=Skalierung; `+7/+8`=Bildkoord. x.4; `+9/+10`=S/T mit
  `fstartS/T=(+9/+10)*(+6)`; `+11`=Alpha=fstartA; Gradienten = baryz. Gradienten der
  W-skalierten Größen über Pixel; `ftriangleCMD` = Kommandowort (nicht gerechnet).
- **Zweitanker:** echte Registerspur Frame #2942 (`analysis/_f2942_rawtrace.txt`, Skript
  `m69_regtrace_probe.py`): 73/74 Dreiecke vollständig, Reihe 73/73, 444/444 Koords x.4-quant.
- **Offen (2b-II Teil 4):** QUELLE der Laufzeitfelder +6/+9/+10/+11 (Walk-/DSD-Stufe, `+9`
  HYPOTHESIS); Producer der Kettenworte (kein F→R-Transfer im ISA; FPACK/MANT 0× im Programm).
- **Zahlen:** `glsetup` 1 Dreieck; `glown` 2999 Dreiecke, davon **20 mit Registerdaten**;
  Regression 32 Frames + 9 Anker = 41, 0 Fehler. Werkzeuge: `m69_{chain_anchor,regtrace_probe,
  dm,dis,workstream}.py`; Regeln P37/P38.

## Batch 67: SHARC-Stromgrammatik VOLLSTÄNDIG + Blockgrammatik korrigiert + Asset-Herkunft
- **Grammatik-Quelle ist NICHT `_consume_extract.txt` allein**: dessen Spalte `Verbrauch` ist ein
  DUPLIKAT von `Reads` (Extraktor druckt `n` zweimal), und `Reads` = Reads im HANDLER-RUMPF inkl.
  Fehlerpfad (obere Schranke). Nutzbar nur als Handler-Adresstabelle. Der echte Wert kommt aus dem
  **gelaufenen Pfad im Disassembly** + Stromprobe. Werkzeuge: `scripts/m67_grammar.py` (gemeinsame
  Grammatik), `m67_stream_probe.py`, `m67_stream_sweep.py`, `m67_index_probe.py`, `m67_opcode_census.py`.
- **Port-eigener Strom läuft jetzt vollständig**: 5221 Worte, 580 Pakete, 29 distinkte Opcodes,
  109×0x56, 100×0x5D, 39×0x66, 111×0x10 (Sollwerte in `port_selftest vertex` Abschnitt 5).
  Dump: `port_selftest frame capture\ppc_poc_input_0.bin capture\poc_ref_stream_0.txt --ram -o <datei>`.
- **Kernwerte**: 0x5D = 16 Nutzlast (17 gesamt: 15 Rumpf-Reads + Index); 0x0B = PRÄFIX-Opcode
  (1 + Nutzlast des Unterschalters, Handler 0x201DD); 0x68 = 2+2*(count>>1); 0x04 = 4 (5 Reads);
  0x1D/0x1E = 2; 0x1F = 6; 0x21 = 6; 0x26 = 6; 0x2D = 9; 0x57 = 1.
- **Blockgrammatik (`render_sink.cpp block_packet_words`) war falsch** (PPC-Dekompilat-Längen):
  0x04 38→5, 0x26 5→7, 0x2D 11→10, 0x5C 16→18, 0x5D 16→17, 0x65/0x66 3+(cnt/6)*6→3+6*cnt,
  neu 0x08=3, 0x1F=7, 0x21=7, 0x68=3+2*(cnt>>1), 0x0B rekursiv. Wirkung kanonischer Dump:
  **118/118 Blöcke zerlegt (vorher 86/32), 452 Pakete, 379 Draw-Aufträge (vorher 232)** — Anker
  in `render_check.cpp` neu verankert (alte Werte im Kommentar). `port_gl.exe gl` zählt jetzt 379.
- **Herkunft**: SHARC hat KEIN Programm-ROM (MAME-Set); Boot = DMA6 aus dem Shared-Fenster
  (ext 0x400000) -> die PPC-Firmware-Uploads (0x20040/0x22800, LZSS). Der Boot-Code schreibt die
  Zeigertabellen SELBST: 0x2007A–0x20083 füllt Wort 0..511 mit `0x29E0F` und 512..4095 mit
  `0x01401000` (Datenbereich ab 0x1401000) -> die alte Aussage "kein Store auf 0x01400000" ist FALSCH
  (der Store ist register-indirekt über I0). Tabelleneinträge = DM-WORTadressen (Block/Bibliothek
  entweder intern 0x29xxx oder privat 0x140xxxx).
- **Index-Raum = statische Geometrie-Bibliothek**: über alle 21 Ströme 136 distinkte Indizes im
  privaten RAM, jeder mit EINDEUTIGEM Handler; Handler-Satz {0x6C,0x6E,0x72,0x74,0x83,0x8D,0x8F}
  (= Inline-Vertex-/Unpacker-Familie; 0x74 = 0x237DA "Mesh"). Record-Layout (an Index 7 bit-exakt):
  `{param|handler} {count|flags} 4×Vertex(3×10 Bit)`. **Port-Frame-0-Handler: 0x6C:73, 0x83:55,
  0x6E:47, 0x74:5 -> der "Mesh-Emitter 0x37DA" ist nur 5/217; die Record/Unpacker-Familie ist der Hebel.**
- **Port-eigene Geometrie ist demonstriert** (Anker Abschnitt 7): eigener Tabelleneintrag + eigener
  Record (Handler 0x37C0, 4 gepackte Vertizes) -> Dreieck bit-exakt wie Ground Truth; verschobene
  Vertizes -> andere Lage, 3/3 aus eigenen Daten. API: `SharcState::set_table_entry/poke_dm`.

## Teilstrang 2b-I (Batch 66): Vertex-Transform der SHARC-Kette
- Dateien: `port/sharc_state.*` (SHARC-Datenzustand als EINGANG: DM-Abbild `kSharcDmBase=0x20000` LE-u32,
  Pointer-Tabelle `0x01400000`, `resolve/read_block`, `SharcBlock{selector,param,count_a}`,
  Pfadsuche `capture/sharcdumps/` -> `C:/Users/Arcade/sharcdumps/`),
  `port/sharc_consumer.*` (Wortverbrauchsgrammatik, Registerzustand, Slotauflösung, Emitter-Dispatch,
  Register-/Viewport-Pakete gehen ZUSÄTZLICH an die Senke), `port/vertex_transform.*` (Transform `0x20CFF`
  in **f32**, 10-Bit-Entpackung, `emit_237c0`, `MatrixState` + `MatrixSource`, `measured_344_matrix()`),
  `port/vertex_check.*`; Senke: `RenderSink::draw_triangle(ScreenTriangle)`; GL-Backend: Shader-Durchlauf.
- Modi: `port_selftest vertex` (Exit 0), `port_gl.exe glstream` (zeichnet 3 Dreiecke -> `_m66_gl_frame.ppm`,
  Box x 345..503 / y 215..276, 5014 weiße Pixel). `gl` (Dump) unverändert: 232 Aufträge gezählt.
- Sollwerte: Strom 7556 Worte/592 konsumiert/28x0x56/3x0x37C0+25x0x37DA/Abbruch 0x0208@591;
  `Tabelle[7]=0x29EC6` (Sel 0x37C0 a=3), `Tabelle[15]=0x29F7A` (Sel 0x37DA a=1);
  Blockvertizes bit-exakt; Emission #1 = Ground-Truth-Burst B00.
- Regression: `python scripts\port_regression.py` = 32 Frames + 5 Anker (`abi`/`cfg`/`render`/`hit`/`vertex`).
- **Offen (2b-II, revidiert nach Batch 67 auf ~6–9 Batches):** Record-/Unpacker-Familie der
  Handler {0x6C,0x6E,0x72,0x74,0x83,0x8D,0x8F} (liest Vertizes aus I4 = Record/Bibliothek,
  10-Bit- und 16-Bit-Feldvarianten; 0x37DA ist EIN Mitglied davon — kein eigener Arbeitsstrang mehr);
  dann S/T/W/Alpha-Burst (13 weitere Register), Koeffizientenquelle der Matrix (nicht im Dump;
  HYPOTHESIS {03}-Handler), Boot-Frames 1/2/3 (12 offene Blöcke je Frame, kein Referenzstrom).

## GL-Senke: RDP-Falle + statische Verlinkung (R370/R371, Batch 154, CONFIRMED)
- Ein `port_gl.exe`-Lauf **wartete** in einer RDP-Sitzung in einem **modalen Dialog
  des AMD-Treibers** ("LoadLibrary failed with error 87: Falscher Parameter") -
  Signatur: CPU 0,062 s, kein Output, reproduzierbar. `SetErrorMode` unterdrueckt
  IHN **nicht** (gemessen: Fenster mit Titel `Error` bleibt, Exit 87).
- **Fix (Umfeld, NICHT im Repo - `port/build/` ist gitignoriert):** Software-OpenGL
  von `pal1000/mesa-dist-win` (Asset `mesa3d-<ver>-release-mingw.7z`), daraus
  `x64\opengl32.dll` **und** `x64\libgallium_wgl.dll` nach `port/build/` neben
  `port_gl.exe` legen (die kleine `opengl32.dll` ist nur die Huelle). Danach:
  `GL_VERSION=4.6 (Core Profile) Mesa … | GL_RENDERER=llvmpipe`; die neun
  GL-Anker laufen **9/9** (vorher 9x GL-TIMEOUT). `GALLIUM_DRIVER=llvmpipe`
  erzwingt den Software-Treiber (sonst versucht Mesa erst zink/Vulkan).
- Die drei Harness-Binaries sind **statisch gelinkt** (`-static`: `Makefile`
  `LDFLAGS` + `scripts/port_build.ps1`) und laufen **ohne msys im PATH**
  (gemessen: `port_selftest vleaf` Exit 0 ohne msys-Eintrag). Systembibliotheken
  (`opengl32`, `gdi32`, `user32`, `kernel32`, `api-ms-win-crt-*`) bleiben dynamisch.
- Der Harness schaltet die Fehlerdialoge der Kinder ab (`SetErrorMode`, vererbt)
  und meldet den Exit-Code `0xC0000135` als **DLL-FEHLT** (zaehlt als FEHLER).

## Bauen/Testen (immer von Projektwurzel)
- **Bau (ab Batch 132, R310 - INKREMENTELL, immer so):**
  `$env:PATH = 'C:\Users\Arcade\msys64\ucrt64\bin;' + $env:PATH`
  `& 'C:\Users\Arcade\msys64\ucrt64\bin\mingw32-make.exe' -j16`
  (`clean` erzwingt den Vollbau). Nur so aendern sich Objekte einzeln; der alte
  g++-Einzeiler ueber alle `.cpp` ist abgeloest und bleibt nur als Notnagel fuer
  Sonderfaelle. `Makefile` im Projektroot, Objekte in `port/build/obj`.
- Bau (alt/GL): `& .\scripts\port_build.ps1` (g++ UCRT64; baut `poc/ppc_native/ppc_poc.exe` + `port/build/port_selftest.exe`);
  `-Gl` baut zusätzlich `port/build/port_gl.exe` (GL-Senke, `-DPORT_RENDER_GL`). Laufzeit braucht
  `C:\Users\Arcade\msys64\ucrt64\bin` im PATH. Achtung: das Skript bricht bei JEDER g++-Warnung ab.
- `port_selftest.exe abi`      -> ABI gegen ROM-Bild (20 SDA-Zellen, Exit 0 = OK)
- `port_selftest.exe cfg`      -> cfg-Prüfanker (Profile/Ladepfad/COIN/Hook/Screen, Exit 0 = OK)
- `port_selftest.exe render`   -> RAM-Kette == PoC-Kern (19 Dumps), Senke/Blockzensus/Commit, Exit 0 = OK
- `port_selftest.exe audio`    -> Audio-Anker (Port-Schritt 4): 40/40 ROM-Wortanker, 15/15 Hooks
  (+ Trampolinpfad), ID-Dekodierung 75/116, Variante/Gate, Queue-Mechanik, Lautstärke-Zähler, Backend
- `port_selftest.exe service`  -> Servicemenü (37 Zeilen) + Dialogkette-Berichte, Abschnitte (1)–(11)
- `port_selftest.exe service-ui` -> **sichtbare Textausgabe** (beide Optionsseiten als Zeichenraster,
  Dialogfrage, SAVE-Pfad; seit Batch 88d-1 auch der **Grafik-/Ladeteil** (Warteschlange,
  Arbeitsobjekt, Zellpool-Ausschnitt, Bankeintrag, Zaehler); druckt bei Exit 0 `AUSGABE OK`)
- `port_selftest.exe paketd`   -> Paket-d-Anker **(17)–(22)**, 157 Prüfungen, Exit 0 = OK (Paket-d-Emitter,
  Render-Kern, beide Trigonometrietabellen)
- `port_selftest.exe paketd-ui` -> sichtbare Paketspur von D-265 (21 Pakete) + Kernspur (`AUSGABE OK`)
- `port_selftest.exe ranking` -> **RANKING-Schirm** (Batch 83): Abschnitte (30) ROM-Wortanker/Texte/
  Zensus, (31) Blocktabelle aus den Rohworten, (32) 12 Verhaltensfaelle (Lesen/Pruefsumme/Waechter/
  Schreiben/Automat), (33) sichtbare Ausgabe; Exit 0 = OK
- `port_selftest.exe input`   -> **Testmode-Tastenzugang** (Batch 82): Abschnitte (27) Herkunft
  + Zensus, (28) Wirkung ueber das echte Menue, (29) Konfiguration; Exit 0 = OK
- `port_selftest.exe input2`  -> **allgemeine Eingabeschicht** (Batch 86): Abschnitte (42) ROM-Wortanker
  Waffenpfad + Sprungziele + Datenfolgen, (43) Verdrahtung Host->Panelwoerter, (44) Panelhistorie,
  (45) Statusmaschine, (46) Mapping + Menuewirkung, (47) Spur; Exit 0 = OK
- `port_selftest.exe input-map` -> sichtbare Rohsicht + 16 Bilder Waffenpfad (`AUSGABE OK`)
- `port_selftest.exe testmode` -> sichtbare Menue-Sitzung ueber die Taste (`AUSGABE OK`)
- `port_selftest.exe testmode-live [sekunden]` -> echte Tastatur live (blockiert; Handbetrieb;
  `PORT_TEST_SWITCH_KEY`/`_BIT`/`_MODE` konfigurieren Taste/Bit/Hold|Toggle)
- `port_selftest.exe abi-call` -> 15 Funktionen direkt vs. via Deskriptor (aus `capture/` starten!)
- `port_selftest.exe frame <dump> <ref> [--ram] [--stats] [-o out]` -> Frame durchs Trampolin; `--ram` = RAM-Kette
  (Ausgabe bewusst PoC-identisch; Diagnose nur mit `PORT_TRACE=1`)
- `port_gl.exe gl`             -> GL-3.3-Senke headless (Status-Rückleseprüfung, PPM, Exit 0 = OK)
- **Vorflug/Nachflug (STANDARD ab Batch 137): `python scripts/preflight.py before` |
  `python scripts/preflight.py after <hex>...`** - bündelt R207 tails/check/sanity/
  nachzuegler, R216 A-D, P100, R222 und die Regression in EINEM Aufruf (Exit 0 = sauber).
- `python scripts\port_regression.py` (**Stand Batch 143: 32 Frames = 16 PoC + 16 RAM
  + 260 Anker, 0 Fehler**; `--baseline` schreibt die Frame-Baseline; Artefakte u.a.
  `analysis/_m88d_regression.txt`). **NICHT mit `-X utf8` aufrufen** - das bricht die
  `textfmt`-Ausgabe (`stdout=None`-Absturz in `port_regression.py`).
  **Die Schritte 87/88/88b/88b-2/88c/89 sind in `/memories/repo/eingabeschicht.md` gefuehrt,
  88d-1 in `/memories/repo/ladeteil.md`.**
- `port_selftest.exe vleaf` -> **Waehler-Blaetter 2** (Anker (230)-(233); Stand Batch 143:
  43 Koepfe / 1564 Worte / 6256 B, FNV-1a `2A55E5B8`, Faelle 2/2, **122/122**, 44/44, 44/44);
  Regressionszeilen `vleaf-anker`, `vleaf-woerter-anker`, `vleaf-b135-anker`,
  `vleaf-b143-anker` (R219/R222/R216-A-Zeilen + die LZSS-Naht mit ROM-Alias).
  Modus `leaves` = dieselbe Familie.
- **Artefakte mit `Set-Content -Encoding utf8` schreiben** - PowerShell `>` schreibt UTF-16
  und bricht die Python-Werkzeuge (R297-Klasse).

## Schritt 1: cfg (Dateien)
- `port/include/port/cfg.h` + `src/cfg.cpp`: `cfg_off`-Offsets, `cfg_sound`/`cfg_input`/`cfg_coin`,
  `kFactoryProfiles[5]`, `CfgBlock` (Zugriffsschicht aufs RAM-Abbild, KEIN struct),
  `read_factory_profiles`, `load_factory_defaults` (= idx 34), `apply_default_block_to_active` (= FUN_8000D52C).
- `cfg_binding.{h,cpp}`: der EINE Hook `FUN_80026C34` (nicht 0x80026C40 — das liegt im Rumpf).
- `service_screen.{h,cpp}`: Vertrag (a) Init / (b) Frame 0=weiter 1=fertig + Schalterabbruch
  `(cfg+0x30>>4)&8` (Bit 7); `register_screen(reg, ScreenSlot{init,frame}, screen)`.
- `cfg_check.{h,cpp}` + CLI-Modus `cfg`; Beleg `scripts/m63_cfg_map.py` -> `analysis/_m63_cfg_map.txt`.

## Schritt 2: Render-Transport/Senke (Dateien)
- `port/render_sink.h` (RenderSink: **Pakete** + Draw-Aufträge, KEINE Strombytes), `render_transport.{h,cpp}`
  (1:1-Kette auf dem RAM-Abbild: `walker`/`object_loop`/`state_diff`/`group_setup`+`group_packet`/`record_copy`/
  `texture_windows`/`dirty_drain`/`draw_index`/`commit_frame`/`terminator`/`cursor_save|restore` + 12 Emitter),
  `render_sinks.h`+`render_sink.cpp` (`TransportRecorderSink` = Prüfpfad, `DrawSink` = Produktionspfad mit
  `RenderState`/`DrawOp`/Blockzensus), `render_check.{h,cpp}` (4-fach-Anker), `render_gl.{h,cpp}` (GL 3.3, headless FBO).
- Zustandsquelle = RAM-Abbild; der Dump ist nur Testeingang (Anfangszustand + `r3`/`r4` = `rec_array`/`count`).
  Der Spiegel setzt zusätzlich **Laufzeit-Anker**: `[[r2+4]]`=Frame, `[r2+0xF8]`=State, `[r2+0]=Bank`,
  Zeigerarray bei `rec_array`; `[r2+0x100/0x10/0x14/0xFC/0x104]` sind **statisch** und werden nur geprüft.
- Gemessen (Batch 67 korrigiert): kanonischer Dump `ppc_poc_input_0.bin` = 118 Datensätze, **118 Blöcke
  zerlegt / 0 offen** (452 Blockpakete), **379 Draw-Aufträge** (Batch 64 hatte 86/32, 270, 232);
  GL-Senke: 379 Aufträge **ohne Vertex-Transform** gezählt (Teilstrang 2b).

## Layout/Fakten (CONFIRMED, am Bild gemessen; `analysis/_m62_abi_map.txt`)
- RAM 0x80000000..0x803FFFFF (4 MB); Bild `rom/build/830d01.27p.main.bin` (0xAE298 B);
  **Byte-Summe = 0x0321F4C4** (Algorithmus: Summe Bytes mod 2^32) = Integritätstest.
- r2 = SDA-Basis **0x800ADA5C**; Pool 0x800ACB08 (327×12) endet **exakt** bei r2.
  Pool-Index 0 = `fn 0x80000000` (Bildbasis) = **kein** Funktionseinstieg.
- Trampolin 0x8000005C: `lwz r0,0(r11)/stw r2,0x14(r1)/mtspr CTR/lwz r2,4(r11)/bctr`.
- Matrix 0x800AA380 = **200 4-B-Zeiger** in den Pool (Zeilenstride 0x14), Ende = SDA(0x5F8)=0x800AA6A0;
  124 distinkte Indizes; „kein Handler“ = **Index 114** (fn 0x8004A288, 67 Zellen), dann Index 124 (7).
- Typzeilen `[SDA(0x300)]=0x8009E218`, Stride 0x5C (Zeilenanzahl 40 vs 79 noch offen);
  `+0x00/+0x04/+0x08` = Pool-Zeiger, `+0x58` = Matrixbasis.

## Fallstricke
- (P13) **Die Kette schreibt keine Strombytes**: Pakete gehen an die Senke, `frame+0x18` bleibt Zahl (Cursor).
- (P14) Host-Seite (IRQ/Komm/Dirty-Queues 1+2) wird **gezählt**, nicht emuliert (`HostStubStats`).
- (P15) Unbelegte Block-Opcodes **brechen die Zerlegung ab und werden gezählt** (kein Raten); Sollzensus im Anker.
- (P16) **Doppelte Negationen getrennt transkribieren**: `FUN_80017E60(a,b,c)=FUN_80019ED0(-a,-b,c)` und
  `FUN_80019ED0` negiert intern erneut — Zusammenlegen invertiert die Fog-Kurve (46 Halbworte).
- Blockgrammatik (Batch 67 vollständig): Längen jetzt aus der SHARC-Handler-Disassembly, nicht aus dem
  PPC-Dekompilat (`0x10`=16, `0x0B` rekursiv 1+Unterschalter, `0x18`=7, `0x17`=4, `0x08`=3, `0x1F`=7,
  `0x21`=7, `0x26`=7, `0x2D`=10, `0x04`=5, `0x5C`=18, `0x5D`=17, `0x63/0x64`=3+3*cnt, `0x65/0x66`=3+6*cnt,
  `0x68`=3+2*(cnt>>1)); damit 118/118 Blöcke des kanonischen Dumps zerlegt. Offen nur noch Boot-Frames.
- **Dumps werden überschrieben**: `POC_TARGET=n` schreibt immer `capture/ppc_poc_input_<n>.bin`;
  ein Injektionslauf kann einen früheren Dump zerstören -> vorher wegkopieren.
- Dump-Fenster beim Spiegeln **wortweise BE** schreiben (Container halten dekodierte u32).
- `port_selftest frame`-Ausgabe ist absichtlich identisch zur PoC-CLI (Grundlage von port_regression.py).
- PoC-Kern liegt jetzt in `poc/ppc_native/ppc_core.h` (Split aus main.cpp; Sicherung `main.cpp.m62bak`).
  PoC = Regressionstor: nicht umbauen, nur einbinden.
- (P9) `cfg` als Zugriffsschicht aufs RAM-Abbild, nicht als C++-struct (Offsets sichtbar halten).
- (P10) Werte, die im Bild stehen, zur Laufzeit LESEN und gegen die Solltabelle prüfen.
- (P11) Feldzensus liefert **Instruktions**adressen — Hooks am Funktions-**Einstieg** registrieren
  (Prolog-Bytes am Bild gegenprüfen).
- (P12) Eine **Blockkopie ist kein Schreiber**: Felder ohne `stw` (z.B. `cfg+0x48`) kommen per
  `memcpy` (`FUN_8000D1A0`) hinein — Suche über Speicher-zu-Speicher-Helfer.
- Ein byte-genauer **cfg-Frame** ist nicht möglich: kein Referenzstrom mit offenem Servicemenü
  (Coverage Paket e 4,9 %, Options-Zeilen 0 %).

## Batch 152: der 251-Insn-Zuschnitt von `8005382C` + die Naht `0x80055414` (2026-09-25)
- **Fuenf neue Koepfe (223 Insn) in `port/voter_leaves2.{h,cpp}`:** `l687ec_step`
  (`800687EC`, 46, 3-Weg-Automat ueber `byte[SDA(0x550)]`), `l67c50_tick`
  (`80067C50`, 6, Zaehler +0x10, altes Byte +0x14), `s68b20_fill` (`80068B20`,
  24, 16-B-Fueller + 2x `8000FE78`), `s68ab0_stamp` (`80068AB0`, 28,
  **VERDECKT**, je 8-B-Satz `800109FC(7)` + `80010580(13,20,4,0x8008A470)`),
  `s688d4_case` (`800688D4`, 119, 7-fach-Sprungtafel `[SDA(0x558)]+0x554`,
  Codebasis `[SDA(0x55C)]`). Modul jetzt **58 Koepfe / 2369 Worte / 9476 B**,
  FNV-1a **`11144A3B`**; Anker (230) 2/2, (231) 180/180, (232) 54/54,
  (233) 62/62; Regression **32 + 267, 0 Fehler**; Huelle (B) **333 Knoten /
  316 gebaut / 17 offen (1860 B = 465 Insn)**.
- **Die Naht `0x80055414` ist VERDRAHTET (R194/R280)** - im `tail` von
  `mission5_step` (`= FUN_8005471C`, R216-C/Dok-Kopf, fuer R207 unsichtbar)
  steht jetzt `voter::leaves2::s5382c(ram, slot, h, nullptr)` statt des
  gezaehlten Hakens; ROM-Wort `4BFFE419`. Die **zwei INNEREN Naehte**
  (`800687EC`, `80067C50`) laufen ECHT, die zwei klassengebundenen Ziele
  (`8000FE78`, `8000F1E0`) bleiben GEZAEHLT (R215). **Entscheidungsregel:**
  der Widerspruch B148 („nur der Zuschnitt fehlt") gegen B150 („zusaetzlich
  `FUN_8005471C` ungebaut") loest sich so auf - derselbe Dok-Kopf faehrt schon
  `0x80054804`/`0x80054EB4` echt; der R280-Einwand verlangt den Anker (Rufstelle
  + gefahrene Zaehler + ROM-Wort), keinen Verzicht.
- **Werkzeugluecke (gemeldet, nicht umgangen):** `m104_built.py nachzuegler`
  sieht Rufstellen der modernen API `mission::call_hook(...)` NICHT (Stelle als
  Konstante, kein Hakenmarker) - die neue `8000F1E0`-Stelle @`80068A78` fehlt
  deshalb in der Liste (gemessen: 82/34 (3/2) statt der erwarteten 84/35 (4/2)).
- **Port-Entscheidung:** der 16-B-Scratch fuer `s68b20_fill` liegt bei
  `leaves2::k152Scratch = 0x803E0D00` (gemessen frei gegen ALLE sechs
  Reservierungen: `kAuxHeapBase`, `kFmtState`, `kShowBuf`, `kFcAux`,
  `kMirrorBase`, `kFrameBuf`).


## Batch 157 (2026-09-25) — GL-Referenz geheilt + Zwei-Rechner-Hygiene (R380–R387)
- `analysis/_gl_ref_hashes.txt` ist **neu gestempelt** (glsetup `aa5610e5…`). `--write-gl-ref` **verweigert** das Schreiben, wenn der Lauf den neun Mitschnitten `analysis/_m155/_gl_<modus>.txt` widerspricht (`--force-gl-ref` erzwingt und weist aus); EIN Hashweg: `gl_stdout_text`/`gl_stdout_sha`.
- **R381:** `GALLIUM_OVERRIDE_CPU_CAPS` wirkt heute **nicht** (Studio UND Arcade); tragend ist `LP_NATIVE_VECTOR_WIDTH`. Pins bleiben gesetzt.
- **R382:** `.gitattributes` → `analysis/*.txt text=auto eol=lf` (LF-schreibende Werkzeuge vs. CRLF-Auscheck → sonst ` M` in `git status` trotz leerem `git diff`).
- **R383:** 7zr wird nur mit Hash-Treffer benutzt; Quelle 1 = versioniertes `ip7z/7zip` 26.03, Quelle 2 `www.7-zip.org`. **R384:** der Preflight-Kopf druckt `Werkzeugkette` (PATH-g++ = MinGW.org 6.3.0 ≠ Bau-g++ = MSYS2 UCRT64 16.2.0).
- Laufprotokoll (nicht getrackt) sind jetzt auch die **15** Selbsttest-Berichte `_m65_hit_report.txt` … `_m88b_opmode_ui.txt`.
- **Scheibe A:** 2 von 8 Nähten verdrahtet (`800547DC`→`m6_state_b`, `800547EC`→`counter_scale(9,1)`); Nachweis in `mission_check.cpp` (h)/(a) über die **Wirkung** (`blk+0x632 == 17`, `content_helper_stats().calls`, `flow_stats().calls`, `st.wired == 2`, Haken 0). Die fünf T3-Typpfad-Nähte (8/9/10): `rec+kRecType = N` erreicht den Pfad **nicht** (Zuordnung erst messen) und der Lauf verändert geteilte Zellen (`cfg`/F-Log) → eigener Sandkasten (**R386**). `80054AE4`-Wirt **reicht** (`h.lzss->frame` + `aux()`, R347b/B150), Nachweis fehlt.
- **R385:** der Haken-Mitschrieb kann **unvollständig** sein (`80054B0C`: `r4` fehlte, ROM setzt `addi r4,r3,0`) → vor dem Verdrahten die **Rohworte** lesen. **R387:** `nachzuegler`, R216 B und R207 `check benannt` zählen **Verschiedenes**.

