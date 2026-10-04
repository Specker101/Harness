"""R13bt-5-Sonde (nur lesend am Original): feuert der neue Ausloeser wie gewollt?

Gebaut wird ein WEGWERF-Repo, in das die ECHTEN Auftraege/Reviews von B262..B265 kopiert
werden - die Pflichtzeile `STATION: nein` wird ergaenzt (die echten Reviews entstanden VOR
der Regel; behauptet wird damit nur das, was der Nutzer fuer B259/B261 als Station genannt
hat und was fuer B260/B262..B264 gilt). EIN weiterer Batch (B266) ist SYNTHETISCH: er steht
nur da, um die Schwelle 4 zu erreichen - so ein Batch fehlt heute, weil B265 noch laeuft.
Das echte Repo wird nicht angefasst. Beleg wird selbst als UTF-8/LF geschrieben.
"""
import io
import json
import pathlib
import shutil
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "harness"))
ZIEL = pathlib.Path(__file__).with_suffix(".txt")


def main() -> str:
    from hx import aussensicht, stand, state as st
    from hx.config import load_config
    from hx.util import ensure_dir, write_text_atomic

    buf = io.StringIO()
    echt = load_config()
    z = stand.stillstand_zaehler(echt, anzahl=12)
    print(f"TEIL A - ECHTER Stand (root {echt.root}):", file=buf)
    print(f"  Zaehler={z['zaehler']} von Schwelle {z['schwelle']}, "
          f"Luecke ab B{z['luecke_ab']}, offen={z['offen']} - die echten Reviews tragen "
          "die Pflichtzeile noch nicht (Regel seit R13bt)", file=buf)
    print(f"  station_stillstand() -> {aussensicht.station_stillstand(echt)!r}"
          "   (nichts behauptet, kein Ausloeser)", file=buf)

    tmp = HIER / "_tmp_r13bt5"
    shutil.rmtree(tmp, ignore_errors=True)
    root = ensure_dir(tmp / "harness")
    ensure_dir(tmp / "decomp" / "analysis")
    cfg = load_config()
    cfg.data["paths"]["root"] = str(root)
    cfg.data["paths"]["decomp"] = str(tmp / "decomp")
    cfg.data["paths"]["harness_home"] = str(tmp)
    for n in (262, 263, 264, 266):                  # 266 = synthetischer Zusatzbatch
        quelle = pathlib.Path(echt.root) / "runs" / f"b{n:03d}" / "auftrag.md"
        if quelle.is_file():
            write_text_atomic(root / "runs" / f"b{n:03d}" / "auftrag.md",
                              quelle.read_text(encoding="utf-8"))
        else:
            write_text_atomic(root / "runs" / f"b{n:03d}" / "auftrag.md", "STRANG: B\n")
    for n in (263, 264, 265, 267):                  # Reviews: bewerten B262..B264 + B266
        quelle = pathlib.Path(echt.root) / "runs" / f"b{n:03d}" / "review.md"
        text = quelle.read_text(encoding="utf-8") if quelle.is_file() else ""
        write_text_atomic(root / "runs" / f"b{n:03d}" / "review.md",
                          "STATION: nein\n" + text)

    z2 = stand.stillstand_zaehler(cfg, anzahl=12)
    print("\nTEIL B - WEGWERF-REPO, echte Reviews B262..B264 (+B266 synthetisch), "
          "Pflichtzeile `STATION: nein` ergaenzt:", file=buf)
    print(f"  Zaehler={z2['zaehler']} von {z2['schwelle']} (B{z2['von']}..B{z2['bis']}), "
          f"schwelle_erreicht={z2['schwelle_erreicht']}", file=buf)
    print(f"  station_stillstand():\n    {aussensicht.station_stillstand(cfg)}", file=buf)
    print(f"  station_neuester_b() -> {aussensicht.station_neuester_b(cfg)} "
          "(Markenschluessel = ERSTER Batch des Laufs)", file=buf)

    s = st.State(root / "state" / "run.json")
    s.data["batch"] = 266
    s.save()
    g1 = [g for g in aussensicht.faellig(cfg, s) if g.startswith(aussensicht.STATION_GRUND)]
    print(f"\n  faellig(B266) -> {json.dumps(g1, ensure_ascii=False)}", file=buf)
    bis = aussensicht.station_marke_setzen(cfg, s)
    s.data["meta"]["geprueft_batch"] = 266
    s.save()
    write_text_atomic(root / "runs" / "b267" / "auftrag.md", "STRANG: B\n")
    write_text_atomic(root / "runs" / "b268" / "review.md", "STATION: nein\n")
    s.data["batch"] = 267
    s.save()
    g2 = [g for g in aussensicht.faellig(cfg, s) if g.startswith(aussensicht.STATION_GRUND)]
    z3 = stand.stillstand_zaehler(cfg, anzahl=12)
    print(f"  Marke gesetzt auf B{bis}; naechster Batch B267 (Zaehler steht auf "
          f"{z3['zaehler']}) -> faellig(B267) -> {json.dumps(g2, ensure_ascii=False)}", file=buf)
    print("  ^ derselbe Stillstand meldet NICHT erneut (sonst ein Abo-Lauf je Batch);\n"
          "    nach einer Station springt `von` und die Schwelle ist wieder scharf.", file=buf)
    shutil.rmtree(tmp, ignore_errors=True)
    return buf.getvalue()


if __name__ == "__main__":
    text = main()
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"geschrieben: {ZIEL}")
    print(text)
