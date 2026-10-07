"""R13bw-11 - Beleg: der Hook lehnt den Original-Aufruf aus B289 ab (nur lesen).

Der Aufruf wird WORTGETREU aus dem Mitschnitt gelesen (`runs/b289/stream.jsonl:56505`),
nicht abgetippt: `tool_name` und `tool_input.command` gehen so in den Hook, wie die
Claude-CLI sie geschickt hat.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import time

HARNESS = pathlib.Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx import streamjson                                    # noqa: E402
from hx.util import ensure_dir, write_text_atomic            # noqa: E402

ZEILE = 56505
STREAM = HARNESS / "runs" / "b289" / "stream.jsonl"
TMP = HARNESS / "tests" / "_tmp_r13bw11_beleg"
ZIEL = pathlib.Path(r"g:\Harness\docs\_r13bw11_beleg.txt")

zeilen = [f"R13bw-11 Beleg {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]

d = json.loads(STREAM.read_text(encoding="utf-8", errors="replace").splitlines()[ZEILE - 1])
ruf = [c for c in d["message"]["content"] if c.get("type") == "tool_use"][0]
name, input_ = ruf["name"], ruf["input"]
zeilen.append(f"Aufruf aus {STREAM.relative_to(HARNESS)}:{ZEILE}")
zeilen.append(f"  tool_name  : {name}")
zeilen.append(f"  command    : {input_['command']}")
zeilen.append(f"  description: {input_.get('description')}")
zeilen.append(f"  -> streamjson.port_suche_kuerzung = "
              f"{streamjson.port_suche_kuerzung(name, input_)}")

shutil.rmtree(TMP, ignore_errors=True)
root = ensure_dir(TMP / "root")
lauf = ensure_dir(root / "runs" / "b289")
state = root / "state" / "run.json"
write_text_atomic(state, json.dumps({"live": {"batch": 289}}))


def hook(cmd: str) -> tuple[str, str]:
    args = [sys.executable, str(HARNESS / "tools" / "batch_uhr.py"),
            "--state", str(state), "--umschalt", "80", "--pre", "--run", str(lauf)]
    daten = {"hook_event_name": "PreToolUse", "tool_name": name,
             "tool_input": {"command": cmd}}
    p = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    return p.stdout.decode("utf-8"), p.stderr.decode("utf-8", "replace")


zeilen.append("")
zeilen.append("Hook-Antwort auf DIESEN Aufruf (PreToolUse):")
aus, err = hook(input_["command"])
zeilen.append("  " + (aus.strip() or "(leer)"))
zeilen.append(f"  stderr: {err.strip()[:200] or '(leer)'}")

zeilen.append("")
zeilen.append("Gegenproben mit demselben Skript:")
for cmd in ("python scripts/port_suche.py 80008828",
            "python scripts/port_suche.py 80008828 --schreiben",
            "python scripts/port_suche.py 80008828 | Select-Object -First 25"):
    a, _ = hook(cmd)
    kurz = "ABGELEHNT" if a.strip() else "erlaubt (keine Hook-Antwort)"
    zeilen.append(f"  {kurz:<28} {cmd}")

marke = lauf / "port_suche-blockiert.jsonl"
zeilen.append("")
zeilen.append(f"Belegdatei {marke.name}: "
              + ((marke.read_text(encoding='utf-8').strip() or '(leer)')
                 if marke.is_file() else '(fehlt)'))
shutil.rmtree(TMP, ignore_errors=True)

text = "\n".join(zeilen) + "\n"
ZIEL.write_text(text, encoding="utf-8", newline="\n")
print(text)
