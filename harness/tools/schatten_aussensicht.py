"""Schatten-Aussensicht: einen Aussensicht-Lauf mit einem ANDEREN Modell wiederholen (R13bw-14).

Nur-Lese-Werkzeug - es haengt NICHT im Harness (`hx/` bleibt unberuehrt) und wird von Hand
gestartet. Zweck: dieselbe Aussensicht (gleicher Prompt, gleiche angeheftete Tiefenprobe)
mit z. B. `claude-sonnet-5-5` fahren und die Befunde/Verdikte gegen die echte `meta.md`
stellen (`tools/schatten_vergleich.py`).

WAS ES ABSICHTLICH **NICHT** TUT (Zustand bleibt unberuehrt):

  * kein `ablage_pruefen` (R13br kann einen `AblageKonflikt` werfen - hier irrelevant),
  * kein `tiefenprobe_merken` (die Ziehung wird angeheftet, nicht gezogen),
  * kein `schreibe_rate_limit` (`logs/rate-limit.json` wird nur GELESEN),
  * kein `verteile`/`uebernehmen` (der Befund-Ledger wird nicht angefasst),
  * **keine** Pfade der echten `meta.*`-Dateien - Mitschnitt und Fehlerdatei landen in
    `%TEMP%`, die Hook-Einstellungsdatei ebenfalls; geschrieben wird nur der Bericht,
    den `--ziel` nennt (Vorgabe `docs/_sonnet_vergleich_b<N>.md`).

Was es uebernimmt: dieselbe Umgebung wie die Abo-Laeufe (`hx.envs.reviewer_env` - also
dieselbe Denkstufe, `[claude] reviewer_effort`), denselben Prompt-Bau
(`hx.aussensicht.build_prompt`) und dieselbe Werkzeug-Allowlist (`build_command`: nur
Read/Grep/Glob und lesendes git). **Das Werkzeug kann deshalb nichts schreiben und
startet auch keine Hybrid-Laeufe oder Preflights** - Bash ist gar nicht erlaubt.

Aufruf:

    python tools/schatten_aussensicht.py --batch 285 --batch 289 --ja
    python tools/schatten_aussensicht.py --batch 285 --trocken      # nur zeigen, nicht laufen
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hx import aussensicht, envs, secrets, streamjson          # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.proc import run_stream                                 # noqa: E402
from hx.util import read_text, write_text_atomic               # noqa: E402

MODELL_VORGABE = "claude-sonnet-5-5"
# "- Lauf: rc=0 dauer=379s modell=claude-opus-5-5 befunde=6 ... runden=37 ... tiefenprobe=B277"
_RE_Lauf = re.compile(r"^-\s*Lauf:\s*(?P<rest>.+)$", re.M)
_RE_Tiefe = re.compile(r"^-\s*Tiefenprobe:\s*Batch\s+(?P<batch>\d+)\s+aus dem Fenster\s+"
                       r"B(?P<von>\d+)\.\.B(?P<bis>\d+)", re.M)
_RE_Vorher = re.compile(r";\s*vorher gezogen:\s*(?P<liste>[^;\n]+)")
_RE_Anlass = re.compile(r"^-\s*Anlass:\s*(?P<rest>.+)$", re.M)
_RE_Zeit = re.compile(r"^-\s*Zeitpunkt:\s*(?P<rest>.+)$", re.M)


def kopf_lesen(cfg, batch: int) -> dict:
    """Die Kopfdaten der echten Aussensicht (`runs/b<N>/meta.md`) lesen - nur lesend."""
    p = aussensicht.pfad_neu(cfg, batch, "md")
    text = read_text(p)
    if not text:
        raise SystemExit(f"kein Bericht: {p}")
    lauf = {}
    m = _RE_Lauf.search(text)
    if m:
        for stueck in m.group("rest").split():
            if "=" in stueck:
                k, v = stueck.split("=", 1)
                lauf[k.strip()] = v.strip()
    t = _RE_Tiefe.search(text)
    vorher = _RE_Vorher.search(text)
    a = _RE_Anlass.search(text)
    z = _RE_Zeit.search(text)
    return {
        "pfad": str(p),
        "lauf": lauf,
        "modell_echt": lauf.get("modell", ""),
        "anlass": a.group("rest").strip() if a else "",
        "zeitpunkt": z.group("rest").strip() if z else "",
        "tiefenprobe": ({"batch": int(t.group("batch")),
                         "fenster": list(range(int(t.group("von")), int(t.group("bis")) + 1)),
                         "gezogen": [int(x.strip().lstrip("Bb")) for x in
                                     (vorher.group("liste").split(",") if vorher else [])
                                     if x.strip()]}
                        if t else {}),
    }


def hook_datei(cfg, batch: int) -> str | None:
    """Zuguhr-Hook wie `aussensicht.write_hook_settings` - aber in `%TEMP%` (R13bw-14)."""
    skript = Path(__file__).resolve().parents[1] / "tools" / "aussensicht_uhr.py"
    if not skript.is_file():
        return None
    grenze = int(aussensicht.grenzen(cfg)["max_turns"])
    daten = {"hooks": {"PostToolUse": [{"hooks": [{
        "type": "command", "timeout": 10, "command": sys.executable,
        "args": [str(skript), "--limit", str(grenze),
                 "--frist", str(aussensicht.FRIST_ABSTAND)]}]}]}}
    ziel = Path(tempfile.gettempdir()) / f"schatten_aussensicht_hooks_b{batch}.json"
    write_text_atomic(ziel, json.dumps(daten, indent=1) + "\n")
    return str(ziel)


def bericht_schreiben(cfg, batch: int, modell: str, kopf: dict, text: str, roh: dict) -> Path:
    """Den Schattenbericht so schreiben, dass `tools/schatten_vergleich.py` ihn lesen kann.

    Kopfzeilen im selben Format wie `meta.md` (`- Lauf: …`), darunter die ROHE Antwort -
    die `<BEFUND>`/`<PRUEFUNG>`-Bloecke bleiben damit unveraendert erhalten.
    """
    ziel = Path(cfg.root).parent / "docs" / f"_sonnet_vergleich_b{batch}.md"
    tiefe = kopf["tiefenprobe"]
    zeilen = [
        f"# Schatten-Aussensicht Batch {batch} ({modell})",
        "",
        f"- Zeitpunkt: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}",
        f"- Anlass: Schattenlauf (dieselbe Eingabe wie die echte Aussensicht: "
        f"{kopf['anlass'] or '-'})",
        f"- Lauf: rc={roh['rc']} dauer={roh['dauer_s']:.0f}s modell={roh['modell'] or '-'} "
        f"befunde={roh['befunde']} verworfen={roh['verworfen']} zuege={roh['zuege']} "
        f"runden={roh['runden']} subtype={roh['subtype']} tiefenprobe=B{tiefe.get('batch')}",
        f"- Zuege (Werkzeugrunden): {roh['runden']} von "
        f"{int(aussensicht.grenzen(cfg)['max_turns'])}",
        f"- Echte Aussensicht: `{Path(kopf['pfad']).name}` mit "
        f"`{kopf['modell_echt'] or '?'}` vom {kopf.get('zeitpunkt') or '-'}",
        f"- Tiefenprobe: Batch {tiefe.get('batch')} aus dem Fenster "
        f"B{(tiefe.get('fenster') or [0])[0]}..B{(tiefe.get('fenster') or [0])[-1]} "
        f"(angeheftet, NICHT gezogen/merken) - vorher gezogen: "
        + (", ".join(f"B{b}" for b in tiefe.get("gezogen") or []) or "-"),
        f"- Nutzerlimit (Abo) VOR dem Lauf: {roh['rate_vor'] or 'keine Angabe'}",
        f"- Nutzerlimit (Abo) NACH dem Lauf: {roh['rate_nach'] or 'keine Angabe'}",
        f"- Hinweis: Mitschnitt und Fehlerdatei lagen in `%TEMP%` "
        f"(`{Path(roh['stream']).name}`); dieser Bericht ist das EINZIGE Artefakt im Repo.",
        "",
        "## Antwort (roh)",
        "",
        text.strip(),
        "",
    ]
    write_text_atomic(ziel, "\n".join(zeilen))
    return ziel


def tiefe_anhaften(batch: int, kopf: dict) -> dict:
    """Die damalige Ziehung nachbauen (`build_prompt` bekommt sie fertig uebergeben)."""
    t = kopf["tiefenprobe"]
    if not t.get("batch"):
        raise SystemExit(f"B{batch}: im Kopf steht keine Tiefenprobe")
    return {"batch": int(t["batch"]), "fenster": list(t["fenster"]),
            "gezogen": list(t.get("gezogen") or []),
            "kandidaten": [int(t["batch"])], "neu_zyklus": False,
            "grund": "Schattenlauf: dieselbe Ziehung wie die echte Aussensicht"}


def ein_lauf(cfg, batch: int, modell: str, trocken: bool) -> int:
    kopf = kopf_lesen(cfg, batch)
    tiefe = tiefe_anhaften(batch, kopf)
    from hx import state as st_mod
    state = st_mod.State(Path(cfg.sub("state")) / "run.json")
    grund = f"Schattenlauf {modell} (B{batch})"
    prompt = aussensicht.build_prompt(cfg, state, grund, tiefe=tiefe)
    # Modell NUR im Speicher tauschen - `harness.toml` bleibt unberuehrt.
    cfg.data.setdefault("claude", {})["aussensicht_modell"] = modell
    hooks = hook_datei(cfg, batch)
    cmd = aussensicht.build_command(cfg, hooks_settings=hooks)
    print(f"B{batch}: echtes Modell war {kopf['modell_echt'] or '?'}, "
          f"Tiefenprobe B{tiefe['batch']} aus B{tiefe['fenster'][0]}..B{tiefe['fenster'][-1]}")
    print("  " + " ".join(f'"{c}"' if " " in c else c for c in cmd[:12]) + " …")
    if trocken:
        print("  --trocken: kein Lauf.")
        return 0
    rate_vor = streamjson.rate_limit_zeile((streamjson.lies_rate_limit(cfg) or {}).get("info")
                                           or {})
    ziel = Path(tempfile.gettempdir()) / f"schatten_aussensicht_b{batch}.jsonl"
    fehler = ziel.with_suffix(".jsonl.err")
    oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
    env = envs.reviewer_env(cfg, os.environ, oauth)
    g = aussensicht.grenzen(cfg)
    t0 = time.time()
    run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=ziel, on_event=None,
                     hard_wall_s=float(g["wall_s"]), stdin_text=prompt,
                     stderr_path=fehler)
    stats = streamjson.StreamStats()
    for linie in (read_text(ziel) or "").splitlines():
        stats.feed(linie)
    text = stats.final_text() or ""
    summary, befunde, verworfen, pruefungen = aussensicht.parse(text, int(g["max_befunde"]))
    rate_nach = streamjson.rate_limit_zeile(stats.rate_limit or {})
    roh = {"rc": run.rc, "dauer_s": run.duration_s, "modell": stats.model or "",
           "befunde": len(befunde), "verworfen": len(verworfen), "zuege": stats.num_turns(),
           "runden": stats.runden(), "subtype": str((stats.result or {}).get("subtype") or ""),
           "rate_vor": rate_vor, "rate_nach": rate_nach, "stream": str(ziel)}
    p = bericht_schreiben(cfg, batch, modell, kopf, text, roh)
    print(f"  fertig: rc={run.rc} dauer={run.duration_s:.0f}s modell={stats.model or '?'} "
          f"runden={stats.runden()} befunde={len(befunde)} (verworfen {len(verworfen)}) "
          f"| {time.time() - t0:.0f}s")
    print(f"  Rate-Limit vor : {rate_vor or 'keine Angabe'}")
    print(f"  Rate-Limit nach: {rate_nach or 'keine Angabe'}")
    print(f"  Bericht: {p}")
    return 0 if run.rc == 0 else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", type=int, action="append", required=True,
                    help="Batchnummer der echten Aussensicht (mehrfach moeglich)")
    ap.add_argument("--modell", default=MODELL_VORGABE, help=f"Vorgabe {MODELL_VORGABE}")
    ap.add_argument("--trocken", action="store_true",
                    help="nur Prompt/Kommandozeile zeigen - KEIN bezahlter Lauf")
    ap.add_argument("--ja", action="store_true",
                    help="Bestaetigung fuer die bezahlten Laeufe (ohne --ja nur --trocken)")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if not args.trocken and not args.ja:
        print("Abbruch: das sind bezahlte Abo-Laeufe. Mit --ja bestaetigen "
              "(oder --trocken nur zeigen).")
        return 2
    rc = 0
    for batch in args.batch:
        rc |= ein_lauf(cfg, batch, args.modell, args.trocken)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
