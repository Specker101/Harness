"""R13v-Nachprobe (2026-09-28): faengt `--disallowedTools PowerShell(Start-Sleep*)`
auch einen Befehl, der NICHT mit `Start-Sleep` beginnt?

Kein Mustertest. Hier laeuft der ECHTE `claude`-Prozess mit GENAU der Kommandozeile
des Workers (`hx.worker.build_command`, Profil "none" - der einzige Unterschied ist
die um je eine Regel erweiterte Sperrliste) und mit der Umgebung des Workers
(`hx.envs.worker_env`). Das Modell bekommt einen Befehl wortwoertlich zum Ausfuehren;
bewertet wird, was im Mitschnitt steht (tool_use-Eingabe + tool_result), nicht was
das Modell behauptet.

Aufruf:
    python tools/r13v_sperrprobe.py                 # alle Faelle in docs/_r13v_sperrprobe.txt
    python tools/r13v_sperrprobe.py --nur kontrolle # einzelner Fall

Faelle:
  kontrolle        `Start-Sleep -Seconds 3`                 Sperre unveraendert
  schleife         for-Schleife mit Start-Sleep             Sperre unveraendert
  schleife_stern   dieselbe Schleife                        + PowerShell(*Start-Sleep*)
  schleife_deny2   dieselbe Schleife                        + PowerShell(for *)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER / "harness"))

from hx import envs, secrets  # noqa: E402
from hx.config import load_config  # noqa: E402
from hx.proc import run_stream  # noqa: E402
from hx.profiles import load_profile  # noqa: E402
from hx import worker as wkmod  # noqa: E402

AUS = HIER / "docs" / "_r13v_sperrprobe.txt"
SANDBOX = HIER / "sandbox" / "sperrprobe"

# Der Befehl aus der Nutzerfrage (hausinternes Beispiel aus B207, nur kuerzer).
SCHLEIFE = ('for ($i=0; $i -lt 40; $i++) { if (-not (Get-Process -Id 1 -EA 0)) '
            '{ break }; Start-Sleep -Seconds 20 }')
# Dieselbe Schleife mit dem PowerShell-ALIAS `sleep` statt `Start-Sleep` - so laesst
# sich pruefen, ob die Sperre an der Zeichenkette haengt oder an der Arbeitsweise.
SCHLEIFE_ALIAS = ('for ($i=0; $i -lt 40; $i++) { if (-not (Get-Process -Id 1 -EA 0)) '
                  '{ break }; sleep -Seconds 20 }')
NAKTER_SCHLAF = "Start-Sleep -Seconds 3"

FAELLE = [
    ("kontrolle", NAKTER_SCHLAF, []),
    ("schleife", SCHLEIFE, []),
    ("schleife_stern", SCHLEIFE, ["PowerShell(*Start-Sleep*)"]),
    ("schleife_deny2", SCHLEIFE, ["PowerShell(for *)"]),
    # Isolierung: laeuft das Werkzeug ueberhaupt, und wie wird verglichen?
    ("echo_kontrolle", 'Write-Output "hallo"', []),
    ("if_sleep", "if ($true) { Start-Sleep -Seconds 3 }", []),
    ("stueck_sleep", 'Write-Output "a"; Start-Sleep -Seconds 3', []),
    ("alias_schleife", SCHLEIFE_ALIAS, []),
    # Wie vergleicht der Werkzeugkasten? Auf der Wortzeichenkette oder auf dem Befehl?
    ("zitat_sleep", 'Write-Output "Start-Sleep -Seconds 3"', []),
    ("alias_allein", "sleep -Seconds 3", []),
    ("fremder_schlaf", "[Threading.Thread]::Sleep(2000)", []),
]

PROMPT = """Du bist eine Messsonde. Fuehre GENAU den folgenden Befehl aus - Zeichen fuer
Zeichen unveraendert, mit dem PowerShell-Werkzeug:

{cmd}

Regeln:
- Kein Ersatzbefehl, keine Umschreibung, kein Weglassen von Teilen, keine eigene Datei.
- Wird der Aufruf VERWEIGERT oder BLOCKIERT: antworte mit der Zeile
  "ERGEBNIS: BLOCKIERT" und danach dem wortwoertlichen Text der Verweigerung.
- Wird der Aufruf ausgefuehrt: antworte mit der Zeile "ERGEBNIS: AUSGEFUEHRT" und
  danach dem wortwoertlichen Ergebnis (Exit-Code, Ausgabe).
- Sonst nichts: keine Erklaerungen, keine weiteren Werkzeuge.
"""


def cmd_fuer_fall(cfg, extra: list[str], lauf: Path) -> list[str]:
    """Worker-Kommandozeile; nur die Sperrliste wird um `extra` erweitert."""
    cmd, _mcp = wkmod.build_command(cfg, load_profile(cfg.root, "none"), lauf,
                                    str(uuid.uuid4()))
    if extra:
        i = cmd.index("--disallowedTools")
        cmd[i + 1:i + 1] = extra
    return cmd


def _tool_use_befehl(zeilen: list[str], name: str) -> str | None:
    for zeile in reversed(zeilen):
        try:
            ev = json.loads(zeile)
        except (ValueError, TypeError):
            continue
        if ev.get("type") != "assistant":
            continue
        for teil in (ev.get("message") or {}).get("content") or []:
            if teil.get("type") == "tool_use" and teil.get("name") == name:
                return str((teil.get("input") or {}).get("command", ""))
    return None


def _tool_results(zeilen: list[str]) -> list[str]:
    out: list[str] = []
    for zeile in zeilen:
        try:
            ev = json.loads(zeile)
        except (ValueError, TypeError):
            continue
        if ev.get("type") != "user":
            continue
        for teil in (ev.get("message") or {}).get("content") or []:
            if teil.get("type") != "tool_result":
                continue
            inhalt = teil.get("content")
            if isinstance(inhalt, list):
                inhalt = " ".join(str((c or {}).get("text", "")) for c in inhalt)
            out.append(str(inhalt or ""))
    return out


def _modell_text(zeilen: list[str]) -> str:
    teile: list[str] = []
    for zeile in zeilen:
        try:
            ev = json.loads(zeile)
        except (ValueError, TypeError):
            continue
        if ev.get("type") == "assistant":
            for teil in (ev.get("message") or {}).get("content") or []:
                if teil.get("type") == "text":
                    teile.append(str(teil.get("text", "")))
    return "\n".join(teile).strip()


VERWEIGERUNG = re.compile(r"denied|not allowed|blocked|verweigert|"
                          r"permission to use|requires approval|disallowed",
                          re.IGNORECASE)


def urteil(zeilen: list[str], erwarteter_befehl: str) -> tuple[str, str]:
    """(Urteil, Begruendung) aus dem Mitschnitt - nicht aus der Modellprosa."""
    bufehl = _tool_use_befehl(zeilen, "PowerShell")
    results = _tool_results(zeilen)
    if bufehl is None:
        return "KEIN AUFRUF", ("das Modell hat das PowerShell-Werkzeug nicht aufgerufen; "
                               "Mitschnitt zeigt keinen tool_use-PowerShell-Block")
    gleich = bufehl.strip() == erwarteter_befehl.strip()
    kopf = ("Befehl im Mitschnitt " + ("wortgleich" if gleich else "ABWEICHEND")
            + f": {bufehl.strip()[:160]!r}")
    if not results:
        return "UNKLAR", kopf + " | kein tool_result im Mitschnitt"
    for r in results:
        if VERWEIGERUNG.search(r):
            return "BLOCKIERT", kopf + f" | tool_result: {r.strip()[:300]!r}"
    return "AUSGEFUEHRT", kopf + f" | tool_result: {results[0].strip()[:300]!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nur", default="", help="nur diesen Fall fahren")
    ap.add_argument("--timeout", type=float, default=240.0, help="Wanduhr je Fall")
    args = ap.parse_args()

    cfg = load_config()
    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    # WICHTIG: `os.environ` selbst uebergeben, NICHT `dict(os.environ)` - die
    # Windows-Umgebung ist in Python nur als `_Environ` unempfindlich gegen
    # Gross-/Kleinschreibung; als reines dict faellt z. B. "SystemRoot" weg und
    # `claude.exe` (Bun) startet mit rc=1 ("%SystemRoot% ... is not set").
    env = envs.worker_env(cfg, os.environ, token)
    SANDBOX.mkdir(parents=True, exist_ok=True)

    zeilen = ["# R13v-Nachprobe: faengt PowerShell(Start-Sleep*) auch die Schleife?",
              f"# erzeugt {time.strftime('%Y-%m-%d %H:%M:%S')} von tools/r13v_sperrprobe.py",
              f"# claude:  {cfg.get('claude', 'exe')}",
              f"# Modell:  {cfg.get('claude', 'model_worker')} (Basis {cfg.get('claude', 'base_url')})",
              "# Kommandozeile: hx.worker.build_command (wie im echten Batch), Profil 'none'",
              "# Umgebung:      hx.envs.worker_env (wie im echten Batch)",
              ""]
    ergebnisse: list[tuple[str, str, str]] = []

    for name, befehl, extra in FAELLE:
        if args.nur and args.nur != name:
            continue
        lauf = SANDBOX / name
        lauf.mkdir(parents=True, exist_ok=True)
        cmd = cmd_fuer_fall(cfg, extra, lauf)
        i_deny = cmd.index("--disallowedTools")
        ende = next((k for k in range(i_deny + 1, len(cmd)) if cmd[k].startswith("--")), len(cmd))
        deny = cmd[i_deny + 1:ende]
        zeilen += [f"======== Fall {name} ========",
                   f"Zusatz-Sperre : {extra or '(keine - wie im echten Batch)'}",
                   "Sperrliste    : " + " ".join(repr(d) for d in deny),
                   "Befehl an das Modell:", "  " + befehl, ""]
        t0 = time.time()
        run = run_stream(cmd, env, cwd=str(SANDBOX),
                         out_path=lauf / "stream.jsonl", hard_wall_s=args.timeout,
                         stdin_text=PROMPT.format(cmd=befehl),
                         stderr_path=lauf / "stream.err.txt")
        dauer = round(time.time() - t0, 1)
        roh = (lauf / "stream.jsonl").read_text(encoding="utf-8", errors="replace")
        urt, grund = urteil(roh.splitlines(), befehl)
        ergebnisse.append((name, urt, grund))
        zeilen += [f"rc={run.rc}  Dauer={dauer}s  Zeilen={run.lines}",
                   f"URTEIL: {urt}",
                   f"Begruendung: {grund}",
                   "Modell-Antwort (Auszug):",
                   "  " + _modell_text(roh.splitlines())[:600].replace("\n", "\n  "),
                   ""]

    zeilen += ["======== Zusammenfassung ========"]
    for name, urt, _g in ergebnisse:
        zeilen.append(f"  {name:16s} -> {urt}")
    AUS.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print("\n".join(zeilen))
    print(f"\n# Beleg: {AUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
