"""Git-Werkzeuge des Harness (R9): fetch, Divergenz, Checkpoint, WIP, Push.

Regel: der Harness arbeitet auf `main` und pusht nach jedem Batch. Vor jedem
Batch wird `git fetch` gemacht; weicht origin ab -> Pause + Telegram, KEIN Merge.
Niemals `git add -A`: das Projekt hat untracked Belegordner.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import envs
from .proc import run_capture
from .util import ensure_dir, write_text_atomic

# Git NIE interaktiv: ohne das wartete ein Push auf Zugangsdaten und der Harness
# stand still (R11-1, gemessen an B159). Der Credential Manager darf dabei ruhig
# weiterhelfen - nur eben ohne Fenster und ohne Konsoleneingabe.
GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GCM_INTERACTIVE": "never",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes",
    "GIT_PAGER": "cat",
    "GIT_OPTIONAL_LOCKS": "0",
    "LC_ALL": "C",
}


class GitError(RuntimeError):
    pass


class Git:
    def __init__(self, cfg, log=None):
        self.cfg = cfg
        self.repo = str(cfg.decomp)
        self.branch = str(cfg.get("git", "branch", "main"))
        self.remote = str(cfg.get("git", "remote", "origin"))
        self.log = log
        self.timeout = float(cfg.get("git", "timeout_s", 120))
        self.push_timeout = float(cfg.get("git", "push_timeout_s", 180))
        self.fetch_timeout = float(cfg.get("git", "fetch_timeout_s", 180))

    # ----------------------------------------------------------------- Basis
    def run(self, *args: str, timeout: float | None = None) -> tuple[int, str, str]:
        env = envs.base_env(os.environ)
        env.update(GIT_ENV)
        return run_capture(["git", *args], cwd=self.repo,
                           timeout=self.timeout if timeout is None else timeout, env=env)

    def out(self, *args: str, timeout: float | None = None) -> str:
        rc, so, se = self.run(*args, timeout=timeout)
        if rc != 0:
            raise GitError(f"git {' '.join(args)} -> rc={rc}: {se.strip()[:300]}")
        return so.strip()

    def status_porcelain(self) -> list[str]:
        rc, so, _se = self.run("status", "--porcelain")
        return [ln for ln in so.splitlines() if ln.strip()]

    def head(self) -> str:
        return self.out("rev-parse", "HEAD")

    def head_short(self) -> str:
        return self.out("rev-parse", "--short", "HEAD")

    def head_subject(self) -> str:
        return self.out("log", "-1", "--pretty=%s")

    def recent_commits(self, n: int = 5) -> list[str]:
        try:
            return self.out("log", f"-{n}", "--pretty=%h %s").splitlines()
        except GitError:
            return []

    # -------------------------------------------------------------- Fetch/Sync
    def fetch(self) -> tuple[bool, str]:
        rc, so, se = self.run("fetch", self.remote, self.branch, timeout=self.fetch_timeout)
        if rc != 0:
            return False, (se.strip() or so.strip())[:400]
        return True, ""

    def divergence(self) -> dict:
        """Vergleicht HEAD mit origin/<branch>."""
        local = self.head()
        try:
            remote = self.out("rev-parse", f"{self.remote}/{self.branch}")
        except GitError as exc:
            return {"ok": False, "error": str(exc), "local": local, "remote": None}
        counts = self.out("rev-list", "--left-right", "--count",
                          f"{self.remote}/{self.branch}...HEAD")
        behind, ahead = (int(x) for x in counts.split())
        return {"ok": True, "local": local, "remote": remote,
                "same": local == remote, "behind": behind, "ahead": ahead}

    def push(self) -> tuple[bool, str]:
        """Push mit Zeitlimit - nie interaktiv, nie haengend (R11-1)."""
        rc, so, se = self.run("push", "--porcelain", self.remote, self.branch,
                              timeout=self.push_timeout)
        text = (se or so).strip()[:600]
        if rc != 0:
            return False, text
        return True, text

    # -------------------------------------------------------------- Checkpoint
    def checkpoint(self, batch: int) -> str:
        """Leichtes lokales Tag als Fangpunkt vor dem Batch (wird NICHT gepusht)."""
        tag = f"harness/b{batch}-start"
        rc, so, _se = self.run("rev-parse", "--verify", "-q", f"refs/tags/{tag}")
        if rc == 0:
            return tag
        rc, _so, se = self.run("tag", tag)
        if rc != 0 and self.log:
            self.log.warn("Checkpoint-Tag fehlgeschlagen", tag=tag, fehler=se.strip()[:200])
        return tag

    # --------------------------------------------------- Verlauf seit Checkpoint
    def has_ref(self, ref: str) -> bool:
        rc, _so, _se = self.run("rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        return rc == 0

    def log_since(self, ref: str, n: int = 15) -> list[str]:
        if not self.has_ref(ref):
            return [f"(Checkpoint {ref} existiert nicht - Batch lief ohne Checkpoint)"]
        try:
            return self.out("log", f"--max-count={n}", "--pretty=%h %ad %s",
                            "--date=short", f"{ref}..HEAD").splitlines()
        except GitError as exc:
            return [f"(nicht ermittelbar: {exc})"]

    def diffstat_since(self, ref: str) -> str:
        if not self.has_ref(ref):
            return f"(Checkpoint {ref} existiert nicht - Batch lief ohne Checkpoint)"
        try:
            return self.out("diff", "--stat", f"{ref}..HEAD").strip() or "(keine Änderungen)"
        except GitError as exc:
            return f"(nicht ermittelbar: {exc})"

    def name_status_since(self, ref: str, limit: int = 80) -> list[str]:
        if not self.has_ref(ref):
            return []
        try:
            return self.out("diff", "--name-status", f"{ref}..HEAD").splitlines()[:limit]
        except GitError:
            return []

    def commits_since(self, ref: str) -> int:
        if not self.has_ref(ref):
            return 0
        try:
            return int(self.out("rev-list", "--count", f"{ref}..HEAD") or 0)
        except (GitError, ValueError):
            return 0

    # --------------------------------------------------------------- WIP-Rettung
    def wip_rescue(self, batch: int, log_dir: str | Path) -> dict:
        """Sichert unfertige Arbeit VOR dem Beenden (E6/J2).

        Es wird KEIN add -A gemacht. Gesichert werden:
          1. `git status --porcelain`          (Liste)
          2. `git diff HEAD`                   (Patchdatei)
          3. optional `git stash push -m ...`  (nur wenn konfiguriert)
        """
        res = {"dirty": False, "status": [], "patch": "", "stash": None}
        status = self.status_porcelain()
        res["status"] = status
        res["dirty"] = bool(status)
        if not status:
            return res
        out_dir = Path(log_dir)
        ensure_dir(out_dir)
        write_text_atomic(out_dir / f"wip-b{batch}-status.txt", "\n".join(status) + "\n")
        rc, diff, _se = self.run("diff", "HEAD")
        if rc == 0 and diff:
            p = write_text_atomic(out_dir / f"wip-b{batch}.patch", diff)
            res["patch"] = str(p)
        if self.cfg.get("git", "wip_stash", True):
            rc, so, se = self.run("stash", "push", "-m", f"harness-wip-b{batch}")
            if rc == 0:
                res["stash"] = (so or se).strip()[:200]
                if self.log:
                    self.log.info("WIP im Stash gesichert", batch=batch)
        return res
