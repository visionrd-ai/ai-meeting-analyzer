#!/usr/bin/env python3
"""
Fix NumPy compatibility issues with soundcard library.
This script helps resolve the "fromstring is removed, use frombuffer instead" error.
"""

import subprocess
import sys
import os

def check_numpy_version():
    """Check current NumPy version."""
    try:
        import numpy as np
        version = np.__version__
        print(f"Current NumPy version: {version}")
        
        major, minor = map(int, version.split('.')[:2])
        if major > 1 or (major == 1 and minor >= 20):
            print("⚠️ NumPy 1.20+ detected - may cause soundcard compatibility issues")
            return True
        else:
            print("✅ NumPy version is compatible with soundcard")
            return False
    except ImportError:
        print("❌ NumPy not installed")
        return False

def check_soundcard_version():
    """Check soundcard library version."""
    try:
        import soundcard
        if hasattr(soundcard, '__version__'):
            print(f"Soundcard version: {soundcard.__version__}")
        else:
            print("Soundcard version: Unknown")
        return True
    except ImportError:
        print("❌ Soundcard library not installed")
        return False

def fix_numpy_compatibility():
    """Fix NumPy compatibility by downgrading to compatible version."""
    print("\n🔧 Fixing NumPy compatibility...")
    print("This will downgrade NumPy to version 1.19.5 (compatible with soundcard)")
    
    response = input("Do you want to proceed? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Fix cancelled")
        return False
    
    try:
        print("📦 Installing compatible NumPy version...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "numpy==1.19.5", "--force-reinstall"
        ])
        print("✅ NumPy 1.19.5 installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install NumPy 1.19.5: {e}")
        return False

def alternative_solutions():
    """Show alternative solutions."""
    print("\n💡 Alternative Solutions:")
    print("=" * 50)
    print("1. Use microphone-only recording:")
    print("   - Select 'Microphone' as audio source in the app")
    print("   - This avoids system audio capture entirely")
    print()
    print("2. Update soundcard library (experimental):")
    print("   pip install --upgrade soundcard")
    print("   (May not be available yet)")
    print()
    print("3. Use AssemblyAI transcription:")
    print("   - Select 'AssemblyAI' as transcription engine")
    print("   - Works with any audio source")
    print()
    print("4. Virtual Audio Cable:")
    print("   - Install VB-Audio Virtual Cable")
    print("   - Route system audio through virtual cable")
    print("   - Use virtual cable as microphone input")

def test_system_audio():
    """Test if system audio capture works."""
    print("\n🧪 Testing system audio capture...")
    try:
        import soundcard as sc
        import numpy as np
        
        # Try to get loopback device
        loopback = None
        all_mics = sc.all_microphones(include_loopback=True)
        
        for mic in all_mics:
            if hasattr(mic, 'isloopback') and mic.isloopback:
                loopback = mic
                break
        
        if not loopback:
            print("❌ No loopback device found")
            return False
        
        print(f"📡 Testing with device: {loopback.name}")
        
        # Try to record a small sample
        with loopback.recorder(samplerate=16000) as recorder:
            data = recorder.record(numframes=1024)
            print("✅ System audio capture test successful!")
            return True
            
    except ValueError as e:
        if "fromstring" in str(e):
            print("❌ NumPy compatibility error confirmed")
            return False
        else:
            print(f"❌ System audio test failed: {e}")
            return False
    except Exception as e:
        print(f"❌ System audio test failed: {e}")
        return False

def main():
    print("🔧 NumPy Compatibility Fix for AI Meeting Analyzer")
    print("=" * 60)
    
    # Check current versions
    numpy_incompatible = check_numpy_version()
    soundcard_available = check_soundcard_version()
    
    if not soundcard_available:
        print("\n❌ Soundcard library not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "soundcard"])
            print("✅ Soundcard library installed")
        except:
            print("❌ Failed to install soundcard library")
            return
    
    # Test system audio
    if numpy_incompatible:
        print("\n⚠️ NumPy compatibility issue detected")
        test_works = test_system_audio()
        
        if not test_works:
            print("\n🔧 Recommended Actions:")
            print("1. Fix NumPy compatibility (recommended)")
            print("2. Use alternative solutions")
            
            choice = input("\nChoose option (1/2): ").strip()
            
            if choice == "1":
                if fix_numpy_compatibility():
                    print("\n✅ Fix applied! Please restart the application.")
                    print("System audio should now work properly.")
                else:
                    alternative_solutions()
            else:
                alternative_solutions()
        else:
            print("✅ System audio works despite NumPy version")
            print("No fix needed!")
    else:
        test_works = test_system_audio()
        if test_works:
            print("✅ Everything looks good!")
        else:
            print("❌ System audio issues detected")
            alternative_solutions()

if __name__ == "__main__":
    main()