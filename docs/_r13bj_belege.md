# R13bj — B235-Sicherung, eigene Batchnummer, vorlaeufige Zeitgrenzen (01.10.2026)

Auftrag des Nutzers in drei Teilen (A: Belegsicherung/Batchnummer, B: Zeitgrenzen,
C: Tests+Commit). Der Harness ist pausiert (Gate „B235 Fortsetzung"), es wurde nichts an
ihm gestartet. Belege: dieses Dokument, `docs/_r13bj_sichtung.txt`,
`docs/_r13bj_b234sichtung.txt`, `docs/_r13bj_reviewsichtung.txt`, `docs/_r13bj_handover.txt`,
`docs/_r13bj_volle_reihe.txt`.

## A1. `runs/b235/` gesichert (Kopie, nicht verschoben)

Ziel: `runs/b235_lauf1_sicherung/` (15 Dateien). Original und Kopie sind in **Groesse und
Zeitstempel** gleich (Vergleich mit `Get-ChildItem … Length/LastWriteTime`):

| Datei | Bytes | Zeit |
|---|---|---|
| `auftrag.md` | 16 925 | 01.10. 15:46:07 |
| `mcp.json` | 242 | 15:46:07 |
| `worker-hooks.json` | 1 299 | 15:46:07 |
| `stream.err.txt` | 85 | 15:46:19 |
| `preflight-blockiert.jsonl` | 94 | 17:21:12 |
| `preflight-aufrufe.jsonl` | 182 | 18:08:03 |
| `stream.jsonl` | 22 217 541 | 18:40:11 |
| `result.json` | 9 877 | 18:40:12 |
| `antwort.md` | 4 259 | 18:40:12 |
| `handover.jsonl` | 10 495 | 18:41:20 |
| `handover.jsonl.err` | 0 | 18:41:04 |
| `harness-facts.md` | 8 161 | 18:41:20 |
| `reviewer.jsonl.err` | 0 | 18:41:22 |
| `review.md` | 13 863 | 18:45:13 |
| `reviewer.jsonl` | 249 667 | 18:45:13 |

Zusaetzlich in der Sicherung: `review_zu_b234.md` (wiederhergestellt, A2) und `HERKUNFT.md`
(Herkunft, Zeitlinie, Inhalt).

## A2. Das Review zu B234 war ueberschrieben — es ist wiederhergestellt

**Ja, die Vermutung stimmt.** `runs/b235/review.md` (18:45:13) ist das Review **ZU B235**:

* `runs/b235/harness-facts.md:1` = `- Review: bewertet wird Batch 235; die Instruktion gilt
  fuer Batch 235`, `:2` = `- Naechster Batch laut Anker: 235 (Anker-Kopf: BATCH 234)`.
* Der Reviewer-Mitschnitt `runs/b235/reviewer.jsonl` traegt **genau ein** `result`-Ereignis
  (Session `c7230a1e`), geschrieben 18:45:13 - das Review zu B234 ist dort **nicht** mehr
  enthalten (die Datei wurde mit dem neuen Review neu geschrieben).

**Wiederherstellungsquelle (gefunden):** der Harness legt von JEDEM Review eine
Volltextkopie unter `logs/review-<JJJJ-MM-TTTHHMMSS+0000>.md` ab.

| Datei | Bytes | Was |
|---|---|---|
| `logs/review-2026-10-01T112543+0000.md` | 10 673 | **Review zu B234** (Kennphrase `2450 von 2582`, `Front: 200M Schranke …`) |
| `logs/review-2026-10-01T164513+0000.md` | 13 862 | Review zu B235 (= `runs/b235/review.md`, 13 863 B) |

Die Wiederherstellung liegt als **byteweise Kopie** unter
`runs/b235_lauf1_sicherung/review_zu_b234.md` (SHA-256 der Quelle und der Kopie gleich:
`E3106B7F183900C2F6139C321CC52327A865E0B411B799EBC17D53115CD9162A`).

Zweite, unabhaengige Quelle fuer den Inhalt des B234-Reviews: `runs/b235/handover.jsonl`
(18:41:20) - der Handover-Text der **alten** Reviewer-Session `f94fdd42`, 1 811 Zeichen,
beginnt `**Stand:** B234 (C-Batch A, wiederholt nach einem Fehlalarm des
Prozess-Detektors) ist bewertet; FERTIG WENN nicht erreicht.` (Volltext:
`docs/_r13bj_handover.txt`).

**Was NICHT wiederherstellbar ist:** der Reviewer-**Mitschnitt** des B234-Reviews
(`reviewer.jsonl` wurde ueberschrieben, kein ZIP - die Aufbewahrung packt erst nach 14
Tagen). Der Review-**Volltext** und der daraus entstandene Auftrag (`auftrag.md`, 15:46)
sind vollstaendig erhalten.

## A3/A4. Die Ursache und was jetzt gilt

**Ursache (gemessen):** `orchestrator.expected_batch()` rechnete **ausschliesslich** als
Ankerkopf + 1. Der Ankerkopf stand auf `BATCH 234` (der Worker hat ihn nicht
fortgeschrieben) - also war „die naechste Nummer" **235**, sowohl fuer den Lauf B235 als
auch fuer die Ablage des Reviews, das B235 bewertet. Beide landeten in `runs/b235`. Das
Review zu B234 (15:46 in denselben Ordner geschrieben) wurde dabei ueberschrieben.
Das Review hat den Fehler selbst benannt (`runs/b235/review.md`, Abschnitt
`## VERALLGEMEINERUNG`, F1).

**Woher die Nummer kam (Datei:Zeile, Stand vor R13bj):**

| Stelle | Was |
|---|---|
| `hx/orchestrator.py:2030` `anchor_batch()` | liest `**Stand:** BATCH …` aus `cfg.anchor_file` (`protocol.parse_anchor_batch`) |
| `hx/orchestrator.py:2039` `expected_batch()` | **Anker + 1** - der einzige Zaehler; Kommentar: „Es gibt bewusst KEINEN zweiten Zaehler im Harness" |
| `hx/worker.py:155` `run_dir()` | Laufverzeichnis `runs/b<N>` (`ensure_dir`) |
| `hx/orchestrator.py:1815` (Review) | Review-Ablage = `runs/b<target>`, `target = expected_batch()` (bzw. die Nummer aus der Instruktion) |
| `hx/orchestrator.py:2887` (`_loop`) | `batch_no = tools["batch"] or expected_batch()`; dann `state.last_batch_number = batch` |


**Jetzt gilt (Code):**

| Regel | Stelle |
|---|---|
| Die Nummer zaehlt der **Harness** (`letzter Start + 1`); der Anker ist Gegenprobe | `hx/orchestrator.py::own_batch`/`expected_batch` |
| Abweichung steht in der Prompt-/Statuszeile UND als eigene Zeile in den Review-Fakten | `batch_number_line`, `batch_nummer_fakten_zeile` (Aufruf in `harness_facts`) |
| Die Nummernregel fuer den Reviewer kommt aus EINER Quelle (kein zweiter Wortlaut) | `batch_nummer_regel`, `review_context["batch_nummer_zeile"/"batch_nummer_regel"]`, `reviewer.build_prompt` |
| Dieselbe Nummer wie der bewertete Lauf = **Fortsetzung** (erlaubt, `tools["fortsetzung"]`) | `gate_from_review` |
| Ein fertiger Lauf (`result.json`) im Zielordner ⇒ **Pause mit Meldung**, der Auftrag bleibt stehen | `lauf_ordner_blockiert`, Aufruf in `_loop` vor dem Start |
| Belege des vorigen Laufs wandern nach `runs/b<N>/lauf<k>/` (Review bleibt oben) | `worker.sichere_vorgaenger` (`LAUF_BELEGE`/`LAUF_MUSTER`), `lauf_ordner_nummer` |
| Aufbewahrung packt auch `lauf<k>/`-Mitschnitte | `retention.kandidaten` |

Die Zuordnung je Lauf ist damit lesbar: `runs/b<N>/review.md` + `harness-facts.md` = Auftrag
und Messdaten fuer den laufenden Lauf, `runs/b<N>/lauf<k>/` = Auftrag/Mitschnitt/Ergebnis
des k-ten Laufs derselben Nummer. Fuer B235 Lauf 1 liegt der beauftragende Review
wiederhergestellt als `review_zu_b234.md` in `runs/b235_lauf1_sicherung/`; beim
Fortsetzungslauf wandern `auftrag.md`, `stream.jsonl`, `result.json`, `antwort.md` und
`mcp.json`/`worker-hooks.json` nach `runs/b235/lauf1/` - **die wiederhergestellte
Review-Datei muss dort noch hinein** (sie liegt bewusst nur in der Sicherung, damit der
Ordner `runs/b235/` bis zum Start unberuehrt bleibt):

    Copy-Item runs\b235_lauf1_sicherung\review_zu_b234.md runs\b235\review_zu_b234.md
    # ... dann verschiebt der Lauf sie beim Start selbst nach runs/b235/lauf1/

Handbuch: `docs/bedienung.md` §8 (neu geschrieben: „der Harness zaehlt, der Anker ist
Gegenprobe"), §12d (Lauf-Ordner statt `-v1`) und §13 (R13bj-Uebersicht mit Rueckbau-Vermerk).

## B. Zeitgrenzen vorlaeufig erhoeht

**Anlass (gemessen, `analysis/_m235/_preflight_zeiten.txt`):**

    Summe Teilschritte | 1799.187
    Gesamtwanduhr     | 1799.468
    Abweichung (Gesamt - Summe) | 0.281  (0.02 %)

Die Werkzeug-Obergrenze stand bei **1800 s** - der Lauf endete **0,5 s** davor. Groesster
Posten: `m212_zeilen / Hybrid-Lauf | 1392.031`, danach `c_kopf_check / C Koepfe | 330.672`.
B235 selbst lief 2h53m (Alarm 150 min, harte Grenze 180 min).

| Groesse | vorher | jetzt | Rueckbau |
|---|---|---|---|
| `[claude] bash_max_timeout_s` | 1800 s | **3600 s** | zurueck auf 1800 s, sobald der Preflight wieder **unter 900 s** liegt |
| `[limits] hard_wall_s` | 10800 s | **14400 s** | zurueck auf 10800 s, gleiche Bedingung |
| Worker-Vorspann + `prompts/reviewer.md` | `timeout=1800000` | **`timeout=3600000`** | zurueck auf 1800000 |

Unveraendert: `alarm_wall_s = 9000` (150 min), `umschalt_vor_alarm_s = 900` (Schwelle 135 min),
`BASH_DEFAULT_TIMEOUT_MS = 600000` (Vorgabe ohne eigenen Parameter - Schutz gegen haengende
Befehle). Mitgezogen: die Rueckfallwerte in `hx/worker.py` und `hx/watch.py` und die
Plausibilitaetsgrenze der Uhr (`hx/uhr.py::MAX_START_ALTER_S`, 4 h → 5 h).

Der Rueckbau-Vermerk steht in `docs/bedienung.md` §13 (Tafel) - dort stehen alle drei
Stellen, die zurueckzustellen sind.

## C. Tests

* Neu: `harness/tests/test_r13bj_fixes.py` (20 Tests) - Zaehler/Gegenprobe, Fortsetzung,
  Ordner-Sperre (auch fuer Altbestand-Gates ohne `tools["fortsetzung"]`), `lauf<k>/`,
  Aufbewahrung der `lauf<k>`-Mitschnitte, beide Zeitgrenzen, Vorspann/`reviewer.md`,
  Rueckbau-Vermerk im Handbuch.
* Angepasst (die Regel hat sich geaendert): `test_r10_fixes.py` (Prompt-Zeile, Review landet
  im Ordner des Zaehlers), `test_r13v3_fixes.py` (Zaehler statt Anker; `-v1` auf `lauf<k>/`),
  `test_r13ah_fixes.py` (3600 s), `test_r13aj_fixes.py` (`timeout=3600000`),
  `test_r13ad_fixes.py` (`hard_wall_s = 14400`), `test_r13v_fixes.py` (3600 s).
* **Erster voller Lauf (19:14:30) war rot** - Auszug in
  `docs/_r13bj_volle_reihe_rot.txt`: 1349 Tests, **1 Fehler, 1 Fehlschlag**, 524,8 s.
  Beide sind behoben:

  | Befund | Ursache | Fix |
  |---|---|---|
  | `test_r13af_fixes.py:295` `ValueError: int('235_lauf1_sicherung')` | Der Test las `runs/b*/auftrag.md` aus dem LEBENDEN Laufverzeichnis und nahm an, jeder Ordner heisse `b<Zahl>` - die neue Sicherung `runs/b235_lauf1_sicherung/` faellt darunter | Ziffernpruefung im Test; zusaetzlich **ein** Helfer `util.batch_ordner()` fuer alle Lesestellen (siehe unten) |
  | `test_r13v_fixes.py:162` `'3600000' != '1800000'` | uebersehene zweite Zusicherung auf die alte Werkzeug-Obergrenze | auf 3600 s umgestellt |

* **Sauberer Lauf danach: 1350 Tests, 0 Fehler, 0 Fehlschlaege, 0 uebersprungen, OK in
  584,7 s** (`docs/_r13bj_volle_reihe.txt`, HEAD `e4df496`, Zustand STOPPED/235 -
  der Harness wurde nicht gestartet).

* **Fallstrick (neu, deshalb der Helfer):** ein Ordner unter `runs/`, der mit `b` beginnt und
  nicht `b<Zahl>` heisst, bricht Leser, die `glob("b*")` ohne Ziffernpruefung verwenden. Im
  Bestand waren vier Stellen betroffen: `orchestrator._do_send` (nahm `dirs[-1]` = die
  Sicherung als „neuester Lauf"), `orchestrator.letzte_review_datei` und
  `bilanz.kosten_block` (zweimal - die Kopie haette die B235-Kosten **doppelt** gezaehlt).
  Alle vier laufen jetzt ueber `util.batch_ordner()` (`hx/util.py`), das nur `b<Zahl>` liefert.
  `aussensicht`, `denken`, `stand` und `fragen` hatten die Pruefung schon.
* **Erledigt:** der saubere volle Lauf und der Commit (R13bj, 01.10.2026). Zwischendurch war
  das Terminal-Werkzeug abgeschaltet - der rote Lauf oben stammt aus dieser Zeit.
