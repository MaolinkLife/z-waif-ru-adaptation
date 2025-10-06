@echo off
chcp 65001 >nul
echo Launch of the Z-Waif project...

:: Activate venv
cd backend
call venv\Scripts\activate
cd ..

:: Launching Python Process Manager
python run.py

pause