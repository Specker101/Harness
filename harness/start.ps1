# start.ps1 - startet den Harness in einem EIGENEN PowerShell-Fenster (nicht VS Code).
# Aufruf:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 [-Paused] [-Mock]
# -Paused  : im Freigabemodus und Zustand PAUSIERT starten (Bot laeuft;
#            "hx.cli resume" bzw. Telegram /resume startet weiter)
# -Mock    : Attrappen statt echter API-Aufrufe (kostet nichts)
param(
    [switch]$Mock,
    [switch]$Paused,
    [string]$Config = ''
)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { Write-Host 'python nicht im PATH gefunden.'; exit 2 }
if ([string]::IsNullOrWhiteSpace($Config)) { $Config = Join-Path $here 'harness.toml' }
Set-Location $here
try { $Host.UI.RawUI.WindowTitle = 'Silent-Scope-Harness' } catch { }

$pyArgs = @('-u', '-m', 'hx.cli', '--config', $Config, 'run')
if ($Mock)   { $pyArgs += '--mock' }
if ($Paused) { $pyArgs += '--paused' }

# C (R13c): stderr ZUSAETZLICH in eine Datei mitschreiben. Am 2026-09-26 starb der
# Harness um 00:30 still und ohne Logeintrag - ein Traceback im Fenster war danach weg.
$logDir = Join-Path $here 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$errLog = Join-Path $logDir 'start-stderr.log'
Add-Content -Path $errLog -Value ("`n=== Start {0} : {1} ===" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), ($pyArgs -join ' '))

Write-Host ("Harness startet: {0} {1}" -f $py, ($pyArgs -join ' '))
& $py @pyArgs 2>> $errLog
$code = $LASTEXITCODE

if ($code -ne 0) {
    # Meldung im Fenster stehen lassen, damit der Absturz nicht wieder spurlos ist.
    $crash = Get-ChildItem (Join-Path $logDir 'crash-*.txt') -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime | Select-Object -Last 1
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Red
    Write-Host ("HARNESS ABGESTUERZT oder mit Fehler beendet (Exit-Code {0})" -f $code) -ForegroundColor Red
    if ($crash) {
        Write-Host ("Crash-Bericht: {0}" -f $crash.FullName) -ForegroundColor Red
        Write-Host ('--- letzte 20 Zeilen ---') -ForegroundColor Red
        Get-Content $crash.FullName -Tail 20
    } else {
        Write-Host 'Kein Crash-Bericht gefunden (Absturz vor dem ersten Zustandswechsel).' -ForegroundColor Red
    }
    Write-Host ("stderr-Mitschnitt: {0}" -f $errLog) -ForegroundColor Red
    Write-Host ('=' * 72) -ForegroundColor Red
    Read-Host 'Fenster bleibt offen - Enter zum Schliessen'
}
exit $code
