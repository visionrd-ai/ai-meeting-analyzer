#!/usr/bin/env python3
"""
Create a test conversation audio file for speaker diarization testing.
"""

import os
import numpy as np
import wave
import requests
import time
from dotenv import load_dotenv

def create_test_conversation():
    """Create a test audio file with two distinct speakers."""
    print("🎵 Creating Test Conversation Audio")
    print("=" * 50)
    
    try:
        # Audio parameters
        sample_rate = 16000
        duration_per_speaker = 10  # 10 seconds each
        total_duration = duration_per_speaker * 4  # 40 seconds total
        
        # Create time array
        t = np.linspace(0, total_duration, sample_rate * total_duration, False)
        
        # Create different "voices" using different frequencies and patterns
        audio_segments = []
        
        # Speaker 1: Lower frequency pattern (simulating male voice)
        for i in range(2):  # Speaker 1 talks twice
            start_time = i * duration_per_speaker * 2
            end_time = start_time + duration_per_speaker
            
            segment_t = t[start_time * sample_rate:end_time * sample_rate]
            
            # Create a complex waveform that sounds more like speech
            voice1 = (
                0.3 * np.sin(2 * np.pi * 150 * segment_t) +  # Fundamental frequency
                0.2 * np.sin(2 * np.pi * 300 * segment_t) +  # First harmonic
                0.1 * np.sin(2 * np.pi * 450 * segment_t) +  # Second harmonic
                0.05 * np.random.normal(0, 1, len(segment_t))  # Add some noise
            )
            
            # Add amplitude modulation to simulate speech patterns
            modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * segment_t)  # 3 Hz modulation
            voice1 *= modulation
            
            audio_segments.append(voice1)
        
        # Speaker 2: Higher frequency pattern (simulating female voice)
        for i in range(2):  # Speaker 2 talks twice
            start_time = i * duration_per_speaker * 2 + duration_per_speaker
            end_time = start_time + duration_per_speaker
            
            segment_t = t[start_time * sample_rate:end_time * sample_rate]
            
            # Create a different complex waveform
            voice2 = (
                0.3 * np.sin(2 * np.pi * 220 * segment_t) +  # Higher fundamental
                0.2 * np.sin(2 * np.pi * 440 * segment_t) +  # First harmonic
                0.1 * np.sin(2 * np.pi * 660 * segment_t) +  # Second harmonic
                0.05 * np.random.normal(0, 1, len(segment_t))  # Add some noise
            )
            
            # Different modulation pattern
            modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * segment_t)  # 4 Hz modulation
            voice2 *= modulation
            
            audio_segments.append(voice2)
        
        # Combine all segments in order: Speaker1, Speaker2, Speaker1, Speaker2
        final_audio = np.concatenate([
            audio_segments[0],  # Speaker 1 - first segment
            audio_segments[2],  # Speaker 2 - first segment  
            audio_segments[1],  # Speaker 1 - second segment
            audio_segments[3]   # Speaker 2 - second segment
        ])
        
        # Normalize and convert to 16-bit integers
        final_audio = final_audio / np.max(np.abs(final_audio))  # Normalize
        final_audio = (final_audio * 0.8 * 32767).astype(np.int16)  # Convert to int16
        
        # Save as WAV file
        test_file = "test_conversation.wav"
        with wave.open(test_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(final_audio.tobytes())
        
        print(f"✅ Test conversation created: {test_file}")
        print(f"   Duration: {total_duration} seconds")
        print(f"   Sample rate: {sample_rate} Hz")
        print(f"   Format: 16-bit mono WAV")
        print(f"   Pattern: Speaker1 (0-10s), Speaker2 (10-20s), Speaker1 (20-30s), Speaker2 (30-40s)")
        
        return test_file
        
    except Exception as e:
        print(f"❌ Error creating test audio: {e}")
        return None

def test_with_assemblyai(filepath):
    """Test the file with AssemblyAI speaker diarization."""
    print(f"\n🧪 Testing with AssemblyAI: {os.path.basename(filepath)}")
    
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    if not api_key:
        print("❌ No AssemblyAI API key")
        return False
    
    try:
        # Upload file
        print("📤 Uploading test file...")
        headers = {"authorization": api_key}
        
        with open(filepath, 'rb') as f:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f}
            )
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return False
        
        upload_url = response.json()["upload_url"]
        print(f"✅ Upload successful")
        
        # Request transcription with speaker diarization
        print("🎙️ Requesting speaker diarization...")
        
        transcript_request = {
            "audio_url": upload_url,
            "speaker_labels": True,
            "speakers_expected": 2,
            "language_code": "en"
        }
        
        headers["content-type"] = "application/json"
        
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
        
        # Poll for results
        print("⏳ Waiting for results...")
        polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        
        for attempt in range(60):  # Wait up to 5 minutes
            response = requests.get(polling_endpoint, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Polling failed: {response.status_code}")
                return False
            
            result = response.json()
            status = result["status"]
            
            if status == "completed":
                print("✅ Transcription completed!")
                
                # Check results
                if "utterances" in result and result["utterances"]:
                    utterances = result["utterances"]
                    speakers = set(u["speaker"] for u in utterances)
                    
                    print(f"🎙️ SUCCESS! Speaker diarization worked!")
                    print(f"   Speakers detected: {len(speakers)} ({list(speakers)})")
                    print(f"   Total utterances: {len(utterances)}")
                    
                    # Show timeline
                    print(f"\n📝 Speaker Timeline:")
                    for utterance in utterances:
                        speaker = utterance["speaker"]
                        start = utterance["start"] / 1000
                        end = utterance["end"] / 1000
                        text = utterance["text"]
                        print(f"   [{start:.1f}s-{end:.1f}s] Speaker {speaker}: {text}")
                    
                    return True
                else:
                    print("⚠️ No speaker diarization data found")
                    if result.get("text"):
                        print(f"   Raw transcript: {result['text']}")
                    return False
                
            elif status == "error":
                error = result.get("error", "Unknown error")
                print(f"❌ Transcription failed: {error}")
                return False
            
            if attempt % 6 == 0:  # Print status every 30 seconds
                print(f"📊 Status: {status} (attempt {attempt + 1}/60)")
            
            time.sleep(5)
        
        print("❌ Timeout waiting for transcription")
        return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Main function."""
    print("🎯 Speaker Diarization Test with Clean Audio")
    print("=" * 60)
    
    # Create test conversation
    test_file = create_test_conversation()
    
    if test_file:
        # Test with AssemblyAI
        success = test_with_assemblyai(test_file)
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 SUCCESS! Speaker diarization is working!")
            print("=" * 60)
            print("The issue was with your recorded audio files.")
            print("For your next recording with your wife:")
            print("1. Make sure you both speak clearly")
            print("2. Take turns speaking (avoid overlapping)")
            print("3. Each person should speak for at least 5-10 seconds")
            print("4. Record for at least 1-2 minutes total")
            print("5. Use a good quality microphone")
            print("6. Minimize background noise")
        else:
            print("\n" + "=" * 60)
            print("❌ Speaker diarization still not working")
            print("=" * 60)
            print("This might be an issue with:")
            print("1. AssemblyAI API key or account")
            print("2. Network connectivity")
            print("3. AssemblyAI service availability")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Test cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()