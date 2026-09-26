"""Telegram-Bot (Abschnitt I) - Standardbibliothek, Long-Polling, Allowlist.

Sicherheit (Original 17 / E9):
  * Leere Allowlist = der Bot IGNORIERT alles (kein Echo, keine Auskunft).
  * Freitext ist NIE ein Befehl; nur ein fuehrendes "/" wird als Befehl gelesen.
  * Nachrichten an den Worker/Reviewer werden IMMER nur als Queue-Datei abgelegt.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"

# R13l: harte Zeitgrenze statt Vertrauen auf den Socket-Zeitgeber.
#
# MESSUNG 2026-09-27: `urlopen(..., timeout=15)` blieb ueber 17 Minuten in
# `ssl.read` stehen (py-spy-Stack, Prozess-CPU eingefroren) - der Socket-Zeitgeber
# hat den Aufruf NICHT befreit. Ein Aufruf, der einen Harness-Thread festhaelt,
# macht auch `/stop` unwirksam. Deshalb laeuft jeder Telegram-Aufruf in einem
# eigenen Faedchen mit `join(grenze)`: der Aufrufer kommt in JEDEM Fall zurueck.
# Bleibt ein Aufruf haengen, wird sein Faedchen als Daemon aufgegeben - aber nur
# bis zu `MAX_HAENGER` mal, danach wird sofort abgelehnt (kein Aufstau).
#
# MESSUNG 2026-09-27 (laufender Betrieb, Log): ZWEI Haenger binnen 90 s am
# Langpoll (`getUpdates`, Grenze 45 s); der erste Faden war beim zweiten Hänger
# schon von selbst fertig (Log "offen=1"). Die Grenze steht deshalb auf 4 -
# Luft fuer mehrere gleichzeitige Haenger, aber weiterhin klar begrenzt.
MAX_HAENGER = 4
_HAENGER_LOCK = threading.Lock()
_HAENGER: set[threading.Thread] = set()


def haengende_aufrufe() -> int:
    """Wie viele Telegram-Aufrufe gerade ihre harte Zeitgrenze gerissen haben."""
    with _HAENGER_LOCK:
        for faden in [f for f in _HAENGER if not f.is_alive()]:
            _HAENGER.discard(faden)
        return len(_HAENGER)


HELP = (
    "Befehle:\n"
    "/status - Zustand, Batch, Laufzeit, Queue, Kosten\n"
    "/pause - nach dem laufenden Batch anhalten\n"
    "/resume - weiter\n"
    "/stop - laufenden Batch abbrechen (WIP wird gesichert)\n"
    "/approve [Text] - wartenden Batch freigeben\n"
    "/number <N> - Batch-Nummer des offenen Auftrags setzen\n"
    "/autonom - Dauerbetrieb an/aus (ohne Rueckfrage starten)\n"
    "/ds <Text> - Nachricht an den Worker (Queue)\n"
    "/claude <Text> - Nachricht an den Reviewer (Queue)\n"
    "/ask <Frage> - freie Frage an Claude (eigener Lauf, nur lesend)\n"
    "/review - neuer Review jetzt (verwirft einen offenen Auftrag, hebt die Pause auf)\n"
    "/last [ds|claude] [n] - letzten Text zeigen (claude = vollstaendige Instruktion)\n"
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
    def call(self, method: str, params: dict | None = None, timeout: float = 40.0,
             grenze: float | None = None) -> dict:
        """Ein Telegram-Aufruf, der den Aufrufer NIE laenger als `grenze` aufhaelt.

        `timeout` ist das Socket-Zeitlimit (Best-Effort, s. Modulkommentar),
        `grenze` die harte Wanduhr-Grenze (Vorgabe: `timeout` + 5 s).
        """
        if haengende_aufrufe() >= MAX_HAENGER:
            raise TelegramError(
                f"Netz haengt ({MAX_HAENGER} offene Aufrufe) - Aufruf {method} nicht gestartet")
        return self._call_mit_grenze(method, params, timeout,
                                     timeout + 5.0 if grenze is None else grenze)

    def _call_mit_grenze(self, method: str, params: dict | None, timeout: float,
                         grenze: float) -> dict:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params or {}).encode("utf-8")
        box: dict = {}

        def arbeit() -> None:
            try:
                with urllib.request.urlopen(url, data=data, timeout=timeout) as r:
                    box["res"] = json.loads(r.read().decode("utf-8", errors="replace"))
            except BaseException as exc:                    # noqa: BLE001
                box["err"] = exc

        faden = threading.Thread(target=arbeit, name=f"hx-tg-{method}", daemon=True)
        faden.start()
        faden.join(grenze)
        if faden.is_alive():
            # Der Faden laeuft als Daemon weiter und raeumt sich selbst ab; bis dahin
            # zaehlt er gegen das Kontingent, damit sich haengende Aufrufe nicht aufstauen.
            with _HAENGER_LOCK:
                _HAENGER.add(faden)
            offen = haengende_aufrufe()
            if self.log:
                self.log.warn("Telegram haengt", methode=method,
                              grenze=f"{grenze:.0f}s", offen=offen)
            raise TelegramError(
                f"Zeitgrenze hart gerissen ({grenze:.0f} s) - Aufruf {method} laeuft weiter")
        if "err" in box:
            raise TelegramError(str(box["err"])) from box["err"]
        return box.get("res") or {}

    def get_me(self) -> dict:
        return self.call("getMe", {}, timeout=20).get("result", {})

    def get_updates(self, offset: int = 0, timeout: int | None = None) -> list[dict]:
        """`timeout=0` = kurze Abfrage (fuer den laufenden Betrieb), None = Langpoll.

        R13k: Das Zeitlimit ist ABSICHTLICH knapp. Am 2026-09-27 stand der Harness
        ueber 17 Minuten, weil ein `get_updates` (aus dem Mitschnitt-Leser heraus)
        in `urlopen` haengen blieb. Der Netz-Aufruf ist jetzt aus dem Leser verbannt;
        zusaetzlich soll ein haengender Aufruf den Takt-Thread nur kurz kosten.

        R13l: Das Socket-Zeitlimit hat den Aufruf damals NICHT befreit - deshalb gibt
        es zusaetzlich die harte Wanduhr-Grenze in `call`.
        """
        to = timeout if timeout is not None else self.poll_timeout
        # Kurze Abfrage: knapp (der Betrieb wartet darauf). Langpoll: der Server haelt
        # bis `to` Sekunden - die harte Grenze liegt darueber, aber endlich.
        kur = to == 0
        res = self.call("getUpdates", {"offset": offset, "timeout": to,
                                       "allowed_updates": json.dumps(["message"])},
                        timeout=(8.0 if kur else to + 15),
                        grenze=(8.0 if kur else to + 20))
        return res.get("result", [])

    def send(self, text: str, chat_id: str | None = None) -> bool:
        cid = chat_id or self.last_chat_id
        if not cid:
            return False
        ok = True
        for chunk in split_message(text or ""):
            try:
                # R13k: knapp begrenzt - ein Sendeversuch darf keinen Lauf aufhalten
                # (Alarme werden auch aus dem Mitschnitt-Leser heraus gemeldet).
                self.call("sendMessage", {"chat_id": cid, "text": chunk,
                                          "disable_web_page_preview": "true"},
                          timeout=15, grenze=20)
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
    """Telegram-Grenze: Nachrichten ueber 4000 Zeichen werden automatisch geteilt.

    Geteilt wird an Zeilenenden; eine EINZELNE Zeile ueber der Grenze wird hart
    geteilt, sonst wuerde Telegram die Nachricht ablehnen (Instruktionen sind
    lang und enthalten auch lange Zeilen).
    """
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
    out: list[str] = []
    for c in chunks:
        while len(c) > limit:
            out.append(c[:limit])
            c = c[limit:]
        if c:
            out.append(c)
    return out
