# R13bh — Preflight parallelisieren? Auftragsvorbereitung (nur gelesen, 2026-10-01)

Auftrag: **nichts ändern**, nur vorbereiten. Quellen: `scripts/preflight.py`,
`analysis/_m<N>/_preflight_zeiten.txt` (B230–B234), die Modulquellen unter `scripts/`.
Alle Zeilenangaben gelten für **Decomp-Repo `7ec9d6a`**. Rohbelege:
`docs/_r13bh_preflight.txt` (Zeiten), `docs/_r13bh_quellen.txt` (Schreibziele/Starter).

## 0. Was der Preflight heute ist

`scripts/preflight.py:91` (`CHECK_MODULES`) fährt **15 Gruppen seriell in
Registry-Reihenfolge** (`collect()` `:197`); jedes Modul fällt sein Urteil selbst
(`verdict.py`) und schreibt seine Belege über `evidence.py` (`EV.target/guard/write`) —
dabei wird der Altstand nach `analysis/_archiv/<name>.<NNN>.<hash>.ext` gesichert und
**jede** Sicherung in `analysis/_archiv/MANIFEST.txt` angehängt
(`scripts/evidence.py:141`).

Gemessene Wanduhr (Summe je Batch, `_preflight_zeiten.txt`): B230 **524,9 s**,
B231 533,5 s, B232 547,6 s, B233 549,3 s, **B234 1578,5 s** — also 8,7–9,2 min im
Regelfall (B234 war der Ausreißer mit dem langen Frontlauf).

## 1. Tafel: Gruppe | Sekunden | liest | schreibt

Sekunden = Mittel B230–B234 (B234 in Klammern, wo es abweicht).

| Gruppe | s (Ø) | liest | schreibt |
|---|---|---|---|
| `m104_built` (R207) | 1,7 | Belege früherer Batches (`analysis/_m196/_rest_nachher.txt`, `_m222/_c_paket_e_vorher.txt`, `_m216/_kandidaten.txt`) | `analysis/_m104_nachzuegler.txt` (EV) |
| `m115_pass` (R216 A/B/C) | 3,8 | `port/src/`, `port/…` (ABI/Impl/Doc-Sonden) | `analysis/_m115_abi.txt`, `_m115_impl.txt`, `_m115_doc.txt`, `_m115_r216raw.txt` (EV, `m115_pass.py:174/215/242/308`) |
| `m116_pass` (R216 D) | 2,1 | `port/src/` (`voter_select*`) | **`port/src/voter_select_words.inc`, `port/src/voter_select_expect.inc`** (`m116_pass.py:189/402`) + `analysis/_m116_probe.txt`, `_m116_doc4.txt` (`:471/531`) |
| `m114_pass` (P100) | 0,0 | `port/src/`, Kopfprofile | `analysis/_m114_p100.txt`, `_p100sel.txt`, `_r216.txt`, `_r222.txt`, `_sel.txt` (EV, `m114_pass.py:177…532`) |
| `m130_ast` (R222) | 0,0 | `port/src/`, ROM | `analysis/_m130_{hulls,hull,span,sites,deps,dis,words,raw,cells}.txt` (EV, `m130_ast.py:377…676`) |
| `m5_kopf_check` (M5) | 2,9 | `port/src/mission5_head_words.inc`, `port/build/m193_head.exe` | **baut `port/build/m193_head.exe`** (`mingw32-make -j4 head193`, `m5_kopf_check.py:109`) |
| **`c_kopf_check`** (C Köpfe) | **310,0** | `scripts/c_kopf.py` `PROFILES` (115 Köpfe), ROM `rom/`, Profile; **baut bei Bedarf `port/build/c_kopf.exe`** (`c_kopf.py:3155`) | `analysis/_m<N>/_c_kopf_lauf.txt`, `analysis/_m<N>/_bahnabdeckung.txt` (`c_kopf.py:2652/2655`) |
| `m200_einbindung` | 5,3 | Kopf-Registry (`c_kopf.py`), `port/src/` | `analysis/_m<N>/_c_einbindung.txt`, `_c_nachzuegler_a.txt` (`m200_einbindung.py:296/327`) |
| `m210_bahnabdeckung` | **0,1** | **Cache** des gemeinsamen ROM-Laufs aus `c_kopf_check` (`c_kopf._DECKUNG_CACHE`) | `analysis/_m<N>/_bahnabdeckung_<modus>.txt`, `_bahnabdeckung_preflight.txt` (`m210_bahnabdeckung.py:177/203`) |
| `m210_r391` | 7,5 | `git log --all` (Commit-Reihenfolge) | `analysis/_m<N>/_r391_<n>.txt` (`m210_r391.py:346`) |
| `m227_profile_live` | 0,1 | `scripts/c_kopf.py`, `analysis/_m222/_prof_nachher` | `analysis/_m<N>/_prof_live/*`, `_profile_reproduzierbar.txt` (`m227_profile_live.py:85/141/155`) |
| **`m212_zeilen`** (4 Zeilen + **Hybrid-Lauf**) | **382,9** (B234 **1199,0**; Hybrid-Lauf allein Ø 365,8) | `analysis/_m197/_ck_*.case`, `_m209/_isa_orakel.txt`, `_m211/_zweig_unicorn.txt`, `analysis/_m<N>/_profile_reproduzierbar.txt`, Kopf-Registry | `analysis/_m<N>/_ck_zeilen.txt`, `_ck_fallrueckgang.txt`, `_hybrid.txt` (`m212_zeilen.py:187/218/464`), `_formen_gruen.txt` (via `m227_formen.py`, `:557`) |
| `m214_archiv` | 1,0 | `git` (getrackte Dateien unter `analysis/_m<k>`, k<N) | `analysis/_m<N>/_archiv_rotprobe.txt` (`m214_archiv.py:440`) |
| `m233_binary` | 0,1 | `Makefile`, `port/src/*`, mtimes der sechs Binaries | `analysis/_m<N>/_binary_quellen.txt` (`m233_binary.py:202`) |
| `port_regression` (REG) | 29,3 | `poc/ppc_native/ppc_poc.exe`, `port/build/port_selftest.exe`, `port_gl.exe`, `analysis/_gl_ref_hashes.txt` | 13 `analysis/*_regression_anker.csv`, 15 Selbsttest-Berichte, GL-`.ppm` (`port_regression.py:3559…3657`); `analysis/_gl_ref_hashes.txt` **nur** ohne Abweichung/`--force-gl-ref` (`:3841`) |

**Gemeinsames Schreibziel:** nur `analysis/_archiv/MANIFEST.txt` (Append, `evidence.py:141`)
— die Belegnamen selbst sind je Gruppe verschieden.

## 2. Unabhängigkeit — und die Falle

**Dateiseitig sind die Gruppen unabhängig** (kein gemeinsamer Belegname außer MANIFEST).
**Prozessseitig sind sie es NICHT:**

* `m210_bahnabdeckung` (0,1 s) und `m212_zeilen / C verifiziert` (0,1 s) sind
  **Cache-Treffer** desselben ROM-Laufs, den `c_kopf_check` in-process fährt
  (`c_kopf.py:2586 deckung`, `:2612 _vergl_alle`; `c_kopf_check.py:56` „IN-PROCESS statt
  Unterprozess"). **Beleg (gemessen, vor der Änderung B217):**
  `analysis/_m216/_preflight_zeiten.txt` — `C Koepfe` **241,2 s**, `Bahnabdeckung`
  **213,3 s**, `C verifiziert` **216,9 s** = 91,5 % der Wanduhr, und die beiden Auswertungen
  fuhren dieselben 85 ROM-Läufe **zweimal**.
  ⇒ Würde man diese drei in **getrennte Prozesse** legen, kostet das **+213 s +217 s** —
  die Parallelisierung wäre dann **deutlich langsamer** als heute.

**Weitere harte Reihenfolgen (aus den Schreibzielen):**

1. `m116_pass` schreibt `port/src/*.inc` → **vor** jedem Bau (`m5_kopf_check`) und **vor**
   `m233_binary` (das Binary-Alter gegen die Quellen prüft).
2. `m5_kopf_check` baut `m193_head.exe` → **vor** `m233_binary`.
3. `m227_profile_live` schreibt `_profile_reproduzierbar.txt` → **vor** `m212_zeilen`
   (so steht es auch als Kommentar in `preflight.py`).
4. `c_kopf_check` und `m212_zeilen/Hybrid-Lauf` starten Port-Köpfe
   (`c_kopf.exe`, `hybrid_lauf.exe`) → **niemals gleichzeitig** (Nutzerauflage).

## 3. Vorschlag: drei Bahnen (max. 3 gleichzeitig, 1 Hybrid)

| Bahn | Inhalt | Dauer (B230–B233) |
|---|---|---|
| **A** — Hybrid-Kette, **ein** Prozess, streng seriell | `m227_profile_live` → `c_kopf_check` → `m210_bahnabdeckung` → `m212_zeilen` | 0,1 + 310,0 + 0,1 + 183 = **493 s** |
| **B** — Bau/Regression | `m116_pass` → `m5_kopf_check` → `port_regression` → `m233_binary` | 2,1 + 2,9 + 29,3 + 0,3 = **34,6 s** |
| **C** — kurz, sonst unabhängig | `m104_built`, `m115_pass`, `m114_pass`, `m130_ast`, `m200_einbindung`, `m210_r391`, `m214_archiv` | ≈ **16 s** |

**Erwartete Gesamtzeit** = max(A; B+C) = **493 s (8,2 min)** statt 525 s (8,7 min) im
Regelfall → **−32 s (−6 %)**; für B234: 1509 s statt 1578 s → **−69 s (−4 %)**.

**Ehrliche Einordnung:** Die Parallelisierung der Gruppen bringt **Sekunden, nicht
Minuten**, weil 94–96 % der Zeit in den zwei Port-Läufen steckt (310 s + 183…1199 s) und
genau die nicht überlappen dürfen. Wer wirklich Zeit will, muss **innerhalb** dieser zwei
Läufe ansetzen (kürzerer Frontlauf, weniger Köpfe je Preflight) — das ist eine
inhaltliche Entscheidung, keine Harness-Frage, und steht hier nur als Option.

## 4. Der Auftragstext

Der fertige `/ds`-Vorschlag liegt in `docs/_r13bh_ds_vorschlag.txt` (Wortlaut unten):
Bahnen mit fester Ausgabereihenfolge, Gleichwertigkeitsbeweis gegen den seriellen Lauf,
Rotprobe und die Hybrid-Regel.
