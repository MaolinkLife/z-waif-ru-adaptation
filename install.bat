@echo off
echo ----------------------------------
echo Installing Z-Waif dependencies
echo ----------------------------------

echo.
echo install frontend...
cd frontend
call npm install
cd ..

echo.
echo install backend...
cd backend

IF NOT EXIST venv (
    echo Create a virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt
cd ..

echo.
echo Installation is complete. Ready to run!
pause