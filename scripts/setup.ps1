$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir

if (-not (Test-Path ".venv/Scripts/python.exe")) {
    Write-Host "Creating Python virtual environment (.venv)..."
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        py -3.12 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Using Python 3.12 for MediaPipe compatibility."
            py -3.12 -m venv .venv
        } else {
            py -3.11 -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Using Python 3.11 for MediaPipe compatibility."
                py -3.11 -m venv .venv
            } else {
                Write-Warning "Python 3.12/3.11 not found. Falling back to default 'py -3'."
                py -3 -m venv .venv
            }
        }
    } else {
        python -m venv .venv
    }
}

$pythonExe = Join-Path $rootDir ".venv/Scripts/python.exe"

Write-Host "Installing backend dependencies..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt

Write-Host "Installing frontend dependencies..."
Push-Location frontend
npm install
Pop-Location

if ((Test-Path ".env.example") -and -not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

if ((Test-Path "frontend/.env.example") -and -not (Test-Path "frontend/.env")) {
    Copy-Item "frontend/.env.example" "frontend/.env"
}

if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

Write-Host "Setup complete."
Write-Host "Backend: .venv/Scripts/python.exe server.py"
Write-Host "Frontend: cd frontend; npm run dev"
