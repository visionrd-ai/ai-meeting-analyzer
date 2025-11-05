#!/usr/bin/env python3
"""
Manual test of speaker diarization with direct file upload.
"""

import os
import requests
import time
import json
from dotenv import load_dotenv

def test_direct_assemblyai():
    """Test AssemblyAI directly without our wrapper."""
    load_dotenv()
    
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("❌ No AssemblyAI API key")
        return False
    
    print("🎯 Testing AssemblyAI Direct Upload")
    print("=" * 50)
    
    # Find a recent audio file
    recordings_dir = "recordings"
    audio_file = None
    
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith('.wav'):
                audio_file = os.path.join(root, file)
                break
        if audio_file:
            break
    
    if not audio_file:
        print("❌ No audio file found")
        return False
    
    print(f"📁 Using file: {audio_file}")
    
    # Step 1: Upload file
    print("📤 Uploading file...")
    
    headers = {"authorization": api_key}
    
    try:
        with open(audio_file, 'rb') as f:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f}
            )
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return False
        
        upload_url = response.json()["upload_url"]
        print(f"✅ Upload successful: {upload_url}")
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
    
    # Step 2: Request transcription with speaker diarization
    print("🎙️ Requesting transcription with speaker diarization...")
    
    transcript_request = {
        "audio_url": upload_url,
        "speaker_labels": True,
        "speakers_expected": 2  # Expecting 2 speakers (you and your wife)
    }
    
    headers["content-type"] = "application/json"
    
    try:
        response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            json=transcript_request,
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Transcription request failed: {response.status_code} - {response.text}")
            return False
        
        transcript_id = response.json()["id"]
        print(f"✅ Transcription started: {transcript_id}")
        
    except Exception as e:
        print(f"❌ Transcription request error: {e}")
        return False
    
    # Step 3: Poll for results
    print("⏳ Waiting for transcription to complete...")
    
    polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    
    while True:
        try:
            response = requests.get(polling_endpoint, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Polling failed: {response.status_code}")
                return False
            
            result = response.json()
            status = result["status"]
            
            print(f"📊 Status: {status}")
            
            if status == "completed":
                print("✅ Transcription completed!")
                
                # Check for speaker diarization
                if "utterances" in result and result["utterances"]:
                    print(f"🎙️ Speaker diarization successful!")
                    print(f"   Total utterances: {len(result['utterances'])}")
                    
                    # Show first few utterances
                    for i, utterance in enumerate(result["utterances"][:5]):
                        speaker = utterance["speaker"]
                        text = utterance["text"]
                        start = utterance["start"] / 1000  # Convert to seconds
                        
                        print(f"   [{start:.1f}s] Speaker {speaker}: {text[:80]}...")
                    
                    # Count unique speakers
                    speakers = set(u["speaker"] for u in result["utterances"])
                    print(f"   Unique speakers detected: {len(speakers)} ({list(speakers)})")
                    
                    return True
                else:
                    print("⚠️ No speaker diarization data found")
                    print("   Raw transcript available:", bool(result.get("text")))
                    if result.get("text"):
                        print(f"   Transcript: {result['text'][:200]}...")
                    return False
                
            elif status == "error":
                error = result.get("error", "Unknown error")
                print(f"❌ Transcription failed: {error}")
                return False
            
            time.sleep(5)  # Wait 5 seconds before polling again
            
        except Exception as e:
            print(f"❌ Polling error: {e}")
            return False

def create_test_audio():
    """Create a simple test audio file for testing."""
    print("\n🎵 Creating Test Audio File")
    print("=" * 50)
    
    try:
        import numpy as np
        import wave
        
        # Create a simple test audio with two different tones
        sample_rate = 16000
        duration = 30  # 30 seconds
        
        # Generate two different frequency tones to simulate different speakers
        t = np.linspace(0, duration, sample_rate * duration, False)
        
        # Speaker 1: 440 Hz tone for first 15 seconds
        speaker1 = np.sin(2 * np.pi * 440 * t[:sample_rate * 15])
        
        # Speaker 2: 880 Hz tone for last 15 seconds  
        speaker2 = np.sin(2 * np.pi * 880 * t[:sample_rate * 15])
        
        # Combine
        audio = np.concatenate([speaker1, speaker2])
        
        # Convert to 16-bit integers
        audio = (audio * 32767).astype(np.int16)
        
        # Save as WAV
        test_file = "test_speaker_diarization.wav"
        with wave.open(test_file, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio.tobytes())
        
        print(f"✅ Test audio created: {test_file}")
        print(f"   Duration: {duration} seconds")
        print(f"   Sample rate: {sample_rate} Hz")
        
        return test_file
        
    except ImportError:
        print("❌ NumPy not available - cannot create test audio")
        return None
    except Exception as e:
        print(f"❌ Error creating test audio: {e}")
        return None

def main():
    """Main function."""
    print("🎯 Manual Speaker Diarization Test")
    print("=" * 60)
    
    # Test with existing files first
    success = test_direct_assemblyai()
    
    if not success:
        print("\n" + "=" * 60)
        print("💡 TROUBLESHOOTING SUGGESTIONS")
        print("=" * 60)
        print("1. The audio file might be corrupted or have header issues")
        print("2. Try recording a new conversation with clear speech")
        print("3. Make sure you and your wife speak distinctly")
        print("4. Each person should speak for at least 5-10 seconds at a time")
        print("5. Avoid overlapping speech")
        print("6. Use a good quality microphone")
        print("\n🎙️ For your next recording:")
        print("   - Have a clear conversation")
        print("   - Take turns speaking")
        print("   - Speak clearly and distinctly")
        print("   - Record for at least 1-2 minutes")
        print("   - Avoid background noise")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Test cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()