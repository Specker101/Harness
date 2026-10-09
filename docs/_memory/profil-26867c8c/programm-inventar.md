# Programm-Inventar / Analyse-Stufen (Batch 60, 2026-09-17)

**Frage, die dieses Dokument beantwortet:** „Wie viel der 2072 Ghidra-Funktionen ist
wirklich gelesen?" Antwort: siehe `analysis/programm-inventar-2026-09-17.md`.

## Zahlen (CONFIRMED, reproduzierbar)

> **NACHLauf Batch 130 (2026-09-23):** `python scripts/m60_inventar.py` wurde
> erneut gefahren (Snapshot weiter 2072 Fn). B130: **S1-DOKU 1642 (79,2 %)**,
> S2-EINZELARTEFAKT 301, S3-SAMMELDUMP 129, S4/S5 0 → Rest ohne
> Doku-Rolle **430 Fn**.
>
> **NACHLauf Batch 131 (2026-09-23):** **S1-DOKU 1648 (79,5 %)**, S2 295,
> S3 129, S4/S5 0 → Rest ohne Doku-Rolle **424 Fn**. Die alten B60-Zahlen
> unten (1392 / 680 / 26,8 %) sind damit **zweimal ueberholt**; sie stehen im
> Dokument `analysis/programm-inventar-2026-09-17.md` in einem KORREKTUR-Kasten
> nebeneinander (B60 | B130 | B131).
> **R308: `m60_inventar.py` vor JEDER Zitat-Verwendung neu fahren und mit Datum
> nennen.** Die Stufe waechst allein dadurch, dass jede Batch neue
> `analysis/`-Belege schreibt — sie ist **kein ROM-Mass**.

- 2072 Ghidra-Fn in `830d01.27p.main.bin` (ein Segment `ram` 0x80000000–0x800AE297,
  flacher Rohimport). 1611 davon im 1611er-Ursprungsinventar (`_ppc_inventory_classified.json`),
  461 neu seit Batch 42 (Nebenwirkungen). Code-Summe über alle Spannen: 495 084 B.
- Stufen (exklusiv): **S1-DOKU 1392 (67,2 % / 73,2 % der Bytes)**, S2-EINZELARTEFAKT 421,
  S3-SAMMELDUMP 218, S4-NUR-GELISTET 41, **S5-NIE 0**. Rest ohne Doku-Rolle = **680 Fn /
  132 476 B = 26,8 %**.
- Strenge Zahl „Rolle belegt" = **340** (strukturierte Gelesen-Listen B42-59 inkl. 327er-Pool);
  `.md`-namentlich 1337 Funktionsanfänge.
- **Kein unbekanntes Subsystem mehr:** größtes zusammenhängendes Rest-Band 3,8 kB / 14 Fn
  (`0x800554B8-0x80056384`). Von **74 MMIO-Funktionen** lag genau 1 im Rest (gelesen).
- Callee-Hüllen (Tiefe 3) der Port-Schnittstellen: Render d 0, Treffer c 0, Konfig e/f 7
  (gelesen, Helfer), Audio 3 (gelesen).

## Reproduktion

`python scripts/m60_fetch.py` (Funktionsliste/Segmente) →
`python scripts/m60_inventar.py` (`_m60_inventar.csv/.txt`) →
`python scripts/m60_audio.py` (Audio) → `python scripts/m60_reach.py` (Erreichbarkeit).

## Regeln (wichtig bei jeder künftigen Zählung)

- **(349) Adresslisten sind teils Pool-INDIZES** (`NEU53` in `m54_open`, `SCHON58` in
  `m58_cov`) → erst über `pool[idx][1]` auflösen.
- **(350) Der 327er-Pool ist kein Funktionsverzeichnis** (nur 65/327 Ghidra-Funktionen).
- **(348) Eine Adresse in einem Artefakt ist kein Analysebeleg** — Dateiklassen trennen
  (Funktionslisten/Zensus vs. Einzelartefakt vs. Sammel-Dump > 200 Fn-Adressen).
