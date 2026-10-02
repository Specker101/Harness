# R13bl — Harness-Wartung (02.10.2026)

Vier Punkte des Nutzers, **je Punkt ein Commit**. Das Decomp-Repo bleibt unberuehrt.
Der Harness **laeuft** (PID 7460, gestartet 01.10. 21:24) und steht im Zustand
`GATE_APPROVAL`, `batch=236`, `worker=None` — es lief also **kein Batch**; die neuen
`hx/`-Fassungen greifen erst nach dem Neustart am Gate nach B237. `prompts/*.md` liest der
laufende Prozess je Lauf von der Platte, `harness.toml` nur beim Start (bekannte Regel,
`docs/bedienung.md` §12t).

---

## Teil 1 — Pflichtzeile `B-SCHRITT:` fuehrt die B-Nummer als Zaehlung

**Auftrag:** die Vorlage `B-Batch X von max 20` in `prompts/reviewer.md` ersetzen durch
`B-Batch X (Zählung, keine Grenze – Nutzerentscheid 30.09.)`. Vorher Grep ueber `prompts/`,
`hx/`, `tests/` nach `max 20` und `20 B-Batches`, jede Fundstelle mit `Datei:Zeile` nennen
**und entscheiden**.

### Fundstellen und Entscheidung

| Fundstelle | was dort steht | Entscheidung |
|---|---|---|
| `prompts/reviewer.md:431` | Blockformat-Vorlage der Telegram-Zusammenfassung | **geaendert** |
| `prompts/reviewer.md:448` | die Pflichtzeile im Abschnitt „Strang B" | **geaendert** |
| `prompts/reviewer.md:450` | Beispielzeile + Folgesatz | **geaendert** (+ Satz: Grenze seit 30.09.2026 aufgehoben, `k` ist Zaehlung, kein Budget) |
| `hx/stand.py:2212` | der Text, den der Harness in den Review-Prompt schreibt (`pflichtzeile_hinweis`) | **geaendert** (sonst driftet Prompt gegen Vorlage) |
| `docs/bedienung.md:858` | Zitat-Spalte einer Beleg-Tafel („Pflichtzeile im Review dieses Batches") | **bleibt** — Zitat eines echten Dokuments; die Regel steht in §8, die Aenderung in §13 |
| `harness.toml:167` | Begruendung des Stillstands-Zaehlers („Budget von 10-20 B-Batches") | **bleibt** — historische Begruendung, keine aktive Regel |
| `tests/fixtures/stand_b224/root/runs/b214/auftrag.md:119` | eingefrorene Fixture (echtes Dokument vom 30.09.) | **bleibt** — eine Fixture darf nicht rueckdatiert werden; sie haelt den damaligen Stand |
| `tests/test_r13aa_fixes.py:219,264,303` | Reviewer-Summaries als **Testeingabe** | **bleiben** — Eingabe, kein erzeugter Text |
| `tests/test_r13ah_fixes.py:581` | dito | **bleibt** |
| `tests/test_r13w_fixes.py:168,300,321,322,333` | dito | **bleiben** |

**Warum die Testeingaben bleiben duerfen:** der Parser liest nur `B-SCHRITT: <n>/5`
(`stand._RE_B_SCHRITT`, `stand.py:1889`) — der Zusatz „von max 20" war fuer die Maschine nie
relevant. Belegt durch `test_der_parser_haengt_nicht_am_wortlaut` (alte **und** neue
Schreibweise werden erkannt).

### Aenderung

- `prompts/reviewer.md`: Blockformat-Zeile, Pflichtzeile und Beispiel auf
  `B-Batch <k> (Zählung, keine Grenze – Nutzerentscheid 30.09.)`.
- `hx/stand.py::pflichtzeile_hinweis`: derselbe Wortlaut (ASCII-Schreibweise des Moduls).

### Test (Punkt 1)

```
python -m unittest discover -s tests -p test_r13bl_fixes.py -v
Ran 4 tests in 0.361s
OK
```

Enthalten: Vorlage ohne „von max 20"; Hinweistext mit „keine Grenze";
**erzeugter** Reviewer-Prompt (ueber `review_context` + `reviewer.build_prompt`) ohne
„von max 20"; Parser-Toleranz gegenueber beiden Schreibweisen.
