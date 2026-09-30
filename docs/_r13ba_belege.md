# R13ba — eine Rate „Köpfe je C-Batch": beide Grundmengen, Median ist die Rechengrundlage

**Auftrag (Nutzer, 2026-09-30).** „Durchsatzzeile angleichen (`hx/stand.py`, Außensicht
M221-5, Frage aus Review b222): Die Rate ‚Köpfe je C-Batch' wird nur über C-Batches mit
SOLL-KOEPFE > 0 gebildet, wie der Median. Ausgabe beider Werte mit Definition nebeneinander:
‚Median Zuwachs (Kopf-Batches): 6 | Mittel über alle C-Batches: 3,0'. Die Hochrechnung für
Paket E nutzt den Median. Test mit den echten Werten."

**Anlass (Aussensicht M221-5, Gewicht niedrig, Empfänger Reviewer).** Wortlaut im Register
(`harness/state/meta_befunde.json`, Eintrag `M221-5`): „Eingabe BILANZ (GESAMT) nennt
‚+3.0 je C-Batch … → 9 C-Batches' für Paket E; das Mittel enthält die Batches mit SOLL-KOEPFE
0. Eingabe PLAN/IST nennt dagegen ‚MEDIAN der 2 Zuwaechse … 6 Koepfe je C-Batch'."
Der Reviewer hatte geantwortet: „übernommen (beide Raten mit Definition in hybrid-plan)" —
also eine **Dokument**änderung; die Harness-Zeilen selbst nannten weiter zwei Zahlen. Der
Auftrag B222 (Decomp-Repo) führte den Punkt als `TEIL … (Review B222)`: „C-Rate-Abschnitt mit
beiden Raten nebeneinander" — der Reviewer hatte ihn an den **Worker** gegeben, nicht an den
Harness. Das ist die Lücke, die dieser Batch schließt.

## Was geändert wurde (`harness/hx/stand.py`)

| Stelle | vorher | jetzt |
|---|---|---|
| `rate_text` (`stand.py:432@HEAD`) | — | die Zeile selbst: `Median Zuwachs (Kopf-Batches): 6 \| Mittel ueber alle C-Batches: 3,0` (beide Grundmengen im Namen; Mittel mit Dezimalkomma) |
| `c_rate` (`stand.py:444@HEAD`) | — | **eine** Rechnung: Median über die Zuwächse der C-Batches mit `SOLL-KOEPFE > 0` (`plan_ist`) **und** Mittel über alle gemessenen C-Batch-Schritte (`c_trend().c_schritte`), dazu `rate` (= Median, Rückfall Mittel), `quelle` und `text` |
| `kalender_zeilen` (`stand.py:582@HEAD`) | rechnete mit `d['mittel_c_koepfe']` (3.0 → **9 C-Batches**) | rechnet mit `d['rate_c_koepfe']` (**Median** 6 → **4 C-Batches**); Rückfall auf das Mittel bleibt, wird aber in `(Grundlage: …)` benannt (`stand.py:596@HEAD`) |
| `durchsatz_zeilen` (`stand.py:1648@HEAD`) | hatte keine Rate-Zeile | holt die Rate selbst (`stand.py:1666@HEAD`) und schreibt sie als eigene Zeile: `C-Rate je C-Batch: …` (`stand.py:1736@HEAD`) — vor der Paket-E-Hochrechnung, die damit erklärt ist |
| `_relevanz_zeilen` (`stand.py:1836@HEAD`) | Mittel | Median (dieselbe Rate wie die Hochrechnungen) |
| `plan_ist_text` (`stand.py:2058@HEAD`) | eigener Median-Block | derselbe `c_rate`-Aufruf (`stand.py:2098@HEAD`); die Zeile `MEDIAN der N Zuwaechse …` bleibt wortgleich, darunter steht jetzt `(Median Zuwachs (Kopf-Batches): 6 \| Mittel ueber alle C-Batches: 3,0)` |

Die frühere Zeile `(Summen-Mittel derselben Batches, nur zur Einordnung: …)` ist **ersetzt**:
sie nannte einen dritten Wert (die **Summen** 85/90, keine Rate) und war genau die Sorte
Zahl, die M221-5 beanstandet hat.

## Beleg (gemessen, `docs/_r13ba_belege.txt`, Erzeuger `docs/_r13ba_belege.py`)

```
1) Die Rate (stand.c_rate)
  Median (Kopf-Batches)      : 6.0
  Mittel (alle C-Batches)    : 3.0
  gerechnet wird mit         : 6.0  (Median der Zuwaechse der Kopf-Batches (+5 (B219), +7 (B216)))
  Zeile                      : Median Zuwachs (Kopf-Batches): 6 | Mittel ueber alle C-Batches: 3,0
  Kopf-Batches (Batch, Zuwachs): [(219, 5), (216, 7)]
  C-Batch-Schritte der Preflight-Reihe (Delta je Schritt): +0, +0, +7, +5

2) Die Hochrechnung fuer Paket E: vorher (Mittel) und jetzt (Median)
  offener Paket-E-Vorrat: 26 Koepfe (aus der Messung)
  VORHER (Mittel): -> 9 C-Batches bei +3.0 Koepfe je C-Batch (Grundlage: Mittel ueber alle C-Batches …)
  NACHHER (Median): -> 4 C-Batches bei +6.0 Koepfe je C-Batch (Grundlage: Median der Zuwaechse der Kopf-Batches (+5 (B219), +7 (B216)))
```

Der Unterschied ist genau der des Befunds: **9 gegen 4** C-Batches für denselben Vorrat
(26 Köpfe). Die echten Ausgabezeilen stehen im Beleg unter 3), 4) und 6) — u. a.

```
                 C-Rate je C-Batch: Median Zuwachs (Kopf-Batches): 6 | Mittel ueber alle C-Batches: 3,0
                 HYPOTHESIS (Paket E, Arbeitsvorrat):
                   -> 4 C-Batches bei +6.0 Koepfe je C-Batch (Grundlage: Median der Zuwaechse der Kopf-Batches (+5 (B219), +7 (B216)))
```

Die PLAN/IST-Tafel (Zeile 3 der Tafel, unverändert im Wortlaut) und die Durchsatzzeile nennen
jetzt **dieselbe** Zahl (6) mit **derselben** Grundmenge; die zweite Zahl (3,0) steht mit ihrer
Definition daneben.

## Tests

* neu `harness/tests/test_r13ba_fixes.py` (20; im Nachtrag unten auf 31 erweitert): `rate_text` (echte Werte, Komma, „nicht
  gemessen"), `c_rate` (Median über die Kopf-Batches, Mittel über alle C-Batch-Schritte,
  `SOLL-KOEPFE: 0` zählt nicht mit, Rückfall auf das Mittel), die Hochrechnung mit Median
  (4 C-Batches) gegen den alten Mittel-Fall (9 C-Batches), `durchsatz_zeilen` und
  `bilanz.gesamt_block` mit der neuen Zeile — und die **echten Werte** gegen das Decomp-Repo
  (Median 6, Mittel 3.0, Text wortgleich; `skipTest`, wenn die Kopf-Batches weiterziehen).
* angepasst (Verhalten hat sich bewusst geändert): `test_r13ay_fixes.py` (die
  `Summen-Mittel`-Zeile ist durch die Rate-Zeile ersetzt), `test_r13ac_fixes.py` (gleiche
  Zeile im Median-Test).

## Nachtrag (30.09.2026): der Nebenbefund ist behoben

**Auftrag.** „Durchsatzzeile angleichen … Nachtrag zu R13ba, Nebenbefund Paket-E-Messung
(`hx/stand.py`, `paket_e_messung`): Auswahl der jüngsten Messdatei primär nach der
Batchnummer aus dem Ordnernamen (`_m<N>`), danach ‚nachher' vor ‚vorher'; Datum aus dem
Dateikopf nur noch als Anzeige und Gleichstand-Entscheider, nie als Hauptkriterium. Datum
tolerant lesen (Formate der B219- und B222-Dateien; im Kopf nachsehen, nicht raten). Fehlt
es: Datum = Änderungszeit, gekennzeichnet ‚(Datum aus Dateizeit)', und ein Hinweis in den
Review-Fakten ‚PARSER: Messdatum in `<Datei>` nicht erkannt'. Test mit den echten Dateien
`_m219/_c_paket_e_nachher.txt` und `_m222/_c_paket_e_vorher.txt`: gewählt wird `_m222`,
offen = 25, kein negativer Vorher-Vergleich. `test_r13ay_fixes::test_offener_vorrat_ist_26_nicht_38`
wieder auf eine eingefrorene Fixture stellen statt auf die lebenden Dateien."

### Was geändert wurde

| Stelle | vorher | jetzt |
|---|---|---|
| Auswahl (`stand.py:435@HEAD`) | `(datum, mtime, stand, name)` — ein **fehlendes** Datum sortierte als kleinstes, also hinter jede datierte Datei | `(batch, stand-Rang, datum, mtime, name)` mit Rang `nachher` (2) > bloße Messung (1) > `vorher` (0): **Batchnummer zuerst**, das Datum entscheidet nur innerhalb eines Batches |
| Datum (`paket_e_datum`, `stand.py:355@HEAD`) | nur `^# Messung: <Tag>` (Regex `RE_PAKET_E_MESSKOPF`, entfernt) | **zwei** Formen, nur im Kopf (erste `PAKET_E_KOPF_ZEILEN` = 15 Zeilen, `stand.py:345`/`:352`): `# Messung: 2026-09-30 03:33` (B219) und `… Datum 2026-09-30` (B222). Fehlt beides → **Dateizeit**, `datum_quelle="dateizeit"` |
| Anzeige (`paket_e_offen_text`, `stand.py:489@HEAD`) | „Datum aus der Aenderungszeit" | `gemessen B222, 2026-09-30 13:44 (Datum aus Dateizeit)` |
| Review-Fakten (`paket_e_datum_hinweis`, `stand.py:466@HEAD`; Aufruf `orchestrator.py:2370@HEAD`) | keine Zeile | `PARSER: Messdatum in _m222/_c_paket_e.txt nicht erkannt - es gilt die Dateizeit (…); gemessen B222, 25 Koepfe / 2011 Insn` — **nur** der Fehlerfall, damit die Fakten nicht bei jedem Lauf wachsen (der Erfolgsfall steht in der BILANZ-Zeile) |

### Beleg (Abschnitt 7 in `docs/_r13ba_belege.txt`)

```
  gewaehlt            : _m222/_c_paket_e.txt  (B222, 25 Koepfe / 2011 Insn, Dateiname-Rang stand='bloss')
  Datum               : '2026-09-30 13:44'  Quelle dateizeit  -> Anzeige '(Datum aus Dateizeit)'
  Vorher (anderer Wert): _m219/_c_paket_e_nachher.txt  (B219, 26 Koepfe)  -> Paar B219 -> B222
  gleicher Wert im selben Batch: _m222/_c_paket_e_vorher.txt
  Paket E offen: 25 Koepfe / 2011 Insn   [gemessen B222, 2026-09-30 13:44 (Datum aus Dateizeit): _m222/_c_paket_e.txt]   (B219 -> B222: 1 Koepfe / 103 Insn gebaut)
  Review-Fakten       : PARSER: Messdatum in _m222/_c_paket_e.txt nicht erkannt - es gilt die Dateizeit (2026-09-30 13:44); gemessen B222, 25 Koepfe / 2011 Insn
```

Vorher stand dort `Paket E offen: 26 Koepfe / 2114 Insn … (B222 -> B219: -1 Koepfe / -103 Insn
gebaut)` — falsche Zahl, verdrehtes Paar, negative „gebaut"-Zahl. Jetzt: **25** Koepfe,
Paar `B219 -> B222`, `+1 Koepfe / +103 Insn gebaut` (`bilanz.py:554@HEAD`; `dk = vor["koepfe"]
- messung["koepfe"]`).

Die Rate aus dem Hauptteil bleibt unberührt (Median 6 / Mittel 3,0 → `-> 4 C-Batches`, jetzt
über 25 statt 26 Köpfe gerechnet, unverändert 4).

### Tests

* `tests/test_r13ba_fixes.py` von 20 auf **31** erweitert: `paket_e_datum` (beide Formen, kein
  Datum, ein Datum **weit unten** zählt nicht), Batchnummer schlägt das Datum
  (`_m222` ohne Datum gegen `_m219` mit Datum), Rang `nachher` > bloß > `vorher` auch gegen ein
  späteres Datum, Datum als Gleichstand-Entscheider, kein verdrehtes Vorher-Paar
  (`(B219 -> B222: 1 Koepfe / 103 Insn gebaut)`, `(B222 -> B219` kommt nicht vor),
  PARSER-Hinweis nur bei fehlendem Datum, und **die echten Dateien** des Auftrags
  (`_m222` gewählt, 25/2011, Paar nicht verdreht, Hinweis + „(Datum aus Dateizeit)").
* `tests/test_r13ay_fixes.py`: die zwei Prüfungen gegen lebende Dateien
  (`test_offener_vorrat_ist_26_nicht_38`, `test_bilanz_zeigt_die_gemessene_zahl`) liegen jetzt
  in `TestOffenerVorratGefroren` auf einer **eingefrorenen Fixture** (Dokument sagt 38/2674,
  Messung 26/2114 → die Messung gewinnt). Der Live-Lauf hatte sich mit B222 selbst
  ungültig gemacht (B222 legt eigene Messdateien an); `test_median_der_echten_zuwaechse_ist_sechs`
  bleibt gegen die echten Preflight-Dateien.

