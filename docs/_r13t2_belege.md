# Belege R13t2 (2026-09-28) - Portfund 8005BF74, CA-Zensus mit Port-Seite, Punkt 3a-c

Alles rein LESEND: kein Ghidra-Schreibzugriff, keine Aenderung im Decomp-Repo
(`git status --porcelain` dort bleibt leer; es wurden keine Decomp-Werkzeuge
ausgefuehrt, die in `analysis/_m*` schreiben koennten).

## 1a - CA-Muster in den Port-Quellen der 34 CA-Koepfe

Werkzeug `tools/r13t2_port_ca_scan.py`, Belege `docs/_r13t2_beleg_1a.txt` und
`docs/_r13t2_ca_port.json`.

* 34 der 78 registrierten Koepfe (`KOPF_DEF`) enthalten CA-Formen; **kein einziger**
  enthaelt eine CA-**lesende** Form (`adde`/`addze`/`addme`/`subfe`/`subfze`/`subfme`).
* Port-Seite: je Kopf wurde die Portfunktion (aus `const Head kHeads[]`,
  `port/src/ckopf_leaves.cpp:2363`) geschnitten (Brace-Matching) und auf
  CA-verbrauchende Muster geprueft - Inkrement (`+= 1`, `+ 1u`) **mit Vergleich** im
  Zeilenfenster ±2 (damit auch mehrzeilige `if (…)` greifen) plus jede CA-Nennung.
* **Genau ein Treffer** (Datei:Zeile):

      port/src/ckopf_leaves.cpp:1977   if (r0 >= r10) r0 += 1u;   // CA aus `subfc`

  Das ROM-Wort dazu ist `0x7C005014` = `addc` (XO 10, Rc = 0): `addc` liest CA nicht.
  Alle uebrigen 33 Koepfe haben im Port **keine** CA-Addition.
* Gegenprobe im ganzen Port (unabhaengig, `Select-String`): CA-Nennungen stehen nur an
  `ckopf_leaves.cpp:129` (Kommentar `addic`), `:1977` (der Fund), `:2026/2112/2183/2276`
  (Kommentare), `adc_check.cpp:45` (Worttafel-Kommentar), und in **legitimen** Ketten:
  `game_result.cpp:94-99` (`addze`), `mission_content_helpers.cpp:406-407` (`subfe`),
  `:561-572` (`addze` nach `addc`), `mission5_head.cpp:270` (`addic`, kein Carry),
  `mission_helpers.cpp` (`resolve_carry` = Zaehler, kein XER.CA).
* Programmweiter Zensus (Inventar-CSV, innerhalb `size`): CA-**lesend** `addze` 382x,
  `subfe` 18x; CA-schreibend `addc` 3815x, `subfc` 1490x. In den 78 Koepfen 0 lesende.

## 1b - warum 8005BF74 gruen war

`docs/_r13t2_beleg_1b_fall.txt` (Analyse mit Datei:Zeile), Rohworte
`docs/_r13t2_beleg_1b_rom.txt`. Kurz:

* `c_kopf` vergleicht **jedes geschriebene Speicherwort und den Rueckgabewert** Zeile fuer
  Zeile (`c_kopf.py:1852` `cmd_vergl`, `:1825` `_diff`, Dump `:1389` `MEM %08X %02X`).
* Eingaben: `_faelle` (`:1472`) aus `WERTEFAECHER`/`SANDFAECHER` (`:1427/1429`), Saat
  `0x19800000+head`, ROM-Leitern in `WERTE_DEF` (`:1521`); fuer diesen Kopf stehen die
  24 Faelle in `analysis/_m197/_ck_5BF74.case`.
* **Alle 24 Faelle haben r5 = 0** und `[r3+8] = 0x10000` → `diff > 0` → der Kopf nimmt in
  jedem Fall den fruehen Ausgang `ckopf_leaves.cpp:1979` und **betritt die Schleife nie**,
  in der das verschobene `r0` als Vergleichsschwelle wirkt. Deshalb 0 Abweichungen.
* Vorschlag (auch im /ds-Auftrag): feste Grenzfaelle (0, 1, 2, 3, `0x7FFFFFFF`,
  `0x80000000`, `0xFFFFFFFF`, `0xFFFFFFF0`, `0x10`, gleiche Operanden, Vergleichsgrenze ±1)
  in jede Fallfabrik; Standardmutation „CA-Semantik vertauscht“ in `MUT` (`c_kopf.py:1943`).

## 2 - lehnt der Interpreter unbekannte Opcodes laut ab?

**Ja, laut.** `scripts/m114_matrix.py`:

| Stelle | Zeile | Wirkung |
|---|---|---|
| Opcode 31, XO nicht modelliert | `m114_matrix.py:539` | `raise ValueError("op31 xo %d @%08X")` — `adde` (138), `addze` (202), `addme` (234), `subfe` (136), `subfze` (200), `subfme` (232) landen hier |
| Hauptopcode unbekannt | `m114_matrix.py:567` | `raise ValueError("op %d @%08X (%08X)")` |
| bekanntes, aber NICHT gebautes Geschwister mit Rc/OE | `m114_matrix.py:383-389` | `EXC op31 xo %d oe/rc (…, nicht gebaut)` (R534-Regel) |
| Brachfeld nicht modelliert | `m114_matrix.py:267` | `raise ValueError("BO %d nicht modelliert")` |
| Rufziel nicht modelliert | `m114_matrix.py:584` | `raise ValueError("Ruf nach %08X nicht modelliert")` |

Es gibt **keinen** stillen Zweig: ein CA-lesender Befehl wird nicht „irgendwie“ gerechnet,
sondern bricht mit `EXC …` ab. Eine neue Ablehnungsregel ist deshalb **nicht** noetig.

## 3a - Definition von "C" (Wortlaut readme.md)

`readme.md:34-37`:

> The transition between (1) and (2) was decided on **2026-09-27**: the order is
> **`B A C`** (B = audio up to the tone, A = `FUN_8005471C` as one head,
> C = the systematic pass). **C has been running since Batch 197**; its order is
> 1. the rest of the voter hull (the 17-node rest), smallest first,
> 2. **packet E** (UI, text, test mode, service menu) — it keeps priority
>    **inside C** as well, leaves first, smallest first,

und dieselbe Entscheidung in Prosa `readme.md:638-642`:

> **DECISION (2026-09-27, user): the transition order is `B A C`** — first
> **B = audio up to the tone** (own voice mixer, this batch), then
> **A = `FUN_8005471C` as one head**, then **C = the systematic pass**. The reason:
> the tone is the last missing piece of a runnable port, and the conversion of the
> remaining heads can be measured against it.

(Der Nutzerhinweis "readme.md:628" trifft dieselbe Passage; die Zeilennummern sind
inzwischen 34-37 bzw. 638-642.)

## 3b/3c - wie laufen die nicht gebauten Funktionen, und was laeuft ohne MAME?

* Der Port hat **keinen** Interpreter-Rueckfall und **keine** MAME-Bindung:
  `Select-String` ueber `port/src/*.cpp` + `port/include/port/*.h` findet MAME nur als
  **Dokumentationsverweis** in Kommentaren (z. B. `adc12138.cpp:3` "WOERTLICH MAME
  `src/devices/machine/adc1213x.cpp`"). Es gibt kein `mame`-Include und keine Bibliothek.
* Die Einhaengepunkte des Ports sind Pruefprogramme (`port/src/*_drv.cpp: int main`,
  `port_selftest.cpp:2414 int main`) plus die GL-Senke; `Makefile` baut
  `port/build/port_selftest.exe` (`all`) und `port_gl.exe` (`gl`), dazu Einzelkopf-Ziele
  (`head188` … `head193`). Es gibt **kein Spiel-Binary**.
* Die ~670 "ausgefuehrten, aber nicht gebauten" Funktionen laufen im Port **gar nicht**:
  "ausgefuehrt" ist eine Aussage ueber die **Aufnahme** (`capture/ppc_coverage*.bin`,
  aus einem fremden Lauf), nicht ueber den Port. Der Port fuehrt heute nur die gebauten
  Koepfe aus - im Selbsttest/`ckopf` gegen den Wortinterpreter (`scripts/m114_matrix.py`,
  die Python-Testwelt) und in den GL-Pruefungen.
* Eigenstaendig ohne MAME laeuft: die **Wortinterpreter-Welt** (Python/PoC,
  `poc/ppc_native/` rechnet die kommandoerzeugende Kernschicht nativ und ist gegen einen
  MAME-Referenzstrom halbwortgenau geprueft, `poc/ppc_native/ppc_core.h:14-27`) und der
  **Port als Pruefstand** (Einzelkopf-Vergleiche + Selbsttest + GL-Senke).
  **Kein Boot, kein Attract, kein Level 1** als laufendes Programm: es fehlt der Rahmen
  (Main-Loop, Runtime-Init) - genau der Punkt, den `readme.md:634-642` als "the tone is
  the last missing piece of a runnable port" beschreibt.

## 4 - drei Klassen (Beleg)

`docs/_r13t2_beleg_4.txt` (Werkzeug `tools/r13t_cov_relevanz.py`, Cache
`docs/_port_relevanz.json`). Stand 2026-09-28:

| Klasse | Koepfe | Insn |
|---|---|---|
| (1) ausgefuehrt, noch nicht gebaut | 677 | 28976 |
| (2) nicht ausgefuehrt, Paket E | 1 | 38 |
| (3) nicht ausgefuehrt, sonstiger Rest | 725 | 24521 |
| Summe (= Inventar 2072 minus gebaut) | 1403 | 53535 |

Aufnahmen (gemessen): `ppc_coverage.bin` 31929 markierte Woerter (Gameplay-Replay),
`ppc_cov_boot.bin` 42599 (Boot+Attract), Union **52015** von 4194304 = 1,2 %.
Beschreibung/Herkunft: `analysis/f5-descr-batch42-2026-09-17.md:87-88` ("74 528
markierte PCs aus Boot+Attract+Gameplay-Replay" = beide Karten **summiert**);
Grenze der Aussage: `analysis/bucket-d-2026-09-16.md:312` ("Menuepfade sind im
Coverage-Lauf nicht enthalten"). Eigene Paket-E-Nachrechnung: 265 Koepfe, davon 28 offen
(Projektzahl 274/38).

## 5 - Entscheidungszeile fuer /fragen (nur formuliert, NICHT umgesetzt)

`docs/_r13t2_ds_5.txt` (als `/ds` in der Queue: `harness/inbox/ds/…DCF33E7E8896.md`).
Wortlaut des Postens:

> **(7) NEU:** heute laeuft C nach "Blaetter zuerst, kleinste zuerst" - gemessen sind aber
> **677 der 1403** noch nicht gebauten Koepfe (48 %, 28976 Insn) in den vorhandenen
> Aufnahmen schon AUSGEFUEHRT … **soll C nach Paket E in der Reihenfolge "ausgefuehrt
> zuerst, dann kleinste zuerst" laufen? (Vorschlag: ja)** bei ja: … bei nein: …

Der Text ist so gebaut, dass `stand.entscheidbar()` ihn als eine entscheidbare Zeile
liest (Ja/Nein-Frage mit `?`, `Vorschlag:`, `bei ja:`/`bei nein:`); die Zeile erscheint
in `/fragen`, sobald der naechste Batch sie in den Ankerkopf uebernimmt.

## Queue (an den Worker)

* `_r13t2_ds_1c.txt` → `harness/inbox/ds/20260928_005858_0000_37FE2536D0FB.md`
  (Korrektur 8005BF74, Kommentar `m114_matrix.py:395-397`, R535 im Anker/B206-Dokument,
  Grenzfaelle + Standardmutation, alle 78 neu vergleichen)
* `_r13t2_ds_5.txt` → `harness/inbox/ds/20260928_005858_0000_DCF33E7E8896.md`
  (Ankerposten (7) - nur Frage, kein Umbau)
