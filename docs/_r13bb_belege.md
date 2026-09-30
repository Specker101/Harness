# R13bb — vier Harness-Punkte aus Aussensicht B224 / Review B225

**Auftrag (Nutzer, 2026-09-30, vier Punkte, je ein Commit).** 1. Fortsetzung nach frühem
Preflight wieder erlauben (R13ax anpassen); 2. Preflight-Zähler gegen die archivierten
Dateien abgleichen (Befund 4, offene Frage aus Review B225: ja); 3. Mischregel der Prognose
(Befund 5); 4. Paket-E-Kopfzeile kodierungstolerant lesen (M224-4).

Belege: `docs/_r13bb_belege.txt` (Erzeuger `docs/_r13bb_belege.py`), Tests
`harness/tests/test_r13bb_fixes.py`.

## Punkt 2 — Preflight-Zähler gegen das Archiv (Befund M224-4)

`runs/b218/result.json` meldete `preflight_laeufe: 2`, laut `runs/b218/antwort.md:7` liefen
aber **3**; `runs/b223/result.json` meldete 1 (es liefen 2), `runs/b224` meldete 1 (es liefen
2). Verpasst wurden jedes Mal die **Fehlläufe** — genau die Läufe, die die Regel „ein gültiger
Preflight je Batch" überwacht.

**Rückblick, gemessen** (`docs/_r13bb_belege.txt`, Abschnitt 2):

| Batch | Aufrufe im Mitschnitt | Fehlläufe im Archiv | Läufe gesamt | überholt |
|---|---|---|---|---|
| 218 | 2 | 1 (`analysis/_m218/_preflight_218_fehllauf1.txt`) | **3** | 0 |
| 223 | 1 | 1 (`analysis/_m223/_preflight_223_fehllauf1.txt`) | **2** | 0 |
| 224 | 1 | 1 (`analysis/_m224/_preflight_224_fehllauf1.txt`) | **2** | 0 |

Deckung mit den Berichten: B218 nennt „01:57 als Fehllauf, 02:03 als überholt, 02:15 gültig"
(`runs/b218/antwort.md:7`), B223 nennt „ein Fehllauf als `_m223/_preflight_223_fehllauf1.txt`
archiviert" (`runs/b223/antwort.md:26`), B224 nennt den Fehllauf aus dem ersten Lauf
(`runs/b224/antwort.md:17`).

**Neu:**

* `stand.preflight_archiv(cfg, batch)` zählt in `analysis/_m<N>/` die Dateien
  `_preflight_<N>_fehllauf*.txt` und `_preflight_<N>*ueberholt*.txt`.
  **Nicht** gezählt: `_vor_fortsetzung<k>.txt` (byteweise Kopie eines schon gezählten Laufs,
  R13ah) und die Nicht-Lauf-Dateien (`_preflight_zeiten.txt`, `_preflight_vergleich.txt`,
  `_preflight_stderr*.txt`, `*zwischenlauf*`).
* `stand.zaehle_preflight_aufrufe(cfg, batch)` liest `runs/b<N>/preflight-aufrufe.jsonl`
  mit derselben Definition wie `worker.zaehle_preflight_aufrufe` — damit der Rückblick für
  ältere Batches nichts nachbaut.
* `stand.preflight_zaehler_zeile(...)` liefert die Review-Fakten-Zeile (Aufrufe gegen
  Archiv), `orchestrator.harness_facts` hängt sie an.
* `result.json` trägt zusätzlich `preflight_archiv_fehllauf`, `preflight_archiv_ueberholt`,
  **`preflight_ungezaehlt`** (die Differenz) und `preflight_laeufe_gesamt`
  (`preflight_laeufe + preflight_ungezaehlt`); der Worker warnt bei Fund im Log
  (`Preflight-Zaehler: archivierte Fehllaeufe nicht gezaehlt`). `preflight_laeufe` selbst
  bleibt unverändert definiert (Aufrufe im Mitschnitt).

Überholte Läufe werden **getrennt** genannt und nicht addiert: in B215/B220 wurden sie vom
Worker abgelegt, können aber im Mitschnitt schon gezählt sein
(`analysis/_m220/_preflight_220_ueberholt1.txt` gegen 2 Aufrufe in
`runs/b220/preflight-aufrufe.jsonl`). Die Zahl, die das nicht riskiert, ist
`preflight_laeufe_gesamt` **ohne** die überholten — sie ist damit eine **untere** Schranke.
