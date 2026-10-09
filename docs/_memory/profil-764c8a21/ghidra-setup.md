# Ghidra-Setup (verifiziert, Silent Scope Decomp)

- Ghidra 12.1.2 verlangt exakt JDK 21. Installiert: Temurin 21.0.12.1 unter `%LOCALAPPDATA%\Programs\Eclipse Adoptium\jdk-21.0.12.1+1`; Maven 3.9.9 unter `%LOCALAPPDATA%\Programs\Apache\apache-maven-3.9.9`; uv unter `%LOCALAPPDATA%\Programs\uv`. JAVA_HOME/MAVEN_HOME + PATH (User) gesetzt.
- ghidra-mcp: Clone `tools/ghidra-mcp` (v6.0.0); Setup via `python -m tools.setup preflight|ensure-prereqs|build|deploy --ghidra-path "<ws>\ghidra_12.1.2_PUBLIC"`. deploy patcht FrontEndTool.xml + `_code_browser.tcd` → MCP-HTTP-Server (127.0.0.1:8089) startet automatisch mit der GUI.
- `.vscode/mcp.json` braucht ABSOLUTEN uv-Pfad (`C:/Users/Arcade/AppData/Local/Programs/uv/uv.exe`), sonst „MCP server unable to start" (VS Code kennt nachträgliche PATH-Änderungen nicht).
- Headless-Import: Elternordner `ghidra/` muss existieren, sonst „Directory not found". Ghidra 12.1.2: `Program.setImageBase(addr, bool)` gibt void zurück. Raw-Binary-Import hat KEINE Entry Points → Seeds nötig (`SeedEntryPoints.java`: 0xFFFFFFFC + 0xFFE00000), sonst keine Disassembly.
- ROM 830d01.27p: 16-Bit-word-swapped (MAME ROM_LOAD16_WORD_SWAP); Arbeitskopie `rom/build/830d01.27p.be.bin`; Image-Base 0xFFE00000 verifiziert (Reset-Vektor 0xFFFFFFFC = letztes Wort, `bl 0xFFFFFFE0`); Sprache PowerPC:BE:32:default. Projekt `ghidra/sscope-uad`, Programm `/830d01.27p.be.bin`.
- MCP-Endpoints (GUI): `GET /open_program?path=…`, `/decompile_function?address=…` (Param `address`!), `/list_functions?limit=…`, `/read_memory?address=&length=`, `/mcp/schema` = Referenz. Projekt öffnen ist manuell (GUI, File→Open Project).
- **`GET /list_functions` ohne Parameter** liefert die VOLLE Liste als Klartext `NAME at ADDR`
  (~44 kB, 1770 Fn) — billigster Ersatz für das **veraltete** `analysis/_ppc_inventory.json`
  (1611 Fn, verankert in `scripts/PpcInventory.java`). Für Feld-/Konstantenzuordnung immer diese
  frische Liste benutzen (`scripts/m43c_fieldowner.py` zeigt das Muster).
- **Displacement-Scans brauchen immer die Funktionszuordnung** — `ra == r2` auszuschließen reicht
  nicht: `obj+0x280` erscheint als `stw r3,0x280(r1)` (Stack), `obj+0x268` als `lwz r0,0x268(r31)`
  bei `0x8003812C` (fremdes Subsystem). Treffer erst nach Prüfung der enthaltenden Funktion werten.
- **Ghidra-Funktionsgrenzen gegen Tabellenabstände prüfen:** `FUN_80068D14` war 3888 B groß und
  hatte vier Matrixzeilen-Ziele eingesogen (`0x80069158/9620/9728/9A64`) — erst `create_function`
  macht Feldzuordnung korrekt.
- Befund für RE: Reset-Code bei 0xFFFFFFE0 endet mit `mtdcr BR1,r3` + `ba 0xff000000` → ROM vermutlich bei 0xFF000000 aliasiert (Hypothese).
