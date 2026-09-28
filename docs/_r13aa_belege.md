# R13aa — Strang-Klassifikation, verworfene Befunde, getrennte Hochrechnung

**Auftrag (Nutzer, 2026-09-28, drei Punkte aus `runs/meta-209.md`):**

1. **Fehlauslöser:** „Kernzahl ohne Bewegung" hat B208/B209 als C-Batches gezählt; beide
   waren B-Batches. Die Pflichtzeile `B-SCHRITT:` fehlte (auch im B210-Review). Die
   Klassifikation darf **nicht allein** an der Reviewer-Zeile hängen: zusätzlich
   `DS_INSTRUCTION` („Strang B", „B-Batch") und `hybrid-plan.md`. Fehlt die Pflichtzeile,
   im Review-Protokoll warnen. Test mit den echten Reviews B207–B210.
2. **Beleg-Regel:** M209-4 wurde verworfen, obwohl die Zahlen aus den Eingabedaten stammen
   (Laufzeiten je Batch). Auch `Eingabe <Abschnitt>` bzw. `runs/b<N>/result.json` gelten
   lassen; verworfene Befunde **nicht wegwerfen**, sondern in `/fragen` als
   „verworfen — prüfen?" zeigen.
3. **Hochrechnung:** getrennt ausweisen — Durchsatz je C-Batch, Anteil C-Batches
   (Mischverhältnis), daraus Kalender-Batches.

Beleg: `docs/_r13aa_belege.txt` (echte Dateien, nur lesend; Beispiele in einem
Wegwerf-Baum). Tests: `tests/test_r13aa_fixes.py` (33), volle Reihe **645 Tests OK**.

## 1. Welcher Batch ist ein B-Batch?

Der Fehler ist am echten Anlass nachlesbar — `runs/meta-209.md`:

```
- Anlass: Kernzahl ohne Bewegung ueber die letzten C-Batches: C Koepfe = 78 (B208 wie B209); …
```

`ist_b_batch` hing allein an der Pflichtzeile `B-SCHRITT:` im Review des Batches. Gemessen
(`_r13aa_belege.txt` §1): **kein** Review B205–B210 trägt diese Zeile — also war jeder
Batch ein „C-Batch", und die C-Zahl *musste* in einem B-Batch stehenbleiben.

Neu: `stand.strang_von_batch` liest vier Quellen, in dieser Reihenfolge (die erste, die
etwas sagt, gewinnt; die Quelle wird mitgeliefert):

| Quelle | Am echten Beleg |
|---|---|
| Pflichtzeile im Review, das den Batch bewertet hat | (fehlt bisher überall) |
| Marker im Auftrag, der **diesen** Batch nennt | `runs/b208/auftrag.md`: „B208 ist der ERSTE Batch von Strang B" → **B**; `runs/b210/auftrag.md`: „B210 ist ein C-Batch" → **C** |
| Zeile mit dem Strang am Zeilenanfang im Auftrag | `runs/b209/auftrag.md`: „Strang B, Batch 2 von hoechstens 20" → **B** |
| Zeile `Mischverhaeltnis …` in `analysis/hybrid-plan.md` | `… 2 B : 1 C … : B208 B, B209 B, B210 C` |

Ergebnis (echt gemessen): B206/B207 **unbekannt** → zählen wie bisher als C, B208 **B**,
B209 **B**, B210 **C**, B211 unbekannt. Fremde Erwähnungen zählen nicht: der B209-Auftrag
enthält „B210 = C-Batch" — das macht B209 nicht zum C-Batch (eigener Test).

**Wirkung am echten Stand:** der Stillstands-Auslöser meldet jetzt **nur C-Batches** — kurz
nach dem Einbau `C Koepfe = 78 (B206 wie B207)`, im Beleg §1 der jeweils aktuelle Stand
(nach B210: `(B207 wie B210)`; B208/B209 sind als B-Batches ausgelassen).

**Warnung im Review-Protokoll.** `stand.pflichtzeile_hinweis` sagt dem Reviewer, was
dieser Review über den Strang schreiben **muss**; der Block
`=== PROTOKOLL-WARNUNG (Pflichtzeilen im Review) ===` steht im Review-Prompt
(`reviewer.build_prompt`), und beim Review wird es ins Protokoll geschrieben
(`orchestrator.pflichtzeile_melden`: B-Batch → `log.warn`, C-Batch → `log.info`,
unbekannt → Info). Am echten Stand:

```
B210 ist ein C-Batch (Auftrag runs/b<N>/auftrag.md). In DEINER TELEGRAM_SUMMARY gehoert die
Zeile `B-SCHRITT: kein B-Batch (Strang C)`. In den letzten Reviews fehlte sie in: B208, B209.
```

## 2. Beleg-Regel und verworfene Befunde

Der echte M209-4 (`runs/meta-209.json` → `verworfen`):

```
aussage: Das vorzeitige Ende wiederholt sich auch nach der Get-Date-/70-min-Regel (B208, B209) …
beleg  : Laufzeiten aus den Kosten und Laufzeiten je Batch: B201 18,1 min, B202 25,2 min,
         B208 19,3 min, B209 28,0 min … Entscheidung aus dem Review in `runs/b206`
-> beleg_gueltig: True
```

`beleg_gueltig` nimmt jetzt zusätzlich an: `Eingabe <Abschnitt>`, `=== <EINGABEBLOCK> ===`,
`runs/b209`, `runs/b209/result.json`. Die alten Formen bleiben, ein Bauchgefühl bleibt
ungültig (alles im Beleg §2 mit `True`/`False` je Form).

**Nicht wegwerfen.** `bericht_schreiben` legt verworfene Befunde über
`verworfene_speichern` als zweite Liste in `state/meta_befunde.json` (`"verworfen"`) ab,
mit eigener Kennung `M209-v1` (eigene Form, weil die Nummern der angenommenen Befunde beim
Verteilen nach Gewicht neu vergeben werden — sonst gäbe es doppelte Kennungen). Ein
Register-Schreibvorgang **ohne** `verworfen` löscht die Liste nicht (Test).

`/fragen` zeigt sie (Beleg §3):

```
  M209-v1   AUSSENSICHT (verworfen - pruefen?): Das vorzeitige Ende wiederholt sich auch nach
            der Get-Date-/70-min-Regel (B208, B209). Das ist ein Vorgehensproblem: …
            Empfehlung: Die Auftraege der B-Batches sollten eine geordnete Nachrueckliste …
            Beleg: nicht anerkannt: Laufzeiten aus den Kosten und Laufzeiten je Batch: …
            Quelle: runs/meta-209.md (Rohantwort dort)
ANTWORTEN: /claude <Kennung> <Text>   (z. B. "/claude M209-v1 ja" - …)
```

`/claude M209-v1 pruefen` wird angenommen (`ids_am_anfang` kennt die `-v`-Form), der Anhang
trägt Wortlaut, Empfehlung, den **nicht anerkannten** Beleg und den Zeiger auf die
Rohantwort (`Quelle:` — neu im Anhang). Gezeigt wird der **neueste** Lauf; das Register
behält alle. Die Quote (§12e) zählt sie **nicht** mit (Beleg §3: `gesamt: 0`).

## 3. Hochrechnung getrennt

Der Befund M209-3 nannte: „Die Hochrechnung ‚369 Batches bei +3,8' stützt sich auf ein
Fenster (B204 bis B208), das diesen Stillstand nicht enthält." Am echten Stand jetzt (Beleg
§4):

```
  Durchsatz    : Koepfe (R207 gebaut) letzter Batch 208: 686 -> 686 (+0)
                 Mittel der letzten 5 (B+C gemischt): +3.8 Koepfe je Batch   (Fenster: …)
                 nur C-Batches: +4.8 Koepfe je C-Batch (4 von 5: B207, B206, B205, B204)
  Mischung     : 4 C von 5 Batches im Fenster (80 %); Regel hybrid-plan.md: "2 B : 1 C"
                 -> jeder 3. Batch ist ein C-Batch (33 %)
                 HYPOTHESIS (C gesamt, GEMESSEN): offen 1403 Koepfe / 53535 Insn …
                   -> 295 C-Batches bei +4.8 Koepfe je C-Batch (C-Batches im Fenster: …)
                   -> ca. 886 KALENDER-Batches (295 C-Batches / Anteil 33 % = Regel …)
```

Drei Dinge sind daran wichtig: das gemischte Mittel (+3,8) steht **gekennzeichnet** als
„B+C gemischt" und wird für die Rechnung **nicht** mehr benutzt; gerechnet wird mit dem
Durchsatz **je C-Batch** (+4,8); und das Ergebnis steht in **zwei** Schritten da
(295 C-Batches → 886 Kalender-Batches), damit die Annahme (jeder 3. Batch ist C) sichtbar
bleibt. Die drei Vorratsklassen rechnen ebenfalls in C-Batches
(`-> ca. N C-Batches`). Fehlt der Anteil, steht „nicht rechenbar" statt einer Zahl.

## Grenzen

- Die Klassifikation ist belegbasiert, nicht vollständig: **unbekannt** bleibt unbekannt und
  zählt als C-Batch (die vorsichtige Seite). Für B206/B207 gibt es keinen Beleg — sie
  zählen also als C-Batches, obwohl sie es sind. Das ist gewollt (nichts raten) und ändert
  das Ergebnis nicht, weil beide in dieselbe Richtung zeigen.
- Die Kalender-Rechnung nimmt die **Regel** aus `hybrid-plan.md`, wenn es sie gibt — sie
  beschreibt die Zukunft, während im Fenster noch reine C-Batches liegen (dort 80 %).
  Beide Zahlen stehen deshalb nebeneinander.
- Die verworfenen Befunde sind **keine** Registerbefunde: sie haben keine Zustandsführung
  außer „gezeigt/beantwortet" über die Queue. Wer einen retten will, antwortet per
  `/claude M209-v1 …`; die nächste Aussensicht prüft ihn dann mit einer anerkannten
  Belegform erneut.
