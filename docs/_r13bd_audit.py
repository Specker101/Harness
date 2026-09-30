"""R13bd-Audit (2. Fassung): welche Tests lesen WIRKLICH lebende Dateien?

Erste Fassung war eine reine Textanalyse und lieferte 166 "Kandidaten", weil
`assertEqual(x, [])` in einem reinen Rechentest genauso aussieht wie in einem Test, der
ein rollendes Fenster liest. Diese Fassung misst stattdessen:

  Stufe 1 (zur Laufzeit): die Datei-Zugriffe (`read_text`/`open`/`glob`/`is_file`/…) werden
          umhuellt; protokolliert wird nur, was unter einem LEBENDEN Pfad liegt
          (Decomp-Repo, `state/`, `runs/`, `sessions/`, `prompts/`, `harness.toml`).
          Wegwerfordner unter `tests/_tmp*` und die Fixture sind ausdruecklich aussen vor.
  Stufe 2 (AST): je gefundenem Test die drei Leerlauf-Bauformen
          A Zusicherung nur in einem `if`-Zweig, B Schleife ohne Zusicherung im Rumpf,
          C Zusicherung, die fuer eine leere Menge ebenso gilt.

Ergebnis: `docs/_r13bd_audit.txt` (Bericht) und `docs/_r13bd_audit.json` (Rohdaten).
Die volle Testreihe laeuft dabei einmal mit - das ist der Preis fuer eine Messung statt
einer Vermutung.

Aufruf: python -u docs/_r13bd_audit.py
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
import time
import unittest
from pathlib import Path

HIER = Path(__file__).resolve().parent
HARNESS = HIER.parent / "harness"
TESTS = HARNESS / "tests"
ZIEL = HIER / "_r13bd_audit.txt"
ROH = HIER / "_r13bd_audit.json"

sys.path.insert(0, str(HARNESS))

from hx.config import load_config                                    # noqa: E402

REAL = load_config()
LIVE = {
    "decomp": Path(REAL.decomp),
    "state": Path(REAL.root) / "state",
    "runs": Path(REAL.root) / "runs",
    "sessions": Path(REAL.root) / "sessions",
    "prompts": Path(REAL.prompts_dir),
}

_treffer: dict[str, set[str]] = {}          # Testname -> {"kategorie: pfadmuster"}
_aktiver_test = {"name": "", "datei": ""}
ZAHL_RE = re.compile(r"\d+")


def _kategorie(text: str) -> str | None:
    """Lebender Pfad? `None` = interessiert nicht (Wegwerfordner, Fixture, Quellcode)."""
    s = text.replace("\\", "/")
    if "/tests/_tmp" in s or "/tests/fixtures/" in s or "/_tmp_" in s:
        return None
    for name, wurzel in LIVE.items():
        w = str(wurzel).replace("\\", "/").rstrip("/").lower()
        if s.lower().startswith(w + "/") or s.lower() == w:
            return name
    if s.lower().endswith("/harness.toml"):
        return "config"
    if "/docs/bedienung.md" in s:
        return "docs-bedienung"
    return None


def _merken(pfad: object) -> None:
    try:
        text = str(pfad)
    except Exception:                                                  # noqa: BLE001
        return
    art = _kategorie(text)
    if art is None:
        return
    # Zugriffe ausserhalb eines Tests (Modulimport, setUpModule) laufen unter eigenem Namen:
    # `ECHTER_CFG = load_config()` beim Import ist genau so ein lebender Zugriff.
    name = _aktiver_test["name"] or "(Modulimport)"
    muster = ZAHL_RE.sub("N", text.replace("\\", "/")[-90:])
    _treffer.setdefault(name, set()).add(f"{art}: {muster}")


def _umhuellen() -> None:
    """Die Lese-Wege von `pathlib.Path` beobachten (nur beobachten, nie veraendern)."""
    for name in ("read_text", "read_bytes", "open", "exists", "is_file", "is_dir",
                 "glob", "rglob", "iterdir", "stat"):
        original = getattr(Path, name)

        def neu(self, *a, __orig=original, **k):                       # noqa: ANN001
            _merken(self)
            return __orig(self, *a, **k)

        setattr(Path, name, neu)


class Sammler(unittest.TextTestResult):
    """Haelt fest, welcher Test gerade laeuft (fuer die Zuordnung der Zugriffe)."""

    def startTest(self, test) -> None:                                 # noqa: ANN001
        modul = test.__class__.__module__.split(".")[-1]
        _aktiver_test["datei"] = modul
        _aktiver_test["name"] = f"{modul}:{test.__class__.__name__}.{test._testMethodName}"
        super().startTest(test)


# ------------------------------------------------------------------ Stufe 2 (AST)
def assert_aufrufe(knoten: ast.AST) -> int:
    n = 0
    for k in ast.walk(knoten):
        if isinstance(k, ast.Call):
            f = k.func
            if isinstance(f, ast.Attribute) and (f.attr.startswith("assert")
                                                 or f.attr in ("fail", "skipTest")):
                n += 1
            elif isinstance(f, ast.Name) and f.id == "assert":
                n += 1
    return n


def leere_zusicherung(knoten: ast.AST) -> bool:
    for k in ast.walk(knoten):
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute) \
                and k.func.attr.startswith("assert"):
            if k.func.attr in ("assertEqual", "assertNotEqual") and len(k.args) >= 2:
                a, b = k.args[0], k.args[1]
                if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) \
                        and a.func.id == "len" and isinstance(b, ast.Constant) \
                        and b.value in (0, [], {}, ""):
                    return True
                for x in (a, b):
                    if isinstance(x, (ast.List, ast.Dict, ast.Tuple)) and not x.elts:
                        return True
    return False


_BAUM_CACHE: dict[str, ast.Module] = {}


def bauformen(datei: str, klasse: str, test: str) -> dict:
    p = TESTS / f"{datei}.py"
    if not p.is_file():
        return {}
    if datei not in _BAUM_CACHE:
        _BAUM_CACHE[datei] = ast.parse(p.read_text(encoding="utf-8"))
    baum = _BAUM_CACHE[datei]
    for cls in [k for k in ast.walk(baum)
                if isinstance(k, ast.ClassDef) and k.name == klasse]:
        for fn in [k for k in cls.body if isinstance(k, ast.FunctionDef) and k.name == test]:
            a, b = [], []
            for k in ast.walk(fn):
                if isinstance(k, ast.If):
                    if assert_aufrufe(ast.Module(body=k.body, type_ignores=[])) and \
                            not assert_aufrufe(ast.Module(body=k.orelse, type_ignores=[])):
                        a.append(k.lineno)
                if isinstance(k, (ast.For, ast.AsyncFor)):
                    if assert_aufrufe(ast.Module(body=k.body, type_ignores=[])) == 0:
                        b.append(k.lineno)
            return {"if_ohne_else": a, "for_ohne_assert": b,
                    "leere_zusicherung": leere_zusicherung(fn),
                    "asserts": assert_aufrufe(fn)}
    return {}


def main() -> int:
    muster = sys.argv[1] if len(sys.argv) > 1 else "test_*.py"
    probe = len(sys.argv) > 1
    ziel = ZIEL if not probe else ZIEL.with_name("_r13bd_audit_probe.txt")
    roh_ziel = ROH if not probe else ROH.with_name("_r13bd_audit_probe.json")
    start = time.time()
    print(f"Stufe 1: Testreihe mit Beobachtung der Datei-Zugriffe laeuft ... "
          f"(Muster {muster})", flush=True)
    os.chdir(HARNESS)
    _umhuellen()
    suite = unittest.TestLoader().discover("tests", pattern=muster)
    puffer = io.StringIO()
    ergebnis = unittest.TextTestRunner(stream=puffer, verbosity=1,
                                       resultclass=Sammler).run(suite)
    dauer = time.time() - start
    print(f"fertig nach {dauer:.0f} s: {ergebnis.testsRun} Tests, "
          f"{len(ergebnis.errors)} Fehler, {len(ergebnis.failures)} Fehlschlaege, "
          f"{len(ergebnis.skipped)} uebersprungen", flush=True)

    zeilen = [f"R13bd-Audit {time.strftime('%Y-%m-%d %H:%M:%S')}",
              "Lebende Wurzeln: " + " | ".join(f"{k}={v}" for k, v in LIVE.items()),
              f"Ausgenommen: {TESTS}/_tmp*, {TESTS}/fixtures (Fixture = eingefroren, kein "
              "lebender Pfad)",
              f"Testreihe: {ergebnis.testsRun} Tests in {dauer:.0f} s, "
              f"{len(ergebnis.errors)} Fehler, {len(ergebnis.failures)} Fehlschlaege, "
              f"{len(ergebnis.skipped)} uebersprungen",
              f"Skips: " + (", ".join(f"{t.__class__.__module__}.{t}" for t, _ in ergebnis.skipped)
                            or "(keine)"),
              "",
              f"== Tests, die lebende Dateien anfassen: {len(_treffer)} =="]
    roh = []
    for name in sorted(_treffer, key=lambda n: (n.split(":")[0], n)):
        formen: dict = {}
        if ":" in name:            # "(Modulimport)" hat keinen Klassen-/Testnamen
            datei, rest = name.split(":", 1)
            if "." in rest:
                klasse, test = rest.split(".", 1)
                formen = bauformen(datei, klasse, test)
        eintrag = {"test": name, "pfade": sorted(_treffer[name]), **formen}
        roh.append(eintrag)
    # Rohdaten zuerst schreiben: die Formatierung unten darf den Lauf nicht kosten.
    roh_ziel.write_text(json.dumps(roh, indent=1, ensure_ascii=False), encoding="utf-8",
                        newline="\n")
    for eintrag in roh:
        formen = eintrag
        verdacht = []
        if formen.get("if_ohne_else"):
            verdacht.append(f"A(if {formen['if_ohne_else']})")
        if formen.get("for_ohne_assert"):
            verdacht.append(f"B(for {formen['for_ohne_assert']})")
        if formen.get("leere_zusicherung"):
            verdacht.append("C(leere Zusicherung)")
        zeilen.append(f"\n{eintrag['test']}")
        zeilen.append("  Pfade: " + "; ".join(eintrag["pfade"]))
        zeilen.append(f"  Zusicherungen: {formen.get('asserts')}"
                      + (f"   VERDACHT: {', '.join(verdacht)}" if verdacht else ""))
    ROH.write_text(json.dumps(roh, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    roh_ziel.write_text(json.dumps(roh, indent=1, ensure_ascii=False), encoding="utf-8",
                        newline="\n")
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {ziel.name}, {roh_ziel.name} ({len(roh)} Eintraege)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
