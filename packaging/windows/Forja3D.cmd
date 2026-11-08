@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Forja3D - inchide aceasta fereastra ca sa opresti aplicatia
cd /d "%~dp0"
"%~dp0python\python.exe" -m forja3d ui %*
if errorlevel 1 (
  echo.
  echo ============================================================
  echo  Forja3D s-a oprit cu o eroare. Verific instalarea...
  echo ============================================================
  "%~dp0python\python.exe" -m forja3d doctor
  echo.
  echo Copiaza textul de mai sus intr-un issue:
  echo   https://github.com/nDumitru/forja3d/issues
  echo.
  pause
)
