"""Ausgangsmessung R13ah (2026-09-29): Belege fuer die drei Fixes nach der Aussensicht B214.

Nur lesend. Druckt und schreibt `docs/_r13ah_messung.txt`:

  1. die Werkzeug-Zeitgrenzen aus `hx/envs.py` und `harness.toml`,
  2. alle Werkzeugaufrufe >= 500 s aus `runs/b212..b214/result.json` mit Befehl,
  3. alle `Hybrid-Lauf`-Zeilen der echten Preflight-Dateien,
  4. den Strang der letzten Batches,
  5. die Ausloeser-Gruende der Aussensicht (neuer Stillstands-Ausloeser).

Aufruf aus `harness/`:  python -u ../docs/_r13ah_probe.py
"""

from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent                # docs/
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import aussensicht, stand                              # noqa: E402
from hx import state as st                                     # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import read_json, read_text                       # noqa: E402

cfg = load_config()
zeilen: list[str] = []


def sag(text: str = "") -> None:
    zeilen.append(text)
    print(text)


sag(f"R13ah Ausgangsmessung - erzeugt {datetime.datetime.now():%Y-%m-%d %H:%M}")
sag(f"Harness-Root: {cfg.root}")
sag(f"Decomp-Repo : {cfg.decomp}")

sag("")
sag("=== 1) Werkzeug-Zeitgrenzen ===")
for i, zeile in enumerate((HARNESS / "hx" / "envs.py").read_text(
        encoding="utf-8").splitlines(), 1):
    if "TIMEOUT_MS" in zeile:
        sag(f"  hx/envs.py:{i}: {zeile.strip()}")
sag(f"  harness.toml claude.tool_timeout_ms   = "
    f"{cfg.get('claude', 'tool_timeout_ms', '(nicht gesetzt -> Vorgabe 600000)')}")
sag(f"  harness.toml claude.bash_max_timeout_s = "
    f"{cfg.get('claude', 'bash_max_timeout_s', '(nicht gesetzt)')}")

sag("")
sag("=== 2) Werkzeugaufrufe >= 500 s (runs/b212..b214/result.json) ===")
for b in (212, 213, 214):
    res = read_json(Path(cfg.root) / "runs" / f"b{b:03d}" / "result.json", {}) or {}
    st_dat = res.get("stats") or {}
    lang = (st_dat.get("laufzeit") or {}).get("langsamste") or []
    sag(f"  --- B{b}: rc={res.get('rc')} dauer={res.get('duration_s')} "
        f"Anfragen={st_dat.get('requests')} ---")
    treffer = [e for e in lang if float(e.get("dauer_s") or 0) >= 500]
    if not treffer:
        sag(f"      keine Aufrufe >= 500 s (Top-Liste hat {len(lang)} Eintraege)")
    for e in treffer:
        sag(f"      {float(e.get('dauer_s')):8.1f} s  {e.get('name')}: "
            f"{(e.get('kurz') or '')[:110]}")

sag("")
sag("=== 3) Hybrid-Lauf-Zeilen der echten Preflight-Dateien ===")
ana = Path(cfg.decomp) / "analysis"
dateien = sorted((p for p in ana.glob("_preflight_*.txt") if re.search(r"_\d+\.txt$",
                                                                       p.name)),
                 key=lambda p: int(re.search(r"_(\d+)\.txt$", p.name).group(1)))
for p in dateien[-16:]:
    nr = int(re.search(r"_(\d+)\.txt$", p.name).group(1))
    gefunden = [z for z in read_text(p).splitlines() if z.startswith("Hybrid-Lauf")]
    sag(f"  _preflight_{nr}.txt: {gefunden[0].strip() if gefunden else '(keine)'}")

sag("")
sag("=== 4) Strang und Halt-PC/Wegmass der letzten Batches ===")
verlauf = {e["batch"]: e for e in stand.hybrid_verlauf(cfg, 8)}
for b in range(211, 215):
    s = stand.strang_von_batch(cfg, b)
    e = verlauf.get(b)
    feld = (f"Halt-PC {e['halt_pc']} | {e['art']} | Wegmass {e['weg']}/{e['weg_gesamt']}"
            if e else "keine Hybrid-Lauf-Zeile")
    sag(f"  B{b}: strang={s.get('strang') or '-'} ({s.get('quelle') or 'keine Quelle'})"
        f" | {feld}")

sag("")
sag("=== 5) Ausloeser der Aussensicht (neuer Stand) ===")
state = st.State(Path(cfg.root) / "state" / "run.json")
for g in aussensicht.faellig(cfg, state):
    sag(f"  - {g}")
sag(f"  Hybrid-Stillstand: {aussensicht.hybrid_stillstand(cfg) or '(keiner)'}")
sag(f"  neuester B-Batch mit Hybrid-Zeile: B{aussensicht.hybrid_neuester_b(cfg)}")
sag(f"  Marken: {json.dumps(state.data.get('meta') or {}, ensure_ascii=False)}")
sag(f"  Preflight-Dauer (letzter Batch): {json.dumps(stand.preflight_dauer(cfg), default=str)}")

ziel = HIER / "_r13ah_messung.txt"
ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
print(f"\n-> {ziel} ({ziel.stat().st_size} B)")
