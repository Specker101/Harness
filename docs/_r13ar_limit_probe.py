"""R13ar-Probe: was zaehlt `--max-turns` - und was `num_turns`? (MESSUNG)

Anlass (Punkt 3 des Auftrags): `runs/meta-214` lief laut `result.json` mit **35 Zuegen**
erfolgreich durch, obwohl `[meta] max_turns = 30` war (gemessen: der Wert stand seit R13w
unveraendert, `git show <rev>:harness/harness.toml`). `runs/meta-217` brach dagegen bei
`num_turns = 31` mit `error_max_turns` ab. `num_turns` ist also nicht die Zahl, gegen die
das Limit prueft.

Diese Sonde faehrt zwei winzige Laeufe mit dem **Worker-Modell** (DeepSeek, Bruchteile eines
Cents) und einem Auftrag, der genau drei `Read`-Aufrufe braucht:

  A) OHNE `--max-turns`
  B) MIT `--max-turns 2`

Verglichen werden Exit-Code, `subtype`, `num_turns` (aus dem Ergebnis-Ereignis) und die
Zahl der Werkzeugaufrufe im Mitschnitt. Damit ist belegt, ob die Option greift und welche
Zahl sie zaehlt.

Aufruf: python -u docs/_r13ar_limit_probe.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
sys.path.insert(0, str(HARNESS))

from hx import envs, secrets, streamjson                         # noqa: E402
from hx.config import load_config                                # noqa: E402
from hx.proc import run_stream                                   # noqa: E402

TMP = HIER / "_r13ar_probe"
PROMPT = ("Lies nacheinander genau diese drei Dateien mit je einem Read-Aufruf: a.txt, "
          "b.txt, c.txt. Schreibe danach nur das Wort OK.")


def einlauf(exe: str, cfg, env, nummer: str, extra: list[str], modell: str) -> dict:
    ziel = TMP / f"lauf{nummer}.jsonl"
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose",
           "--model", modell,
           "--permission-prompts", "none",
           "--allowedTools", "Read",
           "--add-dir", str(TMP),
           *extra]
    run = run_stream(cmd, env, cwd=str(TMP), out_path=ziel, on_event=None,
                     hard_wall_s=180.0, log=None, stdin_text=PROMPT,
                     stderr_path=TMP / f"lauf{nummer}.err.txt")
    stats = streamjson.StreamStats()
    ids: set = set()
    for z in ziel.read_text(encoding="utf-8", errors="replace").splitlines():
        stats.feed(z)
        try:
            e = json.loads(z)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            mid = (e.get("message") or {}).get("id")
            if mid:
                ids.add(mid)
    res_ev = stats.result or {}
    return {"rc": run.rc, "dauer_s": round(float(run.duration_s or 0.0), 1),
            "subtype": str(res_ev.get("subtype") or ""),
            "num_turns": res_ev.get("num_turns"),
            "antworten": len(ids),
            "tool_use": len(stats.tools),
            "werkzeuge": dict(stats.tool_counts),
            "fehler": "; ".join(str(x) for x in (res_ev.get("errors") or []))[:160],
            "antwort": (stats.final_text() or "").strip()[:60]}


def main() -> int:
    rolle = "worker"
    if "--rolle" in sys.argv:
        rolle = sys.argv[sys.argv.index("--rolle") + 1]
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name in ("a.txt", "b.txt", "c.txt"):
        (TMP / name).write_text(f"Inhalt von {name}\n", encoding="utf-8")
    cfg = load_config()
    exe = str(cfg.get("claude", "exe"))
    if rolle == "reviewer":
        token = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
        env = envs.reviewer_env(cfg, os.environ, token)
        modell = str(cfg.get("claude", "model_reviewer", "claude-opus-5-5"))
    else:
        token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
        env = envs.worker_env(cfg, os.environ, token)
        modell = str(cfg.get("claude", "model_worker"))
    beschriftung = [("A: ohne --max-turns", []),
                    ("B: mit --max-turns 2", ["--max-turns", "2"])]

    print("R13ar-Probe: zaehlt `--max-turns` die Zahl `num_turns`? "
          f"(Rolle {rolle}, Modell {modell})")
    print(f"Auftrag: {PROMPT}")
    print()
    ergebnisse: list[tuple[str, dict]] = []
    for name, extra in beschriftung:
        print(f"--- {name} ---")
        aus = einlauf(exe, cfg, env, f"{rolle}{name[0]}", extra, modell)
        ergebnisse.append((name, aus))
        print(f"    rc={aus['rc']} subtype={aus['subtype'] or '-'} "
              f"num_turns={aus['num_turns']} antworten={aus['antworten']} "
              f"tool_use={aus['tool_use']} dauer={aus['dauer_s']}s")
        print(f"    Werkzeuge: {aus['werkzeuge']}")
        if aus["fehler"]:
            print(f"    Fehlertext: {aus['fehler']}")
        print(f"    Antwort: {aus['antwort']!r}")
    print()
    a = ergebnisse[0][1]
    b = ergebnisse[1][1]
    print("Lesehilfe:")
    print(f"   A brauchte {a['tool_use']} Werkzeugaufrufe, {a['antworten']} Modellantworten, "
          f"num_turns={a['num_turns']}.")
    print(f"   B mit Limit 2: subtype={b['subtype'] or '-'}, num_turns={b['num_turns']}, "
          f"Antworten={b['antworten']}, Werkzeugaufrufe={b['tool_use']}.")
    print("   Greift das Limit, muss B mit `error_max_turns` enden; die Zahl, gegen die")
    print("   geprueft wird, ist dann aus num_turns/Antworten/Werkzeugaufrufen ablesbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
