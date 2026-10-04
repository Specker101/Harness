# R13bu (2026-10-04): ROM-Adressen-Suche — Regel im Vorspann, Werkzeug im Decomp-Repo

Auftrag (Nutzer): „Der Worker findet vorhandene native Port-Funktionen nicht (B260 gun_input,
B264 opmode, früher 0x40000000), obwohl die Grep-Pflicht R13az gilt." Entscheidung: Prompt-Regel
**ja**, Werkzeug **ja**, Zentraltafel zurückgestellt.

## 1. Was gemessen wurde (die Ursache, nicht die Vermutung)

Aus den Mitschnitten des Harness (`harness/runs/…`, nur gelesen):

| Batch | Werkzeugaufruf | Ergebnis |
|---|---|---|
| B264 | `runs/b264/stream-forts1.jsonl:21020` — `Grep {pattern: "80026718\|800261C4\|80025CDC\|80025cdc\|8000005C\|8000005c\|80083E18\|80026748\|800267B0", head_limit: 20, -n}` — **ohne `path`** | 20 Treffer: 19 aus `analysis/bucket-*.md` (B42/B43-Altbelege), **ein** Port-Treffer (`port/hybrid/hybrid_lauf.cpp:2543`). Die Port-Dateien mit dem Dispatcher fielen aus dem Fenster |
| B265 | `runs/b265/stream.jsonl:5816` — derselbe Fall mit `path: "port\\src"`, `head_limit: 80` | erste Treffer `port/src/opmode.cpp:189…`, `port/src/input_layer.cpp:26` — **gefunden** |
| B260 | `runs/b260/stream.jsonl:86060` — `mcp__ghidra__decompile_function {"address": "800237B4"}` | eine **Instruktionsadresse** in `FUN_8002379C`; im Port liegen die Belege unter dem Funktionseintrag |

Dazu die Schreibweisen im Port (ohne `port/build`): `8002379C` 20×`FUN_…`, 4×`0x…`;
`800261C4` 12×`FUN_…`, 5×`0x…`; `800237B4` 0×`FUN_…`, 2×`0x…`, 3× nackt. Dieselbe Funktion
heißt `FUN_800261C4` (`port/include/port/opmode.h:61`) **und** `FUN_800261c4`
(`port/src/game_words.inc:71`) — ohne `-i` fehlt die Hälfte.

## 2. Prompt-Regel (ein Commit je Repo)

* **Decomp-Repo** `AGENTS.md`, neuer Abschnitt „ROM-Adressen suchen (R13az, nachgezogen
  2026-10-04)": Werkzeug zuerst, Fehlstelle-Wortlaut, fünf Grep-Regeln (path zuerst `port`;
  `-i`; nackte Adresse ohne `0x`; `head_limit` mindestens 80; bei Instruktionsadressen zuerst
  den Funktionseintrag) — Commit `a5f2f7f`, gepusht.
* **Harness** `hx/worker.py::WORKER_PREAMBLE`, neuer Block „ROM-ADRESSEN SUCHEN" im
  ARBEITSUMFELD: dieselben fünf Regeln plus die Pflicht, `scripts/port_suche.py` zuerst zu
  nehmen und **seine Ausgabe ins Batch-Dokument** zu schreiben.
* Test `harness/tests/test_r13bu_fixes.py` (6 Tests) hält den Wortlaut fest und prüft, dass
  Werkzeug und Regel im Decomp-Repo wirklich liegen (beide Repos können sonst still
  auseinanderlaufen).

## 3. Werkzeug `scripts/port_suche.py` (Decomp-Repo, Commit `7da2a74`, gepusht)

Normalisierung (`8002379C`, `0x8002379c`, `FUN_800261c4`, `8002379C+0x1A`, `kFn…`),
Offset-Auflösung über `analysis/_m225/_funktionen.txt` (Rückfall `_ppc_inventory.json`),
vier Suchformen, Filter (`port/build`, `analysis/_archiv`, > 2 MB, `*_roh.txt`, eigene
Berichte), Klassifikation je Treffer und Aufrufer/Aufgerufene aus `_ppc_inventory.json`.

Selbsttest (`python scripts/port_suche.py --selftest`, alle vier Fälle OK):

| Fall | Funktion | PORT | Einordnung |
|---|---|---|---|
| `8002379C` | `0x8002379C` FUN_8002379c | 7 Dateien / 24 Treffer | 21 Funktionsbelege (u. a. `kFnPanelRead` in `port/include/port/gun_input.h:84`) |
| `800237B4` | `0x8002379C` (Instruktion darin) | 7 Dateien / 28 Treffer | 20 Funktionsbelege + 2 Instruktionsprüfung (`input2_check.cpp:39,219`) |
| `800261C4` | `0x800261C4` FUN_800261c4 | 7 Dateien / 19 Treffer | 13 Funktionsbelege (u. a. `kFnInitDispatch` in `port/include/port/opmode.h:116`) |
| `0x40000000` | keine (außerhalb des ROM-Bereichs) | 11 Dateien / 119 Treffer | **0 Funktionsbelege** → SPU-Block, Float-Wort 2.0, Bit-30-Maske |

Belegdatei: `analysis/_port_suche_beleg.txt` (Decomp-Repo, mit dem Werkzeug-Commit gepusht).

## 4. Volle Reihe am Gate

`docs/_r13bu_volle_reihe.txt` (HEAD, Harness-Zustand und Testzahl stehen im Kopf der Datei).
