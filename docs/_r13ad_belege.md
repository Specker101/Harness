# R13ad — Batch-Zeitbudget, Kontextmessung, Fortsetzungsanstoss (2026-09-29)

Auftrag (Nutzer, drei Punkte, Reihenfolge der Commits vorgegeben):

1. **Kontext messen** — je Anfrage `input + cache_read + cache_creation`, in `result.json`
   und in den Review-Fakten; Kompaktierungen vermerken; einmaliger Rueckblick B205–B212.
2. **EINE Zeitquelle** — `alarm_wall_s` bleibt 90 min, neue Umschaltschwelle
   `umschalt_vor_alarm_s = 600` (Alarmgrenze minus 10 min = 80 min); der Reviewer nennt
   **keine eigene Minutenzahl** mehr; die Batch-Uhr zeigt Zeit, Schwelle und Kontext.
3. **Fortsetzungsanstoss** — ein regulaer, aber frueh beendeter Lauf wird im **selben
   Chat** fortgesetzt (`--resume`), solange (a)–(e) gelten.

## 1. Rueckblick B205–B212 (gemessen, `tools/kontext_rueckblick.py`)

Quelle: `runs/b<N>/stream.jsonl` (roh), gerechnet mit `streamjson.StreamStats.kontext_stats()`
— derselben Funktion, die `result.json` fuellt. Dauer/Anfragen aus `runs/b<N>/result.json`.

| Batch | Dauer | Anfragen | kontext_max | kontext_letzte_anfrage | Kompaktierungen |
|---|---|---|---|---|---|
| B205 | 38.6 min | 136 | 391246 | 391246 | keine |
| B206 | 58.0 min | 223 | 368260 | 368260 | keine |
| B207 | 47.4 min | 137 | 259162 | 259162 | keine |
| B208 | 19.3 min | 77 | 221665 | 221665 | keine |
| B209 | 28.0 min | 172 | 300186 | 300186 | keine |
| B210 | 46.2 min | 175 | 314422 | 314422 | keine |
| B211 | 37.4 min | 214 | 344847 | 344847 | keine |
| B212 | 52.4 min | 217 | 367772 | 367772 | keine |

Geprüft wurde der Mitschnitt **direkt** (nicht angenommen): `assistant.message.usage` traegt
`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`.
`system` fuehrt `subtype` `init|thinking_tokens|task_started|task_notification|…` — ein
`compact_boundary` kam in **keinem** der acht Mitschnitte vor (die vier „compact"-Treffer
in B212 sind Prosa in Denkbloecken bzw. die Slash-Command-Liste im `init`). Auto-Compact
lief also nie; die Kontextspitze lag bei 391k von 1M.

## 2. Was gebaut wurde

| Teil | Ort | Inhalt |
|---|---|---|
| Kontext | `hx/streamjson.py` | `kontext_summe`/`kontext_werte`/`kontext_stats`, `kompaktierungen` (explizite Grenze ODER Rueckgang ≥ 20000 Tokens und ≥ 20 %), `letzte_antwort_ohne_werkzeug`, `werkzeug_enthaelt`; `result`-Ereignisse werden gelistet und **summiert** (Fortsetzungen!) |
| result.json | `hx/worker.py` `_finish_run` | `kontext_letzte_anfrage`, `kontext_max`, `kontext_verlauf` (jede 25. Anfrage, letzte immer dabei), `kompaktierungen`, `fortsetzungen` |
| Live-Kontext | `hx/worker.py` `live_schreiben` | `state/run.json → live.kontext` (die Batch-Uhr liest ihn ohne Mitschnitt-Zugriff) |
| Review-Fakten | `hx/orchestrator.py` | Zeile „Kontext (Anfrage-Ende) … | Maximum … | Kompaktierungen …" und „Fortsetzungen (R13ad): …" |
| Eine Zeitquelle | `harness.toml` | `umschalt_vor_alarm_s = 600`, `kontext_limit = 1000000`, `kontext_schwelle = 550000`, `max_fortsetzungen = 2` |
| Batch-Uhr | `hx/uhr.py`, `tools/batch_uhr.py` | `… min von 90 min (Umschalten ab 80) | Kontext 310k von 1M …` |
| Fortsetzung | `hx/worker.py` | `build_command(..., resume=True)` → `--resume <session-id>`; `fortsetzung_pruefen`, `fortsetzungs_text`, `nachrueckliste_erledigt`, `rest_wanduhr_s`; die Laufschleife in `run_batch` |
| Reviewer | `prompts/reviewer.md` | keine eigene Minutenzahl mehr (relativ zur Umschaltschwelle); Pflichtabschnitt `## NACHRUECKLISTE`; bei Fortsetzung gilt der LETZTE Preflight |
| Rueckblick | `tools/kontext_rueckblick.py`, `docs/_kontext_rueckblick.txt` | die Tabelle oben, reproduzierbar |

## 3. Fortsetzung — Bedingungen und Grenzen

Fortgesetzt wird **nur**, wenn ALLE Punkte gelten: (a) regulaeres Ende (letzte Antwort ohne
Werkzeugaufruf, `killed_reason` leer, rc 0), (b) Batch-Uhr vor der Umschaltschwelle,
(c) `kontext_letzte_anfrage < kontext_schwelle`, (d) `NACHRUECKLISTE` im Auftrag,
(e) weniger als `max_fortsetzungen` Anstoesse. Danach: Anstoss im selben Chat; antwortet der
Worker `NACHRUECKLISTE ERLEDIGT`, ist Schluss.

Zeit, harte Wanduhr, Anfragen- (1000) und Kostenlimit ($2) gelten **kumuliert** ueber alle
Teillaute: alle Ereignisse laufen in DENSELBEN `StreamStats`; die harte Wanduhr wird je
Teillauf um die verbrauchte Zeit gekuerzt (`rest_wanduhr_s`). Die Fortsetzung schreibt ihren
Mitschnitt nach `stream-forts<N>.jsonl` und wird an `stream.jsonl` **angehaengt** — damit
bleiben `watch`, `rebuild` und der reasoning-Snapshot unveraendert gueltig. Der Teilmitschnitt
bleibt zusaetzlich liegen (Nachweis, welche Zeilen zu welchem Anstoss gehoeren) und ist in
`retention.MIT_ZIP_MUSTER` aufgenommen, wird also nach 14 Tagen mitgepackt.

**Bedingung (d) — korrigierte Messung (2026-09-29).** Ein erster Check ueber die
VS-Code-Suche meldete „kein Treffer"; das war **falsch**, denn die Suche ueberspringt `runs/`
(`search.exclude` / `.gitignore`). Mit PowerShell nachgemessen:

    Select-String -Path runs\b2*\auftrag.md -Pattern 'NACHR(UE|Ü)CKLISTE' -CaseSensitive:$false

| Beleg | Zeile | Wortlaut (Anfang) |
|---|---|---|
| `runs/b211/auftrag.md:170` | 170 | `NACHRUECKLISTE (in dieser Reihenfolge, je Punkt ein eigener Commit, nur wenn die Pflicht vor 70 min erfuellt ist):` |
| `runs/b212/auftrag.md:169` | 169 | `NACHRUECKLISTE (nach TEIL 1-5, vor dem Preflight, je Posten ein Commit mit Soll-Delta):` |
| `runs/b213/review.md:126` | 126 | `NACHRUECKLISTE (vor dem Preflight, je Posten ein Commit mit Soll-Delta):` (in `<DS_INSTRUCTION>`) |

Das Format `NACHRUECKLISTE (…):` am Zeilenanfang gab es also **schon**. `worker.hat_nachrueckliste`
akzeptiert es neben `## NACHRUECKLISTE`, `NACHRUECKLISTE:` und `Nachrückliste` (jeweils am
Zeilenanfang, Gross/Klein egal) und weist blosse Erwaehnungen mitten in der Zeile ab
(`  (4) NACHRUECKLISTE;`, `- Offen: Nachrueckliste B211 (…)`). Die Pflicht
`## NACHRUECKLISTE` in `prompts/reviewer.md` bleibt (klarere Gliederung), ist aber **keine**
Voraussetzung dafuer, dass (d) greifen kann.

## 4. Tests und Zustand

- `tests/test_r13ad_fixes.py` (neu): **30 Tests** — Kontextsumme/Verlauf/Kompaktierung,
  Summen ueber Fortsetzungen, `result.json` aus dem Attrappenlauf, Batch-Uhr mit Schwelle
  und Kontext, Hook im Unterprozess, je eine Probe fuer die Bedingungen (a)–(e) des
  Fortsetzungsanstosses, und die Erkennung des `NACHRUECKLISTE`-Abschnitts (vier Formen,
  Gegenproben, echter Text aus `runs/b213/review.md` und `runs/b211|b212/auftrag.md`).
- Volle Reihe: **768 Tests, OK** (512,6 s; vorher 742).

## 5. Was NICHT geprueft wurde

* **Kein echter `--resume`-Lauf mit dem Worker-Modell** (das kostet einen Batch). Belegt ist
  die Mechanik: dieselbe CLI-Flagge nutzt der Reviewer seit R13b (`--session-id` anlegen,
  `--resume` fortsetzen, `tests/test_r13b_fixes.py::test_fortsetzen_nutzt_resume`) und
  `/ask` ebenso; `claude --help` fuehrt `-r, --resume [value]  Resume a conversation by
  session ID`.
* **Kein Live-Test der Hook-Zeile** mit der neuen Umschaltschwelle (die Sonde aus R13ac
  bleibt der Beleg fuer die Ankunft beim Modell).
* Die Rueckblick-Tabelle zeigt `kontext_letzte_anfrage == kontext_max` in allen acht Batches
  (der Kontext waechst monoton) — der Maximalwert ist damit keine Zusatzinformation, bleibt
  aber als eigene Zahl stehen.
