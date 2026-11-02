param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)." } }
Get-Command python -ErrorAction Stop | Out-Null
python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
Check-Exit 'Python version'
Get-Command node -ErrorAction Stop | Out-Null
Get-Command npm.cmd -ErrorAction Stop | Out-Null
node -e "if(Number(process.versions.node.split('.')[0])<22)process.exit(1)"
Check-Exit 'Node 22+ version'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    Check-Exit 'Creating venv'
}
if (-not $SkipInstall) {
    & '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements-lock.txt
    Check-Exit 'Backend dependencies'
    Push-Location frontend
    try { npm.cmd ci; Check-Exit 'Frontend dependencies' } finally { Pop-Location }
}
New-Item -ItemType Directory -Force -Path data,logs,workspace\projects,workspace\artifacts,workspace\runs | Out-Null
Push-Location backend
try { & '..\.venv\Scripts\python.exe' -c "from app.main import create_app; create_app(start_worker=False); print('SQLite initialized')"; Check-Exit 'Database' } finally { Pop-Location }
Push-Location frontend
try { npm.cmd run build; Check-Exit 'Frontend build' } finally { Pop-Location }
try {
    $LocalAITags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    foreach ($LocalAIModel in @('qwen3:4b','qwen2.5-coder:7b')) {
        if ($LocalAIModel -in $LocalAITags.models.name) { Write-Host "Model OK: $LocalAIModel" }
        else { Write-Warning "Missing local model: $LocalAIModel. No download was attempted." }
    }
} catch { Write-Warning 'Ollama is unavailable. Start your existing installation with: ollama serve' }
Write-Host 'Setup complete. Start: powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1'
