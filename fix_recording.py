#!/usr/bin/env python3
"""
Fix recording issues for Perfect AI.
"""

import subprocess
import sys
import os

def install_packages():
    """Install missing packages."""
    print("📦 Installing missing packages...")
    
    packages = [
        "faster-whisper",
        "noisereduce", 
        "webrtcvad",
        "soundcard",
        "scipy",
        "librosa",
        "numpy<1.20.0"  # Compatible version
    ]
    
    for package in packages:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    return True

def test_installation():
    """Test if everything is working."""
    print("\n🔍 Testing installation...")
    
    try:
        # Test faster-whisper
        from faster_whisper import WhisperModel
        print("✅ Faster Whisper working")
        
        # Test PyAudio
        import pyaudio
        audio = pyaudio.PyAudio()
        audio.terminate()
        print("✅ PyAudio working")
        
        # Test other packages
        import noisereduce
        import scipy
        import librosa
        print("✅ Audio processing packages working")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def check_environment():
    """Check environment setup."""
    print("\n🔧 Checking environment...")
    
    # Check .env file
    if not os.path.exists('.env'):
        print("⚠️ .env file not found")
        print("Creating basic .env file...")
        with open('.env', 'w') as f:
            f.write("# Perfect AI Environment Variables\n")
            f.write("SECRET_KEY=your-secret-key-here\n")
            f.write("XAI_API_KEY=your-xai-api-key-here\n")
            f.write("DATABASE_URL=sqlite:///perfect_ai.db\n")
        print("✅ Basic .env file created")
    else:
        print("✅ .env file exists")
    
    # Check for API key
    from dotenv import load_dotenv
    load_dotenv()
    
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key or xai_key == "your-xai-api-key-here":
        print("⚠️ XAI_API_KEY not set properly")
        print("   Get your API key from: https://console.x.ai")
        print("   Add it to your .env file: XAI_API_KEY=your-actual-key")
    else:
        print("✅ XAI_API_KEY is set")

def main():
    """Main fix function."""
    print("🎯 Perfect AI Recording Fix")
    print("=" * 40)
    
    # Step 1: Install packages
    if not install_packages():
        print("❌ Package installation failed")
        return False
    
    # Step 2: Test installation
    if not test_installation():
        print("❌ Installation test failed")
        return False
    
    # Step 3: Check environment
    check_environment()
    
    print("\n" + "=" * 40)
    print("🎉 Fix complete!")
    print("\n📋 Next steps:")
    print("1. Make sure your .env file has the correct XAI_API_KEY")
    print("2. Restart the server: python app_perfect_ai.py")
    print("3. Go to https://localhost:5000/debug to test recording")
    print("4. If still not working, check the debug page for detailed errors")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Fix cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)