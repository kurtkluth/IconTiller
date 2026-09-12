@echo off
cd /d "%~dp0"
if not exist ".venv312\Scripts\python.exe" (
  echo Run the setup instructions in README.md first.
  pause
  exit /b 1
)
".venv312\Scripts\python.exe" app.py
if errorlevel 1 pause
