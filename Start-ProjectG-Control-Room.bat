@echo off
setlocal
cd /d "%~dp0"
set "PORT=8765"
set "URL=http://127.0.0.1:%PORT%"

if exist ".\.venv\Scripts\pythonw.exe" (
  start "ProjectG Quant Control Room" ".\.venv\Scripts\pythonw.exe" "scripts\control_room_app.py" --host 127.0.0.1 --port %PORT%
) else (
  start "ProjectG Quant Control Room" ".\.venv\Scripts\python.exe" "scripts\control_room_app.py" --host 127.0.0.1 --port %PORT%
)

timeout /t 2 >nul
start "" "%URL%"
