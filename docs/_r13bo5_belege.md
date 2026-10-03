# R13bo-5 Belege (Harness-Wartung 2026-10-03)

Auftrag: Stillstandsmelder, Plan/Ist+Prognose auf Insn, Worker-Vorlage, zwei
Pruefungen, eine Messung. Commits siehe `git log`. Das Decomp-Repo wurde nicht
angefasst.

## Punkt 1 - Stillstandsmelder (Aussensicht M239-2/M236-7)

GEMESSEN am lebenden Stand:

* Zeile `Hybrid-Lauf` (200M-Schranke), Halt-PC **8000EC3C**, Wegmass 3120/42599 -
  unveraendert seit B238. Der alte Melder verglich genau das und schlug in B250 an.
* Zeile `Hybrid-A4` (echter Halt): B240-B247 `655951355 / 8001684C`, **B248
  `181055466 / 8000A164` (Form)**, B249-B254 `696571792 / 8001684C`. Der Wechsel in
  B248 war die Bewegung, die der alte Melder nicht sah.
* Die Reihe `Hybrid-A4` ueber B248/B249/B250 hat ZWEI verschiedene Halt-PC -> kein
  Stillstand; zusaetzlich schweigt der Melder, weil B251-B254 C-Batches sind
  (`strang_von_batch`).

Umsetzung: `stand.hybrid_a4_verlauf` (Halt-PC/Schritte/Art der A4-Zeile),
`stand.preflight_hybrid_fehler` (nur der STATUS `FEHLER` einer **Hybrid**-Zeile -
das blosse Wort steht in JEDER Datei in der GL-Zeile "0 sonst. FEHLER"; der erste
Anlauf mit "jede Zeile" lieferte eine LEERE Reihe), `aussensicht.hybrid_stillstand`
(Quelle A4, Ruhe-Guard ueber die letzten 3 Batches), `hybrid_neuester_b` (Marke,
gleiche Quelle). Der Grund heisst weiter "Hybrid-Lauf haengt" (so heisst der
Ausloeser), die Meldung nennt die Quelle `Zeile "Hybrid-A4"`.

## Punkt 2 - Zielgroesse und Prognose fuer C (Aussensicht M249-4)

Reihe `Ausgefuehrte Menge`, eigene referenzgleiche Insn = Zuwachs der kumulierten
`referenzgleich Insn` gegen den vorigen gemessenen Batch:

| Batch | referenzgleich Insn | eigene Insn | davon nicht referenzgleich (offen) |
|---|---|---|---|
| B250 (Basis, Feld fehlt: 69355-65052) | 4303 | - | 65052 |
| B251 | 4813 | **510** | 64542 |
| B252 | 5004 | **191** | 64351 |
| B253 | 5465 | **461** | 63890 |
| B254 | 5641 | **176** | 63714 |

Median der letzten 4 C-Batches = **326** Insn (Spanne 176..510). Prognose =
63714 / 326 = **ca. 195 C-Batches** (Spanne 63714/510 .. 63714/176 = ca. 125..362).
`davon in teilgeprueften Koepfen` (Feld `referenzgleich aber teilgeprueft`) = 29.
Umsetzung: `stand.ausgefuehrte_menge`, `stand.c_insn_rate`, `stand.c_insn_text`;
`plan_ist_text` zeigt die C-INSN-Zeile, das ZIEL und die HYPOTHESIS, die
Kopf-Medianzeile ist nur noch Einordnung (kein "hoechstens ca. N Koepfe").
Test: `tests/test_r13bo5_fixes.py::TestReihe` mit genau dieser Reihe.

## Punkt 3 - Worker-Vorlage (R13aj/R13bj)

`hx/worker.py::WORKER_PREAMBLE`: gestrichen sind "Unabhaengige Rechenlaeufe parallel
starten, nicht nacheinander." und der Hintergrund-"Weg 2" (`Start-Process … -PassThru`
plus `Wait-Process -Id $p.Id -Timeout 480`). Ersetzt durch EINEN blockierenden Aufruf
(`timeout` bis 1800000 = 30 min), "Hybrid-Laeufe NIE parallel" und den Verweis auf
Stopp-Schalter/Vorwaermskript des Auftrags. Mitgezogen: der Kommentar an der
Start-Sleep-Sperre und der Abbruchtext der Warteschleifen-Notbremse
(`hx/worker.py`). Der erlaubte **gezielte** Prozessabbau (`Start-Process … -PassThru`
fuer die PID, R13i) bleibt.
Test: `tests/test_r13bo5_fixes.py::TestWorkerVorlage`.

## Punkt 4a - Lesepfade der Aussensicht (NUR GEPRUEFT)

**Wo die Datei liegt:** `g:\Harness\tools\r13t_cov_relevanz.py` - ein Geschwister von
`g:\Harness\harness`, also **ausserhalb** der beiden Lesewurzeln der Aussensicht.
Genau das ist die Meldung "g:\Harness ausserhalb von harness\ abgelehnt".

**Welche Lesepfade die Aussensicht hat** (`hx/aussensicht.py::build_command:1258`):

* `--allowedTools *pfad_regeln((cfg.root, cfg.decomp))` - `hx/aussensicht.py:1276`
* `--add-dir cfg.root` und `--add-dir cfg.decomp` - `:1282`/`:1283`
* Verbote: `VERBOTEN` (`:76`, Bash/Write/Edit/…), `git_schreib_verbote` (`:1279`),
  `secrets_verbote(cfg.secrets_dir, *secrets.ALT_ORTE)` (`:1280`),
  `credential_verbote` (`:1281`)

`cfg.root` = `g:/Harness/harness`, `cfg.decomp` = `g:/Silent Scope Decomp`
(`harness.toml` `[paths]`). **`cfg.harness_home` = `g:/Harness` ist NICHT dabei** -
obwohl der Harness-Code selbst darueber liest (z. B. `stand.port_relevanz`,
`hx/stand.py:2110` liest `docs/_port_relevanz.json`). Das Modell sieht die Zahl also
im Prompt, das Werkzeug dahinter aber nicht.

**Vorschlaege mit Aufwand:**

1. **Nichts aendern (Aufwand 0).** Der Inhalt des Werkzeugs steht als Zahl schon im
   Prompt (BILANZ-Block aus `stand.port_relevanz`/`_relevanz_zeilen`). Empfehlung:
   einen Satz in `prompts/aussensicht.md` ergaenzen, dass Werkzeuge unter
   `g:\Harness\tools` nicht lesbar sind und die Zahlen im BILANZ-Block stehen.
2. **Wurzel oeffnen (klein, ~5 Zeilen + 1 Test).** `pfad_regeln((cfg.harness_home,
   cfg.decomp))` und `--add-dir cfg.harness_home` in `aussensicht.build_command`.
   ZWINGEND `cfg.backups_dir` in `secrets_verbote` aufnehmen - sonst wird
   `g:\Harness\backups` mitgelesen (`/ask` macht das schon:
   `hx/ask.py:227`). Danach sind `docs/` und `tools/` lesbar (gewollt), `secrets/`
   und `backups/` bleiben gesperrt.
3. **Feiner (mittel).** Nur `harness_home/docs` und `harness_home/tools` erlauben -
   weniger Angriffsflaeche, mehr Regeln zu pflegen.
4. **Alternative (Aufwand klein, aber Duplikat).** Das Werkzeug nach
   `harness/tools/` kopieren/verschieben; dann liegt es in der erlaubten Wurzel.

## Punkt 4b - Das Modellfeld (NUR GEPRUEFT)

In `runs/b251..b254/result.json` gibt es **keinen Top-Level-Schluessel `modell`**.
Der Wert steht **im Block `review`**:

```json
"review": {"batch": 251, "modell": "claude-opus-5-5,claude-sonnet-5-5",
           "modell_soll": "claude-sonnet-5-5", "art": "C", "effort": "high",
           "kind": "batch_end", "session_id": "ed90113a-…",
           "ts": "2026-10-03T04:02:35+00:00"}
```

* **Schreiber:** `Orchestrator.review_in_result` (`hx/orchestrator.py:2202`), der Block
  ab `:2216`, das Feld in `:2218`.
* **Herkunft des Werts:** `ReviewResult.model_seen` - die vom Reviewer-Lauf
  GEMELDETE Modell-Liste, komma-verbunden aus `result.modelUsage`
  (`hx/reviewer.py:200-202`). Zwei Namen heissen: die Session lief unter mehr als
  einem Modell (hier `ed90113a-…`, unter Opus angelegt und mit `--resume` unter
  Sonnet weitergefuehrt).
* **Nur Reviews.** Die Aussensicht schreibt ihr Modell woanders: `runs/meta-<N>.json`
  Feld `modell` (`hx/aussensicht.py:1913-1915`). `/ask` hat kein `result.json`; sein
  Modell steht im Rueckgabe-Feld `modell` (`hx/ask.py:360`) und im `result`-Ereignis
  von `logs/ask/ask-<stempel>.jsonl`.
* **Das Modell des Reviews allein:** `runs/b<N>/result.json -> review.modell`
  (gesehen) und `review.modell_soll` (gewaehlt), `review.art` (B/C/unklar).
  Zusaetzlich `state/run.json -> reviewer.model_seen/modell_soll/modell_art/effort`.
  Fuer "welches Modell war gewaehlt" ist `modell_soll` die verlaessliche Angabe;
  `model_ok` ist eine Teilmengenpruefung (`hx/reviewer.py:307`), ein Komma-Wert ist
  daher kein Fehler.

## Punkt 5 - Verbrauch seit dem Neustart (NUR GEMESSEN)

Verfahren R13bn-2, Fenster seit dem Neustart (`logs/start-stderr.log`:
"=== Start 2026-10-02 21:44:00" lokal = 2026-10-02T19:44Z). Skript
`docs/_r13bo5_verbrauch.py`, Tafel in `docs/_r13bo5_verbrauch.txt`
(`docs/_r13bn_verbrauch.txt` bleibt unberuehrt). Kurzfassung:

| Typ | Aufrufe | Tokens (CLI) | Anteil am Abo | CLI-Kosten |
|---|---|---|---|---|
| Review | 8 | 7 284 213 | 32.4 % | $62.49 |
| Aussensicht | 3 | 14 692 186 | 65.4 % | $8.52 |
| /ask | 2 | 504 818 | 2.2 % | $0.58 |
| Worker | 13 | 211 671 157 | (eigene API) | $139.25 |

Je Modell: Review 4x `claude-opus-5-5` ($18.98) und 4x
`claude-opus-5-5,claude-sonnet-5-5` ($43.51); Aussensicht 3x `claude-opus-5-5`;
/ask 2x `claude-sonnet-5-5`; Worker `deepseek-flash[1m]`.

Rate-Limit seit dem Neustart: Woche 4 % -> 19 % (13 Messpunkte), Sitzung 7..71 %.
Letzter Stand (`logs/rate-limit.json`, 03.10. 12:05 durch /ask): Sitzung 17 %,
Woche 19 %, Reset der Woche 06.10. 07:00.

Die Aussensicht ist mit **65 % Anteil** der teuerste Abo-Posten im Fenster (3 Laeufe,
14,7 Mio Tokens) - fuer die Auswertung nach Paragraph 19 zu beachten.
