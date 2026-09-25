"""Queue-Dateien (Abschnitt E): Telegram-Nachrichten ueberleben einen Batch.

Format:  inbox/<ziel>/<YYYY-MM-DD_HHMMSS>_<id>.md  mit Frontmatter
Zustellung: NUR am Batch-Uebergang; danach Verschieben nach inbox/done/.
"""

from __future__ import annotations

import re
from pathlib import Path

from .util import ensure_dir, new_id, now_iso, read_text, write_text_atomic

TARGETS = ("ds", "claude")


class QueueItem:
    def __init__(self, path: Path, meta: dict, body: str):
        self.path = path
        self.meta = meta
        self.body = body

    @property
    def id(self) -> str:
        return str(self.meta.get("id") or self.path.stem)

    @property
    def text(self) -> str:
        return self.body.strip()

    def render(self) -> str:
        return f"[{self.meta.get('ts','?')} | {self.meta.get('source','?')}] {self.text}"


def _parse(path: Path) -> QueueItem:
    raw = read_text(path)
    meta: dict = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            body = parts[2]
    return QueueItem(path, meta, body)


def enqueue(root: str | Path, target: str, text: str, source: str = "telegram",
            user_id: str | None = None) -> Path:
    if target not in TARGETS:
        raise ValueError(f"unbekanntes Ziel: {target}")
    text = (text or "").strip()
    if not text:
        raise ValueError("leere Nachricht")
    folder = ensure_dir(Path(root) / "inbox" / target)
    ts = now_iso()
    mid = new_id()
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", ts.replace(":", "").replace("-", "").replace("T", "_"))[:20]
    p = folder / f"{slug}_{mid}.md"
    body = (f"---\nid: {slug}_{mid}\nts: {ts}\ntarget: {target}\nsource: {source}\n"
            f"user_id: {user_id or ''}\n---\n{text}\n")
    return write_text_atomic(p, body)


def pending(root: str | Path, target: str) -> list[QueueItem]:
    folder = Path(root) / "inbox" / target
    if not folder.is_dir():
        return []
    items = [_parse(p) for p in sorted(folder.glob("*.md"))]
    return sorted(items, key=lambda it: it.meta.get("ts", ""))


def deliver_block(root: str | Path, target: str, delivered_ids: list[str]) -> tuple[str, list[str]]:
    """Baut den Textblock fuer den naechsten Auftrag; gibt (block, ids) zurueck."""
    items = [it for it in pending(root, target) if it.id not in set(delivered_ids or [])]
    if not items:
        return "", []
    lines = ["", "NACHRICHTEN AUS DER QUEUE (vom Nutzer, nicht verhandelbar):"]
    for it in items:
        lines.append(f"- {it.render()}")
    return "\n".join(lines) + "\n", [it.id for it in items]


def archive(root: str | Path, items_ids: list[str], target: str) -> list[str]:
    """Verschiebt zugestellte Dateien nach inbox/done/ (idempotent)."""
    done = ensure_dir(Path(root) / "inbox" / "done")
    moved = []
    folder = Path(root) / "inbox" / target
    for p in sorted(folder.glob("*.md")):
        it = _parse(p)
        if it.id in set(items_ids or []):
            target_path = done / p.name
            try:
                p.replace(target_path)
                moved.append(str(target_path))
            except OSError:
                pass
    return moved
