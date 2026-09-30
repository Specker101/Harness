# R13at-Belege (2026-09-30): Zuglimit 70 und Frist ab Limit − 8

Auftrag Teil B: `meta_max_turns` auf 70, Zuguhr-Hook mit dem Abstand 8 statt 5, Frühwarnung
über 80 % — „nur berichten": wie passt `meta-214` mit 35 Zügen bei Limit 30 zusammen?

**Wichtig vorab:** Punkt 2 (Hook) und Punkt 3 (Frühwarnung) sind **schon gebaut** — in
R13ar, Commit `84c3197` (`tools/aussensicht_uhr.py`, `aussensicht.write_hook_settings`,
`aussensicht.limit_hinweis`, Bericht/JSON/Telegram). Dieser Batch bringt den **Unterschied**:
das Limit (50 → 70) und den **Frist-Abstand** (5 → 8, eine Quelle:
`aussensicht.FRIST_ABSTAND`, der Prompt und der Hook lesen dieselbe Zahl). Der Hook-Beweis
mit echtem Lauf steht in `docs/_r13ar_probe_hook.txt`.

## 1. Die Zahl im Auftrag ist `num_turns`, nicht die Zahl der CLI (gemessen)

Der Auftrag nennt „41 von 50 Zügen (82 %)" für die Wiederholung meta-218. Nachgemessen
(`docs/_r13at_messung.txt`) — `num_turns` und Runden, beide Quellen (Mitschnitt und
Sitzungs-Transcript):

| Lauf | rc | `num_turns` | Werkzeugrunden | Aufrufe | Limit | Anteil am Limit |
|---|---|---|---|---|---|---|
| meta-208 | 0 | 28 | 18 | 27 | 30 | 60 % |
| meta-209 | 0 | 17 | 10 | 15 | 30 | 33 % |
| meta-210 | 0 | 26 | 19 | 25 | 30 | 63 % |
| meta-211 | 0 | 25 | 15 | 24 | 30 | 50 % |
| meta-212 | 0 | 24 | 16 | 23 | 30 | 53 % |
| meta-213 | 0 | 29 | 18 | 28 | 30 | 60 % |
| meta-214 | 0 | **35** | **23** | 34 | 30 | 77 % |
| meta-217 | **1** | 31 | **30** | 41 | 30 | **100 %** (`error_max_turns`) |
| **meta-218** | 0 | **41** | **30** | 40 | 50 | 60 % |

Die CLI prüft `--max-turns` gegen die **Werkzeugrunden** (R13ar, mit echtem Lauf belegt:
`docs/_r13ar_limit_probe_reviewer.txt`, Limit 2 ⇒ Abbruch nach 2 Runden, `num_turns=3`;
meta-217 brach bei **genau 30** Runden ab). Damit lag meta-218 bei **30 von 50 Runden
= 60 %**, nicht bei 82 %. `num_turns` zählt etwas anderes (Werkzeugergebnisse + 1:
40 Aufrufe → 41; meta-214 34 → 35, das ist die „35 Züge"-Zahl aus dem Auftrag).

**Trotzdem angehoben — wie beauftragt.** 70 = 30 gemessene Runden (meta-218, der
größte bisher) + Reserve; die Tiefenprobe wächst mit jedem Befund, und ein
`error_max_turns` kostet einen ganzen Lauf (meta-217: rc=1, 0 Befunde). Die Erhöhung ist
damit nicht *nötig*, aber sie ist billig und deckt den Fall ab, dass ein Lauf wirklich
länger wird.

## 2. Der Frist-Abstand: warum 8

Die Frist ist der Text, den das Modell **während** des Laufs sieht (der Hook-Kontext), und
die Zeile im Auftrag. Sie liegt `FRIST_ABSTAND` Züge vor dem harten Limit:

* `harness.toml` → `max_turns = 70` (`meta_max_turns` ist der Alias mit Vorrang,
  `aussensicht.max_turns`; beide Namen liefern 70).
* `aussensicht.build_prompt` → `ZEITLIMIT: Schreibe spaetestens nach 62 Zuegen …`
  (70 − 8).
* `aussensicht.write_hook_settings` → `--limit 70 --frist 8`; der Hook schreibt ab
  `Zug >= Limit − 8` zusätzlich `JETZT die Antwort im Blockformat schreiben,
  Unvollständiges als nicht geprüft kennzeichnen.`
* Rückfall im Hook, falls `--frist` fehlt: **8** (`FRIST_STANDARD`, getestet).

Warum 8 und nicht 5: die Antwort im Blockformat braucht mehrere Züge (Antwort schreiben,
Belege nachsehen, Verdikte). meta-217 zeigt den Schaden — der Lauf schrieb nach 30 Runden
nur einen Zwischenstand und wurde als gescheitert gezählt (R13aq).

## 3. Die Frühwarnung (Punkt 3, seit R13ar) — an den neuen echten Zahlen geprüft

`aussensicht.limit_hinweis(batch, runden, grenze)` warnt ab **mehr als 80 %**:

```
Aussensicht B218: 25 von 30 Zuegen genutzt - Limit pruefen
```

Telegram + Zeile `- LIMIT PRUEFEN: …` im Bericht, Log `Zuglimit fast erreicht`; der
Bericht nennt immer `- Zuege (Werkzeugrunden): X von Y - num_turns laut CLI: N`, und
`runs/meta-<N>.json` trägt `zug_runden` (geschrieben ab dem nächsten Neustart — der
laufende Harness hat die alte Fassung im Speicher, deshalb fehlt das Feld bei meta-218
noch). Mit dem neuen Limit: meta-218 (30 Runden) würde bei 70 **nicht** warnen (43 %);
mit dem alten Limit 50 hätte es bei 30 auch nicht gewarnt — gewarnt hätte erst ein Lauf
über 40 Runden. Der Auftragstext „82 %" ist die `num_turns`-Zahl.

## 4. Punkt 4 (nur berichten): `meta-214` mit 35 Zügen bei Limit 30

Aufgelöst in R13ar (`docs/_r13ar_belege.md` §1), hier die Kurzfassung:

* `[meta] max_turns` stand seit R13w (`1eee551`) unverändert auf **30** — das Limit war
  damals **nicht** höher.
* `num_turns=35` ist **nicht** die Zahl, gegen die die CLI prüft. meta-214 brauchte
  **23 Werkzeugrunden** (34 Werkzeugaufrufe) — unter 30, deshalb lief der Lauf durch.
  `num_turns` = Werkzeugergebnisse + 1 (8 von 8 erfolgreichen Läufen).
* Gegenseite: meta-217 hatte **30 Runden** = genau das Limit ⇒ `error_max_turns`.

## 5. Tests

`harness/tests/test_r13ar_fixes.py` (30, angepasst): Frist-Abstand aus dem Harness
(`--frist`), Rückfall 8, „genau an der Grenze", der echte Fall Limit 70 (61 Runden ohne
Frist, 62 mit), Einstellungsdatei trägt `--limit` **und** `--frist`.
`harness/tests/test_r13aq_fixes.py` (30, angepasst): `max_turns = 70` in `harness.toml`,
Prompt nennt `Limit − FRIST_ABSTAND`.

## 6. Offen

* Der laufende Harness (B219) rechnet weiter mit dem Limit aus dem Speicher; die 70
  greifen ab dem nächsten Start. Bis dahin schreibt er auch kein `zug_runden`.
* Der Hook-Beweis (`_r13ar_probe_hook.txt`) ist mit Limit 5 geführt; die Zeile selbst ist
  unabhängig von der Zahl, die 8 steht jetzt aber in der Einstellungsdatei (Test).
