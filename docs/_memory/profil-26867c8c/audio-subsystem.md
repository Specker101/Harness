# Audio (Silent Scope / Hornet) — Batch 60

**Kernfakt: Audio liegt NICHT im PPC-Image.** Eigener Rechner (CONFIRMED aus
`mame/mame/src/mame/konami/hornet.cpp`, `ROM_START(sscope)`):

- Sound-CPU **Motorola MC68EC000 @16 MHz**, eigenes Programm-ROM **`830a08.7s`** (512 KB) — lokal in `rom/`
- Sound-Chip **Ricoh RF5C400** (PCM, 32 Kanäle), 68K-Adressraum `0x200000-0x200fff`
- Sample-ROMs **`830a09.16p` + `830a10.14p`** (je 4 MB), lokal in `rom/`
- PPC <-> Sound: **Konami K056800 (MIRAC)** Mailbox im PPC-Adressraum **`0x7D030000-0x7D03000F`**
- Sysreg `0x7D010000`: Reg 4 Bit 7 = SNDRES; Reg 5 = Sound Control (MODE/MUTE/DEEN/ATCK je Kanal)
- MAME-Referenzen lokal: `src/devices/sound/rf5c400.cpp` (18 kB), `k056800.cpp` (3,9 kB)

## PPC-Seite (CONFIRMED, Batch 60 + 61 gelesen — Batch 61 = Abschluss)

- **Mailbox-Nutzer (5, Suchmuster `lis rD,0x7D03`):** `FUN_8000E6BC` (Kommando-Sender: 4 B nach
  `0x7D030000`, Flag `0x7D030007=0x10`, Handshake-Poll Bit 7, Timeout `0x7D000`), `FUN_8000E690`
  (MIRAC-Bit `0x7D030006`), `FUN_8002403C` (Selbsttest), `FUN_8002D644` + `FUN_8002D798` (Status)
- **Treiberblock `0x8000E588-0x8000EBAF` = 13 Fn** (Batch 61 korrigiert; `FUN_8000E7F0`
  = 492-B-Lump = 52+216+224 B, `0x8000E824`/`0x8000E8FC` = Rampen L/R): Bit-Bang `E588`/`E60C`
  über **Sysreg Reg 5 `0x7D010005`** (`0x44/0x55`=MUTE=Puls runter, `0x11`=ATCK=Puls hoch),
  Delay `EC08`, Sender `E6BC`, Dequeue `E7A0`, Master-Init `E7F0`(Volumen 20/20),
  Lautstärke `E9DC`, Queue-Reset `EB40`, Cursor `EB68`, Modus `EB7C`, Append `EB88`
- **Trigger: DREI Einstiege, 208 Aufrufstellen** — `FUN_8003C750(id)` 79 Fn/132 Stellen,
  `FUN_8003C6F0(id<<16)` 31/48, `FUN_8000EB88(id<<16)` 18/28 (direkt, ohne Gate/Variante).
  Kein Rohwort-Treffer ⇒ Trigger läuft nie über das Deskriptor-Trampolin.
- **Wire-Wert = `id << 16`** (4 Byte BE nach `0x7D030000`, dann `0x7D030007=0x10` = IRQ);
  Ringpuffer **`[SDA(0x24)]+0x14`**, 64 Einträge `id<<16`, Zeiger `+0x115`/`+0x114`,
  Volumen L/R `+0x11/+0x12` (0..30), Modusbyte `+0x10` (toter Code, nur 0).
- **ID = `Gruppe<<8 | Index`**: `0x0xx` global, `0x1xx` = **BGM mit `+0x20`-Variante**,
  `0x2xx..0x8xx` SFX-Bänke, `0x9xx` = BGM-Transport (0x901/0x902). 76 distinkte IDs belegt;
  **keine ID-Tabelle im PPC** ⇒ Mapping liegt im 68K.
- **Variantenflag = `cfg+0x48` Bit 23** (+0x20 wird bei Flag **0** addiert — Batch-60-Angabe
  war invertiert); **Gate = Bit 1 von `*[SDA(0x240)]+8`** (Trigger wird verworfen).
- **Lautstärke-Quelle:** `cfg+0x48` Bits 25-29 (Default `0x29800000` ⇒ 20 = Init-Wert);
  Hardware ist ein **6-Bit-Auf/Ab-Zähler ohne Readback** ⇒ Treiber führt Istwert selbst;
  **MAME modelliert die Lautstärke nicht** (Reg 5 nur Log, K056800 Reg 4/5 nie geschrieben).
- **Für den Port: 3 Trigger-Hooks + 1 Stop-Hook + 1 Feldwert** (kein Volume-Hook).

## Konsequenz für den Port

Audio ist **kein Blocker** für den Renderer-Port. Empfehlung: RF5C400/K056800 wie MAME
**einbetten** statt 68K-Programm zu analysieren; Lautstärke (Gain) muss der Port **selbst**
machen (MAME hat sie nicht). Stufe 1 = reiner ID-Logger (3 Hooks).

Details: `analysis/f5-descr-batch61-2026-09-17.md` (Abschluss),
`analysis/programm-inventar-2026-09-17.md` §5, `analysis/port-interface.md` §5,
Skripte `scripts/m60_audio.py`, `scripts/m61_{ids,audio2}.py`.
