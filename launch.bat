@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%lib;%PYTHONPATH%"

cd /d "%SCRIPT_DIR%"

:: pythonw suppresses the console window when launched from Xbox / shortcut
pythonw main.py %*
