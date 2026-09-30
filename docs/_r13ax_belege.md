# R13ax-Belege (2026-09-30): kein Fortsetzungsanstoss nach einem Preflight (M219-5)

Auftrag (Aussensicht B219, Befund 5, Gewicht mittel): hat der Worker im Batch schon einen
Preflight gestartet (`streamjson.ist_preflight_aufruf`), gibt es **keinen** Anstoss mehr;
Log und Review-Fakten nennen
`Kein Fortsetzungsanstoss: Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG`.
Die Archivierung „Preflight vor Fortsetzung" entfällt praktisch — der Code bleibt, die
Tests werden angepasst; `prompts/reviewer.md` bekommt einen Hinweis.

## 1. Der Befund

`port-batch219-…md:203-206`: Preflight bei 60 von 75 min, obwohl NACHRUECKLISTE 1 offen war.
Weitere Fälle: B217 mit **zweitem** Preflight in der Fortsetzung (`981a8bd`, der erste Lauf
liegt als `_m217/_preflight_217_vor_fortsetzung1.txt`), B218 mit **drei** Preflights, B219
mit abgebrochener Fortsetzung. Drei Vorgaben stiessen zusammen: „nach dem Preflight kein
`port/`", „Preflight erst nach der Nachrueckliste" und die automatische Fortsetzung.

## 2. Die Regel

In `worker.fortsetzung_pruefen` als **letzte** Bedingung (nach dem `NACHRUECKLISTE`-Test,
damit der Grund eindeutig ist):

```
    if preflight_gestartet(stats):
        return {"ja": False, "grund": UEBERTRAG_GRUND, "uebertrag": True}
```

* `worker.preflight_gestartet(stats)` prüft **jeden** Werkzeugaufruf mit
  `streamjson.ist_preflight_aufruf` — dieselbe Definition wie der Preflight-Zähler (R13ao):
  nur ein **Start** zählt; eine blosse Nennung in `description`, ein `Select-String`-Filter
  oder ein `Read` der Preflight-Datei zählt nicht.
* `UEBERTRAG_GRUND = "Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG"`,
  `UEBERTRAG_TEXT = "Kein Fortsetzungsanstoss: " + UEBERTRAG_GRUND`.
* Im Lauf: `log.info(UEBERTRAG_TEXT)`; `res.fortsetzung_grund` / `res.fortsetzung_uebertrag`
  gehen nach `result.json` (oben **und** in `stats`, damit die Anzeige sie liest).
* Review-Fakten (`orchestrator.fortsetzungen_zeile`): an die Fortsetzungszeile wird
  `| Kein Fortsetzungsanstoss: Preflight bereits gelaufen, offene Nachrueckliste -> UEBERTRAG`
  angehängt — auch wenn es vorher schon Anstösse gab (`#1 bei 42 min (…) | Kein …`). Bei
  anderen Gründen steht dort `kein weiterer Anstoss: <grund>`.
* `prompts/reviewer.md` (Abschnitt „Fortsetzung und Preflight"): die Regel ist als
  **vorgesehene Übergabe** beschrieben — kein Regelverstoss, kein Abbruch; geprüft wird, ob
  die übertragenen Posten im nächsten Auftrag/Anker wieder auftauchen. Eine
  `NACHRUECKLISTE` bleibt Pflicht (sie greift bei einem **frühen** Ende ohne Preflight).

## 3. Die Archivierung bleibt

`worker.archiviere_preflight_vor_fortsetzung` (R13ah) wird durch die neue Regel praktisch
nie mehr erreicht — der Aufruf im Fortsetzungszweig bleibt als Sicherung stehen und ist dort
mit einem Kommentar versehen. Die R13ah-Tests (`tests/test_r13ah_fixes.py`, 8 Stück) laufen
unverändert weiter, weil die Funktion selbst unangetastet ist.

## 4. Tests

`harness/tests/test_r13ax_fixes.py` — **15 Tests**:

* `preflight_gestartet`: echter Start (beide Schreibweisen), blosse Nennung, Filter,
  `Read`, ohne Aufrufe/`None`;
* `fortsetzung_pruefen`: ohne Preflight wird angestossen; nach Preflight
  `{"ja": False, "grund": UEBERTRAG_GRUND, "uebertrag": True}`; Wortlaut festgeschrieben;
  **andere** Gründe tragen kein `uebertrag`-Merkmal; ein Abbruch bleibt ein Abbruch;
  `run_batch` loggt den Satz und setzt das Merkmal (Quelltext-Prüfung);
* `result.json` trägt `fortsetzung_grund`/`fortsetzung_uebertrag`; `harness-facts.md` zeigt
  den Satz; ohne Übertrag steht die alte Form; die Zeile hängt den Grund an bestehende
  Anstösse an.

## 5. Offen

* Der laufende Harness (Stand: `IDLE`, B219 beendet) hat die Regel erst nach einem Neustart.
* Die Aussensicht-Kennzahl „übernommen/wirksam" (zweite Hälfte der Empfehlung) ist **nicht**
  Teil dieses Auftrags und bleibt offen.
