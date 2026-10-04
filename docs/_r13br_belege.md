# R13br — Belege: Ablage der Aussensicht im Batch-Ordner (2026-10-04)

**Auftrag (Nutzer, Harness-Wartung; das Decomp-Repo wird nicht angefasst).** Die Dateien der
Außensicht lagen lose in `runs/` (`meta-<N>.md`, `.json`, `.jsonl`, `.err.txt`,
`-hooks.json`). Sie sollen im Ordner des jeweiligen Batches liegen:
`runs/b<N>/meta.md|meta.json|meta.jsonl|meta.err.txt|meta-hooks.json`.

1. Zuerst **nur lesen** und berichten (Fundstellen, Namensableitung, Fensterlogik,
   betroffene Batch-Ordner).
2. Umsetzung: neuer Ort, Leser akzeptieren beide Orte, Originale bleiben liegen, Wandler
   mit Trockenlauf, kein Überschreiben im Batch-Ordner.
3. Tests: neuer Ort geschrieben, alter gelesen, neuer gewinnt, Fensterlogik gleich,
   Trockenlauf ändert nichts.
4. Doku, Commits, am Gate die volle Reihe, push.

---

## 1) Befund (nur gelesen)

### Erzeuger (vor dem Umbau)
`harness/hx/aussensicht.py:217-226` (`bericht_pfad`/`json_pfad`/`stream_pfad`),
`:1705` (Mitschnitt), `:1721`/`:1731-1732` (stderr), `:1333` (Hook-Einstellungen),
`:1923-1924`/`:1930` (Bericht + Maschinenfassung). Die Nummer kommt aus `state.batch`
(`:1703`), nicht aus einem Dateinamen.

### Leser (vor dem Umbau)
`aussensicht.py:467` Glob `runs.glob("meta-*.json")` + `:472` Regex `meta-(\d+)\.json`
(`letzte_bericht_batches`), `:513` derselbe Glob nach `mtime` (`bericht_zustand`, Nummer
aus dem JSON-Inhalt). Aufrufer: `faellig` (`:1813-1820`, Wiederholungs-Auslöser),
`zeile` (`:552-573` → `/bilanz`, `/status`), `fragen.py:260` (`/fragen`).
Anzeigetexte mit Pfad: `fragen.py:231`/`:273`. Register (nicht betroffen):
`ledger_pfad` = `state/meta_befunde.json`. Marker/Quote/Tiefenprobe laufen über den
Zustand bzw. das Register, **nicht** über die `meta-<N>`-Dateien.
Nachlass-Werkzeuge, die die alten Pfade lesen: `docs/_r13bn_verbrauch.py:33`,
`docs/_r13bf_probe.py`.

### Betroffene Batch-Ordner (gemessen)
| Was | Ergebnis |
|---|---|
| Meta-Batches | **28** (208…256) |
| Lose Dateien | **131**: 112 × `.md/.json/.jsonl/.err.txt` (28 × 4) + **19** × `-hooks.json` (ab 219) |
| Größe zusammen | **12,64 MB**; größter Mitschnitt 0,6 MB |
| Batch-Ordner fehlt | **keiner** — für alle 28 existiert `runs/b<N>` |
| Kollision im Zielordner | **keine** — in `b208..b256` liegt keine `meta*`-Datei |
| Fortsetzung | `runs/b235/lauf1/` (derselbe Zahlenraum zweimal) |

Angelegt wird `runs/b<N>/` vom Worker (`worker.run_dir`, `worker.py:155-157`; Aufrufe
`:731`, `:1411`, `:1595`) — im Normalfall vorhanden, **nicht** garantiert (z. B. `/meta`
im Gate/Pause oder eine Nummer ohne Worker). `worker.sichere_vorgaenger` verschiebt
`LAUF_BELEGE` (`worker.py:161-168`) nach `lauf<k>/` — `meta.*` steht dort **nicht** drin.
`retention.kandidaten` (`retention.py:177-192`) packt nur `stream*.jsonl`/`reviewer.jsonl`.

**Entscheidung des Nutzers zu dieser Lücke:** nur der Wächter, **keine** Änderung an
`worker.sichere_vorgaenger`/`LAUF_BELEGE`.

## 2) Umsetzung

`harness/hx/aussensicht.py`: Tabelle `ABLAGE` (art → neuer Name im Batchordner, alter
Name in `runs/`), `batch_ordner` (legt an), `pfad_neu`/`pfad_alt`/`pfad` (neuer Ort
zuerst, alter als Rückfall), `anzeige_pfad` (für `/fragen`), `bericht_dateien` (beide
Orte, je Batch einmal — neuer Ort gewinnt), `ablage_konflikt`/`ablage_pruefen`
(Wächter), `ablage_wandeln`/`ablage_tafel` (Wandler). `run()` prüft **vor** dem Lauf,
`bericht_schreiben()` prüft als zweites Netz. `bericht_zustand`/`letzte_bericht_batches`
sind auf `bericht_dateien` umgestellt. Neu in `hx/cli.py`: `meta-ablage`.

Wächter-Regel: `md` muss mit `# Aussensicht Batch <N>` beginnen, `json` muss `batch == N`
und `rc` tragen, `jsonl` in der ersten nicht-leeren Zeile ein JSON-Objekt mit `type` sein.
Alles andere = fremd → `AblageKonflikt` (Lauf **nicht** gestartet, nichts geschrieben).
`meta.err.txt`/`meta-hooks.json` sind Hilfsdateien und werden je Lauf neu geschrieben.

**Wandler, gemessen am echten Bestand (Trockenlauf):**

    Aussensicht-Belege: Trockenlauf (nichts geaendert) - --ausfuehren kopiert
    Quellen: 131 - kopiert: 0, schon da: 0, Ziel belegt: 0
    (runs/b208/meta.md … runs/b256/meta-hooks.json alle "vorhanden: nein" → "kopieren")
    danach geprueft: runs/b208/meta.md und runs/b256/meta.json existieren NICHT

## 3) Tests

Neu: `harness/tests/test_r13br_fixes.py` — **29 Tests, OK, 1,19 s**, ohne API-Kosten
(Wegwerf-Wurzeln `tests/_tmp_r13br_*`). Abgedeckt: neuer Ort geschrieben (Mock-Lauf,
Ordneranlage, Hook-Datei, Meldung mit neuem Pfad), alter Ort lesbar (alle fünf Arten,
Rangfolge, keine Doppelzählung), Fensterlogik (dieselbe Lage alt vs. gemischt liefert
gleiches `bericht_zustand`/`zeile`/`letzte_bericht_batches`), Wächter (fremd bricht ab,
eigene Dateien erlauben den Wiederholungslauf, Hilfsdateien blockieren nicht), Wandler
(Trockenlauf unverändert, `--ausfuehren` kopiert + Originale bleiben, „schon da",
„Ziel belegt", `--batches`, Namenserkennung), CLI-Verdrahtung.

Nachgezogen (Verhalten hat sich geändert): `tests/test_r13ar_fixes.py` (Name und Ordner
der Hook-Datei, JSON über `json_pfad`), `tests/test_r13aq_fixes.py` (Bericht über
`json_pfad`). Vorrichtungen, die **alte** Pfade schreiben, bleiben absichtlich stehen —
sie sind der Rückfall-Test.

Betroffene Bestandsdateien einzeln gefahren (alle grün): `test_r13w_fixes` (45),
`test_r13x_fixes` (33), `test_r13z_fixes` (24), `test_r13aa_fixes` (33),
`test_r13ac_fixes` (46), `test_r13ac3_fixes` (16), `test_r13aq_fixes` (30),
`test_r13ar_fixes` (30), `test_r13bm_fixes` (37), `test_r13bn_fixes` (18),
`test_r13bo5_fixes` (9), `test_r13bq_fixes` (14).

## 4) Volle Reihe am Gate (R13au)

    HEAD: 6e0bc14 R13br-2b: drei Beschreibungen des Ablageorts nachgezogen
    Harness-Zustand: state=GATE_APPROVAL batch=259 worker=False
    Dauer: 615.6 s
    Tests: 1522 | Fehler: 0 | Fehlschläge: 0 | übersprungen: 0
    ERGEBNIS: OK

Vergleich zum vorigen Batch: R13bq hatte 1493 Tests → +29 = genau die neue Testdatei.

## Commits

| Commit | Inhalt |
|---|---|
| `c6983cb` | R13br-2: Ablage im Batch-Ordner, Rückfall, Wächter, Wandler (`hx/aussensicht.py`, `hx/cli.py`, `hx/fragen.py`, zwei nachgezogene Tests) |
| `db439ba` | R13br-3: `tests/test_r13br_fixes.py` (29 Tests) |
| `bdf87a0` | R13br-4: `docs/bedienung.md` |
| `6e0bc14` | R13br-2b: drei Doku-Strings auf den neuen Ort |

## Offene Entscheidung für den Nutzer

**Sollen die 131 losen Dateien nach dem Wandeln gelöscht werden?** Empfehlung: **ja, aber
erst nach einem erfolgreichen `--ausfuehren` und einer Sichtprüfung** — dann sind sie
Kopien ohne Zusatzwert, und `runs/` wird wieder übersichtlich. Bis dahin bleiben sie
Beleg. **Nicht** gemacht und nicht empfohlen: die Dateien verschieben (der Wandler kopiert
nur, damit jederzeit ein Rückweg existiert).

Zwei Tests lesen die alten losen Dateien namentlich und überspringen sich, wenn sie
fehlen (`test_r13aq_fixes.py:116`, `test_r13ar_fixes.py:80-99` — Vorrichtungen zu
meta-214/217); ein Löschen nimmt diesen Vergleich, kostet aber keinen Ausfall.

---

# Nachtrag R13bs (2026-10-04) — `meta-ablage --verschieben`

**Auftrag (Nutzer).** Das Werkzeug `meta-ablage` um `--verschieben` erweitern; Trockenlauf
bleibt Standard, `--ausfuehren` weiterhin nötig. Es kopiert wie bisher und löscht danach das
lose Original in `runs/` **nur**, wenn die Kopie am Ziel existiert und **Größe und SHA-256**
gleich sind. Bei Abweichung oder Kollision bleibt das Original liegen, mit Grund in der Tafel
(`Datei | Ziel | Hash gleich | Aktion`). Schlusszeile `kopiert, geloescht, behalten`.

**Umsetzung.** `ablage_wandeln(..., verschieben=False)`; neuer Helfer `_gleich(quelle, ziel)`
(Größe **und** SHA-256, `OSError` = nicht gleich). Reihenfolge je Datei: Lage am Ziel
feststellen (`fehlt`/`gleich`/`verschieden`) → Plan → kopieren → **Kopie nachlesen** →
erst dann löschen. `verschieden` wird nie überschrieben und nie gelöscht. `--verschieben`
ohne `--ausfuehren` ist ein reiner Trockenlauf (`geplant kopieren: n, geplant loeschen: n`).
Tafel jetzt `Datei | Ziel | Hash gleich | Aktion` mit `-` für „am Ziel liegt noch nichts".

**Gemessen (Trockenlauf gegen den echten Bestand, HEAD `a5a8cf1`):**

    Quellen: 131 - kopiert: 0, geloescht: 0, behalten: 0
    Trockenlauf: geplant kopieren: 131, geplant loeschen: 131 - nichts geaendert.
    lose meta-Dateien vorher=131 nachher=131, Kopien im Zielordner: 0

**Tests.** `test_r13br_fixes.py` 33 Tests (neu: `test_verschieben_loescht_das_original`,
`test_verschieben_loescht_auch_ohne_neue_kopie`, `test_verschieben_laesst_abweichendes_
original_liegen`, `test_verschieben_trockenlauf_aendert_nichts`, Hash-Spalte/Bilanz;
`test_ausfuehren_kopiert_und_laesst_die_originale` belegt, dass **ohne** `--verschieben`
nichts verschwindet). Weiter: `test_r13aq_fixes` 30, `test_r13ar_fixes` 30,
`test_r13w_fixes` 45 — grün.

**Zwei Lose-Leser auf beide Orte (R13bs).** `test_r13aq_fixes.py` und
`test_r13ar_fixes.py` suchen die Belege meta-214/217 über den neuen Helfer `_meta_beleg()`
zuerst in `runs/b<N>/meta.*`, dann in `runs/meta-<N>.*`; die Skip-Meldung nennt beide Orte.
Damit bleiben die Vergleiche gültig, wenn die losen Dateien einmal weggeräumt werden.

**Volle Reihe am Gate** (Arbeitsbaum = `a5a8cf1` + dieser Diff; das Belegwerkzeug schreibt
den HEAD beim Start, also den Commit davor):

    HEAD: a5a8cf1   Zustand: state=GATE_APPROVAL batch=259 worker=False
    Dauer: 638.1 s
    Tests: 1526 | Fehler: 0 | Fehlschläge: 0 | übersprungen: 0
    ERGEBNIS: OK
    (R13br: 1522 → +4 = die vier neuen Verschieben-Tests)
