# Belege R13w (2026-09-28) — Aussensicht (Meta-Review)

Gebaut auf freigegebenem Plan mit den Nutzerentscheidungen vom 2026-09-28:
(1) synchron, (2) je Befund eine `/claude`-Nachricht, (3) **keine** Textmarken —
stattdessen Pflichtzeilen des Reviewers, (4) `/ds`-Queue sichtbar;
(a) Kernzahl-Auslöser nach Batch-Art getrennt, (b) Beleg-Pflicht gelockert,
(c) Stichprobenpflicht, (d) Antwortpflicht des Reviewers mit Register-Übernahme.

Alles nur im Harness-Repo; das Decomp-Repo bleibt unberührt (nur lesende Zugriffe).

## 1. Was gebaut wurde

| Teil | Ort | Inhalt |
|---|---|---|
| Modul | `hx/aussensicht.py` (neu) | Eingaben sammeln, Prompt/Kommando bauen, Lauf, Parser, Register, Verteilung, Auslöser, Bericht |
| Rolle | `prompts/aussensicht.md` (neu) | Prüfauftrag (6 Punkte), Stichprobenpflicht, Verbote, Grenzen |
| Auslöser + Ablauf | `hx/orchestrator.py` | `/meta`, `_do_aussensicht`, Prüfpunkt in `_loop` **vor** dem Review, `meta_zeile`, `/fragen`-Zusatz, Antwort-Übernahme nach jedem Review |
| Steuerung | `hx/control.py` (`meta`), `hx/cli.py` (`hx.cli meta`) | bei laufendem Harness nur die Kontrolldatei `state/ctl/meta`, sonst Direktlauf |
| Anzeige | `hx/bilanz.py`, `hx/telegram.py` | `/bilanz`-Zeile, `/meta` in der Hilfe |
| Konfiguration | `harness.toml` `[meta]` | `every_batches 10`, `wall_s 900`, `max_turns 30`, `max_befunde 7`, `summaries 10`, `bilanz_zeitfenster 12` |
| Prompt des Reviewers | `prompts/reviewer.md` | Pflichtzeile `B-SCHRITT: <n>/5 …`, bedingte Zeilen `MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:`, Antwortpflicht zu `M<batch>-<n>` |
| Tests | `tests/test_r13w_fixes.py` (neu, 29) | Parser, Kommando, Auslöser, Register, Verteilung, Orchestrator-Ablauf, `/bilanz`-Zeile |
| Doku | `docs/bedienung.md` §12e + Befehlsliste | Zweck, Auslöser, Ablauf, Empfänger, Ablage, Grenzen |

## 2. Entscheidungen und ihre Umsetzung im Code

| Entscheidung | Beleg im Code |
|---|---|
| synchron (1) | `orchestrator._do_aussensicht` ruft `aussensicht.run(...)` direkt; Zeitgrenze `[meta] wall_s` an `run_stream(hard_wall_s=…)` |
| je Befund eine `/claude`-Nachricht (2) | `_do_aussensicht`: Schleife über `verteilung["ids"]`, je Reviewer-Befund `queue.enqueue(..., "claude", …)`; Test zählt Queue-Einträge gegen Reviewer-Befunde |
| keine Textmarken (3) | `aussensicht._marker` liest **nur** `MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:` aus den Review-Zusammenfassungen; Test „blosse Erwaehnung loest nicht aus" (der Satz „Das Abbruchkriterium … ist NICHT erreicht" darf nicht auslösen) |
| `/ds`-Queue sichtbar (4) | `aussensicht.eingaben` Block `=== /ds-QUEUE ===` über `queue.deliver_block`; Prompt-Test prüft den Block |
| (a) Kernzahlen nur gegen C-Batches | `aussensicht.kernzahl_stillstand` filtert B-Batches über `ist_b_batch` (Pflichtzeile) heraus; Tests: ein einzelner C-Batch ⇒ kein Auslöser, zwei C-Batches mit Stillstand ⇒ Auslöser, bewegte Zahlen ⇒ kein Auslöser; B-Schritt-Stillstand separat über `b_schritt_stillstand` |
| (b) Beleg-Pflicht gelockert | `aussensicht.beleg_gueltig`: `Datei:Zeile` ODER Zahl + Quelldatei ODER `Fehlstelle: …`; Test mit allen drei Formen und einer Gegenprobe ohne Beleg |
| (c) Stichprobenpflicht | `prompts/aussensicht.md` (eigener Abschnitt) + `aussensicht.FORMAT_HINWEIS` (Block „STICHPROBEN (PFLICHT)"); Prompt-Test verlangt „mindestens ZWEI" und den Denkblock-Pfad `snapshots/b<N>/reasoning.jsonl`. Lesezugriff: `snapshots/` liegt in `cfg.root`, das per `pfad_regeln((cfg.root, cfg.decomp))` + `--add-dir` freigegeben ist |
| (d) Antwortpflicht + Register | `reviewer.md` (Block „Aussensicht-Befunde beantworten"), `aussensicht.antworten_uebernehmen` (Regex auf `M<batch>-<n>: übernommen/abgelehnt/erledigt/verworfen`), aufgerufen nach jedem gültigen Review in `_loop`; unbeantwortet bleibt `offen` und steht weiter in `zeile()` |

## 3. Auslöser — gemessen/geprüft in Tests

| Auslöser | Test |
|---|---|
| `/meta` (Vormerkung, mehrfaches zählt einmal) | `TestAusloeser.test_vorgemerkt_ist_ein_grund_und_zaehlt_einmal`, `TestOrchestratorAblauf.test_mehrfaches_vormerken_bleibt_eines` |
| alle 10 Batches (erst nach der ersten Aussensicht) | `test_zehn_batches_erst_nach_der_ersten_aussensicht` |
| Worker-Abbruch | `test_worker_abbruch_loest_aus` |
| Meilenstein / Abbruchkriterium (Pflichtzeilen) | `test_meilenstein_und_abbruchkriterium_loesen_aus`, `test_blosse_erwaehnung_loest_nicht_aus` |
| B-Schritt-Stillstand | `test_b_schritt_stillstand_loest_aus`, `test_b_schritt_fortschritt_loest_nicht_aus` |
| Kernzahl-Stillstand (nur C-Batches) | `test_kernzahl_stillstand_nur_ueber_c_batches`, `test_kernzahl_stillstand_ueber_zwei_c_batches`, `test_kernzahl_bewegung_loest_nicht_aus` |
| nur einmal je Batch (Merker `geprueft_batch`), `/meta` sticht den Merker | `test_nach_entscheidung_kein_zweiter_lauf_fuer_denselben_batch` |
| nie während ein Worker läuft | `TestOrchestratorAblauf.test_waehrend_worker_wird_nur_vorgemerkt` |

## 4. Tests und Zustand

- `tests/test_r13w_fixes.py`: **29 Tests grün**.
- Volle Reihe: **528 Tests, OK** (306,1 s; vorher 499).
- **Nebenbefund (gemessen, nicht angenommen):** zum Zeitpunkt des Commits lief der
  Harness **nicht** — `state/run.json` stand auf `STOPPED` (Batch 207, Phase „gate
  Batch 208", letzter Protokolleintrag `2026-09-28T14:22:53 Harness beendet sich nach
  Stopp`), es lebte nur ein `hx.cli watch`. Deshalb konnte die volle Reihe gefahren
  werden, ohne den Betrieb zu stören. **Nichts** am laufenden Betrieb geändert: keine
  Zustandsdatei, kein `state/ctl/*`, kein Harness-Prozess angefasst.
- Wirksam nach Neustart: Code und `harness.toml` liest der Harness beim Start.
  `prompts/reviewer.md` liest er je Review frisch von der Platte — die neuen
  Pflichtzeilen gelten also schon für das nächste Review, ohne Neustart.
