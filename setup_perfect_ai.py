#!/usr/bin/env python3
"""
Perfect AI Meeting Analyzer Setup Script
Automated setup and configuration for the Perfect AI voice processing system.

This script will:
1. Check system requirements
2. Install dependencies
3. Configure audio devices
4. Test Perfect AI components
5. Set up environment variables
"""

import os
import sys
import subprocess
import platform
import json
from pathlib import Path

def print_banner():
    """Print Perfect AI setup banner."""
    print("\n" + "="*70)
    print("🎯 PERFECT AI MEETING ANALYZER SETUP")
    print("="*70)
    print("Advanced voice processing with perfect background noise cancellation")
    print("="*70 + "\n")

def check_python_version():
    """Check if Python version is compatible."""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        print("   Please upgrade Python and try again.")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True

def check_system_requirements():
    """Check system requirements for Perfect AI."""
    print("\n🔍 Checking system requirements...")
    
    system = platform.system()
    print(f"   Operating System: {system}")
    
    # Check for required system libraries
    requirements_met = True
    
    if system == "Windows":
        print("   🪟 Windows detected - checking for audio support...")
        # Windows-specific checks
        try:
            import winreg
            print("   ✅ Windows Registry access available")
        except ImportError:
            print("   ⚠️ Windows Registry access limited")
    
    elif system == "Linux":
        print("   🐧 Linux detected - checking for audio support...")
        # Check for ALSA/PulseAudio
        alsa_check = subprocess.run(['which', 'aplay'], capture_output=True, text=True)
        if alsa_check.returncode == 0:
            print("   ✅ ALSA audio system detected")
        else:
            print("   ⚠️ ALSA not found - audio may not work properly")
    
    elif system == "Darwin":
        print("   🍎 macOS detected - checking for audio support...")
        print("   ✅ Core Audio should be available")
    
    else:
        print(f"   ⚠️ Unsupported operating system: {system}")
        requirements_met = False
    
    return requirements_met

def install_dependencies():
    """Install Perfect AI dependencies."""
    print("\n📦 Installing Perfect AI dependencies...")
    
    # Check if we should use the perfect AI requirements
    requirements_file = "requirements_perfect_ai.txt"
    if not os.path.exists(requirements_file):
        requirements_file = "requirements.txt"
        print(f"   Using fallback requirements: {requirements_file}")
    else:
        print(f"   Using Perfect AI requirements: {requirements_file}")
    
    try:
        # Upgrade pip first
        print("   📦 Upgrading pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        
        # Install requirements
        print("   📦 Installing dependencies...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", requirements_file], 
                               check=True, capture_output=True, text=True)
        
        print("   ✅ Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed to install dependencies: {e}")
        print(f"   Error output: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"   ❌ Requirements file not found: {requirements_file}")
        return False

def setup_environment():
    """Set up environment variables."""
    print("\n⚙️ Setting up environment variables...")
    
    env_file = Path(".env")
    env_content = []
    
    if env_file.exists():
        print("   📄 Found existing .env file")
        with open(env_file, 'r') as f:
            env_content = f.readlines()
    else:
        print("   📄 Creating new .env file")
    
    # Check for required environment variables
    required_vars = {
        'XAI_API_KEY': 'Your xAI API key from https://console.x.ai',
        'ASSEMBLYAI_API_KEY': 'Your AssemblyAI API key (optional)',
        'PERFECT_AI_LOG_LEVEL': 'INFO',
        'PERFECT_AI_AUDIO_BUFFER_SIZE': '2048',
        'PERFECT_AI_NOISE_REDUCTION': 'aggressive'
    }
    
    existing_vars = {}
    for line in env_content:
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.strip().split('=', 1)
            existing_vars[key] = value
    
    updated = False
    for var, description in required_vars.items():
        if var not in existing_vars:
            if var == 'XAI_API_KEY':
                print(f"\n   🔑 {var} is required for AI analysis")
                print(f"      Get your API key from: https://console.x.ai")
                api_key = input(f"      Enter your {var} (or press Enter to skip): ").strip()
                if api_key:
                    env_content.append(f"{var}={api_key}\n")
                    updated = True
                else:
                    env_content.append(f"# {var}=your_api_key_here  # {description}\n")
                    updated = True
            else:
                # Set default values for other variables
                default_value = {
                    'PERFECT_AI_LOG_LEVEL': 'INFO',
                    'PERFECT_AI_AUDIO_BUFFER_SIZE': '2048',
                    'PERFECT_AI_NOISE_REDUCTION': 'aggressive'
                }.get(var, '')
                
                env_content.append(f"{var}={default_value}  # {description}\n")
                updated = True
    
    if updated:
        with open(env_file, 'w') as f:
            f.writelines(env_content)
        print("   ✅ Environment variables configured")
    else:
        print("   ✅ Environment variables already configured")
    
    return True

def test_audio_devices():
    """Test audio device availability."""
    print("\n🎤 Testing audio devices...")
    
    try:
        import pyaudio
        
        # Initialize PyAudio
        audio = pyaudio.PyAudio()
        
        print("   🔍 Available input devices:")
        input_devices = []
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append((i, info['name']))
                print(f"      {i}: {info['name']} ({info['maxInputChannels']} channels)")
        
        if not input_devices:
            print("   ❌ No input devices found!")
            return False
        
        print("   🔍 Testing system audio (loopback)...")
        try:
            import soundcard as sc
            loopback_devices = []
            all_mics = sc.all_microphones(include_loopback=True)
            
            for mic in all_mics:
                if hasattr(mic, 'isloopback') and mic.isloopback:
                    loopback_devices.append(mic.name)
                    print(f"      ✅ Loopback: {mic.name}")
            
            if not loopback_devices:
                print("      ⚠️ No loopback devices found")
                print("      💡 To capture system audio (Zoom/Teams):")
                print("         Windows: Enable 'Stereo Mix' in Sound settings")
                print("         Linux: Configure PulseAudio loopback")
                print("         macOS: Use BlackHole or similar virtual audio device")
        
        except ImportError:
            print("      ⚠️ soundcard library not available - system audio capture disabled")
        except Exception as e:
            print(f"      ⚠️ System audio test failed: {e}")
        
        audio.terminate()
        print("   ✅ Audio device testing complete")
        return True
        
    except ImportError:
        print("   ❌ PyAudio not available - audio processing will not work")
        return False
    except Exception as e:
        print(f"   ❌ Audio device test failed: {e}")
        return False

def test_perfect_ai_components():
    """Test Perfect AI components."""
    print("\n🎯 Testing Perfect AI components...")
    
    # Test Faster-Whisper
    print("   🤖 Testing Faster-Whisper...")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("   ✅ Faster-Whisper loaded successfully")
    except ImportError:
        print("   ❌ Faster-Whisper not available")
        return False
    except Exception as e:
        print(f"   ⚠️ Faster-Whisper test warning: {e}")
    
    # Test noise reduction
    print("   🔇 Testing noise reduction...")
    try:
        import noisereduce as nr
        import numpy as np
        
        # Test with dummy audio
        dummy_audio = np.random.randn(16000).astype(np.float32)
        cleaned = nr.reduce_noise(y=dummy_audio, sr=16000)
        print("   ✅ Noise reduction working")
    except ImportError:
        print("   ❌ Noise reduction library not available")
        return False
    except Exception as e:
        print(f"   ⚠️ Noise reduction test warning: {e}")
    
    # Test Perfect AI audio processor
    print("   🎯 Testing Perfect AI audio processor...")
    try:
        from audio_processor_perfect_ai import PerfectVoiceProcessor
        processor = PerfectVoiceProcessor()
        print("   ✅ Perfect AI audio processor loaded")
    except ImportError:
        print("   ❌ Perfect AI audio processor not available")
        return False
    except Exception as e:
        print(f"   ⚠️ Perfect AI processor test warning: {e}")
    
    print("   ✅ Perfect AI components test complete")
    return True

def create_desktop_shortcut():
    """Create desktop shortcut for Perfect AI."""
    print("\n🖥️ Creating desktop shortcut...")
    
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            print("   ⚠️ Desktop folder not found - skipping shortcut creation")
            return True
        
        script_dir = Path.cwd()
        
        if platform.system() == "Windows":
            # Create Windows shortcut
            shortcut_path = desktop / "Perfect AI Meeting Analyzer.bat"
            with open(shortcut_path, 'w') as f:
                f.write(f'@echo off\n')
                f.write(f'cd /d "{script_dir}"\n')
                f.write(f'python app_perfect_ai.py\n')
                f.write(f'pause\n')
            print(f"   ✅ Windows shortcut created: {shortcut_path}")
        
        else:
            # Create Unix shell script
            shortcut_path = desktop / "perfect_ai_meeting_analyzer.sh"
            with open(shortcut_path, 'w') as f:
                f.write(f'#!/bin/bash\n')
                f.write(f'cd "{script_dir}"\n')
                f.write(f'python3 app_perfect_ai.py\n')
            
            # Make executable
            os.chmod(shortcut_path, 0o755)
            print(f"   ✅ Shell script created: {shortcut_path}")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ Could not create desktop shortcut: {e}")
        return True  # Non-critical error

def print_usage_instructions():
    """Print usage instructions."""
    print("\n" + "="*70)
    print("🎯 PERFECT AI SETUP COMPLETE!")
    print("="*70)
    print("\n📋 Usage Instructions:")
    print("   1. Start the Perfect AI server:")
    print("      python app_perfect_ai.py")
    print("\n   2. Open your browser and go to:")
    print("      http://localhost:5000")
    print("\n   3. Configure Perfect AI settings:")
    print("      • Voice Isolation Level: Maximum (recommended)")
    print("      • Noise Cancellation: Aggressive (recommended)")
    print("      • Audio Source: Choose based on your needs")
    print("        - Microphone: For your voice only")
    print("        - System Audio: For meeting audio (Zoom/Teams)")
    print("        - Both: For complete meeting capture")
    print("\n   4. Start recording and enjoy Perfect AI!")
    print("\n💡 Tips for best results:")
    print("   • Use a good quality microphone")
    print("   • Minimize background noise")
    print("   • For system audio, ensure loopback is enabled")
    print("   • Set your XAI API key in the .env file")
    print("\n🔧 Troubleshooting:")
    print("   • If audio doesn't work, check device permissions")
    print("   • For system audio issues, see audio setup guides")
    print("   • Check the console for error messages")
    print("\n" + "="*70)

def main():
    """Main setup function."""
    print_banner()
    
    # Check requirements
    if not check_python_version():
        return False
    
    if not check_system_requirements():
        print("⚠️ Some system requirements not met - continuing anyway...")
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies - setup incomplete")
        return False
    
    # Setup environment
    if not setup_environment():
        print("❌ Failed to setup environment - setup incomplete")
        return False
    
    # Test components
    if not test_audio_devices():
        print("⚠️ Audio device issues detected - Perfect AI may not work properly")
    
    if not test_perfect_ai_components():
        print("❌ Perfect AI components test failed - setup incomplete")
        return False
    
    # Create shortcuts
    create_desktop_shortcut()
    
    # Print instructions
    print_usage_instructions()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎉 Perfect AI Meeting Analyzer setup completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Perfect AI setup failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)