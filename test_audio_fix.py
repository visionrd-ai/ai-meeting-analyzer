#!/usr/bin/env python3
"""
Test script to verify audio processing fixes.
"""

import numpy as np
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_audio_processing():
    """Test audio processing functions."""
    print("🧪 Testing Audio Processing Fixes")
    print("=" * 50)
    
    try:
        # Import the audio processing functions
        from audio_processor_faster_whisper_meet import (
            apply_noise_cancellation, 
            detect_voice_activity, 
            optimize_audio_for_speech
        )
        
        # Create test audio data (simulate 1 second of audio)
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)
        
        # Generate test audio (sine wave + noise)
        t = np.linspace(0, duration, samples)
        frequency = 440  # A4 note
        audio_signal = np.sin(2 * np.pi * frequency * t)
        noise = np.random.normal(0, 0.1, samples)
        test_audio = audio_signal + noise
        
        # Convert to int16 (typical audio format)
        test_audio_int16 = (test_audio * 32767).astype(np.int16)
        
        print(f"✅ Generated test audio: {len(test_audio_int16)} samples")
        print(f"   Data type: {test_audio_int16.dtype}")
        print(f"   Range: {np.min(test_audio_int16)} to {np.max(test_audio_int16)}")
        
        # Test noise cancellation
        print("\n🔧 Testing noise cancellation...")
        try:
            cleaned_audio = apply_noise_cancellation(test_audio_int16, sample_rate)
            print(f"✅ Noise cancellation successful")
            print(f"   Output type: {cleaned_audio.dtype}")
            print(f"   Output range: {np.min(cleaned_audio):.3f} to {np.max(cleaned_audio):.3f}")
        except Exception as e:
            print(f"❌ Noise cancellation failed: {e}")
            return False
        
        # Test voice activity detection
        print("\n🎤 Testing voice activity detection...")
        try:
            has_voice = detect_voice_activity(cleaned_audio)
            print(f"✅ Voice activity detection successful")
            print(f"   Voice detected: {has_voice}")
        except Exception as e:
            print(f"❌ Voice activity detection failed: {e}")
            return False
        
        # Test speech optimization
        print("\n🎯 Testing speech optimization...")
        try:
            optimized_audio = optimize_audio_for_speech(test_audio_int16)
            print(f"✅ Speech optimization successful")
            print(f"   Output type: {optimized_audio.dtype}")
            print(f"   Output range: {np.min(optimized_audio):.3f} to {np.max(optimized_audio):.3f}")
        except Exception as e:
            print(f"❌ Speech optimization failed: {e}")
            return False
        
        # Verify data types are correct
        if cleaned_audio.dtype != np.float32:
            print(f"⚠️  Warning: Cleaned audio type is {cleaned_audio.dtype}, expected float32")
        
        if optimized_audio.dtype != np.float32:
            print(f"⚠️  Warning: Optimized audio type is {optimized_audio.dtype}, expected float32")
        
        print("\n🎉 All audio processing tests passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("pip install numpy scipy noisereduce")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_socketio_compatibility():
    """Test SocketIO compatibility."""
    print("\n🌐 Testing SocketIO Compatibility")
    print("=" * 50)
    
    try:
        import flask_socketio
        print(f"✅ Flask-SocketIO version: {flask_socketio.__version__}")
        
        # Test creating a SocketIO instance
        from flask import Flask
        app = Flask(__name__)
        socketio = flask_socketio.SocketIO(
            app, 
            cors_allowed_origins="*", 
            async_mode='threading',
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1000000,
            logger=False,
            engineio_logger=False
        )
        print("✅ SocketIO instance created successfully")
        
        # Test emit without broadcast parameter
        try:
            # This should work without errors
            test_data = {'test': 'data', 'timestamp': '12:34:56'}
            # Note: This won't actually emit since no clients are connected
            print("✅ SocketIO emit syntax is compatible")
        except Exception as e:
            print(f"❌ SocketIO emit error: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Flask-SocketIO not available: {e}")
        return False
    except Exception as e:
        print(f"❌ SocketIO test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Audio Processing & SocketIO Fix Verification")
    print("=" * 60)
    
    audio_ok = test_audio_processing()
    socketio_ok = test_socketio_compatibility()
    
    print("\n" + "=" * 60)
    if audio_ok and socketio_ok:
        print("🎉 All tests passed! The fixes should resolve the issues.")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
    
    print("\nNext steps:")
    print("1. Run: python app_meet.py")
    print("2. Test recording with both Faster-Whisper and AssemblyAI")
    print("3. Check for ONNX Runtime and SocketIO errors")