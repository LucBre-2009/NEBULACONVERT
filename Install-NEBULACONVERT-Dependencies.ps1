$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "NEBULACONVERT - Dependency Setup"
Write-Host "`nNEBULACONVERT - Dependency Setup" -ForegroundColor Cyan
Write-Host "================================`n"

$requirements = Join-Path $PSScriptRoot "requirements.txt"
if (-not (Test-Path -LiteralPath $requirements)) {
    Write-Host "ERROR: requirements.txt was not found next to this script." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$python = Get-Command "py.exe" -ErrorAction SilentlyContinue
if ($python) {
    $pythonCommand = $python.Source
    $pythonArgs = @("-3", "-m", "pip")
} else {
    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command "python" -ErrorAction SilentlyContinue }
    if (-not $python) {
        Write-Host "Python was not found. Install Python 3.11 or 3.12 (64-bit) from https://www.python.org/downloads/windows/ and enable 'Add Python to PATH'." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    $pythonCommand = $python.Source
    $pythonArgs = @("-m", "pip")
}

Write-Host "Using Python: $pythonCommand" -ForegroundColor Gray
Write-Host "Installing dependencies from requirements.txt...`n" -ForegroundColor Yellow
& $pythonCommand @pythonArgs install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to update pip." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}
& $pythonCommand @pythonArgs install -r $requirements
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency installation failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}
Write-Host "`nAll Python dependencies were installed successfully." -ForegroundColor Green
Write-Host "To start NEBULACONVERT, run: py -3 main.py"
Read-Host "Press Enter to exit"
