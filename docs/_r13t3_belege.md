# Belege R13t3 (2026-09-28) - "lauffaehiges Spiel": Widerspruch, A/B/C, Entscheidung (7)

Nur LESEND; keine Aenderung im Decomp-Repo. Alle Zahlen unten sind gemessen (nicht
geschaetzt), was HYPOTHESIS ist, steht ausdruecklich dabei.

## 1. Der Widerspruch readme "runnable port" <-> "kein Spiel-Binary"

| Aussage | Fundstelle | Wortlaut |
|---|---|---|
| Reihenfolge-Entscheidung | `readme.md:638-642` | "the reason: the tone is the last missing piece of a **runnable port**, and the conversion of the remaining heads can be measured against it" |
| Milestone 3 | `readme.md:753-754` | "A native PC port that **renders the game's scenes** without MAME" — offen |
| Milestone 4 | `readme.md:755-757` | "**Replace the still-emulated layers** (audio, boot/I/O) with native code, so that the port becomes a standalone executable" — offen |
| Paket F | `readme.md:53` | "**Paket F** (boot / low-level I/O) is lower priority; it is PC-replaceable" |
| Status | `readme.md:747-750` | "native port in progress (graphics chain proven natively; audio route decided …)" |

Gegenprobe zum Befund "kein Spiel-Binary" (gemessen):

* Einhaengepunkte (nur Pruefprogramme): `port/src/c_kopf_drv.cpp:118`,
  `mission5_head_drv.cpp:89`, `mission5_head_drv189.cpp:187`, `port_selftest.cpp:2414`;
  `Makefile`-Ziele: `all` (`port_selftest.exe`), `gl` (`port_gl.exe`), `ckopf`,
  `head188`…`head193`. **Kein** Spielziel.
* Umfang: **103** Portmodule (ohne `*_check`) + **56** Pruefmodule, **125636 Zeilen** in
  `port/src/*.cpp` + `port/include/port/*.h`.
* Die neun GL-Anker (`analysis/_gl_ref_hashes.txt`) belegen die **Rendering-Kette**
  (glstream, glown, glmatrix, glsetup, gltex, gltexsetup, glcolor, glcolorsetup, …),
  nicht Szenen.

**Urteil:** der Satz meint den Abschluss von **Zweig B** (Audio bis zum Ton = letzte noch
emulierte Schicht nach Milestone 4), nicht einen lauffaehigen Port. Textvorschlag:
`docs/_r13t3_ds_readme.txt`, Queue `…F462C373BC95.md`.

## 2. Was heute existiert (Basis des A/B/C-Vergleichs)

* **Bau-Liste:** 686 Koepfe gebaut (`m104_built.built_map()`), 1403 nicht gebaut
  (Inventar 2072), davon **677 in den Aufnahmen ausgefuehrt** (`docs/_r13t2_beleg_4.txt`).
* **Wortinterpreter** `scripts/m114_matrix.py` (Python): deckt **97,3 %** der
  ROM-Befehlsworte. Messung: alle Woerter in den Inventarbereichen
  (`analysis/_m60_inventar.csv`, `size` auf 0x2000 gedeckelt) = **117648 Woerter**;
  modelliert 114490. Es fehlen **3158 Woerter / 35 Formen**, die groessten:
  `op 0` 2037 (mit hoher Wahrscheinlichkeit Daten in zu grossen Inventarspannen),
  `addze` 382, `mfcr` 109, `stwx` 60, `cntlzw` 57, `mtdcr` 56, `mulli` 55,
  `mfdcr` 51, `stbx` 37, `srw` 35, `sthbrx` 34, `subfe` 18, `sthu` 12 …
* **PoC-Kern** `poc/ppc_native/ppc_core.h` ist **keine CPU**: hand-portierte
  Kernschicht (`struct Record/Dump/Machine`, `run()` in Zeile 718), die einen
  MAME-Dump nachrechnet - kein Ausfuehrer von ROM-Code.
* **Takt (MAME, Referenz):** `mame/mame/src/mame/konami/hornet.cpp:29`
  "IBM PowerPC 403GA at **32MHz** (main CPU)"; 68K 16 MHz, SHARC 36 MHz.
  → Echtzeit heisst ~32 Mio. PPC-Instruktionen/s: Python ist dafuer 3-4
  Groessenordnungen zu langsam, ein C++-Kern mit einfachem RAM nicht.
* **Referenz fuer einen ganzen Lauf:** 21 Stroeme `capture/poc_ref_*.txt`
  (`analysis/_m67_opcode_census.txt`: 11995 Pakete, **34 distinkte Opcodes**), dazu die
  Coverage-Karten (Boot+Attract+Gameplay, 31929 + 42599 markierte Woerter).
* **Hardware-Modelle im Port (Auswahl):** `vbi_handler.cpp`, `image_tick.cpp`,
  `frame_commit.cpp`, `display_bank.cpp`, `render_transport.cpp`, `render_gl.cpp`,
  `rtc.cpp`, `nvram.cpp`, `adc12138.cpp`, `gun_input.cpp`, `gun_volume.cpp`,
  `input_layer.cpp`, `host_input.cpp`, `sharc_*.cpp` (6), `audio68k_*.cpp` (4),
  `audio_mixer.cpp`, `voodoo_color_stage.cpp`, `vertex_transform.cpp`,
  `triangle_setup.cpp`.

## 3. A/B/C - Vergleich (Aufwand = HYPOTHESIS, Basis oben)

| | A) C zu Ende, dann integrieren | B) Hybrid-Laeufer frueh | C) Static-Recompilation vorziehen |
|---|---|---|---|
| Erster sichtbarer Meilenstein | erst nach C + Audio-Rest + Integration | "ROM bootet und faehrt **Attract** im Hybrid-Laeufer" (HYPOTHESIS 10-20 Batches) | "Boot/Attract aus generiertem C++" (HYPOTHESIS 15-30 Batches, schwerer zu debuggen) |
| Aufwand bis spielbar | **~295 Batches** (1403 ÷ 4,7 K/Batch gemessen) + Integration | 16-32 Batches (403-Kern 4-8, Maschine/MMIO/DCR/Timer 4-8, Kopf-Uebernahme + Boot-Debug 6-12, Audio/ Pad 2-4) | 20-40 Batches (Translator + Runtime + dieselbe Maschine wie B) |
| Was fehlt konkret | die 1403 Koepfe, Audio-Rest (1808 Insn), Main-Loop, Ersatz von Paket F | **schneller C++-403-Kern** (Python zu langsam), Maschinensicht (flaches 4-MiB-RAM + MMIO-Bus + DCR/Timer/IRQ), die 35 fehlenden Befehlsformen, Kopf-Uebernahme ueber `kHeads`, Boot "gut genug" emulieren | derselbe Maschinen-Rahmen wie B **plus** Code-Erzeugung; ohne fertigen Port fehlt die Referenz (`readme.md:661-673` verbietet es ausdruecklich: "document only - do not work on this") |
| Neue Gegenprobe | keine (nur Interpreter<->Port) | **dritte Welt:** ganzer Lauf gegen Referenzstroeme + Coverage (schliesst den R535-Fall "beide Welten teilen denselben Denkfehler" aus) | dieselbe wie B, aber die erzeugte Quelle ist kein lesbarer Beleg |
| Risiko | spaete Rueckmeldung, Fehler wie R535 bleiben bis zum Ende unsichtbar | Rutsch in "ein besserer Emulator" (Ziel-Gefahr), Doppelbuchhaltung, MMIO-/Timing-Genauigkeit | Zielkonflikt: erzeugter Code ist keine Dekompilation; Widerspruch zur eigenen Readme-Entscheidung |
| Wirkung auf das Ziel | maximal (jeder Kopf bleibt Handarbeit = lesbar) | ziel-neutral, beschleunigt die Messbarkeit; Koepfe werden weiter 1:1 ersetzt | als Geruest nuetzlich, als Lieferung schaedlich |

**Empfehlung:** B als **Pruef-Fahrzeug** (nicht als Zielwechsel), C laeuft unveraendert
weiter, Static-Recompilation bleibt vertagt. Entscheidungszeile fuer `/fragen`:
`docs/_r13t3_ds_abc.txt`, Queue `…C60ECDC3C72F.md` - Anker wird in diesem Rahmen NICHT
von Hand geaendert.

## 4. Entscheidung (7)

`docs/_r13t3_ds_7.txt`, Queue `…AA3B5FA62A28.md`: **(7) ENTSCHIEDEN (Nutzer, 2026-09-28):
ja** - nach Paket E "ausgefuehrt zuerst, dann kleinste zuerst"; die Kandidatenliste
bekommt die Spalte "ausgefuehrt (Aufnahmen)", der Vorhersage-Commit nennt sie je Kandidat.
