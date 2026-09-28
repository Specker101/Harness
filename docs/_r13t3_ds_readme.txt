README-KORREKTUR: "runnable port" ist irrefuehrend (Nutzerauftrag 2026-09-28, Punkt 1)

BEFUND (nur gelesen): `readme.md:638-642` begruendet die Reihenfolge `B A C` mit dem
Satz "the reason: the tone is the last missing piece of a runnable port, and the
conversion of the remaining heads can be measured against it." Der Satz liest sich, als
waere der Port nach dem Ton **lauffaehig**. Das ist er nicht (Stand 2026-09-28):

* Es gibt **kein Spiel-Binary**. Einhaengepunkte sind nur Pruefprogramme:
  `port/src/c_kopf_drv.cpp:118`, `mission5_head_drv.cpp:89`, `mission5_head_drv189.cpp:187`,
  `port_selftest.cpp:2414` und die GL-Senke (`Makefile`: Ziele `all`, `gl`, `ckopf`,
  `head188`..`head193`).
* Kein Boot, kein Attract, kein Level: es fehlen Rahmen (Main-Loop/Init) und die
  Ersetzung der emulierten Schichten.
* `readme.md:752-766` (Milestones) sagt genau das: 3. "A native PC port that renders the
  game's scenes without MAME" - **offen** (die neun GL-Anker
  `analysis/_gl_ref_hashes.txt` belegen die **Kette**, nicht Szenen: glstream, glown,
  glmatrix, glsetup, gltex, gltexsetup, glcolor, glcolorsetup ...);
  4. "Replace the still-emulated layers (audio, boot/I/O) with native code, so that the
  port becomes a standalone executable" - **offen**; `readme.md:53`: "Paket F
  (boot / low-level I/O) is lower priority; it is PC-replaceable."
* Der Ton schliesst also **Zweig B** (Audio bis zum Ton) ab - die letzte noch
  emulierte Schicht nach Milestone 4 -, nicht den Port.

TEXTVORSCHLAG (den "reason"-Satz in `readme.md:640-642` ersetzen):

    reason: with the tone, the last still-emulated **audio layer** is replaced by
    native code (Milestone 4) - that closes **branch B**, not the port. There is
    still no game binary: Milestone 3 ("renders the game's scenes without MAME") is
    open, Packet F (boot / low-level I/O, `readme.md:53`) has yet to be replaced,
    and the frame/main loop is not built. What the tone gives is the finished audio
    chain that the conversion of the remaining heads can be measured against.

Bitte ausserdem pruefen, ob `readme.md:69x` ("Current Status: native port in progress
(graphics chain proven natively; ...)") den Stand sauber beschreibt - der Text ist
richtig, solange "graphics chain" nicht als "Szenen" gelesen wird.
