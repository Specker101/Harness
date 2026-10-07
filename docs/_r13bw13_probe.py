"""R13bw-13 - Beleg: Marker, Sperre und Langlauf-Fenster an den ECHTEN Bauteen B282/B284.

Nur lesend: der Mitschnitt wird gelesen, der Hook wird in einem Wegwerf-Verzeichnis
aufgerufen (nie im lebenden Lauf). Ausgabe nach `docs/_r13bw13_beleg.txt`.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime

HARNESS = pathlib.Path(r"g:\Harness\harness")
sys.path.insert(0, str(HARNESS))

from hx import streamjson, worker                     # noqa: E402
from hx.util import ensure_dir, write_text_atomic     # noqa: E402

ZIEL = pathlib.Path(r"g:\Harness\docs\_r13bw13_beleg.txt")
TMP = HARNESS / "tests" / "_tmp_r13bw13_beleg"
MARKER = "NACHRUECKLISTE ERLEDIGT"
zeilen = [f"R13bw-13 Beleg {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _kurz(cmd: str) -> bool:
    """Kurze Form? (die freie Schranke aus streamjson)"""
    return streamjson.langlauf_aufruf("PowerShell", {"command": cmd}) == ""


def langlaeufe(b: int) -> list[tuple[float, int, str]]:
    """Langlauf-STARTS eines Batches mit Minute seit dem ersten Mitschnitt-Eintrag."""
    p = HARNESS / "runs" / f"b{b:03d}" / "stream.jsonl"
    if not p.is_file():
        return []
    t0 = None
    out = []
    for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            d = json.loads(l)
        except ValueError:
            continue
        t = d.get("timestamp")
        if not t:
            continue
        if t0 is None:
            t0 = ts(t)
        if d.get("type") != "assistant":
            continue
        for c in (d.get("message") or {}).get("content") or []:
            if c.get("type") != "tool_use":
                continue
            inp = c.get("input") or {}
            name = streamjson.langlauf_aufruf(c.get("name"), inp)
            if not name:
                continue
            cmd = str(inp.get("command") or "")
            # Das passende BEFEHLSTEIL zeigen (die Aufrufe stehen oft in einem mehrzeiligen
            # Block - die ersten 150 Zeichen der ganzen Zeile zeigen dann etwas anderes).
            treffer = ""
            for teil in streamjson._befehls_teile(cmd):
                if streamjson._RE_LANGLAUF_QUERY.search(teil):
                    continue
                if streamjson._RE_LANGLAUF_START.search(teil.strip()):
                    treffer = " ".join(teil.split())[:120]
                    break
            out.append((round((ts(t) - t0).total_seconds() / 60, 1), i, name, treffer or cmd[:120]))
    return out


# ---------------------------------------------------------------- 1) Die Belegstelle
zeilen.append("1) Die Belegstelle (Nutzerauftrag): runs/b282/stream.jsonl:55860/55861")
p = HARNESS / "runs" / "b282" / "stream.jsonl"
z = p.read_text(encoding="utf-8", errors="replace").splitlines()
for n in (55860, 55861):
    d = json.loads(z[n - 1])
    for c in (d.get("message") or {}).get("content") or []:
        t = str(c.get("text") or c.get("thinking") or "")
        if "nachrueck" in t.lower() or "nachrück" in t.lower():
            kurz = " ".join(t.split())[:300]
            zeilen.append(f"  Zeile {n}  typ={c.get('type'):8s} {kurz}")
zeilen.append(f"  -> worker.nachrueckliste_marker(runs/b282) = "
              f"{worker.nachrueckliste_marker(HARNESS / 'runs' / 'b282') or '(keiner)'}")
zeilen.append("     (in B282 stand der Marker nur im DENKEN - Denkbloecke zaehlen nicht;")
zeilen.append("      haette der Worker ihn als sichtbaren Text oder als Antwort geschrieben,")
zeilen.append("      waere die Preflight-Sperre nach dem neuen S1 sofort gefallen.)")

# ------------------------------------------------- 2) Langlauf-Starts und das Fenster
schwelle = 134.98          # gemessen 2026-10-07: alarm 150 - max(15, preflight 10.02+5)
vorlauf = 30.0
zeilen.append("")
zeilen.append(f"2) Erkannte Langlauf-STARTS je Batch (Schwelle {schwelle:.1f} min, "
              f"Fenster ab {schwelle - vorlauf:.1f} min, frei unter 200M Schritte)")
for b in (282, 284, 289):
    rufe = langlaeufe(b)
    rp = HARNESS / "runs" / f"b{b:03d}" / "result.json"
    dauer = json.loads(rp.read_text(encoding="utf-8")).get("duration_s", 0) / 60 if rp.is_file() else 0
    zeilen.append(f"  B{b} ({dauer:.0f} min, {len(rufe)} Starts):")
    for m, i, name, teil in rufe:
        kurz = "FREI (unter der Schranke)" if "--schritte" in teil and _kurz(teil) else ""
        fenster = "IM FENSTER -> gesperrt" if m >= schwelle - vorlauf else ""
        zeilen.append(f"     +{m:6.1f} min  Z{i:6d}  {name:22s} "
                      f"{fenster or kurz or 'vor dem Fenster (erlaubt)'}")
        zeilen.append(f"                  {teil}")
    if rufe:
        zeilen.append("     (gezeigt ist das passende BEFEHLSTEIL - die Aufrufe stehen oft in")
        zeilen.append("      einem mehrzeiligen Block, dessen erste Zeile etwas anderes tut.)")

# --------------------------------------------------------- 3) Der Hook, echt aufgerufen
shutil.rmtree(TMP, ignore_errors=True)
root = ensure_dir(TMP / "root")
lauf = ensure_dir(root / "runs" / "b999")
state = root / "state" / "run.json"


def hook(cmd: str, minuten: float, marker: bool) -> str:
    write_text_atomic(lauf / "auftrag.md", "# Auftrag\n\n## NACHRUECKLISTE\n\n1. Posten\n")
    if marker:
        write_text_atomic(lauf / "antwort.md", f"{MARKER}\n")
    else:
        for f in lauf.glob("antwort*.md"):
            f.unlink()
    start = datetime.now().astimezone() - __import__("datetime").timedelta(minutes=minuten)
    write_text_atomic(state, json.dumps(
        {"worker": {"pid": 1, "started_at": start.isoformat(timespec="seconds")},
         "live": {"batch": 999}}))
    args = [sys.executable, str(HARNESS / "tools" / "batch_uhr.py"), "--state", str(state),
            "--umschalt", "135", "--pre", "--run", str(lauf)]
    daten = {"hook_event_name": "PreToolUse", "tool_name": "PowerShell",
             "tool_input": {"command": cmd}}
    r = subprocess.run(args, input=json.dumps(daten).encode("utf-8"),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    aus = r.stdout.decode("utf-8").strip()
    if not aus:
        return "erlaubt (keine Antwort)"
    return json.loads(aus)["hookSpecificOutput"].get("permissionDecisionReason", "deny")


PRE = "python -u scripts/preflight.py before *> analysis/_preflight_999.txt"
LANG = '& "G:\\Silent Scope Decomp\\port\\build\\hybrid_lauf.exe" --schritte 2700000000'
zeilen.append("")
zeilen.append("3) Der Hook, echt aufgerufen (Wegwerf-Lauf, Schwelle 135 min):")
for beschr, cmd, m, mk in (("Preflight 40 min, Liste OFFEN", PRE, 40.0, False),
                           ("Preflight 40 min, Marker da", PRE, 40.0, True),
                           ("2,7G-Lauf 40 min, Marker da", LANG, 40.0, True),
                           ("2,7G-Lauf 40 min, kein Marker", LANG, 40.0, False),
                           ("2,7G-Lauf 110 min, kein Marker", LANG, 110.0, False),
                           ("100M-Lauf 110 min, kein Marker",
                            '& "G:\\Silent Scope Decomp\\port\\build\\hybrid_lauf.exe" '
                            "--schritte 100000000", 110.0, False)):
    zeilen.append(f"  {beschr:32s} -> {hook(cmd, m, mk)[:150]}")
marke = lauf / "langlauf-blockiert.jsonl"
zeilen.append(f"  Beleg langlauf-blockiert.jsonl: "
              + (marke.read_text(encoding='utf-8').strip().replace('\n', ' | ')[:300]
                 if marke.is_file() else "(keine)"))
shutil.rmtree(TMP, ignore_errors=True)


text = "\n".join(zeilen) + "\n"
ZIEL.write_text(text, encoding="utf-8", newline="\n")
print(text)
