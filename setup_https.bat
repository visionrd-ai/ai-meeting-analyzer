@echo off
echo 🎯 Perfect AI HTTPS Setup for Windows
echo =====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found
echo.

REM Install cryptography package
echo 📦 Installing cryptography package...
pip install cryptography>=41.0.0
if errorlevel 1 (
    echo ❌ Failed to install cryptography package
    pause
    exit /b 1
)

echo ✅ cryptography package installed
echo.

REM Run the HTTPS setup script
echo 🔒 Setting up HTTPS certificates...
python setup_https.py
if errorlevel 1 (
    echo ❌ HTTPS setup failed
    pause
    exit /b 1
)

echo.
echo ✅ HTTPS setup complete!
echo.
echo 🚀 You can now run: python app_perfect_ai.py
echo 🌐 Then open: https://localhost:5000
echo.
echo ⚠️  Remember to accept the security warning in your browser
echo    (this is normal for self-signed certificates)
echo.
pause