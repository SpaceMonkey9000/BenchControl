@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Install.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" sustained_benchmark.py --seconds 180 --query-delay-ms 0
pause
