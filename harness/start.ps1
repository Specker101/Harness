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

Write-Host ("Harness startet: {0} {1}" -f $py, ($pyArgs -join ' '))
& $py @pyArgs
exit $LASTEXITCODE
