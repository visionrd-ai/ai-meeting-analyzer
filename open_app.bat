@echo off
echo 🎯 Opening Perfect AI Meeting Analyzer...
echo.
echo Opening https://localhost:5000 in your default browser...
echo.
echo ⚠️  You may see a security warning - this is normal!
echo    Click "Advanced" then "Proceed to localhost" to continue.
echo.
echo 🎤 Remember to allow microphone access when prompted.
echo.

REM Open the HTTPS URL in default browser
start https://localhost:5000

echo ✅ Browser opened! 
echo.
echo If the page doesn't load, make sure the server is running:
echo    python app_perfect_ai.py
echo.
pause