@echo off
setlocal

title Xinyi AI - One Click Start

echo [Xinyi AI] Starting backend in WSL...
wsl.exe -e bash -lc "cd ~/Xinyi_AI && ./scripts/ops/start_dev.sh"
set ERR=%ERRORLEVEL%

if not "%ERR%"=="0" (
  echo.
  echo [Xinyi AI] Startup failed, exit code: %ERR%
  echo Check WSL / MySQL / .env / logs^/dev.log
  pause
  exit /b %ERR%
)

echo [Xinyi AI] Opening browser: http://localhost:5000/
timeout /t 2 >nul
start "" "http://localhost:5000/"

echo [Xinyi AI] Done.
endlocal
