@echo off
rem ============================================================================
rem  Kiwi launcher
rem
rem  Usage:
rem    start.bat              -> production mode (loads dist/, fastest)
rem    start.bat -Dev         -> development mode with HOT RELOAD:
rem                                backend  auto-reloads on .py changes
rem                                frontend HMR on .tsx / .ts / .css edits
rem    start.bat -Rebuild     -> force a fresh production frontend build
rem    start.bat -Dev -Rebuild
rem ============================================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
