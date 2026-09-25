# stop.ps1 - bittet den Harness, sich zu beenden; -Force killt den Prozessbaum hart.
# Aufruf:  powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1 [-Force]
param(
    [switch]$Force
)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$stateDir = Join-Path $here 'state'
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force -Path $stateDir | Out-Null }
$marker = Join-Path $stateDir 'STOP'
New-Item -ItemType File -Force -Path $marker | Out-Null
Write-Host ("Stop-Marker gesetzt: {0}" -f $marker)
Write-Host 'Der Harness beendet sich beim naechsten Durchlauf (laufender Batch wird mit WIP-Sicherung abgebrochen).'

if ($Force) {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like '*hx.cli*' }
    if (-not $procs) { Write-Host 'Kein Harness-Prozess gefunden.'; exit 0 }
    foreach ($p in $procs) {
        Write-Host ("taskkill /PID {0} /T /F" -f $p.ProcessId)
        & taskkill /PID $p.ProcessId /T /F | Out-Null
    }
}
exit 0
