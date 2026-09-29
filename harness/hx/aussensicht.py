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
    `<BEFUND n="1" gewicht="hoch" empfaenger="Reviewer|Nutzer">Beleg: … Aussage: … Empfehlung: …</BEFUND>`
    Der Empfaenger folgt dem **Entscheidungstraeger** (R13y): Reviewer = Orchestrator-Sache
    (Regelfall), Nutzer = nur Ziel/Scope/Budget/fruehere Nutzerentscheidungen. Ein Befund mit
    beiden Anteilen wird mechanisch geteilt (`M208-5a` Nutzer / `M208-5b` Reviewer,
    `entscheidungstraeger`).
    und je frueherem Befund `<PRUEFUNG id="M208-3" status="erledigt|offen|verworfen"/>`.

Ausloeser (`faellig`): Vormerkung durch `/meta`, alle `[meta] every_batches` Batches, ein
Worker-Abbruch, `MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:` in der neuesten
Review-Zusammenfassung, ein stehengebliebener B-Schritt (Weg B) bzw. eine C-Kernzahl ohne
Bewegung ueber die letzten **C-Batches**. Je Batch wird hoechstens einmal entschieden
(`geprueft_batch`).

Entprellt (Auftraege 2026-09-29): ein liegengebliebener C-Stillstand feuert nur EINMAL je
neuem C-Batch - die Marke `kernzahl_gemeldet_bis` (im Zustand, `state.data["meta"]`) haelt
den neuesten bereits gemeldeten C-Batch und wird erst nach einem erfolgreichen Lauf
(rc=0) gesetzt, an dem der Grund beteiligt war. Stillstand heisst **allein: `C Koepfe`
unveraendert** (Ist-Delta 0) bei `SOLL-KOEPFE > 0`; `C Faelle` steht nur als Information
im Anlass-Text. Auch der eigene Grund `c_soll_null_serie` (drei C-Batches in Folge mit
`SOLL-KOEPFE: 0`) ist entprellt (`c_soll_null_gemeldet_bis`): er feuert erst wieder, wenn
ein NEUER C-Batch die Serie verlaengert oder eine neue Serie entsteht.

R13z (2026-09-28): die **Quote** des Registers steht in `/bilanz` und `/status`
(`zeile`/`quote`): "Aussensicht: n Befunde, davon u uebernommen, a abgelehnt, o offen".
Gezaehlt wird je Kennung; die Zuordnung der Statusworte zu den Klassen macht `klasse`
(s. dort) - der Reviewer schreibt das Verdikt, das Wort wird so gespeichert, wie er es
geschrieben hat.

Belege/Regeln dieser Datei: `docs/_r13w_belege.md`, Doku `docs/bedienung.md`.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import uuid
from pathlib import Path

from . import envs, protocol, secrets, stand, streamjson
from .proc import run_stream
from .profiles import credential_verbote, git_schreib_verbote, nur_lese_git_regeln, pfad_regeln, secrets_verbote
from .util import (ensure_dir, now_iso, read_json, read_text, write_json_atomic,
                   write_text_atomic)

# ------------------------------------------------------------------ Vorgaben
# `every_batches` ist die Vorgabe, falls der Schluessel in `harness.toml` fehlt; die
# eingestellte Zahl steht dort (`[meta]`, seit R13z = 3, Begruendung in
# docs/bedienung.md Paragraph 12e).
STANDARD = {"every_batches": 3, "wall_s": 900, "max_turns": 30, "max_befunde": 7,
            "summaries": 10, "bilanz_zeitfenster": 12, "bschritt_stillstand_batches": 3}
# `bschritt_stillstand_batches` heisst seit R13ah: so viele **B-Batches in Folge** muessen
# denselben Halt-PC zeigen und duerfen im Wegmass nicht steigen (Hybrid-Lauf-Zeile). Der
# Schluesselname bleibt (eine Aenderung wuerde nur Konfiguration und Doku umbenennen).

# Alles Sperrende - dieselbe Haltung wie beim Reviewer, nur ohne MCP.
VERBOTEN = ["Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch",
            "Task", "TodoWrite", "SlashCommand", "Skill", "mcp__ghidra"]
GIT_TOOL = "PowerShell"

GEWICHT_REIHENFOLGE = ("hoch", "mittel", "niedrig")
EMPFAENGER = ("Reviewer", "Nutzer")

# Kernzahlen des C-Strangs aus `stand.kernzahlen` (R13x: C Koepfe = Preflight-Zeile,
# Paket E = Ist-Spalte der Soll/Ist-Tafel) - Befund Nr. 2:
# sie werden NUR ueber die letzten C-Batches verglichen, nie ueber einen B-Batch hinweg.
#
# Ausloeser (Auftrag 2026-09-29): NUR die Kopfzahl entscheidet. Frueher standen hier auch
# `C Faelle`, Paket E, Bau-Liste, Inventar und C-Vorrat - eine einzige unveraenderte
# genuegte (ODER). `C Abweichungen` ist ganz entfernt (Zielwert 0, stand immer still), und
# **Stillstand heisst jetzt allein: `C Koepfe` unveraendert** (Ist-Delta 0 bei
# `SOLL-KOEPFE > 0`).
KERNZAHL_KRITERIUM = (("c_koepfe", "C Koepfe"),)
# `C Faelle` wird nur noch als INFORMATION im Anlass-Text gefuehrt - kein eigener
# Ausloeser (Auftrag 2026-09-29).
KERNZAHL_INFO = (("c_faelle", "C Faelle"),)
# Anzeige (Kriterium + Information); enthaelt bewusst kein `c_abweichungen` mehr.
KERNZAHLEN = KERNZAHL_KRITERIUM + KERNZAHL_INFO

# Entprellung (Auftraege 2026-09-29). Beide Marken liegen in `state.data["meta"]` und
# halten die Nummer des NEUESTEN C-Batches, fuer den der jeweilige Grund schon gemeldet
# wurde. Fehlt `kernzahl_gemeldet_bis` (aeltere Zustaende), gilt einmalig 210 - der
# Stillstand B207/B210 ist in `runs/meta-212.md` gemeldet und darf nicht erneut feuern.
# `c_soll_null_gemeldet_bis` startet bei 0: nach der geltenden Regel "fehlende
# SOLL-KOEPFE-Zeile = SOLL > 0" bilden B207/B210/B213 keine SOLL-0-Serie (Bericht zum
# Nachtrag 2026-09-29), es gibt also nichts zu unterdruecken.
MARKE_SCHLUESSEL = "kernzahl_gemeldet_bis"
MIGRATION_MARKE = 210
MARKE_SOLL_SCHLUESSEL = "c_soll_null_gemeldet_bis"
MIGRATION_SOLL_MARKE = 0
# Der Wortlaut des Grundes (auch die Kennung, an der `kernzahl_beteiligt` ihn erkennt).
KERNZAHL_GRUND = "Kernzahl ohne Bewegung ueber die letzten C-Batches"
# Eigener Grund: so viele C-Batches in Folge ohne Bau-Auftrag (`SOLL-KOEPFE: 0`).
C_SOLL_GRUND = "c_soll_null_serie"
SOLL_NULL_SERIE = 3

# Entprellung des Stillstands-Ausloesers (R13ah, Aussensicht B214 Befund 4). Das Feld
# `B-SCHRITT:` des Reviews mass nichts (B212 2/5, B213 2/5 - waehrend der Hybrid-Lauf in
# B214 von 28/407 auf 448/42599 lief). Gemessen wird jetzt die ZEILE `Hybrid-Lauf` der
# Preflight-Datei: Feld 2 (Halt-PC) und Feld 4 (Wegmass-Zaehler). Der Preflight liegt VOR
# dem Review vor - der Ausloeser kommt damit frueher. Die Marke haelt die Nummer des
# neuesten VERGLICHENEN B-Batches (hier: der Preflight-Dateiname, also der Batch selbst).
MARKE_HYBRID_SCHLUESSEL = "hybrid_gemeldet_bis"
# Der Wortlaut des Grundes (Kennung fuer `hybrid_beteiligt`).
HYBRID_GRUND = "Hybrid-Lauf"
# Wie viele B-Batches IN FOLGE denselben Halt-PC und kein steigendes Wegmass zeigen
# muessen (`[meta] bschritt_stillstand_batches`, Vorgabe 3).
HYBRID_STILLSTAND_BATCHES = 3


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


def ledger_schreiben(cfg, befunde: list[dict],
                    verworfen: list[dict] | None = None,
                    tiefenprobe: dict | None = None) -> None:
    """Das Register schreiben.

    R13aa (Punkt 2): unter dem zweiten Schluessel `verworfen` stehen die Befunde, die
    die **Beleg-Regel** aussortiert hat. Sie werden NICHT weggeworfen - `/fragen` zeigt
    sie als "verworfen - pruefen?", damit ein zu strenges Urteil auffaellt. Wird
    `verworfen` nicht mitgegeben, bleibt der vorhandene Stand stehen (sonst loeschte
    jeder Register-Schreibvorgang die Liste).

    R13ac3: dasselbe gilt fuer den dritten Schluessel `tiefenprobe` (Rotationsstand der
    Tiefenprobe, s. `tiefenprobe_waehlen`) - er darf bei keinem Schreibvorgang verloren
    gehen.
    """
    daten: dict = {"updated_at": now_iso(), "befunde": list(befunde)}
    alt = read_json(ledger_pfad(cfg), {}) or {}
    if not isinstance(alt, dict):
        alt = {}
    if verworfen is None:
        verworfen = list(alt.get("verworfen") or [])
    daten["verworfen"] = list(verworfen)
    if tiefenprobe is None:
        tiefenprobe = dict(alt.get(TIEFE_SCHLUESSEL) or {})
    if tiefenprobe:
        daten[TIEFE_SCHLUESSEL] = tiefenprobe
    write_json_atomic(ledger_pfad(cfg), daten)


def verworfene(cfg, batch: int | None = None) -> list[dict]:
    """Die von der Beleg-Regel verworfenen Befunde (leer, wenn es keine gibt).

    `batch=N` liefert nur die des Laufs zu Batch N - so zeigt `/fragen` die frischesten
    als "verworfen - pruefen?" (der gespeicherte Stand bleibt vollstaendig erhalten).
    """
    p = ledger_pfad(cfg)
    if not p.is_file():
        return []
    try:
        daten = json.loads(read_text(p))
    except (OSError, ValueError):
        return []
    liste = daten.get("verworfen") if isinstance(daten, dict) else None
    out = [b for b in liste if isinstance(b, dict)] if isinstance(liste, list) else []
    if batch is not None:
        out = [b for b in out if int(b.get("batch") or 0) == int(batch)]
    return out


def verworfene_speichern(cfg, batch: int, liste: list[dict]) -> list[str]:
    """Verworfene Befunde ins Register uebernehmen (Kennung `M<batch>-v<n>`).

    R13aa (Punkt 2): ein Befund, den nur die Beleg-Regel aussortiert hat, ist damit
    nicht verloren - er steht mit Wortlaut in `runs/meta-<batch>.md`, im Register und in
    `/fragen` ("verworfen - pruefen?"). Eine EIGENE Kennung (`-v1`) ist noetig, weil die
    Nummern der angenommenen Befunde beim Verteilen nach Gewicht neu vergeben werden -
    sonst koennten zwei Eintraege dieselbe Kennung tragen.
    """
    if not liste:
        return []
    alt = [b for b in verworfene(cfg) if int(b.get("batch") or 0) != int(batch)]
    neu: list[dict] = []
    for i, b in enumerate(liste, 1):
        e = {k: v for k, v in dict(b).items() if k != "n"}
        e.update({"id": f"M{int(batch)}-v{i}", "batch": int(batch), "ts": now_iso(),
                  "status": "offen", "quelle": "aussensicht",
                  "verworfen": "Beleg-Regel"})
        neu.append(e)
    ledger_schreiben(cfg, ledger(cfg), verworfen=alt + neu)
    return [str(e["id"]) for e in neu]


def offene(cfg) -> list[dict]:
    """Befunde, die noch nicht beantwortet/geprueft sind."""
    return [b for b in ledger(cfg) if klasse(b) == "offen"]


# ------------------------------------------------- Quote des Registers (R13z)
# Der Reviewer schreibt "M208-3: uebernommen (…)" oder "M208-3: abgelehnt, Grund …"
# (`antworten_uebernehmen`), die Aussensicht selbst schreibt in `<PRUEFUNG …>` "erledigt"
# bzw. "verworfen". Fuer die Quote zaehlen diese Woerter in zwei Klassen zusammen:
#
#   uebernommen  uebernommen | beantwortet (das alte Wort aus R13w, noch in aelteren
#                Registereintraegen) | erledigt (die Aussensicht hat es nachgeprueft)
#   abgelehnt    abgelehnt | verworfen
#   offen        alles Uebrige - auch ein UNBEKANNTES Wort. Ein Befund verschwindet
#                nicht dadurch aus der offenen Liste, dass ein Status falsch geschrieben
#                ist (dieselbe Haltung wie beim Ankerposten: nichts still umdeuten).
# R13ak (29.09.2026): `zurueckgestellt` gehoert in die Klasse `uebernommen`. Gemessen:
# `runs/b211/review.md:15` antwortet "M209-3b: zurueckgestellt (Nutzer), spaetestens
# B216" - der Befund war damit BEANTWORTET, stand aber weiter als "offen" im Register
# (und wurde nicht mehr vorgelegt). Als offen gezaehlt waere er schlicht falsch; die
# Absage ("abgelehnt") ist er auch nicht. Das Wort selbst bleibt im Register stehen
# (`status`), nur die Quote zaehlt ihn zu den uebernommenen.
UEBERNOMMEN_WORTE = ("uebernommen", "beantwortet", "erledigt", "zurueckgestellt")
ABGELEHNT_WORTE = ("abgelehnt", "verworfen")


def klasse(befund: dict) -> str:
    """`uebernommen` | `abgelehnt` | `offen` - die Klasse, in die ein Befund zaehlt.

    R13ak: Umlaute werden vor dem Vergleich vereinheitlicht (`zurückgestellt` ==
    `zurueckgestellt`) - sonst fiele ein Eintrag, den ein anderer Schreibweg mit Umlaut
    abgelegt hat, still in die Klasse `offen` zurueck.
    """
    wert = str((befund or {}).get("status") or "offen").strip().lower().replace("ü", "ue")
    if wert in UEBERNOMMEN_WORTE:
        return "uebernommen"
    if wert in ABGELEHNT_WORTE:
        return "abgelehnt"
    return "offen"


# ------------------------------------------------- Tiefenprobe (R13ac3, 2026-09-29)
# Nutzerauftrag: zusaetzlich zur Stichprobe des neuesten Batches wird je Lauf EIN
# zufaelliger Batch aus den letzten `TIEFE_FENSTER` gelaufenen Batches in der Tiefe
# geprueft (Denkbloecke, Belege, Behauptungen des Abschlussberichts gegen die Rohdaten).
# Der Rotationsstand liegt im Register (`state/meta_befunde.json` -> `tiefenprobe`):
# "derselbe Batch wird erst wieder gezogen, wenn alle anderen des Fensters dran waren."
TIEFE_FENSTER = 10
TIEFE_SCHLUESSEL = "tiefenprobe"


def gelaufene_batches(cfg) -> list[int]:
    """Die Batches mit einem abgeschlossenen Lauf (`runs/b<N>/result.json`), aufsteigend.

    Nur diese koennen tief geprueft werden - ein Batch ohne Ergebnis hat keine Rohdaten.
    """
    try:
        ordner = list((Path(cfg.root) / "runs").glob("b*"))
    except OSError:
        return []
    out: list[int] = []
    for p in ordner:
        m = re.fullmatch(r"b(\d+)", p.name)
        if m and (p / "result.json").is_file():
            out.append(int(m.group(1)))
    return sorted(out)


def tiefenprobe_stand(cfg) -> dict:
    """Der gespeicherte Rotationsstand: `{"gezogen": [...], "letzte": int|None}`.

    `gezogen` wird **gegen das aktuelle Fenster gelesen**: ein Batch, der aus den letzten
    zehn herausgefallen ist, zaehlt nicht mehr zur Rotation (sonst blockierte er einen
    Platz, ohne je wieder gezogen werden zu koennen).
    """
    fenster = gelaufene_batches(cfg)[-TIEFE_FENSTER:]
    daten = read_json(ledger_pfad(cfg), {}) or {}
    stand_daten = daten.get(TIEFE_SCHLUESSEL) if isinstance(daten, dict) else None
    if not isinstance(stand_daten, dict):
        return {"gezogen": [], "letzte": None, "fenster": fenster}
    gezogen = [int(b) for b in (stand_daten.get("gezogen") or []) if str(b).isdigit()]
    letzte = stand_daten.get("letzte")
    return {"gezogen": [b for b in gezogen if b in fenster],
            "letzte": int(letzte) if letzte else None, "fenster": fenster}


def tiefenprobe_waehlen(cfg, zufall=None) -> dict:
    """Einen Batch aus den letzten `TIEFE_FENSTER` ziehen, den noch keiner dran hatte.

    Rueckgabe: `{batch, fenster, gezogen, kandidaten, neu_zyklus, grund}`.
    `batch=None` heisst: kein abgeschlossener Lauf im Fenster - dann gibt es keine
    Tiefenprobe (und der Prompt sagt das).

    `zufall` ist ein Objekt mit `choice` (`random` als Vorgabe); Tests geben einen
    `random.Random(<seed>)` mit, damit die Ziehung reproduzierbar ist.
    """
    alle = gelaufene_batches(cfg)
    fenster = alle[-TIEFE_FENSTER:]
    if not fenster:
        return {"batch": None, "fenster": [], "gezogen": [], "kandidaten": [],
                "neu_zyklus": False, "grund": "kein abgeschlossener Lauf gefunden"}
    stand_daten = tiefenprobe_stand(cfg)
    gezogen = list(stand_daten["gezogen"])
    kandidaten = [b for b in fenster if b not in gezogen]
    neu_zyklus = False
    if not kandidaten:
        # Alle des Fensters waren dran -> neuer Zyklus, das Fenster ist wieder voll.
        neu_zyklus = True
        gezogen = []
        kandidaten = list(fenster)
    wahl = int((zufall or random).choice(kandidaten))
    return {"batch": wahl, "fenster": fenster, "gezogen": gezogen,
            "kandidaten": kandidaten, "neu_zyklus": neu_zyklus,
            "grund": ("alle anderen waren dran - neuer Zyklus" if neu_zyklus else "")}


def tiefenprobe_merken(cfg, wahl: dict) -> dict:
    """Die Ziehung in den Rotationsstand uebernehmen (Register bleibt vollstaendig)."""
    batch = wahl.get("batch")
    if batch is None:
        return tiefenprobe_stand(cfg)
    daten = read_json(ledger_pfad(cfg), {}) or {}
    if not isinstance(daten, dict):
        daten = {}
    alt = daten.get(TIEFE_SCHLUESSEL) if isinstance(daten.get(TIEFE_SCHLUESSEL), dict) else {}
    gezogen = [int(b) for b in (alt.get("gezogen") or []) if str(b).isdigit()]
    gezogen = ([b for b in gezogen if b in wahl["fenster"]]
               + ([int(batch)] if int(batch) not in gezogen else []))
    stand_daten = {"gezogen": gezogen, "letzte": int(batch), "ts": now_iso(),
                   "fenster": list(wahl["fenster"])}
    ledger_schreiben(cfg, ledger(cfg), tiefenprobe=stand_daten)
    return stand_daten


def letzte_bericht_batches(cfg) -> list[int]:
    """Die Batches, fuer die ein Aussensicht-Bericht vorliegt (`runs/meta-<N>.json`).

    R13aa (Punkt 2): damit laesst sich sagen, welcher Lauf der NEUESTE war - `/fragen`
    zeigt die verworfenen Befunde nur, wenn dieser Lauf welche verworfen hat.
    """
    try:
        dateien = list((Path(cfg.root) / "runs").glob("meta-*.json"))
    except OSError:
        return []
    out: list[int] = []
    for p in dateien:
        m = re.fullmatch(r"meta-(\d+)\.json", p.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def quote(cfg) -> dict:
    """Das Register nach Klassen gezaehlt: {"gesamt", "uebernommen", "abgelehnt", "offen"}.

    Gezaehlt wird **je Kennung** (jeder Registereintrag): ein geteilter Befund
    (`M208-5a` Nutzer / `M208-5b` Reviewer) zaehlt zweimal, weil beide Teile einzeln
    beantwortet werden.
    """
    q = {"gesamt": 0, "uebernommen": 0, "abgelehnt": 0, "offen": 0}
    for b in ledger(cfg):
        q["gesamt"] += 1
        q[klasse(b)] += 1
    return q


def zeile(cfg) -> str:
    """Eine Zeile fuer `/bilanz` und `/status` ('' = es gab noch keine Aussensicht).

    Aufbau (R13z, Nutzerauftrag): `Aussensicht: n Befunde, davon u uebernommen,
    a abgelehnt, o offen` - dahinter in Klammern die letzte Aussensicht (Batch und Zahl
    der Befunde des Laufs) und der eingestellte **Takt** (`harness.toml`,
    `[meta] every_batches`). Die Quote ist die Grundlage der Auswertung nach einer Woche.
    """
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
    q = quote(cfg)
    kopf = (f"Aussensicht: {q['gesamt']} Befunde, davon {q['uebernommen']} uebernommen, "
            f"{q['abgelehnt']} abgelehnt, {q['offen']} offen")
    herkunft = [f"letzte Aussensicht: Batch {batch or '?'}"]
    if berichte and anzahl:
        herkunft.append(f"{anzahl} Befunde in diesem Lauf")
    try:
        takt = int(grenzen(cfg).get("every_batches") or 0)
    except (TypeError, ValueError):
        takt = 0
    if takt:
        herkunft.append(f"Takt: alle {takt} Batches")
    return kopf + "   (" + "; ".join(herkunft) + ")"


# ------------------------------------------- Entscheidungstraeger (R13y)
# Was der Orchestrator laut AGENTS.md "Roles" SELBST entscheiden darf, geht an den
# Reviewer. An den Nutzer geht nur, was Ziel, Scope, Budget oder eine fruehere
# Nutzerentscheidung beruehrt. Ein Befund mit beiden Anteilen wird geteilt.
# Absichtlich eine kurze, pruefbare Liste von WENDUNGEN (kein Sprachmodell): "Ziel des
# naechsten Batches" ist ein Zuschnitt-Thema des Reviewers und darf NICHT als "Ziel"
# durchschlagen, deshalb stehen dort "projektziel"/"zielsatz" und nicht "ziel".
NUTZER_THEMEN = re.compile(
    r"(projektziel|zielsatz|projektumfang|umfang des projekts|\bscope\b|\bbudget\b|"
    r"tagesbudget|kostenrahmen|\bkontingent\b|\babo\b|priorisier\w*|priorit\w*|"
    r"\breadme\b|nutzerentscheid\w*|nutzerauftrag\w*|deine entscheidung|"
    r"abbruchkriteri\w*|liefergegenstand\w*|was wird nie gebaut|nicht mehr gebaut)",
    re.IGNORECASE)
_SATZ_ENDE = re.compile(r"(?<=[.!?])\s+")


def _saetze(text: str) -> list[str]:
    """Einen Text in Saetze zerlegen (Leerraum normalisiert, leere Teile weg)."""
    t = " ".join(str(text or "").split())
    return [s.strip() for s in _SATZ_ENDE.split(t) if s.strip()] if t else []


def _ist_nutzer_thema(text: str) -> bool:
    return bool(NUTZER_THEMEN.search(str(text or "")))


def entscheidungstraeger(befund: dict) -> list[dict]:
    """Befund nach Entscheidungstraeger aufteilen (R13y) -> 1 oder 2 Befunde.

    Regel (Nutzerauftrag 2026-09-28):
      * Saetze der Aussage, die Ziel/Scope/Budget/fruehere Nutzerentscheidungen
        beruehren, gehen an den **Nutzer**;
      * alle anderen an den **Reviewer** (der Orchestrator entscheidet den Regelfall
        selbst, AGENTS.md "Roles");
      * hat der Befund beide Anteile, entstehen ZWEI Befunde - gleicher Beleg, gleiches
        Gewicht, getrennte Kennungen (`M208-5a` Nutzer, `M208-5b` Reviewer);
      * die Empfehlung geht an den Teil, zu dem sie inhaltlich gehoert; beim geteilten
        Befund bleibt der andere Teil ohne Empfehlung (dann steht dort keine Zeile).

    Die Aufteilung ist absichtlich mechanisch und nachpruefbar - sie ersetzt die
    Empfaengerangabe des Modells, wenn sie widerspricht.
    """
    aussage = str(befund.get("aussage") or "")
    empfehlung = str(befund.get("empfehlung") or "")
    saetze = _saetze(aussage)
    nutzer = [s for s in saetze if _ist_nutzer_thema(s)]
    rest = [s for s in saetze if not _ist_nutzer_thema(s)]
    e_nutzer = _ist_nutzer_thema(empfehlung)
    if not saetze:
        return [dict(befund, empfaenger="Nutzer" if e_nutzer else "Reviewer",
                     geteilt=False)]
    if not nutzer:
        return [dict(befund, empfaenger="Reviewer", geteilt=False)]
    if not rest:
        return [dict(befund, empfaenger="Nutzer", geteilt=False)]
    return [dict(befund, empfaenger="Nutzer", geteilt=True, teil="a",
                 aussage=" ".join(nutzer), empfehlung=empfehlung if e_nutzer else ""),
            dict(befund, empfaenger="Reviewer", geteilt=True, teil="b",
                 aussage=" ".join(rest), empfehlung="" if e_nutzer else empfehlung)]


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


# R13ah (Aussensicht B214, Befund 4): die frueheren Funktionen `b_schritt` und
# `b_schritt_stillstand` sind ENTFALLEN. Sie lasen die Pflichtzeile `B-SCHRITT: <n>/5`
# aus den Review-Zusammenfassungen - eine Zahl, die nichts mass (B212 2/5, B213 2/5,
# waehrend der Hybrid-Lauf in B214 von 28/407 auf 448/42599 lief). Der Stillstand wird
# jetzt aus der Preflight-Zeile `Hybrid-Lauf` gemessen (`hybrid_stillstand` unten), die
# VOR dem Review vorliegt. Die Klassifikation "B-Batch oder C-Batch" (`stand.strang_von_
# batch`) nutzt die Zeile weiterhin als einen Beleg - sie bleibt deshalb im Prompt.


def hybrid_stillstand(cfg) -> str:
    """Steht der Hybrid-Lauf ueber die letzten B-Batches still? ('' = nein)

    Verglichen werden die letzten `[meta] bschritt_stillstand_batches` **B-Batches in
    Folge** (Vorgabe 3), fuer die es eine Zeile `Hybrid-Lauf` gibt. Stillstand heisst:
    der **Halt-PC** (Feld 2) ist in allen gleich **und** das **Wegmass** (Feld 4,
    Zaehler) steigt nicht.

    C-Batches zaehlen nicht mit (sie haben keinen B-Fortschritt), und Batches ohne die
    Zeile (vor B212) fehlen in der Reihe - beides wird NICHT geraten.
    """
    n = max(2, int(grenzen(cfg).get("bschritt_stillstand_batches")
                   or HYBRID_STILLSTAND_BATCHES))
    verlauf = stand.hybrid_verlauf(cfg, n + 4)
    reihe = [e for e in verlauf
             if str(stand.strang_von_batch(cfg, int(e["batch"])).get("strang")) == "B"]
    if len(reihe) < n:
        return ""
    letzte = reihe[-n:]
    pcs = {e["halt_pc"] for e in letzte}
    if len(pcs) != 1:
        return ""
    wege = [int(e["weg"]) for e in letzte]
    if any(b > a for a, b in zip(wege, wege[1:])):
        return ""                      # das Wegmass STEIGT - also Fortschritt
    b_erst, b_letzt = letzte[0]["batch"], letzte[-1]["batch"]
    b_reihe = ", ".join(f"B{e['batch']}" for e in letzte)
    return (f"Hybrid-Lauf haengt: Halt-PC {letzte[-1]['halt_pc']} unveraendert und "
            f"Wegmass {wege[0]}/{letzte[0]['weg_gesamt']} -> "
            f"{wege[-1]}/{letzte[-1]['weg_gesamt']} steigt nicht "
            f"({b_reihe}, Quelle analysis/{letzte[-1]['datei']}, Zeile \"Hybrid-Lauf\") "
            f"- kein Fortschritt ueber {n} B-Batches (B{b_erst} bis B{b_letzt})")


def hybrid_neuester_b(cfg) -> int:
    """Die Nummer des neuesten B-Batches mit `Hybrid-Lauf`-Zeile (0 = keiner)."""
    reihe = [e for e in stand.hybrid_verlauf(cfg, 6)
             if str(stand.strang_von_batch(cfg, int(e["batch"])).get("strang")) == "B"]
    return int(reihe[-1]["batch"]) if reihe else 0


def hybrid_gemeldet_bis(meta: dict) -> int:
    """Die Stillstands-Marke; fehlt sie, gilt 0 (nichts gemeldet)."""
    wert = (meta or {}).get(MARKE_HYBRID_SCHLUESSEL)
    try:
        return int(wert) if wert is not None else 0
    except (TypeError, ValueError):
        return 0


def hybrid_marke_setzen(cfg, state) -> int:
    """Die Marke auf den neuesten verglichenen B-Batch setzen.

    Wird - wie `kernzahl_marke_setzen` - erst NACH einem erfolgreichen Lauf (rc=0) gerufen,
    an dem der Grund beteiligt war.
    """
    neu = hybrid_neuester_b(cfg)
    if neu > 0:
        meta = dict(state.data.get("meta") or {})
        meta[MARKE_HYBRID_SCHLUESSEL] = int(neu)
        state.data["meta"] = meta
    return int(neu)


def hybrid_beteiligt(gruende) -> bool:
    """War der Hybrid-Lauf-Stillstand an diesen Ausloeser-Gruenden beteiligt?"""
    return any(str(g).startswith(HYBRID_GRUND) for g in (gruende or []))


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
    """Ist dieser Batch ein B-Batch? (`stand.strang_von_batch` - unbekannt = nein).

    R13aa (Punkt 1): vorher hing das allein an der Pflichtzeile `B-SCHRITT:` im Review.
    Die fehlt seit B205 in JEDEM Review, also hielt der Stillstands-Ausloeser B208/B209
    fuer C-Batches und schlug Alarm, weil sich die C-Zahl in einem B-Batch nicht bewegt.
    """
    return stand.strang_von_batch(cfg, int(batch)).get("strang") == "B"


def c_batches(cfg) -> list[dict]:
    """Die C-Batch-Eintraege des Bilanzfensters (B-Batches ausgelassen).

    Welcher Batch ein B-Batch ist, kommt aus `stand.strang_von_batch` (R13aa: Pflichtzeile,
    Auftrag, hybrid-plan.md) - nicht allein aus der Pflichtzeile, die in der Praxis fehlte.
    """
    fenster = stand.kernzahlen(cfg, int(grenzen(cfg)["bilanz_zeitfenster"]))
    return [e for e in fenster if not ist_b_batch(cfg, int(e.get("batch") or 0))]


def soll_koepfe_batch(cfg, batch: int, log=None) -> int | None:
    """`SOLL-KOEPFE` aus `runs/b<N>/auftrag.md` - oder None.

    Der Reviewer gibt die Sollzahl seit B211 mit der Zeile `SOLL-KOEPFE: <n>` selbst vor
    (`stand.soll_koepfe`). Fehlt die Datei oder die Zeile, wird das - wenn ein `log`
    mitgegeben ist - vermerkt und der Batch anschliessend als `SOLL > 0` behandelt
    (`kernzahl_stillstand`): es wird nicht geraten, aber auch kein Stillstand verschluckt.
    """
    p = Path(cfg.root) / "runs" / f"b{int(batch):03d}" / "auftrag.md"
    text = read_text(p) or ""
    wert = stand.soll_koepfe(text) if text else None
    if wert is None and log is not None:
        log.warn("SOLL-KOEPFE fehlt - Batch gilt als SOLL > 0", batch=int(batch),
                 datei=f"runs/b{int(batch):03d}/auftrag.md")
    return wert


def kernzahl_neuester_c(cfg) -> int:
    """Die Nummer des neuesten verglichenen C-Batches (0 = keiner im Fenster)."""
    cbs = c_batches(cfg)
    return int(cbs[-1].get("batch") or 0) if cbs else 0


def kernzahl_gemeldet_bis(meta: dict) -> int:
    """Die Marke aus dem Zustand; fehlt sie, gilt die Migrationsmarke (`MIGRATION_MARKE`)."""
    wert = (meta or {}).get(MARKE_SCHLUESSEL)
    if wert is None:
        return MIGRATION_MARKE
    try:
        return int(wert)
    except (TypeError, ValueError):
        return MIGRATION_MARKE


def kernzahl_marke_setzen(cfg, state) -> int:
    """Die Marke auf den neuesten verglichenen C-Batch setzen.

    Wird vom Orchestrator NACH einem erfolgreichen Aussensicht-Lauf (rc=0) gerufen, an dem
    der Grund `KERNZAHL_GRUND` beteiligt war - nicht schon beim Ausloesen. Rueckgabe ist
    die gesetzte Nummer (0 = nichts gesetzt, kein C-Batch im Fenster).
    """
    neu = kernzahl_neuester_c(cfg)
    if neu > 0:
        meta = dict(state.data.get("meta") or {})
        meta[MARKE_SCHLUESSEL] = int(neu)
        state.data["meta"] = meta
    return int(neu)


def kernzahl_beteiligt(gruende) -> bool:
    """War der Kernzahl-Stillstand an diesen Ausloeser-Gruenden beteiligt?"""
    return any(KERNZAHL_GRUND in str(g) for g in (gruende or []))


def kernzahl_info_text(cfg) -> str:
    """`C Faelle` als INFORMATION zum Anlass - kein eigener Ausloeser (Auftrag 2026-09-29)."""
    cbs = c_batches(cfg)
    if len(cbs) < 2:
        return ""
    neu, alt = cbs[-1], cbs[-2]
    teile: list[str] = []
    for schluessel, name in KERNZAHL_INFO:
        n, a = neu.get(schluessel), alt.get(schluessel)
        if n is None or a is None:
            continue
        wenn = (f"{n[0]}/{n[1]}" if isinstance(n, (list, tuple)) else str(n))
        teile.append(f"{name} = {wenn} (nur Information, kein Kriterium)")
    return ("; " + "; ".join(teile)) if teile else ""


def c_soll_null_reihe(cfg, log=None) -> dict:
    """Die letzte `SOLL_NULL_SERIE`-Reihe aus C-Batches mit `SOLL-KOEPFE 0`.

    Rueckgabe: `{"bis": <neuester C-Batch der Serie | 0>, "batches": [...], "text": "…"}`.
    `bis == 0` heisst: keine vollstaendige Serie. Eigener Grund (Auftrag 2026-09-29): baut
    kein C-Batch mehr Koepfe, misst der Kernzahl-Stillstand nichts mehr - die fehlende
    Bewegung ist dann kein Befund, sondern die Folge eines fehlenden Bau-Auftrags.
    """
    cbs = c_batches(cfg)
    if len(cbs) < SOLL_NULL_SERIE:
        return {"bis": 0, "batches": [], "text": ""}
    letzte = cbs[-SOLL_NULL_SERIE:]
    solls = [(int(e.get("batch") or 0),
              soll_koepfe_batch(cfg, int(e.get("batch") or 0), log=log)) for e in letzte]
    if not all(s == 0 for _, s in solls):
        return {"bis": 0, "batches": [], "text": ""}
    batches = [b for b, _ in solls]
    return {"bis": batches[-1], "batches": batches,
            "text": (C_SOLL_GRUND + ": " + str(SOLL_NULL_SERIE) + " C-Batches in Folge mit "
                     "SOLL-KOEPFE 0 (B" + ", B".join(str(b) for b in batches)
                     + ") - kein C-Batch hatte einen Bau-Auftrag")}


def c_soll_null_serie(cfg, log=None) -> str:
    """Der Text des Serien-Grundes (`''` = keine Serie) - siehe `c_soll_null_reihe`."""
    return c_soll_null_reihe(cfg, log=log)["text"]


def c_soll_null_gemeldet_bis(meta: dict) -> int:
    """Die Serien-Marke aus dem Zustand; fehlt sie, gilt `MIGRATION_SOLL_MARKE` (0)."""
    wert = (meta or {}).get(MARKE_SOLL_SCHLUESSEL)
    if wert is None:
        return MIGRATION_SOLL_MARKE
    try:
        return int(wert)
    except (TypeError, ValueError):
        return MIGRATION_SOLL_MARKE


def c_soll_null_marke_setzen(cfg, state, log=None) -> int:
    """Die Serien-Marke auf den neuesten C-Batch der gemeldeten Serie setzen.

    Wird - wie `kernzahl_marke_setzen` - erst NACH einem erfolgreichen Lauf (rc=0) gerufen,
    an dem der Grund beteiligt war. So feuert dieselbe Serie nur EINMAL; eine Verlaengerung
    (neuer C-Batch mit `SOLL-KOEPFE 0`) oder eine neue Serie hebt die Marke wieder.
    """
    bis = int(c_soll_null_reihe(cfg, log=log)["bis"])
    if bis > 0:
        meta = dict(state.data.get("meta") or {})
        meta[MARKE_SOLL_SCHLUESSEL] = bis
        state.data["meta"] = meta
    return bis


def c_soll_null_beteiligt(gruende) -> bool:
    """War `c_soll_null_serie` an diesen Ausloeser-Gruenden beteiligt?"""
    return any(C_SOLL_GRUND in str(g) for g in (gruende or []))


def kernzahl_stillstand(cfg, log=None) -> list[str]:
    """C-Kernzahlen, die sich ueber die letzten beiden **C-Batches** nicht bewegt haben.

    Befund Nr. 2 des Nutzers (2026-09-28): bei einem Mischverhaeltnis 2 B : 1 C darf der
    Ausloeser nicht in jedem B-Batch feuern. Deshalb werden B-Batches ausgelassen und nur
    die C-Batches verglichen (`c_batches`).

    Kriterium (Auftrag 2026-09-29): **nur `C Koepfe`** - ist die Kopfzahl unveraendert
    (Ist-Delta 0) und hat der Batch `SOLL-KOEPFE > 0`, gilt der Stillstand. `C Faelle`
    steht nur als Information im Anlass-Text (`kernzahl_info_text`), nie als eigener
    Ausloeser; `C Abweichungen` ist entfernt. Fehlt die `SOLL-KOEPFE`-Zeile, wird geloggt
    und der Batch als `SOLL > 0` behandelt.
    """
    cbs = c_batches(cfg)
    if len(cbs) < 2:
        return []
    neu, alt = cbs[-1], cbs[-2]
    stehend: list[str] = []
    for schluessel, name in KERNZAHL_KRITERIUM:
        n, a = neu.get(schluessel), alt.get(schluessel)
        if n is None or a is None or n != a:
            continue
        wenn = (f"{n[0]}/{n[1]}" if isinstance(n, (list, tuple)) else str(n))
        stehend.append(f"{name} = {wenn} (B{alt.get('batch')} wie B{neu.get('batch')})")
    if not stehend:
        return []
    if soll_koepfe_batch(cfg, int(neu.get("batch") or 0), log=log) == 0:
        return []
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


def eingaben(cfg, state, tiefe: dict | None = None) -> str:
    """Alle Eingabebloecke - was nicht da ist, wird als solches benannt, nie erfunden."""
    g = grenzen(cfg)
    batch = int(state.batch or 0)
    bloecke: list[str] = []
    if tiefe:
        bloecke.append(tiefenprobe_block(cfg, tiefe))

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
Beleg: EINE dieser Formen (R13aa):
  * <Datei:Zeile>            z. B. `_m209/_isa_orakel.txt:448`
  * <Zahl + Quelldatei>      z. B. "137 Anfragen in runs/b207/result.json"
  * "Eingabe <Abschnitt>"    z. B. "Eingabe Kosten und Laufzeiten je Batch" (die Bloecke,
                             die DU als Eingabe bekommst - sie sind ein Beleg)
  * <Lauf-/Belegordner>      z. B. "runs/b209" oder "runs/b209/result.json"
  * "Fehlstelle: gesucht in <Ort>, nicht gefunden"
Aussage: <was nicht stimmt, in EINEM Satz>
Empfehlung: <was getan werden sollte, in EINEM Satz>
</BEFUND>

(weitere Befunde fortlaufend nummeriert, hoechstens {max_befunde} Stueck, nach Gewicht
sortiert: hoch zuerst. Ein Befund OHNE jeden Beleg wird verworfen und zaehlt nicht.)

EMPFAENGER (R13y, pruefe JEDEN Befund daran):
  Reviewer = alles, was der Orchestrator laut AGENTS.md "Roles" selbst entscheidet
             (Reihenfolge/Zuschnitt/Werkzeuge/Messmethoden/Code/Plan) - der Regelfall.
  Nutzer   = NUR Ziel, Scope, Budget, frueherere Nutzerentscheidungen (readme-Zielsatz,
             Projektumfang, Priorisierung, Kostenrahmen/Abo, Aufheben einer Entscheidung).
  Befund mit beiden Anteilen: ZWEI Befunde schreiben (einer Nutzer, einer Reviewer),
  sonst setzt der Harness die Aufteilung selbst durch.

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
3. TIEFENPROBE (R13ac3, Nutzerauftrag 2026-09-29): pruefe den Batch aus dem Block
   "=== TIEFENPROBE (Pflicht): BATCH <N> ===" in der Tiefe - Denkbloecke, Belege,
   jede pruefbare Behauptung seines Abschlussberichts gegen die Rohdaten. Nenne die
   Nummer in <AUSSENSICHT> woertlich (`TIEFENPROBE B<N>`).
Ziel: nicht dieselben aufbereiteten Zahlen als einzige Quelle nehmen.

=== PFLICHT BEI FUNDEN AUS AELTEREN BATCHES (R13ac3) ===
Jeder Fund aus einem FRUEHEREN Batch (auch aus der Tiefenprobe) wird gegen den AKTUELLEN
Stand geprueft: HEAD (`git log -1` / `git show`), Ankerkopf (`analysis/r1b-workstream.md`),
aktuelle Belegdateien des Decomp-Repos.
  * Wirkt der Fund HEUTE noch - oder kehrt er als Muster wieder?  -> BEFUND.
  * Ist er bereits behoben?  -> KEIN Befund. Stattdessen EINE Zeile in <AUSSENSICHT>:
      geprueft: <Fund in einem Satz>, behoben in B<N> (Beleg: <Datei:Zeile|Commit>)
  Ein Fund, der nur noch historisch ist, gehoert nicht in die Befundliste - die soll
  zeigen, was JETZT zu tun ist.

=== GRENZEN ===
- Du entscheidest NICHTS und aenderst NICHTS (kein Anker, kein Code, keine Queue).
- Keine Datei schreiben, kein Ghidra, kein Netz.
- Hoechstens {max_befunde} Befunde. Lieber drei belastbare als sieben schwache.
"""


def tiefenprobe_block(cfg, tiefe: dict) -> str:
    """Der Eingabeblock `=== TIEFENPROBE: BATCH <N> ===` (R13ac3).

    Der gezogene Batch und seine Rohbelege stehen ausdruecklich da - der Prompt nennt
    die Nummer, damit der Bericht sie tragen kann (sie wird zusaetzlich vom Harness
    hineingeschrieben, `bericht`).
    """
    nummer = tiefe.get("batch")
    if nummer is None:
        return ("=== TIEFENPROBE (Pflicht) ===\n"
                "In diesem Lauf KEINE Tiefenprobe moeglich: "
                + str(tiefe.get("grund") or "kein abgeschlossener Lauf im Fenster"))
    runs = Path(cfg.root) / "runs"
    snaps = Path(cfg.root) / "snapshots"
    fenster = tiefe.get("fenster") or []
    zeilen = [
        f"=== TIEFENPROBE (Pflicht): BATCH {nummer} ===",
        f"Gezogen aus dem Fenster der letzten {len(fenster)} gelaufenen Batches: "
        f"B{fenster[0]}..B{fenster[-1]}" if fenster else "",
        "Schon dran gewesen (nicht wieder gezogen): "
        + (", ".join(f"B{b}" for b in (tiefe.get("gezogen") or [])) or "keiner")
        + ("; dieser Lauf beginnt einen NEUEN Zyklus ("
           + str(tiefe.get("grund")) + ")" if tiefe.get("neu_zyklus") else ""),
        "",
        f"Pruefe DIESEN Batch in der Tiefe (nicht nur ueber die aufbereiteten Zahlen):",
        f"  * Auftrag     : runs/b{int(nummer):03d}/auftrag.md (die Forderungen)",
        f"  * Abschluss   : runs/b{int(nummer):03d}/antwort.md (was der Worker behauptet)",
        f"  * Ergebnis    : runs/b{int(nummer):03d}/result.json (rc, Dauer, Anfragen, "
        "Abbruch)",
        f"  * Denkbloecke : snapshots/b{int(nummer):03d}/reasoning.jsonl (was er sich "
        "dabei dachte)",
        f"  * Mitschnitt  : runs/b{int(nummer):03d}/stream.jsonl (Werkzeugaufrufe, "
        "Wartezeiten)",
        f"  * Belege      : die Dateien, die der Bericht als Beleg NENNT, jeweils "
        "gegen den Rohinhalt",
        "",
        "Nimm JEDE Behauptung des Abschlussberichts, die du pruefen kannst, und halte "
        "sie gegen die Rohdaten (Zahl, Datei:Zeile, Werkzeugausgabe). Was du NICHT "
        "pruefen kannst, sagst du. Nenne die Nummer in <AUSSENSICHT> woertlich: "
        f"`TIEFENPROBE B{nummer}`.",
        "ABER: erhebe NUR dann einen Befund, wenn die Sache HEUTE noch gilt (s. PFLICHT "
        "in den Stichproben).",
        "Rohbelege dieses Batches:",
        f"  {runs / f'b{int(nummer):03d}'}",
        f"  {snaps / f'b{int(nummer):03d}'}",
    ]
    return "\n".join([z for z in zeilen if z != ""])


def build_prompt(cfg, state, grund, tiefe: dict | None = None) -> str:
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
    return "\n".join(kopf) + "\n" + eingaben(cfg, state, tiefe=tiefe) + "\n\n" + \
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
# Ein benannter EINGABE-Abschnitt ("Eingabe Kosten und Laufzeiten je Batch") oder ein
# Blockkopf der Eingaben ("=== KOSTEN UND LAUFZEITEN JE BATCH ===", R13aa Punkt 2).
_RE_EINGABE = re.compile(r"\beingabe\b\s*:?\s*\S|===+\s*\w[^=\n]{2,60}?===+",
                         re.IGNORECASE)
# Lauf-/Belegordner: `runs/b209`, `runs/b209/result.json`, `runs\b209`.
_RE_RUNS = re.compile(r"runs[/\\]b\d{1,4}\b", re.IGNORECASE)


def beleg_gueltig(beleg: str) -> bool:
    """Beleg-Pflicht, gelockert (Nutzerentscheidung 2026-09-28, Punkt b; R13aa Punkt 2).

    Gueltig ist:
      * `Datei:Zeile`,
      * eine Zahl mit Quelldatei,
      * eine **Eingabe**-Stelle ("Eingabe <Abschnitt>" - genau die Bloecke, die die
        Aussensicht selbst als Eingabe bekommt, z. B. "Kosten und Laufzeiten je Batch"),
      * ein **Lauf-/Belegordner** (`runs/b<N>`, `runs/b<N>/result.json`),
      * die ausdrueckliche Fehlstelle ("Fehlstelle: gesucht in <Ort>, nicht gefunden").

    R13aa (Befund M209-4): vorher fiel ein Befund durch, dessen Zahlen aus den
    EINGABEDATEN stammten (Laufzeiten je Batch, Beleg "runs/b206") - die Regel verlangte
    eine Datei mit bekannter Endung. Eine ehrliche Fehlstelle ist ein Ergebnis, kein
    Fehler; eine benannte Eingabe ist ein Beleg.
    """
    t = str(beleg or "").strip()
    if not t:
        return False
    if _RE_DATEI_ZEILE.search(t):
        return True
    if re.search(r"\d", t) and _RE_DATEI.search(t):
        return True
    if _RE_EINGABE.search(t):
        return True
    if _RE_RUNS.search(t):
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


# Der Reviewer antwortet mit `M<batch>-<n>: <Verdikt> …`. Das Muster war zu streng: es
# verlangte das Verdikt DIREKT hinter dem Doppelpunkt. Gemessen (29.09.2026) waren zwei
# beantwortete Befunde deshalb weiter "offen":
#   runs/b211/review.md:15  "M209-3b: zurueckgestellt (Nutzer), spaetestens B216"
#   runs/b213/review.md:11  "M212-1: fuer B213 abgelehnt (Werkzeug vor Serie), fuer
#                            B216 uebernommen (SOLL-KOEPFE > 0, Liste aus B213)"
# R13ak: der Text hinter der Kennung wird gelesen und **das LETZTE Verdikt darin**
# entscheidet - der Reviewer darf erst verwerfen und spaeter uebernehmen. Ohne Verdikt
# gilt die Zeile NICHT als Antwort (sonst wuerde jede Prosa-Erwaehnung eines Befunds ihn
# stillschweigend zuklappen).
_RE_ANTWORT = re.compile(r"\bM(\d{3})-(\d+)([a-z]?)\s*:\s*(?P<rest>[^\n]*)", re.IGNORECASE)
_RE_VERDIKT = re.compile(r"\b(uebernommen|übernommen|abgelehnt|erledigt|verworfen|offen|"
                         r"zurueckgestellt|zurückgestellt)\b", re.IGNORECASE)

# Die Kennung im Text einer Aussensicht-Nachricht ("Aussensicht Batch 214 - Befund
# M214-1 (Gewicht hoch):"). R13ak: damit findet der Harness den Registereintrag zu einer
# Queue-Datei, ohne den Text zu deuten.
_RE_BEFUND_KENNUNG = re.compile(r"Befund\s+(M\d{3}-\d+[ab]?)\b")


def kennung_aus_text(text: str) -> str:
    """Die Befundkennung (`M214-1`) aus dem Text einer Aussensicht-Nachricht ('' = keine)."""
    m = _RE_BEFUND_KENNUNG.search(str(text or ""))
    return m.group(1) if m else ""


def finde_eintraege(index: dict, bid: str) -> list[dict]:
    """Die Registereintraege zu einer Kennung - auch die Teile eines geteilten Befunds.

    Ein geteilter Befund heisst `M208-5a` (Nutzer) und `M208-5b` (Reviewer). Antwortet
    der Reviewer auf die Kurzform `M208-5`, gilt das fuer BEIDE Teile (R13y).
    """
    bid = str(bid or "").strip()
    if bid in index:
        return [index[bid]]
    return [e for k, e in index.items()
            if k.lower() in (bid.lower() + "a", bid.lower() + "b")]


def antworten_uebernehmen(cfg, summary: str, batch: int) -> list[str]:
    """Antworten des Reviewers zu Befund-IDs uebernehmen (Nutzerentscheidung d).

    Der Reviewer muss jede `/claude`-Nachricht mit `M<batch>-<n>` beantworten
    ("M208-3: uebernommen (…)" / "M208-3: abgelehnt, Grund …"). Unbeantwortete Befunde
    bleiben `offen` und erscheinen weiter in `/bilanz`. Seit R13y gibt es geteilte
    Befunde (`M208-5a`/`M208-5b`) - die Kurzform gilt fuer beide.

    R13ak: Tolerant gelesen wird ausserdem, wenn das Verdikt nicht direkt am Anfang der
    Zeile steht ("fuer B213 abgelehnt, fuer B216 uebernommen") und wenn der Reviewer
    schiebt statt zu entscheiden ("zurueckgestellt"). Massgeblich ist das **letzte**
    Verdikt der Zeile.
    """
    alle = ledger(cfg)
    if not alle:
        return []
    index = {str(b.get("id")): b for b in alle}
    geaendert: list[str] = []
    for m in _RE_ANTWORT.finditer(summary or ""):
        rest = str(m.group("rest") or "")
        verdikte = list(_RE_VERDIKT.finditer(rest))
        if not verdikte:
            continue                     # Kennung genannt, aber kein Verdikt -> keine Antwort
        bid = f"M{m.group(1)}-{m.group(2)}{m.group(3) or ''}"
        wort = verdikte[-1].group(1).lower()
        # R13z: das Wort des Reviewers wird SO gespeichert, wie er es geschrieben hat
        # ("uebernommen"/"abgelehnt"/"erledigt"/"verworfen"/"zurueckgestellt"), nur
        # die Umlautschreibweise wird vereinheitlicht. Vorher wurde "uebernommen" zu
        # "beantwortet" umgeschrieben - dann stand in der Quote (R13z) ein Wort, das der
        # Reviewer nie benutzt hat. Alte Eintraege mit "beantwortet" zaehlen ueber
        # `klasse` weiter als uebernommen.
        status = {"übernommen": "uebernommen",
                  "zurückgestellt": "zurueckgestellt"}.get(wort, wort)
        for eintrag in finde_eintraege(index, bid):
            eintrag["status"] = status
            eintrag["antwort"] = (rest.strip()[:400] or str(summary).strip()[:200])
            eintrag["antwort_batch"] = int(batch)
            eintrag["antwort_ts"] = now_iso()
            geaendert.append(str(eintrag.get("id")))
    if geaendert:
        ledger_schreiben(cfg, alle)
    return geaendert


def verteile(cfg, state, summary: str, befunde: list[dict], pruefungen: list[dict],
             batch: int, log=None) -> dict:
    """Befunde in den Ledger uebernehmen, Verdikte anwenden, Empfaenger bedienen.

    R13y: Jeder Befund wird vorher nach **Entscheidungstraeger** aufgeteilt
    (`entscheidungstraeger`): was der Orchestrator selbst entscheiden darf, geht an den
    Reviewer; an den Nutzer nur Ziel/Scope/Budget/fruehere Nutzerentscheidungen. Ein
    Befund mit beiden Anteilen wird geteilt und bekommt zwei Kennungen
    (`M208-5a` Nutzer / `M208-5b` Reviewer).

    Rueckgabe: {"ids": [...], "queue": [...], "nutzer": [...], "verdikte": [...]}
    """
    alle = ledger(cfg)
    index = {str(b.get("id")): b for b in alle}
    neu_ids: list[str] = []
    geteilt: list[str] = []
    umgeleitet: list[str] = []
    for i, b in enumerate(befunde, 1):
        teile = entscheidungstraeger(b)
        for t in teile:
            bid = f"M{batch}-{i}{t.get('teil') or ''}"
            eintrag = dict(t)
            eintrag.update({"id": bid, "batch": int(batch), "ts": now_iso(),
                            "status": "offen", "quelle": "aussensicht",
                            "antwort": "", "antwort_batch": None,
                            "empfaenger_modell": str(b.get("empfaenger") or "")})
            eintrag.pop("teil", None)
            index[bid] = eintrag
            alle.append(eintrag)
            neu_ids.append(bid)
        if len(teile) > 1:
            geteilt.append(f"M{batch}-{i}")
        elif str(teile[0].get("empfaenger")) != str(b.get("empfaenger") or ""):
            umgeleitet.append(f"M{batch}-{i} {b.get('empfaenger')} -> "
                              f"{teile[0].get('empfaenger')}")

    verdikte: list[str] = []
    for p in pruefungen:
        treffer = finde_eintraege(index, str(p.get("id")))
        if not treffer:
            continue
        for eintrag in treffer:
            eintrag["status"] = p.get("status") or "offen"
            eintrag["letzte_pruefung"] = int(batch)
            verdikte.append(f"{eintrag.get('id')} -> {eintrag['status']}")

    # Alte, laenger unbeantwortete Befunde mitzaehlen (Sichtbarkeit im Bericht)
    offen_alt = [b["id"] for b in alle
                 if str(b.get("status")) == "offen" and b["id"] not in neu_ids]
    ledger_schreiben(cfg, alle)
    if log:
        log.info("Aussensicht: Befunde uebernommen", batch=batch, neu=neu_ids,
                 verdikte=verdikte, offen_alt=len(offen_alt), geteilt=geteilt,
                 umgeleitet=umgeleitet)
    return {"ids": neu_ids, "verdikte": verdikte, "offen_alt": offen_alt,
            "geteilt": geteilt, "umgeleitet": umgeleitet,
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
        # R13ac3: die Ziehung dieses Laufs (`tiefenprobe_waehlen`).
        self.tiefe: dict = {}

    def describe(self) -> str:
        return (f"rc={self.rc} dauer={self.dauer_s:.0f}s modell={self.modell or '-'} "
                f"befunde={len(self.befunde)} verworfen={len(self.verworfen)}"
                + (f" tiefenprobe=B{self.tiefe.get('batch')}"
                   if self.tiefe.get("batch") else ""))


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


def run(cfg, log, state, grund: str, mock: bool = False,
        zufall=None) -> Ergebnis:
    """Die Aussensicht fahren (synchron, begrenzt durch `[meta] wall_s`).

    R13ac3: VOR dem Lauf wird die Tiefenprobe gezogen (`tiefenprobe_waehlen`) - der
    Batch steht damit im Prompt und im Bericht. Gemerkt wird die Ziehung erst, wenn der
    Lauf etwas geliefert hat (ein abgebrochener Lauf verbrennt keinen Batch).
    `zufall` dient den Tests (reproduzierbare Ziehung).
    """
    res = Ergebnis()
    batch = int(state.batch or 0)
    res.tiefe = tiefenprobe_waehlen(cfg, zufall=zufall)
    prompt = build_prompt(cfg, state, grund, tiefe=res.tiefe)
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
    if res.tiefe.get("batch") and (res.summary or res.befunde):
        tiefenprobe_merken(cfg, res.tiefe)
        if log:
            log.info("Tiefenprobe gezogen", batch=res.tiefe["batch"],
                     fenster=f"{res.tiefe['fenster'][0]}..{res.tiefe['fenster'][-1]}",
                     neu_zyklus=res.tiefe.get("neu_zyklus", False))
    return res


# ------------------------------------------------------------------ Ausloeser
def letzter_lauf(cfg, state) -> dict:
    return dict(state.data.get("meta") or {})


def faellig(cfg, state, log=None) -> list[str]:
    """Gruende, warum jetzt eine Aussensicht faellig ist ([] = nicht faellig)."""
    g = grenzen(cfg)
    meta = dict(state.data.get("meta") or {})
    batch = int(state.batch or 0)
    letzte = int(meta.get("letzter_lauf_batch") or 0)
    if meta.get("geprueft_batch") == batch and not meta.get("vorgemerkt"):
        return []                              # fuer diesen Batch schon entschieden
    # Migration (Auftraege 2026-09-29): fehlende Marken werden EINMALIG gesetzt.
    #   * `kernzahl_gemeldet_bis` -> 210: der Stillstand B207/B210 ist in
    #     `runs/meta-212.md` gemeldet und darf nicht erneut feuern.
    #   * `c_soll_null_gemeldet_bis` -> 0: nach der geltenden Regel "fehlende
    #     SOLL-KOEPFE-Zeile = SOLL > 0" bilden B207/B210/B213 keine SOLL-0-Serie.
    #   * `hybrid_gemeldet_bis` -> 0 (R13ah): der Ausloeser ist neu und liest die
    #     Preflight-Zeile `Hybrid-Lauf`; fuer B212/B213 gibt es nur ZWEI B-Batches mit
    #     Zeile, ein Stillstand ist damit nicht gemeldet - es gibt nichts zu ueberspringen.
    # NICHT die Variante "neu.batch > letzter_lauf_batch" - die Marken sind eigenstaendig.
    fehlend = False
    if MARKE_SCHLUESSEL not in meta:
        meta[MARKE_SCHLUESSEL] = MIGRATION_MARKE
        fehlend = True
    if MARKE_SOLL_SCHLUESSEL not in meta:
        meta[MARKE_SOLL_SCHLUESSEL] = MIGRATION_SOLL_MARKE
        fehlend = True
    if MARKE_HYBRID_SCHLUESSEL not in meta:
        meta[MARKE_HYBRID_SCHLUESSEL] = 0
        fehlend = True
    if fehlend:
        state.data["meta"] = meta
        try:
            state.save()
        except Exception:                                        # noqa: BLE001
            pass
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
    still = hybrid_stillstand(cfg)
    if still and hybrid_neuester_b(cfg) > hybrid_gemeldet_bis(meta):
        gruende.append(still)
    kern = kernzahl_stillstand(cfg, log=log)
    if kern and kernzahl_neuester_c(cfg) > kernzahl_gemeldet_bis(meta):
        gruende.append(KERNZAHL_GRUND + ": " + "; ".join(kern[:3])
                       + kernzahl_info_text(cfg))
    serie = c_soll_null_reihe(cfg, log=log)
    if serie["bis"] > c_soll_null_gemeldet_bis(meta):
        gruende.append(serie["text"])
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
    ]
    # R13ac3: die gezogene Nummer steht im Bericht - auch wenn das Modell sie nicht nennt.
    tiefe = dict(res.tiefe or {})
    if tiefe.get("batch"):
        fenster = tiefe.get("fenster") or []
        zeilen.append(f"- Tiefenprobe: Batch {tiefe['batch']} aus dem Fenster "
                      f"B{fenster[0]}..B{fenster[-1]}"
                      + (" (neuer Zyklus: alle anderen waren dran)"
                         if tiefe.get("neu_zyklus") else "")
                      + ("; vorher gezogen: "
                         + ", ".join(f"B{b}" for b in tiefe.get("gezogen") or [])
                         if tiefe.get("gezogen") else ""))
    else:
        zeilen.append("- Tiefenprobe: keine - "
                      + str(tiefe.get("grund") or "kein abgeschlossener Lauf"))
    zeilen += [
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
    # R13aa (Punkt 2): verworfene Befunde ins Register - nicht wegwerfen (siehe
    # `verworfene_speichern`), damit `/fragen` sie als "verworfen - pruefen?" zeigen kann.
    verworfene_speichern(cfg, int(batch), list(res.verworfen or []))
    write_json_atomic(json_pfad(cfg, batch), {
        "batch": int(batch), "ts": now_iso(), "grund": grund, "gruende": list(gruende),
        "summary": res.summary, "rc": res.rc, "dauer_s": res.dauer_s, "modell": res.modell,
        "befunde": res.befunde, "verworfen": res.verworfen, "pruefungen": res.pruefungen,
        "ids": verteilung.get("ids") or [], "verdikte": verteilung.get("verdikte") or [],
        "offen_alt": verteilung.get("offen_alt") or [],
        "tiefenprobe": dict(res.tiefe or {}),
        "text": res.text,
    })
    return p
