"""R13bp Punkt 3 (NUR MESSEN): Wartezeit des Batches B255 vorher/nachher.

Der Befund des Nutzers lautet: B255 meldete `warteschleifen: 0` und `warte_s: 0,5 s`,
obwohl das Modell gut 20 Minuten auf den Hybrid-Lauf gewartet hat. Dieses Werkzeug
faehrt den ECHTEN Mitschnitt (`runs/b255/stream.jsonl`, 25,6 MB) durch den Leser und
zeigt je Wartemuster: Anzahl, Summe, erlaubt/verboten und die Belegzeile im Mitschnitt.

Aufruf:  python -u docs/_r13bp_wait_b255.py

Es schreibt NICHTS und aendert NICHTS - es liest nur den Mitschnitt und die Regel
`hx.streamjson.warte_muster` / `warte_sekunden` / `warte_verstoesse`.
"""
import io
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "harness"))

from hx import streamjson                                  # noqa: E402

MIT = WS / "harness" / "runs" / "b255" / "stream.jsonl"
WEITERE = sorted((WS / "harness" / "runs" / "b255").glob("stream-forts*.jsonl"))


def befehle(pfad: Path):
    """(zeile, werkzeug, befehl) je Shell-Werkzeugaufruf - wie der Leser selbst."""
    with io.open(pfad, encoding="utf-8", errors="replace") as fh:
        for nr, ln in enumerate(fh, 1):
            if '"tool_use"' not in ln:
                continue
            try:
                ev = json.loads(ln)
            except ValueError:
                continue
            for b in ((ev.get("message") or {}).get("content") or []):
                if isinstance(b, dict) and b.get("type") == "tool_use" \
                        and b.get("name") in streamjson.SHELL_WERKZEUGE:
                    yield nr, b.get("name"), ((b.get("input") or {}).get("command") or "")


def main() -> int:
    dateien = [MIT] + WEITERE
    gesamt = {"n": 0, "n_erlaubt": 0, "n_verboten": 0, "s": 0.0, "s_verboten": 0.0}
    treffer: list[tuple] = []
    for p in dateien:
        if not p.is_file():
            continue
        for nr, wz, befehl in befehle(p):
            grund = streamjson.warte_muster(befehl)
            if not grund:
                continue
            sek = streamjson.warte_sekunden(befehl)
            erlaubt = streamjson.warte_erlaubt(grund)
            gesamt["n"] += 1
            gesamt["s"] += sek
            if erlaubt:
                gesamt["n_erlaubt"] += 1
            else:
                gesamt["n_verboten"] += 1
                gesamt["s_verboten"] += sek
            treffer.append((p.name, nr, wz, grund, sek, erlaubt))

    print("R13bp Punkt 3 - Wartezeit in B255 (Mitschnitt %s)" % MIT.name)
    print("-" * 100)
    for name, nr, wz, grund, sek, erlaubt in treffer:
        print("%-18s:%-7d %-10s %-38s %8.1f s  %s"
              % (name, nr, wz, grund, sek, "erlaubt" if erlaubt else "VERBOTEN"))
    print("-" * 100)
    print("Summe: %d Aufrufe / %.1f s Wartezeit   (davon erlaubt: %d / %.1f s, "
          "verboten: %d / %.1f s)"
          % (gesamt["n"], gesamt["s"], gesamt["n_erlaubt"], gesamt["s"] - gesamt["s_verboten"],
             gesamt["n_verboten"], gesamt["s_verboten"]))
    print("Meldung in result.json (alt, gemessen): warteschleifen = 0, warte_s = 0,5 s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
