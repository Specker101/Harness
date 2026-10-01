"""R13bg (nur lesend): Rechnerlast der Batches B228-B234 auswerten.

Frage des Nutzers (2026-10-01): je Batch `cpu_mittel`, `cpu_max`, `ram_frei_min`,
`fremdlast_minuten`, `last_proben` - wie viele Minuten lag der freie RAM unter 500 bzw.
200 MB, und lief in diesen Minuten ein `hybrid_lauf`, Preflight oder Bau? Gegenfrage: wie
viele Minuten lag die CPU ueber 90 %? Einschaetzung Speicher gegen CPU.

**Befund der Datenlage:** `result.json` traegt nur **Kennzahlen** (Mittel, Spitze,
Minimum) - die Minutenreihe selbst (`hx/last.py:Recorder.proben`) lebt nur im Speicher
des Harness und wird NICHT abgelegt. Die Zahl der Minuten unter einer Schwelle ist daraus
deshalb nur als **Schranke** ableitbar (0, wenn die Schwelle nie erreicht wurde; sonst
mindestens 1, hoechstens `last_proben`). Was dagegen gemessen werden kann: welche Minuten
eines Batches mit Arbeit belegt waren (Preflight, `hybrid_lauf`, Bau) - aus den
Zeitstempeln der Werkzeugaufrufe im Mitschnitt.

    python -u docs/_r13bg_last.py        -> docs/_r13bg_last.txt
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from hx import last, stand, streamjson                                # noqa: E402
from hx.config import load_config                                     # noqa: E402

BATCHES = range(228, 235)
# Die Zuordnung der Arbeit zu einem Werkzeugaufruf (Rohbefehl, klein geschrieben).
KLASSEN = (
    ("Preflight", lambda c: streamjson.ist_preflight_aufruf("PowerShell", {"command": c})),
    ("hybrid_lauf", lambda c: "hybrid_lauf" in c),
    ("Bau", lambda c: bool(re.search(r"port_build|mingw32-make|\bmake \b|g\+\+", c))),
)


def _iso(text: str):
    return stand._iso_zeit(text)


def mitschnitt(rd: Path) -> list[Path]:
    """Die Mitschnitte des LAUFENDEN Laufs (`stream.jsonl` + Fortsetzungen).

    `stream-v1.jsonl` ist die weggesicherte Fassung eines VORIGEN (abgebrochenen) Laufs
    desselben Batchordners (R13v3, `sichere_vorgaenger`) - sie gehoert nicht zu den
    Kennzahlen in `result.json` und wird deshalb getrennt gemeldet.
    """
    return [p for p in ([rd / "stream.jsonl"] + sorted(rd.glob("stream-forts*.jsonl")))
            if p.is_file()]


def arbeit(rd: Path) -> dict:
    """Welche Minuten eines Batches waren mit Preflight/hybrid_lauf/Bau belegt?"""
    aufrufe: list[tuple[str, str, str]] = []          # (klasse, start-iso, ende-iso)
    for p in mitschnitt(rd):
        offen: dict[str, tuple[str, str]] = {}
        try:
            zeilen = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for zeile in zeilen:
            if '"tool_use"' not in zeile and '"tool_result"' not in zeile:
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(satz, dict):
                continue
            nachricht = satz.get("message")
            if not isinstance(nachricht, dict):
                continue
            for b in nachricht.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    cmd = str((b.get("input") or {}).get("command") or "").lower()
                    if not cmd:
                        continue
                    for name, trifft in KLASSEN:
                        if trifft(cmd):
                            offen[str(b.get("id"))] = (name, str(satz.get("timestamp") or ""))
                            break
                elif b.get("type") == "tool_result":
                    k = offen.pop(str(b.get("tool_use_id")), None)
                    if k:
                        aufrufe.append((k[0], k[1], str(satz.get("timestamp") or "")))
        for k in offen.values():                       # ohne Ergebnis (Abbruch)
            aufrufe.append((k[0], k[1], ""))
    return {"aufrufe": aufrufe}


def minuten_belegt(aufrufe: list[tuple[str, str, str]], start, ende) -> dict:
    """Je Klasse: Anzahl Minuten (relativ zum Start), in denen sie lief."""
    belegt: dict[str, set[int]] = {}
    dauer: dict[str, float] = {}
    for name, s, e in aufrufe:
        t0, t1 = _iso(s), _iso(e)
        if t0 is None:
            continue
        if t1 is None or t1 < t0:
            t1 = t0
        dauer[name] = dauer.get(name, 0.0) + (t1 - t0).total_seconds()
        if start is not None:
            von = max(0, int((t0 - start).total_seconds() // 60))
            bis = max(0, int((t1 - start).total_seconds() // 60))
            for m in range(von, bis + 1):
                belegt.setdefault(name, set()).add(m)
    return {"minuten": {k: sorted(v) for k, v in belegt.items()},
            "dauer_min": {k: round(v / 60.0, 1) for k, v in dauer.items()}}


def schranke(minimum, grenze: int, proben: int) -> tuple[int, int]:
    """(mindestens, hoechstens) Minuten unter/ueber der Grenze - nur aus Min/Max."""
    if minimum is None:
        return 0, 0
    if (grenze >= 0 and minimum >= grenze) if grenze >= 0 else False:
        return 0, 0
    return 1, proben


def maschine_extra() -> dict:
    """CPU-Name (Registry) und Spitze der Auslagerungsdatei (WMI) - nur lesend."""
    aus: dict = {"cpu_name": "", "pagefile_peak_mb": None}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            aus["cpu_name"] = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
    except OSError:
        pass
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_PageFileUsage | Select-Object -First 1 "
             "-ExpandProperty PeakUsage)"], capture_output=True, text=True, timeout=180)
        roh = (r.stdout or "").strip()
        aus["pagefile_peak_mb"] = int(roh) if roh.isdigit() else None
        aus["pagefile_roh"] = f"rc={r.returncode} out={roh[:40]!r} err={r.stderr[:120]!r}"
    except Exception as exc:                                       # noqa: BLE001
        aus["pagefile_roh"] = f"{type(exc).__name__}: {exc}"
    return aus


def main() -> int:
    cfg = load_config()
    z: list[str] = []
    z.append("R13bg - Rechnerlast B228-B234 (nur lesend aus runs/b<N>/result.json)")
    z.append("Quelle der Kennzahlen: hx/last.py (Recorder, Takt 60 s, psutil)")
    z.append("")
    m = last.maschine()
    extra = maschine_extra()
    z.append(f"Maschine JETZT gemessen: {extra['cpu_name'] or '(CPU-Name nicht gelesen)'} - "
             f"{m.get('kerne')} Kerne / {m.get('threads')} Threads, "
             f"RAM gesamt {m.get('ram_gesamt_mb')} MB [Quelle {m.get('quelle')}]")
    if extra.get("pagefile_peak_mb") is not None:
        z.append(f"  Auslagerungsdatei: Spitze {extra['pagefile_peak_mb']} MB "
                 f"(Zeitpunkt nicht je Batch erfasst)")
    else:
        z.append(f"  Auslagerungsdatei-Spitze nicht gelesen ({extra.get('pagefile_roh')})")
    z.append("")
    kopf = (f"{'Batch':>6} {'proben':>6} {'cpu_mittel':>10} {'cpu_max':>8} {'RAM frei min':>13} "
            f"{'fremdlast':>10} {'fremd_max':>9} {'ghidra_max':>10} {'eigene_max':>10} {'quelle':>7}")
    z.append(kopf)
    z.append("-" * len(kopf))
    daten: dict[int, dict] = {}
    for b in BATCHES:
        p = HARNESS / "runs" / f"b{b:03d}" / "result.json"
        if not p.is_file():
            z.append(f"{b:>6}   keine result.json")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        daten[b] = d
        z.append(f"{b:>6} {str(d.get('last_proben')):>6} {str(d.get('cpu_mittel')):>10} "
                 f"{str(d.get('cpu_max')):>8} {str(d.get('ram_frei_min')):>13} "
                 f"{str(d.get('fremdlast_minuten')):>10} {str(d.get('last_fremd_max')):>9} "
                 f"{str(d.get('last_ghidra_max')):>10} "
                 f"{str(d.get('last_eigene_max')):>10} "
                 f"{str(d.get('last_quelle')):>7}")
    z.append("")
    z.append("Fremde Prozessnamen (Grundrauschen, ueber alle Batches): "
             + ", ".join(sorted({n for d in daten.values()
                                 for n in (d.get("last_fremde_namen") or [])})))
    z.append("")
    z.append("Schranken aus Minimum/Spitze (die Minutenreihe selbst liegt NICHT in")
    z.append("result.json - `last.py:Recorder.proben` lebt nur im Speicher):")
    z.append(f"{'Batch':>6} {'RAM<500':>18} {'RAM<200':>18} {'CPU>90':>18}")
    for b, d in daten.items():
        proben = int(d.get("last_proben") or 0)
        r = d.get("ram_frei_min")
        c = d.get("cpu_max")
        ram500 = ("0 min (nie erreicht)" if (r is not None and r >= 500)
                  else (f"1..{proben} min" if r is not None else "nicht gemessen"))
        ram200 = ("0 min (nie erreicht)" if (r is not None and r >= 200)
                  else (f"1..{proben} min" if r is not None else "nicht gemessen"))
        cpu90 = ("0 min (nie erreicht)" if (c is not None and c <= 90)
                 else (f"1..{proben} min" if c is not None else "nicht gemessen"))
        z.append(f"{b:>6} {ram500:>18} {ram200:>18} {cpu90:>18}")
    z.append("")
    z.append("Arbeit im Mitschnitt (welche Minuten des Batches belegt waren):")
    z.append(f"{'Batch':>6} {'Wanduhr':>8} {'RAM frei min':>13} {'Preflight':>22} "
             f"{'hybrid_lauf':>22} {'Bau':>22}")
    for b, d in daten.items():
        rd = HARNESS / "runs" / f"b{b:03d}"
        start = None
        if d.get("finished_at") and d.get("duration_s"):
            e = _iso(d["finished_at"])
            if e is not None:
                start = datetime.fromtimestamp(
                    e.timestamp() - float(d["duration_s"]), tz=e.tzinfo)
        a = arbeit(rd)
        mb = minuten_belegt(a["aufrufe"], start, None)
        wand = float(d.get("duration_s") or 0) / 60.0

        def spalte(name: str) -> str:
            ms = mb["minuten"].get(name) or []
            dm = mb["dauer_min"].get(name) or 0.0
            if not ms:
                return "-"
            return f"{len(ms)} von {int(wand)} min ({dm:.0f} min Arbeit)"

        z.append(f"{b:>6} {wand:>7.0f}m {str(d.get('ram_frei_min')):>13} "
                 f"{spalte('Preflight'):>22} "
                 f"{spalte('hybrid_lauf'):>22} {spalte('Bau'):>22}")
    z.append("")
    z.append("Arbeitsminuten im Wortlaut (Minutenindex im Batch):")
    for b, d in daten.items():
        rd = HARNESS / "runs" / f"b{b:03d}"
        start = None
        if d.get("finished_at") and d.get("duration_s"):
            e = _iso(d["finished_at"])
            if e is not None:
                start = datetime.fromtimestamp(
                    e.timestamp() - float(d["duration_s"]), tz=e.tzinfo)
        mb = minuten_belegt(arbeit(rd)["aufrufe"], start, None)
        teile = []
        for name in ("Preflight", "hybrid_lauf", "Bau"):
            ms = mb["minuten"].get(name) or []
            if ms:
                teile.append(f"{name}: {ms[0]}..{ms[-1]} ({len(ms)} min)")
        z.append(f"  B{b}: " + "; ".join(teile or ["keine Arbeit klassifiziert"]))
    z.append("")
    z.append("Speicher JETZT (Kontext, nicht Batch-Messung):")
    ps = last._psutil()
    if ps is not None:
        v = ps.virtual_memory()
        s = ps.swap_memory()
        z.append(f"  RAM gesamt {v.total / 1048576:.0f} MB, verfuegbar "
                 f"{v.available / 1048576:.0f} MB ({v.percent:.0f} % belegt)")
        z.append(f"  Auslagerungsdatei gesamt {s.total / 1048576:.0f} MB, benutzt "
                 f"{s.used / 1048576:.0f} MB ({s.percent:.0f} %)")
        gross = []
        for p in ps.process_iter(["pid", "name", "memory_info"]):
            try:
                gross.append((int(p.info["memory_info"].rss), int(p.info["pid"]),
                              str(p.info.get("name") or "")))
            except Exception:                                      # noqa: BLE001
                continue
        gross.sort(reverse=True)
        z.append("  groesste Verbraucher jetzt (RSS):")
        for rss, pid, name in gross[:8]:
            z.append(f"    {name:<22} pid {pid:<8} {rss / 1048576:>7.0f} MB")
    z.append("")
    z.append("Abgebrochene Vorgaengerlaeufe im Batchordner (nicht mitgezaehlt):")
    for b in BATCHES:
        rd = HARNESS / "runs" / f"b{b:03d}"
        alt = sorted(p.name for p in rd.glob("stream-v*.jsonl"))
        if alt:
            z.append(f"  B{b}: {', '.join(alt)}")
    text = "\n".join(z) + "\n"
    ziel = ROOT / "docs" / "_r13bg_last.txt"
    ziel.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"Beleg: {ziel}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
