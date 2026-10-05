"""R13bw-4: den festen Stand `tests/fixtures/stand_b268/` bauen (einmalig).

**Warum.** `test_r13aa_fixes.TestEchteBelege.test_bilanz_weist_die_hochrechnung_getrennt_aus`
las die **lebende** Bilanz (`stand.durchsatz_zeilen(ECHTER_CFG)`). Am 05.10.2026 wurde der
Test rot, ohne dass sich am Harness etwas geaendert hatte: die lebende Preflight-Reihe war
auf 13 Dateien gewachsen (B255, B257..B268 - B256 fehlt) und kam damit in den Zustand
„Strang C ruht", fuer den R13bt-1 (`0a6c07b`) den Wortlaut umgestellt hat. Dieselbe Lehre wie
R13an (Plan) und R13bc (Stand b224): **die Erwartungen gehoeren zu eingefrorenen Dateien.**

Kopiert AUSSCHLIESSLICH (nur lesend aus dem Decomp-Repo und dem Harness-`runs/`):

  * `analysis/_preflight_<N>.txt`            N = 248..268, soweit vorhanden
  * `analysis/_m<N>/_bilanz*.txt`            je Ordner die NEUESTE (N = 246..268)
  * `analysis/_m<N>/_c_paket_e*.txt`         die JUENGSTE Messung (fuer `paket_e_messung`)
  * `analysis/hybrid-plan.md`                traegt die Mischverhaeltnis-Regel
  * `runs/b<N>/auftrag.md`, `runs/b<N>/review.md`   N = 248..269

Der Stand ist EINGEFROREN (Regel wie `stand_b224`): ein neuer Stand bekommt ein eigenes
Verzeichnis, die Erwartungen im Test gehoeren zu genau diesen Dateien.

    python -u docs/_r13bw_fixture_b268.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
DECOMP = HARNESS.parent.parent / "Silent Scope Decomp"
FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b268"
# Das Trendfenster ist 12 (`stand.TREND_FENSTER`) -> 13 Punkte; B256 fehlt in der
# lebenden Reihe, deshalb beginnt die Kopie bei 248 (Luft fuer das Fenster).
PREFLIGHT = range(248, 269)
BILANZ = range(246, 269)
RUNS = range(248, 270)

README = """# Fixture `stand_b268` - eingefrorener Stand (05.10.2026, nach B268)

Gebaut mit `docs/_r13bw_fixture_b268.py` fuer **R13bw-4**: der Test
`test_r13aa_fixes.TestEchteBelege.test_bilanz_weist_die_hochrechnung_getrennt_aus` hat die
**lebende** Bilanz gelesen und wurde rot, sobald die lebende Preflight-Reihe in den Zustand
„Strang C ruht" kam - der Wortlaut dieses Zustands war mit R13bt-1 umgestellt worden.

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`), die Erwartungen im Test gehoeren zu genau dieser Fixture.

## Aufbau

```
stand_b268/
  decomp/analysis/_preflight_248..268.txt   (soweit vorhanden; B256 fehlt - das ist echt)
      Zeilen: "C Koepfe  <n> / <faelle> / <abw>", "Bahnabdeckung ... verifiziert <n>"
  decomp/analysis/_m<N>/_bilanz*.txt        (kanonische Bilanzdateien, je Ordner die
      neueste: tragen "R207 <vorher> -> <nachher>")
  decomp/analysis/_m<N>/_c_paket_e*.txt     (die juengste Paket-E-Messung)
  decomp/analysis/hybrid-plan.md            (Mischverhaeltnis-Regel; Zustand nach B216)
  root/runs/b<N>/auftrag.md                 (Instruktionen: Strang, SOLL-KOEPFE)
  root/runs/b<N>/review.md                  (die Reviews: Pflichtzeile B-SCHRITT/STATION)
```

## Was der Stand zeigt (gemessen im Test)

* Der Durchsatz-Block ist rechenbar (13 Preflight-Dateien im Fenster, Luecke bei B256).
* Strang C **ruht**: die letzten Batches sind B-Batches -> die Kalender-Hochrechnung nennt
  einen Grund statt einer Zahl („die C-Hochrechnung ruht (kein Anteil aus der Plan-Regel)",
  R13bt-1) - kein Plan-Anteil als Rechengroesse.
* Die kanonischen Bilanzdateien fehlen fuer einzelne Batches (z. B. B264) - der R207-Zaehler
  weist das Fenster als lueckenhaft aus.
"""


def kopiere(quelle: Path, ziel: Path) -> int:
    if not quelle.is_file():
        print("FEHLT:", quelle)
        return 0
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(quelle, ziel)
    return 1


def paket_e_juengste() -> Path | None:
    """Die juengste Paket-E-Messung - dieselbe Regel wie `stand.paket_e_messung`."""
    kandidaten = [p for p in (DECOMP / "analysis").glob("_m*/_c_paket_e*.txt") if p.is_file()]
    if not kandidaten:
        return None
    return max(kandidaten, key=lambda p: p.stat().st_mtime)


def main() -> int:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    n = 0
    for b in PREFLIGHT:
        n += kopiere(DECOMP / "analysis" / f"_preflight_{b}.txt",
                     FIXTURE / "decomp" / "analysis" / f"_preflight_{b}.txt")
    for b in BILANZ:
        # Die Dateinamen sind historisch uneinheitlich (`_bilanz.txt`, `_bilanz_237.txt`, …)
        # - `stand.bilanz_je_batch` nimmt je `_m<N>` die neueste passende.
        kandidaten = sorted((DECOMP / "analysis" / f"_m{b}").glob("_bilanz*.txt"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        for quelle in kandidaten[:1]:
            n += kopiere(quelle, FIXTURE / "decomp" / "analysis" / f"_m{b}" / quelle.name)
    pe = paket_e_juengste()
    if pe is not None:
        n += kopiere(pe, FIXTURE / "decomp" / "analysis" / pe.parent.name / pe.name)
    n += kopiere(DECOMP / "analysis" / "hybrid-plan.md",
                 FIXTURE / "decomp" / "analysis" / "hybrid-plan.md")
    for b in RUNS:
        for name in ("auftrag.md", "review.md"):
            n += kopiere(HARNESS / "runs" / f"b{b}" / name,
                         FIXTURE / "root" / "runs" / f"b{b}" / name)
    (FIXTURE / "README.md").write_text(README, encoding="utf-8")
    print(f"{n} Dateien kopiert nach {FIXTURE}")
    return 0 if n >= 40 else 1


if __name__ == "__main__":
    sys.exit(main())
