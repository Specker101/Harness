# R13s - Belege (2026-09-28)

Auftrag: Plan R13s freigegeben, mit Ergaenzungen 1-7. Belege zu Punkt **3** und **4a/4b**,
dazu die Antwort auf die Vorbedingungen aus Punkt **6**. Messungen sind mit Werkzeug und
Datum benannt; alles ist **rein lesend** erhoben (kein Ghidra, kein Netz, kein MAME-Lauf).

---

## Punkt 3 - Enthaelt der Review-Prompt die /ds-Queue-Nachrichten des bewerteten Batches?

**Antwort: NEIN.** Der Reviewer sieht die `/ds`-Nachrichten nicht.

Belege (Datei:Zeile, Stand 2026-09-28):

| Was | Stelle | Aussage |
|---|---|---|
| Der Review-Kontext hat genau diese Schluessel | `harness/hx/orchestrator.py:1789-1807` (`review_context`) | `batch, next_batch, anchor_batch, anchor_hint, facts, worker_report, diff, historie, markers, queue_block, anchor, snapshot, handover, retry_hint, previous_raw, extra` |
| `queue_block` IST die **/claude**-Queue | `harness/hx/orchestrator.py:1799` (`"queue_block": reviewer_note`) + Aufrufer `orchestrator.py:2014` (`read_queue_block("claude", mark=False)`) | die Nachrichten an den **Reviewer**, nicht die des Workers |
| Der Worker-Bericht ist die **letzte Nachricht** | `harness/hx/orchestrator.py:1780` (`report = read_text(edir / "antwort.md")`) | nur der Abschlussbericht, nicht der Prompt |
| Die **/ds**-Queue geht ausschliesslich an den Worker | `harness/hx/orchestrator.py:2127` (`read_queue_block("ds")`) -> `2134` (`run_worker(..., note_block)`) -> `harness/hx/worker.py:686-703` (`build_prompt(..., queue_block, ...)`) | der Queue-Block haengt am Worker-Prompt |
| Der volle Worker-Prompt liegt als Datei daneben | `harness/hx/worker.py:252` (`write_text_atomic(rd / "auftrag.md", prompt)`) | `runs/b<N>/auftrag.md` - im Review-Prompt **nicht** enthalten |

**Vorschlag R13t (NICHT gebaut, wie beauftragt):** einen Block
`=== NUTZER-NACHRICHTEN DIESES BATCHES (/ds) ===` in `review_context` aufnehmen, Quelle
`runs/b<state.batch>/auftrag.md` (Abschnitt zwischen `=== AUFTRAG (vom Reviewer) ===` und
dem Ende) oder die Queue-Dateien selbst. Nutzen: der Reviewer kann beurteilen, ob eine
Nutzer-Nachricht die Batch-Aufgabe veraendert hat. Aufwand: ~10 Zeilen + 3 Tests.

---

## Punkt 6 - Zwei Vorbedingungen

### 6a) Sieht der Reviewer die Denkbloecke / das Worker-Protokoll?

**Antwort: NEIN - nur den Abschlussbericht und Summen.**

* Denkbloecke werden als eigene Datei geschrieben (`harness/hx/worker.py:727-734` ->
  `snapshots/b<N>/reasoning.jsonl`), aber **kein** Pfad dorthin geht in den Review-Prompt
  (`orchestrator.review_context`, Schluessel s. o.). Der Reviewer bekommt
  `heartbeat`-freie Kennzahlen (`facts` = `runs/b<N>/harness-facts.md`), den
  `snapshot` (`snapshots/b<N>/snapshot.md`: Kennzahlen, Ankerkopf, **Werkzeugnutzung als
  Summe**, Abschlussbericht) und den Bericht selbst.
* Das **Werkzeug-Protokoll** (welcher Aufruf wann, mit welchem Argument) sieht er nicht;
  er sieht nur die Zaehlung (`snapshots/b<N>/tools.tsv`, im Snapshot als Tabelle).
  Fuer die neue Denkblock-Anzeige gibt es `watch` (volle Bloecke) und `/thinking` (R13r).

### 6b) Hat der Reviewer Lesezugriff auf `g:\Harness` (alte DS_INSTRUCTIONs)?

**Antwort: teilweise - ja auf `g:\Harness\harness\**`, nein auf `g:\Harness` selbst.**

* `harness/hx/reviewer.py:77`: `--allowedTools *pfad_regeln((cfg.root, cfg.decomp))`;
  `harness/hx/reviewer.py:94-95`: `--add-dir str(cfg.root)` und `--add-dir str(cfg.decomp)`.
* `harness/hx/profiles.py:98-105` (`pfad_regeln`) erzeugt daraus `Read(//<pfad>/**)`.
* `cfg.root` ist **`g:/Harness/harness`** (so steht es in `harness/harness.toml`).
  Damit sind **alte Instruktionen lesbar**: sie liegen als `runs/b<N>/auftrag.md`
  unterhalb von `cfg.root`.
* **Nicht** freigegeben (und damit verweigert): `g:\Harness\docs\*` (die Belege), der
  ganze `g:\Harness`-Wurzelordner und `g:\Harness\secrets` (zusaetzlich verboten,
  `reviewer.py:92`). Wer will, dass der Reviewer Belege aus `docs\` liest, muss
  `cfg.harness_home` in `pfad_regeln`/`--add-dir` aufnehmen - das ist eine eigene
  Entscheidung (R13o hat das nur fuer `/ask` gemacht).

---

## Punkt 4a - CA-abhaengige Befehle in den gruenen Koepfen (gemessen)

Werkzeug: `tools/r13s_ca_zensus.py` (nur lesend, Quellen `scripts/c_kopf.py` `KOPF_DEF`
und `rom/build/830d01.27p.main.bin`). Beleg: `docs/_r13s_beleg_4a.txt`, Rohdaten
`docs/_r13s_ca_zensus.json`.

**Ergebnis: 34 von 78 registrierten Koepfen enthalten einen CA-abhaengigen Befehl.**
Gefunden wurden ausschliesslich **`addc`** und **`subfc`** (kein `adde`/`addme`/`addze`/
`subfe`/`subfme`/`subfze`). Die schwersten Faelle: `80010A20` (addc x20),
`80065898` (addc x19 + subfc x3), `8000CE14` (addc x6), `8005873C` (addc x4 + subfc x2),
`80010E9C` (addc x3 in nur 8 Befehlen).

Die vollstaendige Liste (Kopf, Rumpf-Insn, erzeugender Befehl) steht in
`docs/_r13s_beleg_4a.txt`. **Fuenf der 34 sind genau die in B206 gebauten Blaetter**
(`8005BF74`, `80055DA8`, `80017A8C`, `8005873C`, `80065898`) - sie sind also frisch
verifiziert, aber unter dem CA-Verdacht.

Damit ist die Neupruefung nach dem R535-Fix **keine Kleinigkeit**: nicht 12 Koepfe (das
war die B206-Probe mit `+ self.ca`), sondern **34 Koepfe** muessen danach neu verglichen
werden - und die 44 uebrigen bleiben als Regressionsschranke.

## Punkt 4b - Port-Relevanz aus der vorhandenen Aufnahme (gemessen)

Werkzeug: `tools/r13s_cov_probe.py` (nur lesend). Quellen: `analysis/_m60_funcs.json`
(2072 Funktionen), `capture/ppc_coverage.bin` + `capture/ppc_cov_boot.bin` (`SSCOV1`-Byte-Maps des
**vorhandenen** Gameplay-/Boot-Laufs, gelesen wie in `scripts/m43b_phasecov.py`),
`scripts/c_kopf.py` (`KOPF_DEF` = 78 verifizierte Koepfe). Beleg: `docs/_r13s_beleg_4b.txt`.

| Zahl | Wert |
|---|---|
| Coverage-Bytes gesetzt | 52 015 von 4 194 304 (1,24 % des Abbilds) |
| Funktionen im Inventar | 2072 |
| davon in der Aufnahme **ausgefuehrt** (Fenster 256 B) | 1299 |
| davon ausgefuehrt (nur Eintrittsbyte, streng) | 1066 |
| verifizierte C-Koepfe | 78 |
| davon ausgefuehrt | 64 |
| **Anteil der ausgefuehrten Funktionen, die verifiziert sind** | **4,9 %** (64/1299) |

**Ohne neuen MAME-Lauf machbar** - die Aufnahme liegt vor. Offener Aufwand fuer die
volle Zahl („portiert UND verifiziert" statt „verifiziert"): die Bau-Liste
(`m104_built.built_map()`, 686 Koepfe) statt `KOPF_DEF` einsetzen und das Fenster
sauber ueber den Funktionsrumpf legen (erste `blr`): **~30 Minuten**, ein weiterer
kleiner Werkzeuglauf. Sinnvoll als **eigene Messzeile** in der Bilanz („Anteil der
ausgefuehrten Funktionen, die der Port schon faehrt"), damit die Reihenfolge der Arbeit
an der Wirkung haengt und nicht an der Reihenfolge im Inventar.

## Punkt 4c - Paket-E-Zahlen als feste Zeile

Vorschlag unveraendert: eine maschinengeschriebene Zeile
`PAKET-E: offen <k> Koepfe / <i> Insn (Blaetter <a> / <b>)` je Batch-Dokument **und**
ein Feld in `analysis/_bilanz_snapshot.json`. Heute liest der Harness sie aus der
Soll/Ist-Tafel des Batch-Dokuments (`| Paket E offen | … | **…** |`), was funktioniert,
solange die Tafel da ist - sie fehlt aber in aelteren Dokumenten (gemessen: nur B205 und
B206 tragen sie). Nicht im Harness gebaut (das waere eine Aenderung im Decomp-Repo).
