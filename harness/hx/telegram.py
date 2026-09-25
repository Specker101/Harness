"""Telegram-Bot (Abschnitt I) - Standardbibliothek, Long-Polling, Allowlist.

Sicherheit (Original 17 / E9):
  * Leere Allowlist = der Bot IGNORIERT alles (kein Echo, keine Auskunft).
  * Freitext ist NIE ein Befehl; nur ein fuehrendes "/" wird als Befehl gelesen.
  * Nachrichten an den Worker/Reviewer werden IMMER nur als Queue-Datei abgelegt.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"

HELP = (
    "Befehle:\n"
    "/status - Zustand, Batch, Laufzeit, Queue, Kosten\n"
    "/pause - nach dem laufenden Batch anhalten\n"
    "/resume - weiter\n"
    "/stop - laufenden Batch abbrechen (WIP wird gesichert)\n"
    "/approve [Text] - wartenden Batch freigeben\n"
    "/autonom - Dauerbetrieb an/aus (ohne Rueckfrage starten)\n"
    "/ds <Text> - Nachricht an den Worker (Queue)\n"
    "/claude <Text> - Nachricht an den Reviewer (Queue)\n"
    "/review - Review jetzt anstossen\n"
    "/last [ds|claude] [n] - letzten Text zeigen\n"
    "/budget - Kosten und Grenzen\n"
    "/queue - offene Nachrichten\n"
    "/why - letzte Reviewer-Entscheidung\n"
    "/help - diese Liste"
)


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, allowlist: list[str] | None = None, poll_timeout: int = 25,
                 log=None, read_only: bool = False):
        self.token = token
        self.allowlist = [str(x) for x in (allowlist or [])]
        self.poll_timeout = poll_timeout
        self.log = log
        self.read_only = read_only
        # Bei genau einem freigegebenen Nutzer ist das Ziel bekannt (Direktchat):
        # sonst koennte der Harness beim Start nicht von sich aus melden.
        self.last_chat_id: str | None = self.allowlist[0] if len(self.allowlist) == 1 else None

    # ------------------------------------------------------------------- API
    def call(self, method: str, params: dict | None = None, timeout: float = 40.0) -> dict:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        try:
            with urllib.request.urlopen(url, data=data, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            raise TelegramError(str(exc)) from exc

    def get_me(self) -> dict:
        return self.call("getMe", {}, timeout=20).get("result", {})

    def get_updates(self, offset: int = 0, timeout: int | None = None) -> list[dict]:
        to = timeout if timeout is not None else self.poll_timeout
        res = self.call("getUpdates", {"offset": offset, "timeout": to,
                                       "allowed_updates": json.dumps(["message"])},
                        timeout=to + 15)
        return res.get("result", [])

    def send(self, text: str, chat_id: str | None = None) -> bool:
        cid = chat_id or self.last_chat_id
        if not cid:
            return False
        ok = True
        for chunk in split_message(text or ""):
            try:
                self.call("sendMessage", {"chat_id": cid, "text": chunk,
                                          "disable_web_page_preview": "true"}, timeout=30)
            except TelegramError as exc:
                ok = False
                if self.log:
                    self.log.warn("Telegram senden fehlgeschlagen", fehler=str(exc)[:120])
        return ok

    # ------------------------------------------------------------- Allowlist
    def is_allowed(self, user_id) -> bool:
        return bool(self.allowlist) and str(user_id) in self.allowlist

    # --------------------------------------------------------------- Abfragen
    def probe_senders(self, limit: int = 20) -> list[dict]:
        """Liest die Absender der letzten /start-Nachrichten (fuer die Freigabe)."""
        out = []
        try:
            updates = self.get_updates(offset=0, timeout=0)
        except TelegramError:
            return out
        for u in updates[-limit:]:
            msg = u.get("message") or {}
            frm = msg.get("from") or {}
            chat = msg.get("chat") or {}
            if not frm.get("id"):
                continue
            out.append({
                "user_id": str(frm.get("id")),
                "username": frm.get("username") or "",
                "first_name": frm.get("first_name") or "",
                "chat_id": str(chat.get("id") or frm.get("id")),
                "text": (msg.get("text") or "")[:40],
            })
        # Duplikate (mehrere Nachrichten desselben Nutzers) zusammenfassen
        uniq: dict[str, dict] = {}
        for o in out:
            uniq[o["user_id"]] = o
        return list(uniq.values())


def split_message(text: str, limit: int = 4000) -> list[str]:
    """Telegram-Grenze: Nachrichten ueber 4000 Zeichen werden automatisch geteilt."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > limit:
            chunks.append(cur)
            cur = ""
        cur += line
    if cur:
        chunks.append(cur)
    return chunks
