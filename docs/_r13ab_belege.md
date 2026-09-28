# R13ab — Pflichtzeile `B-SCHRITT:`: warum sie fehlte, und was jetzt passiert

**Auftrag (Nutzerprüfung vor dem nächsten Review, 2026-09-28, vier Punkte):** die
Pflichtzeile fehlte in den Reviews B209/B210, obwohl beide nach dem Neustart mit R13w
liefen. Belegen, ob die Regel im tatsächlich verwendeten Prompt stand; wie
`prompts/reviewer.md` ankommt und ob ein geänderter Systemprompt bei `--resume` wirkt;
je nach Befund rotieren (erzwungen + automatisch per Hash); und `/fragen` trennen
(`ENTSCHIEDEN` → „zur Kenntnis").

Belege: `docs/_r13ab_probe.txt` (Messung), `tools/r13ab_probe_systemprompt.py` (Sonde),
`tests/test_r13ab_fixes.py` (17 Tests).

## 1. Stand die Regel im tatsächlich verwendeten Prompt? **Nein.**

Die beiden Reviews und ihre gesendeten Prompts:

| Review (Ordner) | bewertet | Prompt-Datei | geschrieben (UTC) |
|---|---|---|---|
| `runs/b209/review.md` | B208 | `logs/review-prompt-2026-09-28T172525+0000.md` | 17:25:25 → Review 17:27:14 |
| `runs/b210/review.md` | B209 | `logs/review-prompt-2026-09-28T181337+0000.md` | 18:13:37 → Review 18:14:58 |

Zuordnung ist belegt: der Prompt nennt „Naechster Batch laut Anker: 209 (Anker-Kopf nennt
BATCH 208)", und genau diese Zeile steht in `runs/b209/review.md`; für B210 ebenso
(`state.run.json` → `review.started_at = 2026-09-28T18:13:37+00:00`, `dir = runs/b210`).

In diesen Prompt-Dateien kommt `B-SCHRITT` **nur zitiert** vor — 8× bzw. 4×, und zwar in
Commit-Betreffen (`063d033 … B208: Werkzeug …`), in Ankerzeilen („**B209 = B-Schritt 2
Maschine**") und im Diff/der Historie. Die **Regel** steht in der Rollenanweisung
`prompts/reviewer.md` (Zeile 275 im Antwortgerüst, Zeile 287 „**In jedem B-Batch ist diese
Zeile Pflicht**", Zeile 290 der Wortlaut) — und die wird **nicht** in den Prompt
geschrieben, sondern als eigener Systemprompt übergeben.

## 2. Wie kommt `prompts/reviewer.md` an — und wirkt sie bei `--resume`? **Angehängt ja, gelesen nein.**

Der Harness hängt sie bei **jedem** Aufruf an (`hx/reviewer.py:118`, direkt vor der
Sitzungswahl in Zeile 120 `--resume` bzw. `--session-id`). Das ist auch beim Fortsetzen
so — es genügt aber nicht:

**Messung** (`tools/r13ab_probe_systemprompt.py`, Beleg `docs/_r13ab_probe.txt`, mit
demselben Modell und derselben Umgebung wie ein echter Review):

```
### 1) neue Session mit MARKER: PROBE-A      → Antwort: 'PROBE-A'
### 2) dieselbe Session per --resume,
       Datei auf MARKER: PROBE-B geaendert  → Antwort: 'PROBE-A'
Verdikt: Die geaenderte Datei kommt bei --resume NICHT an.
```

Die CLI liest `--append-system-prompt-file` in einer **laufenden** Session also nicht neu;
ein geänderter Systemprompt braucht eine **neue Session**.

**Warum es die Reviews B209/B210 traf** (die Zeitachse, alles belegt):

| Zeit (UTC) | Ereignis | Beleg |
|---|---|---|
| 2026-09-27 22:02:56 | Reviewer-**Session** `bdc3a357…` wird angelegt | `state/run.json` → `reviewer.started_at` |
| 2026-09-28 16:32:52 | **R13w** bringt die Pflichtzeile in `prompts/reviewer.md` | `git log -1 --format=%ci 1eee551` |
| 2026-09-28 16:46:33 | Harness startet neu → R13w-Code | `logs/harness-2026-09-28T164633+0000.log` |
| 2026-09-28 17:25:25 | Prompt des Reviews B209 | s. o. |
| 2026-09-28 18:13:37 | Prompt des Reviews B210 | s. o. |

Die Session war **18 Stunden älter** als die Regel. Der Reviewer hat sie also **nicht
ignoriert** — er konnte sie nicht kennen. Punkt 3 zweiter Halbsatz („`review_ok` soll als
unvollständig melden und nachfordern") greift damit **nicht** und wurde nicht gebaut.

## 3. Was jetzt gilt

**Automatische Rotation bei geändertem Systemprompt.** `reviewer.prompt_hash` (12 Hexzeichen
über `prompts/reviewer.md`); `state.reviewer_new_session` speichert den Hash der Fassung,
mit der die Session **angelegt** wurde; `orchestrator.do_review` vergleicht vor jedem Review
(`orchestrator.py:1560-1562`) und rotiert bei Abweichung (`:1576` ff.) mit Übergabe der alten
Session. Der Grund steht im Log und in Telegram:

```
Reviewer-Session wird gewechselt - Systemprompt geaendert (prompts/reviewer.md). Die alte Session uebergibt.
```

Eine Session aus einer **älteren** Fassung (wie die laufende) hat noch keinen Hash — sie
rotiert **einmal** („Systemprompt-Hash fehlt"), danach ist der Zustand vollständig und es
bleibt ruhig. **Für die laufende Instanz heißt das: der nächste Review rotiert von selbst.**

**Erzwingen ohne Prompt-Änderung:** `python -m hx.cli rotate` legt `state/ctl/rotate` ab
(nur der Harness schreibt den Zustand), `orchestrator._do_rotate` setzt
`reviewer.force_rotate`; das Flag wird beim nächsten Review verbraucht. Dasselbe Ziel hatte
bisher nur der Handgriff in `state/run.json` — das Flag wurde gelesen, aber **von nichts
gesetzt** (jetzt schon).

Die Tests dazu (`tests/test_r13ab_fixes.py`): Hash folgt dem Inhalt · Anhängen in **beiden**
Sitzungswegen · geänderter Prompt rotiert · gleicher Prompt rotiert nicht · Altbestand ohne
Hash rotiert genau einmal · `force_rotate` aus der Steuerdatei wird gesetzt und verbraucht ·
`rotate` ohne Session meldet das · Probe-Beleg vorhanden.

## 4. `/fragen`: zwei Listen

`ENTSCHIEDEN`-Zeilen des Reviewers sind keine Fragen an dich — er hat den Regelfall selbst
entschieden, du kannst nur ein Veto einlegen. Sie stehen jetzt unter

```
ZUR KENNTNIS (Veto per /claude <Kennung> moeglich)
```

Unter „OFFENE FRAGEN AN DICH" bleibt, was wirklich eine Entscheidung braucht: Ankerposten
(`A<n>`), Aussensicht-Befunde (`M…`, Empfänger du), verworfene Befunde (`M…-v<n>`) und die
Marker `ENTSCHEIDUNG NOETIG` / `OFFENE FRAGE` / `WARTET AUF LIVE-AUFNAHME`. Beide Listen sind
über die Kennung antwortbar (auch `/claude R209-4 Widerspruch: …`). `/status` zählt dieselben
Töpfe getrennt: `Fragen an dich: 4 offen, 2 zur Kenntnis (offen: …) (zur Kenntnis: R210-4, R210-5)`.

Am echten Stand (2026-09-28, `runs/b210/review.md`): die drei `ENTSCHIEDEN`-Zeilen
(`R209-1..3`) stehen unter „ZUR KENNTNIS"; im Abschnitt „OFFENE FRAGEN" stand zu diesem
Zeitpunkt keine (die Ankerposten und Aussensicht-Befunde waren über `/claude` beantwortet und
standen unter „BEANTWORTET, WARTET AUF REVIEW").

## Grenzen

- Die Sonde prüft **eine** CLI-Eigenschaft (Systemprompt bei `--resume`). Sie kostet zwei
  Mini-Aufrufe über das Abo; das Ergebnis ist zweimal reproduziert (`docs/_r13ab_probe.txt`
  ist der zweite Lauf, der erste stand wortgleich im Terminal).
- Der Hash-Vergleich greift erst, **nachdem** eine Session mit Hash angelegt wurde — die
  einmalige Rotation für die laufende Session ist gewollt, aber sie kostet eine Übergabe.
- `prompts/ask.md` und `prompts/aussensicht.md` sind nicht betroffen: die Aussensicht startet
  immer frisch, `/ask` beginnt bei `--neu` bzw. abgelaufener Chatgrenze neu.
