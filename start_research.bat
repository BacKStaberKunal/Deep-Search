@echo off
echo Starting Research Application...
cd /d "%~dp0"
cd main
call "..\venv\Scripts\activate.bat"
python app.py
pause