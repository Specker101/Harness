"""R13v3-Nachprobe Zustand: haelt `/autonom off` ueber Stop und Neustart?

Belegt drei Dinge mechanisch (kein Nachbau, echte Funktionen):

  1. Wo ueberhaupt `autonomous` GESCHRIEBEN wird (Datei:Zeile in `hx/`).
  2. Der Ist-Wert in JEDER Zustandsdatei unter `harness/state/`.
  3. Probelauf der Kette: `handle_command("/autonom off")` -> Datei lesen ->
     Stoppen (`state.set(STOPPED)`) -> neu laden -> Wert noch da?

Dazu die Nummernfrage: `anchor_batch()` und `expected_batch()` aus dem ECHTEN
Ankerkopf (nur lesend) - was ein abgebrochener Lauf fuer die naechste Nummer bedeutet.

Aufruf: python -u tools/r13v3_zustand_probe.py
Beleg:  docs/_r13v3_beleg_zustand.txt
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER / "harness"))

from hx import state as st                    # noqa: E402
from hx.config import load_config             # noqa: E402
from hx.orchestrator import Orchestrator      # noqa: E402
from hx.util import Log                       # noqa: E402

BELEG = HIER / "docs" / "_r13v3_beleg_zustand.txt"
TMP = HIER / "sandbox" / "sperrprobe" / "_zustand"

zeilen: list[str] = []


def sag(text: str = "") -> None:
    zeilen.append(text)
    print(text)


def schreibstellen() -> list[str]:
    treffer: list[str] = []
    for datei in sorted((HIER / "harness" / "hx").glob("*.py")):
        for i, z in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"""\[["']autonomous["']\]\s*=|DEFAULTS\s*=|"autonomous":""", z):
                treffer.append(f"  {datei.relative_to(HIER)}:{i}: {z.strip()[:110]}")
    return treffer


def main() -> int:
    cfg = load_config()
    TMP.mkdir(parents=True, exist_ok=True)
    sag("# R13v3-Nachprobe: /autonom-Haltbarkeit und Batch-Nummer")
    sag("# erzeugt von tools/r13v3_zustand_probe.py")
    sag(f"# Harness: {cfg.root}")
    sag()

    sag("======== 1. Wo wird `autonomous` geschrieben? (hx/) ========")
    sag("(Der einzige Nutzerpfad ist der Telegram-Zweig in orchestrator.handle_command;")
    sag(" cli.py schreibt nur in der Attrappe auf IHREN eigenen Zustand.)")
    sag("\n".join(schreibstellen()))
    sag()

    sag("======== 2. Ist-Wert in jeder Zustandsdatei ========")
    gefunden = 0
    for datei in sorted((Path(cfg.root) / "state").rglob("*.json")):
        try:
            daten = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(daten, dict) and "autonomous" in daten:
            gefunden += 1
            sag(f"  {datei.relative_to(HIER)}: autonomous = {daten['autonomous']!r}")
    if not gefunden:
        sag("  (keine Zustandsdatei mit dem Feld gefunden)")
    sag()

    sag("======== 3. Probelauf: Befehl -> Stop -> Neustart ========")
    # Echter Zustand, aber in einer Wegwerf-Datei; der echte Zustand wird NICHT angefasst.
    datei = TMP / "run.json"
    if datei.exists():
        datei.unlink()
    orch = Orchestrator.__new__(Orchestrator)
    orch.cfg = cfg
    orch.state = st.State(datei)
    orch.log = Log(TMP / "log.jsonl", echo=False)
    orch.qroot = TMP
    gesagt: list[str] = []
    orch.say = lambda *t, **k: gesagt.append(" ".join(str(x) for x in t))
    orch.state.data["autonomous"] = True
    orch.state.save()
    sag(f"  Ausgangswert (absichtlich AN): {st.State(datei).data['autonomous']!r}")
    Orchestrator.handle_command(orch, "/autonom off")
    sag(f"  Telegram-Antwort: {gesagt[-1] if gesagt else '(keine)'}")
    sag(f"  SOFORT auf der Platte:        {json.loads(datei.read_text(encoding='utf-8'))['autonomous']!r}")
    neu = st.State(datei)
    sag(f"  nach Neustart (frisch gelesen): {neu.data['autonomous']!r}")
    neu.data["stopped"] = True
    neu.set(st.STOPPED, "Stop (Probelauf)")
    wieder = st.State(datei)
    sag(f"  nach STOPPEN:                 {wieder.data['autonomous']!r} "
        f"(Zustand {wieder.data['state']}, stopped={wieder.data['stopped']})")
    wieder.data["autonomous"] = True
    wieder.save()
    sag(f"  Gegenrichtung (/autonom an):  {st.State(datei).data['autonomous']!r}")
    sag("  Vorgabe fuer eine fehlende Datei: "
        f"{st.DEFAULTS['autonomous']!r} (also AUS)")
    sag()

    sag("======== 4. Batch-Nummer nach einem Abbruch ========")
    anker = orch.anchor_batch()
    sag(f"  Ankerkopf im Decomp-Repo nennt: BATCH {anker}")
    sag(f"  expected_batch() = Anker + 1  : {orch.expected_batch()}")
    sag("  Der Zustand selbst zaehlt NICHT mit (kein zweiter Zaehler):")
    orch.state.data["batch"] = 999
    sag(f"    state['batch'] auf 999 gesetzt -> expected_batch() bleibt "
        f"{orch.expected_batch()}")
    sag("  Folge: Wird ein Lauf abgebrochen, OHNE dass der Worker den Ankerkopf")
    sag("  fortschreibt, bekommt der naechste Lauf DIESELBE Nummer; sein Review liegt")
    sag("  wieder in runs/b<derselben Zahl> (die neue Fassung ueberschreibt dort")
    sag("  auftrag.md/stream.jsonl - der Vorgaenger steht als stream-v1.jsonl im ZIP-Schutz).")
    sag()
    sag("======== Regeln ========")
    sag(" * `/autonom off|on` schreibt SOFORT in den Zustand (orchestrator.handle_command).")
    sag(" * Beim Laden werden fehlende Felder aus DEFAULTS ergaenzt - ein gespeichertes")
    sag("   False bleibt False, ein True bleibt True. Weder Stop noch Neustart fassen es an.")
    sag(" * Eine fehlende Zustandsdatei ergibt AUS (Vorgabe).")
    BELEG.parent.mkdir(parents=True, exist_ok=True)
    BELEG.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n# Beleg: {BELEG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
