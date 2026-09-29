# R13al-Belege (2026-09-29): Peak-Sperre vervollständigen

Auftrag (5 Punkte): (1) zweite Prüfung **direkt vor dem Batch-Start** (vor
`git_preflight()`), wartend statt verwerfend, Telegram `PEAK: Auftrag B<N> wartet bis
<Uhrzeit Berlin>`, danach alle 20 s neu prüfen und automatisch starten; (2) **Vorlauf**
`peak_vorlauf_min` (Vorgabe 90) an beiden Prüfstellen; (3) **`/approve jetzt`** startet
trotz Peak, mit Vermerk „trotz Peak gestartet (Nutzer)" in Log und `result.json`;
(4) `extra_offpeak_dates` = 2026-10-01, -02, -05, -06, -07; (5) **nur berichten**: wie oft
startete ein Batch bisher im Peak?

---

## 0. Befund: die Sperre hatte drei Lücken (Anlass)

`peak_gate()` stand im ganzen Harness an **einer** Stelle — vor dem Review
(`hx/orchestrator.py:2539@480059d`). Damit konnte ein Batch trotzdem im Peak starten:

1. der Review läuft in den Peak hinein (Review-Dauer 2–5 min, Peak-Grenze stündlich),
2. beim Start ist das Gate da, aber **eine Entscheidung** fehlt („wartet auf deine
   Entscheidung") — `/approve` im Peak startet sofort,
3. „Git-Pause": `git_preflight()` bricht ab, der Auftrag bleibt stehen, `/resume` startet
   ihn später — auch mitten im Peak.

Dieselbe Beobachtung stand schon in `logs/ask/ask-20260929-203631+0000.md`
(„Eine zweite Peak-Prüfung gibt es auf diesem Weg nicht"). Ein **laufender** Batch wird
nach R5b nie unterbrochen — daran ändert R13al nichts.

## 1. Punkt 5 — Bericht: kein Batch bisher im Peak

Werkzeug `docs/_r13al_peakstart_probe.py` (nur lesend), Rohausgabe
`docs/_r13al_messung.txt`.

**Die im Auftrag genannte Quelle gibt es nicht.** „Starte Batch" steht **nicht** in
`logs/`: `Orchestrator.say()` schickt nur per Telegram, der Log-Satz entsteht nicht
(geprüft über alle `logs/harness-*.log`; Test `test_starte_batch_steht_nicht_im_log`).
Gerechnet wurde deshalb aus zwei belastbaren Spuren:

* `runs/b<N>/auftrag.md` → `Batch-Start (Harness-Zeitstempel): HH:MM:SS Ortszeit am …`
  (unmittelbar vor dem Prozessstart),
* `runs/b<N>/result.json` → `finished_at − duration_s` (Rückfall, wenn der Vorspann fehlt).

Ergebnis über **57 Batches** mit Ergebnisdatei (b001, b159–b215):

```
Im PEAK gestartet: 0
Off-peak, aber < 90 min vor einem Peak-Fenster: 0
```

Der Grund ist messbar: die Peak-Fenster liegen Mo–Fr 01–04 und 06–10 UTC, und alle
Nachtstarts (b161–b196) lagen auf **Sa 26.09. / So 27.09.** — Wochenenden sind immer
off-peak. Die Werktags-Starts (b207–b215) lagen bei 11:16, 13:18, 14:55, 17:02, 17:45,
17:53, 19:48, 21:06, 22:52 UTC — alle außerhalb. Auch der **Vorlauf** hätte keinen
bisherigen Start verhindert: der knappste Abstand zu einem Peak-Fenster beträgt
**122 min** (b212, 22:52 UTC → 01:00 UTC).

## 2. Punkt 1 und 2 — zweite Prüfung und Vorlauf

* `hx/pricing.py`: neu `next_peak_start()`, `im_vorlauf()`, `start_blockiert()`,
  `frei_ab()` (minutengenau, derselbe Vorlauf) und `ortszeit_text()` (Anzeige in
  Europe/Berlin mit der EU-Sommerzeitregel des Moduls).
* `hx/orchestrator.py::peak_gate(jetzt=None)` prüft jetzt Peak **oder** Vorlauf und nennt
  im Text beide Fälle getrennt (`Peak-Tarif aktiv (…)` / `Peak beginnt in N min
  (Vorlauf 90 min)`) plus `wieder frei ab <Ortszeit>`.
* Neu `warte_auf_offpeak(s, batch_no, trotz_peak=False)`: setzt den Zustand
  `GATE_APPROVAL` mit Grund `PEAK: wartet bis <Ortszeit Berlin>`, meldet **einmal**
  `PEAK: Auftrag B<N> wartet bis <Uhrzeit Berlin> (Ortszeit Berlin)`, prüft alle
  `PEAK_POLL_S = 20 s` neu und startet von selbst. Wird der Auftrag währenddessen
  verworfen (`/review`) oder freigegeben-der-Nutzer-stoppt, endet das Warten mit
  `PEAK-Warten beendet - Auftrag nicht mehr freigegeben`.
* Aufrufstelle: unmittelbar **vor** `ok, why = self.git_preflight()` im Startpfad; die
  erste Prüfung vor dem Review bleibt. Der laufende Batch wird nicht angefasst
  (Test `test_keine_peak_pruefung_im_laufenden_batch` prüft, dass nach
  `self.run_worker(` in `_loop` kein `peak_gate` mehr vorkommt).
* `/approve` bleibt unverbraucht: `approved_gate` wird beim Warten nicht gelöscht, das
  Gate wird erst nach Git-Vorprüfung und Checkpoint verbraucht (R13m).

## 3. Punkt 3 — `/approve jetzt`

* `_do_approve("jetzt")` setzt `self.approved_peak = <gate-id>`; `jetzt`, `sofort` und
  `trotz peak` werden als Ausweg erkannt, alles andere bleibt `/ds`-Nachricht.
* Beim Start: `warte_auf_offpeak(..., trotz_peak=True)` schreibt
  `state.data["peak_hinweis"] = "trotz Peak gestartet (Nutzer)"`, loggt
  `trotz Peak gestartet (Nutzer)` und sagt es per Telegram.
* `hx/worker.py::_finish_run` nimmt den Vermerk in `result.json` auf
  (`"peak_hinweis"`), der Orchestrator entfernt ihn nach dem Lauf wieder — er gilt nur für
  diesen einen Start.
* `discard_gate` und der Start löschen `approved_peak` ebenfalls (der Ausweg gilt nur für
  den offenen Auftrag).

## 4. Punkt 4 — Feiertage

`harness/harness.toml`:

```toml
peak_vorlauf_min    = 90
extra_offpeak_dates = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"]
```

Kommentar in der Datei: chinesischer Nationalfeiertag laut State Council; **ob DeepSeek
Feiertage ausnimmt, ist auf der Preisseite nicht eindeutig belegt** — die Liste ist die
billigere Annahme (off-peak). Nur Werktage eingetragen (Sa/So sind ohnehin off-peak).

### Nachtrag (Nutzerentscheid 2026-09-29): Vorlauf 90 → **10**

*Die Abschnitte oben bleiben stehen (sie beschreiben den Stand von R13al). Geändert wurde
nur die Zahl:*

* `harness.toml`: `peak_vorlauf_min = 10` — **Durchsatz vor den paar Cent
  Peak-Aufschlag**; ein Batch, der kurz vor dem Peak startet und hineinläuft, ist
  ausdrücklich akzeptiert.
* `peak_vorlauf_min()` hat denselben Rückfallwert 10 (sonst hätten Code und Datei zwei
  Meinungen, falls der Schlüssel einmal fehlt).
* Wirkung auf die Tests: `Basis.setUp` setzt den Vorlauf **ausdrücklich** (90) und ist
  damit unabhängig von `harness.toml`; neu dazu die beiden Fälle mit **10**
  (`test_5_min_vor_peak_wartet_bei_vorlauf_10`, `test_15_min_vor_peak_startet_bei_vorlauf_10`);
  `test_feiertage_stehen_in_der_konfiguration` prüft jetzt den Dateiwert **10**.
* Folgen für die Praxis: der knappste bisherige Abstand zu einem Peak war 122 min (b212) —
  bei 10 min hätte sich am Verhalten **keiner** der 57 bisherigen Batches etwas geändert;
  die zweite Prüfung vor dem Start und `/approve jetzt` bleiben unverändert wirksam.

## 5. Tests

`harness/tests/test_r13al_fixes.py` — **24 Tests**:

| Klasse | was geprüft wird |
|---|---|
| `TestPeakFenster` | Peak sperrt; 30 min vor Peak sperrt („Peak beginnt in 30 min, Vorlauf 90 min"); 120 min vor Peak startet; `frei_ab()` ist wirklich frei; `peak_vorlauf_min = 0` sperrt nur das Fenster selbst; abschaltbar; Feiertag (Do 02:00 UTC) ist kein Peak; die fünf Daten stehen in der Konfiguration; die Regel-Funktionen in `pricing` |
| `TestZweitePruefungVorDemStart` | Start im Peak **wartet** und startet bei Off-Peak (Arbeitstext belegt den Start); der Wartezustand wird als `GATE_APPROVAL` mit `PEAK…`-Grund gesetzt; ein verworfenes Gate beendet das Warten ohne Start; Off-Peak startet sofort und ohne Warte-Meldung; **kein** `peak_gate` nach `run_worker` in `_loop` |
| `TestApproveJetzt` | `/approve` im Peak setzt **keinen** Ausweg, `/approve jetzt` setzt ihn und loggt `Freigabe trotz Peak (Nutzer)`; Text nach `/approve` bleibt `/ds`-Nachricht; der erzwungene Start trägt `trotz Peak gestartet (Nutzer)` im Zustand **und** in `result.json` und räumt ihn danach weg; `_finish_run` schreibt das Feld nur, wenn der Vermerk gesetzt ist |
| `TestPeakBericht` | Sonde und Beleg liegen im Repo, der Beleg sagt „Im PEAK gestartet: 0"; **`Starte Batch` steht nicht im Log** (sonst wäre der Beleg falsch) |

Zusätzlich re-gelaufen (Schleife/Peak berührt): `test_r13u` 4, `test_r13m` 3, `test_r13b`
18, `test_r13c` 25, `test_units` 30, `test_r10` 23, `test_r13k` 7, `test_r13p` 24,
`test_r13ad` 30, `test_local_control` 22 — alle OK.

## 6. Was NICHT geprüft ist

* Der 20-s-Takt ist im Test abgeschaltet (`time.sleep` gepatcht); gemessen ist die **Zahl**
  der Prüfungen, nicht die echte Wartezeit.
* Der Zustand `GATE_APPROVAL` mit `PEAK:`-Grund ist im Test nur über `state.set`
  nachgewiesen (die Anzeige in `/status` und `watch` wurde nicht nachgesehen).
* Ob DeepSeek an den fünf Feiertagen wirklich off-peak abrechnet, ist **nicht belegt** —
  die Liste folgt der billigeren Annahme.
