"""Herzschlag fuer die Waisenmessung (R13v2-Nachprobe, 2026-09-28).

Schreibt jede halbe Sekunde einen Zeitstempel in eine Datei. Bleibt die Datei
frisch, laeuft der Prozess noch - auch wenn der Startende laengst beendet ist.
Damit wird gemessen (und nicht vermutet), was `taskkill /T /F` stehen laesst.

Aufruf:  python tools/r13v_herzschlag.py <datei> <sekunden>
Gefahren wird das ueber tools/r13v_waise_probe.ps1.
"""
import datetime
import sys
import time

ziel = sys.argv[1]
dauer = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
ende = time.time() + dauer
with open(ziel, "a", encoding="utf-8") as fh:
    while time.time() < ende:
        fh.write(datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3] + "\n")
        fh.flush()
        time.sleep(0.5)
    fh.write("ENDE\n")
