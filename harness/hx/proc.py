"""Prozessstart mit wirklich harten Grenzen.

Lehren aus dem Sandkasten (results-probe.md):
  * stdout des Kindes MUSS als UTF-8 gelesen werden (sonst verstuemmelte Umlaute),
  * `Start-Process -PassThru` liefert ohne -Wait keinen ExitCode -> hier
    subprocess.Popen mit echtem Rueckgabecode,
  * ein Zeitlimit muss den GANZEN Prozessbaum beenden (claude startet Kinder).
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path

from .util import ensure_dir, now_iso


def kill_tree(pid: int) -> None:
    """Beendet den Prozessbaum hart (Windows: taskkill /T)."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=30)
            return
        except Exception:
            pass
    try:
        os.kill(pid, 9)
    except OSError:
        pass


class StreamRun:
    """Ergebnis eines Prozesslaufs."""

    def __init__(self):
        self.rc: int | None = None
        self.duration_s: float = 0.0
        self.killed_reason: str | None = None
        self.lines: int = 0
        self.stdout_path: str | None = None
        self.stderr_path: str | None = None
        self.pid: int | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        # R13j: Wie lange wurde nach dem Kind-Ende auf das Ausgabeende gewartet?
        self.eof_offen_s: float | None = None


def run_stream(cmd: list[str], env: dict, cwd: str, out_path: str | Path,
               on_event=None, hard_wall_s: float | None = None,
               cancel=None, log=None, stdin_text: str | None = None,
               stderr_path: str | Path | None = None, on_start=None,
               eof_gnade_s: float = 60.0) -> StreamRun:
    """Startet den Prozess, liest stdout zeilenweise (UTF-8) und ruft on_event(line).

    on_event(line) darf "kill" zurueckgeben -> Prozessbaum wird beendet und
    killed_reason auf "event" gesetzt. cancel() wird im Sekundentakt gefragt.
    on_start(pid) wird sofort nach dem Start gerufen (fuer den Zustand).

    `eof_gnade_s` (R13j): Ist der Kindprozess beendet, aber die Ausgabe-Pipe meldet
    kein Ende (EOF), obwohl schon so viele Sekunden keine Zeile mehr kam, wird der
    Lauf abgeschlossen. Grund (gemessen 2026-09-26): ein vom Worker gestarteter
    Enkelprozess erbt das Schreibende der Pipe und haelt sie offen, auch wenn der
    Worker fertig ist. Ohne diese Bremse wartet der Harness unbegrenzt - der Batch
    wurde nie abgeschlossen, kein `result.json`, kein Push, kein Review.
    """
    res = StreamRun()
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    if stderr_path is None:
        stderr_path = out_path.with_suffix(out_path.suffix + ".err")
    stderr_path = Path(stderr_path)

    out_fh = open(out_path, "wb")
    err_fh = open(stderr_path, "wb")
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        )
        res.pid = proc.pid
        res.started_at = now_iso()
        res.stdout_path = str(out_path)
        res.stderr_path = str(stderr_path)
        if on_start is not None:
            try:
                on_start(proc.pid)
            except Exception:
                pass

        q: "queue.Queue[bytes | None]" = queue.Queue()

        def reader():
            try:
                for raw in iter(proc.stdout.readline, b""):
                    out_fh.write(raw)
                    out_fh.flush()
                    q.put(raw)
            finally:
                q.put(None)

        def err_reader():
            try:
                for raw in iter(proc.stderr.readline, b""):
                    err_fh.write(raw)
                    err_fh.flush()
            except Exception:
                pass

        threading.Thread(target=reader, daemon=True).start()
        threading.Thread(target=err_reader, daemon=True).start()

        if stdin_text is not None:
            # WICHTIG: in einem eigenen Thread schreiben. Der Pipe-Puffer ist klein
            # (Windows wenige KB); ein 40-kB-Prompt wuerde im Hauptthread blockieren,
            # bevor der Kindprozess liest -> Deadlock.
            def feed_stdin():
                try:
                    proc.stdin.write(stdin_text.encode("utf-8"))
                    proc.stdin.flush()
                except Exception:
                    pass
                finally:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass

            threading.Thread(target=feed_stdin, daemon=True).start()

        start = time.time()
        letzte_zeile = start
        last_cancel_check = 0.0
        drain_deadline = None
        while True:
            try:
                raw = q.get(timeout=0.5)
            except queue.Empty:
                raw = b""
            if raw is None:
                break
            if raw:
                res.lines += 1
                letzte_zeile = time.time()
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                if on_event is not None and not res.killed_reason:
                    try:
                        if on_event(line) == "kill":
                            kill_tree(proc.pid)
                            res.killed_reason = "event"
                            drain_deadline = time.time() + 10
                    except Exception as exc:  # Ereignisfehler darf den Lauf nicht toeten
                        if log:
                            log.warn("on_event-Fehler", err=str(exc)[:120])
            now = time.time()
            if hard_wall_s and not res.killed_reason and (now - start) > hard_wall_s:
                kill_tree(proc.pid)
                res.killed_reason = self_reason = "wall"
                drain_deadline = now + 10
            if cancel is not None and not res.killed_reason and (now - last_cancel_check) > 1.0:
                last_cancel_check = now
                try:
                    if cancel():
                        kill_tree(proc.pid)
                        res.killed_reason = "cancel"
                        drain_deadline = now + 10
                except Exception:
                    pass
            if drain_deadline and time.time() > drain_deadline:
                break
            if (not res.killed_reason and eof_gnade_s and proc.poll() is not None
                    and (now - letzte_zeile) > eof_gnade_s):
                # R13j: Kind fertig, Pipe ohne EOF (Enkelprozess haelt das Handle).
                res.eof_offen_s = round(now - letzte_zeile, 1)
                if log:
                    log.warn("Kind beendet, Ausgabe-Pipe ohne EOF - Lauf wird abgeschlossen",
                             gewartet_s=res.eof_offen_s)
                break

        res.duration_s = round(time.time() - start, 3)
        try:
            res.rc = proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            kill_tree(proc.pid)
            res.rc = proc.wait(timeout=30) if proc.poll() is not None else None
        res.finished_at = now_iso()
        return res
    finally:
        try:
            out_fh.close()
        except Exception:
            pass
        try:
            err_fh.close()
        except Exception:
            pass


def run_capture(cmd: list[str], cwd: str, env: dict | None = None,
                timeout: float = 120.0, text_input: str | None = None) -> tuple[int, str, str]:
    """Einfacher Einmalaufruf (Git, taskkill, Pruefbefehle) mit UTF-8-Ausgabe.

    Ein Zeitlimit bricht IMMER ab und meldet es - ein haengender Aufruf darf den
    Harness nicht stehen lassen (R11-1: git wartete auf Zugangsdaten).
    """
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout,
                           input=text_input.encode("utf-8") if text_input is not None else None)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode("utf-8", errors="replace")
        err = (exc.stderr or b"").decode("utf-8", errors="replace")
        return -9, out, (err + f"\n[ZEITLIMIT {timeout:.0f}s erreicht - Aufruf abgebrochen]").strip()
    except OSError as exc:
        return -1, "", f"[Start fehlgeschlagen: {exc}]"
    return (p.returncode,
            p.stdout.decode("utf-8", errors="replace"),
            p.stderr.decode("utf-8", errors="replace"))
