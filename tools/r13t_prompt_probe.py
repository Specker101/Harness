"""R13t (Punkt 4): Beleg, dass PLAN/IST und die /ds-Nachrichten im Review-Prompt stehen.

Der Block wird von der ECHTEN Funktion `reviewer.build_prompt` erzeugt (kein Nachbau);
gedruckt wird nur der Ausschnitt von "=== PLAN/IST" bis "=== ANKERDATEI".

Aufruf:  python tools/r13t_prompt_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))

from hx import reviewer, stand  # noqa: E402
from hx.config import load_config  # noqa: E402

AUS = Path("docs/_r13t_beleg_4_prompt.txt")


def ausschnitt(text: str) -> str:
    a = text.find("=== PLAN/IST")
    b = text.find("=== ANKERDATEI")
    return text[a:b].strip() if a >= 0 and b > a else text


def main() -> int:
    cfg = load_config()
    zeilen = ["# Review-Prompt-Ausschnitt (R13t) - erzeugt von reviewer.build_prompt",
              f"# Anker: {cfg.anchor_file}",
              f"# PLAN/IST-Zeilen: {len(stand.plan_ist_text(cfg).splitlines())}",
              ""]
    # 1) Wahrheitsfall dieses Laufs: Batch 206 hatte KEINE /ds-Nachricht im Auftrag.
    echt206 = stand.ds_nachrichten(cfg, 206)
    # 2) Der Fall, den B207 wirklich haben wird: die jetzt in der Queue liegende
    #    R535-Korrektur (sie wird dem Worker beim naechsten Uebergang zugestellt).
    from hx import queue
    qroot = Path(cfg.root)
    offen = queue.pending(qroot, "ds")
    ds_text = queue.deliver_block(qroot, "ds", [])[0] if offen else ""
    for titel, ds in (("B206 (Auftrag ohne /ds-Block)", echt206),
                      (f"B207 (simuliert: {len(offen)} Nachricht(en) in inbox/ds)", ds_text)):
        ctx = {"batch": 206 if "206" in titel else 207, "next_batch": 207,
               "anchor_batch": 206, "anchor_hint": None,
               "facts": "(gekuerzt - nur der Ausschnitt zaehlt)",
               "worker_report": "(gekuerzt)", "diff": "(gekuerzt)",
               "historie": "(gekuerzt)", "markers": "(gekuerzt)",
               "plan_ist": stand.plan_ist_text(cfg),
               "queue_block": "", "anchor": "(gekuerzt)", "snapshot": "(gekuerzt)",
               "handover": "", "ds_queue": ds, "extra": ""}
        prompt = reviewer.build_prompt(cfg, "batch_end", ctx)
        zeilen += [f"======== {titel} ========", ausschnitt(prompt), ""]
    AUS.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\n# Beleg: {AUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
