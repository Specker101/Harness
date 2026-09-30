# R13aq-Belege (2026-09-30): gescheiterte Aussensicht zählt nicht, Zuglimit, „zur Kenntnis"

Auftrag: **1.** Bericht, warum `runs/meta-217.md` rc=1 hat (Log, subtype, Züge), wie hoch
das Zuglimit ist (Datei:Zeile) und wie viele Züge die erfolgreichen Läufe meta-208…meta-216
brauchten. **2.** Bericht, welche Marken der Harness nach dem gescheiterten Lauf setzt und
ob rc=1 als erledigte Aussensicht zählt. **3.** Fix: rc ≠ 0 oder 0 Befunde ohne
AUSSENSICHT-Block zählt nicht als gelaufen (keine Marke, Telegram-Meldung, genau eine
Wiederholung beim nächsten Batch-Ende), Zuglimit konfigurierbar (`meta_max_turns`) mit
Reserve, Frist im Prompt, kein Ersatz-Eintrag im Register. **4.** `_RE_VERDIKT` um
„zur Kenntnis" erweitern (zählt wie „erledigt"), M213-4a nachtragen.

Messwerte: `docs/_r13aq_messung.txt` (Werkzeug `docs/_r13aq_probe.py`, nur lesend).

## 1. Warum rc=1 (Punkt 1 des Auftrags)

`runs/meta-217.jsonl`, letztes Ereignis:

```
{"type":"result","subtype":"error_max_turns","is_error":true,"num_turns":31,
 "duration_ms":200556,"errors":["Reached maximum number of turns (30)"]}
```

* **Ursache: Zuglimit.** Der Lauf brauchte für die Vorarbeit alle Züge und schrieb vor dem
  Abbruch nur einen Zwischenstand („Zwischenstand: B217 hat die R391-Reihenfolge
  eingehalten … Jetzt die Tiefenprobe B214") — 0 Befunde, keine Zusammenfassung.
  `runs/meta-217.md`: `rc=1 dauer=202s modell=claude-opus-5-5 befunde=0 verworfen=0`.
* **Zuglimit, Datei:Zeile:** `harness/harness.toml:131` (`[meta] max_turns = 30`, vorher),
  Rückfall-Vorgabe `hx/aussensicht.py:66` (`STANDARD … "max_turns": 30`), wirksam über
  `--max-turns` in `hx/aussensicht.py:build_command` (`grenzen(cfg)["max_turns"]`).
* **Züge der erfolgreichen Läufe** (aus den Mitschnitten):

| Lauf | 208 | 209 | 210 | 211 | 212 | 213 | 214 | 217 |
|---|---|---|---|---|---|---|---|---|
| Züge (`num_turns`) | 28 | 17 | 26 | 25 | 24 | 29 | **35** | 31 (Abbruch) |

Der **größte** bisherige Lauf war also **35** Züge (meta-214) — genau der Grund, warum 30
zu knapp war. (Neu: **50** = 35 gemessen + Reserve, s. §3.)

**Nachtrag R13ar (30.09.2026):** `num_turns` ist **nicht** die Zahl, gegen die die CLI ihr
`--max-turns` prüft — sie zählt **Werkzeugrunden**. meta-214 brauchte nur **23** Runden
(deshalb lief er mit Limit 30 durch), meta-217 genau **30** (deshalb der Abbruch).
Messung: `docs/_r13ar_belege.md` §1. Das Zuglimit von 50 bleibt davon unberührt (23 bzw.
30 Runden liegen darunter).

## 2. Marken nach dem gescheiterten Lauf (Punkt 2 des Auftrags)

`state/run.json` unmittelbar nach dem Lauf (gemessen):

| Marke | Wert | Bedeutung |
|---|---|---|
| `letzter_lauf_batch` | **217** | die Takt-Marke stand auf dem **gescheiterten** Lauf |
| `letzter_lauf_ts` | 2026-09-29T22:49:49+00:00 | Zeitstempel des gescheiterten Laufs |
| `geprueft_batch` | 217 | für diesen Batch war entschieden (Entprellung) |
| `vorgemerkt` | False | /meta-Vormerkung verbraucht |
| `kernzahl_gemeldet_bis` | 210 | **unverändert** (wird nur bei `rc == 0` gesetzt) |
| `c_soll_null_gemeldet_bis` | 0 | unverändert (dito) |
| `hybrid_gemeldet_bis` | 0 | unverändert (dito) |

**Antwort: Ja — rc=1 zählte als erledigte Aussensicht.** Die drei Stillstands-Marken waren
schon seit einem früheren Auftrag auf `rc == 0` beschränkt, die **Takt-Marke**
(`letzter_lauf_batch`) wurde aber im `finally` **bedingungslos** gesetzt
(`hx/orchestrator.py`, alte Zeile 872-875). Folge: die Regel „alle 3 Batches" rechnete von
217 → der nächste automatische Lauf wäre erst bei **Batch 220** gekommen, mit einem
Bericht, der wie ein Ergebnis aussieht.

Weitere Messwerte: `updated_at` des Registers wurde vom gescheiterten Lauf auf
`2026-09-29T22:49:49` gesetzt, **sonst nichts** — 40 Befunde (unverändert), kein Eintrag
zu Batch 217, und die für den Lauf gezogene Tiefenprobe **B214** steht **nicht** unter
`gezogen` (`[205, 206, 212]`, R13ac3 wirkt: ein Lauf ohne Ergebnis verbraucht keinen
Batch). Die Anzeige „letzte Aussensicht" hat den gescheiterten Lauf trotzdem gezeigt
(`/bilanz` las den jüngsten Bericht) — behoben in §3d.

## 3. Der Fix

### 3a. Was als gelaufen zählt (`hx/aussensicht.py::gelaufen`)

```python
if int(res.rc or 0) != 0:                    # Abbruch (Zeitgrenze, Zuglimit, API)
    -> (False, "rc=1, error_max_turns, 31 Zuege")
if not (res.summary or res.befunde):         # kein <AUSSENSICHT>-Block
    -> (False, "kein AUSSENSICHT-Block in der Antwort (0 Befunde)")
sonst (True, "")
```

`Ergebnis` trägt dafür neu `subtype` und `zuege` (aus dem `result`-Ereignis), und
`describe()`/`bericht`/`meta-<N>.json` zeigen sie: der Bericht bekommt die Zeile
`- ERGEBNIS: GESCHEITERT (<Grund>) - zaehlt NICHT als Aussensicht, keine Marke, keine
Verdikte`, das JSON die Felder `gelaufen: false`, `gescheitert_grund`, `subtype`, `zuege`.

### 3b. Der Orchestrator (`_do_aussensicht`, `_aussensicht_gescheitert`)

| Fall | Verhalten |
|---|---|
| **gelaufen** | wie bisher; `letzter_lauf_batch`/`letzter_lauf_ts`/`geprueft_batch` werden gesetzt, der Fehlvermerk gelöscht |
| **rc ≠ 0 oder kein Block** | Bericht wird geschrieben (Beleg!), aber **nichts** angewendet: `verteile` wird nicht gerufen (keine Verdikte, keine Queue, kein Registereintrag) — Telegram: `Aussensicht B217 gescheitert (rc=1, error_max_turns, 31 Zuege), wird beim nächsten Batch-Ende wiederholt` + `Bericht: …` |
| **Ausnahme** | derselbe Weg (`Ausnahme: <Text>`) |
| **Wiederholung** | `meta.gescheitert_batch = 217` **und** der Bericht selbst: `aussensicht.faellig` meldet `Wiederholung nach gescheiterter Aussensicht B217 (rc=1, …)` — aber **erst**, wenn `batch > gescheitert_batch`, also beim nächsten Batch-Ende |
| **zwei Quellen für die Wiederholung** | (a) der Zustandsvermerk `gescheitert_batch` (seit diesem Fix) und (b) `aussensicht.bericht_zustand` — der jüngste Bericht mit `gelaufen: false` bzw. `rc != 0`, der noch nicht durch einen gelungenen Lauf überholt ist. (b) ist nötig, weil `runs/meta-217.json` **vor** dem Fix entstand (Zustandsvermerk fehlt) und weil ein Absturz zwischen Lauf und Zustandsschreiben die Wiederholung sonst verlöre. Der höhere der beiden Werte gilt |

**Eine Abweichung vom Wortlaut, bewusst und begründet:** `geprueft_batch` wird auch im
Fehlerfall auf den laufenden Batch gesetzt. Die Schleife ruft `aussensicht.faellig` in
**jedem** Durchgang (`hx/orchestrator.py`, Kommentar an der Aufrufstelle); ohne diese
Entprellung würde derselbe Lauf sofort wiederholt — je ~3,5 min und ein Opus-Lauf. Die
**Takt**-Marke (`letzter_lauf_batch`) bleibt dagegen stehen, d. h. der gescheiterte Lauf
zählt nicht als gelaufen — das war der Punkt. Ein Test hält beides fest
(`test_gescheiterter_lauf_setzt_keine_takt_marke`).

### 3c. Zuglimit (Punkt 3 des Auftrags)

* `harness/harness.toml:131`: `max_turns = 30` → **50** (Kommentar nennt Messung und Reserve).
* `hx/aussensicht.py::max_turns(cfg)`: liest **`[meta] meta_max_turns`** (der Name aus dem
  Auftrag), sonst das alte `[meta] max_turns`, sonst `STANDARD` (**50**). `grenzen()` nutzt
  die Funktion, damit alle Leser denselben Wert sehen (`build_command`, Prompt, Tests).
* Frist im Prompt (`build_prompt`, dynamisch): `ZEITLIMIT: Schreibe spaetestens nach 45
  Zuegen die Antwort im Blockformat, auch wenn die Tiefenprobe unvollstaendig ist;
  Unvollstaendiges als nicht geprueft kennzeichnen.` (Zahl = `max_turns - 5`).
  Dieselbe Regel als eigener Abschnitt „Zuglimit und Frist" in
  `harness/prompts/aussensicht.md` — mit dem gemessenen meta-217-Fall als Begründung.

### 3d. Anzeige „letzte Aussensicht" (`aussensicht.zeile`)

`/bilanz` und `/status` nennen jetzt die letzte **gelungene** Aussensicht; ein gescheiterter
Bericht wird übersprungen und eigens genannt:

```
Aussensicht: 40 Befunde, davon 40 uebernommen, 0 abgelehnt, 0 offen
  (letzte Aussensicht: Batch 214; 6 Befunde in diesem Lauf;
   zuletzt gescheitert: Batch 217 (wird wiederholt); Takt: alle 3 Batches)
```

Erkannt wird ein gescheiterter Bericht an `gelaufen: false` **oder** an `rc != 0` — der
zweite Fall, damit auch der **bestehende** `runs/meta-217.json` (rc=1, vom alten Code
geschrieben) richtig angezeigt wird, ohne einen Beleg nachträglich zu ändern. Alte Berichte
ohne beide Felder zählen als gelaufen.

### 3e. Kein Ersatz-Eintrag im Register

Der gescheiterte Lauf hat 40 Befunde, kein Eintrag zu Batch 217 (gemessen, §2) — und der
Fix ändert daran nichts: im Fehlerfall wird `verteile` übersprungen und
`bericht_schreiben` bekommt eine leere Verteilung; `verworfene_speichern` schreibt bei
leerer Liste nichts. Es wird also **weder** ein Befund **noch** ein „gescheitert"-Posten
ins Register gelegt; der Fehlvermerk lebt im Zustand (`meta`) und im Bericht.

## 4. „zur Kenntnis" als Verdikt (Punkt 4 des Auftrags)

* `hx/aussensicht.py::_RE_VERDIKT` kennt jetzt `zur\s+Kenntnis` (drittes Verdikt neben
  übernommen/abgelehnt/zurückgestellt), und `UEBERNOMMEN_WORTE` führt `"zur kenntnis"` —
  damit zählt `klasse()` es **wie „erledigt"** (also als übernommen, nicht als offen).
  Mehrfache Leerzeichen werden zu einem zusammengezogen (`" ".join(split())`).
* **Nachtrag ausgeführt** (`docs/_r13aq_nachtrag.py --schreiben`,
  Beleg `docs/_r13aq_nachtrag.txt`, Muster R13ak: Probelauf ist die Vorgabe):

```
runs/b217/review.md:15   M213-4a: zur Kenntnis - die Batch-Uhr bleibt das Maß
vorher:  status='offen'      antwort_batch=None
nachher: status='zur kenntnis' antwort_batch=216   (bewerteter Batch)
Quote:   40 Befunde, davon 39 uebernommen, 0 abgelehnt, 1 offen
     ->  40 Befunde, davon 40 uebernommen, 0 abgelehnt, 0 offen
Offene Befunde: keine
```

Die Registerdatei `harness/state/meta_befunde.json` ist gitignoriert — der Nachweis steht
deshalb als Belegdatei im Repo. Der Nachtrag ist idempotent (derselbe Aufruf setzt denselben
Wert) und wurde **nur** über dieses Skript geschrieben.

## 5. Tests

`harness/tests/test_r13aq_fixes.py` — **30 Tests**: `gelaufen()` (rc≠0, ohne Block, mit
Summary/Befunden; das echte `meta-217.jsonl` als Beispiel), Zuglimit (Alias-Vorrang,
Rückfall, kaputter Wert, Reserve gegen die 35 Züge, `--max-turns` im Kommando,
`harness.toml`-Wert), Prompt-Frist (45 bzw. 35 bei Limit 40), Auslöser (im selben Batch
keine Wiederholung, beim nächsten Batch-Ende schon, ohne Vermerk nicht, **der Bericht
allein trägt die Wiederholung**, ein überholter Bericht löst nicht aus), der
Orchestrator-Weg (gescheitert → Takt-Marke unverändert + `gescheitert_batch` + Telegram +
nichts in der Queue + `gelaufen:false` im JSON; leerer Lauf; gelungener Lauf setzt die
Marke und löscht den Vermerk; Ausnahme zählt nicht), „zur Kenntnis" (erkannt, zählt wie
erledigt, Prosa ohne Verdikt schließt nichts, echte Zeile aus `runs/b217/review.md`) und
die Statuszeile (gescheiterter Bericht wird übersprungen und genannt).

**Mitgezogen:** die Attrappen in `test_r13w_fixes.py` (45 Tests) und
`test_r13ah_fixes.py` (49 Tests) lieferten bei `rc=0` eine **leere** Antwort — nach der
neuen Regel ist das kein gelaufener Lauf, die Marken-Tests wurden deshalb rot (2 bzw. 1
Fehler, gemessen). Die Attrappen liefern jetzt eine Zusammenfassung, wie ein echter Lauf;
die Absicht der Tests („rc=0 setzt die Marke") bleibt unverändert.

Volle Reihe: **1035 Tests OK** in 432,5 s (`docs/_r13aq_volle_reihe.txt`; der Harness stand
beim Lauf am Gate, wie vom Auftrag verlangt). `pyflakes` meldet für die geänderten Dateien
nur die zwei f-String-Warnungen, die schon vorher in `aussensicht.py` standen (jetzt
Zeile 1080/1089 statt 1005/1014) und den alten `.envs`-Import in `orchestrator.py`.

## 6. Nicht geprüft / offen

* Die **Wiederholung** ist nicht mit einem echten Aussensicht-Lauf gemessen (das hätte
  einen Opus-Lauf gekostet); geprüft sind Auslöser und Orchestrator-Weg mit Attrappen —
  und **am echten Beleg**: `docs/_r13aq_messung.txt` §3 zeigt
  `bericht_zustand -> letzte_gelungen=B214, neuester_gescheitert=B217 (rc=1)` und
  `faellig(batch=218) -> ['Wiederholung nach gescheiterter Aussensicht B217 (rc=1)']`.
  Der gescheiterte **meta-217 wird also beim nächsten Batch-Ende (B218) von selbst
  wiederholt**, obwohl sein Zustandsvermerk fehlt (der Lauf war vor dem Fix). Gemessen
  wurde gegen eine **Kopie** des Zustands im Tempordner — unter `state/` wurde nichts
  geschrieben.
* Der laufende Harness (B217) hat die **alte** Fassung im Speicher; der Fix wirkt nach
  einem Neustart. `letzter_lauf_batch` steht dort noch auf 217 (die alte Fassung hat es
  gesetzt) — für die Anzeige und den Auslöser ist das ohne Belang, beide lesen jetzt den
  Bericht.
* Die **Frist im Prompt** ist eine Bitte an das Modell, keine Sperre: ob sie greift,
  zeigt erst der nächste Lauf mit vielen Zügen. Das Zuglimit selbst (50) ist hart.
* `meta_max_turns` ist als **Alias** angelegt (`max_turns` gilt weiter) — der Auftrag
  nannte den Namen, `harness.toml:131` führt `max_turns`. Beide Wege sind getestet.
