"""Werkzeugprofile (E4/R7b): Built-ins fest, Ghidra-Profil steuert nur MCP.

Die Profildateien liegen in <root>/profiles/*.json und werden von
tools/make_profiles.py aus dem Werkzeugkatalog (_ghidra_schema.json) erzeugt
und danach von Hand geprueft.
"""

from __future__ import annotations

import json
from pathlib import Path

# Built-ins: der Worker darf IMMER Dateien bearbeiten, Git und PowerShell nutzen,
# unabhaengig vom Ghidra-Profil (Entscheidung R7b). Ohne sie kein Port-Batch.
BUILTIN_WORKER = ["Read", "Write", "Edit", "Glob", "Grep", "PowerShell"]
BUILTIN_REVIEWER = ["Read", "Grep", "Glob"]

# Immer gesperrt - auch in "full" (run_ghidra_script/run_script_inline = beliebige
# Codeausfuehrung in Ghidra, Debugger sprechen einen fremden Prozess).
NEVER_ALLOW = [
    "run_ghidra_script",
    "run_script_inline",
]

PROFILES = ("none", "ghidra-read", "ghidra-standard", "ghidra-full")


class ProfileError(RuntimeError):
    pass


class Profile:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    # ------------------------------------------------------------- Zugriff
    @property
    def name(self) -> str:
        return self.data.get("name", "?")

    @property
    def mcp(self) -> bool:
        return bool(self.data.get("mcp", False))

    @property
    def groups(self) -> str:
        return self.data.get("groups", "")

    @property
    def allowed(self) -> list[str]:
        return list(self.data.get("allowed") or [])

    @property
    def denied(self) -> list[str]:
        return list(self.data.get("denied") or [])

    @property
    def writes_ghidra(self) -> bool:
        """True, wenn dieses Profil in die Ghidra-DB schreiben kann (Backup-Pflicht)."""
        return bool(self.data.get("writes_ghidra", False))

    def mcp_names(self, server: str = "ghidra") -> list[str]:
        return [f"mcp__{server}__{n}" for n in self.allowed]

    def mcp_denied_names(self, server: str = "ghidra") -> list[str]:
        return [f"mcp__{server}__{n}" for n in self.denied]

    def summary(self) -> str:
        if not self.mcp:
            return "kein MCP-Server"
        return f"{len(self.allowed)} MCP-Werkzeuge erlaubt, {len(self.denied)} gesperrt, Gruppen={self.groups}"


def load_profile(root: str | Path, name: str) -> Profile:
    if name not in PROFILES:
        raise ProfileError(f"unbekanntes Profil: {name}")
    p = Path(root) / "profiles" / f"{name}.json"
    if not p.is_file():
        raise ProfileError(f"Profildatei fehlt: {p} (tools/make_profiles.py fahren)")
    return Profile(json.loads(p.read_text(encoding="utf-8")), p)


def builtin_args(role: str) -> tuple[str, list[str]]:
    """( --tools-Wert, --allowedTools-Grundliste ) fuer Worker oder Reviewer."""
    names = BUILTIN_WORKER if role == "worker" else BUILTIN_REVIEWER
    return ",".join(names), list(names)


# --------------------------------------------------- pfadgebundene Leseregeln
# GEMESSEN 2026-09-26 (docs/_ask_zugriff_regeln.txt): ein blosses
# `--allowedTools Read` erlaubt das Werkzeug OHNE Pfadbeschraenkung - damit war
# `g:\Harness\secrets\deepseek.key` fuer Reviewer UND Worker lesbar. Wirksam ist
# nur die gebundene Form `Read(//<pfad>/**)` (CLI-Hilfe: 'Bash(git *)').
LESE_ROLLEN = ("Read", "Grep", "Glob")


def pfad_regeln(wurzeln, rollen: tuple[str, ...] = LESE_ROLLEN) -> list[str]:
    """`Read(//g:/Harness/harness/**)` usw. fuer jede Wurzel und jede Rolle."""
    regeln: list[str] = []
    for w in wurzeln:
        p = str(w).replace("\\", "/").rstrip("/")
        regeln += [f"{rolle}(//{p}/**)" for rolle in rollen]
    return regeln


def secrets_verbote(*dirs, rollen: tuple[str, ...] = LESE_ROLLEN) -> list[str]:
    """Ausdrueckliches Verbot fuer Ordner, die NIE gelesen werden (Guertel+Hosentraeger).

    Mehrere Ordner sind moeglich: seit dem Umzug (2026-09-26) wird auch der ALTE
    Ort der Schluessel weiter verboten, damit ein Modell dort gar nicht erst sucht.
    Seit R13o kommt der Backup-Ordner dazu (die Ghidra-Sicherungen gehen niemanden
    etwas an, und ein 14-MB-.gar bringt ein Lesewerkzeug nur zum Anschlag).
    Das Verbot greift auch dann, wenn irgendwo versehentlich ein ungebundenes
    `Read` in der Erlaubnisliste steht.
    """
    regeln: list[str] = []
    for d in dirs:
        if not d:
            continue
        s = str(d).replace("\\", "/").rstrip("/")
        regeln += [f"{rolle}(//{s}/**)" for rolle in rollen]
        regeln += [f"{rolle}({s}/**)" for rolle in rollen]
    return regeln


# R13o: Zugangsdateien, die in KEINER Wurzel gelesen werden duerfen. Claude Code legt
# die Abo-Zugangsdaten als `.credentials.json` im jeweiligen CLAUDE_CONFIG_DIR ab -
# hier `harness/cc-reviewer/`. Ohne dieses Verbot koennte ein Lese-Lauf den Token des
# eigenen Kontos oeffnen und zitieren.
CREDENTIAL_NAMEN = (".credentials.json",)


def credential_verbote(wurzeln, rollen: tuple[str, ...] = LESE_ROLLEN) -> list[str]:
    """Verbot fuer Zugangsdateien unter jeder Wurzel - in allen Schreibweisen.

    Drei Fassungen je Wurzel, weil die Trefferregel der CLI nicht dokumentiert ist:
    `**/<name>` (auch direkt in der Wurzel), `*/<name>` (eine Ebene tiefer) und die
    beiden konkreten Konfigurationsordner, die der Harness selbst setzt.
    """
    regeln: list[str] = []
    for w in wurzeln:
        if not w:
            continue
        p = str(w).replace("\\", "/").rstrip("/")
        for name in CREDENTIAL_NAMEN:
            # `**/<name>` deckt auch die Wurzel selbst ab, `*/<name>` eine Ebene tiefer,
            # dazu die beiden Konfigurationsordner, die der Harness selbst setzt.
            for muster in (f"//{p}/**/{name}", f"//{p}/{name}", f"//{p}/*/{name}"):
                regeln += [f"{rolle}({muster})" for rolle in rollen]
            for ordner in ("cc-worker", "cc-reviewer"):
                regeln += [f"{rolle}(//{p}/{ordner}/{name})" for rolle in rollen]
            # Zweite Schreibweise ohne fuehrende Doppelstriche (wie bei secrets).
            regeln += [f"{rolle}({p}/**/{name})" for rolle in rollen]
    return list(dict.fromkeys(regeln))
