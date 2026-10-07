"""Schatten-Vergleich: Sonnet-Befunde gegen die echten (Opus-)Aussensichten stellen (R13bw-14).

Nur-Lese-Werkzeug: es liest `runs/b<N>/meta.md` (die echte Aussensicht) und
`docs/_sonnet_vergleich_b<N>.md` (der Schattenlauf aus `tools/schatten_aussensicht.py`)
und **gibt aus** - es schreibt nichts.

Ausgegeben wird je Batch:

  * **Befunde**: `gefunden` (gleiche Beleg-Referenz in beiden Laeufen), `verpasst`
    (nur in der echten), `zusaetzlich` (nur im Schatten) - mit Gewicht und Empfaenger;
    die Summentafel zaehlt je Gewicht (`hoch|mittel|niedrig`).
  * **Verdikte**: `<PRUEFUNG id="M…" status="…"/>` je Kennung - `gleich` oder `anders`,
    mit beiden Statusworten.
  * **Kosten/Lauf**: Werkzeugrunden, Laufzeit, Modell und die Nutzerlimit-Zeile
    (`utilization` vor/nach) aus den Kopfdaten beider Berichte.

Der Schluessel eines BEFUNDS ist seine **erste Beleg-Referenz** (`Datei:Zeile` aus der
`Beleg:`-Zeile) - das Format der Aussensicht vergibt keine Kennung fuer Befunde
(`<BEFUND n="1" gewicht="…" empfaenger="…">`); Kennungen gibt es nur fuer die
**Verdikte** (`M<batch>-<n>`). Deshalb heisst ein Befund hier nach seinem Beleg, und
„verpasst" heisst: **kein** Schattenbefund nennt denselben Beleg. Das ist eine
mechanische Naeherung - der Text daneben entscheidet, ob wirklich etwas fehlt.

Aufruf:

    python tools/schatten_vergleich.py --batch 285 --batch 289
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hx import aussensicht                                     # noqa: E402
from hx.config import load_config                              # noqa: E402
from hx.util import read_text                                  # noqa: E402

RE_DATUM = r"[\w./\\-]+\.(?:cpp|hpp|h|c|py|md|json|txt|inc|ps1|toml|cfg|tsv|csv)\s*:\s*\d+"
_RE_REF = re.compile(RE_DATUM, re.IGNORECASE)
_RE_ZEILE = re.compile(r"^-\s*(?P<name>[A-Za-z()][^:]*):\s*(?P<rest>.+)$", re.M)
_RE_KV = re.compile(r"(?P<k>[a-z_]+)=(?P<v>\S+)", re.IGNORECASE)
GEWICHTE = ("hoch", "mittel", "niedrig")


# ------------------------------------------------------------------ Lesen
def kopf(text: str) -> dict:
    """Die `- Name: …`-Zeilen des Berichtskopfes als dict, dazu `- Lauf:`-Felder."""
    out: dict = {}
    for m in _RE_ZEILE.finditer(text):
        out[m.group("name").strip().lower()] = m.group("rest").strip()
    lauf = {m.group("k"): m.group("v") for m in _RE_KV.finditer(out.get("lauf", ""))}
    out["lauf_felder"] = lauf
    return out


def schluessel(befund: dict) -> str:
    """Die Beleg-Referenz eines Befunds (erste `Datei:Zeile`), sonst der Beleg-Textanfang.

    Normalisiert wird nur die Schreibweise des Belegordners: `_m283/x.txt:12` und
    `analysis/_m283/x.txt:12` sind dieselbe Stelle. Backticks und Anfuehrungszeichen
    fallen weg, weil die Aussensicht sie mal setzt und mal nicht.
    """
    beleg = str(befund.get("beleg") or "").strip().replace("`", "").replace('"', "")
    m = _RE_REF.search(beleg)
    if not m:
        return ("ohne-referenz: " + " ".join(beleg.split())[:80]) if beleg else "ohne-beleg"
    ref = m.group(0).replace("\\", "/")
    ref = re.sub(r"\s*:\s*", ":", ref)          # `result.json: 3` == `result.json:3`
    for prefix in ("analysis/", "./"):
        if ref.lower().startswith(prefix):
            ref = ref[len(prefix):]
    return ref


def befunde(text: str, max_befunde: int = 7) -> tuple[dict, list[dict]]:
    """(Kopf, Befunde) eines Berichts - ueber den Harness-Parser (gleiche Semantik)."""
    _s, liste, _v, _p = aussensicht.parse(text, max_befunde)
    for b in liste:
        b["schluessel"] = schluessel(b)
    return kopf(text), liste


def _verdikt_liste(text: str) -> list[tuple[str, str]]:
    """Alle Verdikte in Reihenfolge (id, status) - robust ohne Attribut-Reihenfolge."""
    out: list[tuple[str, str]] = []
    for m in aussensicht._RE_PRUEFUNG.finditer(text or ""):
        attrs = {a.group("name").lower(): a.group("wert")
                 for a in aussensicht._RE_ATTR.finditer(m.group("attrs") or "")}
        if attrs.get("id"):
            out.append((attrs["id"], str(attrs.get("status") or "offen").lower()))
    return out


# ------------------------------------------------------------------ Vergleich
def vergleiche(echt_text: str, schatten_text: str) -> dict:
    """Der Vergleich zweier Berichte - rein rechnend, ohne Seiteneffekte."""
    k_echt, b_echt = befunde(echt_text)
    k_schatten, b_schatten = befunde(schatten_text)
    nach_echt = {b["schluessel"]: b for b in b_echt}
    nach_schatten = {b["schluessel"]: b for b in b_schatten}
    gefunden = [b for s, b in nach_echt.items() if s in nach_schatten]
    verpasst = [b for s, b in nach_echt.items() if s not in nach_schatten]
    zusaetzlich = [b for s, b in nach_schatten.items() if s not in nach_echt]
    v_echt, v_schatten = dict(_verdikt_liste(echt_text)), dict(_verdikt_liste(schatten_text))
    gleich, anders = [], []
    for kid in sorted(set(v_echt) | set(v_schatten)):
        paar = (v_echt.get(kid, "-"), v_schatten.get(kid, "-"))
        (gleich if paar[0] == paar[1] else anders).append((kid, *paar))
    return {"echt": k_echt, "schatten": k_schatten, "befunde_echt": b_echt,
            "befunde_schatten": b_schatten, "gefunden": gefunden, "verpasst": verpasst,
            "zusaetzlich": zusaetzlich, "verdikte_gleich": gleich, "verdikte_anders": anders}


def _zeile(b: dict, marke: str = "") -> str:
    kurz = " ".join(str(b.get("aussage") or "").split())[:88]
    return (f"    {marke:<11} n={b.get('n')} {str(b.get('gewicht')):<7} "
            f"{str(b.get('empfaenger')):<8} {b.get('schluessel')}\n"
            f"                {kurz}")


def tafel(v: dict, batch: int) -> str:
    z = [f"=== B{batch}: {v['echt'].get('lauf_felder', {}).get('modell', '?')} (echt) "
         f"gegen {v['schatten'].get('lauf_felder', {}).get('modell', '?')} (Schatten)"]
    for name in ("echt", "schatten"):
        k = v[name]
        lf = k.get("lauf_felder", {})
        z.append(f"  {name:<8} dauer={lf.get('dauer', '?')} runden={lf.get('runden', '?')} "
                 f"zuege={lf.get('zuege', '?')} befunde={lf.get('befunde', '?')} "
                 f"verworfen={lf.get('verworfen', '?')}")
        if k.get("zuege (werkzeugrunden)"):
            z.append(f"           Zuege laut Kopf: {k['zuege (werkzeugrunden)']}")
        for feld in ("nutzerlimit (abo) vor dem lauf", "nutzerlimit (abo) nach dem lauf"):
            if k.get(feld):
                z.append(f"           {feld}: {k[feld]}")
    z.append(f"  Befunde: {len(v['befunde_echt'])} echt / {len(v['befunde_schatten'])} "
             f"Schatten -> gefunden {len(v['gefunden'])}, verpasst {len(v['verpasst'])}, "
             f"zusaetzlich {len(v['zusaetzlich'])}")
    for gew in GEWICHTE:
        z.append(f"    Gewicht {gew:<8} echt {sum(1 for b in v['befunde_echt'] if b.get('gewicht') == gew)}"
                 f" | gefunden {sum(1 for b in v['gefunden'] if b.get('gewicht') == gew)}"
                 f" | verpasst {sum(1 for b in v['verpasst'] if b.get('gewicht') == gew)}"
                 f" | zusaetzlich {sum(1 for b in v['zusaetzlich'] if b.get('gewicht') == gew)}")
    if v["verpasst"]:
        z.append("  VERPASST (nur echt):")
        z += [_zeile(b, "verpasst") for b in v["verpasst"]]
    if v["zusaetzlich"]:
        z.append("  ZUSAETZLICH (nur Schatten):")
        z += [_zeile(b, "zusaetzlich") for b in v["zusaetzlich"]]
    if v["gefunden"]:
        z.append("  GEFUNDEN (gleicher Beleg):")
        z += [_zeile(b, "gefunden") for b in v["gefunden"]]
    if v["verdikte_gleich"] or v["verdikte_anders"]:
        z.append(f"  Verdikte: {len(v['verdikte_gleich'])} gleich, "
                 f"{len(v['verdikte_anders'])} anders")
        for kid, a, b_ in v["verdikte_anders"]:
            z.append(f"    ANDERS  {kid:<12} echt={a:<10} Schatten={b_}")
        if v["verdikte_gleich"]:
            z.append("    gleich : " + ", ".join(f"{k}({a})" for k, a, _b in v["verdikte_gleich"]))
    return "\n".join(z)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", type=int, action="append", required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    for batch in args.batch:
        echt = read_text(aussensicht.pfad_neu(cfg, batch, "md"))
        schatten_pfad = Path(cfg.root).parent / "docs" / f"_sonnet_vergleich_b{batch}.md"
        schatten = read_text(schatten_pfad)
        if not echt:
            print(f"B{batch}: keine echte meta.md - uebersprungen")
            continue
        if not schatten:
            print(f"B{batch}: kein Schattenbericht ({schatten_pfad}) - "
                  "erst tools/schatten_aussensicht.py fahren")
            continue
        print(tafel(vergleiche(echt, schatten), batch))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
