"""R13bj: Sichtung der Belege zu B235 (nur lesend).

Fragen: Ist `runs/b235/review.md` das Review ZU B235? Laeuft das Review zu B234
noch irgendwo mit (reviewer.jsonl / handover.jsonl / logs/review-prompt-*)?
Speist nach docs/_r13bj_sichtung.txt (UTF-8/LF) und stdout.
"""
from __future__ import annotations

import io
import json
import pathlib
import time

H = pathlib.Path("g:/Harness/harness")
R = H / "runs"


def z(zeilen, s=""):
    zeilen.append(s)


def _ts(eintrag):
    return str(eintrag.get("timestamp") or eintrag.get("ts") or "?")


def sichte_jsonl(p: pathlib.Path, zeilen: list, maxprobe: int = 3):
    z(zeilen, f"### {p.relative_to(H).as_posix()}  ({p.stat().st_size} B, "
              f"{time.strftime('%H:%M:%S', time.localtime(p.stat().st_mtime))})")
    typen: dict[str, int] = {}
    ergebnisse = []
    erste, letzte = None, None
    n = 0
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            n += 1
            try:
                d = json.loads(ln)
            except ValueError:
                typen["<kein json>"] = typen.get("<kein json>", 0) + 1
                continue
            t = str(d.get("type") or "?")
            typen[t] = typen.get(t, 0) + 1
            if erste is None:
                erste = d
            letzte = d
            if t == "result":
                txt = d.get("result") or ""
                ergebnisse.append((_ts(d), d.get("session_id") or d.get("sessionId"),
                                   len(txt), txt[:160].replace("\n", " ")))
    z(zeilen, f"  Zeilen: {n} | Typen: {typen}")
    z(zeilen, f"  erste Zeile: {_ts(erste or {})} | letzte Zeile: {_ts(letzte or {})}")
    for i, (ts, sid, ln, probe) in enumerate(ergebnisse[:maxprobe], 1):
        z(zeilen, f"  result #{i}: ts={ts} session={sid} len={ln}")
        z(zeilen, f"      {probe}")
    z(zeilen)


def main() -> int:
    zeilen: list[str] = []
    z(zeilen, "R13bj - Sichtung der B235-Belege (nur lesend)")
    z(zeilen, f"Stand: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    z(zeilen)

    z(zeilen, "## 1. runs/b235/ (Kopf/Stand)")
    for name in ("review.md", "harness-facts.md", "auftrag.md", "antwort.md", "result.json"):
        p = R / "b235" / name
        if not p.is_file():
            z(zeilen, f"  {name}: FEHLT")
            continue
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        kopf = [l for l in txt.splitlines()[:6] if l.strip()][:3]
        z(zeilen, f"  {name} ({p.stat().st_size} B, "
                  f"{time.strftime('%d.%m %H:%M:%S', time.localtime(p.stat().st_mtime))})")
        for l in kopf:
            z(zeilen, f"      | {l[:150]}")
    z(zeilen)

    z(zeilen, "## 2. Mitschnitte des Reviewers/Handovers")
    for name in ("reviewer.jsonl", "reviewer.jsonl.err", "handover.jsonl"):
        p = R / "b235" / name
        if not p.is_file():
            z(zeilen, f"  {name}: FEHLT")
            continue
        if p.stat().st_size == 0:
            z(zeilen, f"  {name}: leer")
            continue
        sichte_jsonl(p, zeilen)
    z(zeilen)

    z(zeilen, "## 3. logs/ - Review-Prompts und Verworfenes")
    logs = H / "logs"
    for muster in ("review-prompt-*", "review-*", "*review*"):
        treffer = sorted(logs.glob(muster))
        if not treffer:
            continue
        z(zeilen, f"  Muster {muster}: {len(treffer)} Datei(en)")
        for p in treffer[-12:]:
            z(zeilen, f"    {p.name}  {p.stat().st_size} B  "
                      f"{time.strftime('%d.%m %H:%M:%S', time.localtime(p.stat().st_mtime))}")
        break
    z(zeilen)

    z(zeilen, "## 4. Zustand")
    p = H / "state" / "run.json"
    if p.is_file():
        d = json.loads(io.open(p, encoding="utf-8").read())
        for k in ("batch", "phase", "paused", "stopped", "autonomous", "review",
                  "reviewer", "last_batch", "updated_at"):
            if k in d:
                z(zeilen, f"  {k}: {json.dumps(d[k], ensure_ascii=False)[:220]}")
    text = "\n".join(zeilen) + "\n"
    (pathlib.Path("g:/Harness/docs") / "_r13bj_sichtung.txt").write_text(
        text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
