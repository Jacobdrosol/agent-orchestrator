# Example Orchestrator Run Script
# This script demonstrates how to use the orchestrator with pre-filled values
# Copy and customize this script for your specific projects

param(
    [string]$DocumentationPath = "docs/requirements.md",
    [string]$RepositoryPath = ".",
    [string]$Branch = "main",
    [string]$ConfigPath = "config/orchestrator-config.yaml"
)

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Agent Orchestrator - Example Run Script" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Documentation: $DocumentationPath" -ForegroundColor White
Write-Host "  Repository: $RepositoryPath" -ForegroundColor White
Write-Host "  Branch: $Branch" -ForegroundColor White
Write-Host "  Config: $ConfigPath" -ForegroundColor White
Write-Host ""

# Verify files exist
if (-not (Test-Path $DocumentationPath)) {
    Write-Host "✗ Error: Documentation file not found: $DocumentationPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $RepositoryPath)) {
    Write-Host "✗ Error: Repository path not found: $RepositoryPath" -ForegroundColor Red
    exit 1
}

Write-Host "✓ All paths verified" -ForegroundColor Green
Write-Host ""

# Prompt for confirmation
$confirm = Read-Host "Proceed with orchestration? (y/N)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Operation cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Starting orchestration..." -ForegroundColor Cyan
Write-Host ""

# Get the launcher script path
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Split-Path -Parent $ScriptDir
$LauncherScript = Join-Path $ProjectRoot "scripts\orchestrator.ps1"

# Execute the launcher
& $LauncherScript "run" -Config $ConfigPath

exit $LASTEXITCODE
