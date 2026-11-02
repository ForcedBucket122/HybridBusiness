param([switch]$Dev)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$LocalAIPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $LocalAIPython)) { throw 'Run setup.ps1 first.' }
if (-not $Dev -and -not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Build frontend first: cd frontend; npm.cmd run build' }
New-Item -ItemType Directory -Force -Path logs,data | Out-Null
$LocalAIState = Join-Path $PSScriptRoot 'data\processes.json'
if (Test-Path -LiteralPath $LocalAIState) {
    foreach ($LocalAIEntry in @(Get-Content -LiteralPath $LocalAIState -Raw | ConvertFrom-Json)) {
        $LocalAIExisting = Get-Process -Id $LocalAIEntry.pid -ErrorAction SilentlyContinue
        if ($LocalAIExisting -and $LocalAIExisting.StartTime.ToUniversalTime().Ticks.ToString() -eq $LocalAIEntry.started) {
            throw 'LocalAICompany is already running. Use stop.ps1 first.'
        }
    }
}
$LocalAIRecords = @()
# Fail before starting if another application already owns a required port.
foreach ($LocalAIPort in $(if ($Dev) { @(8000,5173) } else { @(8000) })) {
    $LocalAIProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $LocalAIPort)
    try { $LocalAIProbe.Start() } catch { throw "Port $LocalAIPort is occupied. No process was stopped." }
    finally { $LocalAIProbe.Stop() }
}
function Add-TrackedProcess($Process, [string]$Role) {
    $Process.Refresh()
    $script:LocalAIRecords += [pscustomobject]@{ pid=$Process.Id; started=$Process.StartTime.ToUniversalTime().Ticks.ToString(); path=$Process.Path; role=$Role }
    ConvertTo-Json -InputObject @($script:LocalAIRecords) | Set-Content -LiteralPath $LocalAIState -Encoding UTF8
}
# Production serves the built React frontend and API together on one loopback port.
$LocalAIBackend = Start-Process -FilePath $LocalAIPython -ArgumentList @('-m','uvicorn','app.main:create_app','--factory','--app-dir','backend','--host','127.0.0.1','--port','8000','--workers','1') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\backend-out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'logs\backend-error.log') -PassThru
Add-TrackedProcess $LocalAIBackend 'backend-and-frontend'
$LocalAIReady = $false
for ($LocalAIAttempt=0; $LocalAIAttempt -lt 30; $LocalAIAttempt++) {
    if ($LocalAIBackend.HasExited) { throw 'Backend exited. Read logs\backend-error.log.' }
    try {
        $LocalAIHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        if ($LocalAIHealth.status -eq 'ok') { $LocalAIReady = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $LocalAIReady) { throw 'Backend did not become ready. Read logs or use stop.ps1.' }
if ($Dev) {
    $LocalAINode = (Get-Command node -ErrorAction Stop).Source
    $LocalAIFrontend = Start-Process -FilePath $LocalAINode -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $PSScriptRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\frontend-out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'logs\frontend-error.log') -PassThru
    Add-TrackedProcess $LocalAIFrontend 'frontend-dev'
    Write-Host 'Panel (development): http://127.0.0.1:5173'
} else { Write-Host 'Panel: http://127.0.0.1:8000' }
Write-Host 'API documentation: http://127.0.0.1:8000/docs'
if (-not $LocalAIHealth.ollama.online) { Write-Warning 'Ollama is offline. Start the existing Ollama installation.' }
if ($LocalAIHealth.ollama.missing.Count -gt 0) { Write-Warning ('Missing models: ' + ($LocalAIHealth.ollama.missing -join ', ')) }
Write-Host 'Stop only tracked application processes: powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1'
