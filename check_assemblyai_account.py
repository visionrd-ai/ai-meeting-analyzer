#!/usr/bin/env python3
"""
Check AssemblyAI account status and API key validity.
"""

import requests
import os
from dotenv import load_dotenv

def check_api_key():
    """Check if the API key is valid and get account info."""
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    if not api_key:
        print("❌ No ASSEMBLYAI_API_KEY found in .env file")
        return False
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    headers = {"authorization": api_key}
    
    try:
        # Test basic API access
        print("🔍 Testing API access...")
        response = requests.get(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            timeout=10
        )
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API key is valid and working")
            
            # Try to get account info if available
            try:
                data = response.json()
                print(f"📋 Response data: {len(data.get('transcripts', []))} transcripts found")
            except:
                print("📋 Valid response received")
            
            return True
            
        elif response.status_code == 401:
            print("❌ API key is invalid or expired")
            print("   Please check your API key at: https://www.assemblyai.com/app/account")
            return False
            
        elif response.status_code == 403:
            print("❌ API key doesn't have required permissions")
            print("   Make sure your account has access to speaker diarization")
            return False
            
        else:
            print(f"⚠️ Unexpected response: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out - check your internet connection")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - check your internet connection")
        return False
    except Exception as e:
        print(f"❌ Error checking API key: {e}")
        return False

def test_simple_upload():
    """Test a simple file upload without transcription."""
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    if not api_key:
        return False
    
    print("\n📤 Testing file upload capability...")
    
    # Create a minimal test file
    test_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    
    with open("minimal_test.wav", "wb") as f:
        f.write(test_content)
    
    try:
        headers = {"authorization": api_key}
        
        with open("minimal_test.wav", "rb") as f:
            response = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                files={"file": f},
                timeout=30
            )
        
        print(f"📊 Upload response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            upload_url = data.get("upload_url")
            print(f"✅ Upload successful: {upload_url[:50]}...")
            return True
        else:
            print(f"❌ Upload failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists("minimal_test.wav"):
            os.remove("minimal_test.wav")

def check_account_limits():
    """Check if there are any account limitations."""
    print("\n💳 Checking Account Status...")
    
    load_dotenv()
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    if not api_key:
        return False
    
    headers = {"authorization": api_key}
    
    try:
        # Get recent transcripts to check account activity
        response = requests.get(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            params={"limit": 5},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            transcripts = data.get("transcripts", [])
            
            print(f"📊 Recent transcripts: {len(transcripts)}")
            
            if transcripts:
                for i, transcript in enumerate(transcripts[:3]):
                    status = transcript.get("status", "unknown")
                    created = transcript.get("created", "unknown")
                    print(f"   {i+1}. Status: {status}, Created: {created}")
            else:
                print("   No recent transcripts found")
            
            return True
        else:
            print(f"❌ Cannot check account: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking account: {e}")
        return False

def main():
    """Main diagnostic function."""
    print("🎯 AssemblyAI Account & API Key Diagnostic")
    print("=" * 60)
    
    # Check API key
    api_valid = check_api_key()
    
    if api_valid:
        # Test upload capability
        upload_works = test_simple_upload()
        
        # Check account status
        account_ok = check_account_limits()
        
        print("\n" + "=" * 60)
        print("📊 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        if api_valid and upload_works:
            print("✅ API key and upload functionality working")
            print("\n💡 The issue might be:")
            print("1. Speaker diarization feature not enabled on your account")
            print("2. Audio files need to contain actual speech (not tones)")
            print("3. Files need to be longer (try 2+ minutes)")
            print("4. Need multiple distinct speakers")
            print("\n🎙️ For your next recording:")
            print("   - Record a real conversation with your wife")
            print("   - Each person should speak for 10+ seconds at a time")
            print("   - Avoid overlapping speech")
            print("   - Record for at least 2 minutes")
            print("   - Use clear, distinct voices")
        else:
            print("❌ API or upload issues detected")
            print("\n💡 Solutions:")
            print("1. Check your API key at: https://www.assemblyai.com/app/account")
            print("2. Verify your account has speaker diarization enabled")
            print("3. Check your internet connection")
            print("4. Try generating a new API key")
    else:
        print("\n❌ API key issues detected")
        print("Please check your AssemblyAI account and API key")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Diagnostic cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()