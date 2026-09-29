NUTZER-NACHRICHT: Vorlage für Batch 160 und zwei Hinweise.

1. VORLAGE FÜR BATCH 160
Die unten stehende Instruktion wurde vor dem Harness-Bau als "Batch 159" geschrieben, aber nie ausgeführt. Batch 159 ist inzwischen der Doku-Batch (Projektziele, Commit e5f3bc7). Übernimm die Vorlage als Grundlage für Batch 160: Inhalt, Zuschnitt und die neue Vorhersage-Pflicht beibehalten. Nur anpassen:
- Nummern: 160 statt 159 überall (Commit "B160: Vorhersage", Preflight-Datei analysis/_preflight_160.txt, m149_bilanz.py --batch 160). Der Verdrahtungsplan in TEIL 2 gilt für B161ff (nicht B160ff).
- Stand: Batch 159 (Commit e5f3bc7). Stand-Dokumente: Anker plus port-batch158-t3-typpfade-2026-09-25.md und port-batch159-projektziel-korrektur-2026-09-25.md.
- "git push" am Batch-Ende entfällt, das macht das Harness.
- SESSIONNAME im Harness-Betrieb nur melden, nicht als Fehler werten.
- Profil ghidra-read, program /830d01.27p.main.bin.
Erkenntnisse aus dem Batch-Ende-Review zu B159 dürfen die Vorlage ergänzen, sie aber nicht verkleinern.

2. GHIDRA-PROGRAMM
Der PROGRAM_REQUEST /830d01.27p.be.bin aus dem B159-Bericht ist widerlegt (Ghidra-Rauchtest des Harness, 25.09. 23:29): 0x80054AE4 und FUN_8005CC54 liegen im PPC-Hauptprogramm /830d01.27p.main.bin (Basis 0x80000000; read_memory 0x80054AE4 = 48008171 = bl 0x8005CC54 bestätigt). In be.bin (Boot-Image, Basis 0xffe00000) ist die Adresse nicht lesbar.

3. NACHTRAG analysis/ghidra-mcp-notes.md (in Batch 160 miterledigen)
Das Harness startet die Bridge mit --lazy --default-groups listing,function,program,comment (ohne die Gruppe comment fehlen alle Kommentar-Werkzeuge). Speichern der Ghidra-Datenbank macht das Harness, nicht der Worker. Programmwechsel macht das Harness am Batch-Rand.

--- VORLAGE (wortgleich, ursprünglich als Batch 159 geschrieben) ---

Batch 159 — Silent Scope Decomp (Scheibe A abschließen: 80054AE4 + Scheibe B vermessen)

STAND ÜBERNEHMEN: Stand-Block + PFLICHT-BILANZ oben in analysis/r1b-workstream.md und analysis/port-batch158-t3-typpfade-2026-09-25.md. Stand: Batch 158 (Commit f5b0330).

VORAB (laut AGENTS.md "Batch-Ablauf"): git status, SESSIONNAME, m151_memory_sync.py status (ggf. import), setup_mesa.ps1 -Check.

ARBEITSWEISE: wie in AGENTS.md. Keine Bash-Syntax in PowerShell, Commit-Nachricht per Datei. Batch-preflight mit Measure-Command.

VORHERSAGE-PFLICHT (neu, mechanisch): In B158 wurde vor der Vorhersage verdrahtet. Ab jetzt gilt: Die schriftliche Vorhersage der Bilanz-Deltas steht im Batch-Dokument und wird als eigener Commit "B159: Vorhersage" committet, BEVOR irgendeine Datei unter port\ geändert wird. Die Commit-Reihenfolge ist der Nachweis. Als Regel in AGENTS.md ("Batch-Ablauf") eintragen.

TEIL 1 – Naht 80054AE4 (FUN_8005CC54 / cc54_setup, Szene-Satz-Kette):
1. Messen und tabellarisch festhalten: Ziel gebaut? Welcher Wirt wird gebraucht (lzss::Runtime, h.lzss->frame, aux() laut B150/R347b)? Welche Vorbedingungen hat der Pfad (Tore wie in B158: Rückgabewerte, Slot-/ctx-Felder)? Argumente an der Rufstelle aus den Rohworten (R385: alle Argumentregister). Welche Zellen verändert die Kette (Szenensatz [SDA(0x330)], Rahmenpuffer)?
2. Vorhersage schreiben und committen (siehe oben).
3. Verdrahten im Sandkastenmuster von (118p): Vollkopie, Diff je Teillauf, wortweise Rückstellung, Wirkungsnachweis (Haken 0, wired, erwartete Zellen). Die Dekompression innerhalb der Kette muss wie in B150 bytegenau gegen m33_lzss.py stimmen.
4. Nicht erfüllbar: gezählt lassen, Blockade konkret benennen.

TEIL 2 – Scheibe B vermessen (NUR messen, nichts verdrahten):
5. Für alle 19 B-Nähte (laut B155 §5 / B156) eine Tabelle wie B157 TEIL 3: Naht → Ziel, Ziel gebaut ja/nein, Wirtbedarf (klassengebunden? OpMode? LZSS?), Typpfad bzw. Tor-Vorbedingungen (Muster B158), Argumente aus den Rohworten, vorhandene Anker.
6. Daraus einen Verdrahtungsplan für B160ff ableiten: Gruppen von Nähten, die sich einen Sandkasten teilen können, und Nähte, die einen noch fehlenden Wirt brauchen (z. B. OpMode in FlowHooks). Reihenfolge begründen.

BATCH-ENDE (laut AGENTS.md):
- Doku: Batch-Dokument (mit Scheibe-B-Tabelle und Plan), Anker, port-implementation-log.md (nächste freie §-Nummer), tooling-cheatsheet.md bei Werkzeugänderungen.
- Memory: status → export VOR dem Commit.
- Genau einmal: preflight before *> datei (mit Measure-Command), dann m149_bilanz.py --batch 159 --from-preflight datei --write-anchor. Ausgabe unverändert übernehmen, Vorhersage gegen Messung.
- Commit, git status melden, git push.
- Nächster Schritt: nur vorschlagen.