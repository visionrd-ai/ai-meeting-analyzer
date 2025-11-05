#!/usr/bin/env python3
"""
Test AssemblyAI speaker diarization configuration and functionality.
"""

import os
from dotenv import load_dotenv

def test_assemblyai_config():
    """Test AssemblyAI configuration."""
    print("🔍 Testing AssemblyAI Configuration")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check API key
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("❌ ASSEMBLYAI_API_KEY not found in .env file")
        print("   Please add: ASSEMBLYAI_API_KEY=your-api-key-here")
        return False
    
    print(f"✅ AssemblyAI API key found: {api_key[:10]}...")
    
    # Test API connection
    try:
        import requests
        
        headers = {
            "authorization": api_key,
            "content-type": "application/json"
        }
        
        # Test with a simple request
        response = requests.get(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ AssemblyAI API connection successful")
            return True
        else:
            print(f"❌ AssemblyAI API error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ AssemblyAI connection failed: {e}")
        return False

def test_speaker_diarization_module():
    """Test speaker diarization module."""
    print("\n🎙️ Testing Speaker Diarization Module")
    print("=" * 50)
    
    try:
        from speaker_diarization import AssemblyAISpeakerDiarization
        print("✅ Speaker diarization module imported successfully")
        
        # Test initialization
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if api_key:
            diarizer = AssemblyAISpeakerDiarization(api_key)
            print("✅ Speaker diarization initialized successfully")
            return True
        else:
            print("❌ Cannot initialize - no API key")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        return False

def check_recent_recordings():
    """Check for recent recording files."""
    print("\n📁 Checking Recent Recordings")
    print("=" * 50)
    
    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        print("❌ No recordings directory found")
        return []
    
    audio_files = []
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith(('.wav', '.mp3', '.m4a')):
                filepath = os.path.join(root, file)
                file_size = os.path.getsize(filepath)
                audio_files.append({
                    'path': filepath,
                    'size_mb': round(file_size / 1024 / 1024, 2),
                    'name': file
                })
    
    if audio_files:
        print(f"✅ Found {len(audio_files)} audio files:")
        for i, file in enumerate(audio_files[-3:]):  # Show last 3
            print(f"   {i+1}. {file['name']} ({file['size_mb']} MB)")
        return audio_files
    else:
        print("❌ No audio files found")
        return []

def test_with_sample_audio():
    """Test speaker diarization with a sample audio file."""
    print("\n🧪 Testing with Sample Audio")
    print("=" * 50)
    
    audio_files = check_recent_recordings()
    if not audio_files:
        print("⚠️ No audio files to test with")
        return False
    
    # Use the most recent file
    test_file = audio_files[-1]
    print(f"🎵 Testing with: {test_file['name']}")
    
    try:
        from speaker_diarization import AssemblyAISpeakerDiarization
        
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not api_key:
            print("❌ No API key available")
            return False
        
        diarizer = AssemblyAISpeakerDiarization(api_key)
        
        print("🚀 Starting speaker diarization test...")
        print("   This may take 1-2 minutes...")
        
        result = diarizer.process_audio_file(test_file['path'])
        
        if result.get('success'):
            summary = result.get('summary', {})
            print(f"✅ Speaker diarization completed!")
            print(f"   Total speakers detected: {summary.get('total_speakers', 0)}")
            print(f"   Total duration: {summary.get('total_duration', 0)} seconds")
            print(f"   Confidence: {summary.get('confidence_score', 0):.2f}")
            
            # Show first few segments
            segments = result.get('segments', [])
            if segments:
                print(f"\n📝 First few segments:")
                for i, segment in enumerate(segments[:3]):
                    print(f"   {segment['speaker']}: {segment['text'][:100]}...")
            
            return True
        else:
            print(f"❌ Speaker diarization failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🎯 AssemblyAI Speaker Diarization Diagnostic")
    print("=" * 60)
    
    tests = [
        ("AssemblyAI Configuration", test_assemblyai_config),
        ("Speaker Diarization Module", test_speaker_diarization_module),
        ("Sample Audio Test", test_with_sample_audio)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! Speaker diarization should work.")
    else:
        print("❌ Some tests failed. Check the issues above.")
        print("\n💡 Common Solutions:")
        print("   1. Add ASSEMBLYAI_API_KEY to your .env file")
        print("   2. Get API key from: https://www.assemblyai.com/")
        print("   3. Make sure you have recorded some audio files")
        print("   4. Check your internet connection")
        print("   5. Ensure audio files are not corrupted")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()