# Voodoo GL Live-Integration (build & debug)

## Build/Test-Befehle (CONFIRMED)
- MAME: `$env:MSYSTEM="UCRT64"; bash -lc "cd /c/Users/Arcade/mamebuild && make -j16 SUBTARGET=sscope SOURCES=src/mame/konami/hornet.cpp NOWERROR=1"`; vorher voodoo*.{cpp,h} aus `mame\mame\src\devices\video` nach mamebuild syncen (Copy-Item).
- Standalone: MSYS2-PATH voranstellen ist PFLICHT (cc1plus/live_mod.exe crashen sonst 0xC0000135): `$env:PATH='C:\Users\Arcade\msys64\ucrt64\bin;'+$env:PATH`; dann `ucrt64\bin\g++.exe voodoo_gl_live.cpp poc\live_module_test.cpp -O3 -I... -o poc\live_mod.exe -lopengl32 -lgdi32 -luser32`; Start im Verzeichnis `capture\`.
- A/B: `python scripts\cmp_multi.py`; Snaps regenerieren: `SSC_GL_SNAP_FRAMES='500,1500,2500,3500'` + `-video none -nothrottle -state quick -playback scope_session04 -exit_after_playback`.
- Live-Test: `SSC_GL_LIVE=1 SSC_GL_EXIT_AFTER_FRAMES=N`; Erfolg = "SSC-GL: render ok" + Phasen-Log in error.log.
- VOR jedem Lauf alle SSC_GL_*-Env-Vars poppen (Env-Pollution!).

## Stand (Phase 4 fertig, CONFIRMED)
- A/B 4 Frames: mean 1,4-3,0, max 64-158, <=0,07% Pixel>24. Live ~3,5-4,1ms/Frame (~250-280 FPS), Textur-Cache 0 Uploads über 1680 Frames.
- voodoo0 512x384 xoffs=42 yoffs=27 (GL ignoriert Offsets, identische FB-Adressierung); alle y_origin=1 → GL flipY=-1, Window-Zeile == scry == PPM-Zeile.

## Stand (Phase-4-Nachtrag 2026-08-29, CONFIRMED)
- dev1 (Scope) 768x236, xoffs=106 yoffs=17, rowpixels=768 (=width, Snap-Dump 362496 B). A/B über 8 Frames (500,1500,2200,2500,2600,3500,3600,3900): mean 0,19-3,41, max 13-149, <=0,12% >24 — gleiche Klasse wie dev0, keine neuen Bugs (keine Bisektion nötig).
- dev1-Pairing-Bug gefixt: dev1-Dumps liefen im dev0-Swap → Tri-Liste/FB inkonsistent (Screens driften ~58/60 Hz). Fix: Handshake s_pending_dev1_snap, dev1 dumpt im eigenen swap_buffers + snap_fog_dev1_* (vorher fehlte Fog dev1). dump_tri_list()-Helper.
- Frame-Mapping: voodoo0-Swap ≈ Recording-Frame/2 (7973 Frames ↔ ~3950 Swaps). Hit/Explosion ≈ Swap 3550-3950 (dev0 weiß 4,23% @3900), Zoom-Region ≈ 2550-2700, dev1 fmt2 nur @1700/2200.
- Determinismus: 2 Playback-Läufe → byte-identische snap_dev0/dev1.
- Phase 5 -bench (sauber, beide ohne -log, identische Bedingungen): SW 207,8% vs GL 126,8/128,1% (90s Gameplay) — GL ~5,2ms/Frame langsamer. Erster GL-Lauf mit -log+stderr-DBG-fprintf (127,0%) war verunreinigt; fprintf jetzt nur bei SSC_GL_DBG!=0. Logging war NICHT die Ursache der Lücke (SW-Rasterizer multithreaded; GL seriell + Readback 4,3-6 + glGetError 2,6 ms).
- Jitter/Doppel-Overhead (CONFIRMED, §7.1): TEMP-SSC-FRAMEDELTA in swap_buffers (Per-Frame-Delta, Stats alle 600 Swaps, -log). Steady-State reine Arbeit: dev0 p50 11,9ms SW vs 17,8ms GL (+5,8ms seriell), dev1 +11ms (beide Devices teilen EINEN WGL-Kontext → Serialisierung). Throttle-Fenster: Kadenz identisch (p50 34,2ms), Langsamkeit = Warmlauf (Block 0/1 mean 59,7/41,7ms) + Ausläußer (p99 51-54, max 173ms → 3-VBlank-Frames → Drift). Präsentation läuft in beiden Modi gleich — kein doppeltes Present.
- Phase 6: -video opengl + SSC_GL_LIVE → NVIDIA DrvPresentBuffers ACCESS VIOLATION. Workaround: -video gdi. quick.sta emutime=163s → -bench 253 = 90s Gameplay.
- Wichtige Korrektheitspunkte: TMU-W (startw0/dw0dx/dw0dy) statt FBI-W; S/T/W0 mit 2^-32 skaliert; LOD=fast_log2(w0)=log2(w0)*256 ohne Konstante; Fill-Regel strikt innen (Kanten exklusiv) → FS-Discard auf Top/Left-Kanten; Wrap-State pro Dreieck; Clip-Rechteck → Scissor; alphaMode-Bits 24-31 = alpharef; Dump = 51 Tokens (Format in live-integration.md).
- 565-Quantisierung: PPM-Vergleiche nie über 1/31 Auflösung; debug_rgba.raw für exakte Werte.

## Lessons
- multi_replace_string_in_file schlägt teils still fehl → immer mit grep verifizieren.
- PowerShell-Heredocs für Python hängen → Skripts als Datei anlegen.
- GLPFN-Loader: neue Funktionen brauchen Decl (GLFN), Name in names[] UND Pointer in out[].
- Fill-Regel-Fix braucht Fensterhöhe als Variable (voodoo1 = 768x236, nicht 384 hardcoden).
- MAME-Befehle brauchen den Treibernamen (sonst '___empty' → Playback "Input file is for machine 'sscope'").
- logerror nur mit -log (sonst verworfen); Python mit numpy via `py` (3.10), nicht msys2-python.
- -bench = OSD-Option → seconds_to_run; quick.sta emutime=163s → -bench 90 exitet sofort.
- -video opengl + SSC_GL_LIVE crasht NVIDIA-Treiber; -video d3d = schwarze Surfaces (Remote-Session); -video gdi funktioniert sichtbar. Warnscreen braucht Tastendruck.
- Playtest-Launcher: scripts\playtest-gl.ps1 (SSC_GL_LIVE + gdi + -playback scope_session04 + Fenster auf primären Monitor + Münze). Start-Process -ArgumentList quotiert Leerzeichen-Pfade NICHT → rompath explizit quoten ("Error: unknown option: Scope"). PS5.1-Skripts ASCII-only (Em-Dash zerlegt String-Parsing bei UTF-8 ohne BOM).
- Dense-Sampling-Rezept: SNAP_FRAMES 39 Werte passen in den 256-B-Puffer ('100,200,...,3900' = 195 Zeichen).
