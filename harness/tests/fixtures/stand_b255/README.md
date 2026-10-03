# Fixture `stand_b255` — eingefrorener Stand (03.10.2026, B249 bis B256)

Diese Fixture ist ein **fester Stand** für die Tests von R13bp. Vorher lasen solche Tests
die **lebenden** Dateien im Harness-`runs/` und im Decomp-`analysis/`; der laufende Harness
schreibt sie fort, und der Test wird rot, ohne dass sich am Code etwas geändert hätte
(R13bc-Regel).

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`); die Erwartungen im Test gehören zu genau dieser Fixture.

## Aufbau

```
stand_b255/
  decomp/analysis/
    _preflight_249..255.txt   (7 Dateien, BYTEWEISE, alle UTF-8-BOM)
  root/runs/
    b249..b255/auftrag.md     (7 Instruktionen)
    b255/review.md            (Review, das B254 BEWERTET - mit der irrefuehrenden
                               B-SCHRITT-Zeile "4/5 ... B-Batch 26", R13bp Punkt 1)
    b256/review.md            (Review, das B255 BEWERTET - traegt die Pflichtzeile
                               "STRANG: B" und die B-SCHRITT-Zeile 4/5)
```

Neu bauen (aus einem Repo-Stand mit diesen Dateien):

```powershell
$f = "harness\tests\fixtures\stand_b255"; $dec = "g:\Silent Scope Decomp\analysis"
foreach ($b in 249..255) { New-Item -ItemType Directory -Force "$f\root\runs\b$b" | Out-Null
  Copy-Item "harness\runs\b$b\auftrag.md" "$f\root\runs\b$b\" -Force
  Copy-Item "$dec\_preflight_$b.txt" "$f\decomp\analysis\" -Force }
foreach ($b in 255,256) { Copy-Item "harness\runs\b$b\review.md" "$f\root\runs\b$b\" -Force }
```

## Was dieser Stand misst (die Erwartungen der Tests)

| Größe | Wert |
|---|---|
| Strang B249/B250 | `B` — Quelle **Auftrag des Batches** (`runs/b249|b250/auftrag.md`) |
| Strang B251..B254 | `C` — Quelle Auftrag (`„Strang C (Handport). Messziel: Insn.“`) |
| Strang B255 | `B` — Quelle Auftrag (`„Strang B (Hybrid-Läufer), B-Batch 26 …“`) |
| Strang B256 | `B` — Quelle **Pflichtzeile `STRANG: B`** im Auftrag |
| Irreführung (der Anlass) | `runs/b255/review.md` trägt `B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 26` — das ist der **nachfolgende** B-Batch, nicht B254 |
| `Hybrid-A4`-Zeile | B249 und B251 **selbst gemessen** (696571792 / `8001684C`), B250 und B252..B255 **`Zwischenspeicher Treffer`** (`analysis/_preflight_<N>.txt`, Zeile `Zwischenspeicher`) |
| `Nicht betreten`/`A4`-Herkunft | die Cachedatei selbst traegt **keinen** Herkunftsvermerk (reine Rohausgabe, Name = SHA-256-Schlüssel) — der Vermerk steht in der Preflight-Zeile |
