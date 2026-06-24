param(
    [switch]$Dev,
    [switch]$Rebuild
)

$root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir  = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvDir     = Join-Path $backendDir "venv"
$venvPython  = Join-Path $venvDir "Scripts\python.exe"
$distIndex   = Join-Path $frontendDir "dist\index.html"
$electronCmd = Join-Path $frontendDir "node_modules\.bin\electron.cmd"
$requirementsFile = Join-Path $backendDir "requirements.txt"
$reqHashFile      = Join-Path $venvDir "installed.sha256"

$backendPort = 8000
$vitePort    = 5173

function Write-Step([string]$msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Write-OK([string]$msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "  [ERR] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  ===========================================" -ForegroundColor Magenta
Write-Host "    Kiwi - Offline Knowledge OS" -ForegroundColor Magenta
if ($Dev) {
    Write-Host "    Mode: DEVELOPMENT (hot reload)" -ForegroundColor Yellow
    Write-Host "      - Backend  : auto-reloads on .py file changes" -ForegroundColor DarkGray
    Write-Host "      - Frontend : Vite HMR for .tsx / .ts / .css edits" -ForegroundColor DarkGray
    Write-Host "      - Electron : reload window with Ctrl+R to pick up main.js changes" -ForegroundColor DarkGray
} else {
    Write-Host "    Mode: PRODUCTION (use -Dev for hot reload)" -ForegroundColor Magenta
}
Write-Host "  ===========================================" -ForegroundColor Magenta
Write-Host ""

# ── 1. Python venv ─────────────────────────────────────────────────────────────
Write-Step "Checking Python environment..."
if (-not (Test-Path $venvPython)) {
    Write-Warn "Virtual environment not found. Creating..."

    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $pyExe = $pyCmd.Source
    } else {
        $py3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
        if ($py3Cmd) {
            $pyExe = $py3Cmd.Source
        } else {
            $pyExe = $null
        }
    }

    if (-not $pyExe) {
        Write-Err "Python not found in PATH. Install Python 3.10+ and retry."
        Read-Host "Press Enter to exit"
        exit 1
    }
    & $pyExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to create virtual environment."
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-OK "Virtual environment created."
}

# Hash requirements.txt; only run pip install when it changes or venv was just created
$currentHash = (Get-FileHash $requirementsFile -Algorithm SHA256).Hash
$storedHash  = if (Test-Path $reqHashFile) { (Get-Content $reqHashFile -Raw).Trim() } else { "" }

if ($currentHash -ne $storedHash) {
    Write-Step "Installing Python dependencies (requirements changed)..."
    & $venvPython -m pip install -q --upgrade pip 2>&1 | Out-Null
    & $venvPython -m pip install -q -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed. Check requirements.txt and your internet connection."
        Read-Host "Press Enter to exit"
        exit 1
    }
    $currentHash | Set-Content $reqHashFile -NoNewline
    Write-OK "Python dependencies installed."
} else {
    Write-OK "Python dependencies up to date (skipping pip install)."
}

# ── 2. Node dependencies ───────────────────────────────────────────────────────
Write-Step "Checking Node dependencies..."
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Warn "node_modules missing. Running npm install..."
    & npm.cmd --prefix $frontendDir install --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Err "npm install failed."
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-OK "Node dependencies installed."
} else {
    Write-OK "Node dependencies present."
}

# ── 3. Frontend build (app mode only) ─────────────────────────────────────────
if (-not $Dev) {
    if ((-not (Test-Path $distIndex)) -or $Rebuild) {
        Write-Step "Building frontend..."
        & npm.cmd --prefix $frontendDir run build
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Frontend build failed."
            Read-Host "Press Enter to exit"
            exit 1
        }
        Write-OK "Frontend built successfully."
    } else {
        Write-OK "Frontend dist is current. Use -Rebuild to force a new build."
    }
}

# ── 4. Electron binary check ───────────────────────────────────────────────────
if (-not (Test-Path $electronCmd)) {
    Write-Err "electron.cmd not found at: $electronCmd"
    Write-Err "Run 'npm install' in the frontend directory."
    Read-Host "Press Enter to exit"
    exit 1
}

# ── 5. Free ports ──────────────────────────────────────────────────────────────
Write-Step "Freeing ports $backendPort and $vitePort..."
foreach ($port in @($backendPort, $vitePort)) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction Stop
        foreach ($conn in $conns) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}
Start-Sleep -Seconds 1

# ── 6. Start backend ───────────────────────────────────────────────────────────
# In -Dev mode, uvicorn --reload watches the app/ directory and restarts the
# server in-place when any .py file changes — no need to stop & restart manually.
Write-Step "Starting backend on port $backendPort$(if ($Dev) { ' (hot-reload enabled)' })..."
$reloadFlag = if ($Dev) { ' --reload --reload-dir app' } else { '' }
$beArgs = "/k `"title Kiwi-Backend && `"$venvPython`" -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort$reloadFlag`""
$be = Start-Process -FilePath "cmd.exe" -ArgumentList $beArgs -WorkingDirectory $backendDir -WindowStyle Minimized -PassThru
Write-OK "Backend started (PID $($be.Id))."

# ── 7. Start Vite (dev mode only) ─────────────────────────────────────────────
# Vite's dev server provides Hot-Module Replacement (HMR) for React: edits
# to .tsx / .ts / .css files appear instantly without reloading the window.
$fe = $null
if ($Dev) {
    Write-Step "Starting Vite dev server (HMR enabled)..."
    $fe = Start-Process -FilePath "cmd.exe" -ArgumentList "/k `"title Kiwi-Vite && npm.cmd run dev`"" -WorkingDirectory $frontendDir -WindowStyle Minimized -PassThru
    Write-OK "Vite started (PID $($fe.Id))."
    Write-Step "Waiting for Vite to be ready..."
    Start-Sleep -Seconds 3
}

# ── 8. Launch Electron ─────────────────────────────────────────────────────────
# KIWI_FORCE_DEV tells Electron to ignore any prebuilt dist/ and load the live
# Vite dev server so HMR works even when an older production build exists.
if ($Dev) { $env:KIWI_FORCE_DEV = '1' } else { $env:KIWI_FORCE_DEV = '0' }
Write-Step "Launching Kiwi app window..."
$null = Start-Process -FilePath $electronCmd -ArgumentList "." -WorkingDirectory $frontendDir -WindowStyle Normal

# Wait up to 15s for electron.exe to appear
$waited = 0
while ($waited -lt 15) {
    $proc = Get-Process -Name "electron" -ErrorAction SilentlyContinue
    if ($proc) { break }
    Start-Sleep -Seconds 1
    $waited++
}

Write-Host ""
Write-Host "  ===========================================" -ForegroundColor Magenta
Write-Host "    Kiwi is running." -ForegroundColor Magenta
Write-Host "    Close the app window to stop all services." -ForegroundColor Magenta
Write-Host "  ===========================================" -ForegroundColor Magenta
Write-Host ""

# ── 9. Wait for Electron to exit ──────────────────────────────────────────────
$null = Wait-Process -Name "electron" -Timeout 86400 -ErrorAction SilentlyContinue

# ── 10. Cleanup ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Step "Stopping services..."
try { Stop-Process -Id $be.Id -Force -ErrorAction SilentlyContinue } catch {}
if ($null -ne $fe) { try { Stop-Process -Id $fe.Id -Force -ErrorAction SilentlyContinue } catch {} }
foreach ($port in @($backendPort, $vitePort)) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction Stop
        foreach ($conn in $conns) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    } catch {}
}
Write-OK "All services stopped. Goodbye."
Start-Sleep -Seconds 1
