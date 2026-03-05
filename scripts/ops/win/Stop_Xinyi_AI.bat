@echo off
title Stop Xinyi AI
set "LOG=%USERPROFILE%\Desktop\xinyi_ai_stop.log"
echo Stop Time: %DATE% %TIME% > "%LOG%"
wsl -e bash -lc "pkill -f 'app.py' || true; pkill -f 'flask' || true; pkill -f 'gunicorn' || true" >> "%LOG%" 2>&1
echo Done. Log: "%LOG%"
pause
