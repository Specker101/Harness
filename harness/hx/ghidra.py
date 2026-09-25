"""Ghidra: Erreichbarkeit, Serverstart, Programmwechsel, Projekt-Sicherung.

Wichtig (belegt in analysis/ghidra-mcp-notes.md):
  * Programmwechsel headless: POST /load_program_from_project  +  GET /switch_program
  * /open_program ist GUI-only und wird NIE benutzt (Harness-Sperrliste).
  * Der Server ist ein eigener Prozess; er wird bei Bedarf ueber
    scripts\\start-ghidra-headless.ps1 gestartet (300 s Geduld).
  * Projekt-Sicherung bei laufendem Server: GET /save_all_programs +
    POST /archive_project (HeadlessManagementService.java:353 ff.).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .util import ensure_dir, stamp


class GhidraError(RuntimeError):
    pass


class Ghidra:
    def __init__(self, cfg, log=None):
        self.cfg = cfg
        self.log = log
        self.port = int(cfg.get("ghidra", "port", 8089))
        self.base = f"http://127.0.0.1:{self.port}"

    # ------------------------------------------------------------------ HTTP
    def _get(self, path: str, params: dict | None = None, timeout: float = 20.0) -> dict:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def _post(self, path: str, body: dict, timeout: float = 120.0) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    # ------------------------------------------------------------ Pruefungen
    def reachable(self, timeout: float = 4.0) -> tuple[bool, dict]:
        try:
            meta = self._get("/get_metadata", timeout=timeout)
            return True, meta
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return False, {"error": str(exc)}

    def metadata(self) -> dict:
        return self._get("/get_metadata")

    def current_program(self) -> dict:
        return self._get("/get_current_program_info")

    def open_programs(self) -> list[dict]:
        data = self._get("/list_open_programs")
        progs = data.get("programs") or data.get("open_programs") or []
        if isinstance(progs, dict):
            progs = list(progs.values())
        return progs

    @staticmethod
    def _basename(path: str) -> str:
        return str(path).lstrip("/").split("/")[-1]

    def current_name(self) -> str | None:
        try:
            info = self.current_program()
        except Exception:
            return None
        for key in ("program", "program_name", "name", "current_program"):
            v = info.get(key)
            if isinstance(v, str) and v:
                return self._basename(v)
        return None

    # ------------------------------------------------------------ Serverstart
    def ensure_server(self, log=None, timeout_s: float | None = None) -> bool:
        log = log or self.log
        ok, _ = self.reachable()
        if ok:
            return True
        script = Path(self.cfg.get("ghidra", "server_script"))
        if not script.is_file():
            if log:
                log.error("Startskript fehlt", pfad=str(script))
            return False
        if log:
            log.info("Ghidra-Server antwortet nicht - starte Headless-Server", skript=script.name)
        import subprocess
        logdir = ensure_dir(Path(self.cfg.root) / "logs")
        out = open(logdir / f"ghidra-headless-{stamp(True)}.out.log", "wb")
        err = open(logdir / f"ghidra-headless-{stamp(True)}.err.log", "wb")
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(script)], stdout=out, stderr=err,
                         stdin=subprocess.DEVNULL, creationflags=0x08000000)  # CREATE_NO_WINDOW
        deadline = time.time() + float(timeout_s or self.cfg.get("ghidra", "start_timeout_s", 300))
        while time.time() < deadline:
            time.sleep(3)
            ok, _ = self.reachable()
            if ok:
                if log:
                    log.info("Ghidra-Server erreichbar")
                return True
        if log:
            log.error("Ghidra-Server wurde nicht erreichbar", timeout_s=int(timeout_s or 300))
        return False

    # -------------------------------------------------------- Programmwechsel
    def ensure_program(self, wanted: str, log=None) -> dict:
        """Sorgt dafuer, dass genau `wanted` das aktuelle Programm ist (E7).

        Rueckgabe: {"ok":bool, "steps":[...], "current":str, "base":str}
        """
        log = log or self.log
        wanted_name = self._basename(wanted)
        steps: list[str] = []

        progs = self.open_programs()
        names = {self._basename(p.get("path", "")) for p in progs}
        steps.append(f"offen: {sorted(n for n in names if n)}")
        if wanted_name not in names:
            res = self._post("/load_program_from_project", {"path": "/" + wanted_name})
            steps.append(f"load_program_from_project -> {json.dumps(res)[:200]}")
            if not res.get("success", False):
                return {"ok": False, "steps": steps, "current": None, "error": res}
            progs = self.open_programs()
            names = {self._basename(p.get("path", "")) for p in progs}
            steps.append(f"offen jetzt: {sorted(n for n in names if n)}")

        cur = self.current_name()
        if cur != wanted_name:
            res = self._get("/switch_program", {"program": wanted_name})
            steps.append(f"switch_program({wanted_name}) -> {json.dumps(res)[:200]}")
            cur = self.current_name()
        steps.append(f"current jetzt: {cur}")

        ok = (cur is not None and cur.lower() == wanted_name.lower())
        if not ok and log:
            log.error("Programmwechsel fehlgeschlagen", gewuenscht=wanted_name, ist=cur)
        return {"ok": ok, "steps": steps, "current": cur}

    # ------------------------------------------------------- Projekt-Sicherung
    def save_all_programs(self) -> dict:
        return self._get("/save_all_programs", timeout=120.0)

    def archive_project(self, out_dir: str, out_name: str = "") -> dict:
        return self._post("/archive_project",
                          {"output_dir": out_dir, "output_name": out_name})

    def backup_project(self, log=None, reason: str = "") -> dict:
        """Sichert das Ghidra-Projekt bei LAUFENDEM Server (R7 / J4).

        Rueckgabe: {"ok":bool, "path":str, "size":int, "steps":[...]}
        """
        log = log or self.log
        out_dir = Path(self.cfg.get("ghidra", "backup_dir", str(Path(self.cfg.backups_dir) / "ghidra")))
        ensure_dir(out_dir)
        name = f"sscope-uad_{stamp(True)}"
        steps = []
        try:
            self.save_all_programs()
            steps.append("save_all_programs ok")
        except Exception as exc:
            steps.append(f"save_all_programs FEHLER: {exc}")
        try:
            res = self.archive_project(str(out_dir), name)
        except Exception as exc:
            if log:
                log.error("archive_project fehlgeschlagen", fehler=str(exc)[:200], grund=reason)
            return {"ok": False, "path": "", "size": 0, "steps": steps + [f"archive_project FEHLER: {exc}"]}
        steps.append(f"archive_project -> {json.dumps(res)[:300]}")
        ok = bool(res.get("success"))
        path = str(res.get("path") or "")
        size = int(res.get("size_bytes") or 0)
        if log:
            (log.info if ok else log.error)("Ghidra-Projekt gesichert" if ok else "Ghidra-Sicherung fehlgeschlagen",
                                            pfad=path, bytes=size, grund=reason)
        if ok:
            self._rotate_backups(out_dir, log)
        return {"ok": ok, "path": path, "size": size, "steps": steps}

    def _rotate_backups(self, out_dir: Path, log=None) -> None:
        keep = int(self.cfg.get("ghidra", "backup_keep", 5))
        files = sorted(out_dir.glob("sscope-uad_*.gar"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep:]:
            try:
                old.unlink()
                if log:
                    log.info("altes Ghidra-Backup entfernt", datei=old.name)
            except OSError:
                pass
