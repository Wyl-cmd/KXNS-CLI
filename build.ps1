# Kxns Hunter CLI - Windows Build Script
# Run this script in PowerShell: .\build.ps1

param(
    [string]$Python = "python",
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Kxns Hunter CLI Build Script         " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$ScriptDir = $PSScriptRoot
$DistDir = Join-Path $ScriptDir $OutputDir

# Check if virtual environment exists
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $Python = $VenvPython
    Write-Host "Using virtual environment Python: $Python" -ForegroundColor Gray
}

# Install PyInstaller if not present
Write-Host "[1/3] Checking PyInstaller..." -ForegroundColor Cyan
& $Python -m pip install pyinstaller --quiet

# Clean previous build
Write-Host "[2/3] Cleaning previous build..." -ForegroundColor Cyan
if (Test-Path $DistDir) {
    Remove-Item -Recurse -Force $DistDir
}
$BuildDir = Join-Path $ScriptDir "build"
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}

# Build executable
Write-Host "[3/3] Building executable..." -ForegroundColor Cyan
$SpecFile = Join-Path $ScriptDir "kxns.spec"
if (Test-Path $SpecFile) {
    & $Python -m PyInstaller $SpecFile --distpath $DistDir --workpath $BuildDir --clean
} else {
    # Build without spec file
    & $Python -m PyInstaller `
        --name "kxns" `
        --onefile `
        --console `
        --distpath $DistDir `
        --workpath $BuildDir `
        --clean `
        --hidden-import "kxns_cli" `
        --hidden-import "kosong" `
        --hidden-import "pykaos" `
        --collect-all "kxns_cli" `
        (Join-Path $ScriptDir "src\kxns_cli\cli\__main__.py")
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build completed successfully!         " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output directory: $DistDir" -ForegroundColor Yellow
Write-Host ""

# List output files
Get-ChildItem $DistDir -Recurse | ForEach-Object {
    Write-Host "  $($_.FullName)" -ForegroundColor Gray
}
