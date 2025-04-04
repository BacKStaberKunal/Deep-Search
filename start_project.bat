@echo off
echo Starting the Research Application...
cd /d "C:\Users\pu\OneDrive\Desktop\kunalPadosi\kunalPadosi"
if errorlevel 1 (
    echo Error: Could not find the project directory
    pause
    exit /b 1
)
python app.py
if errorlevel 1 (
    echo Error: Could not start the application
    pause
    exit /b 1
)
pause 