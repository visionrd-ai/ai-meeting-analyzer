#!/usr/bin/env python3
"""
Fix audio format issues for speaker diarization.
"""

import os
import wave
import subprocess
from pathlib import Path

def check_audio_file(filepath):
    """Check if audio file is valid."""
    print(f"🔍 Checking: {filepath}")
    
    try:
        # Check file size
        file_size = os.path.getsize(filepath)
        print(f"   File size: {file_size / 1024 / 1024:.2f} MB")
        
        # Try to open with wave module
        if filepath.endswith('.wav'):
            try:
                with wave.open(filepath, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    duration = frames / sample_rate
                    
                    print(f"   ✅ Valid WAV file")
                    print(f"   Duration: {duration:.2f} seconds")
                    print(f"   Sample rate: {sample_rate} Hz")
                    print(f"   Channels: {channels}")
                    print(f"   Frames: {frames}")
                    
                    if duration < 10:
                        print(f"   ⚠️ File is very short ({duration:.2f}s) - may not work well for speaker diarization")
                    
                    return True
                    
            except Exception as e:
                print(f"   ❌ Invalid WAV file: {e}")
                return False
        else:
            print(f"   ⚠️ Non-WAV file - may need conversion")
            return True
            
    except Exception as e:
        print(f"   ❌ Error checking file: {e}")
        return False

def convert_audio_to_proper_format(input_path, output_path):
    """Convert audio to proper format for AssemblyAI."""
    try:
        print(f"🔄 Converting {input_path} to proper format...")
        
        # Use ffmpeg to convert to proper WAV format
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',      # Mono
            '-c:a', 'pcm_s16le',  # 16-bit PCM
            '-y',            # Overwrite output
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ Conversion successful")
            return True
        else:
            print(f"   ❌ Conversion failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("   ❌ ffmpeg not found. Please install ffmpeg:")
        print("      Windows: Download from https://ffmpeg.org/")
        print("      Or use: winget install ffmpeg")
        return False
    except Exception as e:
        print(f"   ❌ Conversion error: {e}")
        return False

def fix_recent_recordings():
    """Fix recent recording files."""
    print("🔧 Fixing Recent Audio Files")
    print("=" * 50)
    
    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        print("❌ No recordings directory found")
        return False
    
    fixed_files = []
    
    # Find recent audio files
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith(('.wav', '.mp3', '.m4a')):
                filepath = os.path.join(root, file)
                
                print(f"\n📁 Processing: {file}")
                
                # Check if file is valid
                is_valid = check_audio_file(filepath)
                
                if not is_valid or file.endswith(('.mp3', '.m4a')):
                    # Convert to proper format
                    base_name = os.path.splitext(file)[0]
                    fixed_filename = f"{base_name}_fixed.wav"
                    fixed_filepath = os.path.join(root, fixed_filename)
                    
                    if convert_audio_to_proper_format(filepath, fixed_filepath):
                        fixed_files.append(fixed_filepath)
                        print(f"   ✅ Fixed file saved as: {fixed_filename}")
                    else:
                        print(f"   ❌ Could not fix: {file}")
                else:
                    print(f"   ✅ File is already in good format")
                    fixed_files.append(filepath)
    
    return fixed_files

def test_fixed_file_with_assemblyai(filepath):
    """Test a fixed file with AssemblyAI."""
    print(f"\n🧪 Testing fixed file with AssemblyAI: {os.path.basename(filepath)}")
    
    try:
        from speaker_diarization import AssemblyAISpeakerDiarization
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        
        if not api_key:
            print("❌ No AssemblyAI API key")
            return False
        
        diarizer = AssemblyAISpeakerDiarization(api_key)
        
        print("🚀 Starting test transcription...")
        result = diarizer.process_audio_file(filepath)
        
        if result.get('success'):
            summary = result.get('summary', {})
            print(f"✅ Success!")
            print(f"   Speakers detected: {summary.get('total_speakers', 0)}")
            print(f"   Duration: {summary.get('total_duration', 0)} seconds")
            print(f"   Words: {summary.get('total_words', 0)}")
            
            # Show sample segments
            segments = result.get('segments', [])
            if segments:
                print(f"\n📝 Sample segments:")
                for segment in segments[:3]:
                    print(f"   {segment['speaker']}: {segment['text'][:80]}...")
            
            return True
        else:
            print(f"❌ Failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Main function."""
    print("🎯 Audio Format Fixer for Speaker Diarization")
    print("=" * 60)
    
    # Fix recent recordings
    fixed_files = fix_recent_recordings()
    
    if fixed_files:
        print(f"\n✅ Fixed {len(fixed_files)} audio files")
        
        # Test with the most recent fixed file
        if fixed_files:
            test_file = fixed_files[-1]  # Most recent
            test_fixed_file_with_assemblyai(test_file)
    else:
        print("\n❌ No files were fixed")
    
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS:")
    print("=" * 60)
    print("1. Make sure your recordings are at least 30 seconds long")
    print("2. Ensure there are actually multiple speakers talking")
    print("3. Speakers should have distinct voices (male/female works best)")
    print("4. Avoid background music or noise")
    print("5. Each speaker should talk for at least a few seconds at a time")
    print("\n🎙️ For best results:")
    print("   - Record a conversation between 2-4 people")
    print("   - Each person should speak for 10+ seconds at a time")
    print("   - Minimize overlapping speech")
    print("   - Use good quality microphone")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()