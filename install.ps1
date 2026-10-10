# install.ps1 - Awake on Deck installer for Windows (ROG Ally / Xbox full-screen experience)
#
# Run this script from any PowerShell window -- it clones or updates the repo automatically.
#
#   irm https://raw.githubusercontent.com/eleonne/awake-on-deck/main/install.ps1 | iex
#
# Or if you already have the file:
#   .\install.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoUrl   = 'https://github.com/eleonne/awake-on-deck.git'
$AppDir    = Join-Path $env:LOCALAPPDATA 'awake-on-deck'
$AppName   = 'Awake on Deck'
$LaunchBat = Join-Path $AppDir 'launch.bat'

function Write-Step { param($msg) Write-Host "[awake] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "[awake] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[awake] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[awake] ERROR: $msg" -ForegroundColor Red; exit 1 }

# 1. Ensure git is installed
Write-Step 'Checking for git...'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn 'git not found. Installing via winget...'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Fail 'winget not found. Install Git for Windows manually from https://git-scm.com and re-run.'
    }
    & winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Write-Fail 'git installation failed. Install Git manually from https://git-scm.com' }
    # Refresh PATH in the current session so git is usable immediately
    $env:PATH = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Fail 'git was installed but is still not on PATH. Please restart PowerShell and re-run.'
    }
    Write-Ok 'git installed.'
} else {
    Write-Ok 'git found.'
}

# 2. Clone or update repo
if (Test-Path (Join-Path $AppDir '.git')) {
    Write-Step "Updating existing installation at $AppDir ..."
    & git -C $AppDir fetch --all
    & git -C $AppDir reset --hard origin/main
    & git -C $AppDir clean -fd
    if ($LASTEXITCODE -ne 0) { Write-Fail 'git update failed.' }
    Write-Ok 'Repository updated.'
} else {
    Write-Step "Cloning $RepoUrl -> $AppDir ..."
    if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
    & git clone $RepoUrl $AppDir
    if ($LASTEXITCODE -ne 0) { Write-Fail 'git clone failed. Check your internet connection.' }
    Write-Ok 'Repository cloned.'
}

# 3. Install dependencies into lib\
Write-Step 'Installing Python dependencies into lib\...'
$libDir = Join-Path $AppDir 'lib'
if (-not (Test-Path $libDir)) { New-Item -ItemType Directory $libDir | Out-Null }

& python -m pip install --target=$libDir --upgrade 'pygame-ce>=2.4' 'wakeonlan>=3.0'

if ($LASTEXITCODE -ne 0) { Write-Fail 'pip install failed.' }
Write-Ok 'Dependencies installed.'

# 5. Create desktop shortcut
Write-Step 'Creating desktop shortcut...'
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\$AppName.lnk")
$Shortcut.TargetPath       = $LaunchBat
$Shortcut.WorkingDirectory = $AppDir
$Shortcut.Description      = 'Wake your PC and launch Steam Remote Play'
$iconPath = Join-Path $AppDir 'img\icon.ico'
if (Test-Path $iconPath) { $Shortcut.IconLocation = $iconPath }
$Shortcut.Save()
Write-Ok "Desktop shortcut created: $AppName.lnk"

# 6. Done
Write-Ok 'Installation complete!'
Write-Host ''
Write-Host '  To add to the Xbox full-screen experience:' -ForegroundColor White
Write-Host '  1. Open the Xbox app and go to My Library.' -ForegroundColor Gray
Write-Host '  2. Click "Add a game on PC" (button near the top of the library).' -ForegroundColor Gray
Write-Host "  3. Browse to: $LaunchBat" -ForegroundColor Gray
Write-Host "  4. It will appear as $AppName in your Xbox library." -ForegroundColor Gray
Write-Host ''
Write-Host '  To update later, re-run this script.' -ForegroundColor Gray
Write-Host ''
