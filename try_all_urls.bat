@echo off
echo 🎯 Perfect AI - Trying All Access Methods
echo ==========================================
echo.

echo 🔍 Running connection diagnostics...
python troubleshoot_connection.py
echo.

echo 🌐 Trying different URLs in your browser...
echo.

echo 1️⃣ Trying localhost (most reliable)...
echo Opening https://localhost:5000
start https://localhost:5000
timeout /t 3 /nobreak >nul

echo.
echo 2️⃣ Trying 127.0.0.1 (alternative localhost)...
echo Opening https://127.0.0.1:5000
start https://127.0.0.1:5000
timeout /t 3 /nobreak >nul

echo.
echo 3️⃣ Trying network IP...
echo Opening https://192.168.100.175:5000
start https://192.168.100.175:5000
timeout /t 3 /nobreak >nul

echo.
echo 4️⃣ Fallback: HTTP (less secure but might work)...
echo Opening http://localhost:5000
start http://localhost:5000

echo.
echo ==========================================
echo 💡 BROWSER TIPS:
echo ==========================================
echo.
echo If you see security warnings:
echo 1. Click "Advanced" at the bottom
echo 2. Click "Continue to [address] (unsafe)"
echo 3. OR type "thisisunsafe" on the warning page
echo.
echo If none work:
echo 1. Make sure server is running: python app_perfect_ai.py
echo 2. Try a different browser (Chrome, Firefox, Edge)
echo 3. Check if antivirus is blocking the connection
echo.
pause