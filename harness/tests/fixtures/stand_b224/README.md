# Fixture `stand_b224` — eingefrorener Projektstand (30.09.2026, Stand B224)

Diese Fixture ist der **feste Stand**, gegen den die früheren „Realtests" laufen (R13bc,
Aufräumrunde). Vorher lasen sie die **lebenden** Dateien im Decomp-Repo und im
Harness-`runs/`; sobald der nächste Batch etwas schrieb, wurden sie rot und schalteten sich
per `skipTest` ab — ein Test, der sich selbst abschaltet, prüft nichts mehr.

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`), die Erwartungen im Test gehören zu genau dieser Fixture. Wer
etwas nachziehen will, legt eine neue Fixture an und nennt sie im Commit.

## Aufbau

```
stand_b224/
  decomp/analysis/      <- Kopien aus g:\Silent Scope Decomp\analysis
    hybrid-plan.md      (voll)
    _preflight_2*.txt   (26 Dateien, B200-B225)
    _m<N>/_bilanz*.txt  (17 Dateien, R207-Zeilen)
    _m210|219|222|224/_c_paket_e*.txt   (9 Paket-E-Messungen, BYTEWEISE)
    _m218|223|224/_preflight_<N>_fehllauf1.txt   (archivierte Fehlläufe)
  root/runs/
    b200..b225/auftrag.md            (26 Instruktionen)
    b218|223|224/preflight-aufrufe.jsonl
```

Die Paket-E-Dateien sind **byteweise** kopiert (`shutil.copy2`): nur so bleiben das
UTF-8-BOM von `_m224/_c_paket_e_nachher.txt` und die fehlende Datumszeile in
`_m222/_c_paket_e.txt` erhalten — beides ist Prüfgegenstand (R13ba-Nachtrag, R13bb Punkt 4).

Neu bauen (aus einem Repo-Stand mit diesen Dateien):

```powershell
$fixt = "harness\tests\fixtures\stand_b224"; $dec = "g:\Silent Scope Decomp\analysis"
Copy-Item "$dec\hybrid-plan.md" "$fixt\decomp\analysis\" -Force
Get-ChildItem $dec -Filter "_preflight_2*.txt" | Copy-Item -Destination "$fixt\decomp\analysis\"
Get-ChildItem $dec -Directory -Filter "_m2*" | ForEach-Object { $b=$_.Name
  New-Item -ItemType Directory -Force "$fixt\decomp\analysis\$b" | Out-Null
  Get-ChildItem $_.FullName -Filter "_bilanz*.txt" | Copy-Item -Destination "$fixt\decomp\analysis\$b\" }
foreach ($b in 210,219,222,224) { New-Item -ItemType Directory -Force "$fixt\decomp\analysis\_m$b" | Out-Null
  Copy-Item "$dec\_m$b\_c_paket_e*.txt" "$fixt\decomp\analysis\_m$b\" -Force }
foreach ($b in 218,223,224) { Copy-Item "$dec\_m$b\_preflight_*fehllauf*.txt" "$fixt\decomp\analysis\_m$b\" -Force }
foreach ($b in 200..225) { New-Item -ItemType Directory -Force "$fixt\root\runs\b$b" | Out-Null
  Copy-Item "harness\runs\b$b\auftrag.md" "$fixt\root\runs\b$b\" -Force }
foreach ($b in 218,223,224) { Copy-Item "harness\runs\b$b\preflight-aufrufe.jsonl" "$fixt\root\runs\b$b\" -Force }
```

## Was dieser Stand misst (die Erwartungen der Tests)

| Größe | Wert |
|---|---|
| Paket E offen | **20 Koepfe / 1657 Insn**, Datei `_m224/_c_paket_e_nachher.txt` (UTF-8-BOM), Datum `2026-09-30 16:55` aus dem Kopf, `stand = nachher` |
| Vorgänger (anderer Wert) | B222, `22 Koepfe / 1849 Insn` → Delta **+2 Koepfe / +192 Insn** |
| gleicher Wert im selben Batch | `_m224/_c_paket_e.txt` (20/1657, UTF-8 ohne BOM) |
| Rate (`stand.c_rate`, Fenster 5) | Median **4** (Kopf-Batches `+3 (B224)`, `+5 (B219)`), Mittel über alle C-Batch-Schritte **2,375** → Zeile `Median Zuwachs (Kopf-Batches): 4 \| Mittel ueber alle C-Batches: 2,4` |
| PLAN/IST-Tafel (`n=12`) | `MEDIAN der 3 Zuwaechse … (+3 (B224), +5 (B219), +7 (B216)): 5 Koepfe je C-Batch` — das Fenster ist größer als bei `c_rate`, die Zahl also 5 statt 4 (auch am lebenden Repo so) |
| Hochrechnung Paket E | `-> 5 C-Batches bei +4.0 Koepfe je C-Batch` (Grundlage: Median der Kopf-Batches) |
| Mischregel | `1 B : 1 C`, Anteil **0.5**, `hybrid-plan.md:368`, Stand `ab B222, NUTZERENTSCHEIDUNG R221-1, 2026-09-30`, Paarliste **leer** |
| Preflight-Zähler | B218 `2 Aufrufe + 1 Fehllauf = 3 Laeufe`, B223 `1 + 1 = 2`, B224 `1 + 1 = 2` |

Quellen der Werte: die Dateien selbst (Zeilennummern über `stand.paket_e_messung`,
`stand.plan_mischung`, `stand.preflight_archiv`). Der Erzeuger der Zahlen in dieser Tabelle
ist `docs/_r13bc_fixture.txt` (`docs/_r13bc_fixture.py`) — er läuft gegen **diese** Fixture,
nicht gegen das lebende Repo.
