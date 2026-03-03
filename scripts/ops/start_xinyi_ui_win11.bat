@echo off
setlocal

title Xinyi AI - 用户界面启动器

echo [Xinyi AI] 正在启动，请稍候...
echo [Xinyi AI] 将在 WSL 中执行 start_dev.sh，并打开首页

wsl.exe -e bash -lc "cd ~/Xinyi_AI && ./scripts/ops/start_dev.sh"
set ERR=%ERRORLEVEL%

if not "%ERR%"=="0" (
  echo.
  echo [Xinyi AI] 启动失败，错误码：%ERR%
  echo 请检查 WSL / Python / MySQL / .env 配置
  pause
  exit /b %ERR%
)

timeout /t 2 >nul
start "" "http://localhost:5000/"

echo [Xinyi AI] 已启动，浏览器已打开首页
endlocal
