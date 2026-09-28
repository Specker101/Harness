# Belege R13v3 (2026-09-28) — /autonom-Haltbarkeit und Aufräumen nach einem Abbruch

Alles rein lesend erzeugt (Decomp-Repo unberührt), Wirkung nach einem Neustart des
Harness-Fensters. Vorgeschichte: `docs/_r13v_belege.md` (R13v/R13v2).

## 1. `/autonom` überlebt Stop und Neustart — der Wert ist AUS

Werkzeug `tools/r13v3_zustand_probe.py`, Beleg `docs/_r13v3_beleg_zustand.txt`.

| Frage | Antwort (gemessen) |
|---|---|
| Wo wird `autonomous` geschrieben? | **nur** `orchestrator.py:718` (`handler` des Telegram-Befehls `/autonom`) und `cli.py:518/539` (Attrappe `hx.cli demo`, schreibt in **ihren eigenen** Zustand). Vorgabe: `state.py:26` `"autonomous": False` |
| Überlebt `/autonom off` einen Neustart? | ja: der Befehl schreibt **sofort** in die Datei; beim Laden werden nur **fehlende** Felder aus den Vorgaben ergänzt (Test: AN → Befehl → Datei `false` → frisch gelesen `false`) |
| Setzt das Stoppen es zurück? | nein: nach `state.set(STOPPED, …)` steht weiter `false` |
| Was steht JETZT in den Zustandsdateien? | `state/run.json` **false**, `state/_demo_ok/state/run.demo-ok.json` false, `state/_demo_parser_error/…` false, `state/run.demo-ok.json` false. Eine Suche über den **ganzen** Harness-Ordner nach `"autonomous": true` findet **keine** Datei |
| Vorgabe ohne Datei | AUS |

**Nachbemerkung des Bearbeiters (eigener Fehler):** im Abschlussbericht zu R13v2 stand
„`state/run.json` hat weiterhin `autonomous: True`" — das war aus der Sitzungs-
zusammenfassung übernommen und **nicht** nachgelesen. Der Wert war und ist `false`;
der Satz war falsch. Lehre: Zustandswerte nicht aus dem Gedächtnis berichten.

Tests: `tests/test_r13v3_fixes.TestAutonomHaelt` (Vorgabe, Befehl → sofort auf der
Platte, Neustart, Stop, Gegenrichtung, Schreibstellen).

## 2. Aufräumen nach einem Abbruch (Punkt 2a)

Werkzeug `tools/r13v3_aufraeumen_probe.py`, Beleg `docs/_r13v3_beleg_aufraeumen.txt`
(Herzschlag-Dateien: `tools/r13v_herzschlag.py` schreibt alle 0,5 s; „Alter wächst" =
Prozess tot). Zusätzlich `tools/r13v3_job_zeitreihe.py` (Zeitreihe mit Absolutzeiten).

| Fall | Messung | Ergebnis |
|---|---|---|
| JOB-DIREKT: Kind echtes Kind der Shell, Job **vor** dem Kind zugewiesen | Alter 0,4 s → 2,4 s → 4,4 s → 6,4 s → 8,4 s | **Kind stirbt mit dem Job** |
| JOB-STARTPROCESS: Kind per PowerShell-`Start-Process` | Alter 0,2 s → 2,2 s → 4,2 s → 6,2 s → 8,2 s | **Kind stirbt mit dem Job** |
| NACHSUCHE-WMI: per WMI gestartet (kein Elternbezug), Wurzel in der Kommandozeile | gefunden `[('python.exe', 20132, 'Kommandozeile nennt die Decomp-Wurzel')]`, beendet; Alter 0,2 s → 4,4 s; Fremdprozess daneben 0,2 s → 0,4 s (lebt) | **beendet**, Fremdprozess **unangetastet** |
| NACHSUCHE-B207: Hintergrundlauf nennt nur `scripts/c_kopf.py`, startendes Shell tot | „OHNE PID-Nachweis: gefunden=[]" / „MIT PID-Nachweis: gefunden … 'waehrend des Laufs als Nachfahre des Workers gesehen', beendet" | **nur der PID-Nachweis findet ihn** |
| R13i-Schutz | `ausgenommen (eigener PID-Kreis): [8844, 10664, 11288, 11392, 19312, 19400]` | Harness + Vorfahren sind **nie** Kandidat |

**Fehler im ersten Messanlauf (dokumentiert, weil lehrreich):** dort wurde der Job erst
zugewiesen, nachdem die Shell das Kind schon gestartet hatte — das Kind erbte ihn nicht
und lief in beiden Fällen weiter (Alter blieb konstant 0,1 s), obwohl die Shell starb.
Die Zeitreihe (`r13v3_job_zeitreihe.py`) hat das entlarvt. Im Harness ist die Reihenfolge
richtig: `proc.run_stream` weist den Job **sofort nach `Popen`** zu, bevor der Worker
irgendetwas starten kann.

Tests: `TestKandidaten` (7 Fälle: Wurzel-Pfad, Nachfahre, Fremdprozess, Harness-Schutz
per Kommandozeile, Alter, ausgenommene PIDs, Bauwerkzeuge), `TestJobObjekt`
(echter Kindprozess stirbt; `run_stream` weist zu), `TestVorgaengerSicherung`.

## 3. Halber Stand wird gesichert und im Review gemeldet (Punkt 2b)

* `orchestrator.wip_nach_abbruch` läuft **direkt nach** `wk.run_batch`, sobald
  `res.killed_reason` gesetzt ist: `gitsafe.wip_rescue` schreibt `logs/wip-b<N>-status.txt`
  und `logs/wip-b<N>.patch` und legt (Konfiguration `git.wip_stash`, Vorgabe an) den
  Stand in den Stash `harness-wip-b<N>`. Neu: die **Stash-Referenz** steht im Ergebnis
  (`git stash apply <ref>`).
* Der Zustand trägt `letzter_abbruch` = {batch, grund, ts, dirty, dateien, ref, patch};
  die Batch-Meldung nennt Grund, Dateizahl, Referenz — und **laut**, wenn die Sicherung
  fehlschlägt.
* Der Review bekommt den Block `=== ABBRUCH DES BEWERTETEN LAUFS ===` mit Grund,
  Sicherung, Handlungsregel (halber Stand ist NICHT mehr im Baum; wer ihn braucht, holt
  ihn per Stash) und der Nummernregel. Messdatenzeile: `Letzter Abbruch (R13v3): …`.

Tests: `TestWipNachAbbruch` (3 Fälle), `TestAbbruchImReview` (4 Fälle, u. a. der
Prompt-Block über die echte `reviewer.build_prompt`).

## 4. Welche Nummer der nächste Lauf bekommt (Punkt 2c)

Gemessen am **echten** Ankerkopf (`docs/_r13v3_beleg_zustand.txt`, Abschnitt 4):

    Ankerkopf im Decomp-Repo: BATCH 207
    expected_batch() = Anker + 1 = 208
    state['batch'] auf 999 gesetzt  ->  expected_batch() bleibt 208

`expected_batch()` liest **ausschließlich** den Ankerkopf (`orchestrator.py:1460`) — es
gibt bewusst keinen zweiten Zähler. Schreibt ein abgebrochener Worker den Anker nicht
fort, bekommt der nächste Lauf **dieselbe** Nummer und läuft in **denselben** Ordner
`runs/b<N>`; sein Review liegt dort ebenfalls. Damit die Belege des abgebrochenen Laufs
dabei nicht verschwinden, werden sie vorher umbenannt (`worker.sichere_vorgaenger`):
`stream.jsonl` → `stream-v1.jsonl` (die Datei, die `retention.MIT_ZIP` schon kannte),
`stream.err.txt`, `auftrag.md`, `result.json`, `antwort.md`, `harness-facts.md` ebenso.
Fremde Dateien (z. B. `reviewer.jsonl`) bleiben unberührt.

Tests: `TestVorgaengerSicherung` (3 Fälle) und
`TestAbbruchImReview.test_nummer_kommt_aus_dem_anker_nicht_aus_dem_zustand`.
