@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title Abydex - inchide aceasta fereastra ca sa opresti aplicatia
cd /d "%~dp0"
"%~dp0python\python.exe" -m abydex ui %*
if errorlevel 1 (
  echo.
  echo ============================================================
  echo  Abydex s-a oprit cu o eroare. Verific instalarea...
  echo ============================================================
  "%~dp0python\python.exe" -m abydex doctor
  echo.
  echo Copiaza textul de mai sus intr-un issue:
  echo   https://github.com/nDumitru/abydex/issues
  echo.
  pause
)
