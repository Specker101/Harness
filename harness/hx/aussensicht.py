r"""Aussensicht (R13w, 2026-09-28) - der Meta-Review.

Anderer Auftrag als der Reviewer (bewusst):

  * Der Reviewer fragt "war der Batch gut?" - die Aussensicht fragt
    "**stimmen Messgroessen, Plan und Annahmen noch?**".
  * eigene, **immer frische** Session (kein Verlauf), eigenes Modell
    (`aussensicht_modell`, R13bo), eigener Systemprompt `prompts/aussensicht.md`,
    Lesezugriff auf Harness UND Decomp-Repo (Schreiben ist doppelt verboten).
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

Ausloeser (`faellig`): Vormerkung durch `/meta`, alle `[meta] aussensicht_takt` Batches
(R13bo 4, vorher `every_batches` 3), ein
Worker-Abbruch, `MEILENSTEIN ERREICHT:` / `ABBRUCHKRITERIUM ERREICHT:` in der neuesten
Review-Zusammenfassung, ein stehengebliebener B-Schritt (Weg B) bzw. eine C-Kernzahl ohne
Bewegung ueber die letzten **C-Batches**, und seit R13bt-5 der **Stillstand der B-Phase**
(Schwelle 4 B-Batches in Folge ohne Station, `analysis/hybrid-plan.md:257-274`). Je Batch
wird hoechstens einmal entschieden
(`geprueft_batch`).

Entprellt (Auftraege 2026-09-29): ein liegengebliebener C-Stillstand feuert nur EINMAL je
neuem C-Batch - die Marke `kernzahl_gemeldet_bis` (im Zustand, `state.data["meta"]`) haelt
den neuesten bereits gemeldeten C-Batch und wird erst nach einem erfolgreichen Lauf
(rc=0) gesetzt, an dem der Grund beteiligt war. Stillstand heisst **allein: `C Koepfe`
unveraendert** (Ist-Delta 0) bei `SOLL-KOEPFE > 0`; `C Faelle` steht nur als Information
im Anlass-Text. Auch der eigene Grund `c_soll_null_serie` (drei C-Batches in Folge mit
`SOLL-KOEPFE: 0`) ist entprellt (`c_soll_null_gemeldet_bis`): er feuert erst wieder, wenn
ein NEUER C-Batch die Serie verlaengert oder eine neue Serie entsteht. Dieselbe Sperre
tragen der Hybrid-Lauf-Stillstand (`hybrid_gemeldet_bis`), die beiden Review-Marker
(`marker_gemeldet_bis`, R13bn) und seit R13bt-5 der B-Phasen-Stillstand
(`station_gemeldet_bis` - dort ist der Schluessel der ERSTE Batch des Laufs, weil der
Zaehler innerhalb des Laufs weiterwaechst).

R13z (2026-09-28): die **Quote** des Registers steht in `/bilanz` und `/status`
(`zeile`/`quote`): "Aussensicht: n Befunde, davon u uebernommen, a abgelehnt, o offen".
Gezaehlt wird je Kennung; die Zuordnung der Statusworte zu den Klassen macht `klasse`
(s. dort) - der Reviewer schreibt das Verdikt, das Wort wird so gespeichert, wie er es
geschrieben hat.

Belege/Regeln dieser Datei: `docs/_r13w_belege.md`, Doku `docs/bedienung.md`.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
import sys
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
# eingestellte Zahl steht dort (`[meta]`, R13bo = 4, vorher R13z = 3; Begruendung in
# docs/bedienung.md Paragraph 12e). Gelesen wird `aussensicht_takt` (R13bo), sonst das
# alte `every_batches` - s. `takt`.
STANDARD = {"every_batches": 4, "wall_s": 900, "max_turns": 50, "max_befunde": 7,
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
# B214 von 28/407 auf 448/42599 lief). Der Preflight liegt VOR dem Review vor - der
# Ausloeser kommt damit frueher.
# R13bo-5 (03.10.2026, Aussensicht M239-2/M236-7): gemessen wird der Halt-PC der Zeile
# **`Hybrid-A4`** (der ECHTE Halt), nicht mehr der der Zeile `Hybrid-Lauf` - deren Feld 2
# ist die 200M-SCHRANKE und bleibt stehen (B250 loeste damit einen Lauf aus, obwohl B248
# einen neuen Halt erreicht hatte). Preflights mit FEHLER-Zeilen fallen aus der Reihe.
# Die Marke haelt die Nummer des neuesten VERGLICHENEN B-Batches (hier: der
# Preflight-Dateiname, also der Batch selbst).
MARKE_HYBRID_SCHLUESSEL = "hybrid_gemeldet_bis"
# Der Wortlaut des Grundes (Kennung fuer `hybrid_beteiligt`). Bleibt `Hybrid-Lauf` - so
# heisst der Ausloeser; die QUELLE der Zahl nennt die Meldung selbst (`Zeile "Hybrid-A4"`).
HYBRID_GRUND = "Hybrid-Lauf"
# Wie viele B-Batches IN FOLGE denselben Halt-PC und kein steigendes Wegmass zeigen
# muessen (`[meta] bschritt_stillstand_batches`, Vorgabe 3).
HYBRID_STILLSTAND_BATCHES = 3
# R13bo-5: Ruhe-Erkennung. Waren die letzten so vielen Batches ALLE C-Batches, ruht der
# B-Strang - der Melder schweigt dann (B250: Opus-Lauf der Aussensicht ohne B-Fortschritt).
HYBRID_RUHE_C_BATCHES = 3

# R13bt-5 (04.10.2026, Nutzerentscheid): der STILLSTAND DER B-PHASE wird ein eigener
# Ausloeser - wie `MEILENSTEIN ERREICHT:` im Review. Regel `analysis/hybrid-plan.md:257-274`:
# Schwelle 4 B-Batches in Folge ohne Station, Zaehler ab jeder Station neu
# (`stand.stillstand_zaehler`). Die Marke haelt den ERSTEN Batch des gezaehlten Laufs
# (`von` = letzte Station + 1), NICHT den neuesten: der Zaehler WAEchst mit jedem weiteren
# Batch (4, 5, 6 ...), eine Marke auf dem neuesten Batch wuerde denselben Stillstand bei
# jeder Pruefung erneut melden (ein Abo-Lauf je Batch). `von` bleibt innerhalb eines Laufs
# konstant und springt erst nach einer Station - genau dann ist die Schwelle wieder scharf.
MARKE_STATION_SCHLUESSEL = "station_gemeldet_bis"
# Der Wortlaut des Grundes (Kennung fuer `station_beteiligt`).
STATION_GRUND = "Stillstand der B-Phase"

# R13bn (Aussensicht M241-4/M242-5/M243-2): die beiden MARKER-Ausloeser bekommen dieselbe
# `gemeldet_bis`-Sperre wie Kernzahl, c_soll_null und Hybrid-Lauf. Vorher nahm
# `faellig` eine gefundene Markerzeile bei JEDER Pruefung neu auf, solange ihre
# Review-Datei unter den letzten drei Zusammenfassungen lag - die EINE Marke aus der
# B241-Review hat damit vier Aussensicht-Laeufe ausgeloest (meta-240, 241, 242, 243),
# waehrend das Wochenkontingent von 84 % auf 89 % stieg (logs/rate-limit.json).
# Gehalten wird JE MARKENART die Review-Datei, aus der sie stammt (Ordner `runs/b<N>`).
MARKE_MARKER_SCHLUESSEL = "marker_gemeldet_bis"
# Die beiden Markenarten: Name (steht im Grund) und Muster in der Review-Zusammenfassung.
MARKER_MUSTER = (("Meilenstein erreicht", r"MEILENSTEIN ERREICHT:"),
                 ("Abbruchkriterium erreicht", r"ABBRUCHKRITERIUM ERREICHT:"))
# Migration: KEINE. Gemessen am 02.10.2026 steht die Marke aus `runs/b241/review.md` nicht
# mehr im Fenster der letzten drei Zusammenfassungen (`runs/b242..b244`) - sie loest
# ohnehin nicht mehr aus. Eine feste Migrationsnummer (z.B. 241) waere hier SCHAEDLICH:
# sie wuerde in jedem frischen Zustand jede Marke bis zu dieser Nummer stillschweigend
# verschlucken (genau das hat `test_r13w_fixes.test_meilenstein_und_abbruchkriterium_
# loesen_aus` gezeigt, als die Migration noch 241 trug). Fehlt der Schluessel, gilt 0 =
# nichts gemeldet.
MARKE_MARKER_SCHLUESSEL = "marker_gemeldet_bis"
# Die beiden Markenarten: Name (steht im Grund) und Muster in der Review-Zusammenfassung.
MARKER_MUSTER = (("Meilenstein erreicht", r"MEILENSTEIN ERREICHT:"),
                 ("Abbruchkriterium erreicht", r"ABBRUCHKRITERIUM ERREICHT:"))


# R13at (30.09.2026): Abstand zwischen der FRUEHWARNUNG im Prompt/de Uhr und dem harten
# Zuglimit. Vorher 5 (R13aq/R13ar), jetzt 8: der Lauf meta-218 brauchte 41 von 50 Zuegen
# (82 %), das Limit steht seit R13at auf 70 - die letzten Zuege muessen fuer die Antwort
# im Blockformat reichen. EINE Quelle: `build_prompt` schreibt die Zahl in den Auftrag,
# `write_hook_settings` gibt sie der Zuguhr mit (`--frist`).
FRIST_ABSTAND = 8


def max_turns(cfg) -> int:
    """Zuglimit der Aussensicht (R13aq) - konfigurierbar, mit Reserve.

    GEMESSEN (30.09.2026): `runs/meta-217.jsonl` brach mit
    `subtype=error_max_turns`/`Reached maximum number of turns (30)` bei **31 Zuegen**
    ab; die gelungenen Laeufe meta-208..meta-214 brauchten 17 bis **35** Zuege
    (meta-214 = 35, der groesste). Das Limit stand auf 30.

    Gelesen wird `[meta] meta_max_turns` (der Name aus dem Auftrag), sonst das alte
    `[meta] max_turns`, sonst `STANDARD` (50 = 35 gemessen + Reserve).
    """
    for schluessel in ("meta_max_turns", "max_turns"):
        wert = cfg.get("meta", schluessel, None)
        if wert is None:
            continue
        try:
            return max(1, int(wert))
        except (TypeError, ValueError):
            continue
    return int(STANDARD["max_turns"])


def takt(cfg) -> int:
    """Batch-Takt der Aussensicht (R13bo) - `aussensicht_takt`, sonst `every_batches`.

    Der reine "alle N Batches"-Takt; die EREIGNIS-Ausloeser (`faellig`) bleiben davon
    unberuehrt. Die Vorgabe `STANDARD["every_batches"]` ist selbst 4.
    """
    for schluessel in ("aussensicht_takt", "every_batches"):
        wert = cfg.get("meta", schluessel, None)
        if wert is None:
            continue
        try:
            return max(1, int(wert))
        except (TypeError, ValueError):
            continue
    return int(STANDARD["every_batches"])


def grenzen(cfg) -> dict:
    """Die Grenzen der Aussensicht aus `[meta]` (Vorgaben als Rueckfall)."""
    g = {k: cfg.get("meta", k, v) for k, v in STANDARD.items()}
    g["max_turns"] = max_turns(cfg)          # R13aq: zwei moegliche Schluesselnamen
    g["every_batches"] = takt(cfg)            # R13bo: neuer Name `aussensicht_takt`
    return g


# ------------------------------------------------------------------ Ablage
# R13br (2026-10-04, Nutzerauftrag): Die Aussensicht legt ihre Dateien in den Ordner des
# BEWERTETEN Batches (`runs/b<N>/meta.*`), nicht mehr lose nach `runs/` (`runs/meta-<N>.*`).
# Damit liegen die Belege eines Batches beieinander (Auftrag, Antwort, Review, Aussensicht),
# und `runs/` waechst nicht mit jeder Aussensicht weiter zu. Gelesen werden BEIDE Ablagen:
# zuerst der neue Ort, als Rueckfall der alte - alte Aussensichten bleiben damit gueltig,
# ohne dass ein Beleg angefasst werden muss.
#
#  art     neuer Name (runs/b<N>/)  alter Name (runs/)      Rolle
#  md      meta.md                  meta-<N>.md             Bericht (Beleg)
#  json    meta.json                meta-<N>.json           Maschinenfassung (Beleg)
#  jsonl   meta.jsonl               meta-<N>.jsonl          Mitschnitt (Beleg)
#  err     meta.err.txt             meta-<N>.err.txt        stderr des Laufs (Hilfsdatei)
#  hooks   meta-hooks.json          meta-<N>-hooks.json     Hook-Einstellungen (Hilfsdatei)
ABLAGE = {
    "md": ("meta.md", "meta-{n:03d}.md"),
    "json": ("meta.json", "meta-{n:03d}.json"),
    "jsonl": ("meta.jsonl", "meta-{n:03d}.jsonl"),
    "err": ("meta.err.txt", "meta-{n:03d}.err.txt"),
    "hooks": ("meta-hooks.json", "meta-{n:03d}-hooks.json"),
}
# Nur die drei BELEGE werden gegen fremde Dateien im Batchordner verteidigt
# (`ablage_konflikt`). `err` und `hooks` gehoeren DIESEM Harness und werden je Lauf neu
# geschrieben; ein Wiederholungslauf derselben Batch-Nummer darf an ihnen nicht scheitern.
BELEGE = ("md", "json", "jsonl")


class AblageKonflikt(RuntimeError):
    """Am Zielort der Aussensicht liegt eine Datei, die nicht von ihr stammt."""


def batch_ordner(cfg, batch: int, anlegen: bool = False) -> Path:
    """`runs/b<N>` - mit `anlegen=True` auch dann, wenn der Ordner noch fehlt.

    Im Normalfall legt ihn der Worker an (`worker.run_dir`, beim Laufstart). Fehlen kann er
    bei `/meta` in Pause/Gate/Leerlauf oder bei einer Nummer, fuer die nie ein Worker lief -
    deshalb legt die Aussensicht ihn selbst an, bevor sie schreibt.
    """
    p = Path(cfg.root) / "runs" / f"b{int(batch):03d}"
    return ensure_dir(p) if anlegen else p


def pfad_neu(cfg, batch: int, art: str) -> Path:
    """Der neue Ort `runs/b<N>/meta.md|json|jsonl|err.txt|hooks.json`."""
    return batch_ordner(cfg, batch) / ABLAGE[art][0]


def pfad_alt(cfg, batch: int, art: str) -> Path:
    """Der alte, lose Ort `runs/meta-<N>.*` (wird nur noch gelesen)."""
    return Path(cfg.root) / "runs" / ABLAGE[art][1].format(n=int(batch))


def pfad(cfg, batch: int, art: str) -> Path:
    """Wo die Datei LIEGT: neuer Ort, sonst alter Ort, sonst der neue Ort (als Ziel)."""
    neu = pfad_neu(cfg, batch, art)
    if neu.exists():
        return neu
    alt = pfad_alt(cfg, batch, art)
    return alt if alt.exists() else neu


def bericht_pfad(cfg, batch: int) -> Path:
    """Ziel des Berichts - und damit der neue Ort (`runs/b<N>/meta.md`)."""
    return pfad_neu(cfg, batch, "md")


def json_pfad(cfg, batch: int) -> Path:
    return pfad_neu(cfg, batch, "json")


def stream_pfad(cfg, batch: int) -> Path:
    return pfad_neu(cfg, batch, "jsonl")


def err_pfad(cfg, batch: int) -> Path:
    return pfad_neu(cfg, batch, "err")


def hooks_pfad(cfg, batch: int) -> Path:
    return pfad_neu(cfg, batch, "hooks")


def anzeige_pfad(cfg, batch: int, art: str = "md") -> str:
    """Der Ablageort als Text fuer Anzeigen (`/fragen`): dort, wo die Datei liegt."""
    p = pfad(cfg, batch, art)
    try:
        return p.relative_to(Path(cfg.root)).as_posix()
    except ValueError:                                    # root ist nicht Elternordner
        return p.as_posix()


def ledger_pfad(cfg) -> Path:
    return Path(cfg.sub("state")) / "meta_befunde.json"


# ------------------------------------------------- Ablage-Waechter (R13br)
def _kopf_md(batch: int) -> str:
    return f"# Aussensicht Batch {int(batch)}"


def _ist_unsere_ablage(pfad: Path, batch: int, art: str) -> bool:
    """Stammt die vorhandene Datei aus DIESER Aussensicht?

    Nur dann darf sie ueberschrieben werden - ein Wiederholungslauf derselben Batch-Nummer
    (Session-Limit, zweites `/meta`) muss moeglich bleiben. Alles andere gilt als fremd.
    """
    if not Path(pfad).is_file():
        return True                                     # nichts da, kein Konflikt
    if art == "md":
        return read_text(pfad).lstrip().startswith(_kopf_md(batch))
    if art == "json":
        d = read_json(pfad)
        return (isinstance(d, dict) and int(d.get("batch") or 0) == int(batch)
                and "rc" in d)
    if art == "jsonl":
        for linie in read_text(pfad).splitlines():      # erste Zeile = unser Ereignis
            if not linie.strip():
                continue
            try:
                d = json.loads(linie)
            except ValueError:
                return False
            return isinstance(d, dict) and "type" in d
        return True                                     # leere Datei: abgebrochener Lauf
    return True                                         # err/hooks: Hilfsdateien des Harness


def ablage_konflikt(cfg, batch: int) -> list[str]:
    """Fremde Dateien am neuen Ablageort (`[]` = frei). Nur pruefen, nichts aendern."""
    out: list[str] = []
    for art in BELEGE:
        p = pfad_neu(cfg, batch, art)
        if p.exists() and not _ist_unsere_ablage(p, batch, art):
            out.append(str(p))
    return out


def ablage_pruefen(cfg, batch: int) -> None:
    """Vor dem (bezahlten) Lauf pruefen - `AblageKonflikt` mit klarer Meldung, sonst still."""
    konflikt = ablage_konflikt(cfg, batch)
    if not konflikt:
        return
    raise AblageKonflikt(
        f"Ablage-Kollision: in {batch_ordner(cfg, batch)} liegt schon "
        + ", ".join(Path(p).name for p in konflikt)
        + ", und die Datei stammt nicht von der Aussensicht zu Batch "
        + f"{int(batch)}. Der Lauf wurde NICHT gestartet und es wurde nichts "
        "geschrieben. Die Datei wegschieben und die Aussensicht erneut ausloesen "
        "(z.B. `/meta`).")


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
    nicht verloren - er steht mit Wortlaut in `runs/b<N>/meta.md` (R13br; vorher
    `runs/meta-<batch>.md`), im Register und in `/fragen` ("verworfen - pruefen?").
    Eine EIGENE Kennung (`-v1`) ist noetig, weil die
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
#
# R13aq (30.09.2026): dasselbe fuer `zur Kenntnis`. Gemessen: `runs/b217/review.md:15`
# antwortet "M213-4a: zur Kenntnis - die Batch-Uhr bleibt das Mass" - der Befund galt
# bis dahin als offen (`runs/meta-217.json`, `offen_alt`). "Zur Kenntnis" heisst: der
# Reviewer hat es gesehen und bewusst NICHT umgesetzt; das ist ein erledigter Posten,
# keine offene Frage (dieselbe Haltung wie `zurueckgestellt`).
UEBERNOMMEN_WORTE = ("uebernommen", "beantwortet", "erledigt", "zurueckgestellt",
                    "zur kenntnis")
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


def bericht_dateien(cfg) -> dict[int, Path]:
    """Die Maschinenfassungen je Batch (`{batch: pfad}`) - neuer Ort vor altem Ort.

    R13br: gelesen werden BEIDE Ablagen. Liegt derselbe Batch an beiden Orten (nach dem
    Wandeln), gilt der NEUE (`runs/b<N>/meta.json`); der alte Beleg bleibt unberuehrt
    liegen und zaehlt nicht doppelt. Die Nummer kommt aus dem Dateinamen (alt) bzw. dem
    Ordnernamen (neu) - der Dateiinhalt (`batch`) entscheidet erst in `bericht_zustand`.
    """
    out: dict[int, Path] = {}
    runs = Path(cfg.root) / "runs"
    if not runs.is_dir():
        return out
    for p in runs.glob("meta-*.json"):                  # alt zuerst - neu ueberschreibt
        m = re.fullmatch(r"meta-(\d+)\.json", p.name)
        if m:
            out[int(m.group(1))] = p
    for p in runs.glob("b*/meta.json"):                 # neuer Ort hat Vorrang
        m = re.fullmatch(r"b(\d+)", p.parent.name)
        if m:
            out[int(m.group(1))] = p
    return out


def letzte_bericht_batches(cfg) -> list[int]:
    """Die Batches, fuer die ein Aussensicht-Bericht vorliegt (BEIDE Ablagen, R13br).

    R13aa (Punkt 2): damit laesst sich sagen, welcher Lauf der NEUESTE war - `/fragen`
    zeigt die verworfenen Befunde nur, wenn dieser Lauf welche verworfen hat.
    """
    try:
        return sorted(bericht_dateien(cfg))
    except OSError:
        return []


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


def bericht_zustand(cfg) -> dict:
    """Die Berichte `runs/b<N>/meta.json` / `runs/meta-*.json` auswerten (R13aq/R13br).

    Rueckgabe: `{letzte_gelungen, befunde, neuester_gescheitert, gescheitert_grund,
    anzahl_berichte}`.

    Gelesen wird ueber `bericht_dateien` BEIDE Ablagen (neuer Ort vor altem).

    Gelaufen wird von **neu nach alt**: ein gescheiterter Bericht (`gelaufen: false` oder
    `rc != 0`) wird gemerkt, der ERSTE gelungene beendet die Suche - er hat die
    gescheiterten ueberholt. Berichte ohne beide Felder (vor R13aq) zaehlen als gelaufen.

    Anlass: `runs/meta-217.json` (rc=1, `error_max_turns`) entstand VOR dem Fix und hat
    die Takt-Marke im Zustand trotzdem gesetzt. Der Bericht ist der dauerhafte Beleg -
    aus ihm kommt deshalb sowohl die Anzeige (`zeile`) als auch der Wiederholungs-Grund
    (`faellig`), ohne dass ein Zustand oder ein Beleg nachtraeglich geaendert werden muss.
    """
    aus = {"letzte_gelungen": 0, "befunde": 0, "neuester_gescheitert": 0,
           "gescheitert_grund": "", "anzahl_berichte": 0}
    runs = Path(cfg.root) / "runs"
    if not runs.is_dir():
        return aus
    try:
        # R13br: beide Ablagen, je Batch hoechstens einmal (neuer Ort gewinnt).
        berichte = sorted(bericht_dateien(cfg).values(),
                          key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return aus
    aus["anzahl_berichte"] = len(berichte)
    for p in berichte:
        try:
            d = json.loads(read_text(p))
        except (OSError, ValueError):
            continue
        batch = int(d.get("batch") or 0)
        if d.get("gelaufen") is False or int(d.get("rc") or 0) != 0:
            if not aus["neuester_gescheitert"]:
                aus["neuester_gescheitert"] = batch
                aus["gescheitert_grund"] = str(d.get("gescheitert_grund")
                                               or f"rc={d.get('rc')}").strip()
            continue
        if not aus["letzte_gelungen"]:
            aus["letzte_gelungen"] = batch
            aus["befunde"] = len(d.get("befunde") or [])
        break
    return aus


def zeile(cfg) -> str:
    """Eine Zeile fuer `/bilanz` und `/status` ('' = es gab noch keine Aussensicht).

    Aufbau (R13z, Nutzerauftrag): `Aussensicht: n Befunde, davon u uebernommen,
    a abgelehnt, o offen` - dahinter in Klammern die letzte Aussensicht (Batch und Zahl
    der Befunde des Laufs) und der eingestellte **Takt** (`harness.toml`,
    `[meta] aussensicht_takt`, R13bo; frueher `every_batches`). Die Quote ist die
    Grundlage der Auswertung nach einer Woche.

    R13aq: "letzte Aussensicht" ist die letzte **gelungene**; ein gescheiterter Lauf wird
    eigens genannt (`zuletzt gescheitert: Batch N (wird wiederholt)`), sonst stuende in
    `/bilanz`, es habe eine Aussensicht gegeben, die es nicht gab.
    """
    alle = ledger(cfg)
    zustand = bericht_zustand(cfg)
    if not alle and not zustand["anzahl_berichte"]:
        return ""
    batch = zustand["letzte_gelungen"]
    anzahl = zustand["befunde"] or len(alle)
    q = quote(cfg)
    kopf = (f"Aussensicht: {q['gesamt']} Befunde, davon {q['uebernommen']} uebernommen, "
            f"{q['abgelehnt']} abgelehnt, {q['offen']} offen")
    herkunft = [f"letzte Aussensicht: Batch {batch or '?'}"]
    if zustand["anzahl_berichte"] and anzahl:
        herkunft.append(f"{anzahl} Befunde in diesem Lauf")
    if zustand["neuester_gescheitert"]:
        herkunft.append(f"zuletzt gescheitert: Batch {zustand['neuester_gescheitert']} "
                        "(wird wiederholt)")
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
# jetzt aus der Preflight-Zeile `Hybrid-A4` gemessen (`hybrid_stillstand` unten), die
# VOR dem Review vorliegt. Die Klassifikation "B-Batch oder C-Batch" (`stand.strang_von_
# batch`) nutzt die Zeile weiterhin als einen Beleg - sie bleibt deshalb im Prompt.


def hybrid_stillstand(cfg) -> str:
    """Steht der Hybrid-Lauf ueber die letzten B-Batches still? ('' = nein)

    R13bo-5 (Aussensicht M239-2/M236-7): verglichen wird der **Halt-PC der Zeile
    `Hybrid-A4`** (der ECHTE Halt), nicht der der Zeile `Hybrid-Lauf` - dort steht die
    200M-Schranke, die auch dann stehen bleibt, wenn der Lauf weiterzieht (B250). Ein
    Preflight mit `FEHLER`-Zeile faellt aus der Reihe (`stand.hybrid_a4_verlauf`).

    Verglichen werden die letzten `[meta] bschritt_stillstand_batches` **B-Batches**
    (Vorgabe 3) mit A4-Zeile. Stillstand heisst: der Halt-PC ist in allen gleich **und**
    die Schritte bis zum ersten echten Halt steigen nicht.

    Der Melder **schweigt**, solange die letzten `HYBRID_RUHE_C_BATCHES` Batches alle
    C-Batches waren (Strang B ruht); waehrend einer B-Phase gilt er normal. C-Batches
    zaehlen nicht mit, und Batches ohne A4-Zeile (vor B240) fehlen in der Reihe - beides
    wird NICHT geraten.
    """
    if not any(ist_b_batch(cfg, int(b))
               for b, _p in stand.preflight_dateien(cfg, HYBRID_RUHE_C_BATCHES)):
        return ""
    n = max(2, int(grenzen(cfg).get("bschritt_stillstand_batches")
                   or HYBRID_STILLSTAND_BATCHES))
    verlauf = stand.hybrid_a4_verlauf(cfg, n + 4)
    reihe = [e for e in verlauf if ist_b_batch(cfg, int(e["batch"]))]
    # R13bp (Punkt 4, Nutzerauftrag): Zwischenspeicher-Treffer sind KEINE eigene Messung -
    # der Preflight druckt dann die Rohausgabe eines aelteren A4-Laufs erneut ab (gemessen
    # 2026-10-03: B250 und B252-B255 trugen alle denselben Wert, nur B249 und B251 hatten
    # selbst gemessen). Solche Eintraege fallen aus der VERGLEICHSREIHE, sonst meldet der
    # Waechter einen Stillstand, den niemand gemessen hat. Ist die Herkunft unbekannt
    # (Preflight ohne Zeile `Zwischenspeicher`, jeder Lauf vor B250), bleibt der Eintrag
    # stehen - es wird nichts behauptet.
    ohne_cache = [e for e in reihe if e.get("cache") is not True]
    ausgelassen = [e for e in reihe if e.get("cache") is True]
    if len(ohne_cache) < n:
        return ""
    letzte = ohne_cache[-n:]
    pcs = {e["halt_pc"] for e in letzte}
    if len(pcs) != 1:
        return ""
    wege = [int(e["weg"]) for e in letzte]
    if any(b > a for a, b in zip(wege, wege[1:])):
        return ""                      # die Schrittzahl STEIGT - also Fortschritt
    b_erst, b_letzt = letzte[0]["batch"], letzte[-1]["batch"]
    b_reihe = ", ".join(f"B{e['batch']}" for e in letzte)
    zusatz = ("" if not ausgelassen else
              "; ausgelassen (Zwischenspeicher-Treffer, keine eigene Messung): "
              + ", ".join(f"B{e['batch']}" for e in ausgelassen))
    return (f"{HYBRID_GRUND} haengt: Halt-PC {letzte[-1]['halt_pc']} unveraendert und "
            f"Schritte {wege[0]} -> {wege[-1]} steigt nicht "
            f"({b_reihe}, Quelle analysis/{letzte[-1]['datei']}, Zeile \"Hybrid-A4\") "
            f"- kein Fortschritt ueber {n} B-Batches (B{b_erst} bis B{b_letzt})"
            f"{zusatz}")


def hybrid_neuester_b(cfg) -> int:
    """Die Nummer des neuesten B-Batches mit `Hybrid-A4`-Zeile (0 = keiner).

    R13bo-5: dieselbe Quelle wie `hybrid_stillstand` - die Marke muss zu der Reihe
    passen, die der Melder vergleicht (sonst feuert derselbe Stand erneut).
    R13bp: die Marke nimmt ALLE Eintraege, auch Zwischenspeicher-Treffer. Der Melder
    vergleicht nur die eigenen Messungen (`hybrid_stillstand`) - waere die Marke daraus
    gebildet, stuende sie auf einem aelteren Batch als der zuletzt gesehene B-Batch und
    derselbe Stand wuerde bei jeder Pruefung erneut gemeldet.
    """
    reihe = [e for e in stand.hybrid_a4_verlauf(cfg, 6) if ist_b_batch(cfg, int(e["batch"]))]
    return int(reihe[-1]["batch"]) if reihe else 0


def hybrid_gemeldet_bis(meta: dict) -> int:
    """Die Stillstands-Marke; fehlt sie, gilt 0 (nichts gemeldet)."""
    wert = (meta or {}).get(MARKE_HYBRID_SCHLUESSEL)
    try:
        return int(wert) if wert is not None else 0
    except (TypeError, ValueError):
        return 0


def marker_gemeldet_bis(meta: dict, name: str) -> int:
    """Bis zu welcher Review-Datei diese Markerart schon gemeldet ist (R13bn).

    Fehlt die Tafel im Zustand, gilt 0 = nichts gemeldet (keine Migration, s. o.).
    """
    tafel = (meta or {}).get(MARKE_MARKER_SCHLUESSEL) or {}
    try:
        return int((tafel or {}).get(name) or 0)
    except (TypeError, ValueError):
        return 0


def marker_beteiligt(gruende) -> dict:
    """Welche Markerart war an diesen Ausloeser-Gruenden beteiligt - mit ihrer Datei?

    Rückgabe `{name: batch}`; leer heisst: kein Marker-Ausloeser dabei. Der Batch wird aus
    dem GRUND gelesen (dieselbe Form, die `faellig` schreibt), damit der Aufrufer nicht
    noch einmal in die Reviews sehen muss.
    """
    out: dict = {}
    for g in (gruende or []):
        for name, _muster in MARKER_MUSTER:
            m = re.match(rf"^{re.escape(name)} - laut Review in runs/b(\d+)", str(g))
            if m:
                out[name] = max(int(m.group(1)), int(out.get(name) or 0))
    return out


def marker_marke_setzen(cfg, state, gruende) -> dict:
    """Die beteiligten Markerarten auf ihre Review-Datei setzen (R13bn).

    Wird - wie `kernzahl_marke_setzen` - erst NACH einem gelaufenen Lauf (rc=0) gerufen.
    Eine Marke feuert damit JE REVIEW-DATEI genau einmal; kommt spaeter eine NEUE Review
    mit derselben Marke, ist ihre Nummer groesser und sie loest wieder aus.
    """
    bet = marker_beteiligt(gruende)
    if bet:
        meta = dict(state.data.get("meta") or {})
        tafel = dict(meta.get(MARKE_MARKER_SCHLUESSEL) or {})
        for name, b in bet.items():
            tafel[name] = max(int(b), int(tafel.get(name) or 0))
        meta[MARKE_MARKER_SCHLUESSEL] = tafel
        state.data["meta"] = meta
    return bet


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


def station_stillstand(cfg) -> str:
    """Text, wenn der Stillstandszähler der B-Phase seine Schwelle erreicht hat (R13bt-5).

    Regel (`analysis/hybrid-plan.md:257-274`, Nutzerklarstellung 2026-10-03): Schwelle **4
    B-Batches in Folge ohne Station**, Zaehler **ab jeder Station neu**; C-Batches zaehlen
    nicht mit und setzen nicht zurueck. In einer reinen B-Reihe ist der Zaehler das
    Fortschrittsmass (die C-Hochrechnung ruht dann, `stand._mischung_zeile`).

    Die QUELLE der Station ist allein die Pflichtzeile `STATION: ja|nein` im Review
    (`runs/b<N+1>/review.md`) - der Harness raet nicht. Ist ein Batch nicht belegt, ist der
    Zaehler eine **Untergrenze**; erreicht er die Schwelle trotzdem, meldet der Ausloeser
    (die gezaehlten Batches sind ja belegt) und nennt die Luecke im Text.
    """
    z = stand.stillstand_zaehler(cfg)
    if not z.get("schwelle_erreicht"):
        return ""
    zusatz = ""
    if z.get("luecke_ab"):
        zusatz = (f"; ab B{z['luecke_ab']} ist der Stand nicht belegt - die Zahl ist eine "
                  "Untergrenze")
    elif z.get("grenze_ab"):
        zusatz = f"; ab B{z['grenze_ab']} ist der Strang nicht belegt"
    return (f"{STATION_GRUND}: {z['zaehler']} B-Batches in Folge ohne Station "
            f"(B{z['von']}..B{z['bis']}, Schwelle {z['schwelle']}) - in der B-Phase ist die "
            f"Station das Fortschrittsmass (analysis/hybrid-plan.md:257-274){zusatz}")


def station_neuester_b(cfg) -> int:
    """Der Markenschluessel des B-Phasen-Stillstands: der ERSTE Batch des gezaehlten Laufs.

    Das ist die letzte Station + 1 (`stand.stillstand_zaehler` -> `von`). Er bleibt
    innerhalb eines Laufs konstant; ohne Station wuerde der Zaehler sonst bei jedem Batch
    erneut melden (s. Kommentar bei `MARKE_STATION_SCHLUESSEL`).

    0 = kein gezaehlter B-Batch (dann gibt es nichts zu melden).
    """
    z = stand.stillstand_zaehler(cfg)
    return int(z["von"]) if int(z.get("zaehler") or 0) else 0


def station_gemeldet_bis(meta: dict) -> int:
    """Die B-Phasen-Marke; fehlt sie, gilt 0 = nichts gemeldet (keine Migration)."""
    wert = (meta or {}).get(MARKE_STATION_SCHLUESSEL)
    try:
        return int(wert) if wert is not None else 0
    except (TypeError, ValueError):
        return 0


def station_marke_setzen(cfg, state) -> int:
    """Die Marke auf den ersten Batch des gemeldeten Laufs setzen (R13bt-5).

    Wird - wie `kernzahl_marke_setzen` und `hybrid_marke_setzen` - erst NACH einem
    erfolgreichen Lauf (rc=0) gerufen. Ein gescheiterter Lauf laesst die Marke unveraendert
    (der Stillstand meldet beim naechsten Batch-Ende erneut - der bezahlte Lauf ist nicht
    verloren).
    """
    neu = station_neuester_b(cfg)
    if neu > 0:
        meta = dict(state.data.get("meta") or {})
        meta[MARKE_STATION_SCHLUESSEL] = int(neu)
        state.data["meta"] = meta
    return int(neu)


def station_beteiligt(gruende) -> bool:
    """War der B-Phasen-Stillstand an diesen Ausloeser-Gruenden beteiligt?"""
    return any(str(g).startswith(STATION_GRUND) for g in (gruende or []))


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
        f"  * Abschluss   : runs/b{int(nummer):03d}/antwort.md (der ERSTE Bericht des "
        f"Workers; seit R13aw bleibt er stehen) + runs/b{int(nummer):03d}/antwort-forts*.md "
        "(die Antworten der Fortsetzungen; fuer B214-B218 liegt der nachgetragene Bericht "
        "als antwort-bericht.md daneben - lies beide)",
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
        # R13aq: meta-217 verbrauchte alle Zuege mit Vorarbeit und schrieb am Ende nur
        # einen Zwischenstand - der Lauf war verloren. Deshalb eine Frist VOR dem Limit
        # (R13at: acht Zuege, `FRIST_ABSTAND`).
        f"ZEITLIMIT: Schreibe spaetestens nach {max(1, int(g['max_turns']) - FRIST_ABSTAND)} "
        "Zuegen "
        "die Antwort im Blockformat, auch wenn die Tiefenprobe unvollstaendig ist; "
        "Unvollstaendiges als nicht geprueft kennzeichnen.",
        "",
    ]
    return "\n".join(kopf) + "\n" + eingaben(cfg, state, tiefe=tiefe) + "\n\n" + \
        FORMAT_HINWEIS.format(max_befunde=int(g["max_befunde"])) + "\n"


# ------------------------------------------------------------------ Kommando
def build_command(cfg, hooks_settings: str | None = None) -> list[str]:
    """Kommandozeile fuer die Aussensicht - IMMER frische Session, nur lesend.

    R13bo: eigenes Modell `aussensicht_modell` (Vorgabe Opus 5.5), Abo-Token, gleiche
    Pfad- und Secret-Regeln wie der Reviewer. `hooks_settings` (R13ar) ist die
    Einstellungsdatei mit der Zuguhr (`write_hook_settings`); fehlt sie, laeuft der
    Aufruf wie vorher ohne Hook.
    """
    exe = str(cfg.get("claude", "exe"))
    tools_value = ",".join(["Read", "Grep", "Glob", GIT_TOOL])
    cmd = [exe, "-p",
           "--output-format", "stream-json",
           "--verbose",
           "--model", str(cfg.get("claude", "aussensicht_modell", "claude-opus-5-5")),
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
    if hooks_settings:
        cmd += ["--settings", str(hooks_settings)]
    return cmd


def write_hook_settings(cfg, batch: int) -> str | None:
    """Die Zuguhr als PostToolUse-Hook fuer DIESEN Lauf (R13ar) -> Pfad.

    Anlass (gemessen): `runs/meta-217` verbrauchte alle Zuege mit Vorarbeit und schrieb
    am Ende nur einen Zwischenstand - der Lauf war verloren. Der einzige Text, den das
    Modell WAEHREND des Laufs zu sehen bekommt, ist der Hook-Kontext (R13ac hat den Weg
    mit echtem Lauf belegt: `docs/_r13ac_hook.txt`). Die Uhr zeigt die Zugarzahl, die
    die CLI selbst zaehlt (Werkzeugrunden), und ab `Limit - FRIST_ABSTAND` (R13at: 8)
    die Aufforderung, im Blockformat zu antworten.

    Fehlt das Skript, wird KEIN Hook gehaengt (der Lauf bleibt unberuehrt).
    """
    skript = Path(__file__).resolve().parents[1] / "tools" / "aussensicht_uhr.py"
    if not skript.is_file():
        return None
    grenze = int(grenzen(cfg)["max_turns"])
    daten = {"hooks": {"PostToolUse": [{"hooks": [{
        "type": "command",
        "timeout": 10,
        "command": sys.executable,
        "args": [str(skript), "--limit", str(grenze), "--frist", str(FRIST_ABSTAND)],
    }]}]}}
    # R13br: Hilfsdatei DIESES Laufs - sie wird je Lauf neu geschrieben (auch bei einem
    # Wiederholungslauf derselben Nummer) und deshalb NICHT vom Ablage-Waechter geprueft.
    ziel = hooks_pfad(cfg, batch)
    write_text_atomic(ziel, json.dumps(daten, indent=1) + "\n")
    return str(ziel)


def limit_hinweis(batch: int, runden: int, grenze: int) -> str:
    """Warnung, wenn ein Lauf mehr als 80 % des Zuglimits gebraucht hat (R13ar).

    Rueckgabe '' heisst: kein Hinweis. Der Satz steht so in der Telegram-Meldung UND
    als Zeile im Bericht (`bericht`) - eine Quelle, zwei Anzeigen.
    """
    if grenze <= 0 or runden <= 0:
        return ""
    if runden > 0.8 * grenze:
        return (f"Aussensicht B{int(batch)}: {int(runden)} von {int(grenze)} Zuegen "
                "genutzt - Limit pruefen")
    return ""


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
# R13aq: `zur Kenntnis` ist das dritte Verdikt neben uebernommen/abgelehnt (es zaehlt wie
# "erledigt", s. `UEBERNOMMEN_WORTE`). Gemessen `runs/b217/review.md:15`.
_RE_VERDIKT = re.compile(r"\b(uebernommen|übernommen|abgelehnt|erledigt|verworfen|offen|"
                         r"zurueckgestellt|zurückgestellt|zur\s+Kenntnis)\b", re.IGNORECASE)

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
        status = " ".join(str(status).split())        # R13aq: "zur  Kenntnis" -> ein Space
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
        # R13bm (Punkt 4): das Session-Limit der Aussensicht selbst - dieselbe Uhr wie
        # beim Reviewer (`protocol.looks_like_limit`), damit der Harness nicht bis zum
        # naechsten Batch-Ende wartet, sondern nach dem Reset wiederholt.
        self.limit_reached: bool = False
        # R13aq: warum der Lauf NICHT als Aussensicht zaehlt (leer = gelaufen).
        self.subtype: str = ""
        self.zuege: int | None = None
        self.gescheitert: str = ""
        # R13ar: Werkzeugrunden - die Zahl, gegen die die CLI ihr Zuglimit prueft.
        self.zug_runden: int = 0

    def describe(self) -> str:
        return (f"rc={self.rc} dauer={self.dauer_s:.0f}s modell={self.modell or '-'} "
                f"befunde={len(self.befunde)} verworfen={len(self.verworfen)}"
                + (f" zuege={self.zuege}" if self.zuege else "")
                + (f" runden={self.zug_runden}" if self.zug_runden else "")
                + (f" subtype={self.subtype}" if self.subtype else "")
                + (f" tiefenprobe=B{self.tiefe.get('batch')}"
                   if self.tiefe.get("batch") else ""))


def gelaufen(res) -> tuple[bool, str]:
    """Zaehlt dieser Lauf als gelungene Aussensicht? (R13aq) -> `(ok, grund)`.

    Nein, wenn
      * der Lauf ins **Session-Limit** gelaufen ist (`res.limit_reached`, R13bm) - das ist
        kein Fehlschlag, sondern ein Wartezustand: der Harness wartet auf den Reset
        (plus Puffer) und wiederholt die Aussensicht dann; oder
      * `rc != 0` ist - Abbruch durch Zeitgrenze, **Zuglimit** (`error_max_turns`),
        API-Fehler; der Grund nennt `subtype` und Zugarzahl, soweit gemessen; oder
      * kein Antwortblock da ist (`0 Befunde` UND keine `<AUSSENSICHT>`-Zusammenfassung).

    GEMESSEN (30.09.2026, `runs/meta-217.md`): rc=1, `error_max_turns` nach 202 s,
    0 Befunde, Rohantwort nur eine Zwischenmeldung ("Zwischenstand: … Jetzt die
    Tiefenprobe B214"). Der Harness zaehlte das als gelaufene Aussensicht und setzte die
    Takt-Marke - der naechste automatische Lauf waere damit erst drei Batches spaeter
    gekommen, mit einem Bericht, der wie ein Ergebnis aussieht.
    """
    if getattr(res, "limit_reached", False):
        teile = [f"rc={res.rc}", "Session-Limit"]
        if res.zuege:
            teile.append(f"{int(res.zuege)} Zuege")
        return False, "Aussensicht im Session-Limit (" + ", ".join(teile) + ")"
    if int(res.rc or 0) != 0:
        teile = [f"rc={res.rc}"]
        if res.subtype:
            teile.append(str(res.subtype))
        if res.zuege:
            teile.append(f"{int(res.zuege)} Zuege")
        return False, ", ".join(teile)
    if not (res.summary or res.befunde):
        return False, "kein AUSSENSICHT-Block in der Antwort (0 Befunde)"
    return True, ""


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

    R13br: die Ablage liegt im Ordner des bewerteten Batches (`runs/b<N>/meta.*`). VOR dem
    Lauf prueft `ablage_pruefen` den Zielort - liegt dort eine fremde Datei, wird
    `AblageKonflikt` geworfen und KEIN bezahlter Lauf gestartet.
    """
    res = Ergebnis()
    batch = int(state.batch or 0)
    ablage_pruefen(cfg, batch)                       # R13br: erst pruefen, dann laufen
    res.tiefe = tiefenprobe_waehlen(cfg, zufall=zufall)
    prompt = build_prompt(cfg, state, grund, tiefe=res.tiefe)
    ziel = stream_pfad(cfg, batch)
    batch_ordner(cfg, batch, anlegen=True)           # fehlt er, legt die Aussensicht ihn an
    res.stream_path = str(ziel)
    if mock:
        roh = MOCK_ANTWORT
        write_text_atomic(ziel, json.dumps({"type": "result", "result": roh}) + "\n")
        res.text, res.rc, res.modell = roh, 0, "(Attrappe)"
    else:
        oauth = secrets.load(cfg.secrets_dir, secrets.CLAUDE_OAUTH)
        env = envs.reviewer_env(cfg, os.environ, oauth)
        # R13ar: die Zuguhr als PostToolUse-Hook (Zug X von Y, ab Limit-5 die Frist).
        hooks = write_hook_settings(cfg, batch)
        cmd = build_command(cfg, hooks_settings=hooks)
        t0 = time.time()
        run = run_stream(cmd, env, cwd=str(cfg.decomp), out_path=ziel,
                         on_event=None, hard_wall_s=float(grenzen(cfg)["wall_s"]),
                         log=log, stdin_text=prompt,
                         stderr_path=err_pfad(cfg, batch))
        res.rc, res.dauer_s = run.rc, run.duration_s
        stats = streamjson.StreamStats()
        for linie in read_text(ziel).splitlines():
            stats.feed(linie)
        res.text = stats.final_text() or ""
        res.modell = stats.model or ""
        # R13bm (Punkt 4): ins Session-Limit gelaufen? Geprueft wird wie beim Reviewer
        # (`reviewer.run_review`) der ROHE Mitschnitt samt Fehlerdatei - im Text steht
        # die Meldung oft nur unvollstaendig.
        roh = read_text(ziel) + "\n" + read_text(err_pfad(cfg, batch))
        res.limit_reached = bool(protocol.looks_like_limit(roh)
                                 or protocol.looks_like_limit(res.text or ""))
        # R13aq: Abbruchgrund und Zugarzahl aus dem `result`-Ereignis (gemessen
        # meta-217: subtype=error_max_turns, num_turns=31) - sie stehen im Bericht und
        # in der Meldung, wenn der Lauf nicht als Aussensicht zaehlt.
        res.subtype = str((stats.result or {}).get("subtype") or "")
        res.zuege = stats.num_turns()
        # R13ar: die Werkzeugrunden (Zahl der CLI fuer ihr Zuglimit) - Grundlage der
        # Fruehwarnung "ueber 80 % des Limits genutzt".
        res.zug_runden = stats.runden()
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
    if meta.get("nach_limit_grund"):
        # R13bm (Punkt 4): Die vorige Aussensicht lief ins Session-Limit. Sie wird nach
        # der Wartezeit WIEDERHOLT - unabhaengig von Takt, Entprellung und Ausloeser:
        # der Anlass von damals muss nicht mehr messbar sein (z.B. ein einmaliger
        # Stillstand), und ohne diese Zeile waere der bezahlte Lauf verloren.
        return [f"Wiederholung nach Session-Limit: {meta['nach_limit_grund']}"]
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
    if MARKE_MARKER_SCHLUESSEL not in meta:
        meta[MARKE_MARKER_SCHLUESSEL] = {}
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
    # R13aq: eine GESCHEITERTE Aussensicht wird beim naechsten Batch-Ende genau einmal
    # wiederholt. Zwei Quellen, der hoehere Wert gilt:
    #   * der Zustandsvermerk `gescheitert_batch` (seit diesem Fix, gilt fuer Laeufe nach
    #     dem Neustart) und
    #   * der **Bericht** selbst (`bericht_zustand`) - `runs/meta-217.json` (rc=1) entstand
    #     VOR dem Fix und hat die Takt-Marke trotzdem gesetzt; der Bericht ist der
    #     dauerhafte Beleg und traegt die Wiederholung auch dann, wenn der Zustand
    #     verloren geht (Absturz zwischen Lauf und Zustandsschreiben).
    berichte = bericht_zustand(cfg)
    gescheitert = max(int(meta.get("gescheitert_batch") or 0),
                      int(berichte["neuester_gescheitert"] or 0))
    if gescheitert and batch > gescheitert:
        grund_text = str(meta.get("gescheitert_grund")
                         or berichte.get("gescheitert_grund") or "").strip()
        gruende.append(f"Wiederholung nach gescheiterter Aussensicht B{gescheitert}"
                       + (f" ({grund_text})" if grund_text else ""))
    # Die 10er-Regel greift erst, wenn schon einmal eine Aussensicht gelaufen ist:
    # sonst wuerde der ERSTE Start nach dieser Aenderung sofort einen Opus-Lauf
    # ausloesen (207 Batches Historie). Die erste Aussensicht loest der Nutzer aus.
    if letzte > 0 and batch > 0 and batch - letzte >= int(g["every_batches"]):
        gruende.append(f"alle {int(g['every_batches'])} Batches "
                       f"(letzte Aussensicht: Batch {letzte})")
    abb = state.data.get("letzter_abbruch") or {}
    if abb and int(abb.get("batch") or 0) > letzte:
        gruende.append(f"Worker-Abbruch in Batch {abb.get('batch')} ({abb.get('grund')})")
    for name, muster in MARKER_MUSTER:
        for b, zeile in _marker(cfg, muster)[:1]:
            if b <= marker_gemeldet_bis(meta, name):
                # R13bn: diese Marke ist aus DIESER Review-Datei schon gemeldet (die Sperre
                # gilt je Markenart). Ohne die Zeile stand derselbe Grund bei jeder Pruefung
                # neu in der Liste, solange die Datei in den letzten drei Reviews lag.
                continue
            gruende.append(f"{name} - laut Review in runs/b{b}: {zeile[:120]}")
    still = hybrid_stillstand(cfg)
    if still and hybrid_neuester_b(cfg) > hybrid_gemeldet_bis(meta):
        gruende.append(still)
    # R13bt-5: Stillstand der B-Phase (Schwelle 4 B-Batches ohne Station). Dasselbe
    # Muster wie oben - Melder UND Marke (der Zaehler waechst weiter, s. `station_neuester_b`).
    still_b = station_stillstand(cfg)
    if still_b and station_neuester_b(cfg) > station_gemeldet_bis(meta):
        gruende.append(still_b)
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
    """Der Bericht `runs/b<batch>/meta.md` (R13br; vorher `runs/meta-<batch>.md`)."""
    zeilen = [
        f"# Aussensicht Batch {batch}",
        "",
        f"- Zeitpunkt: {now_iso()}",
        f"- Anlass: {grund}",
        f"- Ausloeser-Gruende: {'; '.join(gruende[:6]) or '-'}",
        f"- Lauf: {res.describe()}",
    ]
    # R13ar: Zugarzahl und -verbrauch (die CLI prueft gegen die Werkzeugrunden) sowie
    # die Fruehwarnung, wenn ein Lauf ueber 80 % des Limits gebraucht hat.
    if res.zug_runden:
        grenze = int(grenzen(cfg)["max_turns"])
        zeilen.append(f"- Zuege (Werkzeugrunden): {res.zug_runden} von {grenze}"
                      + (f" - num_turns laut CLI: {res.zuege}" if res.zuege else ""))
        warnung = limit_hinweis(batch, res.zug_runden, grenze)
        if warnung:
            zeilen.append(f"- LIMIT PRUEFEN: {warnung}")
    ok, warum = gelaufen(res)
    if not ok:
        zeilen.append(f"- ERGEBNIS: GESCHEITERT ({warum}) - zaehlt NICHT als Aussensicht, "
                      "keine Marke, keine Verdikte")
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
    # R13br: zweites Netz - auch hier gilt, dass eine FREMDE Datei im Batchordner nicht
    # ueberschrieben wird (der erste Waechter steht in `run`, vor dem bezahlten Lauf).
    ablage_pruefen(cfg, int(batch))
    p = bericht_pfad(cfg, batch)
    write_text_atomic(p, bericht(cfg, batch, grund, res, verteilung, gruende))
    # R13aa (Punkt 2): verworfene Befunde ins Register - nicht wegwerfen (siehe
    # `verworfene_speichern`), damit `/fragen` sie als "verworfen - pruefen?" zeigen kann.
    verworfene_speichern(cfg, int(batch), list(res.verworfen or []))
    ok, warum = gelaufen(res)
    write_json_atomic(json_pfad(cfg, batch), {
        "batch": int(batch), "ts": now_iso(), "grund": grund, "gruende": list(gruende),
        "summary": res.summary, "rc": res.rc, "dauer_s": res.dauer_s, "modell": res.modell,
        "befunde": res.befunde, "verworfen": res.verworfen, "pruefungen": res.pruefungen,
        "ids": verteilung.get("ids") or [], "verdikte": verteilung.get("verdikte") or [],
        "offen_alt": verteilung.get("offen_alt") or [],
        "tiefenprobe": dict(res.tiefe or {}),
        # R13aq: der Lauf ist maschinenlesbar als gescheitert markiert (subtype/Zuege).
        "gelaufen": bool(ok), "gescheitert_grund": warum,
        "subtype": res.subtype, "zuege": res.zuege,
        "zug_runden": res.zug_runden,
        "text": res.text,
    })
    return p


# ------------------------------------------------- Ablage wandeln (R13br)
def _rel(cfg, p: Path) -> str:
    """Pfad relativ zur Harness-Wurzel, mit Schraegstrichen."""
    try:
        return p.relative_to(Path(cfg.root)).as_posix()
    except ValueError:
        return p.as_posix()


def _alt_art_und_batch(name: str) -> tuple[str | None, int | None]:
    """Einen ALTEN Dateinamen (`meta-<N>.md` …) auf `(art, batch)` abbilden."""
    for art, (_neu, alt) in ABLAGE.items():
        kopf, ende = alt.split("{n:03d}")
        if not name.startswith(kopf) or not name.endswith(ende):
            continue
        mitte = name[len(kopf):len(name) - len(ende)] if ende else name[len(kopf):]
        if not mitte:
            continue
        try:
            return art, int(mitte)
        except ValueError:
            continue
    return None, None


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _gleich(quelle: Path, ziel: Path) -> bool:
    """Groesse UND SHA-256 gleich? Nur dann darf ein Original geloescht werden."""
    try:
        if not ziel.is_file() or ziel.stat().st_size != quelle.stat().st_size:
            return False
        return _sha256(quelle) == _sha256(ziel)
    except OSError:
        return False


def ablage_wandeln(cfg, ausfuehren: bool = False, batches: list[int] | None = None,
                   verschieben: bool = False) -> dict:
    """Die losen Belege `runs/meta-<N>.*` in die Batch-Ordner bringen (R13br).

    Trockenlauf ist die Vorgabe (`ausfuehren=False`) - es wird nur berichtet, nichts
    geaendert. **Kopiert** wird immer, geloescht nur mit `verschieben=True` (R13bs):
    ein Original in `runs/` verschwindet **nur**, wenn die Kopie am Ziel existiert und
    **Groesse und SHA-256** gleich sind. Bei Abweichung oder Kollision bleibt das
    Original liegen - mit Grund in der Tafel.

    Ein vorhandenes Ziel wird NICHT ueberschrieben: gleicher Inhalt -> "schon da",
    anderer Inhalt -> "Ziel belegt" (gemeldet, nichts geschrieben, nichts geloescht).

    Rueckgabe: `{"zeilen": [...], "quellen": n, "kopiert": n, "geloescht": n,
    "behalten": n, "gleich": n, "belegt": n, "ausgefuehrt": bool, "verschieben": bool,
    "geplant_kopieren": n, "geplant_loeschen": n}`;
    je Zeile `{datei, ziel, vorhanden, hash_gleich, aktion, batch, art}`.
    """
    runs = Path(cfg.root) / "runs"
    gewaehlt = {int(b) for b in batches} if batches else None
    zeilen: list[dict] = []
    kopiert = geloescht = behalten = gleich = belegt = 0
    geplant_kopieren = geplant_loeschen = 0
    quellen = 0
    if runs.is_dir():
        for p in sorted(runs.iterdir()):
            if not p.is_file():
                continue
            art, nummer = _alt_art_und_batch(p.name)
            if art is None or (gewaehlt is not None and nummer not in gewaehlt):
                continue
            quellen += 1
            ziel = pfad_neu(cfg, nummer, art)
            # 1) Lage am Zielort: fehlt / gleich / verschieden
            if not ziel.is_file():
                vorhanden, hash_gleich, lage = "nein", "-", "fehlt"
            elif _gleich(p, ziel):
                vorhanden, hash_gleich, lage = "ja", "ja", "gleich"
            else:
                vorhanden, hash_gleich, lage = "ja", "nein", "verschieden"
            # 2) Plan (im Trockenlauf die Anzeige, sonst das Ziel)
            if lage == "verschieden":
                plan = "Ziel belegt (Hash verschieden) - Original bleibt"
            elif verschieben and lage == "fehlt":
                plan = "kopieren + Original loeschen"
            elif verschieben:
                plan = "Original loeschen (Kopie gleich)"
            else:
                plan = "kopieren" if lage == "fehlt" else "schon da"
            if lage == "fehlt":
                geplant_kopieren += 1
            if verschieben and lage != "verschieden":
                geplant_loeschen += 1
            # 3) Ausfuehren
            aktion = plan
            if lage == "verschieden":
                belegt += 1
                behalten += 1
            elif lage == "gleich":
                gleich += 1
            if ausfuehren and lage != "verschieden":
                if lage == "fehlt":
                    ensure_dir(ziel.parent)
                    shutil.copy2(p, ziel)
                    kopiert += 1
                # Nachlesen: die Kopie muss in Groesse UND SHA-256 stimmen, sonst
                # wird nichts geloescht (das Original ist der Beleg).
                if verschieben:
                    if _gleich(p, ziel):
                        try:
                            p.unlink()
                            geloescht += 1
                            aktion = ("kopiert + Original geloescht" if lage == "fehlt"
                                      else "Original geloescht (Kopie gleich)")
                        except OSError as exc:                      # noqa: BLE001
                            behalten += 1
                            aktion = (f"Loeschen fehlgeschlagen "
                                      f"({exc.__class__.__name__}) - Original bleibt")
                    else:
                        behalten += 1
                        aktion = "Kopie nicht bestaetigt - Original bleibt"
                else:
                    aktion = "kopiert" if lage == "fehlt" else "schon da"
            zeilen.append({"datei": f"runs/{p.name}", "ziel": _rel(cfg, ziel),
                           "vorhanden": vorhanden, "hash_gleich": hash_gleich,
                           "aktion": aktion, "batch": int(nummer), "art": art})
    reihenfolge = list(ABLAGE)
    zeilen.sort(key=lambda z: (z["batch"], reihenfolge.index(z["art"])))
    return {"zeilen": zeilen, "quellen": quellen, "kopiert": kopiert,
            "geloescht": geloescht, "behalten": behalten, "gleich": gleich,
            "belegt": belegt, "ausgefuehrt": bool(ausfuehren),
            "verschieben": bool(verschieben),
            "geplant_kopieren": geplant_kopieren,
            "geplant_loeschen": geplant_loeschen}


def ablage_tafel(erg: dict) -> str:
    """Die Tafel `Datei | Ziel | Hash gleich | Aktion` samt Bilanzzeile."""
    kopf = ("Datei", "Ziel", "Hash gleich", "Aktion")
    rows = [kopf] + [(z["datei"], z["ziel"], z.get("hash_gleich", "-"), z["aktion"])
                     for z in erg.get("zeilen") or []]
    breiten = [max(len(str(r[i])) for r in rows) for i in range(4)]
    linien = ["  ".join(str(r[i]).ljust(breiten[i]) for i in range(4)).rstrip()
              for r in rows]
    trenner = "  ".join("-" * b for b in breiten)
    verschieben = bool(erg.get("verschieben"))
    if erg.get("ausgefuehrt"):
        kopfzeile = "Aussensicht-Belege: KOPIERT" + (" + VERSCHOBEN" if verschieben
                                                     else " (Originale bleiben liegen)")
    else:
        kopfzeile = ("Aussensicht-Belege: Trockenlauf (nichts geaendert) - "
                     "--ausfuehren kopiert"
                     + (", --verschieben loescht danach das Original (nur bei gleicher "
                        "Groesse und gleichem SHA-256)" if verschieben else ""))
    out = [kopfzeile, "", linien[0], trenner, *linien[1:], "",
           (f"Quellen: {erg.get('quellen', 0)} - kopiert: {erg.get('kopiert', 0)}, "
            f"geloescht: {erg.get('geloescht', 0)}, behalten: {erg.get('behalten', 0)}")]
    if not erg.get("ausgefuehrt"):
        out.append(f"Trockenlauf: geplant kopieren: {erg.get('geplant_kopieren', 0)}, "
                   f"geplant loeschen: {erg.get('geplant_loeschen', 0)} - nichts geaendert.")
    elif not verschieben:
        out.append("Ohne --verschieben bleiben alle Originale in runs/ liegen.")
    if erg.get("belegt"):
        out.append("Ziel belegt heisst: im Batch-Ordner liegt eine ANDERE Datei - sie "
                   "wurde nicht angefasst und das Original bleibt liegen (der Waechter "
                   "der Aussensicht bricht dort ebenfalls ab).")
    if verschieben or not erg.get("ausgefuehrt"):
        out.append("Geloescht wird nur, wenn die Kopie am Ziel in Groesse und SHA-256 "
                   "gleich ist; sonst bleibt das Original als Beleg liegen.")
    return "\n".join(out)
