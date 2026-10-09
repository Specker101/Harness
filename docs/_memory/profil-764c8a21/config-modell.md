# Konfigurationsmodell Silent Scope (Stand Batch 63, 2026-09-18) — CONFIRMED
# Port-Umsetzung: port/cfg.{h,cpp} + port/cfg_binding.{h,cpp} + port/service_screen.{h,cpp};
# Selbsttest `port_selftest cfg` (Exit 0, Pruefanker). Beleg: analysis/_m63_cfg_map.txt.

## Struktur
`cfg = *(int*)(r2 + 0x14)` = `[SDA(0x14)]` = 0x800AE378 (RAM, nicht im Image).

| Offset | Typ | Rolle |
|---|---|---|
| +0x00 | u16 | Zustand Vordergrund-/Dialogmaschine |
| +0x02 | u16 | Dialogergebnis (idx 38 schreibt) |
| +0x04 | u16 | **Profil-/Variantenindex 0..4** (27 Leser; 0x8000CBB0 vergleicht mit 2 und setzt Video-Reg `0x74000028`) |
| +0x1A | u8 | 4-stufige Init-Maschine (liest +0x4C >>10 &7 -> [SDA(0x838)]) |
| +0x2E | u8 | **Auswahl-/Modusbyte** (10x lesen, 14x schreiben, XOR-Bit im Dialog) |
| +0x30 | u16 | **Eingabewort** (54 Leser, **1 Schreiber FUN_80026C40**) |
| +0x32 | u16 | Eingabewort 2 (gleicher Schreiber) |
| +0x36 | u16 | 1 Schreiber 0x800274B0 |
| +0x38 | u32 | **Default A** (7-Zeilen-Optionsseite) |
| +0x3C | u32 | **Default B** (16-Zeilen-Seite) |
| +0x40 | u32 | **Default C** (COIN OPTIONS) |
| +0x44 | u32 | reserviert (W4=0, nie adressiert) |
| +0x48 | u32 | Flags (0x8003C6F0/750 = Sequenz-Helfer) |
| +0x4C | u32 | System-/Setup-Flags (45 Leser; Bit 6 = Ranking vorhanden; Bits 10-12 = 3-Bit-Feld) |
| +0x50 | u32 | nur Band 0x800153xx-0x80015Axx (Buchhaltung) |
| +0x56 | u16 | SCREEN CHECK (b) schreibt |
| +0x58 | u32 | **aktuell A** (Options-Seite idx 63-70) |
| +0x5C | u32 | **aktuell B** (Options-Seite idx 73-88) |
| +0x60 | u32 | **aktuell C = COIN** |

## COIN-Wort (+0x60) — CONFIRMED
- Bit 31 = **FREE PLAY** (idx 278, Texte ` FREE PLAY `/ON/OFF)
- Bit 30 = **COIN MECHANISM** INDEPENDENT/COMMON (idx 279)
- Bits 16-19 = **START-Credits** (idx 282, 4 Bit)
- Bits 12-15 = **CONTINUE-Credits** (idx 283, 4 Bit) — bei FREE PLAY verriegelt
- Muster: `neu = (v & 0xF) << shift | alt & ~(0xF << shift)`

## Werksdefaults = 5 Profile (CONFIRMED)
`[SDA(0x70)] = 0x8008CEB0`; Texte ab +0x00 (u. a. `http://www.konami.co.jp` +0x18,
`http://www.konami.co.uk` +0x20); **Default-Bloecke ab +0x58, 16 B je Profil**.
Loader = **idx 34 (0x8000D5E8, Paket f)**:
`memcpy(cfg+0x38, [SDA(0x70)] + idx*0x10 + 0x58, 0x10)`, `idx = max(0, (short)cfg+4)`,
danach `FUN_8000d52c(cfg+0x38)`.

| Profil | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| 0 | 0x29800000 | 0x75094000 | 0x00010000 | 0 |
| 1 | 0x29800000 | 0x74094400 | 0x00021000 | 0 |
| 2 | 0x29800000 | 0x75094400 | 0x00010000 | 0 |
| 3 | 0x29800000 | 0x75194400 | 0x00010000 | 0 |
| 4 | 0x29800000 | 0x75194400 | 0x00010000 | 0 |

W1-Felder: >>0x1D=1, >>0x19&0x1F=20, >>0x18=1, >>0x17=1
W2-Felder: >>0x1E&3=1, >>0x1D=1, >>0x1C=1, >>0x19&0x1F=26, >>0x18=1, >>0x10=1, >>0x0E=1
(profilabhaengig: >>0x14 bei P3/P4, Bits 8-11=4 bei P1-P4, Bits 12-15=4)

## +0x48..+0x54 = KOPIE von +0x38..+0x44 (CONFIRMED Batch 63)
`FUN_8000D52C(p)` = `FUN_8000D1A0(cfg+0x48, p, 0x10)` (= Byte-memcpy) + `FUN_8000DEE8(0x100, cfg+0x48, 0x10)`.
Aufrufstellen im ganzen Bild: `0x8000D360` (`b`, Tail-Call aus Pool-Record idx 14 = `0x8000D358`)
und `0x8000D68C` (`bl` im Rumpf von Pool-Record idx 34 = `0x8000D5E8` = Werkseinstellungen laden).
⇒ Kein `stw`-Schreiber fuer `+0x48` — deshalb findet der Feldzensus keine Schreibstelle.
⇒ `+0x4C` = W2, `+0x50` = W3, `+0x54` = W4 (Kopien); Lautstaerke kommt aus `+0x48` (Kopie von W1).
⇒ Profilindex klemmt nur nach UNTEN (`if (iVar5<0) iVar5=0`), nach oben nicht (Idx 99 liest echte Bytes).

## Eingabewort — der Port-Hook (CONFIRMED)
```
FUN_80026C34 (EINSTIEG, 260 B; 0x80026C40 ist eine Adresse INNERHALB des Rumpfs):
  lwz r3,0xB0(r2)   ; r3 = [SDA(0xB0)] = 0x800B3928 (I/O-Status, BSS)
  lhz r6,0x18(r3) -> cfg+0x32 ; lhz r3,0x1C(r3) -> cfg+0x30
  danach 4-stufige Ini-Maschine ueber cfg+0x1A (OFFEN im Port, gezaehlt)
```
Bits: `(w>>4)&1` = Richtung A; `w&0x88` = Richtung B; `(w>>4)&8` = Bit 7 = TEST-Switch
(Abbruch/fertig); `w&0x100` (idx 41); `[SDA(0xB0)]+0x1C` Bit 2 = Auto/Skip.

## Textbloecke (Basis immer aus der SDA-Zelle nehmen!)
- `SDA(0x784)` = 0x8008C240: ON/OFF/INDEPENDENT/COMMON + COIN-Zeilenlabels
- `SDA(0x78C)` = 0x8008C340: AM/PM + ` HOUR: `/` MINUTE: `/` SECOND: `/` NEXT DATA SUMMARY `
- `SDA(0x1D8)` = 0x80087190: Speicherdialog + SCOPE-ADJUST-Labels (`+0xC8..+0x10C`) + ` SCALE CHECK ` (+0x2B4)
- Beide Bloecke teilen Offsets +0x2AC/2B4/2C0/2E4 (parallel aufgebaut!)

## Offen
- Bedeutung der 5 Profile (STRONG INFERENCE: Region-/Board-Varianten)
- COIN-Submenues idx 280/281 (0x80080D60/0x80080EC8)
- 4. Wortpaar (+0x44/+0x64) reserviert
