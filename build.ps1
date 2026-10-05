$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Create the virtual environment first: python -m venv .venv"
}

& ".venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "Dual Agent Studio" `
    --collect-all PySide6 `
    --add-data "app\core\windows_launcher.ps1;app\core" `
    --add-data "app\ui\assets;app\ui\assets" `
    main.py

Write-Output "Built: dist\Dual Agent Studio\Dual Agent Studio.exe"

