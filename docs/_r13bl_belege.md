# R13bl — Harness-Wartung (02.10.2026)

Vier Punkte des Nutzers, **je Punkt ein Commit**. Das Decomp-Repo bleibt unberuehrt.
Der Harness **laeuft** (PID 7460, gestartet 01.10. 21:24) und steht im Zustand
`GATE_APPROVAL`, `batch=236`, `worker=None` — es lief also **kein Batch**; die neuen
`hx/`-Fassungen greifen erst nach dem Neustart am Gate nach B237. `prompts/*.md` liest der
laufende Prozess je Lauf von der Platte, `harness.toml` nur beim Start (bekannte Regel,
`docs/bedienung.md` §12t).

---

## Teil 1 — Pflichtzeile `B-SCHRITT:` fuehrt die B-Nummer als Zaehlung

**Auftrag:** die Vorlage `B-Batch X von max 20` in `prompts/reviewer.md` ersetzen durch
`B-Batch X (Zählung, keine Grenze – Nutzerentscheid 30.09.)`. Vorher Grep ueber `prompts/`,
`hx/`, `tests/` nach `max 20` und `20 B-Batches`, jede Fundstelle mit `Datei:Zeile` nennen
**und entscheiden**.

### Fundstellen und Entscheidung

| Fundstelle | was dort steht | Entscheidung |
|---|---|---|
| `prompts/reviewer.md:431` | Blockformat-Vorlage der Telegram-Zusammenfassung | **geaendert** |
| `prompts/reviewer.md:448` | die Pflichtzeile im Abschnitt „Strang B" | **geaendert** |
| `prompts/reviewer.md:450` | Beispielzeile + Folgesatz | **geaendert** (+ Satz: Grenze seit 30.09.2026 aufgehoben, `k` ist Zaehlung, kein Budget) |
| `hx/stand.py:2212` | der Text, den der Harness in den Review-Prompt schreibt (`pflichtzeile_hinweis`) | **geaendert** (sonst driftet Prompt gegen Vorlage) |
| `docs/bedienung.md:858` | Zitat-Spalte einer Beleg-Tafel („Pflichtzeile im Review dieses Batches") | **bleibt** — Zitat eines echten Dokuments; die Regel steht in §8, die Aenderung in §13 |
| `harness.toml:167` | Begruendung des Stillstands-Zaehlers („Budget von 10-20 B-Batches") | **bleibt** — historische Begruendung, keine aktive Regel |
| `tests/fixtures/stand_b224/root/runs/b214/auftrag.md:119` | eingefrorene Fixture (echtes Dokument vom 30.09.) | **bleibt** — eine Fixture darf nicht rueckdatiert werden; sie haelt den damaligen Stand |
| `tests/test_r13aa_fixes.py:219,264,303` | Reviewer-Summaries als **Testeingabe** | **bleiben** — Eingabe, kein erzeugter Text |
| `tests/test_r13ah_fixes.py:581` | dito | **bleibt** |
| `tests/test_r13w_fixes.py:168,300,321,322,333` | dito | **bleiben** |

**Warum die Testeingaben bleiben duerfen:** der Parser liest nur `B-SCHRITT: <n>/5`
(`stand._RE_B_SCHRITT`, `stand.py:1889`) — der Zusatz „von max 20" war fuer die Maschine nie
relevant. Belegt durch `test_der_parser_haengt_nicht_am_wortlaut` (alte **und** neue
Schreibweise werden erkannt).

### Aenderung

- `prompts/reviewer.md`: Blockformat-Zeile, Pflichtzeile und Beispiel auf
  `B-Batch <k> (Zählung, keine Grenze – Nutzerentscheid 30.09.)`.
- `hx/stand.py::pflichtzeile_hinweis`: derselbe Wortlaut (ASCII-Schreibweise des Moduls).

### Test (Punkt 1)

```
python -m unittest discover -s tests -p test_r13bl_fixes.py -v
Ran 4 tests in 0.361s
OK
```

Enthalten: Vorlage ohne „von max 20"; Hinweistext mit „keine Grenze";
**erzeugter** Reviewer-Prompt (ueber `review_context` + `reviewer.build_prompt`) ohne
„von max 20"; Parser-Toleranz gegenueber beiden Schreibweisen.

---

## Teil 2 — Rueckbau der vorlaeufigen Zeitgrenzen (R13bj)

**Auftrag:** `bash_max_timeout_s` 3600 -> 1800, `hard_wall_s` 14400 -> 10800,
Worker-Timeout 3600000 -> 1800000; Grep ueber `prompts/` und `hx/` nach `3600000` und
`3600`; `docs/bedienung.md` §13 nachziehen.

### Die Bedingung ist erfuellt (gemessen, nicht uebernommen)

R13bj hatte den Rueckbau an „Preflight wieder unter 900 s" gebunden.

| Messung | Wert | Quelle |
|---|---|---|
| gueltiger Preflight B236 (Werkzeugaufruf) | **456,8 s** | `runs/b236/result.json` -> `stats.laufzeit.langsamste` |
| derselbe Lauf, Zeitentafel | **455,171 s** Gesamtwanduhr (Summe der Teilschritte 454,876 s, Abweichung 0,06 %) | `analysis/_m236/_preflight_zeiten.txt` |
| erster Lauf von B236, **fehlgeschlagen** | 1032,3 s | `analysis/_m236/_preflight_236_fehllauf1.txt` (3708 B) |

Der fehlgeschlagene Lauf zaehlt nicht (R373: genau **ein gueltiger** Preflight je Batch);
er ist der Grund, warum hier **beide** Zahlen stehen und nicht nur die guenstige.

### Fundstellen und Entscheidung (`3600000` / `3600`)

| Fundstelle | Entscheidung |
|---|---|
| `harness.toml:46-50` (`bash_max_timeout_s` = 3600) | **geaendert** -> 1800, Begruendung ersetzt (R13bj-Block durch R13bl-Block) |
| `harness.toml:53-57` (`hard_wall_s` = 14400) | **geaendert** -> 10800 |
| `hx/worker.py:1625` („bis 3600000 = 60 min") | **geaendert** -> 1800000 / 30 min |
| `hx/worker.py:1629-1633` (R13bj-Notiz) | **geaendert** -> R13bl-Notiz mit dem Rueckbau-Grund |
| `hx/worker.py:1636` („laenger als 60 min") | **geaendert** -> 30 min |
| `hx/worker.py:1670-1672` („`timeout=3600000` setzen") | **geaendert** -> 1800000; „seit R13bj 3600 s" -> „seit R13ah 1800 s" |
| `prompts/reviewer.md:222` („`timeout=3600000` (60 min)") | **geaendert** -> 1800000 / 30 min |
| `prompts/reviewer.md:227-230` (R13bj-Notiz) | **geaendert** -> R13bl-Notiz (die historische Nennung „vorlaeufig auf 3600000" bleibt stehen) |
| `hx/envs.py:139,145` | **bleibt** — das ist der Rueckfallwert (`bash_max_timeout_s`, Vorgabe 1800) und stimmt mit dem Rueckbau ueberein; ein Test haelt die Kopplung fest |
| `hx/\{orchestrator,stand,streamjson,uhr,util\}.py` (`3600` in `divmod`, `24*3600`, `5*3600`) | **bleiben** — Sekunden je Stunde, nichts mit der Grenze zu tun |
| `hx/uhr.py:33` `MAX_START_ALTER_S = 5 * 3600` | **bleibt** — R13bj hatte 4 h -> 5 h gesetzt; das war **nicht** Teil des Rueckbau-Auftrags. Ohne Wirkung auf die Laufzeit, aber **offen zur Entscheidung** (in §13 vermerkt) |
| `docs/bedienung.md:1070,1080,1744,1746,1751` (§12b, §12x, §13) | **geaendert** — §13 ist jetzt eine Ist-Tafel statt einer Rueckbau-Ankuendigung |
| `docs/_r13bj_belege.md` | **bleibt** — alter Beleg, wird nicht rueckdatiert |
| `tests/fixtures/**/auftrag.md` (alte Auftraege) | **bleiben** — Fixtures |
| `tests/test_r13ah/aj/ad/bj/v_fixes.py` | **geaendert** — sie prueften die vorlaeufigen Zahlen; jetzt die zurueckgebauten |

### Aenderung

Vier Stellen plus Handbuch: `harness.toml` (2 Werte), `hx/worker.py` (Vorspann, 3 Stellen),
`prompts/reviewer.md` (Lange Befehle), `docs/bedienung.md` (§12b, §12x, §13).

### Test (Punkt 2)

```
test_r13bl_fixes.py  rc=0  Ran 8 tests ; OK
test_r13ah_fixes.py  rc=0  Ran 49 tests in 71.980s ; OK
test_r13aj_fixes.py  rc=0  Ran 20 tests in 0.302s ; OK
test_r13ad_fixes.py  rc=0  Ran 30 tests in 0.459s ; OK
test_r13bj_fixes.py  rc=0  Ran 20 tests in 0.235s ; OK
test_r13v_fixes.py   rc=0  Ran 17 tests in 0.034s ; OK
test_r13aa_fixes.py  rc=0  Ran 33 tests in 2.237s ; OK
test_r13w_fixes.py   rc=0  Ran 45 tests in 45.815s ; OK
```

Neu in `test_r13bl_fixes.py`: Config-Werte, `BASH_MAX_TIMEOUT_MS` = 1800000,
**die drei Quellen nennen dieselbe Zahl** (Config, Worker-Vorspann, `reviewer.md`; der
Vorspann enthaelt `3600000` nicht mehr) und das Handbuch §13.

**Zwei Selbstkorrekturen aus diesem Lauf** (der erste Durchgang war rot): die Zusicherung
„`3600000` kommt in `reviewer.md` nicht mehr vor" war falsch — die **historische** Nennung
muss stehen bleiben, weg muss die **Vorschrift**-Form `timeout=3600000`; und
`test_r13ad_fixes.py:199` pruefte noch `hard_wall_s == 14400`.

---

## Teil 3 — R391-Sperre im PreToolUse-Hook

**Auftrag:** solange im laufenden Batch kein Commit existiert, dessen Betreff mit
`B<N>: Vorhersage` **beginnt**, blockiert der Worker-Hook `Edit`/`Write`/`MultiEdit` auf
Pfade unter `port/` und `scripts/`; der Worker bekommt den Hinweis „erst Vorhersage-Commit".
Varianten (`B<N>: Vorhersage Fortsetzung`, `B<N>: Vorhersage-Nachtrag (…)`) zaehlen;
`analysis/` bleibt frei; `N` kommt aus der Harness-eigenen Zaehlung (R13bj).

### Wo es sitzt

| Ort | Aenderung |
|---|---|
| `tools/batch_uhr.py` (`--pre`-Zweig) | neue Funktionen `r391_grund`, `vorhersage_vorhanden`, `_batch_nummer`, `_betreffs`, `_blockieren`; der Preflight-Stopp (R13be-2) laeuft unveraendert **danach** |
| `tools/batch_uhr.py` (Modul-Docstring) | Regel, Grenzen und Zuständigkeiten beschrieben |
| `hx/reihenfolge.py` | `port_token` zu `pfad_token(text, decomp, name)` verallgemeinert — die Sperre baut die Pfaderkennung **nicht nach** |
| `hx/worker.py::write_worker_hooks` | `--decomp <Decomp-Repo>` in den Hook-Argumenten |

Die Betreffs-Regel ist **nicht nachgebaut**: `reihenfolge.vorhersage_muster(batch)`
(R13as, BOM-tolerant, Wortgrenze) — damit zaehlen die genannten Varianten automatisch.
Der Parser `vorhersage_zeilen_lesen` liest dieselben `git log`-Zeilen wie der Waechter.

### Im Code dokumentiert (Auftrag)

* **Bash-Schreibzugriffe erfasst die Sperre nicht** (Umleitung, `Set-Content`,
  `Copy-Item`, `git checkout`): der Hook hat dort keinen Dateipfad. Dafuer bleibt der
  **Reihenfolge-Waechter** zustaendig — er liest den Mitschnitt nach dem Lauf und zaehlt
  genau diese Faelle (`port_vor_vorhersage`). In B218 waren es 17 `Edit`-Aufrufe.
* **Fortsetzung/Wiederholung derselben Nummer:** gesucht wird ein Commit mit dem Betreff
  der LAUFENDEN Nummer, unabhaengig vom Zeitpunkt — ein im Voriauf entstandener
  Vorhersage-Commit zaehlt also.
* **`analysis/` bleibt frei** — dort wird die Vorhersage begruendet, das ist kein Eingriff.
* **Ohne Nummer im Zustand wird nichts blockiert** (kein Raten); jeder Block bekommt eine
  Zeile in `runs/b<N>/vorhersage-blockiert.jsonl`.

### Test (Punkt 3)

```
test_r13bl_fixes.py  rc=0  Ran 19 tests in 27.543s ; OK
```

Der Hook wird als **Unterprozess** gefahren (so ruft die CLI ihn auf), gegen ein
Wegwerf-Git-Repo: `Edit` auf `port/` ohne Vorhersage-Commit -> `deny`; danach durch;
`analysis/` vorher durch; „Vorhersage-Nachtrag (Wiederholung)" und „Vorhersage
Fortsetzung" zaehlen; fremde Batchnummer (`B236`) zaehlt **nicht**; `scripts/` und
`MultiEdit` ebenfalls gesperrt; `PowerShell` wird **nicht** gesperrt (dokumentierte
Grenze); der Block liegt im Beleg; ohne Batchnummer kein Block.

### Nebenbefund (nicht im Auftrag, mitgeheilt)

`test_r13ae_fixes.py::TestZeitschwelle::test_config_ist_900_s_und_135_min` war **rot** —
und zwar schon vor diesem Auftrag. Er verlangte `umschalt_minuten(...) == 135.0`, aber
diese Zahl zieht die **gemessene** Preflight-Dauer des neuesten Batches vor
(`Alarm − max(15 min, Preflight + 5 min)`, R13ah). Gemessen mit dem lebenden Stand:
`stand.preflight_dauer` = **1032,3 s** (Batch 236, der fehlgeschlagene Lauf) ->
`150 − max(15, 17,205 + 5)` = **127,795 min** — exakt der gemeldete Istwert. Es ist damit
dieselbe Lebenddaten-Zusicherung, die R13bd schon einmal entfernt hat; die Zusicherung
prueft jetzt die **Rechnung** (`umschalt = 150 − vorlauf`, `vorlauf = max(15, preflight+5)`)
statt einer festen Zahl.
---

## Teil 5 — die volle Testreihe und ihre zwei Fehlschlaege

Am Gate (Zustand `GATE_APPROVAL`, `worker=None` — es lief kein Batch) lief die volle Reihe
mit dem Projekt-Werkzeug (`docs/_r13av_lauf.py` gegen `docs/_r13bl_volle_reihe.txt`).
**Erster Lauf: rot.**

```
Tests: 1369 | Fehler: 0 | Fehlschläge: 2 | übersprungen: 0
Dauer: 544,6 s   HEAD: 0565f25   ERGEBNIS: FEHLGESCHLAGEN
```

Beleg: `docs/_r13bl_volle_reihe_rot.txt` (unveraendert archiviert).

| Fehlschlag | Ursache | wem zuzuordnen |
|---|---|---|
| `test_r13bf_fixes.TestZweiterPreflight.test_nicht_committete_aenderung_zaehlt_nach_der_zeit` | Der Test nahm als „Preflight-Start" den **festen** Zeitpunkt `2026-10-01T23:59:59+00:00`. Die Uhr hat ihn in der Nacht zum 02.10. eingeholt; danach lag die Dateizeit der Testdatei **nach** dem Start, und `aenderung_seit_preflight` meldete korrekt „geaendert". **Abgelaufene Zusicherung, nicht durch diese Runde verursacht** — dieselbe Klasse wie die Lebenddaten-Falle (R13bd). | R13bf |
| `test_r13bj_fixes.TestZeitgrenzen.test_handbuch_traegt_den_rueckbau_vermerk` | **Mein Fehler.** Ich hatte die Zusicherung `"B236 brauchte 456 s"` geschrieben, danach den §13-Satz nachgeschaerft („der **gueltige** Preflight von B236 brauchte **456 s**") und diese Testdatei **nicht erneut gefahren** — genau der Fallstrick, den R13be schon einmal notiert hat. | R13bl-2 |

**Behebung** (Commit `R13bl-5`):

* `test_r13bf_fixes`: der Start liegt jetzt **relativ zu jetzt** eine Stunde in der Zukunft
  (`datetime.now(timezone.utc) + timedelta(hours=1)`) — kein ablaufendes Datum mehr.
* `test_r13bj_fixes`: die Zusicherung prueft den **stabilen Teil** der Aussage
  (`"Preflight von B236 brauchte"` + `"456 s"`) statt der zuerst geschriebenen Wortfolge.

Nachweis: beide Dateien einzeln gruen (20 Tests / 20 Tests), danach die volle Reihe erneut.

**Lehre fuer die naechste Runde:** Wer eine Zusicherung auf einen **Wortlaut** schreibt,
muss die Datei nach JEDER Umformulierung dieses Wortlauts erneut fahren — ein gruener
Einzellauf von vor zehn Minuten beweist nichts. Und feste Zeitpunkte in Tests sind
Schulden mit Faelligkeitsdatum.
