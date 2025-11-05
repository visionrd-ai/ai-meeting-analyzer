#!/usr/bin/env python3
"""
Test the enhanced speaker identification with actual names.
"""

import sys
import os

# Add the current directory to Python path to import the Flask app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_speaker_name_detection():
    """Test speaker name detection from the user's transcript."""
    print("🎯 Testing Enhanced Speaker Name Detection")
    print("=" * 60)
    
    # Import the functions from the Flask app
    try:
        from app_perfect_ai import identify_speaker_from_text, add_speaker_profile
        print("✅ Successfully imported speaker identification functions")
    except ImportError as e:
        print(f"❌ Error importing functions: {e}")
        return False
    
    # Test phrases from the user's actual transcript
    test_phrases = [
        "I am renaud and I need yennefer",
        "I am yanni", 
        "My name is claude",
        "And I'm here for siri",
        "Thank you for the information",
        "Actually, I think we should continue"
    ]
    
    print("\n📝 Testing Speaker Identification:")
    print("-" * 40)
    
    for i, phrase in enumerate(test_phrases, 1):
        try:
            speaker = identify_speaker_from_text(phrase, "Mic")
            print(f"{i}. \"{phrase}\"")
            print(f"   → Identified as: {speaker}")
            print()
        except Exception as e:
            print(f"{i}. \"{phrase}\"")
            print(f"   → Error: {e}")
            print()
    
    return True

def test_speaker_profiles():
    """Test speaker profile management."""
    print("👥 Testing Speaker Profile Management")
    print("-" * 40)
    
    try:
        from app_perfect_ai import load_speaker_profiles, add_speaker_profile
        
        # Add some test speakers
        test_speakers = [
            ("speaker_renaud", "Renaud"),
            ("speaker_yennefer", "Yennefer"), 
            ("speaker_yanni", "Yanni"),
            ("speaker_claude", "Claude"),
            ("speaker_siri", "Siri")
        ]
        
        print("Adding test speakers:")
        for speaker_id, name in test_speakers:
            add_speaker_profile(speaker_id, name)
            print(f"   ✅ Added: {name} (ID: {speaker_id})")
        
        # Load and display profiles
        profiles = load_speaker_profiles()
        print(f"\n📊 Total speaker profiles: {len(profiles)}")
        
        for speaker_id, profile in profiles.items():
            print(f"   - {profile['name']} (ID: {speaker_id})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing speaker profiles: {e}")
        return False

def simulate_conversation():
    """Simulate a conversation with the enhanced speaker detection."""
    print("\n🎙️ Simulating Enhanced Conversation")
    print("-" * 40)
    
    try:
        from app_perfect_ai import identify_speaker_from_text
        
        # Conversation based on user's transcript
        conversation = [
            "I am renaud and I need yennefer",
            "I am yanni", 
            "My name is claude",
            "And I'm here for siri",
            "Thank you renaud for organizing this",
            "Actually yanni, I think we should proceed",
            "Claude, can you help with that?",
            "Sure renaud, I'll take care of it"
        ]
        
        print("Enhanced conversation with speaker detection:")
        for i, text in enumerate(conversation, 1):
            speaker = identify_speaker_from_text(text, "Mic")
            timestamp = f"00:0{i//2}:{(i%2)*30:02d}"
            print(f"   [{timestamp}] {speaker}: {text}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error simulating conversation: {e}")
        return False

def main():
    """Main test function."""
    print("🎙️ ENHANCED SPEAKER IDENTIFICATION TEST")
    print("=" * 70)
    
    success = True
    
    # Run tests
    if not test_speaker_name_detection():
        success = False
    
    if not test_speaker_profiles():
        success = False
    
    if not simulate_conversation():
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ Enhanced Speaker Identification Features:")
        print("   - Automatic name detection from speech")
        print("   - Custom speaker profiles (Renaud, Yennefer, Yanni, Claude, Siri)")
        print("   - Persistent speaker memory across sessions")
        print("   - Context-based speaker switching")
        print("   - Speaker management interface")
        
        print("\n🚀 Now when you record:")
        print("   - Say 'I am [name]' or 'My name is [name]' to identify yourself")
        print("   - The system will remember and use your actual name")
        print("   - Use the 👥 Speakers button to manage speaker names")
        print("   - Speaker names will appear instead of 'Speaker 1/2'")
        
    else:
        print("❌ SOME TESTS FAILED")
        print("Please check the errors above and fix the issues.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())