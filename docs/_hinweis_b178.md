NACHRICHT AN DEN REVIEWER (Harness-Wartung, im Auftrag des Nutzers, 2026-09-26)

LAGE: Batch 178 lief um 21:37:57 NICHT zu Ende. Der Worker-Prozess ist weg, der HARNESS
wurde hart abgeraeumt (TerminateProcess) - deshalb gibt es keinen Crash-Bericht, keine
stderr-Zeile, kein `result.json`, keinen Commit und keine `antwort.md` in `runs/b178/`.

BELEGTE URSACHE (kein Worker-Fehler): der Worker hat selbst abgesetzt

    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CPU -gt 50 } |
      ForEach-Object { Stop-Process -Id $_.Id -Force }

und damit jeden `python.exe` mit ueber 50 s CPU-Zeit getoetet - der Harness ist selbst ein
`python.exe` (damals ~370 s CPU). In `runs/b178/stream.jsonl` ist das der letzte Aufruf.
Nachgewiesen mit `docs/_abbau_beleg.txt`: in allen Batches b171-b178 genau dieser eine
gefaehrliche Befehl, die uebrigen sechs Abbau-Befehle waren gezielt (`-Id 1234`) oder per
CommandLine-Filter und damit harmlos.

WAS JETZT AUF DER PLATTE LIEGT (Decomp-Repo, Stand beim Neustart):

* absichtlich LIEGEN GEBLIEBEN (bitte nutzen oder bewusst aufraeumen, nicht als Wildwuchs
  behandeln): `analysis/_m178/` (17 Dateien, ~0,1 MB: Disassembly, Cover-Reports,
  Console-Mitschnitte), `scripts/m178_p345.py`, `scripts/m178_tick.py`,
  `scripts/m178_want.py`
* vom Harness als WIP gerettet und deshalb wieder auf HEAD: `scripts/m170_track3.py`,
  `scripts/m175_cover.py` (Sicherung: Stash `harness-wip-b178` + `logs/wip-b178.patch`)

Der Harness hat in der Pause selbst nichts geaendert. Der Arbeitsbaum gilt nur wegen der
unversionierten Dateien als unsauber; der Nutzer hat das mit `/resume ok` bestaetigt.

BITTE ENTSCHEIDE:

1. Batch 178 mit den VORHANDENEN Messdaten fortsetzen (dann reicht eine kurze Instruktion:
   was fehlt noch, welche Belege sind schon da) - oder den Batch neu ausrollen? Die
   68K-Emulationslaeufe kosten hier 400-600 s je Aufruf; die vorhandenen Ergebnisse in
   `analysis/_m178/` sind bezahlt.
2. Ob die drei neuen Skripte und `analysis/_m178/` in den Batch-Commit gehoeren (dann
   bitte im Auftrag nennen: committen, was fertig ist).
3. Wichtig fuer den Auftrag: Prozesse NUR mit fester Nummer beenden
   (`Start-Process … -PassThru`), nie nach Name/CPU-Filter - der Harness bricht einen
   solchen Befehl seit R13i ab und protokolliert ihn als `prozess_abbau`.
