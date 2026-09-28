r"""Aussensicht (R13w, 2026-09-28) - der Meta-Review.

Anderer Auftrag als der Reviewer (bewusst):

  * Der Reviewer fragt "war der Batch gut?" - die Aussensicht fragt
    "**stimmen Messgroessen, Plan und Annahmen noch?**".
  * eigene, **immer frische** Session (kein Verlauf), gleiches Modell wie der Reviewer,
    eigener Systemprompt `prompts/aussensicht.md`, Lesezugriff auf Harness UND Decomp-Repo
    (Schreiben ist doppelt verboten).
  * **Sie entscheidet nichts** und aendert nichts. Sie liefert eine Befundliste; Befunde
    mit Empfaenger `Reviewer` gehen als `/claude`-Nachricht in die Queue, Befunde mit
    Empfaenger `Nutzer` per Telegram und unter `/fragen`.
  * Ausgabeformat (strikt, damit maschinell lesbar):
    `<AUSSENSICHT>…</AUSSENSICHT>`, je Befund
    `<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">Beleg: … Aussage: … Empfehlung: …</BEFUND>`
    und je frueherem Befund `<PRUEFUNG id="M208-3" status="erledigt|offen|verworfen"/>`.

Ausloeser (`faellig`): Vormerkung durch `/meta`, alle `[meta] every_batches` Batches, ein
Worker-Abbruch, `MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:` in der neuesten
Review-Zusammenfassung, ein stehengebliebener B-Schritt (Weg B) bzw. eine C-Kernzahl ohne
Bewegung ueber die letzten **C-Batches**. Je Batch wird hoechstens einmal entschieden
(`geprueft_batch`).

Belege/Regeln dieser Datei: `docs/_r13w_belege.md`, Doku `docs/bedienung.md`.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from . import envs, protocol, secrets, stand, streamjson
from .proc import run_stream
from .profiles import credential_verbote, git_schreib_verbote, nur_lese_git_regeln, pfad_regeln, secrets_verbote
from .util import ensure_dir, now_iso, read_text, write_json_atomic, write_text_atomic

# ------------------------------------------------------------------ Vorgaben
STANDARD = {"every_batches": 10, "wall_s": 900, "max_turns": 30, "max_befunde": 7,
            "summaries": 10, "bilanz_zeitfenster": 12}

# Alles Sperrende - dieselbe Haltung wie beim Reviewer, nur ohne MCP.
VERBOTEN = ["Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch",
            "Task", "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]
GIT_TOOL = "PowerShell"

GEWICHT_REIHENFOLGE = ("hoch", "mittel", "niedrig")
EMPFAENGER = ("Reviewer", "Nutzer")

# Kernzahlen des C-Strangs aus `stand.kernzahlen` (R13x: C Koepfe = Preflight-Zeile,
# Paket E = Ist-Spalte der Soll/Ist-Tafel) - Befund Nr. 2:
# sie werden NUR ueber die letzten C-Batches verglichen, nie ueber einen B-Batch hinweg.
KERNZAHLEN = (("c_koepfe", "C Koepfe"), ("c_faelle", "C Faelle"),
              ("c_abweichungen", "C Abweichungen"),
              ("paket_e_koepfe", "Paket E offen Koepfe"), ("paket_e_insn", "Paket E offen Insn"),
              ("baut", "Bau-Liste"), ("inventar", "Programm-Inventar"), ("offen", "C-Vorrat"))


def grenzen(cfg) -> dict:
    """Die Grenzen der Aussensicht aus `[meta]` (Vorgaben als Rueckfall)."""
    return {k: cfg.get("meta", k, v) for k, v in STANDARD.items()}


# ------------------------------------------------------------------ Ablage
def bericht_pfad(cfg, batch: int) -> Path:
    return Path(cfg.root) / "runs" / f"meta-{int(batch):03d}.md"


def json_pfad(cfg, batch: int) -> Path:
    return Path(cfg.root) / "runs" / f"meta-{int(batch):03d}.json"


def stream_pfad(cfg, batch: int) -> Path:
    return Path(cfg.root) / "runs" / f"meta-{int(batch):03d}.jsonl"


def ledger_pfad(cfg) -> Path:
    return Path(cfg.sub("state")) / "meta_befunde.json"


def ledger(cfg) -> list[dict]:
    """Alle je erhobenen Befunde (neueste zuletzt), unlesbar = leer."""
    p = ledger_pfad(cfg)
    if not p.is_file():
        return []
    try:
        daten = json.loads(read_text(p))
    except (OSError, ValueError):
        return []
    if isinstance(daten, dict):
        daten = daten.get("befunde")
    return [b for b in daten if isinstance(b, dict)] if isinstance(daten, list) else []


def ledger_schreiben(cfg, befunde: list[dict]) -> None:
    write_json_atomic(ledger_pfad(cfg), {"updated_at": now_iso(), "befunde": list(befunde)})


def offene(cfg) -> list[dict]:
    """Befunde, die noch nicht beantwortet/geprueft sind."""
    return [b for b in ledger(cfg) if str(b.get("status") or "offen") == "offen"]


def zeile(cfg) -> str:
    """Eine Zeile fuer `/bilanz` und `/status` ('' = es gab noch keine Aussensicht)."""
    alle = ledger(cfg)
    berichte = sorted((Path(cfg.root) / "runs").glob("meta-*.json"),
                      key=lambda p: p.stat().st_mtime) if (Path(cfg.root) / "runs").is_dir() else []
    if not alle and not berichte:
        return ""
    batch = 0
    anzahl = len(alle)
    if berichte:
        try:
            d = json.loads(read_text(berichte[-1]))
            batch = int(d.get("batch") or 0)
            anzahl = len(d.get("befunde") or []) or anzahl
        except (OSError, ValueError):
            batch = 0
    offen = len(offene(cfg))
    return (f"letzte Aussensicht: Batch {batch or '?'}, {anzahl} Befunde, davon {offen} offen")


def fragen_zeilen(cfg) -> str:
    """Offene Befunde mit Empfaenger Nutzer fuer `/fragen`."""
    rows = [b for b in offene(cfg) if str(b.get("empfaenger")) == "Nutzer"]
    if not rows:
        return ""
    zeilen = ["", "== AUSSENSICHT - offene Punkte an dich =="]
    for b in rows:
        zeilen.append(f"- [{b.get('id')}] {str(b.get('aussage') or '')[:300]}")
        if b.get("empfehlung"):
            zeilen.append(f"  Empfehlung: {str(b['empfehlung'])[:200]}")
        if b.get("beleg"):
            zeilen.append(f"  Beleg: {str(b['beleg'])[:160]}")
    return "\n".join(zeilen)


# ------------------------------------------------------------------ Eingaben
def _runs_dir(cfg) -> Path:
    return Path(cfg.root) / "runs"


def reviews(cfg, n: int) -> list[tuple[int, str]]:
    """Die letzten `n` Review-Texte als `[(reviewordner, text)]`, aufsteigend."""
    gefunden: list[tuple[int, str]] = []
    try:
        for p in _runs_dir(cfg).glob("b*/review.md"):
            m = re.fullmatch(r"b(\d+)", p.parent.name)
            if not m:
                continue
            try:
                text = read_text(p)
            except OSError:
                continue
            if text.strip():
                gefunden.append((int(m.group(1)), text))
    except OSError:
        return []
    gefunden.sort()
    return gefunden[-max(1, int(n)):]


def summaries(cfg, n: int) -> list[tuple[int, str]]:
    """Die letzten `n` `<TELEGRAM_SUMMARY>`-Texte als `[(reviewordner, summary)]`."""
    out: list[tuple[int, str]] = []
    for batch, text in reviews(cfg, int(n) + 4):
        s = protocol.parse_review(text).summary.strip()
        if s:
            out.append((batch, s))
    return out[-max(1, int(n)):]


def b_schritt(cfg, n: int = 6) -> list[tuple[int, int, str]]:
    """Die `B-SCHRITT:`-Zeilen aus den letzten Reviews: `[(reviewordner, schritt, zeile)]`.

    Die Zeile ist seit R13w Pflicht in der Review-Zusammenfassung
    ("B-SCHRITT: <n>/5 <Name>, B-Batch <k> von max 20"); fehlt sie, ist der Batch kein
    B-Batch (oder der Reviewer hat sie vergessen - dann wird NICHT geraten).
    """
    out: list[tuple[int, int, str]] = []
    for batch, summary in summaries(cfg, n):
        for zeile in summary.splitlines():
            m = re.search(r"B-SCHRITT:\s*(\d+)\s*/\s*5", zeile, re.IGNORECASE)
            if m:
                out.append((batch, int(m.group(1)), zeile.strip()[:160]))
                break
    return out


def b_schritt_stillstand(cfg) -> str:
    """Steht der B-Schritt ueber zwei B-Batches still? ('' = nein)"""
    reihe = b_schritt(cfg, 6)
    if len(reihe) < 2:
        return ""
    b1, s1 = reihe[-2][0], reihe[-2][1]
    b2, s2 = reihe[-1][0], reihe[-1][1]
    if s1 != s2:
        return ""
    return (f"B-Schritt {s2}/5 unveraendert in den B-Batches (Reviews b{b1} und b{b2}) - "
            "kein Fortschritt ueber zwei B-Batches")


def _marker(cfg, muster: str) -> list[tuple[int, str]]:
    """Zeilen mit `muster` in den letzten Review-Zusammenfassungen (neueste zuerst)."""
    treffer: list[tuple[int, str]] = []
    reg = re.compile(muster, re.IGNORECASE)
    for batch, summary in reversed(summaries(cfg, 3)):
        for zeile in summary.splitlines():
            if reg.search(zeile):
                treffer.append((batch, zeile.strip()[:200]))
    return treffer


def ist_b_batch(cfg, batch: int) -> bool:
    """Ist dieser Batch ein B-Batch? (Pflichtzeile `B-SCHRITT:` in seinem Review)"""
    for b, _n, _z in b_schritt(cfg, 8):
        if b == int(batch):
            return True
    return False


def kernzahl_stillstand(cfg) -> list[str]:
    """C-Kernzahlen, die sich ueber die letzten beiden **C-Batches** nicht bewegt haben.

    Befund Nr. 2 des Nutzers (2026-09-28): bei einem Mischverhaeltnis 2 B : 1 C darf der
    Ausloeser nicht in jedem B-Batch feuern. Deshalb werden B-Batches ausgelassen und
    nur die C-Batches verglichen.
    """
    fenster = stand.kernzahlen(cfg, int(grenzen(cfg)["bilanz_zeitfenster"]))
    c_batches = [e for e in fenster if not ist_b_batch(cfg, int(e.get("batch") or 0))]
    if len(c_batches) < 2:
        return []
    neu, alt = c_batches[-1], c_batches[-2]
    stehend: list[str] = []
    for schluessel, name in KERNZAHLEN:
        n, a = neu.get(schluessel), alt.get(schluessel)
        if n is None or a is None or n != a:
            continue
        wenn = (f"{n[0]}/{n[1]}" if isinstance(n, (list, tuple)) else str(n))
        stehend.append(f"{name} = {wenn} (B{alt.get('batch')} wie B{neu.get('batch')})")
    return stehend


def kosten_zeilen(cfg, n: int = 10) -> str:
    """Kosten und Laufzeiten der letzten `n` Batches (aus `runs/b*/result.json`)."""
    zeilen: list[str] = []
    eintraege: list[tuple[int, dict]] = []
    try:
        for p in _runs_dir(cfg).glob("b*/result.json"):
            m = re.fullmatch(r"b(\d+)", p.parent.name)
            if not m:
                continue
            try:
                eintraege.append((int(m.group(1)), json.loads(read_text(p))))
            except (OSError, ValueError):
                continue
    except OSError:
        return "(keine Ergebnisse lesbar)"
    eintraege.sort()
    for batch, d in eintraege[-max(1, int(n)):]:
        zeilen.append(f"- B{batch}: ${float(d.get('cost_usd') or 0):.4f}, "
                      f"{float(d.get('duration_s') or 0) / 60:.1f} min, "
                      f"rc={d.get('rc')}, Abbruch={d.get('killed_reason') or '-'}, "
                      f"Anfragen={(d.get('stats') or {}).get('requests')}")
    return "\n".join(zeilen) or "(keine Ergebnisse)"


def ziel_abschnitte(cfg) -> str:
    """Ziel-/Scope-Abschnitte aus readme.md und AGENTS.md (nur lesen)."""
    teile: list[str] = []
    for name, ueberschrift in (("readme.md", "## Project Goal"),
                               ("AGENTS.md", "## Project Goal")):
        p = Path(cfg.decomp) / name
        try:
            text = read_text(p)
        except OSError:
            continue
        i = text.find(ueberschrift)
        abschnitt = text[i:i + 2600] if i >= 0 else text[:1800]
        teile.append(f"--- {name} ---\n{abschnitt.strip()}")
    return "\n\n".join(teile) or "(weder readme.md noch AGENTS.md lesbar)"


def eingaben(cfg, state) -> str:
    """Alle Eingabebloecke - was nicht da ist, wird als solches benannt, nie erfunden."""
    g = grenzen(cfg)
    batch = int(state.batch or 0)
    bloecke: list[str] = []

    bil = "(Bilanz nicht ermittelbar)"
    try:
        from . import bilanz as bilanzmod
        bil = bilanzmod.bericht(cfg, n=int(g["bilanz_zeitfenster"]), batch=batch or None,
                                voll=True)
    except Exception as exc:                                     # noqa: BLE001
        bil = f"(Bilanz nicht ermittelbar: {str(exc)[:150]})"
    bloecke.append("=== BILANZ: TREND DER LETZTEN "
                   f"{int(g['bilanz_zeitfenster'])} BATCHES ===\n" + bil)

    try:
        plan = stand.plan_ist_text(cfg)
    except Exception as exc:                                     # noqa: BLE001
        plan = f"(PLAN/IST nicht ermittelbar: {str(exc)[:150]})"
    bloecke.append("=== PLAN/IST DER LETZTEN BATCHES ===\n" + (plan or "(keine Daten)"))

    summ = summaries(cfg, int(g["summaries"]))
    if summ:
        zeilen = []
        for b, s in summ:
            zeilen.append(f"--- Zusammenfassung aus runs/b{b:03d}/review.md ---\n{s}")
        bloecke.append("=== LETZTE REVIEW-ZUSAMMENFASSUNGEN (TELEGRAM_SUMMARY) ===\n"
                       + "\n\n".join(zeilen))
    else:
        bloecke.append("=== LETZTE REVIEW-ZUSAMMENFASSUNGEN ===\n(keine lesbar)")

    kopf = stand.anchor_bloecke(cfg)
    bloecke.append("=== ANKERKOPF analysis/r1b-workstream.md ===\n"
                   + "\n".join(f"{k}: {v}" for k, v in kopf.items()))

    bloecke.append("=== ZIEL UND UMFANG (readme.md / AGENTS.md) ===\n" + ziel_abschnitte(cfg))

    try:
        fragen = stand.fragen_text(cfg, gate=state.gate)
    except Exception as exc:                                     # noqa: BLE001
        fragen = f"(/fragen nicht ermittelbar: {str(exc)[:150]})"
    bloecke.append("=== OFFENE FRAGEN UND ENTSCHEIDUNGEN (/fragen) ===\n" + (fragen or "(keine)"))

    bloecke.append("=== KOSTEN UND LAUFZEITEN JE BATCH ===\n" + kosten_zeilen(cfg,
                                                                             int(g["summaries"])))

    ds = "(nicht lesbar)"
    try:
        from . import queue as queuemod
        ds = queuemod.deliver_block(cfg.root, "ds", [])[0] or "(leer)"
    except Exception as exc:                                     # noqa: BLE001
        ds = f"(nicht lesbar: {str(exc)[:150]})"
    bloecke.append("=== /ds-QUEUE (Auftraege, die noch auf Zustellung warten) ===\n" + ds)

    off = offene(cfg)
    if off:
        zeilen = []
        for b in off[-15:]:
            zeilen.append(f"[{b.get('id')}] Gewicht {b.get('gewicht')} | Empfaenger "
                          f"{b.get('empfaenger')} | Status {b.get('status')}\n"
                          f"  Beleg: {b.get('beleg')}\n  Aussage: {b.get('aussage')}\n"
                          f"  Empfehlung: {b.get('empfehlung')}")
        bloecke.append("=== FRUEHERE BEFUNDE, DIE NOCH OFFEN SIND (bitte je ID ein "
                       "VERDIKT abgeben) ===\n" + "\n".join(zeilen))
    else:
        bloecke.append("=== FRUEHERE BEFUNDE ===\n(keine offenen)")
    return "\n\n".join(bloecke)


FORMAT_HINWEIS = """=== DEINE AUSGABE (FORMAT IST PFLICHT) ===
Antworte NUR mit den folgenden Bloecken, ohne Einleitung:

<AUSSENSICHT>
2-4 Zeilen: was du geprueft hast, was du gefunden hast, was dir am meisten Sorgen macht.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch|mittel|niedrig" empfaenger="Reviewer|Nutzer">
Beleg: <Datei:Zeile> ODER <Zahl + Quelldatei> ODER "Fehlstelle: gesucht in <Ort>, nicht gefunden"
Aussage: <was nicht stimmt, in EINEM Satz>
Empfehlung: <was getan werden sollte, in EINEM Satz>
</BEFUND>

(weitere Befunde fortlaufend nummeriert, hoechstens {max_befunde} Stueck, nach Gewicht
sortiert: hoch zuerst. Ein Befund OHNE jeden Beleg wird verworfen und zaehlt nicht.)

Fuer JEDEN noch offenen frueheren Befund eine Zeile:
<PRUEFUNG id="M208-3" status="erledigt|offen|verworfen"/>

=== STICHPROBEN (PFLICHT, im Abschnitt <AUSSENSICHT> nennen) ===
1. Pruefe mindestens ZWEI Aussagen aus den Review-Zusammenfassungen gegen die ROHBELEGE
   des jeweiligen Batches: `runs/b<N>/result.json`, `runs/b<N>/antwort.md`,
   `runs/b<N>/review.md`. ACHTUNG (R13x, gemessen): `runs/b<N>/harness-facts.md` gehoert
   NICHT zu Batch N - der Harness legt sie in den Ordner des NAECHSTEN Batches
   (`runs/b<N+1>/harness-facts.md`, Kopfzeile "Review: bewertet wird Batch N").
   Nenne je Stichprobe das Ergebnis ("bestatigt" / "widerspricht: ...").
2. Lies fuer mindestens EINEN Batch die Denkbloecke des Workers
   `snapshots/b<N>/reasoning.jsonl` (read/grep) und sage, was dort steht, was in den
   aufbereiteten Zahlen NICHT steht.
Ziel: nicht dieselben aufbereiteten Zahlen als einzige Quelle nehmen.

=== GRENZEN ===
- Du entscheidest NICHTS und aenderst NICHTS (kein Anker, kein Code, keine Queue).
- Keine Datei schreiben, kein Ghidra, kein Netz.
- Hoechstens {max_befunde} Befunde. Lieber drei belastbare als sieben schwache.
"""


def build_prompt(cfg, state, grund) -> str:
    g = grenzen(cfg)
    kopf = [
        "# AUSSENSICHT (Meta-Review) - Silent Scope Decomp",
        f"Zeitpunkt: {now_iso()}",
        f"Anlass dieses Laufs: {grund}",
        f"Stand des Harness: Batch {int(state.batch or 0)}, Zustand {state.state}, "
        f"Ankerkopf BATCH {state.data.get('anchor_batch') or '?'}",
        f"Arbeitsverzeichnis: {cfg.decomp} (lesen) und {cfg.root} (lesen)",
        "",
        "Du bist NICHT der Reviewer. Der Reviewer bewertet einen Batch. Du pruefst das "
        "VORGEHEN: messen die Kennzahlen, was sie behaupten? Stimmen Aussagen in readme, "
        "AGENTS.md und Anker mit dem Code ueberein? Welche Probleme wiederholen sich? Ist "
        "der Plan beim gemessenen Durchsatz realistisch? Was wuerde ein Aussenstehender "
        "bezweifeln? Wurden fruehere Aussensicht-Befunde umgesetzt?",
        "",
        "Sei bewusst skeptisch und pruefe nach - eine Zahl aus einer Zusammenfassung ist "
        "kein Beleg. Wenn du etwas nicht pruefen kannst, sage das ausdruecklich.",
        "",
    ]
    return "\n".join(kopf) + "\n" + eingaben(cfg, state) + "\n\n" + \
        FORMAT_HINWEIS.format(max_befunde=int(g["max_befunde"])) + "\n"


# ------------------------------------------------------------------ Kommando
def build_command(cfg) -> list[str]:
    """Kommandozeile fuer die Aussensicht - IMMER frische Session, nur lesend.

    Gleiches Modell wie der Reviewer (Abo-Token), gleiche Pfad- und Secret-Regeln.
    """
    exe = str(cfg.get("claude", "exe"))
    tools_value = ",".join(["Read", "Grep", "Glob", GIT_TOOL])
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(cfg.get("claude", "model_reviewer", "claude-opus-5-5")),
           "--strict-mcp-config",
           "--permission-prompts", "none",
           "--max-turns", str(int(grenzen(cfg)["max_turns"])),
           "--tools", tools_value,
           "--allowedTools", *pfad_regeln((cfg.root, cfg.decomp)),
           *nur_lese_git_regeln(GIT_TOOL),
           "--disallowedTools", *VERBOTEN,
           *git_schreib_verbote(GIT_TOOL),
           *secrets_verbote(cfg.secrets_dir, *secrets.ALT_ORTE),
           *credential_verbote((cfg.root, cfg.decomp)),
           "--add-dir", str(cfg.root),
           "--add-dir", str(cfg.decomp),
           # R13w: IMMER eine frische Kennung - der Meta-Review soll ohne Verlauf urteilen.
           "--session-id", str(uuid.uuid4())]
    sp = Path(cfg.prompts_dir) / "aussensicht.md"
    if sp.is_file():
        cmd += ["--append-system-prompt-file", str(sp)]
    return cmd


# ------------------------------------------------------------------ Auswertung
_RE_BEFUND = re.compile(r"<BEFUND(?P<attrs>[^>]*)>(?P<body>.*?)</BEFUND>", re.S | re.IGNORECASE)
_RE_PRUEFUNG = re.compile(r"<PRUEFUNG(?P<attrs>[^>]*)/?>", re.IGNORECASE)
_RE_SUMMARY = re.compile(r"<AUSSENSICHT>(.*?)</AUSSENSICHT>", re.S | re.IGNORECASE)
_RE_ATTR = re.compile(r'(?P<name>[a-z]+)\s*=\s*"(?P<wert>[^"]*)"', re.IGNORECASE)
_RE_FELD = re.compile(r"^\s*(?P<name>beleg|aussage|empfehlung|text|befund)\s*:\s*(?P<wert>.*)$",
                      re.IGNORECASE | re.MULTILINE)
_RE_DATEI_ZEILE = re.compile(r"[\w./\\-]+\.(?:cpp|hpp|h|c|py|md|json|txt|inc|ps1|toml|cfg|tsv|csv)"
                             r"\s*:\s*\d+", re.IGNORECASE)
_RE_DATEI = re.compile(r"[\w./\\-]+\.(?:cpp|hpp|h|c|py|md|json|txt|inc|ps1|toml|cfg|tsv|csv)",
                       re.IGNORECASE)


def beleg_gueltig(beleg: str) -> bool:
    """Beleg-Pflicht, gelockert (Nutzerentscheidung 2026-09-28, Punkt b).

    Gueltig ist: `Datei:Zeile` ODER eine Zahl mit Quelldatei ODER die ausdrueckliche
    Fehlstelle ("Fehlstelle: gesucht in <Ort>, nicht gefunden"). Nur Befunde ganz ohne
    Beleg werden verworfen - eine ehrliche Fehlstelle ist ein Ergebnis, kein Fehler.
    """
    t = str(beleg or "").strip()
    if not t:
        return False
    if _RE_DATEI_ZEILE.search(t):
        return True
    if re.search(r"\d", t) and _RE_DATEI.search(t):
        return True
    return bool(re.search(r"fehlstelle\s*:", t, re.IGNORECASE))


def parse(text: str, max_befunde: int = 7) -> tuple[str, list[dict], list[dict], list[dict]]:
    """Antwort der Aussensicht lesen: (summary, befunde, verworfene, pruefungen).

    Befunde werden auf `max_befunde` gedeckelt und nach Gewicht sortiert; Befunde ohne
    jeden Beleg landen in `verworfene` (und werden gemeldet, nicht verschwiegen).
    """
    roh = text or ""
    m = _RE_SUMMARY.search(roh)
    summary = (m.group(1).strip() if m else "").strip()

    befunde: list[dict] = []
    verworfen: list[dict] = []
    for i, treffer in enumerate(_RE_BEFUND.finditer(roh), 1):
        attrs = {a.group("name").lower(): a.group("wert").strip()
                 for a in _RE_ATTR.finditer(treffer.group("attrs") or "")}
        felder = {f.group("name").lower(): f.group("wert").strip()
                  for f in _RE_FELD.finditer(treffer.group("body") or "")}
        gewicht = str(attrs.get("gewicht", "mittel")).strip().lower()
        if gewicht not in GEWICHT_REIHENFOLGE:
            gewicht = "mittel"
        empfaenger = str(attrs.get("empfaenger", "Reviewer")).strip().capitalize()
        if empfaenger not in EMPFAENGER:
            empfaenger = "Reviewer"
        eintrag = {
            "n": int(attrs.get("n") or i) if str(attrs.get("n") or i).isdigit() else i,
            "gewicht": gewicht,
            "empfaenger": empfaenger,
            "beleg": str(felder.get("beleg") or ""),
            "aussage": str(felder.get("aussage") or felder.get("text")
                           or felder.get("befund") or ""),
            "empfehlung": str(felder.get("empfehlung") or ""),
        }
        if beleg_gueltig(eintrag["beleg"]):
            befunde.append(eintrag)
        else:
            verworfen.append(eintrag)
    rang = {g: i for i, g in enumerate(GEWICHT_REIHENFOLGE)}
    befunde.sort(key=lambda b: rang.get(str(b["gewicht"]), 9))       # stabil
    befunde = befunde[:max(1, int(max_befunde))]

    pruefungen: list[dict] = []
    for treffer in _RE_PRUEFUNG.finditer(roh):
        attrs = {a.group("name").lower(): a.group("wert").strip()
                 for a in _RE_ATTR.finditer(treffer.group("attrs") or "")}
        if attrs.get("id"):
            pruefungen.append({"id": attrs["id"],
                               "status": str(attrs.get("status", "offen")).strip().lower()})
    return summary, befunde, verworfen, pruefungen


_RE_ANTWORT = re.compile(r"\bM(\d{3})-(\d+)\s*:\s*(uebernommen|übernommen|abgelehnt|erledigt|"
                         r"verworfen|offen)\b(?P<rest>[^\n]*)", re.IGNORECASE)


def antworten_uebernehmen(cfg, summary: str, batch: int) -> list[str]:
    """Antworten des Reviewers zu Befund-IDs uebernehmen (Nutzerentscheidung d).

    Der Reviewer muss jede `/claude`-Nachricht mit `M<batch>-<n>` beantworten
    ("M208-3: uebernommen (…)" / "M208-3: abgelehnt, Grund …"). Unbeantwortete Befunde
    bleiben `offen` und erscheinen weiter in `/bilanz`.
    """
    alle = ledger(cfg)
    if not alle:
        return []
    index = {str(b.get("id")): b for b in alle}
    geaendert: list[str] = []
    for m in _RE_ANTWORT.finditer(summary or ""):
        bid = f"M{m.group(1)}-{m.group(2)}"
        eintrag = index.get(bid)
        if eintrag is None:
            continue
        wort = m.group(3).lower()
        status = {"übernommen": "beantwortet", "uebernommen": "beantwortet"}.get(wort, wort)
        eintrag["status"] = status
        eintrag["antwort"] = (str(m.group(4) or "").strip()[:400]
                              or str(summary).strip()[:200])
        eintrag["antwort_batch"] = int(batch)
        eintrag["antwort_ts"] = now_iso()
        geaendert.append(bid)
    if geaendert:
        ledger_schreiben(cfg, alle)
    return geaendert


def verteile(cfg, state, summary: str, befunde: list[dict], pruefungen: list[dict],
             batch: int, log=None) -> dict:
    """Befunde in den Ledger uebernehmen, Verdikte anwenden, Empfaenger bedienen.

    Rueckgabe: {"ids": [...], "queue": [...], "nutzer": [...], "verdikte": [...]}
    """
    alle = ledger(cfg)
    index = {str(b.get("id")): b for b in alle}
    neu_ids: list[str] = []
    for i, b in enumerate(befunde, 1):
        bid = f"M{batch}-{i}"
        eintrag = dict(b)
        eintrag.update({"id": bid, "batch": int(batch), "ts": now_iso(), "status": "offen",
                        "quelle": "aussensicht", "antwort": "", "antwort_batch": None})
        index[bid] = eintrag
        alle.append(eintrag)
        neu_ids.append(bid)

    verdikte: list[str] = []
    for p in pruefungen:
        eintrag = index.get(str(p.get("id")))
        if eintrag is None:
            continue
        eintrag["status"] = p.get("status") or "offen"
        eintrag["letzte_pruefung"] = int(batch)
        verdikte.append(f"{p['id']} -> {eintrag['status']}")

    # Alte, laenger unbeantwortete Befunde mitzaehlen (Sichtbarkeit im Bericht)
    offen_alt = [b["id"] for b in alle
                 if str(b.get("status")) == "offen" and b["id"] not in neu_ids]
    ledger_schreiben(cfg, alle)
    if log:
        log.info("Aussensicht: Befunde uebernommen", batch=batch, neu=neu_ids,
                 verdikte=verdikte, offen_alt=len(offen_alt))
    return {"ids": neu_ids, "verdikte": verdikte, "offen_alt": offen_alt,
            "empfaenger": {b["id"]: b["empfaenger"] for b in alle if b["id"] in neu_ids}}


def befund_text(b: dict) -> str:
    """Text fuer eine `/claude`-Nachricht (Empfaenger Reviewer) oder Telegram."""
    return "\n".join([
        f"Aussensicht Batch {b.get('batch')} - Befund {b.get('id')} "
        f"(Gewicht {b.get('gewicht')}):",
        f"Beleg: {b.get('beleg')}",
        f"Aussage: {b.get('aussage')}",
        f"Empfehlung: {b.get('empfehlung')}",
        "",
        f"Bitte im naechsten Review beantworten: \"{b.get('id')}: uebernommen (…)\" oder "
        f"\"{b.get('id')}: abgelehnt, Grund …\".",
    ])


# ------------------------------------------------------------------ Lauf
class Ergebnis:
    def __init__(self):
        self.rc: int | None = None
        self.dauer_s: float = 0.0
        self.text: str = ""
        self.summary: str = ""
        self.befunde: list[dict] = []
        self.verworfen: list[dict] = []
        self.pruefungen: list[dict] = []
        self.modell: str = ""
        self.stream_path: str = ""

    def describe(self) -> str:
        return (f"rc={self.rc} dauer={self.dauer_s:.0f}s modell={self.modell or '-'} "
                f"befunde={len(self.befunde)} verworfen={len(self.verworfen)}")


MOCK_ANTWORT = """<AUSSENSICHT>
(Attrappe) Geprueft: zwei Zusammenfassungen gegen die Rohbelege, beide bestaetigt; ein
Denkblock gelesen. Ohne echten Lauf keine belastbare Aussage.
</AUSSENSICHT>

<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer">
Beleg: hx/aussensicht.py:1 (Attrappe)
Aussage: (Attrappe) Eine Kennzahl wird ohne Quelldatei berichtet.
Empfehlung: Die Quelle im Batch-Dokument mitnennen.
</BEFUND>
"""


def run(cfg, log, state, grund: str, mock: bool = False) -> Ergebnis:
    """Die Aussensicht fahren (synchron, begrenzt durch `[meta] wall_s`)."""
    res = Ergebnis()
    batch = int(state.batch or 0)
    prompt = build_prompt(cfg, state, grund)
    ziel = ensure_dir(Path(cfg.root) / "runs") / f"meta-{batch:03d}.jsonl"
    res.stream_path = str(ziel)
    if mock:
        roh = MOCK_ANTWORT
        write_text_atomic(ziel, json.dumps({"type": "result", "result": roh}) + "\n")
        res.text, res.rc, res.modell = roh, 0, "(Attrappe)"
    else:
        oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
        env = envs.reviewer_env(cfg, os.environ, oauth)
        cmd = build_command(cfg)
        t0 = time.time()
        run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=ziel,
                         on_event=None, hard_wall_s=float(grenzen(cfg)["wall_s"]),
                         log=log, stdin_text=prompt,
                         stderr_path=Path(cfg.root) / "runs" / f"meta-{batch:03d}.err.txt")
        res.rc, res.dauer_s = run.rc, run.duration_s
        stats = streamjson.StreamStats()
        for linie in read_text(ziel).splitlines():
            stats.feed(linie)
        res.text = stats.final_text() or ""
        res.modell = stats.model or ""
        streamjson.schreibe_rate_limit(cfg, stats.rate_limit, f"Aussensicht b{batch}")
        if log:
            log.info("Aussensicht fertig", batch=batch, rc=res.rc,
                     dauer_s=round(time.time() - t0, 1), modell=res.modell)
    g = grenzen(cfg)
    res.summary, res.befunde, res.verworfen, res.pruefungen = parse(res.text,
                                                                    int(g["max_befunde"]))
    return res


# ------------------------------------------------------------------ Ausloeser
def letzter_lauf(cfg, state) -> dict:
    return dict(state.data.get("meta") or {})


def faellig(cfg, state) -> list[str]:
    """Gruende, warum jetzt eine Aussensicht faellig ist ([] = nicht faellig)."""
    g = grenzen(cfg)
    meta = dict(state.data.get("meta") or {})
    batch = int(state.batch or 0)
    letzte = int(meta.get("letzter_lauf_batch") or 0)
    if meta.get("geprueft_batch") == batch and not meta.get("vorgemerkt"):
        return []                              # fuer diesen Batch schon entschieden
    gruende: list[str] = []
    if meta.get("vorgemerkt"):
        gruende.append("vorgemerkt durch /meta")
    # Die 10er-Regel greift erst, wenn schon einmal eine Aussensicht gelaufen ist:
    # sonst wuerde der ERSTE Start nach dieser Aenderung sofort einen Opus-Lauf
    # ausloesen (207 Batches Historie). Die erste Aussensicht loest der Nutzer aus.
    if letzte > 0 and batch > 0 and batch - letzte >= int(g["every_batches"]):
        gruende.append(f"alle {int(g['every_batches'])} Batches "
                       f"(letzte Aussensicht: Batch {letzte})")
    abb = state.data.get("letzter_abbruch") or {}
    if abb and int(abb.get("batch") or 0) > letzte:
        gruende.append(f"Worker-Abbruch in Batch {abb.get('batch')} ({abb.get('grund')})")
    for name, muster in (("Meilenstein erreicht", r"MEILENSTEIN ERREICHT:"),
                         ("Abbruchkriterium erreicht", r"ABBRUCHKRITERIUM ERREICHT:")):
        for b, zeile in _marker(cfg, muster)[:1]:
            gruende.append(f"{name} - laut Review in runs/b{b}: {zeile[:120]}")
    still = b_schritt_stillstand(cfg)
    if still:
        gruende.append(still)
    kern = kernzahl_stillstand(cfg)
    if kern:
        gruende.append("Kernzahl ohne Bewegung ueber die letzten C-Batches: "
                       + "; ".join(kern[:3]))
    return gruende


def bericht(cfg, batch: int, grund: str, res: Ergebnis, verteilung: dict,
            gruende: list[str]) -> str:
    """Der Bericht `runs/meta-<batch>.md`."""
    zeilen = [
        f"# Aussensicht Batch {batch}",
        "",
        f"- Zeitpunkt: {now_iso()}",
        f"- Anlass: {grund}",
        f"- Ausloeser-Gruende: {'; '.join(gruende[:6]) or '-'}",
        f"- Lauf: {res.describe()}",
        "",
        "## Zusammenfassung",
        res.summary or "(keine Zusammenfassung im Antwortformat)",
        "",
        f"## Befunde ({len(res.befunde)})",
    ]
    for b in res.befunde:
        zeilen += [f"### {b.get('gewicht')} | Empfaenger {b.get('empfaenger')}",
                   f"- Beleg: {b.get('beleg')}", f"- Aussage: {b.get('aussage')}",
                   f"- Empfehlung: {b.get('empfehlung')}", ""]
    if res.verworfen:
        zeilen.append(f"## Verworfene Befunde ohne Beleg ({len(res.verworfen)})")
        for b in res.verworfen:
            zeilen.append(f"- {str(b.get('aussage'))[:200]} (Beleg fehlte: "
                          f"{str(b.get('beleg'))[:120] or '-'})")
        zeilen.append("")
    if verteilung.get("verdikte"):
        zeilen.append("## Verdikte zu frueheren Befunden")
        zeilen += [f"- {v}" for v in verteilung["verdikte"]]
        zeilen.append("")
    if verteilung.get("offen_alt"):
        zeilen.append("## Weiter offen")
        zeilen += [f"- {i}" for i in verteilung["offen_alt"]]
        zeilen.append("")
    zeilen += ["", "## Rohantwort", "```", (res.text or "(leer)")[:20000], "```"]
    return "\n".join(zeilen) + "\n"


def bericht_schreiben(cfg, batch: int, grund: str, res: Ergebnis, verteilung: dict,
                      gruende: list[str]) -> Path:
    p = bericht_pfad(cfg, batch)
    write_text_atomic(p, bericht(cfg, batch, grund, res, verteilung, gruende))
    write_json_atomic(json_pfad(cfg, batch), {
        "batch": int(batch), "ts": now_iso(), "grund": grund, "gruende": list(gruende),
        "summary": res.summary, "rc": res.rc, "dauer_s": res.dauer_s, "modell": res.modell,
        "befunde": res.befunde, "verworfen": res.verworfen, "pruefungen": res.pruefungen,
        "ids": verteilung.get("ids") or [], "verdikte": verteilung.get("verdikte") or [],
        "offen_alt": verteilung.get("offen_alt") or [],
    })
    return p
