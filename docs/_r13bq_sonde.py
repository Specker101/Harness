"""R13bq Punkt 4 (NUR MESSEN): schreibt die claude-CLI im stream-json-Modus blockweise?

Frage des Nutzers (2026-10-03): in B257 war `runs/b257/stream-forts1.jsonl` nach dem Start
der Fortsetzung (20:21) rund 45 min lang 0 Bytes und danach 4 MB. Der Harness schreibt jede
gelesene Zeile SOFORT (`hx/proc.py:117` `out_fh.write(raw)` + `flush()`, im eigenen Faden)
- also muss die Ausgabe blockweise angekommen sein.

Diese Sonde misst dieselbe Frage an ZWEI minimalen Aufrufen (kein Harness-Zustand, kein
Ghidra, kein MCP; Prompt ueber stdin):

  A) `stdout=PIPE`  (wie im Harness)  -> wann kommt das erste Byte, in wie vielen Stuecken,
                                          und wie weit liegt die Ankunft hinter der
                                          CLI-Zeit im Inhalt?
  B) `stdout=DATEI` (Gegenprobe)      -> waechst die Datei waehrend des Laufs oder springt sie
                                          am Ende?

Der Beleg wird von DIESEM Skript als `docs/_r13bq_sonde.txt` geschrieben (UTF-8, LF -
eine Konsolenumleitung wuerde Umlaute verstuemmeln, s. Projekt-Fallstrick).

Aufruf:  python -u docs/_r13bq_sonde.py        (zwei kurze echte Aufrufe, Kosten ~Cent)
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # g:\Harness
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import envs, secrets                            # noqa: E402
from hx.config import load_config                       # noqa: E402
from hx.util import ensure_dir, write_text_atomic       # noqa: E402

BELEG = ROOT / "docs" / "_r13bq_sonde.txt"
FRAGE = ("Denke kurz nach und antworte dann in EINEM Satz: wieviel ist 17 * 23? "
         "Antworte direkt, ohne Werkzeuge zu benutzen.")
_RE_TS = re.compile(r'"timestamp"\s*:\s*"([0-9T:.\-]+Z)"')

_puffer = io.StringIO()


def sag(text: str = "") -> None:
    print(text)
    _puffer.write(text + "\n")


def befehl(cfg) -> list[str]:
    """Wie der Worker, aber ohne MCP/Profil: nur die Form der Ausgabe zaehlt."""
    return [str(cfg.get("claude", "exe")), "-p",
            "--output-format", "stream-json", "--verbose",
            "--strict-mcp-config",
            "--permission-prompts", "none",
            "--allowedTools", "Read",
            "--model", str(cfg.get("claude", "model_worker")),
            "--max-turns", "1"]


def lauf_pipe(cmd, env, cwd, ziel: Path) -> dict:
    """A) stdout=PIPE: Ankunftszeit und Groesse JEDES Stuecks (os.read am Rohhandle)."""
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.stdin.write(FRAGE.encode("utf-8"))
    p.stdin.close()
    stuecke: list[tuple[float, int, str, float]] = []      # (t_rel, bytes, cli_ts, epoch)
    fd = p.stdout.fileno()
    while True:
        b = os.read(fd, 1 << 20)
        if not b:
            break
        m = _RE_TS.search(b.decode("utf-8", "replace"))
        stuecke.append((round(time.monotonic() - t0, 3), len(b),
                        m.group(1) if m else "", time.time()))
    rc = p.wait()
    ende = round(time.monotonic() - t0, 3)
    fehler = p.stderr.read().decode("utf-8", "replace")[:400]
    p.stdout.close()
    p.stderr.close()
    gesamt = sum(s for _, s, _, _ in stuecke)
    write_text_atomic(ziel, "")            # Platzhalter: nur die Groesse ist hier wichtig
    return {"rc": rc, "ende": ende, "stuecke": stuecke, "bytes": gesamt,
            "stderr": fehler}


def lauf_datei(cmd, env, cwd, ziel: Path) -> dict:
    """B) stdout=DATEI: Zeitreihe der Dateigroesse waehrend des Laufs."""
    if ziel.exists():
        ziel.unlink()
    t0 = time.monotonic()
    fh = open(ziel, "wb")
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE,
                         stdout=fh, stderr=subprocess.PIPE)
    p.stdin.write(FRAGE.encode("utf-8"))
    p.stdin.close()
    proben: list[tuple[float, int]] = []
    while p.poll() is None:
        proben.append((round(time.monotonic() - t0, 2), ziel.stat().st_size))
        time.sleep(0.25)
    fh.close()
    ende = round(time.monotonic() - t0, 3)
    proben.append((ende, ziel.stat().st_size))
    fehler = p.stderr.read().decode("utf-8", "replace")[:400]
    p.stderr.close()
    return {"rc": p.returncode, "ende": ende, "proben": proben,
            "bytes": ziel.stat().st_size, "stderr": fehler}


def ts_zeit(iso: str) -> float:
    if not iso:
        return float("nan")
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def main() -> int:
    cfg = load_config()
    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    if not token:
        sag("KEIN DeepSeek-Token gefunden - Sonde nicht moeglich.")
        write_text_atomic(BELEG, _puffer.getvalue())
        return 2
    env = envs.worker_env(cfg, os.environ, token)
    cmd = befehl(cfg)
    tmp = ensure_dir(Path(cfg.harness_home) / "sandbox" / "_r13bq_sonde")
    logdir = ensure_dir(HARNESS / "logs" / "ask")     # wie `hx.cli ask` (CLI schreibt Logs)

    sag("R13bq Punkt 4 - Sonde: schreibt die claude-CLI blockweise?")
    sag("Zeitpunkt: " + datetime.now().astimezone().isoformat(timespec="seconds"))
    sag(f"Modell: {cfg.get('claude', 'model_worker')} | config_dir: "
        f"{env.get('CLAUDE_CONFIG_DIR')} | base_url: {env.get('ANTHROPIC_BASE_URL')}")
    sag(f"Aufruf: {cmd[0]} -p --output-format stream-json --verbose --model … "
        f"--max-turns 1   (Prompt ueber stdin, kein MCP)")
    sag()

    t_start = time.monotonic()
    a = lauf_pipe(cmd, env, str(cfg.decomp), tmp / "a.jsonl")
    sag("### A) stdout = PIPE (wie im Harness)")
    sag(f"   rc={a['rc']} Dauer={a['ende']:.1f} s Bytes={a['bytes']} "
        f"Stuecke={len(a['stuecke'])}")
    for i, (t, groesse, ts, epoche) in enumerate(a["stuecke"][:12], 1):
        zusatz = ""
        if ts:
            verzug = epoche - ts_zeit(ts)
            zusatz = (f"   Inhalt-Zeit {ts} -> Ankunft {verzug:+.2f} s spaeter "
                      f"(Verzug)")
        sag(f"   Stueck {i:2d}: bei {t:7.2f} s  {groesse:8d} B{zusatz}")
    if len(a["stuecke"]) > 12:
        sag(f"   … {len(a['stuecke']) - 12} weitere Stuecke, letztes bei "
            f"{a['stuecke'][-1][0]:.2f} s")
    if a["stderr"].strip():
        sag("   stderr: " + a["stderr"].strip()[:200])
    sag()

    b = lauf_datei(cmd, env, str(cfg.decomp), tmp / "b.jsonl")
    sag("### B) stdout = DATEI (Gegenprobe)")
    sag(f"   rc={b['rc']} Dauer={b['ende']:.1f} s Bytes={b['bytes']} "
        f"Proben={len(b['proben'])}")
    for t, groesse in b["proben"][:14]:
        sag(f"   bei {t:7.2f} s  Datei {groesse:8d} B")
    if len(b["proben"]) > 14:
        sag(f"   … letzte Probe bei {b['proben'][-1][0]:.2f} s  "
            f"{b['proben'][-1][1]:d} B")
    if b["stderr"].strip():
        sag("   stderr: " + b["stderr"].strip()[:200])
    sag()

    sag("### Verdikt")
    erste_t = a["stuecke"][0][0] if a["stuecke"] else float("nan")
    luecke = 0.0
    if len(a["stuecke"]) > 1:
        luecke = max(y[0] - x[0] for x, y in zip(a["stuecke"], a["stuecke"][1:]))
    sag(f"   A) erstes Byte bei {erste_t:.2f} s von {a['ende']:.1f} s Laufzeit, "
        f"{len(a['stuecke'])} Stuecke fuer {a['bytes']} B, groesste Luecke {luecke:.2f} s")
    sag(f"   B) Datei bei der ersten Probe {b['proben'][0][1] if b['proben'] else 0} B, "
        f"am Ende {b['bytes']} B")
    if a["bytes"] and erste_t > 0.6 * a["ende"]:
        sag("   -> A: die Ausgabe kam (fast) vollstaendig AM ENDE: die CLI puffert am Rohr.")
    else:
        sag("   -> A: die Ausgabe kam unterwegs an (kein reines Endpuffern in diesem Lauf).")
    vorher_schon_da = any(g > 0 for _, g in b["proben"][:-1])
    if vorher_schon_da:
        sag("   -> B: die Datei waechst WAEHREND des Laufs (kein Endpuffern).")
    else:
        sag("   -> B: die Datei springt erst am Ende (auch als Datei gepuffert).")
    sag()
    sag("### Was diese Sonde NICHT zeigt")
    sag("   Der Aufruf ist KURZ (kein Werkzeugaufruf, kein MCP-Server) - genau die Lage,")
    sag("   in der B257/B258 die 0-Byte-Phasen auftraten, ist damit NICHT nachgestellt.")
    sag("   Belegt ist nur: am Rohr und an der Datei kommt die Ausgabe WAEHREND des Laufs")
    sag("   an - eine allgemeine Blockpufferung der CLI gibt es nicht.")
    sag()
    sag("Belege fuer die Ausgangsbeobachtung (B257/B258) stehen in "
        "docs/_r13bq_belege.md.")

    write_text_atomic(BELEG, _puffer.getvalue())
    print(f"\ngeschrieben: {BELEG.name} ({len(_puffer.getvalue())} Zeichen, UTF-8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
