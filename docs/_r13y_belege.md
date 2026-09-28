# R13y — Kennungen für Fragen, Antworten mit Kennung, Empfänger nach Entscheidungsträger

**Auftrag (Nutzer, 2026-09-28, vier Punkte, kein neuer Befehl):**

1. `/fragen`: jede offene Frage an den Nutzer bekommt eine eindeutige Kennung.
2. Eine `/claude`-Nachricht, die mit einer Kennung beginnt, gilt als Antwort: Wortlaut der
   Frage + Empfehlung werden angehängt, die Frage wird „beantwortet, wartet auf Review" und
   verschwindet nach dem Review, das sie aufnimmt. Mehrere Kennungen erlaubt, unbekannte
   Kennung → Rückmeldung mit den gültigen.
3. Aussensicht: Befunde nach Entscheidungsträger aufteilen.
4. `bedienung.md`: „Was nehme ich wann".

## 1. Kennungen (Punkt 1)

An einem echten Lauf (`python -m hx.cli fragen`, Beleg `docs/_r13y_fragen_echt.txt`):

```
FRAGEN AN DICH (Anker: BATCH 209)
OFFENE FRAGEN AN DICH
  A1        ANKERPOSTEN (1): …                     <- Ankerposten "(1)"
  R209-1    ENTSCHIEDEN (Veto per /claude moeglich): …   <- Review, das B209 bewertet hat
  M208-3    AUSSENSICHT (Gewicht mittel): …        <- Aussensicht-Befund (M-ID von ihr)
ANTWORTEN: /claude <Kennung> <Text>   (z. B. "/claude A1 ja" - Kennung am Anfang, dann der Text)
```

| Kennung | Quelle | Beleg im Lauf |
|---|---|---|
| `A1`, `A2`, `A3` | `**Offene Entscheidung:**` des Ankerkopfs, Postennummer | `analysis/r1b-workstream.md` |
| `R209-1..3` | die Marker-Zeilen des Reviews im Ordner `runs/b210` — dessen Fakten-Datei nennt „bewertet wird Batch 209" | `runs/b210/review.md` + `harness-facts.md` |
| `M208-1`, `M208-3`, `M208-5` | offene Aussensicht-Befunde mit Empfänger „Nutzer" (IDs vergibt die Aussensicht selbst) | `state/meta_befunde.json`, `runs/meta-208.md` |

**Kein neuer Zustandsspeicher:** alles wird abgeleitet (Ankerkopf, letztes Review,
Aussensicht-Register, Queue-Dateien). Ein Harness-Neustart oder ein abgebrochener Batch
kann die Kennungen deshalb nicht verlieren. Die Reihenfolge der `R`-Nummern ist
`ENTSCHEIDUNG NOETIG` → `OFFENE FRAGE` → `WARTET AUF LIVE-AUFNAHME` → `ENTSCHIEDEN`.

## 2. Antworten (Punkt 2)

Beleg: `docs/_r13y_belege.txt` (Wegwerf-Baum mit den **echten** Texten; die echten
Queue-Ordner wurden nicht angefasst).

```
### 1) /claude A1 ja, aber erst nach B211
   ok: True | bekannt: ['A1']
   Meldung: In die Queue gelegt. Beantwortet: A1 - die Frage(n) stehen jetzt als
            "beantwortet, wartet auf Review".
   Anhang, der an die Nachricht geht:
     A1 ja, aber erst nach B211

     [Antwort auf Frage(n) - Wortlaut zum Zeitpunkt der Antwort]
     --- A1 (Ankerposten) ---
     Frage: ENTSCHIEDEN (Nutzer, 2026-09-28):** In den B-Plan kommt ein eigener Schritt …
     Empfehlung: …
     Quelle: Ankerkopf r1b-workstream.md

### 2) /fragen danach (Auszug)
   BEANTWORTET, WARTET AUF REVIEW
     A1        …

### 3) Unbekannte Kennung
   ok: False | unbekannt: ['A9']
   Meldung: Unbekannte Kennung: A9. Die Nachricht wurde NICHT in die Queue gelegt.
            Gueltige Kennungen: A1, A2, A3, R209-1, R209-2, R209-3, M208-1, M208-3, M208-5

### 4) Nach dem Review (das Gate hat die Nachricht gelesen)
   Status A1 = aufgenommen
   Zeile in /fragen: ['aufgenommen (nicht mehr offen): A1']
```

Der **Wortlaut im Anhang** ist kein Schmuck: der Ankerposten `(5)` kann in einem späteren
Batch eine andere Frage tragen — die Antwort wird deshalb mit dem Text **von jetzt**
zugestellt. „Aufgenommen" heißt: das Review hat die Nachricht gelesen
(`claude_queue_ids` des Gates) oder sie liegt in `inbox/done/`.

## 3. Empfänger nach Entscheidungsträger (Punkt 3)

Regel in `hx/aussensicht.py` (`NUTZER_THEMEN`, `entscheidungstraeger`), mechanisch und
nachprüfbar:

* Sätze der Aussage mit **Ziel/Scope/Budget/früherer Nutzerentscheidung** → **Nutzer**;
* alle anderen → **Reviewer** (der Orchestrator entscheidet den Regelfall selbst);
* beide Anteile → **zwei** Befunde, gleicher Beleg, gleiches Gewicht:
  `M208-5a` (Nutzer) und `M208-5b` (Reviewer); die Empfehlung geht an ihren Teil;
* die Empfängerangabe des Modells wird überschrieben, wenn sie widerspricht, und die
  Umleitung im Log vermerkt (`umgeleitet`).

Bewusst **kein** bloßes Wort `ziel`: „Ziel des nächsten Batches" ist Zuschnitt-Sache des
Reviewers und darf nicht durchschlagen (Test `test_zuschnitt_des_batches_ist_kein_nutzerthema`).
Ein Befund, der beim Reviewer landet und den Menschen braucht, geht nicht verloren — der
Reviewer eskaliert über `ENTSCHEIDUNG NOETIG:` / `WARTET AUF LIVE-AUFNAHME:`, die ebenfalls
Kennungen tragen.

An echten Befunden: `M208-5` (readme-Ziel + Mischverhältnis) ist ein **reiner**
Nutzer-Befund — die Aussage ist ein Satz und trifft nur das Ziel (kein Teil). Geteilte
Befunde sind in `tests/test_r13y_fixes.py::TestEntscheidungstraeger` und
`::TestVerteilung` belegt.

## 4. Bedienung (Punkt 4)

`docs/bedienung.md`: §16 neu gefasst (Kennungen, Antwortweg), §16a (Tabelle der
Kennungen), §16b (`/claude` mit Kennung), **§17 „Was nehme ich wann"** mit Tabelle und drei
Faustregeln: `/fragen` zum Lesen, `/claude` zum Antworten und für Hinweise, `/ds` nur, wenn
der kommende Batch wirklich anders laufen soll.

## 5. Tests

`harness/tests/test_r13y_fixes.py` (neu, 27 Tests): Kennungen lesen (führend, mehrere,
tolerant gegen Kleinschreibung, nicht mitten im Text), Register aus Anker/Review/Aussensicht,
Statusfolge offen → beantwortet → aufgenommen (Queue, Gate-Kennungen, Archiv),
`nachricht_vorbereiten` (Anhang, Mehrfachkennung, unbekannt, unverändert ohne Kennung),
Orchestrator `/claude` und `/fragen`, `cli send claude` und `cli fragen`,
Entscheidungsträger (drei Fälle + Zuschnitt-Falle), geteilte Befunde im Ledger und die
Kurzform-Antwort `M208-1: …` für beide Teile.

Mitgezogen: `test_r13s_fixes.py` (Kennungen in der `/fragen`-Ausgabe),
`test_r13w_fixes.py` (Aufteilung/Umleitung statt Modellangabe, `/fragen` statt
`fragen_zeilen`, ein Nutzer-Befund in der Attrappe).

Volle Reihe: **588 Tests OK**.

## 6. Grenzen

* Die Empfängerregel ist eine **Wortliste**, kein Verständnis: ein ziel-relevanter Befund
  ohne die Wendungen (`readme`, `Projektziel`, `Budget`, `priorisier…`, `Scope`,
  `Abbruchkriterium`, …) geht an den Reviewer. Dort ist er nicht verloren — der Reviewer
  kann ihn per `ENTSCHEIDUNG NOETIG:` hochziehen.
* Kennungen sind **Zeiger auf die Quelle**, keine Historie: verschwindet ein Posten aus
  dem Anker, verschwindet seine Kennung (sie erscheint dann nicht mehr in `/fragen`).
  Nach einem Wechsel sind alte Kennungen unbekannt — das wird gemeldet, nicht geraten.
* Ältere Aussensicht-Befunde behalten ihre gespeicherte Empfängerangabe (die Aufteilung
  greift beim **Verteilen**, nicht rückwirkend im Register).
