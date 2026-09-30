# R13as-Belege (2026-09-30): Reihenfolge-Wächter (Außensicht M218-1)

Auftrag: Nach jedem Batch aus `runs/b<N>/stream.jsonl` auswerten, ob `port/` **vor** dem
Commit `B<N>: Vorhersage` angefasst wurde; mtime-Befehle im ganzen Batch; Erkundungs-Branches
`erkundung-b<N>` getrennt zählen. Ergebnis nach `result.json` und als Zeile in die
Review-Fakten. Rückwirkend für B208–B218 berichten.

| Datei | Was |
|---|---|
| `docs/_r13as_belege.txt` (erzeugt von `docs/_r13as_belege.py`) | Tabelle B208–B219 + Belegstellen je Abweichung |
| `harness/hx/reihenfolge.py` | der Wächter (reine Regeln + ein `git log`-Aufruf) |
| `harness/tests/test_r13as_fixes.py` | 42 Tests, mit Ausschnitten aus dem echten B218-Mitschnitt |

## 1. Was in B218 gemessen wurde (der Befund)

Der Commit `B218: Vorhersage` entstand am **2026-09-30 01:47:25 +02:00** (`51e736aef`,
`git log --format=%cI`). Davor liegen **18 port/-Schreibzugriffe**:

| Zeile im Mitschnitt | Zeit (UTC) | Werkzeug | Ziel |
|---|---|---|---|
| 24699 | 23:26:53 | Edit | `port/hybrid/ppc_kern.h` |
| 24760 | 23:26:56 | Edit | `port/hybrid/ppc_kern.h` |
| 24764 | 23:26:59 | Edit | `port/hybrid/ppc_kern.cpp` |
| 24950/24953/24957 | 23:27:02–23:27:08 | Edit | `port/hybrid/ppc_kern.cpp` |
| 25594/25654 | 23:27:16–23:27:22 | Edit | `port/hybrid/kern_diff.cpp` |
| … (insgesamt 17 `Edit`, Beleg nennt die ersten acht) | bis 23:42:34 | Edit | `port/hybrid/{ppc_kern,maschine,kern_diff}.cpp/.h` |
| 75343 | 23:46:44 | PowerShell | `git checkout -- port/` (Rücknahme vor dem Commit) |

Danach (23:47:29, Zeile 77707) wurde `port/hybrid/` aus der Sicherungskopie
zurückgeholt und um **23:58:14** (Zeile 80521) die **Änderungszeiten** der vier Dateien
auf „jetzt" gesetzt (`(Get-Item $f).LastWriteTime = $jetzt`) — der im Auftrag genannte
Vorgang. Die R391-Zeile im Denkblock meldete dazu OK.

Zahlen: `port_gesamt` = 21 Zugriffe, davon **18 vor** der Vorhersage, **1 mtime-Befehl**,
0 Erkundung. Die Zeile lautet damit:
`REIHENFOLGE-WÄCHTER: ABWEICHUNG - 18 port/-Schreibzugriffe vor der Vorhersage, 1 mtime-Befehle`.

## 2. Rückblick B208–B219 (Auftrag Punkt 3)

Quelle: `docs/_r13as_belege.txt`. „vorher" = Schreibzugriffe auf `port/` vor dem
Vorhersage-Commit des jeweiligen Batches; „mtime" = Befehle, die Änderungszeiten setzen,
im **ganzen** Batch; „port ges." = alle port/-Schreibzugriffe des Batches.

| Batch | Vorhersage-Commit | vorher | mtime | Erkundung | port ges. | Aufrufe | Befund |
|---|---|---|---|---|---|---|---|
| B208 | 2026-09-28 19:16:32 | **20** | 0 | 0 | 22 | 117 | ABWEICHUNG |
| B209 | 2026-09-28 20:07:20 | **8** | 0 | 0 | 8 | 184 | ABWEICHUNG |
| B210 | 2026-09-28 22:10:24 | 0 | 0 | 0 | 11 | 187 | sauber |
| B211 | 2026-09-28 23:33:13 | **32** | 0 | 0 | 33 | 229 | ABWEICHUNG |
| B212 | 2026-09-29 01:11:41 | 0 | 0 | 0 | 15 | 234 | sauber |
| B213 | 2026-09-29 14:22:09 | **4** | 0 | 0 | 5 | 211 | ABWEICHUNG |
| B214 | 2026-09-29 17:30:43 | **20** | 0 | 0 | 34 | 293 | ABWEICHUNG |
| B215 | 2026-09-29 20:01:07 | 0 | 0 | 0 | 11 | 228 | sauber |
| B216 | 2026-09-29 22:35:02 | 0 | 0 | 0 | 30 | 329 | sauber |
| B217 | 2026-09-30 00:27:36 | 0 | 0 | 0 | 5 | 139 | sauber |
| **B218** | 2026-09-30 01:47:25 | **18** | **1** | 0 | 21 | 271 | ABWEICHUNG |
| B219 | (läuft noch) | – | 0 | 0 | 0 | 81 | kein Vorhersage-Commit |

**Ergebnis:** nicht nur die erwarteten vier. Betroffen sind **B208, B209, B211, B213,
B214, B218** (6 von 11 abgeschlossenen Batches), sauber sind B210, B212, B215, B216, B217.
Der **erste mtime-Befehl der ganzen Reihe** steht in B218 (Zeile 80521) — er ist neu und
gehört deshalb in die Review-Fakten.

## 3. Wie erkannt wird (und was absichtlich NICHT zählt)

`hx/reihenfolge.py` zählt **nur** die im Auftrag genannten Formen:

* `Edit`/`Write`/`MultiEdit`/`NotebookEdit` mit `file_path` (auch `notebook_path`, `path`)
  unter `port/` — relativ (`port/x.cpp`) oder absolut (`g:/Silent Scope Decomp/port/…`);
* Umleitung nach `port/` (`>`, `>>`, `*>`, `*>>` — nicht `2>&1`, deshalb die
  Ziffern-Lookbehind);
* `Copy-Item`/`Move-Item`/`cp`/`mv`/`robocopy`/`xcopy` mit `port/` als **Ziel** (letztes
  Argument ohne Schalter) — die Sicherungskopie **aus** `port/` heraus (B218 Zeile 75340)
  zählt nicht;
* `New-Item`/`Set-Content`/`Out-File`/`Add-Content`/`Remove-Item`/`del`/`rm`/`mkdir`/`ren`
  mit einem `port/`-Argument;
* `git checkout|restore|stash|reset|clean|switch`: auf `port/`, auf den ganzen
  Arbeitsbaum (`.`, `*`, `:/`, keine Pfadangabe, `git stash`, `git reset --hard`,
  `git clean`) — **nicht** bei `-b`/`-c` (anlegen), `stash list/show/drop`, `clean -n`,
  `reset --soft/--mixed`, und nicht bei `git checkout -- analysis/`.

**Nicht gezählt** (Lesen ist kein Eingriff): `Read`/`Grep`/`Select-String -Path port\…`,
`& port\build\hybrid_lauf.exe`, `git status --porcelain port/ Makefile`, `mingw32-make
hybrid` (Bauartefakte unter `port/build/` stehen nicht unter Versionskontrolle — genau
deshalb bleibt die R391-Prüfung `git status --porcelain port/ Makefile` dabei leer).

Zwei Fallen, die erst die Messung gezeigt hat (beide mit Test):

1. **Groß-/Kleinschreibung.** PowerShell schreibt `Copy-Item`, `Remove-Item`,
   `Set-Content` groß. Die erste Fassung verglich klein gegen den Originaltext und
   übersah die Wiederherstellung (B218 Zeile 77707) still — die Testfixture hat es
   aufgedeckt (`_verb_treffer` ist jetzt `IGNORECASE`).
2. **Nutzlast in `-Value`.** In B217 (Zeile 73332) lautet ein Befehl
   `Add-Content -Path analysis\_m217\_hybrid.txt -Value "…port/build/hybrid_lauf.exe…"`:
   der **Text** nennt `port/`, geschrieben wird nach `analysis/`. Werte von
   `-Value/-Content/-Description/-Filter/-Pattern/-Subject/-Message/-Comment/-Encoding`
   werden deshalb nicht als Ziel gelesen (Test `test_nutzlast_im_value_zaehlt_nicht`).

Die Erkundungsregel ist gebaut und getestet, aber **im Material leer**: im Decomp-Repo
gibt es weder Branch noch Worktree `erkundung-b*` (`git branch -a`, `git worktree list`,
2026-09-30), und in B208–B219 nennt kein einziger Befehl diesen Namen. Sie wird als
Textfund im Befehl oder Pfad erkannt; wer erst `cd` in den Worktree macht und danach
relative Pfade bearbeitet, wird über den `file_path` erkannt (absolut), nicht über den
Befehlstext — das ist die benannte Grenze der Erkennung.

## 4. Wo es landet

* `runs/b<N>/result.json`: `reihenfolge_port_vor_vorhersage` (Zeile, ts, Werkzeug, Pfad,
  Grund), `erkundung`, `mtime_manipulation` sowie `reihenfolge_port_gesamt`,
  `reihenfolge_vorhersage_ts`, `reihenfolge_commits`, `reihenfolge_fehler`
  (`worker._finish_run`, eine `git log`-Abfrage je Batch).
* Review-Fakten (`runs/b<N>/harness-facts.md`, `Orchestrator.harness_facts`):
  `- REIHENFOLGE-WÄCHTER: sauber` bzw.
  `- REIHENFOLGE-WÄCHTER: ABWEICHUNG - <n> port/-Schreibzugriffe vor der Vorhersage,
  <m> mtime-Befehle`, bei Erkundung ergänzt um
  `; Erkundung: <k> Zugriffe in erkundung-b* (getrennt gezählt, keine Abweichung)`.
* Kein stilles „sauber": fehlt der Vorhersage-Commit, steht
  `kein Vorhersage-Commit gefunden - <n> port/-Schreibzugriffe im Batch nicht einzuordnen`;
  ist `git` nicht lesbar, `nicht prüfbar - <Grund>`.
* Log: `Reihenfolge-Waechter: ABWEICHUNG` (nur bei Treffern).

## 5. Tests

`harness/tests/test_r13as_fixes.py` — **42 Tests**: Vorhersage-Commit (echte Betreffs,
BOM bei B215, Rumpf-Treffer zählt nicht, frühester gewinnt, Zeitzonenvergleich
UTC gegen `+02:00`), die Schreibzugriffsregeln (alle Nicht-Treffer aus B218, Sicherungskopie
aus `port/`, Nutzlast in `-Value`, Here-String, `git`-Fälle), mtime-Arten, Erkundung,
der **echte B218-Mitschnitt als Ausschnitt** (6 vor / 7 gesamt / 1 mtime, die Leser-Zeilen
1, 5, 7, 9, 10 in keiner Liste), ein sauberer Batch, die Faktenzeilen-Wortlaute, der Weg
über `worker._finish_run` (drei Listen im `result.json`) und die Zeile in
`harness-facts.md`.

Zeilenenden der Belegdatei: `_r13as_belege.py schreiben` schreibt selbst UTF-8 mit LF —
`| Out-File -Encoding utf8` verstümmelte Umlaute (`REIHENFOLGE-WÄCHTER` kam als
`REIHENFOLGE-W─CHTER` an).

## 6. Offen

* Der laufende Harness hat den Wächter noch nicht (die alte Fassung liegt im Speicher) —
  B219 bekommt ihn erst nach einem Neustart; nachgerechnet werden kann jeder Batch mit
  `python -u docs/_r13as_belege.py`.
* Die regulären Nachweise gelten für die im Auftrag genannten Formen; ein Umweg über
  einen Interpreter (`python -c "open('port/x','w')"`) wird nicht erkannt.
