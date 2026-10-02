"""R13bn Punkt 3 - den festen Stand `tests/fixtures/stand_b243/` bauen (einmalig).

Kopiert AUSSCHLIESSLICH (nur lesend aus dem Decomp-Repo und dem Harness-`runs/`):

  * `analysis/_preflight_236..243.txt`          (8 Dateien: Zeilen "C Koepfe",
                                                 "Bahnabdeckung … verifiziert"; B236 als
                                                 Vorgaenger, damit der Zuwachs von B237
                                                 messbar ist)
  * `runs/b236..243/auftrag.md`                 (Instruktionen: SOLL-KOEPFE, Strang)
  * `runs/b237..244/review.md`                  (die Reviews, die 236..243 bewerten:
                                                 Pflichtzeile B-SCHRITT = Strang-Beleg)

Der Stand ist EINGEFROREN (Regel wie `stand_b224`/README): die Erwartungen im Test
gehoeren zu genau diesen Dateien; ein neuer Stand bekommt ein eigenes Verzeichnis.

    python -u docs/_r13bn_fixture_b243.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
DECOMP = HARNESS.parent.parent / "Silent Scope Decomp"
FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b243"
# B236 ist der VORGAENGER: ohne seine Preflight-Datei ist der Zuwachs von B237 nicht
# messbar (`c_trend` bildet nur Schritte zwischen BENACHBARTEN Dateien), und genau B237
# traegt den groessten Zuwachs der Reihe (+4).
BATCHE = range(236, 244)

README = """# Fixture `stand_b243` - eingefrorener Stand (02.10.2026, nach B243)

Gebaut mit `docs/_r13bn_fixture_b243.py` fuer R13bn Punkt 3 (Aussensicht M242-3/M243-3):
der Test der Prognose laeuft gegen die **Reihe B237-B243**.

**Regel: Diese Dateien werden NICHT nachgezogen.** Ein neuer Stand bekommt ein eigenes
Verzeichnis (`stand_b<N>`), die Erwartungen im Test gehoeren zu genau dieser Fixture.

## Aufbau

```
stand_b243/
  decomp/analysis/_preflight_236..243.txt   (8 Dateien, wortgetreu)
      Zeilen: "C Koepfe  <n> / <faelle> / <abw>"  und
              "Bahnabdeckung ... verifiziert <n> | teilgeprueft <m> ..."
  root/runs/b236..243/auftrag.md            (Instruktionen, wortgetreu)
  root/runs/b237..244/review.md             (die Reviews zu 236..243, wortgetreu -
      sie tragen die Pflichtzeile "B-SCHRITT:" und damit den Strang-Beleg)
  decomp/analysis/hybrid-plan.md            (traegt die Regel "1 B : 1 C", gegen die der
      gemessene Abschnitt steht)
  decomp/analysis/_m<N>/_bilanz<N>.txt      (die kanonischen Bilanzdateien, SOWEIT IM REPO
      VORHANDEN: B241 fehlt - das ist der Anlass von M242-3)
```

Gemessen an diesem Stand (siehe `tests/test_r13bn_fixes.py`):

* Zuwaechse der C Koepfe im Fenster B236..B243: +4 (B237), +2 (B239), +2 (B241) ->
  **Median 2**. B241 hat KEINE kanonische Bilanzdatei (`analysis/_m241/_bilanz_241.txt`
  fehlt) - der Median aus den Bilanzdateien liess ihn weg und stand auf **3**.
* Strang: B238 und B240 sind B-Batches, ab B241 sind alle C (Strang B ruht nach R236-1)
  -> Anteil fuer die Rechnung **100 %**.
* `C verifiziert` (Bahnabdeckung): B236 87 -> B243 92 = **+5**; die Reihe B237..B243
  darin: 90 -> 92 = **+2**.
"""


def kopiere(quelle: Path, ziel: Path) -> int:
    if not quelle.is_file():
        print("FEHLT:", quelle)
        return 0
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(quelle, ziel)
    return 1


def main() -> int:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    n = 0
    for b in BATCHE:
        n += kopiere(DECOMP / "analysis" / f"_preflight_{b}.txt",
                     FIXTURE / "decomp" / "analysis" / f"_preflight_{b}.txt")
        n += kopiere(HARNESS / "runs" / f"b{b}" / "auftrag.md",
                     FIXTURE / "root" / "runs" / f"b{b}" / "auftrag.md")
        n += kopiere(HARNESS / "runs" / f"b{b + 1}" / "review.md",
                     FIXTURE / "root" / "runs" / f"b{b + 1}" / "review.md")
    # Der Plan gehoert dazu: er traegt die Regel "1 B : 1 C" (50 %), gegen die der
    # gemessene Abschnitt (100 %) steht.
    n += kopiere(DECOMP / "analysis" / "hybrid-plan.md",
                 FIXTURE / "decomp" / "analysis" / "hybrid-plan.md")
    # Die kanonischen Bilanzdateien, SOWEIT ES SIE GIBT: ohne sie druckt der
    # Durchsatz-Block gar nichts (er bricht bei leerem Fenster ab). Fuer B241 gibt es
    # keine - genau der Anlass von M242-3, das bleibt im Stand sichtbar.
    for b in BATCHE:
        # Die Dateinamen sind historisch uneinheitlich (`_bilanz.txt`, `_bilanz_237.txt`, …)
        # - `stand.bilanz_je_batch` nimmt je `_m<N>` die neueste passende.
        kandidaten = sorted((DECOMP / "analysis" / f"_m{b}").glob("_bilanz*.txt"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        for quelle in kandidaten[:1]:
            n += kopiere(quelle, FIXTURE / "decomp" / "analysis" / f"_m{b}" / quelle.name)
    (FIXTURE / "README.md").write_text(README, encoding="utf-8")
    print(f"{n} Dateien kopiert nach {FIXTURE}")
    return 0 if n >= 20 else 1


if __name__ == "__main__":
    sys.exit(main())
