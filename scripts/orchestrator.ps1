# Agent Orchestrator PowerShell Launcher
# Activates virtual environment and launches the orchestrator CLI

param(
    [Parameter(Position=0)]
    [string]$Command = "run",
    
    [Parameter()]
    [string]$RunId = "",
    
    [Parameter()]
    [string]$Config = ""
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Determine project root (parent of AgentOrchestrator folder)
$ScriptDir = Split-Path -Parent $PSCommandPath
$AgentOrchestratorDir = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $AgentOrchestratorDir

Write-Host "Agent Orchestrator - PowerShell Launcher" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Error: Python not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.10+ from https://www.python.org/" -ForegroundColor Yellow
    exit 1
}

# Check for virtual environment
$VenvPath = Join-Path $ProjectRoot "venv"
if (-not (Test-Path $VenvPath)) {
    Write-Host "✗ Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please create the virtual environment first:" -ForegroundColor Yellow
    Write-Host "  cd `"$ProjectRoot`"" -ForegroundColor Cyan
    Write-Host "  python -m venv venv" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

# Activate virtual environment
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Host "✗ Error: Activation script not found at $ActivateScript" -ForegroundColor Red
    Write-Host ""
    Write-Host "Your virtual environment may be corrupted. Try recreating it:" -ForegroundColor Yellow
    Write-Host "  Remove-Item -Recurse -Force venv" -ForegroundColor Cyan
    Write-Host "  python -m venv venv" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& $ActivateScript

if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
    Write-Host "✗ Failed to activate virtual environment" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Virtual environment activated" -ForegroundColor Green
Write-Host ""

# Change to project root
Set-Location $ProjectRoot

# Build command arguments
$pythonArgs = @("main.py", $Command)

if ($Config) {
    $pythonArgs += @("--config", $Config)
}

if ($RunId) {
    $pythonArgs += @("--run-id", $RunId)
}

# Execute main.py
Write-Host "Launching orchestrator..." -ForegroundColor Cyan
Write-Host "Command: python $($pythonArgs -join ' ')" -ForegroundColor Gray
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

try {
    & python @pythonArgs
    $ExitCode = $LASTEXITCODE
} catch {
    Write-Host ""
    Write-Host "✗ Error executing orchestrator: $_" -ForegroundColor Red
    $ExitCode = 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan

# Deactivate virtual environment
if (Get-Command deactivate -ErrorAction SilentlyContinue) {
    deactivate
    Write-Host "✓ Virtual environment deactivated" -ForegroundColor Green
}

# Exit with the same code as the Python script
if ($null -eq $ExitCode) {
    $ExitCode = 0
}

Write-Host ""
Write-Host "Exiting with code: $ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Red" })
exit $ExitCode
