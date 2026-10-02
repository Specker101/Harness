"""R13bk - PRUEFUNG VOR DEM HOCHLADEN des Harness-Repos (NUR LESEND).

Der Auftrag verlangt sechs Pruefungen vor jedem Push. Dieses Skript fuehrt sie aus
und schreibt EINEN Beleg nach `docs/_r13bk_upload_pruefung.txt`.

GRUNDREGEL: **Es wird nie ein Zugangswert ausgegeben.** Gemeldet werden nur
Art (z. B. "Telegram-Bot-Token"), Datei/Commit/Zeile und - wenn noetig - die
Laenge. Die Werte aus `%USERPROFILE%\\.hx-secrets` werden als Suchmuster benutzt
und selbst nie gedruckt.

Lesend: git-Abfragen, Dateisuche, Regex. Keine Schreiboperation, kein Netz.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"g:/Harness")
BELEG = ROOT / "docs" / "_r13bk_upload_pruefung.txt"

# ------------------------------------------------------------------ Muster
# Telegram-Bot-Token: <8-10 Ziffern>:<35 Zeichen>
PAT_TELEGRAM = r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"
PAT_ANTHROPIC = r"sk-ant-[A-Za-z0-9_\-]{20,}"
PAT_OPENAI = r"\bsk-[A-Za-z0-9]{20,}\b"
PAT_ZUGANG = (r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|bot[_-]?token"
              r"|client[_-]?secret|passw(or)?d|chat[_-]?id|oauth[_-]?token)\b\s*[:=]\s*"
              r"[\"']?([A-Za-z0-9_\-\.:/]{8,})")
PATTERNS = [("Telegram-Bot-Token", PAT_TELEGRAM),
            ("Anthropic-Key (sk-ant-)", PAT_ANTHROPIC),
            ("OpenAI/DeepSeek-artiger Key (sk-)", PAT_OPENAI),
            ("Zugangswort mit Wert (api_key/token/secret/password/chat_id)", PAT_ZUGANG)]

RISIKO_PFADE = ["state/", "runs/", "logs/", "inbox/", "secrets/", "harness/secrets/",
                "backups/", "snapshots/", "sandbox/", ".env", "*.key", "*.pem",
                "*.pfx", "*credentials*", "*_secrets*", "*token*"]
GROSSE_DATEI = 50 * 1024 * 1024          # 50 MB als Meldegrenze
TEXT_ENDUNGEN = {".py", ".md", ".txt", ".json", ".jsonl", ".toml", ".ps1", ".psm1",
                 ".cfg", ".ini", ".yaml", ".yml", ".env", ".key", ".log", ".csv",
                 ".sh", ".bat", ".cmd", ".js", ".ts", ".html", ".xml", ".gitignore",
                 ".gitattributes", ".properties", ".conf"}


def git(*args, cwd=ROOT) -> tuple[int, str]:
    # stdin=DEVNULL ist Pflicht: `git cat-file --batch-check` ohne Eingabe liest
    # stdin und wartet sonst ewig (R13bk: genau das hat den ersten Lauf ab
    # 20:00:48 blockiert - 0,15 s Kernelzeit in 27 Minuten).
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                       stdin=subprocess.DEVNULL,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def schritt(text: str) -> None:
    """Fortschritt nach stderr. Ein haengender Lauf sah sonst aus wie ein
    langsamer (R13bk: 27 Minuten ohne eine Zeile Ausgabe)."""
    print(f"[{datetime.now():%H:%M:%S}] {text}", file=sys.stderr, flush=True)


_TRACKED: set[str] | None = None


def ist_getrackt(rel: str) -> bool:
    """Nur ein Treffer in einer GETRACKTEN Datei geht mit hoch. Ein Treffer im
    ignorierten Laufprotokoll ist ein Hinweis, kein Fund (R13bk: der erste Beleg
    zaehlte beides gleich und kam auf 497 \"Funde\")."""
    global _TRACKED
    if _TRACKED is None:
        _rc, out = git("ls-files")
        _TRACKED = {x for x in out.splitlines() if x.strip()}
    return rel in _TRACKED


def werte_aus_secrets() -> list[tuple[str, str]]:
    """(Quelle, Wert) aus `%USERPROFILE%\\.hx-secrets` - Werte bleiben intern."""
    out: list[tuple[str, str]] = []
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    d = home / ".hx-secrets"
    if not d.is_dir():
        return out
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        try:
            for ln in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
                v = ln.strip()
                if len(v) >= 12 and not v.startswith("#"):
                    out.append((p.name, v))
        except OSError:
            continue
    return out


def main() -> int:
    z: list[str] = []
    funde: list[str] = []      # harte Funde: getrackt oder in der Historie
    weiche: list[str] = []     # Hinweise in ignorierten/untracked Dateien
    needles = werte_aus_secrets()
    z.append("R13bk - Pruefung VOR dem Hochladen des Harness-Repos (nur lesend)")
    z.append(f"Repo: {ROOT}")
    z.append("")

    # ---------------------------------------------------------------- 1. Remote
    schritt("1 Remote")
    z.append("## 1. Remote")
    rc, out = git("remote", "-v")
    z.append(out.strip() or "  (kein Remote eingetragen)")
    rc, out = git("branch", "-vv")
    z.append("  Branch:")
    for ln in out.splitlines():
        z.append("    " + ln.strip())
    z.append("")

    # -------------------------------------------------------- 2. Getrackte Dateien
    rc, tracked = git("ls-files")
    dateien = [d for d in tracked.splitlines() if d.strip()]
    z.append(f"## 2. Getrackte Dateien: {len(dateien)}")
    ordner: dict[str, int] = {}
    for d in dateien:
        top = d.split("/")[0] if "/" in d else "(Wurzel)"
        ordner[top] = ordner.get(top, 0) + 1
    for k in sorted(ordner, key=lambda k: (-ordner[k], k)):
        z.append(f"  {ordner[k]:6d}  {k}")
    z.append("")

    z.append("### 2a. .gitignore-Regeln (Wurzel und harness/)")
    for rel in (".gitignore", "harness/.gitignore"):
        p = ROOT / rel
        if not p.is_file():
            z.append(f"  {rel}: FEHLT")
            continue
        z.append(f"  --- {rel} ---")
        for ln in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
            if ln.strip() and not ln.strip().startswith("#"):
                z.append("    " + ln.rstrip())
    z.append("")

    z.append("### 2b. Getrackte Dateien in Risikobereichen")
    benannt: list[str] = []
    for muster in RISIKO_PFADE:
        rc, out = git("ls-files", "--", muster)
        treffer = [x for x in out.splitlines() if x.strip()]
        if treffer:
            benannt.extend(treffer)
            z.append(f"  {muster}: {len(treffer)} getrackt (Inhalt siehe 2b2)")
            for t in treffer[:20]:
                z.append(f"      {t}")
        else:
            z.append(f"  {muster}: keine getrackten Dateien")
    z.append("")
    z.append("### 2b2. Inhalt der getrackten Dateien mit Risikonamen")
    z.append("  (Ein Name mit `_secrets` ist noch kein Fund - entscheidend ist der Inhalt.)")
    for rel in sorted(set(benannt)):
        p = ROOT / rel
        try:
            txt = io.open(p, encoding="utf-8", errors="replace").read()
        except OSError as e:
            z.append(f"  {rel}: nicht lesbar ({e.__class__.__name__})")
            continue
        hart: list[str] = []
        for art, pat in PATTERNS:
            if re.search(pat, txt):
                hart.append(art)
        for q, v in needles:
            if v in txt:
                hart.append(f"Wert aus .hx-secrets ({q})")
        if hart:
            z.append(f"  {rel}: **TREFFER** {', '.join(sorted(set(hart)))}")
            funde.append(f"GETRACKTE Datei mit Zugangswert: {rel} "
                         f"({', '.join(sorted(set(hart)))}) - Wert NICHT ausgegeben")
        else:
            z.append(f"  {rel}: geprueft - kein Muster, kein Wert aus .hx-secrets")
    z.append("")
    z.append("### 2c. Ignoriert? (Stichprobe je Risikobereich)")
    # Nur Pfade, die es wirklich gibt: `check-ignore` auf einen erfundenen Pfad
    # meldet "NICHT IGNORIERT" und sieht wie eine Luecke aus (R13bk, Lauf 1).
    for probe in ("harness/state/run.json", "harness/runs/b235/stream.jsonl",
                  "harness/runs/b235/review.md", "harness/logs/harness.log",
                  "harness/inbox/x.md", "harness/outbox/x.md",
                  "harness/snapshots/x.zip", "harness/sessions/x.jsonl",
                  "harness/cc-worker/x", "harness/cc-reviewer/x",
                  "harness/tests/_tmp_x/repo/.git/config",
                  "harness/harness.toml", "harness/hx/util.py",
                  "secrets/deepseek.key", "backups/_zugriffsprobe.txt",
                  "sandbox/decomp-link", ".vscode/settings.json",
                  "harness/.env", ".env"):
        if not (ROOT / probe).exists():
            z.append(f"  {probe}: (Pfad gibt es nicht - nicht bewertbar)")
            continue
        rc, out = git("check-ignore", "-v", "--", probe)
        ig = out.strip()
        # Drei Faelle, nicht zwei: "nicht ignoriert" ist fuer eine GETRACKTE Datei
        # die richtige Lage. Gefaehrlich ist nur "nicht ignoriert UND nicht
        # getrackt" - das nimmt `git add .` mit (R13bk, Lauf 2: zwei Fehlalarme).
        if ig:
            z.append(f"  {probe}: ignoriert - {ig}")
        elif ist_getrackt(probe.rstrip("/")):
            z.append(f"  {probe}: nicht ignoriert, aber getrackt - normaler Repo-Inhalt")
        else:
            z.append(f"  {probe}: **nicht ignoriert und NICHT getrackt** - `git add .` "
                     f"wuerde ihn mitnehmen")
            funde.append(f"NICHT IGNORIERT UND NICHT GETRACKT: {probe}")
    z.append("")
    z.append("### 2d. Was `git add -A` mitnehmen wuerde (untracked, nicht ignoriert)")
    rc, out = git("status", "--porcelain", "-uall")
    neu = [ln[3:].strip().strip('"') for ln in out.splitlines() if ln.startswith("?? ")]
    z.append(f"  Dateien: {len(neu)}")
    for rel in sorted(neu):
        p = ROOT / rel
        try:
            n = p.stat().st_size
        except OSError:
            z.append(f"      (nicht lesbar)  {rel}")
            continue
        warn = ""
        if n > 1024 * 1024:
            warn += "  **GROSS (>1 MB)**"
            funde.append(f"UNTRACKED und GROSS: {rel} ({n / 1e6:.1f} MB)")
        if p.suffix.lower() in TEXT_ENDUNGEN and n < 20 * 1024 * 1024:
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                txt = ""
            for art, pat in PATTERNS:
                if re.search(pat, txt):
                    warn += f"  **{art}**"
                    funde.append(f"UNTRACKED mit Zugangsmuster: {rel} ({art})")
            for q, v in needles:
                if v in txt:
                    warn += f"  **Wert aus .hx-secrets ({q})**"
                    funde.append(f"UNTRACKED mit Wert aus .hx-secrets: {rel} ({q}) - "
                                 f"Wert NICHT ausgegeben")
        z.append(f"      {n / 1024:10.1f} KB  {rel}{warn}")
    z.append("")

    # -------------------------------------------------- 3. Verschachtelte Repos
    schritt("3 Verschachtelte Repos / Worktrees / Gitlinks")
    z.append("## 3. Verschachtelte Git-Repos / Worktrees / Gitlinks")
    rc, out = git("ls-files", "-s")
    links = [ln for ln in out.splitlines() if ln.startswith("160000")]
    z.append(f"  Gitlinks (Mode 160000) im Index: {len(links)}")
    for ln in links:
        z.append("    " + ln)
        funde.append("Gitlink (Submodul) im Index: " + ln.split("\t")[-1])
    gm = ROOT / ".gitmodules"
    z.append(f"  .gitmodules: {'vorhanden' if gm.is_file() else 'fehlt'}")
    if gm.is_file():
        for ln in io.open(gm, encoding="utf-8", errors="replace").read().splitlines():
            z.append("    " + ln)
    rc, out = git("worktree", "list")
    z.append("  git worktree list:")
    for ln in out.splitlines():
        z.append("    " + ln.strip())
    gefunden = []
    for wurzel, dirs, files in os.walk(ROOT, followlinks=False):
        if ".git" in dirs and Path(wurzel) != ROOT:
            gefunden.append(Path(wurzel))
            dirs.remove(".git")
        if ".git" in files:                       # Repo-Datei (Worktree/Submodul)
            gefunden.append(Path(wurzel))
        dirs[:] = [d for d in dirs if d != ".git"]
    z.append(f"  Gefundene `.git`-Eintraege unterhalb der Wurzel: {len(gefunden)}")
    for p in gefunden:
        rel = p.relative_to(ROOT).as_posix()
        rc, ig = git("check-ignore", "-v", "--", rel)
        rc2, tr = git("ls-files", "--", rel)
        z.append(f"    {rel}")
        z.append(f"        ignoriert: {ig.strip() or 'NEIN'}")
        z.append(f"        getrackt:  {tr.strip() or 'NEIN (nichts)'}")
        if not ig.strip():
            funde.append(f"NICHT IGNORIERTES verschachteltes Repo: {rel}")
    z.append("")

    # -------------------------------------------------- 4. Zugangsdaten
    schritt("4 Zugangsdaten")
    z.append("## 4. Zugangsdaten")
    z.append(f"  Suchmuster aus %USERPROFILE%\\.hx-secrets: {len(needles)} Wert(e) "
             f"aus {len({q for q, _v in needles})} Datei(en) - Werte werden NICHT ausgegeben.")

    z.append("### 4a. Arbeitsbaum")
    geprueft = 0
    for wurzel, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for name in files:
            p = Path(wurzel) / name
            if p.suffix.lower() not in TEXT_ENDUNGEN:
                continue
            try:
                if p.stat().st_size > 20 * 1024 * 1024:
                    continue
                txt = io.open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            geprueft += 1
            rel = p.relative_to(ROOT).as_posix()
            getrackt = ist_getrackt(rel)
            marke = "[getrackt]" if getrackt else "[ignoriert/untracked]"
            ziel = funde if getrackt else weiche
            for art, pat in PATTERNS:
                for m in re.finditer(pat, txt):
                    zeile = txt[:m.start()].count("\n") + 1
                    ziel.append(f"ARBEITSBAUM {art} in {rel}:{zeile} {marke}")
                    z.append(f"  TREFFER {art}: {rel}:{zeile}"
                             f" (Fundlaenge {len(m.group(0))} Zeichen) {marke}")
            for q, v in needles:
                if v in txt:
                    ziel.append(f"ARBEITSBAUM Wert aus .hx-secrets ({q}) in {rel} {marke}")
                    z.append(f"  TREFFER Wert aus .hx-secrets ({q}): {rel} {marke}")
    z.append(f"  (durchsuchte Textdateien: {geprueft})")

    z.append("### 4b. Historie (alle Commits)")
    rc, revs = git("rev-list", "--all")
    commits = [c for c in revs.splitlines() if c.strip()]
    z.append(f"  Commits in der Historie: {len(commits)}")
    schritt(f"4b Historie: {len(commits)} Commits x {len(PATTERNS)} Muster = "
            f"{len(commits) * len(PATTERNS)} git-grep-Aufrufe")
    for i, rev in enumerate(commits, 1):
        for art, pat in PATTERNS:
            rc, out = git("grep", "-n", "-I", "-E", "-e", pat, rev)
            for ln in out.splitlines():
                if not ln.startswith(rev):
                    continue
                rest = ln[len(rev) + 1:]
                teile = rest.split(":", 2)
                datei = teile[0] if teile else "?"
                nr = teile[1] if len(teile) > 1 else "?"
                kurz = rev[:8]
                funde.append(f"HISTORIE {art} in {datei}:{nr} (Commit {kurz})")
                z.append(f"  TREFFER {art}: {datei}:{nr} (Commit {kurz})")
        if i % 25 == 0:
            z.append(f"    ... {i}/{len(commits)} Commits geprueft")
            schritt(f"4b Historie: {i}/{len(commits)} Commits")
    z.append("")
    z.append("### 4b2. Historie: die WERTE aus .hx-secrets als Suchmuster")
    if not needles:
        z.append("  (keine Werte in %USERPROFILE%\\.hx-secrets gefunden - nichts zu suchen)")
    else:
        # Die Werte werden NICHT als Argument uebergeben: `git grep -e <wert>`
        # schriebe sie in die Kommandozeile und damit in die Prozessliste.
        # Stattdessen jeden Blob ueber seine Objekt-ID holen und im Prozess
        # suchen - gleiche Frage, kein Nebeneffekt.
        rc, out = git("rev-list", "--objects", "--all")
        obj: dict[str, str] = {}
        for ln in out.splitlines():
            teile = ln.split(" ", 1)
            if len(teile) == 2 and re.fullmatch(r"[0-9a-f]{40}", teile[0]):
                obj[teile[0]] = teile[1]
        z.append(f"  Objekte in der Historie (Commits/Baeume/Blobs): {len(obj)}")
        texte: dict[str, bytes] = {}
        for i, oid in enumerate(sorted(obj), 1):
            p = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", oid],
                               capture_output=True, stdin=subprocess.DEVNULL)
            if p.returncode == 0 and p.stdout:
                texte[oid] = p.stdout
            if i % 300 == 0:
                schritt(f"4b2 Blobs: {i}/{len(obj)}")
        z.append(f"  gelesene Blobs: {len(texte)}")
        for q, v in needles:
            vb = v.encode("utf-8", "replace")
            treffer = [(oid, obj.get(oid, "?")) for oid, daten in texte.items()
                       if vb in daten]
            z.append(f"  Wert aus `{q}`: {len(treffer)} Treffer")
            for oid, pfad in treffer[:10]:
                rc2, wo = git("log", "--all", "--oneline", "--find-object=" + oid)
                erste = wo.strip().splitlines()[0] if wo.strip() else "(Commit nicht bestimmbar)"
                z.append(f"      blob {oid[:12]}  Pfad: {pfad}")
                z.append(f"        {erste}")
            if treffer:
                funde.append(f"HISTORIE: Wert aus .hx-secrets (`{q}`) steht in "
                             f"{len(treffer)} Blob(s) - erster blob {treffer[0][0][:12]}, "
                             f"Pfad {treffer[0][1]}")
    z.append("")
    z.append("### 4c. Frueher getrackte Secret-Ordner")
    for pfad in ("secrets/", "harness/secrets/", "backups/", "*.key", "*credentials*"):
        rc, out = git("log", "--all", "--oneline", "--name-only", "--diff-filter=A",
                      "--", pfad)
        treffer = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith(" ")
                   and not re.match(r"^[0-9a-f]{7,} ", ln)]
        z.append(f"  {pfad}: {len(treffer)} jemals hinzugefuegte Datei(en)")
        for t in treffer[:15]:
            z.append("      " + t)
        if treffer:
            funde.append(f"HISTORIE: unter {pfad} wurden Dateien angelegt "
                         f"({len(treffer)}) - Namen siehe Beleg")

    z.append("")
    z.append("### 4d. Fremdwerkzeuge")
    for tool in ("gitleaks", "trufflehog"):
        p = shutil.which(tool)
        z.append(f"  {tool}: {'installiert (' + str(p) + ')' if p else 'nicht installiert'}")
        if p:
            funde.append(f"{tool} ist installiert - Lauf im Beleg nachzuholen")

    # ------------------------------------------------------------ 5. Grosse Dateien
    z.append("")
    schritt("5 Grosse Dateien")
    z.append("## 5. Grosse Dateien (> 50 MB)")
    z.append("### 5a. Arbeitsbaum (ohne .git, ohne Junctions)")
    gross_baum = []
    for wurzel, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            p = Path(wurzel) / name
            try:
                n = p.stat().st_size
            except OSError:
                continue
            if n > GROSSE_DATEI:
                gross_baum.append((n, p.relative_to(ROOT).as_posix()))
    # Nur Dateien zaehlen, die zum Repo gehoeren: `sandbox/` ist ignoriert und
    # liegt auf einer Junction in das Decomp-Repo (R13bk, Lauf 1: 5a listete 81
    # Dateien bis 4 GB aus dem Decomp-Repo, die hier nichts zu suchen haben).
    rels = [rel for _n, rel in gross_baum]
    ignoriert_baum: set[str] = set()
    if rels:
        p = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--stdin"],
                           input="\n".join(rels).encode("utf-8"),
                           capture_output=True)
        ignoriert_baum = {x for x in p.stdout.decode("utf-8", "replace").splitlines()
                          if x.strip()}
    for n, rel in sorted(gross_baum, reverse=True):
        if rel in ignoriert_baum:
            z.append(f"  {n / 1e6:8.1f} MB  {rel}   [ignoriert - nicht Teil des Repos]")
            weiche.append(f"grosse Datei (ignoriert, geht nicht mit hoch): {rel} "
                          f"({n / 1e6:.1f} MB)")
        else:
            z.append(f"  {n / 1e6:8.1f} MB  {rel}   **[GETRACKT/GEFAEHRLICH]**")
            funde.append(f"GROSSE DATEI im Repo: {rel} ({n / 1e6:.1f} MB)")
    if not gross_baum:
        z.append("  keine")
    z.append("### 5b. Historie (alle Blobs)")
    rc, out = git("rev-list", "--objects", "--all")
    objekte = [ln for ln in out.splitlines() if ln.strip()]
    # `--batch-all-objects` liest KEIN stdin - die einzige Variante, die ohne
    # Eingabe nicht blockieren kann. (Der frueher hier stehende Aufruf mit
    # `--buffer` und ohne Eingabe hat den Lauf ab 20:00:48 stumm blockiert.)
    proc = subprocess.run(["git", "-C", str(ROOT), "cat-file", "--batch-check",
                           "--batch-all-objects"], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL,
                          encoding="utf-8", errors="replace")
    gross_hist = []
    for ln in (proc.stdout or "").splitlines():
        teile = ln.split()
        if len(teile) >= 3 and teile[0] == "blob":
            try:
                n = int(teile[2])
            except ValueError:
                continue
            if n > GROSSE_DATEI:
                gross_hist.append((n, teile[1]))
    for n, oid in sorted(gross_hist, reverse=True)[:30]:
        z.append(f"  {n / 1e6:8.1f} MB  blob {oid[:12]}")
        funde.append(f"GROSSER BLOB in der Historie: {oid[:12]} ({n / 1e6:.1f} MB)")
    if not gross_hist:
        z.append("  keine")
    z.append(f"  (Objekte in der Historie: {len(objekte)})")

    # ------------------------------------------------------------ 6. Ergebnis
    z.append("")
    schritt("6 Ergebnis")
    z.append("## 6. Ergebnis")
    z.append(f"  harte Funde (getrackt oder in der Historie): {len(funde)}")
    z.append(f"  Hinweise nur in ignorierten/untracked Dateien: {len(weiche)}")
    z.append("")
    if funde:
        z.append(f"  **{len(funde)} FUND(E)** - vor einem Push klaeren:")
        for f in funde:
            z.append(f"   - {f}")
    else:
        z.append("  **SAUBER** - kein Treffer in getrackten Dateien und in der "
                 "Historie, keine grosse Datei, kein nicht ignoriertes "
                 "verschachteltes Repo.")
    if weiche:
        z.append("")
        z.append(f"  Hinweise (gehen NICHT mit hoch, weil ignoriert/untracked): "
                 f"{len(weiche)}")
        for w in weiche[:15]:
            z.append(f"   - {w}")
        if len(weiche) > 15:
            z.append(f"   - ... und {len(weiche) - 15} weitere")
    text = "\n".join(z) + "\n"
    BELEG.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"Beleg: {BELEG}")
    print(f"Harte Funde: {len(funde)} | Hinweise (ignoriert): {len(weiche)}")
    return 0 if not funde else 2


if __name__ == "__main__":
    raise SystemExit(main())
