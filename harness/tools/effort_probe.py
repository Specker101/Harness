"""Effort-Nachweis: kommt die Denkstufe wirklich an? (Vorarbeit zum DeepSeek-Umschalter)

Zweck.  Bevor die Aussensicht auf DeepSeek umgestellt wird, muss BELEGT sein, dass die
gewaehlte Denkstufe (`--effort low|medium|high|xhigh|max`, `docs/_r13ar_cli_hilfe.txt:81`)
auf dem Endpunkt wirklich ankommt.  Sonst vergleicht ein spaeterer Test zweimal dieselbe
Stufe und wundert sich ueber gleiche Ergebnisse.

Warum nicht aus dem Mitschnitt.  Der Mitschnitt der echten Aussensicht traegt KEIN
Effort-Feld (gemessen 2026-10-09: `runs/b313/meta.jsonl` enthaelt weder `perTurnEffort`
noch `"effort"`).  Der einzige im Projekt belegte Kanal ist der PostToolUse-Hook: sein
stdin traegt unter anderem das Feld `effort` (`docs/_r13ar_hook_eingabe.txt:4`).  Dieses
Werkzeug haengt einen Hook an, der AUSSCHLIESSLICH `hook_event_name`, `effort`,
`duration_ms` und `session_id` mitschreibt - keine Dateiinhalte, keine Pfade, keine
Werkzeugantworten.

WEGGELASSEN
    Es laeuft KEINE Aussensicht: kein `build_prompt`, kein Register, keine Verdikte,
    kein `schreibe_rate_limit`, keine `meta.*`-Datei.  Der Auftrag ist ein Einzeiler
    ("lies eine Datei, antworte OK").  `harness.toml` bleibt unberuehrt.
NICHT ZULAESSIG
    Aussagen ueber die QUALITAET einer Antwort.  Gemessen wird ausschliesslich, welche
    Denkstufe die Sitzung fuehrt und welches Modell geantwortet hat.  Ein "max ist
    besser" laesst sich mit diesem Werkzeug NICHT belegen.

Anbieter.  Nur DeepSeek.  Das Claude-Abo wird hier absichtlich NICHT angefasst - das
Wochenkontingent ist knapp.  Die Umgebung kommt aus `hx.envs.aussensicht_deepseek_env`
(EINE Quelle, dieselbe Bauart wie der Worker), mit eigenem `CLAUDE_CONFIG_DIR` und
waehlbarer Denkstufe.
Das eigene Verzeichnis ist Absicht: `cc-worker` gehoert dem laufenden Worker, und
`.claude.json` wird von der CLI gelesen-geaendert-geschrieben - zwei Prozesse darin
koennen sich gegenseitig den Stand zerkratzen.

Aufruf:

    python tools/effort_probe.py --trocken                 # nur zeigen, kein Lauf
    python tools/effort_probe.py --ja                      # high und max messen
    python tools/effort_probe.py --ja --stufe xhigh --stufe max
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hx import aussensicht, envs, secrets, streamjson          # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.proc import run_stream                                 # noqa: E402
from hx.util import read_text, write_text_atomic               # noqa: E402

STUFEN_VORGABE = ("high", "max")
# Der DeepSeek-Name kommt aus der Konfiguration: erst `aussensicht_modell_deepseek`
# (gibt es noch nicht - kommt mit dem Umschalter), sonst der Modellname des Workers
# (`[claude] model_worker` = DeepSeek V4.1 Flash).  Eine Quelle, kein zweiter Name.
MODELL_VORGABE = "deepseek-flash[1m]"
# Der Auftrag: ein einziger Werkzeugaufruf, damit der PostToolUse-Hook ueberhaupt feuert.
PROMPT = "Lies die Datei readme.md und antworte danach ausschliesslich mit dem Wort OK."
PROBE_DATEI = "readme.md"

# Der Hook.  Er liest sein stdin (JSON) und schreibt NUR die vier Felder weg, die die
# Frage beantworten.  Kein stdout - der Hook-Kontext soll das Modell nicht stoeren.
DUMP_SKRIPT = '''\
import json, sys
felder = ("hook_event_name", "effort", "duration_ms", "session_id")
try:
    d = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
if not isinstance(d, dict):
    raise SystemExit(0)
zeile = {k: d.get(k) for k in felder if k in d}
with open(sys.argv[1], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(zeile, ensure_ascii=False) + "\\n")
raise SystemExit(0)
'''


def dump_skript_anlegen() -> Path:
    """Das Hook-Skript nach `%TEMP%` schreiben (das Repo bleibt sauber)."""
    p = Path(tempfile.gettempdir()) / "effort_probe_hook.py"
    write_text_atomic(p, DUMP_SKRIPT)
    return p


def hook_datei(dump: Path, ausgabe: Path) -> Path:
    """Einstellungsdatei mit genau EINEM PostToolUse-Hook - Bau wie `aussensicht`."""
    daten = {"hooks": {"PostToolUse": [{"hooks": [{
        "type": "command", "timeout": 10, "command": sys.executable,
        "args": [str(dump), str(ausgabe)]}]}]}}
    p = Path(tempfile.gettempdir()) / "effort_probe_hooks.json"
    write_text_atomic(p, json.dumps(daten, indent=1) + "\n")
    return p


def config_dir_vorbereiten(cfg) -> Path:
    """Eigenes `CLAUDE_CONFIG_DIR` anlegen und mit dem Worker-Stand impfen.

    Der Ordner kommt aus `[claude] config_dir_aussensicht` - derselben Quelle, die
    `hx.envs.aussensicht_deepseek_env` benutzt.  Die CLI liest beim Start `.claude.json`
    (Erststart-Merker).  Fehlt sie in einem frischen Ordner, faellt die Sitzung in den
    Erststart-Pfad - deshalb wird der bekannte Stand aus dem Worker-Ordner KOPIERT
    (der Worker bleibt unberuehrt).
    """
    vorgabe = Path(cfg.root) / "cc-aussensicht"
    d = Path(str(cfg.get("claude", "config_dir_aussensicht", vorgabe)))
    d.mkdir(parents=True, exist_ok=True)
    ziel = d / ".claude.json"
    if not ziel.is_file():
        quelle = Path(str(cfg.get("claude", "config_dir_worker"))) / ".claude.json"
        if quelle.is_file():
            shutil.copyfile(quelle, ziel)
    return d


def deepseek_env(cfg, stufe: str) -> dict:
    """Die DeepSeek-Umgebung der Aussensicht - EINE Quelle: `hx.envs`.

    Kein Nachbau hier: Endpunkt, Token, Konfigordner, Werkzeug-Zeitgrenzen und die
    Abschaltungen stehen in `hx/envs.py` (`aussensicht_deepseek_env`); dieses Werkzeug
    waehlt nur die Denkstufe.
    """
    token = secrets.load(cfg.secrets_dir, secrets.DEEPSEEK)
    return envs.aussensicht_deepseek_env(cfg, os.environ, token, stufe)


def modell_name(cfg, uebersteuern: str | None = None) -> str:
    """Der DeepSeek-Modellname fuer den Nachweis (s. `MODELL_VORGABE`)."""
    if uebersteuern:
        return uebersteuern
    for schluessel in ("aussensicht_modell_deepseek", "model_worker"):
        wert = cfg.get("claude", schluessel, None)
        if wert:
            return str(wert)
    return MODELL_VORGABE


def eine_stufe(cfg, stufe: str, wall: float, trocken: bool) -> dict:
    """Ein Messlauf.  Rueckgabe: der Befund als dict (fuer den Belegtext)."""
    dump = dump_skript_anlegen()
    ausgabe = Path(tempfile.gettempdir()) / f"effort_probe_{stufe}.jsonl"
    if ausgabe.exists():
        ausgabe.unlink()
    hooks = hook_datei(dump, ausgabe)
    cmd = aussensicht.build_command(cfg, hooks_settings=str(hooks))
    env = deepseek_env(cfg, stufe)
    befund = {"stufe": stufe, "cmd": cmd, "env": env, "rc": None, "dauer_s": 0.0,
              "modell": "", "model_usage": [], "gesehen": [], "roh": [], "runden": 0,
              "zuege": None, "subtype": "", "stream": "", "ausgabe": ausgabe}
    print(f"\n--- Stufe {stufe} ---")
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd[:11]) + " …")
    print(f"  CLAUDE_CONFIG_DIR={env['CLAUDE_CONFIG_DIR']}")
    print(f"  CLAUDE_CODE_EFFORT_LEVEL={env['CLAUDE_CODE_EFFORT_LEVEL']}")
    if trocken:
        print("  --trocken: kein Lauf.")
        return befund
    ziel = Path(tempfile.gettempdir()) / f"effort_probe_{stufe}.stream.jsonl"
    fehler = ziel.with_suffix(".err")
    t0 = time.time()
    run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=ziel, on_event=None,
                     hard_wall_s=wall, stdin_text=PROMPT, stderr_path=fehler)
    stats = streamjson.StreamStats()
    for linie in (read_text(ziel) or "").splitlines():
        stats.feed(linie)
    befund.update({"rc": run.rc, "dauer_s": run.duration_s,
                   "modell": stats.model or "", "runden": stats.runden(),
                   "zuege": stats.num_turns(),
                   "model_usage": sorted((stats.result or {}).get("modelUsage") or {}),
                   "subtype": str((stats.result or {}).get("subtype") or ""),
                   "stream": str(ziel)})
    # Der Hook hat (mindestens) einmal gefeuert, wenn der Lauf ein Werkzeug benutzt hat.
    gesehen: list[str] = []
    roh: list[str] = []
    for linie in (read_text(ausgabe) or "").splitlines():
        try:
            d = json.loads(linie)
        except ValueError:
            continue
        stufe_roh = d.get("effort")
        if stufe_roh is None:
            continue
        roh.append(json.dumps(stufe_roh, ensure_ascii=False))
        stufe_gesehen = stufe_aus(stufe_roh)
        if stufe_gesehen:
            gesehen.append(stufe_gesehen)
    befund["gesehen"] = gesehen
    befund["roh"] = roh
    print(f"  rc={run.rc} dauer={run.duration_s:.0f}s modell={stats.model or '?'} "
          f"runden={stats.runden()} modelUsage={befund['model_usage'] or '-'}")
    print(f"  Hook-Meldungen: {len(roh)} | gesehene Denkstufe(n): "
          f"{sorted(set(gesehen)) or 'KEINE'} | roh: {sorted(set(roh)) or '-'}")
    if not gesehen:
        print("  KEIN Hook-Feuer - der Auftrag hat kein Werkzeug benutzt? "
              f"(siehe {ausgabe})")
    if time.time() - t0 > wall:
        print(f"  HINWEIS: Lauf lief in die Zeitgrenze ({wall:.0f}s).")
    return befund


def stufe_aus(wert) -> str | None:
    """Die Denkstufe aus dem Hook-Feld `effort` lesen.

    GEMESSEN 2026-10-09: das Feld ist KEIN Text, sondern ein Objekt -
    `"effort": {"level": "high"}`.  Der Vergleich gegen den blossen Namen
    `high` schlug deshalb fehl, obwohl die Stufe ankam.
    """
    if isinstance(wert, dict):
        stufe = str(wert.get("level") or "").strip()
        return stufe or None
    if wert is None:
        return None
    return str(wert).strip() or None


def urteil(befund: dict) -> str:
    """Ein Satz je Stufe - und ob sie angekommen ist."""
    if befund["rc"] is None:
        return f"{befund['stufe']}: nicht gelaufen (--trocken)"
    if befund["rc"] != 0:
        return f"{befund['stufe']}: Lauf rc={befund['rc']} {befund['subtype']} - keine Aussage"
    gesehen = sorted(set(befund["gesehen"]))
    if not gesehen:
        return f"{befund['stufe']}: KEIN Hook-Feuer - Stufe nicht belegt"
    if gesehen == [befund["stufe"]]:
        return (f"{befund['stufe']}: ANGEKOMMEN (Sitzung meldet '{gesehen[0]}', "
                f"Modell {befund['modell'] or '?'}, "
                f"modelUsage {befund['model_usage'] or '-'})")
    return (f"{befund['stufe']}: ABWEICHUNG - verlangt '{befund['stufe']}', "
            f"Sitzung meldet {gesehen}")


def beleg_text(cfg, befund: list[dict]) -> str:
    zeilen = [
        "# Effort-Nachweis (tools/effort_probe.py)",
        "",
        f"- Zeitpunkt: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"- Auftrag: {PROMPT!r} (Datei {PROBE_DATEI})",
        f"- Anbieter: DeepSeek, Modell `{befund[0]['cmd'][befund[0]['cmd'].index('--model') + 1]}`",
        "- Umgebung: `hx.envs.aussensicht_deepseek_env` (`[claude] config_dir_aussensicht`)",
        "- Messkanal: PostToolUse-Hook schreibt `effort` aus seinem stdin weg "
        "(`docs/_r13ar_hook_eingabe.txt:4`); der Mitschnitt fuehrt kein Effort-Feld",
        '- Feldform (gemessen): `"effort": {"level": "<stufe>"}` - ein OBJEKT, kein Text',
        "- NICHT ZULAESSIG: Aussagen ueber die Qualitaet der Antwort",
        "",
        "| Stufe (verlangt) | rc | Dauer | Modell laut Sitzung | modelUsage | Runden | "
        "Denkstufe laut Hook | Urteil |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for b in befund:
        zeilen.append(
            f"| `{b['stufe']}` | {b['rc'] if b['rc'] is not None else '-'} "
            f"| {b['dauer_s']:.0f}s | `{b['modell'] or '-'}` "
            f"| {b['model_usage'] or '-'} | {b['runden']} "
            f"| {sorted(set(b['gesehen'])) or '-'} | {urteil(b)} |")
    zeilen += ["", "Rohform aus dem Hook:", ""]
    for b in befund:
        zeilen.append(f"- `{b['stufe']}`: {sorted(set(b.get('roh') or [])) or '-'}")
    zeilen += ["", "## Umgebungen (Werte maskiert)", ""]
    for b in befund:
        zeilen += [f"### {b['stufe']}", "", "```", envs.describe(b["env"]), "```", ""]
    return "\n".join(zeilen) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stufe", action="append", default=None,
                    help=f"mehrfach moeglich; Vorgabe {list(STUFEN_VORGABE)}")
    ap.add_argument("--trocken", action="store_true",
                    help="nur zeigen - KEIN bezahlter Lauf")
    ap.add_argument("--ja", action="store_true",
                    help="Bestaetigung fuer die bezahlten Laeufe")
    ap.add_argument("--wall", type=float, default=300.0, help="Zeitgrenze je Lauf in s")
    ap.add_argument("--modell", default=None,
                    help=f"DeepSeek-Modellname; Vorgabe aus der Konfiguration, "
                         f"sonst {MODELL_VORGABE}")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if not args.trocken and not args.ja:
        print("Abbruch: das sind bezahlte Aufrufe. Mit --ja bestaetigen "
              "(oder --trocken nur zeigen).")
        return 2
    stufen = list(args.stufe or STUFEN_VORGABE)
    modell = modell_name(cfg, args.modell)
    # Modell NUR im Speicher tauschen - `harness.toml` bleibt unberuehrt.
    cfg.data.setdefault("claude", {})["aussensicht_modell"] = modell
    config_dir = config_dir_vorbereiten(cfg)
    print(f"Effort-Nachweis | Stufen: {', '.join(stufen)} | Modell: {modell} | "
          f"Konfigordner: {config_dir}")
    print("Anbieter: DeepSeek - das Abo wird NICHT benutzt.")
    befund = [eine_stufe(cfg, s, args.wall, args.trocken) for s in stufen]
    print("\n=== Urteil ===")
    for b in befund:
        print("  " + urteil(b))
    if not args.trocken:
        ziel = Path(cfg.root).parent / "docs" / "_effort_probe.txt"
        write_text_atomic(ziel, beleg_text(cfg, befund))
        print(f"\nBeleg: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
