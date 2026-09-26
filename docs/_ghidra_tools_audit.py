#!/usr/bin/env python
"""Audit: Passt die Werkzeugliste der Profile zu den Gruppen, die die Bridge laedt?

Hintergrund (Punkt 10 des Sammelauftrags): Die Bridge wird mit `--lazy` und
`--default-groups <profil.groups>` gestartet. Nur Werkzeuge aus diesen Gruppen
sind ueberhaupt sichtbar; alles andere muesste der Worker mit `load_tool_group`
nachladen - und genau diese Hilfswerkzeuge stehen in `hard_denied`.

Das Werkzeug vergleicht:
  * die Gruppen der Bridge (autoritativ: /mcp/schema des Ghidra-Plugins),
  * `groups` des Profils (was geladen wird),
  * `allowed` / `denied` / `hard_denied` des Profils (was der Client zulaesst).

Aufruf aus g:\\Harness:   python docs\\_ghidra_tools_audit.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HARNESS = Path(r"g:\Harness\harness")
SCHEMA_URL = "http://127.0.0.1:8089/mcp/schema"


def schema_tools() -> dict[str, str]:
    """name -> category (autoritative Gruppenkarte des Plugins)."""
    with urllib.request.urlopen(SCHEMA_URL, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    tools = data.get("tools") or data.get("endpoints") or data
    if isinstance(tools, dict):
        tools = list(tools.values())
    karte: dict[str, str] = {}
    for t in tools:
        if not isinstance(t, dict):
            continue
        # Der Werkzeugname steckt im Pfad ("/add_function_tag"), nicht in "name".
        name = t.get("name") or t.get("tool") or (t.get("path") or "").lstrip("/")
        if not name:
            continue
        karte[str(name)] = str(t.get("category") or "?")
    return karte


def profil(name: str) -> dict:
    return json.loads((HARNESS / "profiles" / f"{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    ziel = Path(__file__).with_name("_ghidra_tools_audit.txt")
    fh = ziel.open("w", encoding="utf-8", newline="\n")

    def p(*a):
        print(*a, file=fh)

    karte = schema_tools()
    p(f"Werkzeuge laut /mcp/schema: {len(karte)}")
    gruppen: dict[str, list[str]] = {}
    for n, c in karte.items():
        gruppen.setdefault(c, []).append(n)
    p("Gruppen: " + ", ".join(f"{g}({len(v)})" for g, v in sorted(gruppen.items())))
    p()

    for prof_name in ("ghidra-read", "ghidra-standard", "ghidra-full"):
        d = profil(prof_name)
        geladen = {g.strip() for g in str(d.get("groups") or "").split(",") if g.strip()}
        allowed = set(d.get("allowed") or [])
        denied = set(d.get("denied") or [])
        hart = set(d.get("hard_denied") or [])
        p(f"=== {prof_name} ===")
        p(f"groups={sorted(geladen)}  allowed={len(allowed)} denied={len(denied)} hard_denied={len(hart)}")
        fehlende_gruppen = sorted(g for g in geladen if g not in gruppen)
        if fehlende_gruppen:
            p(f"  !! Gruppen, die es NICHT gibt: {fehlende_gruppen}")
        sichtbar = {n for n, c in karte.items() if c in geladen}
        p(f"  sichtbar ohne load_tool_group: {len(sichtbar)}/{len(karte)}")

        braucht_gruppe = sorted(allowed - sichtbar)     # allowed, aber nicht geladen
        if braucht_gruppe:
            p(f"  !! erlaubt, aber AUSSERHALB der geladenen Gruppen ({len(braucht_gruppe)}) "
              f"-> nur per load_tool_group:")
            for n in braucht_gruppe:
                p(f"       {n}  [{karte.get(n, 'nicht im Schema')}]")
        sonst = sorted(sichtbar - allowed - denied - hart)
        p(f"  sichtbar, aber nicht in allowed/denied/hard_denied: {len(sonst)}"
          + (": " + ", ".join(sonst[:10]) if sonst else ""))
        konflikt = sorted((allowed & denied) | (allowed & hart))
        if konflikt:
            p(f"  !! in allowed UND gesperrt: {konflikt}")
        p(f"  hard_denied: {sorted(hart)}")
        p()

    p("=== Lazy-Hilfswerkzeuge ===")
    for name in ("list_instances", "connect_instance", "list_tool_groups", "load_tool_group",
                 "unload_tool_group", "check_tools", "search_tools"):
        d = profil("ghidra-standard")
        status = ("hard_denied" if name in (d.get("hard_denied") or [])
                  else "denied" if name in (d.get("denied") or [])
                  else "allowed" if name in (d.get("allowed") or []) else "nicht gelistet")
        p(f"  {name:22s} [{karte.get(name, '?')}] -> {status}")
    fh.close()
    print(f"geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
