#!/usr/bin/env python
"""Nachtbericht B161..B174 aus den Rohbelegen (nur lesen, aendert nichts).

Aufruf (aus g:\\Harness):
    python -u docs\\_nachtbericht_b161_174.py 2>&1 | Out-File -Encoding utf8 docs\\_nachtbericht_b161_174.txt

Quellen je Batch N:
  runs/b<N>/result.json        Messdaten des Worker-Laufs N
  runs/b<N>/stream.jsonl       Rohmitschnitt (Ablehnungen/Fehler neu ausgezaehlt, R13d)
  runs/b<N+1>/harness-facts.md Bilanz, Alarme, Reviewer-Modell, Commits fuer N
  runs/b<N+1>/review.md        Review von N (offene Punkte)
"""

from __future__ import annotations

import builtins
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
RUNS = HARNESS / "runs"
DECOMP = Path(r"g:\Silent Scope Decomp")
sys.path.insert(0, str(HARNESS))

from hx import streamjson                                        # noqa: E402

BATCHES = list(range(161, 175))


def result_of(n: int) -> dict:
    f = RUNS / f"b{n:03d}" / "result.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def facts_of(n: int) -> str:
    """Bilanzblock, der beim Review von Batch N entsteht (liegt in b<N+1>)."""
    f = RUNS / f"b{n + 1:03d}" / "harness-facts.md"
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""


def review_of(n: int) -> str:
    f = RUNS / f"b{n + 1:03d}" / "review.md"
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""


def zeile(text: str, praefix: str) -> str:
    for l in text.splitlines():
        if l.startswith(praefix):
            return l[len(praefix):].strip()
    return ""


def scan_stream(n: int) -> dict:
    """Mitschnitt neu auswerten: Anfragen, Fehler, Ablehnungen, Werkzeuge."""
    f = RUNS / f"b{n:03d}" / "stream.jsonl"
    if not f.is_file():
        return {}
    st = streamjson.StreamStats()
    with f.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            st.feed(line)
    per_tool: dict[str, int] = {}
    for e in st.tool_errors:
        per_tool[e["name"]] = per_tool.get(e["name"], 0) + 1
    return {"requests": len(st.requests), "tool_errors": len(st.tool_errors),
            "per_tool": per_tool, "denials": len(st.denials),
            "api_errors": len(st.api_errors), "tools": dict(st.tool_counts),
            "mcp_servers": st.mcp_servers, "tools_available": st.tools_available}


def commits_of(n: int) -> list[str]:
    """Betreffzeilen der Commits des Batches aus dem Bilanzblock."""
    text = facts_of(n)
    m = re.search(r"- git log seit Checkpoint:\n```\n(.*?)```", text, re.S)
    if m:
        return [l.strip() for l in m.group(1).splitlines() if l.strip()]
    # Kein Bilanzblock (Review steht noch aus): direkt am Checkpoint-Tag messen.
    tag = f"harness/b{n:03d}-start"
    out = subprocess.run(["git", "-C", str(DECOMP), "log", "--oneline",
                          f"{tag}..HEAD"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return [l.strip().lstrip("\ufeff") for l in (out.stdout or "").splitlines() if l.strip()]


def origin_reflog() -> list[tuple[str, str]]:
    """Zeitpunkte, zu denen origin/main aktualisiert wurde (Push-Nachweis)."""
    out = subprocess.run(["git", "-C", str(DECOMP), "reflog", "show", "origin/main",
                          "--date=iso", "--format=%gd|%ad|%gs"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    eintraege: list[tuple[str, str]] = []
    for l in (out.stdout or "").splitlines():
        teile = l.strip().lstrip("\ufeff").split("|")
        if len(teile) >= 3:
            eintraege.append((teile[1], teile[2]))
    return eintraege


def git_log_decomp(seit: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(DECOMP), "log", "--since", seit,
                          "--format=%h %ad %s", "--date=iso"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [l.strip().lstrip("\ufeff") for l in (out.stdout or "").splitlines() if l.strip()]


def main() -> int:
    # Ausgabe geht direkt in die Datei: die Konsole (PowerShell 5.1) wandelt
    # UTF-8 sonst je Codepage um und zerstoert Umlaute.
    ziel = Path(__file__).with_name("_nachtbericht_b161_174.md")
    fh = ziel.open("w", encoding="utf-8", newline="\n")

    def print(*a, **k):                                        # noqa: A001
        k.setdefault("file", fh)
        builtins.print(*a, **k)

    pushes = origin_reflog()
    zustand = {}
    try:
        zustand = json.loads((HARNESS / "state" / "run.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    print("# Nachtbericht B161-B174")
    print()
    print(f"Erzeugt aus den Rohbelegen unter `{RUNS}` (nur gelesen).")
    print()
    print("| Batch | Dauer | Anfragen | Kosten | Profil / Programm | Commits | "
          "Alarme | Ablehn. | Werkzeugfehler | Push | Review-Modell | offene Punkte |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")

    summe_kosten = 0.0
    summe_anfragen = 0
    summe_dauer = 0.0
    auffaellig: list[str] = []
    fehler_gesamt: dict[str, int] = {}
    denials_gesamt = 0

    for n in BATCHES:
        res = result_of(n)
        sc = scan_stream(n)
        text = facts_of(n)
        rev = review_of(n)

        dauer_s = float(res.get("duration_s") or 0)
        dauer = f"{int(dauer_s // 3600)}h{int(dauer_s % 3600 // 60):02d}m" if dauer_s else "-"
        anfragen = res.get("stats", {}).get("requests")
        if anfragen is None:
            anfragen = sc.get("requests")
        kosten = float(res.get("cost_usd") or 0)
        profil = res.get("profile") or zeile(text, "- Profil: ").split("|")[0].replace("Profil:", "").strip() or "-"
        prog = res.get("program") or "-"
        prog = prog.rsplit(".", 2)[-2] + ".bin" if prog.endswith(".bin") else prog
        if (not res) and int(zustand.get("batch") or 0) == n:
            extra = str((zustand.get("phase") or {}).get("extra") or "")
            m = re.search(r"Profil (\w+)", extra)
            if m:
                profil = m.group(1)
        commits = commits_of(n)
        alarme = res.get("alarms") or []
        if not alarme:
            a = zeile(text, "- Alarmmeldungen:")
            alarme = [] if a in ("", "keine") else a.split(";")
        modell = zeile(text, "- Reviewer: Modell ").split(" (Soll")[0] or "-"
        offen = len(re.findall(r"ENTSCHEIDUNG NOETIG|OFFENE FRAGE|WARTET AUF LIVE-AUFNAHME", rev))

        werr = sc.get("tool_errors")
        werr_txt = str(werr) if werr is not None else "-"
        for k, v in (sc.get("per_tool") or {}).items():
            fehler_gesamt[k] = fehler_gesamt.get(k, 0) + v
        denials_gesamt += int(sc.get("denials") or 0)

        push = "-"
        if res.get("finished_at"):
            try:
                ende = datetime.fromisoformat(res["finished_at"])
            except Exception:
                ende = None
            if ende is not None:
                for ts, txt in pushes:
                    try:
                        t = datetime.fromisoformat(ts)
                    except Exception:
                        continue
                    if abs((t - ende).total_seconds()) <= 900:
                        push = "ok" if "push" in txt.lower() else txt[:20]
                        break
        if push == "-" and commits:
            push = "offen?"
        print(f"| {n} | {dauer} | {anfragen if anfragen is not None else '-'} | "
              f"${kosten:.4f} | {profil} / {prog} | {len(commits)} | {len(alarme)} | "
              f"{sc.get('denials', '-')} | {werr_txt} | {push} | {modell} | {offen} |")

        summe_kosten += kosten
        summe_anfragen += int(anfragen or 0)
        summe_dauer += dauer_s

        if not res:
            auffaellig.append(f"B{n}: **kein result.json** (Lauf nicht abgeschlossen)")
        if alarme:
            auffaellig.append(f"B{n}: Alarm(e): " + "; ".join(a[:70] for a in alarme))
        if sc.get("denials"):
            auffaellig.append(f"B{n}: {sc['denials']} Ablehnung(en)")
        if werr:
            auffaellig.append(f"B{n}: {werr} Werkzeugfehler - {sc.get('per_tool')}")

    print()
    print(f"**Summen:** {summe_anfragen} Anfragen | ${summe_kosten:.4f} | "
          f"{int(summe_dauer // 3600)}h{int(summe_dauer % 3600 // 60):02d}m | "
          f"{denials_gesamt} Ablehnungen | {sum(fehler_gesamt.values())} Werkzeugfehler")
    print()
    print("## Werkzeugfehler nach Werkzeug (ganze Nacht)")
    if fehler_gesamt:
        for k, v in sorted(fehler_gesamt.items(), key=lambda x: -x[1]):
            print(f"- `{k}`: {v}")
    else:
        print("- keine")
    print()
    print("## Auffaelligkeiten")
    for a in auffaellig:
        print(f"- {a}")
    print()
    print("## Commits der Nacht (Decomp-Repo)")
    for l in git_log_decomp("2026-09-26 00:00"):
        print(f"- {l}")
    fh.close()
    builtins.print(f"geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
