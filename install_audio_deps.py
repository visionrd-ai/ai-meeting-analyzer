#!/usr/bin/env python3
"""
Installation script for audio processing dependencies with noise cancellation.
Run this script to install all required packages for enhanced audio processing.
"""

import subprocess
import sys
import os

def install_package(package):
    """Install a package using pip."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    print("🎙️ Installing Enhanced Audio Processing Dependencies")
    print("=" * 60)
    
    # Core dependencies
    core_packages = [
        "flask",
        "flask-socketio",
        "python-dotenv",
        "numpy",
        "scipy",
        "faster-whisper",
        "requests"
    ]
    
    # Audio processing dependencies
    audio_packages = [
        "pyaudio",
        "soundcard",
        "noisereduce",
        "librosa",
        "assemblyai"
    ]
    
    print("Installing core dependencies...")
    for package in core_packages:
        install_package(package)
    
    print("\nInstalling audio processing dependencies...")
    for package in audio_packages:
        install_package(package)
    
    print("\n🎉 Installation complete!")
    print("\nEnhanced features enabled:")
    print("✅ Real-time noise cancellation")
    print("✅ Voice activity detection")
    print("✅ Background voice filtering")
    print("✅ Optimized for low latency")
    print("✅ WebSocket real-time updates")
    print("✅ Dual transcription engines (Faster-Whisper + AssemblyAI)")
    print("✅ Cloud and local processing options")
    
    print("\nTo start the application:")
    print("python app_meet.py")

if __name__ == "__main__":
    main()