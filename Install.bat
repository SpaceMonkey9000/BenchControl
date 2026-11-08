@echo off
setlocal
cd /d "%~dp0"
py -3 --version >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or later from python.org with the Python launcher and Tcl/Tk enabled.
  pause
  exit /b 1
)
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Installation complete. Double-click Start.bat.
pause
exit /b 0
:failed
echo Installation failed. Read the error above.
pause
exit /b 1
