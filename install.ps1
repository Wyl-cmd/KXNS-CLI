# Kxns Hunter CLI - Windows Installation Script
# Run this script in PowerShell: .\install.ps1

param(
    [switch]$NoVenv,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Kxns Hunter CLI Installation Script  " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check Python installation
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Cyan
try {
    $pythonVersion = & $Python --version 2>&1
    Write-Host "  Found: $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "  Error: Python not found. Please install Python 3.12+ first." -ForegroundColor Red
    exit 1
}

# Create virtual environment (optional)
$venvPath = Join-Path $PSScriptRoot ".venv"
if (-not $NoVenv) {
    Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Cyan
    if (Test-Path $venvPath) {
        Write-Host "  Virtual environment already exists, skipping..." -ForegroundColor Gray
    } else {
        & $Python -m venv $venvPath
        Write-Host "  Virtual environment created at: $venvPath" -ForegroundColor Gray
    }
    $Python = Join-Path $venvPath "Scripts\python.exe"
} else {
    Write-Host "[2/4] Skipping virtual environment creation..." -ForegroundColor Cyan
}

# Upgrade pip
Write-Host "[3/4] Upgrading pip..." -ForegroundColor Cyan
& $Python -m pip install --upgrade pip --quiet

# Install dependencies
Write-Host "[4/4] Installing dependencies..." -ForegroundColor Cyan
$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
& $Python -m pip install -r $requirementsPath --quiet

# Install the package in development mode
Write-Host "  Installing kxns-cli in development mode..." -ForegroundColor Gray
& $Python -m pip install -e . --quiet

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation completed successfully! " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if (-not $NoVenv) {
    Write-Host "To activate the virtual environment, run:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host ""
}

Write-Host "To verify installation, run:" -ForegroundColor Yellow
Write-Host "  kxns --version" -ForegroundColor White
Write-Host "  kxns --help" -ForegroundColor White
Write-Host ""
