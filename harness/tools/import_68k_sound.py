#!/usr/bin/env python
"""Einmaliger Ghidra-Import des 68K-Soundprogramms (Harness-Verwaltungsschritt).

NICHT fuer den Worker: `load_program` bleibt in allen Profilen gesperrt. Dieses
Werkzeug laeuft auf der Harness-Seite und nutzt dieselbe Ghidra-Schnittstelle
(`hx.ghidra`), die auch der Programmwechsel am Batch-Rand benutzt.

Quelle der Parameter (Fundstellen):
  analysis/_memory/audio-subsystem.md, Abschnitt "B167 ... Import-Rezept":
    Bild   build/m68k/830a08.7s.img   (wortgetauscht, `Bild[i] = Datei[i^1]`)
    Sprache 68000:BE:32:default       (Ghidra 12.1.2 kennt kein MC68000)
    compiler_spec default, Programmname 830a08.7s.68k, Basisadresse 0
  Speicherkarte (CONFIRMED, hornet.cpp:1002-1012): 0x000000-0x07FFFF ROM,
    0x100000-0x10FFFF RAM (64 KB), 0x200000-0x200FFF RF5C400,
    0x300000-0x30001F K056800, Timer 0x500000/0x600000.
  Reset-Vektoren (audio-subsystem.md, "Ladeforschung"): SSP = 0x00110000,
    PC = 0x00000080, IRQ1 0x0AE, IRQ2 0x0C8, IRQ6 0x0E2.

Ablauf: (1) Projekt sichern, (2) Bild pruefen, (3) importieren, (4) analysieren,
(5) speichern, (6) pruefen (Metadaten, Funktionszahl, Stichproben 0x5ED8/0x442C),
(7) Server wieder auf main.bin stellen.

Aufruf aus g:\\Harness\\harness:  python tools\\import_68k_sound.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HARNESS))

from hx.config import load_config                                  # noqa: E402
from hx.ghidra import Ghidra                                       # noqa: E402
from hx.util import Log, read_json                                 # noqa: E402

DECOMP = Path(r"g:\Silent Scope Decomp")
IMG = DECOMP / "build" / "m68k" / "830a08.7s.img"
RAW = DECOMP / "rom" / "830a08.7s"
ZIEL_DATEI = DECOMP / "build" / "m68k" / "830a08.7s.68k"          # Name = Programmname
PROGRAMM = "/830a08.7s.68k"
HAUPT = "/830d01.27p.main.bin"
SPRACHE = "68000:BE:32:default"
STICHPROBEN = [0x5ED8, 0x442C]        # im Repo belegte 68K-Kopfadressen (Scheibe 4c1/4c2)
BERICHT = Path(r"g:\Harness\docs\_68k_import_bericht.txt")

zeilen: list[str] = []


def p(*a) -> None:
    text = " ".join(str(x) for x in a)
    zeilen.append(text)
    print(text)


def bild_pruefen() -> dict:
    """Ist die Arbeitskopie die wortgetauschte Fassung mit den belegten Vektoren?"""
    raw = RAW.read_bytes()
    img = IMG.read_bytes()
    getauscht = all(img[i] == raw[i ^ 1] for i in range(0, len(img), 997))
    ssp = int.from_bytes(img[0:4], "big")
    pc = int.from_bytes(img[4:8], "big")
    erg = {"groesse": len(img), "wortgetauscht": getauscht, "ssp": hex(ssp), "pc": hex(pc),
           "ssp_ok": ssp == 0x00110000, "pc_ok": pc == 0x00000080}
    p(f"  Groesse {len(img)} B | wortgetauscht (Bild[i]=Datei[i^1]): {getauscht}")
    p(f"  SSP = {erg['ssp']} (erwartet 0x00110000: {erg['ssp_ok']}) | "
      f"PC = {erg['pc']} (erwartet 0x00000080: {erg['pc_ok']})")
    return erg


def main() -> int:
    cfg = load_config()
    log = Log(Path(cfg.sub("logs")) / "68k_import.log", echo=False)
    gh = Ghidra(cfg, log)
    ok, meta = gh.reachable()
    p(f"# 68K-Import ins Ghidra-Projekt (Bericht)")
    p("")
    p(f"Server erreichbar: {ok}")
    if not ok:
        p(f"  {meta}")
        BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return 1

    # ---------------------------------------------------------------- 1. Sichern
    p("")
    p("## 1. Projekt sichern (archive_project)")
    bk = gh.backup_project(log, reason="vor dem 68K-Import (Harness-Verwaltungsschritt)")
    p(f"  ok={bk.get('ok')} Pfad={bk.get('path')} Groesse={bk.get('size')} B")
    for s in bk.get("steps", []):
        p(f"  - {s}")
    if not bk.get("ok"):
        p("ABBRUCH: ohne gueltige Sicherung wird nicht importiert.")
        BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return 1

    # ------------------------------------------------------- 2. Bild und Name
    p("")
    p("## 2. Bild pruefen und unter dem Programmnamen bereitstellen")
    pruef = bild_pruefen()
    if not (pruef["wortgetauscht"] and pruef["ssp_ok"] and pruef["pc_ok"]):
        p("ABBRUCH: das Bild passt nicht zum belegten Rezept.")
        BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return 1
    if not ZIEL_DATEI.is_file() or ZIEL_DATEI.read_bytes() != IMG.read_bytes():
        shutil.copy2(IMG, ZIEL_DATEI)
        p(f"  kopiert: {IMG.name} -> {ZIEL_DATEI.name}")
    else:
        p(f"  liegt schon vor: {ZIEL_DATEI}")
    p(f"  /load_program kennt keinen Programmnamen - er folgt dem Dateinamen, "
      f"deshalb heisst die Datei {ZIEL_DATEI.name}")

    # ------------------------------------------------------------- 3. Import
    p("")
    p("## 3. Import (POST /load_program)")
    vorher = len(gh.open_programs())
    p(f"  offene Programme vorher: {vorher}")
    res = gh._post("/load_program", {"file": str(ZIEL_DATEI), "language": SPRACHE,
                                     "compiler_spec": "default"}, timeout=900.0)
    p(f"  Antwort: {json.dumps(res, ensure_ascii=False)[:600]}")
    if not res.get("success", False):
        p("ABBRUCH: /load_program meldet keinen Erfolg.")
        BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        return 1

    prog = ""
    for eintrag in gh.open_programs():
        name = gh._basename(str(eintrag.get("path", "")))
        p(f"  offen: {name} (image_base={eintrag.get('image_base')})")
        if name == ZIEL_DATEI.name:
            prog = name
    p(f"  offene Programme nachher: {len(gh.open_programs())}")

    # ------------------------------------------------- 4./5. Analyse + Speichern
    p("")
    p("## 4. Analyse starten und speichern")
    if prog:
        ist = gh.current_name()
        if ist != prog:
            p(f"  Programm wird gestellt: {prog} (war {ist})")
            gh._get("/switch_program", {"program": prog})
        p(f"  analysis_status: {json.dumps(gh.call('/analysis_status', {'program': prog}), ensure_ascii=False)[:300]}")
        fz0 = gh.call("/get_function_count", {"program": prog})
        p(f"  Funktionszahl direkt nach dem Import: {json.dumps(fz0, ensure_ascii=False)[:200]}")
        anzahl = int(fz0.get("count") or fz0.get("function_count") or 0) if isinstance(fz0, dict) else 0
        if anzahl == 0:
            p("  keine Funktionen -> reanalyze (kann dauern)")
            p(f"  reanalyze: {json.dumps(gh._post('/reanalyze', {}, params={'program': prog}, timeout=3600.0), ensure_ascii=False)[:300]}")
        else:
            p("  Auto-Analyse hat schon gearbeitet - kein zweiter reanalyze-Lauf")
        sp = gh.save_all_programs()
        p(f"  save_all_programs: {json.dumps(sp, ensure_ascii=False)[:300]}")

    # ------------------------------------------------------------- 6. Pruefen
    p("")
    p("## 5. Pruefen (Metadaten, Funktionszahl, Stichproben)")
    info = gh.call("/get_current_program_info", {"program": prog} if prog else None)
    p(f"  get_current_program_info: {json.dumps(info, ensure_ascii=False)[:400]}")
    fz = gh.call("/get_function_count", {"program": prog} if prog else None)
    p(f"  get_function_count: {json.dumps(fz, ensure_ascii=False)[:200]}")

    # R398: fuer /disassemble_bytes vorher und nachher die Funktionszahl buchen.
    vor_fz = fz
    for adr in STICHPROBEN:
        ant = gh._post("/disassemble_bytes", {"start_address": hex(adr), "length": 48,
                                              "include_instructions": True},
                       params={"program": prog}, timeout=120.0)
        instr = ant.get("instructions") or []
        p(f"  Stichprobe 0x{adr:X}: {len(instr)} Instruktionen")
        for i in instr[:6]:
            p(f"    {i.get('address')}  {i.get('mnemonic')} {i.get('operands')}"
              + (f"   [{i.get('bytes')}]" if i.get("bytes") else ""))
        if not instr:
            p(f"    (Antwort: {json.dumps(ant, ensure_ascii=False)[:300]})")
    nach_fz = gh.call("/get_function_count", {"program": prog} if prog else None)
    p(f"  Funktionszahl vor den Stichproben: {json.dumps(vor_fz, ensure_ascii=False)[:120]}")
    p(f"  Funktionszahl nach den Stichproben: {json.dumps(nach_fz, ensure_ascii=False)[:120]}")

    # --------------------------------------------------- 7. Zurueck auf main.bin
    p("")
    p("## 6. Server wieder auf main.bin stellen")
    zurueck = gh.ensure_program(HAUPT, log)
    for s in zurueck.get("steps", []):
        p(f"  - {s}")
    p(f"  ok={zurueck.get('ok')} current={zurueck.get('current')}")

    p("")
    p(f"## Ergebnis")
    p(f"- Programmname im Projekt: {PROGRAMM if prog else '(nicht gefunden!)'}")
    p(f"- Sprache: {SPRACHE} | Basisadresse: 0 (Rohimport ohne Image-Base-Angabe)")
    p(f"- Sicherung: {bk.get('path')} ({bk.get('size')} B)")
    BERICHT.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\ngeschrieben: {BERICHT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
