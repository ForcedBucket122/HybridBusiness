$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$LocalAIState = Join-Path $PSScriptRoot 'data\processes.json'
if (-not (Test-Path -LiteralPath $LocalAIState)) { Write-Host 'No tracked LocalAICompany processes.'; exit 0 }
$LocalAIAllowed = @((Join-Path $PSScriptRoot '.venv\Scripts\python.exe'), (Get-Command node -ErrorAction SilentlyContinue).Source)
foreach ($LocalAIEntry in @(Get-Content -LiteralPath $LocalAIState -Raw | ConvertFrom-Json)) {
    $LocalAIProcess = Get-Process -Id $LocalAIEntry.pid -ErrorAction SilentlyContinue
    if (-not $LocalAIProcess) { continue }
    if ($LocalAIProcess.Path -notin $LocalAIAllowed -or $LocalAIProcess.Path -ne $LocalAIEntry.path -or $LocalAIProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $LocalAIEntry.started) {
        Write-Warning "Identity mismatch for PID $($LocalAIEntry.pid); left untouched."
        continue
    }
    Stop-Process -Id $LocalAIProcess.Id -ErrorAction Stop
    Write-Host "Stopped tracked $($LocalAIEntry.role) (PID $($LocalAIEntry.pid))."
}
Remove-Item -LiteralPath $LocalAIState
