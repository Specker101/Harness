# R13bm Punkt 5: `uhr.MAX_START_ALTER_S` geprueft (R13bj 4 h -> 5 h)

Auftrag: **nur pruefen** - was die Zahl steuert, ob sie an `hard_wall_s` gekoppelt war;
wenn ja, zurueck auf 4 h mit Begruendung. Stand: 02.10.2026, HEAD `c443cdd` vor diesem
Commit.

## 1. Was die Zahl steuert (CONFIRMED, quellenbelegt)

`hx/uhr.py` - die Batch-Uhr (R13ac). `MAX_START_ALTER_S` ist eine **Plausibilitaetsgrenze
fuer einen Zeitstempel**, keine Grenze des Laufs:

| Stelle | Wirkung |
| --- | --- |
| `hx/uhr.py:88` (`start_zeit`) | `unplausibel = alter > MAX_START_ALTER_S or alter < -ZUKUNFT_TOLERANZ_S` |
| `hx/uhr.py:227` (`uhr_text`) | ab `unplausibel` steht im Text: "HINWEIS: der Zeitstempel ist unplausibel alt - er kann aus einem abgebrochenen Lauf stammen" |
| `hx/watch.py:257` | die Anzeige nennt **keine Laufzeit**, sondern "Laufzeit nicht gemessen (Startzeit im Zustand unplausibel …)" |

Kein Prozess wird beendet, kein Batch abgebrochen, kein Budget verbraucht. Gemessen wird
nur `state/run.json:worker.started_at`; die Zahl entscheidet, ob der Worker und die
Anzeige dieser Startzeit **trauen**. Anlass war Befund M210-1 (der Worker hielt 46 min
fuer 180 min).

## 2. War sie an `hard_wall_s` gekoppelt? (CONFIRMED: ja, als Regel - nicht im Code)

* **Im Code: nein.** Kein Import, keine Ableitung - der Wert stand fest im Modul
  (`4 * 3600.0`, seit R13bj `5 * 3600.0`), nur der Kommentar nannte `hard_wall_s`.
  `hx/uhr.py` haelt absichtlich nur `json`/`datetime`/`pathlib`, weil es aus dem
  Claude-Hook `tools/batch_uhr.py` importiert wird und billig bleiben muss.
* **In der Sache: ja.** `git log -p -- harness/hx/uhr.py` zeigt Commit `c77348a`
  (R13bj, "Zeitgrenzen vorlaeufig erhoeht"):

      -# Ein Batch laeuft nie laenger als die harte Grenze (harness.toml: hard_wall_s = 10800 s
      -MAX_START_ALTER_S = 4 * 3600.0
      +# Ein Batch laeuft nie laenger als die harte Grenze (harness.toml: hard_wall_s = 14400 s
      +# = 4 h; R13bj vorlaeufig erhoeht, vorher 10800 s)
      +MAX_START_ALTER_S = 5 * 3600.0

  Die Commit-Nachricht sagt es ausdruecklich: "uhr.MAX_START_ALTER_S mitgezogen". Die
  Regel dahinter: **harte Grenze + 1 h Luft**. Nachgehalten wurde sie von
  `tests/test_r13bj_fixes.py:254` (`MAX_START_ALTER_S >= hard_wall_s`).
* **Die Luecke entstand in R13bl.** Dort wurde `hard_wall_s` 14400 -> 10800
  zurueckgebaut (Preflight von B236 brauchte 456 s), die Uhrgrenze blieb aber auf 5 h.
  Seitdem galt ein Startzeitstempel von 4 bis 5 Stunden als **plausibel**, obwohl ein
  Batch nach 3 h hart beendet wird - genau die Reste aus abgebrochenen Laeufen, gegen
  die die Zahl da ist.

## 3. Entscheidung: zurueck auf 4 h (Begruendung)

`MAX_START_ALTER_S = 4 * 3600.0` = harte Grenze (3 h, `harness.toml: hard_wall_s =
10800`) **+ 1 h Luft**, wie vor R13bj. Die 5 h waren nur mitgezogen worden, weil die
harte Grenze damals 4 h war; diese Begruendung ist mit R13bl entfallen.

Die Kopplung ist jetzt **als Test** festgehalten, damit sie nicht wieder still
auseinanderlaeuft (`tests/test_r13bm_fixes.py`, Klasse `TestUhrGrenze`):

* `MAX_START_ALTER_S == hard_wall_s + 3600` (genau, nicht nur `>=`),
* 4,5 h alter Start -> `unplausibel` und Hinweis im Uhrtext (mit 5 h waere das durchgegangen),
* 3,5 h (innerhalb der Luft) -> gilt, Uhrtext nennt "min von 90 min",
* 30 min in der Zukunft -> `unplausibel`.

## 4. Was sich NICHT aendert

* `hard_wall_s` bleibt 10800 s (3 h), `alarm_wall_s` 9000 s (150 min),
  `umschalt_vor_alarm_s` 900 s: R13bl-2 hat das am 02.10.2026 begruendet (Preflight
  B236 = 456 s), hier wurde nichts angefasst.
* `ZUKUNFT_TOLERANZ_S = 120 s` bleibt: eine kleine Uhrendrift zwischen Prozessen darf
  die Anzeige nicht auf "unplausibel" stellen.
