#!/usr/bin/env python3
"""
Test script to diagnose audio recording issues.
"""

import sys
import os

def test_pyaudio():
    """Test PyAudio installation and microphone access."""
    print("🎤 Testing PyAudio...")
    
    try:
        import pyaudio
        print("✅ PyAudio imported successfully")
        
        # Initialize PyAudio
        audio = pyaudio.PyAudio()
        print("✅ PyAudio initialized")
        
        # List audio devices
        print("\n📋 Available Audio Devices:")
        print("-" * 50)
        
        device_count = audio.get_device_count()
        input_devices = []
        
        for i in range(device_count):
            try:
                info = audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    input_devices.append((i, info))
                    print(f"  [{i}] {info['name']} (Input: {info['maxInputChannels']} channels)")
            except Exception as e:
                print(f"  [{i}] Error reading device info: {e}")
        
        if not input_devices:
            print("❌ No input devices found!")
            return False
        
        # Test default input device
        try:
            default_input = audio.get_default_input_device_info()
            print(f"\n🎯 Default Input Device: {default_input['name']}")
        except Exception as e:
            print(f"❌ No default input device: {e}")
            return False
        
        # Test opening a stream
        print("\n🔍 Testing microphone access...")
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
            print("✅ Microphone stream opened successfully")
            stream.close()
        except Exception as e:
            print(f"❌ Failed to open microphone stream: {e}")
            return False
        
        audio.terminate()
        return True
        
    except ImportError:
        print("❌ PyAudio not installed")
        print("   Install with: pip install pyaudio")
        return False
    except Exception as e:
        print(f"❌ PyAudio error: {e}")
        return False

def test_faster_whisper():
    """Test Faster Whisper installation."""
    print("\n🤖 Testing Faster Whisper...")
    
    try:
        from faster_whisper import WhisperModel
        print("✅ Faster Whisper imported successfully")
        
        # Try to load a small model
        print("🔍 Testing model loading...")
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✅ Whisper model loaded successfully")
        return True
        
    except ImportError:
        print("❌ Faster Whisper not installed")
        print("   Install with: pip install faster-whisper")
        return False
    except Exception as e:
        print(f"❌ Faster Whisper error: {e}")
        return False

def test_environment():
    """Test environment variables."""
    print("\n🔧 Testing Environment...")
    
    # Check for .env file
    if os.path.exists('.env'):
        print("✅ .env file found")
        
        # Load and check API keys
        from dotenv import load_dotenv
        load_dotenv()
        
        xai_key = os.getenv("XAI_API_KEY")
        if xai_key:
            print("✅ XAI_API_KEY found")
        else:
            print("⚠️ XAI_API_KEY not found (required for AI analysis)")
            
    else:
        print("⚠️ .env file not found")
        print("   Create .env file with your API keys")

def test_permissions():
    """Test system permissions."""
    print("\n🛡️ Testing System Permissions...")
    
    if sys.platform == "win32":
        print("🔍 Windows detected - checking microphone permissions...")
        try:
            import subprocess
            result = subprocess.run([
                'powershell', '-Command', 
                'Get-AppxPackage Microsoft.WindowsCamera | Select-Object -ExpandProperty InstallLocation'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print("✅ Camera/Microphone app permissions appear to be working")
            else:
                print("⚠️ Could not check camera/microphone permissions")
                
        except Exception as e:
            print(f"⚠️ Permission check failed: {e}")
    
    elif sys.platform == "darwin":
        print("🔍 macOS detected")
        print("   Check System Preferences > Security & Privacy > Microphone")
        print("   Make sure your terminal/Python is allowed")
        
    elif sys.platform.startswith("linux"):
        print("🔍 Linux detected")
        print("   Check PulseAudio/ALSA settings")
        print("   Test with: arecord -l")

def main():
    """Run all audio tests."""
    print("🎯 Perfect AI Audio Diagnostic")
    print("=" * 50)
    
    tests = [
        ("PyAudio & Microphone", test_pyaudio),
        ("Faster Whisper", test_faster_whisper),
        ("Environment Variables", test_environment),
        ("System Permissions", test_permissions),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
            all_passed = False
        else:
            status = "⚠️ WARNING"
        
        print(f"   {status} {test_name}")
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests passed! Recording should work.")
    else:
        print("❌ Some tests failed. Check the issues above.")
        print("\n💡 Common Solutions:")
        print("   1. Install missing packages: pip install pyaudio faster-whisper")
        print("   2. Check microphone permissions in system settings")
        print("   3. Try running as administrator (Windows)")
        print("   4. Check if another app is using the microphone")
        print("   5. Restart your computer and try again")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)