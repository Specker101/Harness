# R13ah-Belege (2026-09-29): drei Harness-Fixes nach der Aussensicht B214

Auftrag (Nutzer, 2026-09-29): (1) **Fortsetzung nach Preflight** — Preflight vor dem Anstoss
unverändert archivieren und committen, Fortsetzungstext mit der Batch-Nummer aus dem
Harness-Tag; (2) **Zeitkappung** — `BASH_MAX_TIMEOUT_MS` konfigurierbar (1800 s), Batch-Uhr
zeigt „Preflight zuletzt ~X min", Umschaltschwelle um diesen Vorlauf vorgezogen; (3)
**B-Schritt-Auslöser ersetzen** — Stillstand aus der Preflight-Zeile `Hybrid-Lauf`.

Alles im Harness-Repo (`g:\Harness`). Das Decomp-Repo wird nur **gelesen** (Preflight-,
Bilanz- und Aufgabendateien); der laufende Batch (B215) wurde nicht angefasst.

---

## 0. Ausgangsmessung (Sonde `docs/_r13ah_probe.py`, Messdatei `docs/_r13ah_messung.txt`)

Aufruf aus `harness/`: `python -u ../docs/_r13ah_probe.py` (nur lesend; der Zustand wird
nicht gespeichert, weil `faellig` bei `geprueft_batch == batch` frueh zurueckkehrt).

### 0a. Wo die Zeitgrenzen gesetzt wurden (Befund 3)

| Datei:Zeile | Inhalt (vorher) |
|---|---|
| `hx/envs.py:138` | `"BASH_DEFAULT_TIMEOUT_MS": str(cfg.get("claude", "tool_timeout_ms", 600000))` |
| `hx/envs.py:139` | `"BASH_MAX_TIMEOUT_MS": str(cfg.get("claude", "tool_timeout_ms", 600000))` |

`claude.tool_timeout_ms` stand **nicht** in `harness.toml` → beide waren **600000 ms = 600 s**.

### 0b. Werkzeugaufrufe ≥ 500 s (aus `runs/b212…b214/result.json`, `stats.laufzeit.langsamste`)

| Batch | Dauer | Aufruf (Anfang) |
|---|---|---|
| B212 | 602,3 s | `Grep: g:\Silent Scope Decomp\scripts` |
| B212 | 601,9 s | `PowerShell: Get-ChildItem capture\ppc_cov_boot.bin …` |
| B212 | 511,0 s | `PowerShell: & .\scripts\port_build.ps1 -Gl …` |
| B212 | 511,0 s | `Grep: g:\Silent Scope Decomp\port\hybrid\ppc_kern.cpp` |
| B213 | **602,0 s** | `PowerShell: Get-Date; python -u scripts/preflight.py before *> analysis\_preflight_213.txt …` |
| B213 | 601,6 s | `PowerShell: git add port/src/ckopf_leaves.cpp …; git commit -q -m "B213: …"` |
| B214 | **601,8 s** | `PowerShell: cd 'g:\Silent Scope Decomp'; Get-Date …; python -u scripts/preflight.py b…` |
| B214 | **601,3 s** | `PowerShell: cd 'g:\Silent Scope Decomp'; python -u scripts/c_kopf.py mutalle *> analysis\_m214\_mutall…` |
| B214 | 601,1 s | `PowerShell: … Set-Content -Path "$env:TEMP\b214_mut.txt" …` |
| B214 | 541,9 s / 541,8 s | `PowerShell: … $p = Get-Process -Id 18400 …` (Warteschleifen nach der Kappung) |

Die Häufung bei **601–602 s** ist die Kappung selbst: der Aufruf lief in den Hintergrund und
wurde danach abgefragt (R13v-Fund, jetzt auf `BASH_MAX_TIMEOUT_MS` zurückzuführen).

### 0c. Die Zeile `Hybrid-Lauf` (Grundlage für Befund 4)

| Datei | Zeile |
|---|---|
| `_preflight_212.txt` | `Hybrid-Lauf        215 \| 800138F0 \| MMIO \| 28/407 \| 0     OK` |
| `_preflight_213.txt` | `Hybrid-Lauf        215 \| 800138F0 \| MMIO \| 28/407 \| 0     OK` |
| `_preflight_214.txt` | `Hybrid-Lauf        2000000 \| 8000CB98 \| Schranke \| 448/42599 \| nein     OK` |
| `_preflight_199…211.txt` | **keine** `Hybrid-Lauf`-Zeile (die Zeile gibt es erst ab B212) |

Strang der Batches aus `stand.strang_von_batch`: B211 **B**, B212 **B**, B213 **C**,
B214 **B**. Also: B212 und B213 sind gleich (Halt-PC und Wegmaß), aber B213 ist ein
**C**-Batch — für „3 B-Batches in Folge" sind es nur zwei (B212, B214), und B214 zeigt
ohnehin Fortschritt (`448/42599`). **Kein Fehlalarm.**

---

## 1. Fortsetzung nach Preflight (Befund 2)

**Neu** `hx/worker.py`:

* `batch_aus_checkpoint(state)` — Nummer aus dem Tag `harness/b<N>-start`
  (`state.data["last_checkpoint"]`, gesetzt in `hx/orchestrator.py:2626`); fehlt der Tag,
  gilt `state.batch` als Rückfall (wird geloggt).
* `archiviere_preflight_vor_fortsetzung(cfg, state, k, log)` — kopiert
  `analysis/_preflight_<N>.txt` **byteweise** (`shutil.copy2`) nach
  `analysis/_m<N>/_preflight_<N>_vor_fortsetzung<k>.txt`, `git add` genau dieser Datei und
  `git commit -m "B<N>: Preflight vor Fortsetzung archiviert"` (Git-Wache aus R13i bleibt
  aktiv: `gitsafe.Git` verweigert fremde Wurzeln). Wird **vor** dem Anstoss gerufen
  (`run_batch`, unmittelbar nach dem Eintrag in `fortsetzungen`, vor `resume = True`).
* `fortsetzungs_text(..., batch=N)` — der Text **beginnt** mit
  `Du bist weiterhin in Batch <N>. Alle Commits tragen B<N>:, nicht B<N+1>:.`
* `result.json` trägt jetzt `stats.preflight_archiv` (Pfad oder leer).

Gemessen im Test (eigenes Wegwerf-Repo): Archivdatei byte-identisch, Commit-Kopf wie
gefordert, `state.batch = 99` bei Tag `harness/b214-start` → Archiv landet in `_m214/`.

## 2. Zeitkappung und Vorlauf (Befund 3)

| Ort | vorher | jetzt |
|---|---|---|
| `harness.toml` `[claude] bash_max_timeout_s` | fehlte | **1800** |
| `hx/envs.py:139` `BASH_MAX_TIMEOUT_MS` | 600000 | **1800000** (aus der Config) |
| `hx/envs.py:138` `BASH_DEFAULT_TIMEOUT_MS` | 600000 | unverändert (Vorgabe ohne `timeout`) |
| `hx/worker.py::umschalt_minuten` | `Alarm − umschalt_vor_alarm_s` | `Alarm − max(15 min, Preflightdauer + 5 min)` |
| Batch-Uhr-Zeile | `… (Umschalten ab 75) \| Kontext 310k von 1M` | `… \| Kontext 310k von 1M \| Preflight zuletzt ~10 min` |
| `hx/stand.py::preflight_dauer` | — | Dauer des Preflight-Aufrufs aus `runs/b<N>/result.json` |

Gemessen im Test und am echten Bestand: Preflight 601,8 s (B214) → `preflight_min 10,03`,
`vorlauf_min 15,03`, `umschalt_min 74,97` (angezeigt „75"); mit 20 min Preflight wäre die
Schwelle **65 min**, und ein Lauf bei 66 min bekäme **keinen** Anstoss
(`fortsetzung_pruefen` nutzt dieselbe Zahl).

## 3. B-Schritt-Auslöser ersetzt (Befund 4)

**Entfernt** (Aussensicht B214: „das Feld B-SCHRITT misst nichts"): `aussensicht.b_schritt`,
`b_schritt_stillstand`, `bschritt_neuester_b`, `bschritt_gemeldet_bis`,
`bschritt_marke_setzen`, `bschritt_beteiligt`, `BSCHRITT_GRUND`,
`MARKE_BSCHRITT_SCHLUESSEL`, `MIGRATION_BSCHRITT_MARKE`. Die Pflichtzeile `B-SCHRITT:`
selbst **bleibt** — `stand.strang_von_batch` nutzt sie weiter als Beleg für die
Strang-Klassifikation (R13aa).

**Neu** `hx/stand.py::hybrid_verlauf` (liest Feld 2 = Halt-PC, Feld 3 = Art, Feld 4 =
Wegmaß `Zähler/Gesamt`, Feld 5 = Urteil) und `hx/aussensicht.py::hybrid_stillstand`:

* Verglichen werden die letzten `[meta] bschritt_stillstand_batches` **B-Batches in Folge**
  (Vorgabe 3) mit einer `Hybrid-Lauf`-Zeile; C-Batches und Batches ohne Zeile zählen nicht.
* Stillstand = **Halt-PC in allen gleich** und **Wegmaß steigt nicht** (jede Steigerung
  zwischen zwei verglichenen Batches hebt den Stillstand auf).
* Grund-Wortlaut (Beispiel, drei gleiche Werte):
  `Hybrid-Lauf haengt: Halt-PC 800138F0 unveraendert und Wegmass 28/407 -> 28/407 steigt
  nicht (B212, B213, B214, Quelle analysis/_preflight_214.txt, Zeile "Hybrid-Lauf") - kein
  Fortschritt ueber 3 B-Batches (B212 bis B214)`
* Entprellung wie bisher: Marke `hybrid_gemeldet_bis` (Start 0), gesetzt nur nach `rc == 0`
  mit beteiligtem Grund (`orchestrator._do_aussensicht`), gefeuert nur, wenn ein **neuer**
  B-Batch die Reihe verlängert.
* Der Preflight liegt **vor** dem Review vor — der Auslöser kommt damit früher als der
  Review-Auslöser, wie gefordert.

## 4. Tests

`harness/tests/test_r13ah_fixes.py` — **45 Tests**, alle grün: Archivdatei + Commit +
byteweise Gleichheit, Batch-Nummer aus dem Tag (nicht aus `state.batch`), zweite Fortsetzung,
fehlender Preflight, unlesbares Repo, Fortsetzungstext-Kopf; `BASH_*`-Grenzen (Vorgabe und
Config), `preflight_dauer` (Treffer/Rückfall/keine Messung), Schwelle mit 10/20 min
Preflight, Anstoss-Grenze bei 66 min, Hook-Datei und Hook-Skript-Text, Uhr-Zeile;
`hybrid_verlauf`-Feldzerlegung (auch die echten B212/B213/B214-Werte), Stillstand mit
3 gleichen B-Batches, kein Stillstand bei steigendem Wegmaß / anderem Halt-PC / zu kurzer
Reihe, C-Batch und fehlende Zeile zählen nicht, konfigurierbare Schwelle, Marke nur bei
`rc == 0`, kein Fehlalarm an den echten Dateien, und der Nachweis, dass der alte Grund
wirklich weg ist.

## 5. Nicht geprüft (offen)

* **Kein echter Fortsetzungslauf** mit dem neuen Archiv (kostet einen Batch); belegt ist die
  Mechanik an einem eigenen Repo plus die Aufrufstelle im Lauf.
* **Kein realer Batch mit 1800 s** Maximalzeit — die Wirkung zeigt sich erst, wenn ein
  Preflight/`mutalle`-Aufruf länger als 600 s dauert und **nicht** gekappt wird.
* Der **Stillstands-Auslöser** hat noch nie gefeuert (die echten Daten geben keinen her);
  belegt sind Regel, Wortlaut, Marke und die Nicht-Auslösung an den echten Dateien.
* Die alten Marken im Zustand (`bschritt_gemeldet_bis: 214`, `kernzahl_gemeldet_bis: 210`)
  bleiben als tote Zahlen stehen; gelesen wird nur noch `hybrid_gemeldet_bis` (Migration
  setzt sie beim nächsten Lauf auf 0 — im Messlauf nicht, weil `faellig` dort früh
  zurückkehrt).
