"""Batch-Uhr als Claude-Code-Hook (R13ac, Befund M210-1).

Wird vom Harness als `PostToolUse`-Hook in die Worker-Sitzung gehaengt (Einstellungsdatei
`runs/b<N>/worker-hooks.json`, erzeugt in `hx/worker.py`). Der Hook laeuft nach JEDEM
Werkzeugaufruf und gibt eine Zeile `additionalContext` aus - die Claude-CLI haengt sie
als System-Reminder neben das Werkzeugergebnis, das Modell liest sie beim naechsten
Aufruf (Doku "Hooks reference", Abschnitt "Add context for Claude").

    python tools/batch_uhr.py --state <state/run.json> --weich 90 --hart 180 \
        --umschalt 80 --preflight-min 10.0 --preflight-batch 214 \
        --kontext-limit 1000000 --run <runs/b<N>>

Quelle der Zahl ist dieselbe wie in der watch-Anzeige: `hx.uhr` liest
`state/run.json -> worker.started_at` (Prozessstart des Workers). Gegenprobe fuer einen
beendeten Lauf ist `runs/b<N>/result.json:duration_s`.

**R13ao (2026-09-29, Auftrag Teil B) - Hinweis bei zu fruehem Preflight.** Enthaelt ein
Shell-Aufruf `preflight.py`, liegt die Batch-Uhr VOR der Umschaltschwelle und traegt
`auftrag.md` eine `NACHRUECKLISTE` (`hx.worker.hat_nachrueckliste`), haengt der Hook den
Hinweis aus `hx.uhr.PREFLIGHT_HINWEIS` an. **Kein Blockieren** - der Worker entscheidet
selbst. Je erkanntem Preflight-Aufruf wird eine Zeile an
`runs/b<N>/preflight-aufrufe.jsonl` geschrieben (`{"ts", "min", "frueh"}`);
`hx.worker._finish_run` zaehlt sie nach `result.json` (`preflight_laeufe`,
`preflight_frueh`). Ohne `--run` (Einstellungsdatei eines schon laufenden Batches aus
aelterer Fassung) wird **nichts** geschrieben und **nichts** behauptet.

**R13bw-6 (05.10.2026, Nutzerauftrag) - die Sperre haelt bis zur Umschaltschwelle.**
R13be-2 stoppte nur den ERSTEN zu fruehen Preflight-Aufruf und liess jeden weiteren durch
(die Marke `preflight-blockiert.jsonl` wirkte als Einmal-Schalter). Gemessen (B271, B273):
der zweite Start kam **28 s bzw. 9 s** nach dem Stopp und lief ~10 min durch - mitten in der
Arbeit. Jetzt wird **jeder** Preflight-Start vor der Umschaltschwelle gestoppt, solange die
Nachrueckliste offen ist (die drei Bedingungen oben bleiben). Jeder Stopp schreibt eine
Zeile - jetzt mit `versuch` (wievielter Stopp im selben Batch), damit Wiederholungen
messbar sind, statt als "einmaliger Stopp" zu gelten.

**Kein Fehler darf den Batch stoeren**: bei jedem Problem wird nichts ausgegeben (bzw.
nur die Uhr-Zeile) und mit 0 beendet (der Hook ist dann wirkungslos, der Lauf geht
weiter).

**R13bw-13 (07.10.2026, Nutzerauftrag S1+S2).** Zwei Aenderungen an derselben Stelle:

  * **S1 - die Sperre prueft jetzt OFFEN, nicht nur VORHANDEN.** `_nachrueckliste_offen`
    fragt zusaetzlich `worker.nachrueckliste_marker`: liegt der Marker
    `NACHRUECKLISTE ERLEDIGT` in einer Antwort (`antwort.md`/`antwort-forts*.md`) oder in
    einem `text`-Block des laufenden Mitschnitts, ist die Liste erledigt und der Preflight
    **sofort** erlaubt. Anlass: B282 (`runs/b282/stream.jsonl:55860/55861`) - "all done"
    um 63 min, gesperrt bis 135 min, 72 min Leerlauf, gefuellt mit einem 0->2,7G-Lauf.
  * **S2 - keine neuen Hybrid-Langlaeufe** (`hybrid_lauf`, `port_regression`,
    `m2*_lang*.py`) ab dem Marker ODER ab Schwelle minus `LANGLAUF_VORLAUF_MIN` (30 min);
    kurze Formen mit `--schritte` unter `LANGLAUF_FREI_SCHRITTE` (200M ~ 2 min gemessen)
    bleiben frei. Beleg: `langlauf-blockiert.jsonl`.

**R13bw-11 (07.10.2026, Nutzerauftrag) - port_suche nicht mehr gekuerzt.** Der Worker rief`python scripts/port_suche.py 80008828 2>&1 | Select-Object -First 25` auf
(`runs/b289/stream.jsonl:56505`, Aussensicht B289 Befund 4); die Ausgabe brach genau an der
Ueberschrift der **Port-Treffer** ab (`port/src/vbi_handler.cpp`), weil die
Port-Fundstellen am **Ende** stehen (`AGENTS.md` R13az). Die Textregel allein hat das nicht
verhindert. Der `--pre`-Zweig lehnt deshalb jetzt **jeden** `port_suche`-Aufruf ab, der per
Pipe gekuerzt wird (`Select-Object -First|-Last`, `Select -First|-Last`, `head`, `| more`);
**ohne Pipe** und **mit `--schreiben`** bleibt der Aufruf erlaubt. Die Sperre haengt
**nicht** an der Batch-Uhr - sie gilt in jedem Batch. Beleg: `port_suche-blockiert.jsonl`.

**R13bl (02.10.2026, Nutzerauftrag) - R391-Sperre VOR dem Eingriff.** R391 verlangt den
Vorhersage-Commit `B<N>: Vorhersage …` VOR dem ersten Schreibzugriff unter `port/` oder
`scripts/`; der Reihenfolge-Waechter (`hx/reihenfolge.py`, R13as) misst das erst NACH dem
Lauf (B218: 17 `Edit`-Aufrufe auf `port/` vor dem Commit). Der `--pre`-Zweig blockiert
deshalb jetzt `Edit`/`Write`/`MultiEdit` auf diese beiden Baeume, solange kein solcher
Commit existiert - Antwort `deny` mit dem Hinweis "erst Vorhersage-Commit". `analysis/`
bleibt frei (dort wird die Vorhersage begruendet, das ist kein Eingriff in den Port).
**Nicht gefangen werden Bash-Schreibzugriffe** (Umleitung, `Set-Content`, `Copy-Item`,
`git checkout`): die sieht der Hook nicht als Dateipfad: dafuer bleibt der
Reihenfolge-Waechter zustaendig.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ZAHL_DATEI = "preflight-aufrufe.jsonl"
# R13bw-6: der Stopp je Batch - die Datei ist der BELEG (eine Zeile je Stopp mit Zeit,
# Minute und Versuchsnummer). Sie ist KEIN Einmal-Schalter mehr: die Sperre gilt, bis die
# Umschaltschwelle erreicht ist. Frueher liess ihr blosses Vorhandensein jeden weiteren
# Aufruf durch (gemessen in B271/B273: 28 s bzw. 9 s nach dem Stopp lief ein voller
# Preflight durch).
BLOCK_DATEI = "preflight-blockiert.jsonl"
# Wortlaut aus dem Nutzerauftrag (01.10.2026), nachgezogen mit R13bw-6: der Worker soll den
# Stopp nicht als Verbot lesen, aber auch nicht sofort wiederholen - der Preflight gehoert
# an das Batch-Ende, hinter die Umschaltschwelle.
BLOCK_ZUSATZ = ("Die Sperre gilt, bis die Batch-Uhr die Umschaltschwelle erreicht hat - "
                "auch ein zweiter Versuch wird gestoppt. Bis dahin an der Nachrueckliste "
                "weiterarbeiten; ist sie erledigt, das im Batch-Dokument festhalten und die "
                "Schranke abwarten (der Preflight gehoert an das Batch-Ende).")

# --------------------------------------------------- R391-Sperre (R13bl)
# Wortlaut des Auftrags: Edit/Write/MultiEdit auf Pfade unter `port/` und `scripts/`.
SPERR_VERBEN = ("Edit", "Write", "MultiEdit")
SPERR_BAEUME = ("port", "scripts")
# Belegdatei: eine Zeile je geblocktem Aufruf (das Review sieht damit, was passiert ist).
VORHERSAGE_BLOCK_DATEI = "vorhersage-blockiert.jsonl"

# --------------------------------------------- port_suche-Sperre (R13bw-11)
# Belegdatei: eine Zeile je geblocktem Aufruf (wie bei den beiden anderen Sperren).
PORT_SUCHE_BLOCK_DATEI = "port_suche-blockiert.jsonl"
# Wortlaut aus dem Nutzerauftrag (07.10.2026) - wortgleich, damit der Worker die Regel
# wiedererkennt; die Kennung nennt er selbst (`R13az, Aussensicht B289 Befund 4`).
PORT_SUCHE_GRUND = ("PORT_SUCHE-HINWEIS: port_suche ungekuerzt mit --schreiben ausfuehren "
                    "und die Datei lesen (R13az, Aussensicht B289 Befund 4)")

# --------------------------------- Langlaeufe und erledigte Nachrueckliste (R13bw-13)
# Nutzerauftrag 07.10.2026 (S1+S2, Beleg `runs/b282/stream.jsonl:55860/55861`):
#   S1 - die Preflight-Sperre prueft nicht mehr, OB der Auftrag eine NACHRUECKLISTE hat,
#        sondern ob sie noch OFFEN ist (`worker.nachrueckliste_marker`); ist sie erledigt,
#        ist der Preflight sofort erlaubt.
#   S2 - nach dem Marker (oder ab Schwelle minus 30 min) starten keine neuen
#        Hybrid-Langlaeufe mehr; kurze Formen (`--schritte` unter 200M, ~2 min gemessen)
#        bleiben frei.
LANGLAUF_BLOCK_DATEI = "langlauf-blockiert.jsonl"
LANGLAUF_VORLAUF_MIN = 30.0


def _betreffs(decomp) -> list[str]:
    """`git log --all` im Decomp-Repo - nur lesend, ein Aufruf (R13bl).

    Leere Liste, wenn git fehlt oder scheitert: der Hook darf den Lauf NIE stoeren.
    """
    try:
        p = subprocess.run(["git", "-C", str(decomp), "log", "--all", "--date-order",
                            "--pretty=format:%H\x1f%cI\x1f%s"],
                           capture_output=True, stdin=subprocess.DEVNULL, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return []
    return (p.stdout or "").splitlines() if p.returncode == 0 else []


def _batch_nummer(state: dict) -> int:
    """Nummer des laufenden Batches - aus der Harness-EIGENEN Zaehlung (R13bj).

    NICHT aus dem Anker gelesen: `state.batch` setzt der Harness beim Start
    (`orchestrator.own_batch()`), `state.live.batch` ist dieselbe Zahl im Betrieb (R13q).
    """
    for quelle in (state.get("batch"), (state.get("live") or {}).get("batch")):
        try:
            n = int(quelle or 0)
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return 0


def vorhersage_vorhanden(decomp, batch: int) -> bool:
    """Beginnt ein Commit-BETREFF mit `B<N>: Vorhersage`? (R13bl)

    Die Regel ist NICHT nachgebaut, sondern `hx.reihenfolge.vorhersage_muster` (R13as;
    BOM-tolerant, Wortgrenze nach "Vorhersage"). Damit zaehlen auch
    `B<N>: Vorhersage Fortsetzung` und `B<N>: Vorhersage-Nachtrag (…)`. Bei einer
    **Fortsetzung oder Wiederholung** derselben Nummer wird der Commit des VORIGEN Laufs
    gefunden - er zaehlt ausdruecklich (Nutzerauftrag).
    """
    from hx import reihenfolge
    muster = reihenfolge.vorhersage_muster(batch)
    for c in reihenfolge.vorhersage_zeilen_lesen(_betreffs(decomp)):
        if muster.match(c[2]):
            return True
    return False


def r391_grund(eingabe: dict, state: dict, decomp, lauf) -> str:
    """Blockgrund, wenn dieser Aufruf R391 verletzt ('': durchlassen).

    Reihenfolge der Pruefungen (billig zuerst): Werkzeug -> Pfad -> Zustand -> git.
    Die Git-Abfrage laeuft also NUR fuer die drei Datei-Werkzeuge auf `port/`/`scripts/`.
    """
    if str(eingabe.get("tool_name") or "") not in SPERR_VERBEN or decomp is None:
        return ""
    from hx import reihenfolge
    felder = eingabe.get("tool_input")
    felder = felder if isinstance(felder, dict) else {}
    pfad, baum = "", ""
    for feld in ("file_path", "notebook_path", "path"):
        wert = felder.get(feld)
        for name in SPERR_BAEUME:
            if reihenfolge.pfad_token(wert, decomp, name):
                pfad, baum = str(wert or ""), name
                break
        if baum:
            break
    if not baum:
        return ""
    batch = _batch_nummer(state)
    if batch <= 0:
        return ""
    if vorhersage_vorhanden(decomp, batch):
        return ""
    if lauf is not None:
        try:
            from hx.util import append_jsonl
            append_jsonl(Path(lauf) / VORHERSAGE_BLOCK_DATEI,
                         {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "batch": batch, "werkzeug": str(eingabe.get("tool_name") or ""),
                          "pfad": pfad})
        except Exception:                                                  # noqa: BLE001
            pass
    return (f"R391: erst der Vorhersage-Commit `B{batch}: Vorhersage …`, dann "
            f"{baum}/ bearbeiten. Der geplante Eingriff gehoert mit Soll-Werten in die "
            f"Vorhersage; `{pfad}` wird bis dahin nicht geschrieben. Schreiben unter "
            f"`analysis/` ist frei.")


def _blockieren(grund: str) -> None:
    """PreToolUse-Antwort mit `deny` (Beleg: Hooks-Handbuch, `docs/_r13be_belege.md`)."""
    io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                "permissionDecision": "deny",
                                "permissionDecisionReason": grund}},
        ensure_ascii=False))


def _stdin_json() -> dict:
    """Die Hook-Eingabe lesen (PostToolUse). Leer/kaputt -> `{}`."""
    try:
        roh = sys.stdin.read()
    except Exception:                                                     # noqa: BLE001
        return {}
    if not roh or not roh.strip():
        return {}
    try:
        daten = json.loads(roh)
    except ValueError:
        return {}
    return daten if isinstance(daten, dict) else {}


def _nachrueckliste_offen(lauf: Path | None) -> bool:
    """Steht noch ein OFFENER Posten der NACHRUECKLISTE aus? (R13ao, R13bw-13)

    Frueher wurde nur geprueft, OB der Auftrag einen Abschnitt `NACHRUECKLISTE` hat - den
    traegt aber jeder solche Auftrag, also sperrte der Hook den **ganzen Batch**, obwohl
    `hx/uhr.PREFLIGHT_HINWEIS` dem Worker sagt "Er ist nur zulaessig, wenn alle Posten der
    NACHRUECKLISTE erledigt sind". GEMESSEN (`runs/b282/stream.jsonl:55860`): "The hook
    says the preflight is only allowed after the threshold OR if all nachrueckliste items
    are done - but the block persists until 135 min regardless ... I'm at 63 min -> 72 min
    to wait" und `:55861` "The Nachrueckliste work items are all done. Let me use the wait
    for a genuinely useful, long measurement" -> der Leerlauf wurde mit einem 0->2,7G-Lauf
    gefuellt. Jetzt entscheidet der **Marker** (`worker.nachrueckliste_marker`): liegt er
    vor, ist die Liste erledigt und die Sperre faellt.

    Der Import von `hx.worker`/`hx.util` steht ABSICHTLICH hier drin: er kostet ~0,1 s und
    wird nur gebraucht, wenn wirklich eine dieser Sperren zu pruefen ist.
    """
    if lauf is None:
        return False
    p = Path(lauf) / "auftrag.md"
    if not p.is_file():
        return False
    from hx.util import read_text
    from hx.worker import hat_nachrueckliste, nachrueckliste_marker
    if not hat_nachrueckliste(read_text(p)):
        return False
    return not nachrueckliste_marker(lauf)


def pre_tooluse(eingabe: dict, lauf: "Path | None", state_datei, umschalt) -> int:
    """PreToolUse: den Preflight-Aufruf stoppen, solange er zu frueh kaeme (R13be-2, R13bw-6).

    **Was PreToolUse darf** (Beleg: das Hooks-Handbuch im CLI-Binary,
    `docs/_r13be_belege.md`): Ereignis-Tabelle „PreToolUse - Run before tool, **can
    block**“; Ausgabefelder `hookSpecificOutput.permissionDecision` = „allow“, „deny“
    oder „ask“ und `permissionDecisionReason` (beide **PreToolUse only**). Ein Hinweis
    **ohne** Blockieren ginge ueber `additionalContext`; hier wird bewusst `deny`
    benutzt, damit der Worker vor dem Aufruf anhaelt statt danach.

    Geblockt wird in ZWEI Faellen (die port_suche-Sperre braucht weder Uhr noch Zustand):

    1. **port_suche gekuerzt** (R13bw-11, 07.10.2026): `streamjson.port_suche_kuerzung` -
       ein `port_suche`-Aufruf, der per Pipe gekuerzt wird (`Select-Object -First|-Last`,
       `Select -First|-Last`, `head`, `| more`). Die Port-Fundstellen stehen am ENDE der
       Ausgabe (`AGENTS.md` R13az); gekuerzt sah der Worker sie nie (B289 Befund 4).
    2. **Preflight zu frueh** (R13be-2/R13bw-6), nur wenn ALLE Bedingungen gelten:
      * es ist ein Preflight-**Start** (`streamjson.ist_preflight_aufruf`),
      * die Batch-Uhr steht **vor** der Umschaltschwelle (`uhr.preflight_zu_frueh`),
      * `auftrag.md` traegt eine offene `NACHRUECKLISTE` (`_nachrueckliste_offen`).

    **Die Sperre haelt bis zur Umschaltschwelle (R13bw-6, Auftrag 05.10.2026).** Jeder
    weitere Preflight-Start vor der Schranke wird ERNEUT gestoppt - die Datei ist nur der
    Beleg, kein Einmal-Schalter. Grund (gemessen B271/B273): nach dem ersten Stopp kam der
    zweite Start 28 s bzw. 9 s spaeter und lief ~10 min durch. Ohne Laufverzeichnis oder
    ohne Startzeit im Zustand passiert nichts - der Lauf bleibt unberuehrt.
    """
    from hx import streamjson, uhr
    # R13bw-11: diese Sperre zuerst - sie braucht weder Uhr noch Zustand.
    if streamjson.port_suche_kuerzung(eingabe.get("tool_name"),
                                      eingabe.get("tool_input")):
        if lauf is not None:
            from hx.util import append_jsonl
            append_jsonl(Path(lauf) / PORT_SUCHE_BLOCK_DATEI,
                         {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "grund": "pipe-gekuerzt",
                          "werkzeug": str(eingabe.get("tool_name") or "")})
        _blockieren(PORT_SUCHE_GRUND)
        return 0
    # R13bw-13 (S2): neue Hybrid-Langlaeufe nach dem Erledigt-Marker bzw. im Fenster
    # Schwelle minus `LANGLAUF_VORLAUF_MIN` - kurze Formen bleiben frei.
    skript = streamjson.langlauf_aufruf(eingabe.get("tool_name"),
                                       eingabe.get("tool_input"))
    if skript:
        _langlauf_pruefen(skript, lauf, state_datei, umschalt)
    if not streamjson.ist_preflight_aufruf(eingabe.get("tool_name"),
                                           eingabe.get("tool_input")):
        return 0
    if umschalt is None:
        return 0
    state = uhr.lies_state(state_datei)
    d = uhr.start_zeit(state)
    if d["zeit"] is None:
        return 0
    minuten = max(0.0, (d["alter_s"] or 0) / 60.0)
    if not uhr.preflight_zu_frueh(minuten, umschalt):
        return 0
    if not _nachrueckliste_offen(lauf):
        return 0
    marke = (Path(lauf) / BLOCK_DATEI) if lauf is not None else None
    if marke is not None:
        # R13bw-6: JEDE Wiederholung wird gestoppt und belegt (`versuch` = wievielter
        # Stopp im selben Batch). Vorher liess die blosse Existenz der Datei durch.
        from hx.util import append_jsonl, read_text
        versuch = 1
        if marke.is_file():
            versuch = 1 + sum(1 for z in (read_text(marke) or "").splitlines() if z.strip())
        append_jsonl(marke, {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "min": round(minuten, 1), "umschalt": float(umschalt),
                             "versuch": versuch,
                             "werkzeug": str(eingabe.get("tool_name") or "")})
    # Derselbe Wortlaut wie beim Hinweis NACH dem Aufruf ("PREFLIGHT-HINWEIS: …") plus
    # der Zusatz aus dem Auftrag, damit der Worker den Stopp begruendet beantworten kann.
    grund = ("PREFLIGHT-HINWEIS: " + uhr.preflight_hinweis(minuten, umschalt)
             + " " + BLOCK_ZUSATZ)
    _blockieren(grund)
    return 0


def _uhr_minuten(state_datei, umschalt):
    """Die Batch-Uhr in Minuten und die wirksame Umschaltschwelle (``None, None`` = nichts)."""
    if umschalt is None:
        return None, None
    from hx import uhr
    state = uhr.lies_state(state_datei)
    d = uhr.start_zeit(state)
    if d["zeit"] is None:
        return None, None
    return max(0.0, (d["alter_s"] or 0) / 60.0), float(umschalt)


def _langlauf_pruefen(skript: str, lauf, state_datei, umschalt) -> int:
    """Einen Langlauf-Start stoppen, wenn der Marker steht oder das Fenster erreicht ist (R13bw-13).

    Bedingungen (eine genuegt):
      * **Marker** - `worker.nachrueckliste_marker` nennt eine Quelle (die Nachrueckliste
        ist erledigt; dann gibt es keinen Grund mehr, die Wartezeit zu fuellen), ODER
      * **Fenster** - die Batch-Uhr steht weniger als `LANGLAUF_VORLAUF_MIN` Minuten vor
        der Umschaltschwelle (dann passt der Lauf nicht mehr vor den Preflight; gemessen
        B284: 600M ab Minute 121,8 und 700M ab 129,8 bei Schwelle 135).

    Ohne Uhr und ohne Marker passiert nichts - der Lauf bleibt unberuehrt.
    """
    from hx.worker import nachrueckliste_marker
    marker = nachrueckliste_marker(lauf)
    minuten, schwelle = _uhr_minuten(state_datei, umschalt)
    im_fenster = (minuten is not None and schwelle is not None
                  and minuten >= schwelle - LANGLAUF_VORLAUF_MIN)
    if not marker and not im_fenster:
        return 0
    warum = (f"die Nachrueckliste ist erledigt (Marker in {marker})" if marker
             else f"die Batch-Uhr steht auf {minuten:.0f} min, weniger als "
                  f"{LANGLAUF_VORLAUF_MIN:.0f} min vor der Umschaltschwelle "
                  f"{schwelle:.0f} min")
    if lauf is not None:
        from hx.util import append_jsonl
        append_jsonl(Path(lauf) / LANGLAUF_BLOCK_DATEI,
                     {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "skript": skript, "marker": marker or "",
                      "min": None if minuten is None else round(minuten, 1),
                      "umschalt": schwelle,
                      "werkzeug": "PowerShell"})
    _blockieren("LANGLAUF-HINWEIS: neue Hybrid-Langlaeufe (" + skript + ") sind jetzt nicht "
                "mehr erlaubt - " + warum + ". Kurze Formen mit --schritte unter "
                + f"{streamjson_frei()} Schritten bleiben frei; der Preflight ist erlaubt, "
                "sobald die Nachrueckliste erledigt ist. Belege den Stand im Batch-Dokument.")
    return 0


def streamjson_frei() -> str:
    """Die freie Schrittzahl als Text (fuer den Sperr-Hinweis)."""
    from hx import streamjson
    n = streamjson.LANGLAUF_FREI_SCHRITTE
    return f"{n // 1_000_000}M"


def main(argv: list[str]) -> int:
    if "--state" not in argv:
        return 0
    eingabe = _stdin_json()
    try:
        i = argv.index("--state")
        state_datei = Path(argv[i + 1])
        weich = float(argv[argv.index("--weich") + 1]) if "--weich" in argv else 90.0
        hart = float(argv[argv.index("--hart") + 1]) if "--hart" in argv else 180.0
        # R13ad: die Umschaltschwelle (Alarmgrenze minus `umschalt_vor_alarm_s`, seit
        # R13ae 900 s = 15 min) und die Kontextgrenze kommen aus `harness.toml` und
        # werden vom Harness mitgegeben.
        # R13ah: dazu die gemessene Dauer des letzten Preflight-Aufrufs (`--preflight-min`).
        # R13aj: und der Batch, aus dem sie stammt (`--preflight-batch`) - er kann
        # aelter sein, wenn der neueste Aufruf nur parallel lief.
        # R13ao: `--run` ist das Laufverzeichnis (`runs/b<N>`) - daraus kommen
        # `auftrag.md` (NACHRUECKLISTE) und die Zaehldatei.
        umschalt = (float(argv[argv.index("--umschalt") + 1])
                    if "--umschalt" in argv else None)
        preflight_min = (float(argv[argv.index("--preflight-min") + 1])
                         if "--preflight-min" in argv else None)
        preflight_batch = (int(argv[argv.index("--preflight-batch") + 1])
                           if "--preflight-batch" in argv else None)
        kontext_limit = (int(argv[argv.index("--kontext-limit") + 1])
                         if "--kontext-limit" in argv else None)
        lauf = (Path(argv[argv.index("--run") + 1]) if "--run" in argv else None)
        if "--pre" in argv:
            # R13bl: R391-Sperre zuerst - sie ist der haeufigere Fall. Der schnelle Weg
            # bleibt: nur die drei Datei-Werkzeuge loesen das Lesen des Zustands aus,
            # alle anderen Aufrufe gehen ohne Zustandsdatei durch.
            decomp = (Path(argv[argv.index("--decomp") + 1])
                      if "--decomp" in argv else None)
            if str(eingabe.get("tool_name") or "") in SPERR_VERBEN:
                from hx import uhr as uhr_mod
                grund = r391_grund(eingabe, uhr_mod.lies_state(state_datei), decomp, lauf)
                if grund:
                    _blockieren(grund)
                    return 0
            # R13be-2: VOR dem Werkzeugaufruf pruefen (billigster Fall zuerst: kein
            # Preflight-Aufruf -> sofort raus, ohne den Zustand zu lesen).
            return pre_tooluse(eingabe, lauf, state_datei, umschalt)
        from hx import streamjson, uhr
        state = uhr.lies_state(state_datei)
        d = uhr.start_zeit(state)
        if d["zeit"] is None:
            # Nichts gemessen (kein laufender Batch im Zustand) -> KEINE Zeile. Sonst
            # stuende nach jedem Werkzeugaufruf ein Hinweis ohne Messwert im Kontext.
            return 0
        text = uhr.uhr_text(state, weich, hart, umschalt_min=umschalt,
                            kontext_limit=kontext_limit,
                            preflight_min=preflight_min,
                            preflight_batch=preflight_batch)
        # --- R13ao: Preflight-Aufruf erkennen, zaehlen, ggf. hinweisen ----------------
        if streamjson.ist_preflight_aufruf(eingabe.get("tool_name"),
                                           eingabe.get("tool_input")):
            minuten = max(0.0, (d["alter_s"] or 0) / 60.0)
            frueh = (uhr.preflight_zu_frueh(minuten, umschalt)
                     and _nachrueckliste_offen(lauf))
            if lauf is not None:
                from hx.util import append_jsonl
                append_jsonl(Path(lauf) / ZAHL_DATEI,
                             {"ts": datetime.now(timezone.utc).isoformat(
                                 timespec="seconds"),
                              "min": round(minuten, 1), "frueh": bool(frueh),
                              "werkzeug": str(eingabe.get("tool_name") or "")})
            if frueh:
                text += "\nPREFLIGHT-HINWEIS: " + uhr.preflight_hinweis(minuten, umschalt)
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8").write(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                    "additionalContext": text}},
            ensure_ascii=False))
    except Exception:                                                     # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
