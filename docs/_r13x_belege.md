# R13x — Aussensicht-Befund M208-3 abgearbeitet (2026-09-28)

**Anlass.** Die Aussensicht (`runs/meta-208.md`, Befund 3, Gewicht *mittel*, Empfänger
Nutzer) meldete vier Stellen, an denen die Harness-Aufbereitung **keine Messwerte**
weiterträgt:

| # | Befund | Ursache (Datei:Zeile) | Behebung |
|---|---|---|---|
| a | Bilanz zeigt `C verifiziert: 78 Koepfe / 1872 Faelle (+5/+120 in diesem Batch)` statt `78 / 2903` aus B207/B208 | `hx/stand.py`: `_RE_CKOPF` schnitt die **erste** passende Tabellenzeile heraus — das ist die **Vorhersagetafel** (§5). B207 schreibt das Etikett in Backticks (``` **`C Koepfe`** ```), B208 fett in **beiden** Spalten; beide fielen durch das Muster, die Anzeige rutschte still auf das Dokument von **B206** (78/1872, Vorhersage +5/+120) | `C Koepfe` kommt aus der **Preflight-Zeile** `analysis/_preflight_<N>.txt` (maschinengeschrieben); Rückfall: **Ist-Spalte** der Soll/Ist-Tafel (`stand.ist_wert`) |
| b | `Paket E offen … (Bl 15 / 1083)` = Vorhersagespalte von B206 statt gemessen `Bl 17 / 1202` | dieselbe Stelle: `_RE_PAKET_TAB` verlangte die alte Schreibweise `43 Koepfe / 3025 Insn (Bl 20 / 1434)` und ein `**` vor der zweiten Spalte — B208 §6 schreibt `38 / 2674 (Bl 17 / 1202)` ohne Einheit und ohne Fettung | derselbe neue Zeilen-Leser; Paket E hat **keine** Preflight-Zeile, also ist die Ist-Spalte des Dokuments die Messquelle |
| c | Laufzeitspalte der PLAN/IST-Tafel um einen Batch verschoben (B208 zeigt `47m26s` = b207) | `hx/stand.py:646` (alt) las `runs/b<N>/harness-facts.md`. Diese Datei schreibt `orchestrator.review` mit `ziel=rdir` = `runs/b<expected_batch>` — also in den Ordner des **nächsten** Batches. `runs/b<N>/harness-facts.md` gehört damit zu **b<N−1>** | Laufzeit/Abbruch aus `runs/b<N>/result.json` (der Lauf schreibt sie in seinen **eigenen** Ordner); Rückfall nur `runs/b<N+1>/harness-facts.md` **mit** passender Kopfzeile `- Review: bewertet wird Batch N` |
| d | `/status`: `letzter Batch 207: $0.0903` (richtig `$0.1727`) | `orchestrator.live_batch_zeile` zeigte die letzten **Live**-Zahlen. Die enthalten die **Ausgabe-Tokens nicht**: DeepSeek trägt Eingabe/Cache in den `assistant`-Ereignissen exakt ein, die Ausgabe erst im abschließenden `result`-Ereignis (`streamjson.StreamStats.output_total`) — während des Laufs sind alle `output` = 0 | fertiger Batch: Zeile aus `runs/b<N>/result.json` (Dauer, Kosten, Anfragen, Ausgabe-Tokens); laufender Batch: ausdrücklicher Vermerk „OHNE Ausgabe-Tokens" |

## 1. Belege (echte Dateien, B206–B208)

`docs/_r13x_belege_vorher.txt` — der Zustand **vor** der Änderung (mit der echten Konfiguration
und den echten Dateien aufgerufen):

```
C verifiziert: 78 Koepfe / 1872 Faelle / 0 Abweichungen   (+5 Koepfe / +120 Faelle in diesem Batch)
Paket E offen: 38 Koepfe / 2674 Insn (Bl 15 / 1083)   (in diesem Batch: 5 Koepfe / 351 Insn gebaut)
B208 | ? Koepfe | +0 Koepfe / +None Insn | 47m26s | kein Abbruch        <- b207 !
B207 | ? Koepfe | +0 Koepfe / +None Insn | 58m01s | kein Abbruch        <- b206 !
```

`docs/_r13x_belege_nachher.txt` — derselbe Aufruf **nach** der Änderung (hier bereits mit
B209 als letztem fertigen Batch; die B208-Zeilen stimmen mit dem Vorher-Beleg überein):

```
C verifiziert: 78 Koepfe / 2903 Faelle / 0 Abweichungen   (+0 Koepfe / +0 Faelle (B208 -> B209))   [B209, _preflight_209.txt]
Paket E offen: 38 Koepfe / 2674 Insn (Bl 17 / 1202)   ((B207 -> B208): 0 Koepfe / 0 Insn gebaut)   [Ist-Spalte port-batch208-hybrid-kern-2026-09-28.md]
B208 | … | 19m20s | kein Abbruch
B207 | … | 47m26s
B206 | … | 58m01s
B205 | … | 38m35s
/status = Laufender Batch: keiner (letzter Batch 209: 28m00s, $0.2149, 172 Anfragen, 163753
          Ausgabe-Tokens, fertig 20:13 - aus runs/b209/result.json)
```

Frischer Beleg zu (d) an B209 (`runs/b209/result.json`: `cost_usd` 0.214913, `output`
163753, `duration_s` 1680,348) gegen die Live-Zahl aus `state/run.json`
(`live_letzte`: `cost_usd` 0,114786, `output` 0): der Abstand ist genau die Ausgabe
(163753 × $0,60/1M = $0,0983). Vor der Änderung hätte `/status` `$0.1148` gezeigt.

Gegenprobe zu (d) — dieselbe Rechnung mit `hx.pricing`:

```
b207: ohne Ausgabe $0.090280 | mit Ausgabe $0.172692      <- die Live-Zahl war $0.0903
b208: ohne Ausgabe $0.051956 | mit Ausgabe $0.123228      <- die Live-Zahl war $0.0512
```

Die gemeldete Live-Zahl ist also **exakt** die Kostenrechnung ohne Ausgabe-Tokens.

### 1a. Der Nachweis der Verschiebung (c), gemessen an den Kopfzeilen

```
runs/b205/harness-facts.md : "- Review: bewertet wird Batch 204" … Laufzeit: 47m33s
runs/b206/harness-facts.md : "- Review: bewertet wird Batch 205" … Laufzeit: 38m35s
runs/b207/harness-facts.md : "- Review: bewertet wird Batch 206" … Laufzeit: 58m01s
runs/b208/harness-facts.md : "- Review: bewertet wird Batch 207" … Laufzeit: 47m26s
runs/b209/harness-facts.md : "- Review: bewertet wird Batch 208" … Laufzeit: 19m20s
runs/b208/result.json      : duration_s 1160.907  (= 19m20s, die ECHTE Zeit von b208)
```

Jede `harness-facts.md` trägt die Zahlen des **Vorgängerbatches** — genau die Verwechslung,
die die Laufzeitspalte verschoben hat.

## 2. Die neue Lese-Regel, gegen alle Dokumente geprüft

`docs/_r13x_belege_reihe.txt` (erzeugt mit den **echten** Funktionen `stand.c_zahlen`,
`stand.preflight_c_koepfe`, `stand.kernzahlen`, `stand.lauf_ist`):

```
Batch | Dokument-Ist | Preflight | genommen | Quelle                       | Laufzeit
  198 | 17/408       | 17/408    | 17/408   | _preflight_198.txt           | 55m31s
  199 | 45/1080      | 45/1080   | 45/1080  | _preflight_199.txt           | 1h46m50s
  200 | 45/1080      | 45/1080   | 45/1080  | _preflight_200.txt           | 52m47s
  201 | 45/1080      | 45/1080   | 45/1080  | _preflight_201.txt           | 18m03s
  202 | 53/1272      | 45/1080   | 45/1080  | _preflight_202.txt           | 25m12s   <- Dokument falsch
  203 | 53/1272      | 59/1416   | 59/1416  | _preflight_203.txt           | 39m55s   <- Dokument falsch
  204 | 64/1536      | 64/1536   | 64/1536  | _preflight_204.txt           | 47m33s
  205 | 73/1752      | 73/1752   | 73/1752  | _preflight_205.txt           | 38m35s
  206 | 78/1872      | 78/1872   | 78/1872  | _preflight_206.txt           | 58m01s
  207 | 78/2903      | 78/2903   | 78/2903  | _preflight_207.txt           | 47m26s
  208 | 78/2903      | 78/2903   | 78/2903  | _preflight_208.txt           | 19m20s
```

Bemerkenswert: für **B202/B203** widerspricht das Batch-Dokument der maschinengeschriebenen
Preflight-Zeile (53/1272 gegen 45/1080 bzw. 59/1416) — das ist der zweite Grund, die
Preflight-Zeile zu nehmen und nicht die Dokument-Prosa. Eine Preflight-Zeile `C Koepfe`
gibt es ab B198 (vorher, B155..B197, existierte der C-Strang nicht); dort greift der
Rückfall auf die Ist-Spalte.

Paket E (Ist-Spalte, Belegdatei ebenda):

```
B205: 43 Koepfe / 3025 Insn (Bl 20 / 1434)
B206: 38 Koepfe / 2674 Insn (Bl 17 / 1202)   gebaut: 351 Insn
B207: 38 Koepfe / 2674 Insn (Bl 17 / 1202)   gebaut: 0 Insn     (Zeile 139: nur die Vorhersagetafel)
B208: 38 Koepfe / 2674 Insn (Bl 17 / 1202)   gebaut: 0 Insn     (Zeile 214 = Soll/Ist-Tafel)
```

Die B205-Werte stimmen mit der „Vorbatch"-Spalte des B206-Dokuments überein
(`43 Koepfe / 3025 Insn (Bl 20 / 1434)`) — der Leser trifft also den gemessenen Stand.

## 3. Was jetzt wo steht

| Ort | Datei | Zeile/Quelle |
|---|---|---|
| `C Koepfe` (Bilanz, Änderungsblock, Aussensicht-Kernzahlen) | `analysis/_preflight_<N>.txt` → `stand.preflight_c_koepfe` | Zeile `C Koepfe` der neuesten gültigen Preflight-Datei |
| `Paket E offen` / Insn je Batch | `analysis/port-batch<N>-*.md`, **Ist-Spalte** | `stand.ist_wert` bzw. `stand._zahlen_aus_text` |
| Delta-Beschriftung | `bilanz._delta_batch` | `(B207 -> B208)`; bei Lücken `vorher_batch` (Paket E: B206 → B208) |
| Laufzeit/Abbruch (PLAN/IST) | `runs/b<N>/result.json` | `stand.lauf_ist`, Rückfall mit `*` markiert |
| `/status`, letzter Batch | `runs/b<N>/result.json` | `orchestrator.letzter_batch_zeile` |
| Aussensicht-Stichproben | Hinweis korrigiert | `harness-facts.md` gehört zu **N−1** |

Nebenbei mitgenommen (dieselbe Fehlerklasse, beim Bauen an B209 aufgefallen): ein **gerade
laufender** Batch schreibt sein Dokument, bevor er eine Preflight-Zeile hat — dort steht dann
gar keine `C Koepfe`-Zahl (B209: `| C Koepfe | KOPF_DEF-Eintraege | unveraendert 78/2903 |
78/2903 |`). Die Anzeige nimmt deshalb je Zeile den **neuesten Eintrag MIT Wert**
(`bilanz._letzter_mit`) und nennt den Batch in der Zeile (`[B208, _preflight_208.txt]`),
statt die Zeile stillschweigend zu streichen; fehlt die Prosa für Bau-Liste/Vorrat, steht
das ausdrücklich in der Quellenzeile.

## 4. Tests

`harness/tests/test_r13x_fixes.py` (neu, 32 Tests) — zwei Sorten:

* **echte Belege** (B202/B203 + B206–B208 aus `g:/Silent Scope Decomp`, nur lesend; fehlen
  sie, wird die Klasse übersprungen): Ist-Spalte liefert 78/2903 bzw. `Bl 17 / 1202`; die
  Preflight-Zeile schlägt das Dokument (B202 45/1080, B203 59/1416); `bilanz.gesamt_block`
  nennt Quelle und Vergleichsbatch; die PLAN/IST-Tafel zeigt für B208 `19m20s` (und **nicht**
  mehr `47m26s`); die `harness-facts.md` im Nachbarordner ist belegt die des Vorgängers; die
  `/status`-Zeile kommt aus `result.json`.
  Geprüft wird eine **eingefrorene Kopie** unter `tests/_tmp_r13x_echt` — der laufende
  Harness schreibt ständig neue Dokumente und Preflight-Zeilen; ein Test auf „das Neueste"
  war beim ersten Anlauf rot, weil B209 mitten in der Testreihe sein Dokument schrieb.
* **Attrappen** (eigener Temp-Baum): letzte Zeile gewinnt, Prosa-Spalte wird nicht als Wert
  gelesen, Backticks/fette Zellen stören nicht, Vorhersagetafel ≠ Messwert, Preflight
  schlägt Dokument, Lücke in der Reihe (`vorher_batch`), ein noch laufender Batch ohne
  Zahlen streicht die Zeile nicht, Rückfall nur mit passender Kopfzeile, Live-Zahlen mit
  Warnung statt falscher Kosten.

`harness/tests/test_r13s_fixes.py` wurde mitgezogen: die Dokument-Attrappe hat jetzt **beide**
Tafeln (§5 Vorhersage + §6 Soll/Ist), `lauf()` schreibt `result.json` in den eigenen Ordner
**und** die Fakten-Datei in den nächsten (wie der Harness), `preflight()` ist neu.

Volle Reihe: **560 Tests OK** (528 vorher + 32 neue; die zwei angepassten zählen nicht neu).

## 5. Grenzen

* `c_zahlen` (Dokument-Only) bleibt erhalten und wird weiter von Funktionen benutzt, die den
  Dokumentwert brauchen; die **Anzeige** liest `kernzahlen`. Beide Wege sind mechanisch
  getestet.
* Fehlt für einen Batch die Preflight-Zeile **und** eine Ist-Spalte, steht dort weiter
  „nicht ermittelbar" — es wird nichts geschätzt.
* Der Rückfall auf `runs/b<N+1>/harness-facts.md` bleibt nötig für Läufe, deren
  `result.json` fehlt (z. B. nach einem Harness-Neustart mitten im Batch); er wird in der
  Tafel mit `*` und darunter namentlich ausgewiesen.
