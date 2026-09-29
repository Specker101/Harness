# R13ai-Belege (2026-09-29): Fragen an den Nutzer, Zeitkappung nachgemessen

Auftrag (Nutzer, 2026-09-29): (1) Regel „Fragen an den Nutzer" in
`prompts/reviewer.md`; (2) **Nachtrag zu R13ah** — `BASH_DEFAULT_TIMEOUT_MS` bleibt 600 s,
der Vorspann sagt den nötigen `timeout`-Parameter, und es ist zu prüfen/berichten, ob der
Worker in B212–B214 einen `timeout` übergeben hat; (3) **nur berichten**: der `git commit`
in B213 (601,6 s) und die beiden `Grep` in B212 (602,3 s / 511,0 s).

Alles im Harness-Repo; gelesen wurden die Mitschnitte `runs/b212…b214/stream.jsonl`. Der
laufende Batch (B215) wurde nicht angefasst. Messwerkzeug: `docs/_r13ai_stream_probe.py`,
Messdatei `docs/_r13ai_messung.txt` (Dauer je Aufruf aus den Ereignis-Zeitstempeln,
gerechnet wie `hx/streamjson.py`).

---

## 1. Fragen an den Nutzer (umgesetzt in `prompts/reviewer.md`)

Neuer Abschnitt `## Fragen an den Nutzer (R13ai, 2026-09-29)` nach der Eskalationsregel:

* Gefragt wird nur bei **grundsätzlichen Weichenstellungen**: Projektziel, Strategie,
  Strangwechsel, Aufnahmen, Budget/Umfang (die fünf Fälle aus „Wer entscheidet was").
* **Technische Einzelposten entscheidet der Reviewer selbst** und führt sie als
  `ENTSCHIEDEN (Reviewer): …` mit Begründung im Batch-Dokument: Zähler- und Anzeigefehler,
  Werkzeug-Altposten, Aufräumarbeiten, Reihenfolgen, Regelnummern wie `R330`/`R535`. Eine
  Regelnummer ist **kein** Entscheidungsgrund — sie ist Projektwissen aus dem Repo.
* Muss doch gefragt werden: **Alltagssprache**, je Frage **ein Satz**, immer **was sich im
  Ergebnis ändert** und eine **Empfehlung**; **keine Regel- oder Postennummern ohne
  Erklärung**. Beispiele: eine gute Frage (Weichenstellung: Handport vs. Hybrid-Boot, mit
  Wirkung und Vorschlag) und eine schlechte („Soll R330 jetzt gemessen werden?").

Tests: `harness/tests/test_r13ai_fixes.py` (6).

## 2. Zeitkappung — Nachtrag zu R13ah

**Was sich nicht ändert:** `BASH_DEFAULT_TIMEOUT_MS` bleibt **600000 ms**. Ein Aufruf
**ohne** eigenen `timeout`-Parameter wird weiter nach 600 s gekappt; `BASH_MAX_TIMEOUT_MS`
(1800000) ist nur die **Obergrenze** für Aufrufe, die ausdrücklich `timeout` setzen.

**Neu im Vorspann** (`hx/worker.py`, Abschnitt `ZEIT`, direkt bei der Batch-Uhr): *„Für
`preflight.py`, `c_kopf.py mutalle` und `port_build` den Bash-Parameter `timeout=1800000`
setzen; sonst wird nach 600 s gekappt."* Zusätzlich im Abschnitt `RECHENZEIT`: der erlaubte
Wert geht jetzt **bis 1800000 = 30 min** (vorher „bis 600000 = 10 min"), mit dem
Messhinweis **„`timeout=600000` ist KEINE Erhöhung — das war schon die alte Obergrenze"**.

### 2a. Hat der Worker in B212–B214 einen `timeout` übergeben? (gemessen)

| Batch | Aufrufe | davon mit `timeout` | Kappenungen (Aufruf ≥ 600 s) |
|---|---|---|---|
| B212 | 234 | **28** | `Get-ChildItem …` (601,9 s, **ohne** `timeout`), `Grep` (602,3 s, ohne - Grep kennt keinen Parameter) |
| B213 | 211 | **52** | `preflight.py` (602,0 s, **`timeout=600000`**), `git commit … ; mutalle`-Kette (601,6 s, **`timeout=600000`**) |
| B214 | 293 | — | `preflight.py` (601,8 s, `timeout=600000`), `c_kopf.py mutalle` (601,3 s, `timeout=600000`), `Set-Content …; git commit -F` (601,1 s, `timeout=600000`), zwei `Wait-Process`-Warteschleifen (541,9/541,8 s) |

**Antwort:** Ja, der Worker hat bei den langen Python-Aufrufen `timeout` gesetzt — aber
**`timeout=600000`**, also **genau die alte Obergrenze**. Das erhöht nichts: der Aufruf
wurde trotz Parameter bei 600 s gekappt und in den Hintergrund geschoben (wörtlich in den
Ergebnissen: *„Command did not complete within its 600s timeout and was moved to the
background"*). Deshalb die Vorspann-Zeile mit `1800000`.

## 3. Bericht: die drei Aufrufe (nur gelesen, nichts geändert)

### 3a. B213, `git commit`-Kette 601,6 s — Aufruf `call_00_wOBDiYNYko23JfCWSq568167`

```text
timeout : 600000
Befehl  : git add port/src/ckopf_leaves.cpp analysis/_m213/;
          git commit -q -m "B213: Port - L8579C Rueckgabewert und Rufargumente nach dem
          Rohwort"; git log --oneline -1;
          python -u scripts\c_kopf.py mutalle 2>&1 | Select-Object -Last 3
Ergebnis: Command did not complete within its 600s timeout and was moved to the
          background (ID: b1pjmwlod) …
```

**Kein Hänger von Git.** Die Kette enthielt am Ende `python -u scripts\c_kopf.py mutalle` —
der lange Teil ist `mutalle`, und die Kappung traf die **ganze** Kommandozeile. Weder
Editor noch Hook noch Lock kommen in Frage, geprüft am Decomp-Repo:

| Prüfung | Ergebnis |
|---|---|
| `git config core.editor` | (leer) |
| `git config core.hooksPath` | (leer) |
| aktive Hooks in `.git/hooks` | **keine** (nur `.sample`) |
| `git --version` | `2.43.0.windows.1` |
| Commit-Nachricht | kam als `-m "<Text>"` bzw. `-F <Datei>` — kein Editor nötig |

Zwei weitere Beobachtungen zur Kette:
* Ein **früherer** Commit-Versuch in B213 benutzte ein PowerShell-Here-String als
  `-m`-Argument und scheiterte an Git: `error: pathspec 'ausgeduennt' did not match any
  file(s) known to git` (die Zeile `"| ausgeduennt k"` wurde zerteilt). Der Worker hat
  danach auf `git commit -q -F analysis/_m213/_commitmsg_tool.txt` umgestellt — die
  saubere Form. Das war **schnell** (kein Kandidat in der ≥500-s-Liste), nicht die Ursache
  der 601,6 s.
* Die beiden Warteschleifen in B214 (`Get-Process -Id 18400 … Wait-Process -Timeout 540`)
  sind die **Folge** der Kappung von `mutalle`.

### 3b. B212, `Grep` 602,3 s — Aufruf `call_01_HQLhjgqfM2gAM1n6oO1o4624`

```text
timeout : (nicht gesetzt — das Grep-Werkzeug hat keinen solchen Parameter)
Eingabe : pattern = 'ppc_cov_boot|_cov_boot'
          path    = 'g:\Silent Scope Decomp\scripts'      <- der Pfad
          output_mode = content, -n = true, head_limit = 20
Ergebnis: normale Treffer (scripts\f5_descr_triage.py:9 …, m209_boot_zensus.py:14 …)
```

### 3c. B212, `Grep` 511,0 s — Aufruf `call_01_Nw964KtvGL5JYfXePAd81923`

```text
timeout : (nicht gesetzt)
Eingabe : pattern = 'rfi|sc |srr|evpr|EVPR|exception|run_step|mtspr|mfspr|mtmsr|mfmsr'
          path    = 'g:\Silent Scope Decomp\port\hybrid\ppc_kern.cpp'   <- der Pfad
          output_mode = content, -n = true, head_limit = 60
Ergebnis: normale Treffer (393: … xo == 339 … | 555: … rfi …)
```

**Beide Grep-Aufrufe liefen über einen Pfad, nicht über eine Kommandozeile**, und **beide
Ergebnisse sind normale Trefferlisten — keine Kappungsmeldung.** Die Zahl 602,3 s bzw.
511,0 s ist der **Abstand zwischen `tool_use`- und `tool_result`-Ereignis**, nicht die
Laufzeit des Grep selbst (genau so rechnet der Harness in `hx/streamjson.py`). Auffällig:
die beiden 511,0-s-Werte von `port_build.ps1 -Gl` (511,0 s, `timeout=600000`, echtes
Kompilieren der GL-Senke) und dem Grep sind **identisch** — der Messpunkt teilt also eine
gemeinsame Wartezeit auf beide Aufrufe auf (Ergebnisse kommen gebündelt zurück). Für 602,3 s
gilt dasselbe Muster: direkt davor lief der 601,9-s-`Get-ChildItem`-Aufruf in den
Hintergrund (`[IO.File]::ReadAllBytes` + `Sort-Object -Unique` über 4 MiB), der die Maschine
und die Werkzeug-Schlange belegte. **STRONG INFERENCE, nicht CONFIRMED:** belegt ist, dass
kein Kappungs- und kein Fehlertext im Grep-Ergebnis steht; die Ursache der Wartezeit ist aus
dem Mitschnitt allein nicht zu trennen.

## 4. Was NICHT geprüft wurde

* Ob der Worker die neue Vorspann-Zeile **befolgt** — das zeigt erst ein Batch, in dem
  `preflight.py`/`mutalle` länger als 600 s dauert und **nicht** gekappt wird (B215+).
* Eine genaue Zuordnung der 511,0 s: der Mitschnitt hat keine eigene Werkzeug-Laufzeit,
  nur die Ereignis-Abstände (s. 3c).
