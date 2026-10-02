<TELEGRAM_SUMMARY>
Ergebnis: B240 (B-Batch 21) hat die Ursache für den Halt bei Index 132 gefunden. Das Gerüst aus B238 legte die SHARC-Antwort beim Schreiben ab, der PPC holt sie aber beim Lesen ab. Das neue Lese-Modell bringt die Init-Kette eine Stufe weiter (Stufencode 3 → 5). Gegenprobe und Rotprobe sind sauber. Der echte Halt bleibt bei 8001684C. Neu ist eine ehrliche A4-Zahl: von 655.951.355 Schritten bis zum ersten Halt laufen 1.511 nativ (`_preflight_240.txt:31`).
Bewertung: gut gemessen, FERTIG WENN erreicht: ja. Zwei Befunde:
- Prüfung (2) wieder „erfüllt mit benannter Abweichung“, obwohl ich nur erfüllt/nicht erfüllt verlangt hatte. 4 von 6 Funktionen, die nur mit Schatten laufen, sind keine Registry-Köpfe (`_m240/_pruefung2_diff.txt:10-15`).
- 6 neue `.py` unter `analysis/`.
Kosten/Laufzeit: $0,23, 58 min, 176 Anfragen.
Nächster Batch: B241 = C-Batch. Er macht Paket E fertig (die letzten 2 echten Köpfe, Soll 2, weil nur noch 2 offen sind). Dazu ein Cache-Abdruck, der den ganzen Interpreter abdeckt, und eine getrennte Ausweisung der teilgeprüften Köpfe.
B-SCHRITT: 4/5 Boot bis Hauptschleife, B-Batch 21 (Zählung, keine Grenze – Nutzerentscheid 30.09.)
ABBRUCHKRITERIUM ERREICHT: R236-1 – der echte Halt steht nach B238 und B240 weiter bei 8001684C (`_m240/_lauf900m_an.txt`). Strang B ruht nach deiner Regel, bis Paket E fertig ist.
M239-1: übernommen als Preflight-Zeile Hybrid-A4. Wirkung belegt: `_preflight_240.txt:31` – übernommen
M239-6: übernommen. Wirkung belegt: B240 hatte 1 Preflight-Lauf, Anteil 21 % – übernommen
UEBERTRAG: keiner - alle Posten erledigt
ENTSCHIEDEN: Das Urteil zu Prüfung (2) aus B240 wird in B241 über die Aufrufer in Ghidra entschieden.
OFFENE FRAGE: Nach Paket E: soll Strang B ruhen und C die tatsächlich ausgeführten Funktionen abarbeiten (A), oder soll B weiterlaufen mit dem nächsten SHARC-Schritt `FUN_8000ab90` (B)? (B) prüft SHARC-Daten und kommt einem SHARC-Modell nahe. Vorschlag: A.
</TELEGRAM_SUMMARY>

<DS_TOOLS>
profile: ghidra-read
program: /830d01.27p.main.bin
</DS_TOOLS>

## VERALLGEMEINERUNG

**F1 – Urteil zum Nutzerkriterium wieder aufgeweicht** (`port-batch240-…md:216`: „erfuellt mit benannter Abweichung“). Das ist der zweite Fall nach B238, trotz ausdrücklicher Vorgabe „nur erfüllt / nicht erfüllt“.
(a) Fehlerklasse: Eine Abweichung wird mit einer unbelegten Erklärung („Schattenpfade“) zu „erfüllt“ umgedeutet.
(b) Diesmal gibt es eine mechanische Regel statt einer Wortvorgabe. Eine nur-MIT-Funktion zählt nur dann als Schattenpfad, wenn sie laut Ghidra-Aufrufergraph ein direkter oder transitiver Aufgerufener eines Registry-Kopfes ist. Der Nachweis ist die Aufruferkette je Funktion. Fehlt die Kette für eine einzige Funktion, lautet das Urteil **nicht erfüllt**. Betroffen sind die 4 Funktionen `80009DE0`, `8000C6A8`, `800142B4`, `80014820`.
(c) Ob die Schattenpfade in der ROM-Welt auch real laufen, wird nicht geprüft.

**F2 – 6 neue `.py` unter `analysis/_m240/`** (`_preflight_240.txt:32`).
(a) Fehlerklasse: Einmal-Werkzeuge liegen bei den Belegen statt unter `scripts/`.
(b) Die Instruktion verbietet neue `.py` unter `analysis/`; Ziel ist „analysis neue .py“ = 0 neu in B241. Die vorhandenen bleiben liegen, denn Löschen von Belegen ist verboten.
(c) Ob die 6 Skripte reproduzierbar sind, wird nicht geprüft.

**F3 – B-Zahl misst jetzt das Ziel und zeigt Stillstand:** 1511 von 655.951.355 Schritten laufen nativ.
(a) Das ist kein Fehler, sondern der gemessene Befund zu Prüfpunkt a. Die alte Zahl 57819/200M bleibt eine Ersatzzahl.
(b) Strang B ruht nach R236-1; die Zahl wird erst bei einer Wiederaufnahme fortgeschrieben.
(c) Nicht geprüft wird, warum 1511 statt 57819 nativ sind (Schatten gegen ohne Schatten). Das gehört zur Wiederaufnahme.

**Prüfpunkt b:** „Offset 1 für die PPC-Seite unsichtbar“ ist gemessen (`_m240/_sharc_offsets.txt`). Der nächste Blocker `FUN_8000ab90` (SHARC-Daten `0x1121a`) ist bisher nur benannt, nicht im Mitschnitt gesucht. Das gehört zur Nutzerfrage, nicht zu B241.

<DS_INSTRUCTION>
Batch 241 - Silent Scope Decomp

STAND UEBERNEHMEN:
- HEAD b4c16db, Arbeitsbaum sauber.
- Gültiger Preflight `analysis/_preflight_240.txt` (727 s, 0 Befunde). C Köpfe 121/7044/0, davon teilgeprüft 30 (`:19`).
- Paket E laut `_m239/_paket_e_nachher.txt:126-134`: 2 echte Köpfe / 232 Insn offen. Das Blatt ist `80085408` (197 Insn), der zweite Kopf ruft es. Die 4 R215-Host-Modelle zählen nicht.
- **Strang B ruht** nach Nutzerregel R236-1: Der echte Halt `8001684C` hat sich nach B238 und B240 nicht bewegt. Wiederaufnahme nur nach Nutzerentscheid.
- B241 ist ein **C-Batch (Strang C)**.
- SOLL-KOEPFE: 2.

ARBEITSWEISE:
- Startroutine nach AGENTS.md.
- Edit und Write unter `port/` und `scripts/` erst nach dem Commit `B241: Vorhersage`, mit leerer `git status --porcelain port/ scripts/`-Ausgabe.
- **Preflight genau einmal am Ende.** Zwischenprüfungen nur über Einzelgruppen (`c_kopf.py vergl/mut`, `m227_profile_live.py`, `m210_bahnabdeckung.py` direkt).
- Lange Aufrufe blockierend mit `timeout=1800000`.
- **Keine neue `.py` unter `analysis/`.** Hilfsskripte gehören nach `scripts/`. Vorhandene Dateien nicht löschen.
- Einstufen nach CONFIRMED / STRONG INFERENCE / HYPOTHESIS. Belege als `Datei:Zeile@commit`.
- Urteile zu Nutzerkriterien nur „erfüllt“ oder „nicht erfüllt + Grund“.

TEIL 0 – Doku und Urteil Prüfung (2) (nur `analysis/`, Ghidra lesend):
- a) `hybrid-plan.md`: „Sicherungsfenster R236-1 ausgeschöpft: echter Halt 8001684C nach B238 und B240 unverändert (`_m240/_lauf900m_an.txt`); Strang B ruht bis Paket E fertig, Frage an den Nutzer gestellt (Review B240).“
- b) Ankerkopf, Offene Entscheidung, neuer Posten (wortgetreu):
  „Nach Paket E: Soll Strang B ruhen und Strang C die tatsächlich ausgeführten Funktionen (Boot/Attract/Level 1) abarbeiten (A), oder B mit dem nächsten SHARC-Schritt FUN_8000ab90 (prüft SHARC-Daten 0x1121a) weiterlaufen (B)? (Vorschlag: A. bei A: C arbeitet die gemessene ausgeführte Menge ab, B bleibt bei 8001684C. bei B: B baut weiter Gerüst, das sich einem SHARC-Modell nähert, die Front kann sich bewegen.)“
- c) Für die 4 nur-MIT-Funktionen `80009DE0`, `8000C6A8`, `800142B4`, `80014820` die Aufruferkette in Ghidra bis zu einem Registry-Kopf belegen (`get_function_callers`).
  - Nur wenn **alle 4** eine Kette haben: Urteil „Funktionsmenge erfüllt“.
  - Sonst „nicht erfüllt“, mit der Funktion ohne Kette.
  - Urteil in `port-batch240-…md` als Nachtrag und in `_m241/_pruefung2_urteil.txt`.
- Commit `B241: TEIL 0`.

VORHERSAGE (Commit `B241: Vorhersage`):
- Je Bilanzzeile ein Sollwert mit Definition des Zählers.
- C Köpfe 123/…/0; Paket E echte Köpfe 0.
- Preflight-Dauer einschließlich des kalten Profil-Laufs.

TEIL 1 – Messgrundlage (M239-4 + M239-3), vor den Köpfen:
- a) `_mess_hash` (`scripts/c_kopf.py:3961`) nimmt den **gesamten** Quelltext von `m114_matrix` und den Interpreter-Teil von `c_kopf.py` auf (Datei-Hash genügt).
  - Danach **ein kalter Lauf** `c_kopf.py prof` mit Zeitangabe.
  - Ergebnis „Profile reproduzierbar … abweichend 0“, als `_m241/_prof_kalt.txt`.
  - Weicht ein Profil ab: das ist ein Befund (der Altstand war still), mit Kopf und Ursache.
- b) Die Preflight-Zeile `C Koepfe` (oder eine neue Zeile direkt darunter) weist aus: „davon teilgeprüft N / Blöcke ohne Begründung M“. Dasselbe gilt für die Paket-E-Zählung.
  - Vor dem Preflight: Grep der Zeilentexte gegen alle Muster in `m149_bilanz.py:m_preflight`, Liste im Dokument.

TEIL 2 – Paket E fertig:
- Erst `80085408` (Blatt, 197 Insn, Hülle 171, mehrere SPAN-Bereiche), dann der zweite echte Kopf. Je Kopf:
  - Ghidra-Dekompilat und Disassembly, `rumpf_end`;
  - Port in `port/src/ckopf_leaves.cpp` mit Registry-Eintrag, KOPF_DEF und MUT, Fall-Datei;
  - `_m241/_vergl_<k>.txt` mit 0 Abweichungen, `_m241/_mut_<k>.txt` ROT.
- Paket E nachher messen: `_m241/_paket_e_nachher.txt` zeigt echte Köpfe 0.

TEIL 3 – `80056C60`: 41 offene Blöcke:
- Je Block: entweder durch zusätzliche Fälle erreicht (aus `WERTE_DEF` bzw. Werten der Rufstellen, `vergl` weiter 0), oder mit Begründung „unerreichbar, weil …“ (ROM-Stelle).
- Ziel: „ohne Begründung“ = 0 für diesen Kopf.

BATCH-ENDE:
- Preflight einmal: `python -u scripts/preflight.py before *> analysis/_preflight_241.txt`, blockierend mit `timeout=1800000`.
- Zeilendiff zu `_preflight_240`, mit Erklärung je geänderter Zeile.
- Bilanz mit `--write-anchor`. Memory-Export, Commit.
- Ankerkopf `**Stand:** BATCH 241` mit Grep-Beleg und `git status --porcelain` leer.

FERTIG WENN: Paket E echte Köpfe = 0 (beide Köpfe `vergl` 0 + `mut` ROT) UND `_m241/_prof_kalt.txt` zeigt den kalten Lauf mit abweichend 0 (oder einen benannten Befund) UND die C-Zeile weist teilgeprüft/ohne Begründung getrennt aus UND das Urteil Prüfung (2) liegt in `_m241/` UND genau ein gültiger Preflight + Bilanz liegen vor.

STREICHREIHENFOLGE: Gestrichen wird erst, wenn die Batch-Uhr die Umschaltschwelle erreicht. Unmittelbar davor kommt eine `Get-Date`-Zeile ins Dokument. Reihenfolge:
1. TEIL 3.
2. Der zweite Paket-E-Kopf (nicht `80085408`).
NIE streichen: TEIL 0, Vorhersage, TEIL 1, `80085408`, Preflight, Zeilendiff, Bilanz, Memory-Export, Ankerkopf.

## NACHRUECKLISTE
1. Doku und Urteil. FERTIG WENN: `hybrid-plan.md` vermerkt das ausgeschöpfte Sicherungsfenster, der Ankerposten A/B steht wortgetreu, und `_m241/_pruefung2_urteil.txt` enthält je Funktion die Aufruferkette oder „keine“ und das Urteil erfüllt/nicht erfüllt.
2. Vorhersage. FERTIG WENN: `B241: Vorhersage` steht vor dem ersten Diff unter `port/` oder `scripts/`, mit der leeren Porcelain-Ausgabe.
3. Messgrundlage. FERTIG WENN: `_mess_hash` deckt `m114_matrix` vollständig ab, `_m241/_prof_kalt.txt` liegt vor, und die C-Zeile zeigt teilgeprüft/ohne Begründung.
4. `80085408`. FERTIG WENN: `vergl` 0 und `mut` ROT, Dateien in `_m241/`.
5. Zweiter Kopf und Paket E. FERTIG WENN: `vergl` 0 und `mut` ROT, und `_m241/_paket_e_nachher.txt` zeigt echte Köpfe 0.
6. `80056C60`. FERTIG WENN: Die Bahnabdeckung zeigt für `80056C60` „ohne Begründung 0“.
</DS_INSTRUCTION>
