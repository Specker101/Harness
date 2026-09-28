# R13v2-Nachprobe (2026-09-28): Was laesst die Notbremse stehen?
#
# Der Harness bricht einen Worker-Lauf mit `taskkill /PID <claude> /T /F` ab
# (hx/proc.py::kill_tree) - das erwischt nur den BAUM. Diese Sonde misst mit einem
# Herzschlag (Zeitstempel alle 0,5 s in eine Datei), was danach noch laeuft:
# eine kleine Sekundenzahl heisst "schreibt noch", "ENDE" heisst "beendet".
#
#   V1  Startende Shell endet sofort, Kind per Start-Process
#   V2  Startende Shell endet, Kind per WMI (Win32_Process.Create) gestartet
#   V3  Startende Shell LEBT (Muster claude.exe -> Werkzeug-Shell), Kind im Baum,
#       danach Notbremse auf den Baum
#   V4  Startende Shell LEBT, Hintergrundlauf per WMI (Muster B207), dann Notbremse
#
# Aufruf:  powershell -ExecutionPolicy Bypass -File tools\r13v_waise_probe.ps1
# Beleg:   docs\_r13v_waise.txt (schreibt die Sonde selbst)
#
# Anlass/Befund: docs/_r13v_belege.md Abschnitt 5, docs/bedienung.md Abschnitt 12c.

$ErrorActionPreference = 'Continue'
$py = (Get-Command python).Source
$hb = Join-Path $PSScriptRoot 'r13v_herzschlag.py'
$arbeit = Join-Path (Split-Path $PSScriptRoot -Parent) 'sandbox\sperrprobe'
$beleg = Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\_r13v_waise.txt'
New-Item -ItemType Directory -Force -Path $arbeit | Out-Null
$zeilen = New-Object System.Collections.ArrayList
function Sag([string]$t) { [void]$zeilen.Add($t); Write-Host $t }

function Frisch([string]$datei) {
    if (-not (Test-Path $datei)) { return "keine Datei" }
    $sek = [math]::Round(((Get-Date) - (Get-Item $datei).LastWriteTime).TotalSeconds, 1)
    $letzte = (Get-Content $datei -Tail 1)
    return "letzter Eintrag vor $sek s ($letzte)"
}

Sag "R13v2-Waisenmessung (Notbremse = taskkill /PID <wurzel> /T /F)"
Sag "python    : $py"
Sag "herzschlag: $hb"
Sag ""

# ---------------------------------------------------------------- V1
$f1 = Join-Path $arbeit 'hb_v1.txt'
Remove-Item $f1 -Force -ErrorAction SilentlyContinue
$zw1 = "Start-Process -FilePath '$py' -ArgumentList '$hb','$f1','20' -WindowStyle Hidden"
Start-Process -FilePath 'powershell' -Wait -WindowStyle Hidden `
              -ArgumentList '-NoProfile', '-Command', $zw1
Start-Sleep -Seconds 5
Sag "V1  Startende Shell endet sofort            -> $(Frisch $f1)"

# ---------------------------------------------------------------- V2
$f2 = Join-Path $arbeit 'hb_v2.txt'
Remove-Item $f2 -Force -ErrorAction SilentlyContinue
$befehl = "`"$py`" `"$hb`" `"$f2`" 20"
$zw2 = "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments " +
       "@{CommandLine=$([char]39)$befehl$([char]39)} | Out-Null"
Start-Process -FilePath 'powershell' -Wait -WindowStyle Hidden `
              -ArgumentList '-NoProfile', '-Command', $zw2
Start-Sleep -Seconds 5
Sag "V2  Startende Shell endet (Start per WMI)   -> $(Frisch $f2)"

# ---------------------------------------------------------------- V3
$f3 = Join-Path $arbeit 'hb_v3.txt'
Remove-Item $f3 -Force -ErrorAction SilentlyContinue
$zw3 = "Start-Process -FilePath '$py' -ArgumentList '$hb','$f3','40' -WindowStyle Hidden; " +
       "Start-Sleep -Seconds 40"
$wurzel = Start-Process -FilePath 'powershell' -ArgumentList '-NoProfile', '-Command', $zw3 `
                        -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
Sag "V3  Startende Shell LEBT (wie claude.exe)   -> $(Frisch $f3)"
taskkill /PID $wurzel.Id /T /F | Out-Null
Start-Sleep -Seconds 4
Sag "V3  nach taskkill /PID $($wurzel.Id) /T /F        -> $(Frisch $f3)"

# ---------------------------------------------------------------- V4
# Der B207-Fall: in einem LEBENDEN Werkzeug-Shell wird per WMI ein Hintergrundlauf
# gestartet (kein Elternbezug mehr), danach trifft die Notbremse den Shell-Baum.
$f4 = Join-Path $arbeit 'hb_v4.txt'
Remove-Item $f4 -Force -ErrorAction SilentlyContinue
$befehl4 = "`"$py`" `"$hb`" `"$f4`" 30"
$zw4 = "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments " +
       "@{CommandLine=$([char]39)$befehl4$([char]39)} | Out-Null; Start-Sleep -Seconds 30"
$wurzel4 = Start-Process -FilePath 'powershell' -ArgumentList '-NoProfile', '-Command', $zw4 `
                         -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 5
Sag "V4  Hintergrundlauf im lebenden Shell-Baum      -> $(Frisch $f4)"
taskkill /PID $wurzel4.Id /T /F | Out-Null
Start-Sleep -Seconds 4
Sag "V4  nach taskkill /PID $($wurzel4.Id) /T /F       -> $(Frisch $f4)"

Sag ""
Sag "Lesart: eine kleine Sekundenzahl heisst, der Prozess schreibt noch (lebt);"
Sag "'ENDE' oder eine grosse Zahl heisst, er ist beendet."
Sag "Ergebnis gilt fuer DIESE Maschine/Sitzung; die Herzschlagdateien liegen in"
Sag $arbeit

# Beleg VOR dem Aufraeumen schreiben (ein ueberlebender Prozess haelt sonst die
# Ausgabe-Pipe des Aufrufers offen und die Weiterleitung schreibt erst spaeter).
$zeilen | Out-File -FilePath $beleg -Encoding utf8
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*r13v_herzschlag.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Sag "Beleg: $beleg"
$zeilen | Out-File -FilePath $beleg -Encoding utf8
