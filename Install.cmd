@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Install.ps1" %*
if errorlevel 1 (
  echo Installation failed. Read the message above.
  pause
  exit /b 1
)
pause
