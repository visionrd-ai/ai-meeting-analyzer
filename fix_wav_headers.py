#!/usr/bin/env python3
"""
Fix WAV file headers to ensure compatibility with AssemblyAI.
"""

import os
import wave
import struct
import numpy as np
from pathlib import Path

def fix_wav_file(input_path, output_path=None):
    """Fix WAV file headers and format."""
    if output_path is None:
        output_path = input_path.replace('.wav', '_fixed.wav')
    
    print(f"🔧 Fixing: {input_path}")
    
    try:
        # Read the original file
        with wave.open(input_path, 'rb') as wav_in:
            # Get parameters
            channels = wav_in.getnchannels()
            sampwidth = wav_in.getsampwidth()
            framerate = wav_in.getframerate()
            frames = wav_in.getnframes()
            
            print(f"   Original: {channels}ch, {sampwidth*8}bit, {framerate}Hz, {frames} frames")
            
            # Read all frames
            audio_data = wav_in.readframes(frames)
        
        # Convert to numpy array
        if sampwidth == 1:
            dtype = np.uint8
        elif sampwidth == 2:
            dtype = np.int16
        elif sampwidth == 4:
            dtype = np.int32
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")
        
        audio_array = np.frombuffer(audio_data, dtype=dtype)
        
        # Convert to mono if stereo
        if channels == 2:
            audio_array = audio_array.reshape(-1, 2)
            audio_array = audio_array.mean(axis=1).astype(dtype)
            channels = 1
            print("   Converted stereo to mono")
        
        # Ensure 16-bit format
        if dtype != np.int16:
            if dtype == np.uint8:
                # Convert 8-bit unsigned to 16-bit signed
                audio_array = ((audio_array.astype(np.float32) - 128) / 128 * 32767).astype(np.int16)
            elif dtype == np.int32:
                # Convert 32-bit to 16-bit
                audio_array = (audio_array / 65536).astype(np.int16)
            
            sampwidth = 2
            print("   Converted to 16-bit")
        
        # Ensure 16kHz sample rate (standard for speech)
        if framerate != 16000:
            # Simple resampling (not perfect but works for testing)
            target_length = int(len(audio_array) * 16000 / framerate)
            indices = np.linspace(0, len(audio_array) - 1, target_length).astype(int)
            audio_array = audio_array[indices]
            framerate = 16000
            print(f"   Resampled to 16kHz")
        
        # Write the fixed file with proper headers
        with wave.open(output_path, 'wb') as wav_out:
            wav_out.setnchannels(channels)
            wav_out.setsampwidth(sampwidth)
            wav_out.setframerate(framerate)
            wav_out.writeframes(audio_array.tobytes())
        
        # Verify the output file
        with wave.open(output_path, 'rb') as wav_verify:
            verify_channels = wav_verify.getnchannels()
            verify_sampwidth = wav_verify.getsampwidth()
            verify_framerate = wav_verify.getframerate()
            verify_frames = wav_verify.getnframes()
            duration = verify_frames / verify_framerate
            
            print(f"   Fixed: {verify_channels}ch, {verify_sampwidth*8}bit, {verify_framerate}Hz, {verify_frames} frames")
            print(f"   Duration: {duration:.2f} seconds")
        
        return output_path
        
    except Exception as e:
        print(f"   ❌ Error fixing file: {e}")
        return None

def test_with_assemblyai(filepath):
    """Test the fixed file with AssemblyAI."""
    print(f"\n🧪 Testing with AssemblyAI: {os.path.basename(filepath)}")
    
    try:
        import requests
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        
        if not api_key:
            print("❌ No AssemblyAI API key")
            return False
        
        # Upload file
        print("📤 Uploading...")
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
            "speakers_expected": 2
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
        
        # Poll for results (simplified)
        import time
        polling_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        
        for _ in range(60):  # Wait up to 5 minutes
            response = requests.get(polling_endpoint, headers=headers)
            
            if response.status_code != 200:
                print(f"❌ Polling failed: {response.status_code}")
                return False
            
            result = response.json()
            status = result["status"]
            
            if status == "completed":
                print("✅ Transcription completed!")
                
                # Check for speaker diarization
                if "utterances" in result and result["utterances"]:
                    utterances = result["utterances"]
                    speakers = set(u["speaker"] for u in utterances)
                    
                    print(f"🎙️ Speaker diarization successful!")
                    print(f"   Speakers detected: {len(speakers)} ({list(speakers)})")
                    print(f"   Total utterances: {len(utterances)}")
                    
                    # Show sample
                    for utterance in utterances[:3]:
                        speaker = utterance["speaker"]
                        text = utterance["text"]
                        start = utterance["start"] / 1000
                        print(f"   [{start:.1f}s] Speaker {speaker}: {text[:60]}...")
                    
                    return True
                else:
                    print("⚠️ No speaker diarization data")
                    if result.get("text"):
                        print(f"   But got transcript: {result['text'][:100]}...")
                    return False
                
            elif status == "error":
                error = result.get("error", "Unknown error")
                print(f"❌ Transcription failed: {error}")
                return False
            
            print(f"📊 Status: {status}")
            time.sleep(5)
        
        print("❌ Timeout waiting for transcription")
        return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Fix recent WAV files and test."""
    print("🎯 WAV File Header Fixer")
    print("=" * 50)
    
    # Find recent recordings
    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        print("❌ No recordings directory")
        return
    
    audio_files = []
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith('.wav') and not file.endswith('_fixed.wav'):
                filepath = os.path.join(root, file)
                audio_files.append(filepath)
    
    if not audio_files:
        print("❌ No WAV files found")
        return
    
    print(f"📁 Found {len(audio_files)} WAV files")
    
    # Fix the most recent file
    latest_file = max(audio_files, key=os.path.getmtime)
    print(f"\n🔧 Fixing most recent file: {os.path.basename(latest_file)}")
    
    fixed_file = fix_wav_file(latest_file)
    
    if fixed_file:
        print(f"✅ Fixed file created: {os.path.basename(fixed_file)}")
        
        # Test with AssemblyAI
        test_with_assemblyai(fixed_file)
    else:
        print("❌ Failed to fix file")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()