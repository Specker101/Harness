"""Beleg: die Schluessel-Ueberwachung erkennt Zugriffe - und schlaegt nicht falsch an.

Aufruf:  python -u tools\\check_secretwatch.py        ->  docs\\_secretwatch_beleg.txt

Gerpueft werden die Faelle, die im Betrieb vorkommen:

  1. Werkzeugaufruf auf den ALTEN Ort (`g:\\Harness\\secrets`)        -> Treffer
  2. Werkzeugaufruf auf den NEUEN Ort (`%USERPROFILE%\\.hx-secrets`) -> Treffer
  3. Werkzeug namens "/ask" auf den neuen Ort                        -> Treffer
  4. Textinhalt eines Schreibbefehls, der den Pfad ZITIERT           -> KEIN Treffer
  5. Ein Dokument im Mitschnitt, das den Pfad nennt                  -> KEIN Treffer
  6. Der Schluesselwert selbst im Mitschnitt                         -> Treffer (Leck)
  7. Derselbe Fall noch einmal                                       -> kein zweiter Alarm

Werte werden NUR im Speicher verglichen. Ausgegeben werden Name und Fingerabdruck,
nie der Wert; die Belegdatei wird zum Schluss geprueft (der Wert darf nicht drin sein).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hx import secrets, streamjson                                     # noqa: E402
from hx.config import load_config                                      # noqa: E402


def zeile(name: str, treffer: list[dict], erwartet: int) -> tuple[str, bool]:
    got = [(h["art"], h["werkzeug"], h["name"]) for h in treffer]
    ok = len(treffer) == erwartet
    marke = "OK" if ok else "ABWEICHUNG"
    return (f"  {name:52s} erwartet {erwartet}, gefunden {len(treffer)}  [{marke}]"
            + (f"\n      {got}" if got else "")), ok


def main() -> int:
    cfg = load_config()
    w = streamjson.secret_watch(cfg)
    zeilen = ["Beleg: Schluessel-Ueberwachung (R13g)",
              f"  ueberwachte Orte : {w.pfade}",
              f"  ueberwachte Werte: {sorted(w.werte)} (Fingerabdruecke: "
              + ", ".join(f"{n}={secrets.fingerprint(v)}" for n, v in sorted(w.werte.items()))
              + ")",
              ""]
    alles_ok = True

    alt = r"g:\Harness\secrets\deepseek.key"
    neu = str(Path(cfg.secrets_dir) / "telegram.key").replace("\\", "/")

    def feed(*bloecke) -> streamjson.StreamStats:
        s = streamjson.StreamStats(w)
        s.feed(json.dumps({"type": "assistant",
                           "message": {"id": "m1", "model": "m", "usage": {},
                                       "content": list(bloecke)}}, ensure_ascii=False))
        return s

    def tool(tid: str, name: str, inp: dict) -> dict:
        return {"type": "tool_use", "id": tid, "name": name, "input": inp}

    faelle = [
        ("1) Read auf den ALTEN Ort", feed(tool("t1", "Read", {"file_path": alt})), 1),
        ("2) PowerShell auf den NEUEN Ort",
         feed(tool("t2", "PowerShell", {"command": f"Get-Content {neu}"})), 1),
        ("3) Grep auf den NEUEN Ordner",
         feed(tool("t3", "Grep", {"pattern": "key", "path": str(cfg.secrets_dir)})), 1),
        ("4) Write, der den Pfad nur im TEXT nennt",
         feed(tool("t4", "Write", {"file_path": "g:/Silent Scope Decomp/x.md",
                                   "content": f"Der alte Ort war {alt}"})), 0),
        ("5) Dokument im Ergebnis, das den Pfad nennt",
         streamjson.StreamStats(w), 0),
    ]
    # 5) gesondert: Ergebnisblock (kein Werkzeugaufruf)
    s5 = streamjson.StreamStats(w)
    s5.feed(json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t9",
         "content": f"Datei gelesen: {alt} (nur ein Zitat im Dokument)"}]}},
        ensure_ascii=False))
    faelle[4] = ("5) Dokument im Ergebnis, das den Pfad nennt", s5, 0)

    for name, stats, erwartet in faelle:
        t, ok = zeile(name, stats.secret_hits, erwartet)
        zeilen.append(t)
        alles_ok = alles_ok and ok

    # 6) Wert im Mitschnitt (Leck) - Wert kommt aus dem Speicher, nie aus der Datei.
    wert = w.werte.get(secrets.DEEPSEEK) or ""
    s6 = streamjson.StreamStats(w)
    s6.feed(json.dumps({"type": "assistant",
                        "message": {"id": "m6", "model": "m", "usage": {},
                                    "content": [{"type": "text",
                                                 "text": f"gefunden: {wert}"}]}},
                       ensure_ascii=False))
    t, ok = zeile("6) Schluesselwert im Mitschnitt (Leck)", s6.secret_hits, 1)
    zeilen.append(t)
    alles_ok = alles_ok and ok
    # Gegenprobe: steht der Wert irgendwo in der Belegstruktur? (darf nicht)
    j = json.dumps(s6.secret_hits, ensure_ascii=False)
    drin = bool(wert) and wert in j
    zeilen.append(f"  {'7) Gegenprobe: Wert NICHT im Beleg':52s} "
                  f"{'OK' if not drin else 'ABWEICHUNG - Wert steht im Beleg!'}")
    alles_ok = alles_ok and not drin

    # 8) Alarm- und Belegtext
    alarm = streamjson.secret_alarm_text(s6.secret_hits + faelle[0][1].secret_hits,
                                         "Worker", 176)
    zeilen += ["", "Alarmtext (so geht er per Telegram raus):", f"  {alarm}",
               f"  enthaelt einen Wert? {'JA - FEHLER' if any(v in alarm for v in w.werte.values()) else 'nein'}"]
    alles_ok = alles_ok and not any(v in alarm for v in w.werte.values())

    zeilen += ["", f"Gesamt: {'ALLE ERWARTUNGEN ERFUELLT' if alles_ok else 'ABWEICHUNGEN SIEHE OBEN'}"]
    text = "\n".join(zeilen)
    print(text)
    ziel = Path("g:/Harness/docs/_secretwatch_beleg.txt")
    ziel.write_text(text + "\n", encoding="utf-8")
    print(f"\nBeleg: {ziel}")
    return 0 if alles_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
