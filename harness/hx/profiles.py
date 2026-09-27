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


# --------------------------------------------- Nur-Lese-Git fuer den Reviewer (R13p)
# Ausgangslage: Der Reviewer hatte KEINE Shell und konnte `git log` nicht selbst
# fahren - er sah nur, was im Prompt stand. Doku (code.claude.com/docs/en/permissions):
#   * Regelform `Tool(spezifizierer)`; `*` steht fuer beliebigen Text, `:*` ist die
#     gleichwertige Schreibweise fuer ein abschliessendes ` *`,
#   * das `*` MUSS nach dem Unterbefehl stehen: `Bash(git log *)` erlaubt nur `git log`,
#     `Bash(git *)` dagegen JEDEN git-Befehl,
#   * Deny schlaegt Allow (Reihenfolge: deny, ask, allow) - ein breites Verbot laesst
#     sich nicht durch ein engeres Allow aufweichen,
#   * im `-p`-Lauf gibt es keine Rueckfrage: jeder Aufruf OHNE Allow-Regel wird
#     abgelehnt (genau darauf beruht schon die Pfadbindung von `Read`),
#   * `PowerShell`-Regeln: die CLI parst den AST, normalisiert Aliase (`gci` = `dir` =
#     `ls` = `Get-ChildItem`) und verlangt, dass JEDE Teil-Anweisung passt.
# Deshalb ist der Werkzeugsatz eine ERLAUBNISLISTE: die Shell darf genau vier
# Git-Unterbefehle, alles andere (auch Lesen mit `Get-Content`) ist ausdruecklich zu.
NUR_LESE_GIT = ("log", "show", "diff", "status")

GIT_SCHREIBEND = ("add", "am", "apply", "archive", "bisect", "branch", "bundle",
                  "checkout", "cherry-pick", "clean", "commit", "config", "credential",
                  "daemon", "fetch", "filter-branch", "format-patch", "gc", "init",
                  "instaweb", "lfs", "maintenance", "merge", "mergetool", "mv", "notes",
                  "pack-refs", "prune", "pull", "push", "rebase", "reflog", "remote",
                  "repack", "replace", "request-pull", "reset", "restore", "revert", "rm",
                  "send-email", "sparse-checkout", "stash", "submodule", "switch", "tag",
                  "update-index", "update-ref", "worktree")

# Die Shell ist NUR fuer Git da. Alles, was sonst Dateien liest, schreibt oder startet,
# wird verboten - damit ein Modell nicht ueber `Get-Content` an den Schluesselordner
# kommt (der Read-Bann greift bei Shell-Befehlen nur teilweise) und nicht ueber
# `Invoke-Expression` ausbricht.
SHELL_FREMD_VERBOTEN = ("Get-Content", "Get-ChildItem", "Get-Item", "Get-ItemProperty",
                        "Get-Acl", "Get-FileHash", "Select-String", "Select-Object",
                        "Import-Csv", "Import-Module", "Import-Clixml", "Export-Csv",
                        "Out-File", "Set-Content", "Add-Content", "New-Item", "New-ItemProperty",
                        "Set-ItemProperty", "Set-ExecutionPolicy", "Remove-Item",
                        "Remove-ItemProperty", "Move-Item", "Copy-Item", "Rename-Item",
                        "Start-Process", "Start-Job", "Stop-Process", "Invoke-Expression",
                        "Invoke-Command", "Invoke-WebRequest", "Invoke-RestMethod",
                        "Register-ScheduledTask", "New-Service", "Clear-Content",
                        "cmd", "powershell", "pwsh", "wsl", "bash", "sh", "python", "python3",
                        "node", "curl", "wget", "ssh", "scp", "tar", "reg", "net", "schtasks",
                        "wmic", "robocopy", "xcopy", "del", "rmdir", "md", "echo")


def nur_lese_git_regeln(tool: str = "PowerShell") -> list[str]:
    """Erlaubnisse: genau `git log`, `git show`, `git diff`, `git status`."""
    return [f"{tool}(git {v} *)" for v in NUR_LESE_GIT]


def git_schreib_verbote(tool: str = "PowerShell") -> list[str]:
    """Die schreibenden Gegenstuecke ausdruecklich verbieten (Guertel und Hosentraeger).

    Die Allowlisten oben sind die eigentliche Grenze; diese Verbote fangen den Fall ab,
    dass eine Allow-Regel weiter greift als beabsichtigt. `--output` legen Dateien an,
    deshalb sind die Ausgabe-Schalter der vier erlaubten Befehle eigens verboten.
    """
    regeln: list[str] = []
    for v in GIT_SCHREIBEND:
        regeln += [f"{tool}(git {v} *)", f"{tool}(git {v}*)"]
    for v in NUR_LESE_GIT:
        # `--output` legen Dateien an - die vier erlaubten Befehle sind sonst rein lesend.
        regeln += [f"{tool}(git {v}*--output*)", f"{tool}(git {v}*--output *)"]
    for c in SHELL_FREMD_VERBOTEN:
        regeln += [f"{tool}({c} *)", f"{tool}({c}*)"]
    return list(dict.fromkeys(regeln))


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
