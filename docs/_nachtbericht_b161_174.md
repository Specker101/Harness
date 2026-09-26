# Nachtbericht B161-B174

Erzeugt aus den Rohbelegen unter `g:\Harness\harness\runs` (nur gelesen).

| Batch | Dauer | Anfragen | Kosten | Profil / Programm | Commits | Alarme | Ablehn. | Werkzeugfehler | Push | Review-Modell | offene Punkte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 161 | 0h33m | 194 | $0.2372 | ghidra-read / main.bin | 3 | 0 | 0 | 11 | ok | claude-opus-5-5 | 0 |
| 162 | 0h21m | 169 | $0.2751 | ghidra-read / main.bin | 2 | 0 | 2 | 6 | ok | claude-opus-5-5 | 1 |
| 163 | 0h28m | 190 | $0.2422 | ghidra-standard / main.bin | 2 | 0 | 0 | 10 | ok | claude-opus-5-5 | 2 |
| 164 | 0h19m | 181 | $0.2260 | none / - | 2 | 0 | 0 | 6 | ok | claude-opus-5-5 | 1 |
| 165 | 0h43m | 302 | $0.4899 | ghidra-standard / main.bin | 2 | 1 | 0 | 28 | ok | claude-opus-5-5 | 2 |
| 166 | 0h13m | 112 | $0.1448 | none / - | 2 | 0 | 0 | 1 | ok | claude-opus-5-5 | 1 |
| 167 | 0h25m | 158 | $0.2127 | ghidra-full / main.bin | 1 | 0 | 6 | 10 | ok | claude-opus-5-5 | 1 |
| 168 | 0h42m | 275 | $0.3439 | none / - | 2 | 1 | 0 | 27 | ok | - | 3 |
| 169 | 0h45m | 202 | $0.2704 | none / - | 3 | 0 | 0 | 12 | ok | claude-opus-5-5 | 2 |
| 170 | 0h38m | 145 | $0.1655 | ghidra-full / main.bin | 2 | 0 | 7 | 6 | ok | claude-opus-5-5 | 2 |
| 171 | 0h40m | 184 | $0.2684 | none / - | 2 | 0 | 0 | 13 | ok | claude-opus-5-5 | 2 |
| 172 | 1h57m | 272 | $0.3814 | ghidra-full / main.bin | 2 | 2 | 8 | 28 | ok | claude-opus-5-5 | 2 |
| 173 | 0h39m | 208 | $0.2568 | none / - | 4 | 0 | 0 | 19 | ok | claude-opus-5-5 | 2 |
| 174 | 1h19m | 327 | $0.4549 | none / - | 2 | 1 | 0 | 18 | ok | - | 0 |

**Summen:** 2919 Anfragen | $3.9694 | 9h49m | 23 Ablehnungen | 195 Werkzeugfehler

## Werkzeugfehler nach Werkzeug (ganze Nacht)
- `PowerShell`: 140
- `Edit`: 18
- `Read`: 14
- `Grep`: 11
- `mcp__ghidra__search_tools`: 4
- `mcp__ghidra__list_tool_groups`: 2
- `mcp__ghidra__check_tools`: 2
- `mcp__ghidra__load_program`: 2
- `mcp__ghidra__load_tool_group`: 1
- `mcp__ghidra__connect_instance`: 1

## Auffaelligkeiten
- B161: 11 Werkzeugfehler - {'Read': 2, 'Grep': 1, 'Edit': 2, 'PowerShell': 6}
- B162: 2 Ablehnung(en)
- B162: 6 Werkzeugfehler - {'mcp__ghidra__search_tools': 1, 'PowerShell': 5}
- B163: 10 Werkzeugfehler - {'PowerShell': 10}
- B164: 6 Werkzeugfehler - {'Read': 1, 'Grep': 1, 'PowerShell': 4}
- B165: Alarm(e): ALARM: 250 Anfragen erreicht (Alarmgrenze 250)
- B165: 28 Werkzeugfehler - {'Read': 2, 'Grep': 2, 'PowerShell': 20, 'Edit': 4}
- B166: 1 Werkzeugfehler - {'PowerShell': 1}
- B167: 6 Ablehnung(en)
- B167: 10 Werkzeugfehler - {'Read': 2, 'mcp__ghidra__list_tool_groups': 1, 'mcp__ghidra__check_tools': 1, 'mcp__ghidra__search_tools': 1, 'PowerShell': 3, 'Edit': 2}
- B168: Alarm(e): ALARM: 250 Anfragen erreicht (Alarmgrenze 250)
- B168: 27 Werkzeugfehler - {'Grep': 2, 'PowerShell': 23, 'Edit': 2}
- B169: 12 Werkzeugfehler - {'Read': 1, 'Grep': 1, 'PowerShell': 10}
- B170: 7 Ablehnung(en)
- B170: 6 Werkzeugfehler - {'mcp__ghidra__check_tools': 1, 'mcp__ghidra__load_program': 1, 'mcp__ghidra__list_tool_groups': 1, 'mcp__ghidra__search_tools': 1, 'Edit': 1, 'Grep': 1}
- B171: 13 Werkzeugfehler - {'Read': 1, 'PowerShell': 12}
- B172: Alarm(e): ALARM: 250 Anfragen erreicht (Alarmgrenze 250); ALARM: Laufzeit 7060s (Alarmgrenze 5400s)
- B172: 8 Ablehnung(en)
- B172: 28 Werkzeugfehler - {'Read': 3, 'mcp__ghidra__search_tools': 1, 'mcp__ghidra__load_tool_group': 1, 'mcp__ghidra__connect_instance': 1, 'mcp__ghidra__load_program': 1, 'PowerShell': 17, 'Edit': 4}
- B173: 19 Werkzeugfehler - {'Read': 1, 'PowerShell': 17, 'Edit': 1}
- B174: Alarm(e): ALARM: 250 Anfragen erreicht (Alarmgrenze 250)
- B174: 18 Werkzeugfehler - {'Grep': 3, 'PowerShell': 12, 'Read': 1, 'Edit': 2}

## Commits der Nacht (Decomp-Repo)
- 21fd25b 2026-09-26 15:05:50 +0200 Batch 174: Audio-Zeile und Aeste-Uebersicht in der Pflicht-Bilanz, 4c1 (0x5ED8) nativ
- c95fbd6 2026-09-26 14:28:19 +0200 B174: Vorhersage
- 72812a7 2026-09-26 13:43:35 +0200 B173: Doku richtiggestellt - BGM 0x115 in diesem Batch NICHT gemessen
- 011d678 2026-09-26 13:43:21 +0200 B173: Selbsttest-Endbeleg (rc 0, 12 Zeilen 29/29)
- ab7670d 2026-09-26 13:43:09 +0200 Batch 173: Scheibe 4 gemessen und geteilt, 4a (SysEx-/Kennungspfad) nativ
- 15772e0 2026-09-26 13:20:26 +0200 B173: Vorhersage
- 12d1198 2026-09-26 13:00:27 +0200 Batch 172: Scheibe 3 komplett nativ - 3a Stufe 2 (acht Nibbelziele, neun CC-Ziele), Orakel-Schnitt nach R430 repariert
- 17b89c8 2026-09-26 12:44:45 +0200 B172: Vorhersage
- 908c46a 2026-09-26 11:00:21 +0200 Batch 171: Scheibe 3 nativ - 3b (Quelle) und 3a Stufe 1 (Verteiler), Orakel-Spur S und G
- 8c9c24e 2026-09-26 10:38:51 +0200 B171: Vorhersage
- e3f7563 2026-09-26 10:01:59 +0200 Batch 170: 68K-Import blockiert (Werkzeug fehlt), Scheibe 3 geteilt, Tafeln und tickfreie Spur
- de96877 2026-09-26 09:25:49 +0200 B170: Vorhersage
- 393c1e8 2026-09-26 09:21:36 +0200 B169: Umgebung und PFLICHT-BILANZ ins Batch-Dokument (Doku-Nachtrag, kein port/-Byte)
- a7c5b14 2026-09-26 09:21:23 +0200 Batch 169: Scheibe 2 nativ - wer die SMF-Bytes liest, Orakel-Spur, SMF-Dekodierer im Port
- 0a82c78 2026-09-26 09:06:18 +0200 B169: Vorhersage
- b8f5453 2026-09-26 08:33:10 +0200 Batch 168: Audio Scheibe 1 - TYPE_16-Extraktion, 68K-Referenz-Pruefstand (Register-Schreibfolge), Tafeln im Port
- a19a50b 2026-09-26 08:15:57 +0200 B168: Vorhersage
- c695d13 2026-09-26 06:16:03 +0200 Batch 167: Preflight-Regel (Nutzerentscheidung), 68K-ROM ladbar gemacht (Import blockiert), zwei Audio-Restfragen beantwortet, Dekompilierplan (portcode-frei)
- 4923cc7 2026-09-26 05:47:13 +0200 ﻿Batch 166: Audio A' Schritt 1 - Extraktion (MIDI + PCM), Noten->Sample im 68K, Debug-Ausgaben entfernt
- 65fbc3b 2026-09-26 05:36:15 +0200 ﻿B166: Vorhersage
- 6c98b12 2026-09-26 05:30:39 +0200 Batch 165: FUN_8002AC74 gebaut + FUN_800274AC (Spannengrenze, 18 Insn) gebaut + 68K-Nachmessung
- f24d456 2026-09-26 04:57:33 +0200 B165: Vorhersage
- aba1616 2026-09-26 04:44:23 +0200 Batch 164: 68K-Messfrage statisch (Sequenzer-Logik vorhanden) + Teilregression --only (R402)
- 5ba74a4 2026-09-26 04:40:46 +0200 ﻿B164: Vorhersage
- ea6b9ba 2026-09-26 04:01:30 +0200 Batch 163: OpMode-Wirt + N2 + FUN_8003E3D4 (schon gebaut) + R391-Verstoss richtiggestellt
- 94312ca 2026-09-26 03:47:54 +0200 B163: Vorhersage
- 2cf70c4 2026-09-26 03:30:29 +0200 Batch 162: Scheibe B abgeschlossen (19/19) - G2 mit wiederverwendbarem Sandkasten-Helfer + G3/G4/G5
- 56ae5fb 2026-09-26 03:23:39 +0200 B162: Vorhersage
- 50039b3 2026-09-26 03:05:32 +0200 B161: Nachtrag - Verdrahtungsstand der 19 Naehte (9 verdrahtet / 10 offen mit Blockade)
- 751f123 2026-09-26 03:05:15 +0200 Batch 161: Scheibe-B-Gruppe G1 verdrahtet (9 Naehte Typ 12/13/14) + Doku-Korrekturen
- e3db5ae 2026-09-26 02:40:37 +0200 B161: Vorhersage
- 2685fbb 2026-09-26 01:14:28 +0200 Batch 160: Scheibe A abgeschlossen (80054AE4 / FUN_8005CC54 verdrahtet) + Scheibe B (19 Naehte) vermessen
- f7c628e 2026-09-26 01:14:09 +0200 B160: Vorhersage
