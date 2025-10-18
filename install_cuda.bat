@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------------
rem install_cuda.bat
rem Helper script to install CUDA-enabled Python dependencies.
rem Assumes the active Python environment already has base requirements
rem installed. Run this after activating your virtualenv.
rem ---------------------------------------------------------------------------

if "%~1"=="/?" goto :usage
if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python executable not found in PATH.
    echo Please activate your virtual environment before running this script.
    exit /b 1
)

set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%"

echo.
echo Installing CUDA-enabled dependencies from backend\requirements.torch-cu121.txt ...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    popd
    exit /b 1
)

python -m pip install -r backend\requirements.torch-cu121.txt
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] CUDA dependency installation failed with exit code %EXIT_CODE%.
) else (
    echo.
    echo [OK] CUDA dependencies installed successfully.
)

popd
exit /b %EXIT_CODE%

:usage
echo Usage: %~n0
echo        Activate your Python virtual environment, then run this script to
echo        install the CUDA-enabled dependencies required by PyTorch.
exit /b 0
