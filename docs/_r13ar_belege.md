# R13ar-Belege (2026-09-30): Zuguhr der Aussensicht, Frühwarnung, num_turns-Rätsel

Auftrag: **(1)** ein Hook wie die Batch-Uhr des Workers — nach jedem Werkzeugaufruf der
Aussensicht die Zeile `Zug X von <meta_max_turns>`, ab Zug (Limit − 5) zusätzlich „JETZT
die Antwort im Blockformat schreiben, Unvollständiges als nicht geprüft kennzeichnen."
**(2)** Frühwarnung, wenn ein erfolgreicher Lauf mehr als 80 % des Limits braucht
(Telegram + Bericht). **(3)** Nur berichten: wie passt `meta-214` (35 Züge, Limit 30)?

Belege (alle nur lesend erzeugt):

| Datei | Was |
|---|---|
| `docs/_r13ar_zuege.txt` + `_r13ar_zuege.py` | Zählweisen je Lauf (num_turns, Runden, Aufrufe) |
| `docs/_r13ar_limit_probe_reviewer.txt` | Messung mit echtem CLI-Lauf: `--max-turns 2` bricht nach 2 Runden ab |
| `docs/_r13ar_limit_probe.txt` (Rolle Worker) | Gegenprobe: im Worker-Umfeld wirkt `--max-turns` **nicht** |
| `docs/_r13ar_hook_eingabe.txt` | Was ein PostToolUse-Hook auf stdin bekommt (`transcript_path`!) |
| `docs/_r13ar_probe_hook.txt` | Echter Lauf mit der Zuguhr — das Modell nennt die Zeile wörtlich |
| `docs/_r13ar_cli_hilfe.txt` | `claude --help`: `--max-turns` ist dort **nicht** dokumentiert (Grund für die Messung) |

## 1. Was die CLI als „Zug" zählt (Punkt 3 des Auftrags, zuerst gemessen)

Zwei winzige echte Läufe (Modell Opus/Abo, Auftrag: drei Dateien lesen):

```
A: ohne --max-turns      rc=0 subtype=success        num_turns=4  Antworten=4  Werkzeugaufrufe=3
B: mit --max-turns 2     rc=1 subtype=error_max_turns num_turns=3  Antworten=2  Werkzeugaufrufe=2
                         Fehlertext: Reached maximum number of turns (2)
```

→ Die Option **greift** und zählt die **Werkzeugrunden** (Modellantworten mit
Werkzeugaufruf). `num_turns` im Ergebnis-Ereignis ist eine *andere* Zahl: sie ist
`Werkzeugergebnisse + 1` (in B: 2 + 1 = 3; in A: 3 + 1 = 4).

**Auflösung des Rätsels aus R13aq.** `[meta] max_turns` stand seit R13w unverändert auf
**30** (`git show 1eee551:harness/harness.toml`, ebenso `13cec08`, `4d74a57`, `a9b18e5` —
also auch beim Lauf `meta-214` um 18:43) und die Option wird seit R13w mitgegeben
(`--max-turns` in `aussensicht.build_command`). Die Läufe gezählt:

| Lauf | Runden (= Züge der CLI) | `num_turns` | Werkzeugaufrufe | Ergebnis |
|---|---|---|---|---|
| meta-208 | 18 | 28 | 27 | success |
| meta-209 | 10 | 17 | 15 | success |
| meta-210 | 19 | 26 | 25 | success |
| meta-211 | 15 | 25 | 24 | success |
| meta-212 | 16 | 24 | 23 | success |
| meta-213 | 18 | 29 | 28 | success |
| **meta-214** | **23** | **35** | 34 | success (Limit 30 ⇒ **kein** Widerspruch) |
| **meta-217** | **30** | 31 | 41 | `error_max_turns` (Limit 30 ⇒ Abbruch) |

Für alle acht erfolgreichen Läufe gilt `num_turns = Werkzeugergebnisse + 1` (8 von 8) —
`num_turns` zählt also **Werkzeugergebnisse**, nicht die Züge der CLI. meta-214 hatte 34
Aufrufe/Ergebnisse (→ 35) in nur 23 Runden, weil der Reviewer mehrere Aufrufe in einer
Antwort absetzt (R13aj); meta-217 kam auf 30 Runden — genau das Limit — und brach ab.
Gegenprobe aus zweiter Quelle: das **Transcript** der Sitzung meta-217
(`cc-reviewer/projects/g--Silent-Scope-Decomp/d19c9eda-…jsonl`) ergibt dieselben **30**
Runden (`_r13ar_zuege.txt`, Test `test_transcript_zaehlt_dasselbe`).

**Nebenbefund (gemessen):** im **Worker**-Umfeld (DeepSeek, `ANTHROPIC_BASE_URL`) hat
`--max-turns` **keine** Wirkung — Lauf B mit `--max-turns 2` lief mit 4 Zügen durch
(`_r13ar_limit_probe.txt`). Der Worker gibt dort ohnehin 800 mit
(`[claude] max_turns_safety`); für die Aussensicht (Abo-Umfeld) ist das Limit wirksam.

## 2. Die Zuguhr (Punkt 1)

`harness/tools/aussensicht_uhr.py` — PostToolUse-Hook, gehängt über `--settings`:

```json
{"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "timeout": 10,
  "command": "…python.exe", "args": ["…/tools/aussensicht_uhr.py", "--limit", "50"]}]}]}}
```

* Die Einstellungsdatei schreibt `aussensicht.write_hook_settings(cfg, batch)` nach
  `runs/meta-<N>-hooks.json`; `build_command(cfg, hooks_settings=…)` hängt `--settings` an
  (beides in `aussensicht.run`).
* **Gezählt wird im Transcript**, nicht durch Zählen der Hook-Aufrufe: die Hook-Eingabe
  trägt `transcript_path` (gemessen: `_r13ar_hook_eingabe.txt`), und
  `hx.streamjson.runden_aus_zeilen` zählt darin dieselben Runden wie der Harness am Ende
  (`max_turns`-Semantik der CLI). Parallele Aufrufe in einer Antwort zählen **einmal**.
* Ausgabe nach jedem Werkzeugaufruf:

```
AUSSENSICHT-UHR: Zug 7 von 50 (Werkzeugrunden). Noch 43 Zuege bis zum Abbruch.
```

  und ab `Zug >= Limit − 5` zusätzlich (Wortlaut aus dem Auftrag):

```
JETZT die Antwort im Blockformat schreiben, Unvollständiges als nicht geprüft kennzeichnen.
```

* **Belegt mit echtem Lauf** (`_r13ar_probe_hook.txt`, Limit 5, Modell nennt die Zeile
  wörtlich): „AUSSENSICHT-UHR: Zug 1 von 5 (Werkzeugrunden). Noch 4 Zuege bis zum Abbruch.
  JETZT die Antwort im Blockformat schreiben, …" — derselbe Nachweisweg wie bei der
  Batch-Uhr (`docs/_r13ac_hook.txt`).
* **Kein Fehler stört den Lauf**: fehlt das Transcript, ist es unlesbar oder fehlt
  `--limit`, gibt der Hook nichts aus und endet mit 0 (Tests).

## 3. Frühwarnung (Punkt 2)

`aussensicht.limit_hinweis(batch, runden, grenze)` — eine Quelle, zwei Anzeigen:

```
Aussensicht B217: 25 von 30 Zuegen genutzt - Limit pruefen      (ab > 80 % des Limits)
```

* Telegram: der Orchestrator sagt den Satz nach einem **gelaufenen** Lauf und schreibt
  `Zuglimit fast erreicht` ins Log (mit `runden`, `limit`, `num_turns`).
* Bericht `runs/meta-<N>.md`: immer die Zeile
  `- Zuege (Werkzeugrunden): X von Y - num_turns laut CLI: N`, bei > 80 % zusätzlich
  `- LIMIT PRUEFEN: <Satz>`.
* `runs/meta-<N>.json` trägt `zug_runden` (und weiter `zuege` = `num_turns`).
* Gegengerechnet an den echten Läufen: 23/30 warnen nicht, 30/30 hätten gewarnt.

## 4. Tests

`harness/tests/test_r13ar_fixes.py` — **27 Tests**: Rundenzählung (parallele Aufrufe, mehrere
Ereignisse je Nachricht, Antwort ohne Werkzeug, kaputte Zeilen), die **echten** Läufe
meta-214 (23 Runden / `num_turns` 35) und meta-217 (30 / 31), das Transcript der Sitzung
meta-217 (30), der Hook als Unterprozess (Uhr-Zeile, Frist ab Limit − 5, keine Frist
davor, ohne Transcript/Limit still), die Einstellungsdatei samt `--limit`, die
Frühwarnung (Grenze bei genau 80 %) sowie Bericht, JSON und der Orchestrator-Weg.

Volle Reihe: siehe Abschnitt 6.

## 5. Was sich nicht geändert hat

`--max-turns` bleibt in `aussensicht.build_command` und wird weiter aus
`meta_max_turns`/`max_turns` gelesen (R13aq). Der Hook ergänzt ihn, ersetzt ihn nicht.

## 6. Nicht geprüft / offen

* Ob die **Frist** das Modell wirklich zum rechtzeitigen Antworten bewegt, zeigt erst ein
  Lauf, der wieder viele Züge braucht; belegt ist, dass der Text ankommt.
* Die Zuguhr ist im laufenden Harness **noch nicht aktiv** (die alte Fassung liegt im
  Speicher) — sie wirkt ab dem nächsten Start.
* Der Hook liest je Werkzeugaufruf das Transcript (Größenordnung 0,2–0,6 MB, Deckel 16 MB).
  Gemessen ist der Lauf mit dem Hook (6 s, ein Zug); Dauer bei langen Läufen nicht.
