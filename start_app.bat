@echo off
setlocal

:: Get the directory where the script is located
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo 🚀 Starting MedSearch setup for Windows...

:: Check if venv exists, create if not
if not exist "venv\" (
    echo 📦 Virtual environment not found. Creating it now...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment. Please ensure Python is installed and in your PATH.
        pause
        exit /b 1
    )
    echo ✅ venv created.
)

:: Activate venv and install dependencies if requested
set /p choice="📦 Do you want to check and install/update required libraries? (y/N): "
if /i "%choice%"=="y" (
    echo 📥 Installing dependencies...
    call venv\Scripts\activate.bat
    python -m pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo ⏭️ Skipping dependency installation.
)

:: Run the server and open the browser
echo 🌐 Starting MedSearch Backend...
cd backend

:: Start the server in a new window so this script can continue to open the browser
start "MedSearch Backend" cmd /c "..\venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.1 --port 8000"

echo ⏳ Waiting for server to start...
timeout /t 4 /nobreak > nul

echo 🚀 Opening browser at http://127.0.0.1:8000
start http://127.0.0.1:8000

echo.
echo ✅ MedSearch is running! 
echo 💡 Keep the "MedSearch Backend" window open. 
echo ⌨️  Press any key in this window to exit this launcher.
pause > nul
exit
