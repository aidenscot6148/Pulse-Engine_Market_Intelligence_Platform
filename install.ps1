# =============================================================================
# PulseEngine — Windows PowerShell Installer Wrapper
# =============================================================================
# This is a thin convenience wrapper around install.py.
# It ensures a compatible Python is available, then delegates to install.py.
#
# One-line install (run in PowerShell from the repo root):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   irm https://raw.githubusercontent.com/The-Pulse-Engine/`
#       Pulse-Engine_Market_Intelligence_Platform/main/install.ps1 | iex
#
# Or after cloning:
#   powershell -ExecutionPolicy Bypass -File install.ps1
# =============================================================================

#Requires -Version 5.1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
function Write-Ok    { param($msg) Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Write-Info  { param($msg) Write-Host "   ->   $msg" -ForegroundColor Cyan }
function Write-Warn  { param($msg) Write-Host "  [!]   $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "  [X]   ERROR: $msg" -ForegroundColor Red }

function Abort {
    param([string]$Message, [string]$Hint = "")
    Write-Host ""
    Write-Fail $Message
    if ($Hint) {
        Write-Host $Hint -ForegroundColor Yellow
    }
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  PulseEngine - Windows PowerShell Installer Wrapper" -ForegroundColor Cyan -NoNewline
Write-Host ""
Write-Host "  =====================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Resolve repo root
# ---------------------------------------------------------------------------
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# 1. Locate a compatible Python interpreter (3.11 – 3.14)
# ---------------------------------------------------------------------------
Write-Info "Searching for a compatible Python interpreter (3.11-3.14) ..."

$PythonCmd = $null
$PyVersion = $null
$CandidateNames = @("python3.14", "python3.13", "python3.12", "python3.11", "python3", "python", "py")

foreach ($Candidate in $CandidateNames) {
    $Found = Get-Command $Candidate -ErrorAction SilentlyContinue
    if (-not $Found) { continue }

    try {
        $VersionOutput = & $Candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if (-not $VersionOutput) { continue }

        $Parts = $VersionOutput.Trim().Split(".")
        $Major = [int]$Parts[0]
        $Minor = [int]$Parts[1]

        if ($Major -eq 3 -and $Minor -ge 11 -and $Minor -le 14) {
            $PythonCmd = $Candidate
            Write-Ok "Found '$Candidate' (Python $VersionOutput)"
            break
        }
    }
    catch {
        continue
    }
}

# Also try the Windows py launcher with specific versions
if (-not $PythonCmd) {
    $PyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        foreach ($MinorVer in @(14, 13, 12, 11)) {
            try {
                $VersionOutput = & py "-3.$MinorVer" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
                if ($VersionOutput) {
                    $PythonCmd = "py"
                    # We'll pass the version flag below
                    $PyVersion = "-3.$MinorVer"
                    Write-Ok "Found 'py $PyVersion' (Python $VersionOutput)"
                    break
                }
            }
            catch { continue }
        }
    }
}

if (-not $PythonCmd) {
    Abort `
        "No compatible Python version found (need 3.11-3.14)." `
        @"

  Install Python 3.12 and retry:

    Option A — Microsoft Store (simplest):
        winget install Python.Python.3.12

    Option B — Direct download:
        https://www.python.org/downloads/windows/
        Check "Add Python to PATH" during installation.

    After installing, re-run:
        powershell -ExecutionPolicy Bypass -File install.ps1
"@
}

# ---------------------------------------------------------------------------
# 2. Confirm install.py exists
# ---------------------------------------------------------------------------
$InstallScript = Join-Path $ScriptDir "install.py"

if (-not (Test-Path $InstallScript)) {
    Abort `
        "install.py not found in $ScriptDir." `
        "  Make sure you are running this script from the root of the cloned repo."
}

# ---------------------------------------------------------------------------
# 3. Execution policy notice
# ---------------------------------------------------------------------------
$CurrentPolicy = Get-ExecutionPolicy -Scope CurrentUser
if ($CurrentPolicy -eq "Restricted") {
    Write-Warn "PowerShell execution policy is 'Restricted'."
    Write-Host "  To allow scripts in future, run:" -ForegroundColor Yellow
    Write-Host "      Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned" -ForegroundColor Yellow
    Write-Host ""
}

# ---------------------------------------------------------------------------
# 4. Delegate to install.py
# ---------------------------------------------------------------------------
Write-Host ""
Write-Info "Handing off to install.py ..."
Write-Host ""

if ($PyVersion) {
    & py $PyVersion $InstallScript
} else {
    & $PythonCmd $InstallScript
}

exit $LASTEXITCODE
