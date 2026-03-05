@echo off
setlocal enabledelayedexpansion
title Xinyi AI Launcher

REM ==== configure ====
set "WSL_PROJ=~/Xinyi_AI"
set "URL=http://localhost:5000/dashboard"
set "LOG=%USERPROFILE%\Desktop\xinyi_ai_start.log"

echo ===================================  > "%LOG%"
echo Xinyi AI Win11 Launcher             >> "%LOG%"
echo Start Time: %DATE% %TIME%           >> "%LOG%"
echo ===================================  >> "%LOG%"
echo.

echo [1/3] Checking WSL path and script...
echo [1/3] Checking WSL path and script... >> "%LOG%"

wsl -e bash -lc "cd %WSL_PROJ% && pwd && ls -la scripts/ops/start_dev.sh" >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [FAIL] WSL precheck failed. RC=%RC%
  echo [FAIL] WSL precheck failed. RC=%RC% >> "%LOG%"
  echo Please open log: "%LOG%"
  pause
  exit /b %RC%
)

echo [2/3] Starting Xinyi AI...
echo [2/3] Starting Xinyi AI... >> "%LOG%"

REM IMPORTANT: do NOT close window immediately; keep log and pause on failure.
REM Run via bash to avoid executable-bit issues on start_dev.sh.
wsl -e bash -lc "cd %WSL_PROJ% && bash ./scripts/ops/start_dev.sh" >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"

echo Start script RC=%RC% >> "%LOG%"

if not "%RC%"=="0" (
  echo [FAIL] start_dev.sh exited with RC=%RC%
  echo [FAIL] start_dev.sh exited with RC=%RC% >> "%LOG%"
  echo Please open log: "%LOG%"
  pause
  exit /b %RC%
)

echo [3/3] Opening browser: %URL%
echo [3/3] Opening browser: %URL% >> "%LOG%"
start "" "%URL%"

echo.
echo [OK] Started. Log: "%LOG%"
pause
