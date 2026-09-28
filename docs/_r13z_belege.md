# R13z — Aussensicht-Takt 3, Quote in `/bilanz`, zwei Pflichtabschnitte im Review

**Auftrag (Nutzer, 2026-09-28, nach Abnahme von R13y, drei Punkte):**

5. Aussensicht-Takt: `harness.toml` `[meta] every_batches` von 10 auf **3** (vorläufig;
   Begründung in `bedienung.md`; Auswertung nach einer Woche anhand der Quote
   „übernommen" im Register `state/meta_befunde.json`). `/bilanz` zeigt die Quote:
   `Aussensicht: n Befunde, davon u uebernommen, a abgelehnt, o offen`.
6. `prompts/reviewer.md`: Pflichtabschnitt `## VERALLGEMEINERUNG` vor der
   `DS_INSTRUCTION` (steht im `review.md`, **nicht** in der `TELEGRAM_SUMMARY`).
7. `prompts/reviewer.md`: jede „Offene Entscheidung" im Ankerkopf **muss** entscheidbar
   formuliert sein (Frage ja/nein **oder** A/B, Empfehlung, Folgen) — sonst zeigt
   `/fragen` sie als `UNKLAR FORMULIERT`; der nächste Review formuliert A1–A3 neu oder
   schließt sie.

Dazu: Tests, Doku, Commit.

## 5. Takt und Quote

**Takt.** `harness.toml`: `every_batches = 3` (Zeile und Begründungskommentar im Beleg
`docs/_r13z_belege.txt` §1). Dieselbe Zahl steht als Vorgabe in `hx/aussensicht.py`
(`STANDARD`), damit ein fehlender Schlüssel nicht still einen anderen Takt ergibt —
genau die Fehlerklasse aus Befund M208-3 (Vorhersage statt Messwert).

**Quote.** `aussensicht.quote` zählt das Register je Kennung, `aussensicht.zeile` baut
daraus eine Zeile; beide Anzeigen (`/bilanz`, `/status`) benutzen sie. Am **echten**
Register (nur lesend, `docs/_r13z_belege.txt` §2):

```
Eintrag M208-1   status=offen        antwort=
Eintrag M208-2   status=beantwortet  antwort=(Unicorn als unabhängige dritte Welt, …)
Eintrag M208-3   status=offen        antwort=
Eintrag M208-4   status=beantwortet  antwort=(Zensus nur über die Coverage-Adressen …)
Eintrag M208-5   status=offen        antwort=
quote(): {'gesamt': 5, 'uebernommen': 2, 'abgelehnt': 0, 'offen': 3}
aussensicht.zeile(): Aussensicht: 5 Befunde, davon 2 uebernommen, 0 abgelehnt, 3 offen
                     (letzte Aussensicht: Batch 208; 5 Befunde in diesem Lauf;
                      Takt: alle 3 Batches)
im echten /bilanz-Bericht (74 Zeilen): dieselbe Zeile
```

Zwei Dinge daran sind gemessen und wichtig:

- Die beiden „übernommen"-Verdikte des Reviewers stehen im Register als **`beantwortet`**
  — der laufende Harness hatte noch den alten Code, der `uebernommen` in `beantwortet`
  umschrieb. `klasse` zählt `beantwortet` weiter als **übernommen**, sonst würde die
  Quote mit dem ersten Tag falsch anfangen. **Neu** gespeicherte Verdikte tragen das Wort
  so, wie der Reviewer es geschrieben hat (`uebernommen`, `abgelehnt`, `erledigt`,
  `verworfen`) — belegt in `_r13z_belege.txt` §3 (`'übernommen'` → `status='uebernommen'`).
- Ein **unbekanntes** Statuswort zählt als **offen** (`Quatsch->offen` im Beleg). Vorher
  fiel ein solcher Befund aus der offenen Liste — eine unbeantwortete Frage wäre still
  verschwunden.

Kein Doppelpräfix mehr in `/status`: `orchestrator.meta_zeile` setzt dem Ergebnis der
Zeile kein zweites „Aussensicht:" voran (Test
`test_status_zeigt_die_zeile_genau_einmal`).

## 6. `## VERALLGEMEINERUNG`

Der Abschnitt steht im Antwortgerüst **zwischen** `</DS_TOOLS>` und `<DS_INSTRUCTION>`
(Beleg §5: `</DS_TOOLS>` Zeile 241 < `## VERALLGEMEINUNG` Zeile 243 < `<DS_INSTRUCTION>`
Zeile 248) und ist im Fließtext als Pflicht erläutert: je Befund (a) Fehlerklasse,
(b) verwandte Fälle **und wie die Instruktion sie mitprüft** (Prüfung beim Namen, nicht
„ich habe darauf geachtet"), (c) was die Instruktion ausdrücklich **NICHT** prüft.
Beispiel zu (b) aus dem Auftrag: F1 (`slw` mit vertauschten Feldern) → alle Formen mit
`rS` in Feld 6–10 und `rA` in Feld 11–15.

**Nicht** in der `TELEGRAM_SUMMARY` (Beleg §5: Prüfung des Gerüst-Blocks → `NEIN`), und
der Harness wertet ihn **nicht** maschinell aus: die Blockprüfung `review_ok` bleibt
unberührt, die Pflicht steht im Prompt. Ein Review ohne den Abschnitt ist unvollständig;
„nichts zu verallgemeinern" nur mit Begründung.

## 7. Entscheidbare Ankerposten (A1–A3)

Die drei echten Posten sind **nicht** entscheidbar (`_r13z_belege.txt` §4,
`entscheidbar=False` für A1, A2, A3) — `/fragen` zeigt sie mit Kennung, aber als
`UNKLAR FORMULIERT`. Der Reviewer-Prompt hält jetzt fest, dass jeder Posten die drei
Teile haben muss, nennt das Wort `GESCHLOSSEN` für erledigte Posten (sonst bleiben sie
für immer offen) und enthält die **Übergangsregel**: im nächsten Review A1–A3 neu
formulieren oder mit Begründung schließen.

Weil A/B-Fragen ausdrücklich erlaubt sind, konnte der Parser nicht bleiben, wie er war —
er hätte jede A/B-Fassung als `UNKLAR FORMULIERT` gemeldet. `stand.entscheidbar` nimmt
deshalb jetzt auch `Vorschlag: A` / `Empfehlung: B` und `bei A:` / `bei B:` an:

```
Fassung (ja/nein): Frage: Soll der Kontrollfluss/Supervisor als eigener Schritt ZWISCHEN
                   Maschine und kHeads in den B-Plan?
                   Empfehlung: ja | bei ja: eigener Schritt mit eigenem FERTIG WENN |
                                       bei nein: bleibt Teil der Maschine
Fassung (A/B):     Frage: Soll der Hybrid-Kern gegen den PPC-Kern unter `mame/` (A) oder
                   gegen eine Befehlstabelle der ISA (B) geprueft werden?
                   Empfehlung: A | bei A: Vergleich je Form | bei B: nur Stichproben
A/B ohne Empfehlung bleibt unklar: None
```

Beide Fassungen erscheinen in `/fragen` und im Anhang der `/claude`-Antwort
(`Empfehlung: A | bei A: … / bei B: …`, Tests `TestAnzeigeAlternativen`), und die Antwort
mit dem Buchstaben — `/claude A4 B` — wird wie jede andere Kennung angenommen (Anhang mit
Wortlaut). `Vorschlag: Abstand …` ist **keine** A/B-Empfehlung (Wortgrenze; eigener Test).

## Tests, Doku, Grenzen

- Neu: `harness/tests/test_r13z_fixes.py` (24 Tests: Klassen/Quote/Zeile, Takt aus der
  Konfiguration statt fester Zahl, `/bilanz` + `/status`, Prompt-Position und Inhalt,
  A/B-Parser und Anzeige). Angepasst: `test_r13w_fixes` (Takt-Test liest die Zahl jetzt
  aus `[meta]`; Statuswort) und `test_r13y_fixes` (Statuswort). Volle Reihe: **612 Tests
  OK**.
- `docs/bedienung.md`: §12e Takt-Begründung + Auswertungstabelle („Übernahmequote"), neue
  Zeile der Quote; §10d der Pflichtabschnitt; §16a die erweiterte Regel „wie eine Frage
  entscheidbar wird".
- **Grenzen:** Die Quote ist keine Erfolgsmessung (ein „übernommen" heißt nicht, dass der
  Befund gewirkt hat); sie zählt je Kennung, also zählt ein geteilter Befund
  (`M208-5a`/`M208-5b`) zweimal. Der Takt 3 ist **vorläufig** — die Zahl steht in
  `harness.toml`, die Doku nennt die Bedingung, und der Test
  `TestTakt.test_takt_ist_drei` ist die Stelle, die bei einer Änderung mitgeht.
