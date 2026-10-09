# Ghidra im Harness (R12-Rauchtest, gemessen 2026-09-25)

- Projekt `g:\Silent Scope Decomp\ghidra\sscope-uad.gpr`, Server headless auf 127.0.0.1:8089.
  Projektdateien (`ghidra/*.rep/**`) sind gitignored → Speichern macht das Repo NICHT schmutzig.
- ZWEI Programme: `830d01.27p.be.bin` = **Boot-Image**, Basis 0xffe00000, 2 MB, 21 Funktionen
  (das Startskript lädt es); `830d01.27p.main.bin` = **PPC-Hauptprogramm**, Basis 0x80000000,
  713368 B, 2085 Funktionen. main.bin ist nach JEDEM Serverneustart wieder weg →
  `POST /load_program_from_project {"path":"/830d01.27p.main.bin"}` + `GET /switch_program?program=…`.
- Adressen der Port-Batches (0x80054AE4, FUN_8005CC54) liegen in **main.bin**; in be.bin gibt es sie
  nicht (`Unable to read bytes at ram:80054ae4` / `No function found`). Rohwort 0x80054AE4 = 48008171.
- MCP-Bridge: `--lazy --default-groups listing,function,program` = **118 Werkzeuge** (kein
  get/set_comment!). Mit `…,comment` = **126 Werkzeuge** (get_comment, set_comment, set_*_comment).
  Die Profile tragen jetzt `listing,function,program,comment`.
- `set_comment` über die BRIDGE lehnt leeren Text ab ("Comment text is required") → der Worker kann
  nur ein Leerzeichen setzen. Über REST (`POST /set_comment` mit `comment:""`) ist das Feld exakt leer.
- Der Worker darf NIE speichern (`save_program` ist in allen Profilen gesperrt) — Speichern macht das
  Harness (`save_all_programs` in der Vor-Batch-Sicherung, `save_program` gezielt).
- Werkzeug: `python -m hx.cli ghidra-smoke [--skip-write]` fährt a) Wechsel, f) Adressprüfung,
  c) Sicherung, b) Leselauf (ghidra-read), d) Schreiblauf (ghidra-standard), e) Endprogramm.
  Bericht: `runs/ghidra-smoke/report.md`. Probeweise Gruppennamen prüfen: Bridge als MCP-Client
  starten (`mcp` ist im bridge-venv) und `list_tools()` zählen.
