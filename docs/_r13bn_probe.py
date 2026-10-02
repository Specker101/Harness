"""R13bn - Sonde: was rechnen `c_rate`, `c_trend` und der Anteil HEUTE (vor dem Umbau)?

Nur lesend. Gegen den eingefrorenen Stand `tests/fixtures/stand_b224` (R13bc) und - mit
`--live` - gegen die lebenden Dateien des Decomp-Repos (Reihe B237..B243).

    python -u docs/_r13bn_probe.py [--live]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(HARNESS))

import shutil as _shutil                                                  # noqa: E402
from hx import bilanz, stand                                              # noqa: E402
from hx.config import load_config                                         # noqa: E402
from hx.util import ensure_dir                                            # noqa: E402

FIXTURE = HARNESS / "tests" / "fixtures" / "stand_b224"
TMP = HARNESS / "tests" / "_tmp_r13bn_probe"


def gegen_fixture():
    _shutil.rmtree(TMP, ignore_errors=True)
    root, decomp = ensure_dir(TMP / "root"), ensure_dir(TMP / "decomp")
    _shutil.copytree(FIXTURE / "root", root, dirs_exist_ok=True)
    _shutil.copytree(FIXTURE / "decomp", decomp, dirs_exist_ok=True)
    cfg = load_config()
    cfg.data["paths"]["root"] = str(root)
    cfg.data["paths"]["decomp"] = str(decomp)
    cfg.data["paths"]["harness_home"] = str(TMP)
    cfg.data["paths"]["secrets"] = str(ensure_dir(TMP / "secrets"))
    return cfg, "FIXTURE stand_b224"


def gegen_live():
    cfg = load_config()
    return cfg, "LIVE (Decomp-Repo)"


def zeige(cfg, titel: str) -> None:
    print("=" * 78)
    print(titel)
    print("  root  :", cfg.root)
    print("  decomp:", cfg.decomp)
    t = stand.c_trend(cfg, stand.TREND_FENSTER)
    print("\n-- c_trend (Preflight-Reihe, lueckenlos)")
    if t.get("gemessen"):
        print(f"   B{t['erst']['batch']} {t['erst']['koepfe']} -> B{t['letzt']['batch']} "
              f"{t['letzt']['koepfe']} = {t['delta']:+d}  luecken={t['luecken']} "
              f"dateien={t['n_gemessen']}")
        print("   c_schritte:", [(s["bis"], s["delta"]) for s in t["c_schritte"]])
        print("   mittel_je_batch:", t.get("mittel_je_batch"),
              " mittel_je_c_batch:", t.get("mittel_je_c_batch"))
    else:
        print("   nicht gemessen:", t.get("grund"))
    print("\n-- SOLL-KOEPFE je Batch (auftrag.md)")
    for e in (t.get("reihe") or []):
        b = int(e["batch"])
        soll = stand.soll_koepfe(stand.auftrags_text(cfg, b)[0])
        strang = stand.strang_von_batch(cfg, b).get("strang") or "?"
        print(f"   B{b}: koepfe={e['koepfe']:>5}  SOLL={soll!s:>5}  strang={strang}")
    print("\n-- c_rate")
    r = stand.c_rate(cfg, stand.STANDARD_FENSTER)
    print("   median:", r["median"], " mittel:", r["mittel"], " rate:", r["rate"])
    print("   kopf_batches:", r["kopf_batches"])
    print("   quelle:", r["quelle"])
    print("\n-- durchsatz: Anteil der C-Batches")
    d = stand.durchsatz(cfg, stand.STANDARD_FENSTER)
    print("   anteil_c:", d.get("anteil_c"), " anteil_gemessen:", d.get("anteil_gemessen"))
    print("   anteil_quelle:", d.get("anteil_quelle"))
    print("   rate_c_koepfe:", d.get("rate_c_koepfe"))
    print("\n-- C verifiziert (Bahnabdeckung)")
    try:
        print("   ", "\n    ".join(bilanz._verifiziert_zeile(cfg)))
    except Exception as exc:                                       # noqa: BLE001
        print("    Fehler:", exc)
    try:
        reihe = stand.preflight_bahnabdeckung(cfg, 8)
        print("   Reihe:", [(e["batch"], e.get("verifiziert"), e.get("teilgeprueft"))
                            for e in reihe])
    except Exception as exc:                                       # noqa: BLE001
        print("    Fehler:", exc)


def main() -> int:
    if "--live" in sys.argv:
        cfg, titel = gegen_live()
    else:
        cfg, titel = gegen_fixture()
    zeige(cfg, titel)
    if "--live" not in sys.argv:
        _shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
