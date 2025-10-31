@echo off
echo 🎯 Installing Missing Packages for Perfect AI
echo =============================================
echo.

echo 📦 Installing faster-whisper (required for recording)...
pip install faster-whisper
if errorlevel 1 (
    echo ❌ Failed to install faster-whisper
    echo Trying alternative installation...
    pip install --upgrade pip
    pip install faster-whisper --no-cache-dir
)

echo.
echo 📦 Installing other audio dependencies...
pip install noisereduce webrtcvad soundcard scipy librosa

echo.
echo 🔍 Testing installation...
python test_audio.py

echo.
echo ✅ Installation complete!
echo 🚀 You can now run: python app_perfect_ai.py
echo.
pause