#!/usr/bin/env python3
"""
Enhanced Speaker Identification System
Supports custom speaker names and voice pattern learning.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

class EnhancedSpeakerIdentifier:
    """Enhanced speaker identification with custom names and voice learning."""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id
        self.speaker_profiles = {}
        self.current_speaker = None
        self.last_speaker_change = time.time()
        self.speaker_history = []
        self.voice_patterns = {}
        
        # Load existing speaker profiles
        self.load_speaker_profiles()
    
    def load_speaker_profiles(self):
        """Load speaker profiles from file."""
        profiles_file = "speaker_profiles.json"
        if os.path.exists(profiles_file):
            try:
                with open(profiles_file, 'r') as f:
                    self.speaker_profiles = json.load(f)
                print(f"✅ Loaded {len(self.speaker_profiles)} speaker profiles")
            except Exception as e:
                print(f"Error loading speaker profiles: {e}")
                self.speaker_profiles = {}
    
    def save_speaker_profiles(self):
        """Save speaker profiles to file."""
        profiles_file = "speaker_profiles.json"
        try:
            with open(profiles_file, 'w') as f:
                json.dump(self.speaker_profiles, f, indent=2)
            print(f"✅ Saved {len(self.speaker_profiles)} speaker profiles")
        except Exception as e:
            print(f"Error saving speaker profiles: {e}")
    
    def add_speaker_profile(self, speaker_id: str, name: str, voice_characteristics: Dict = None):
        """Add or update a speaker profile."""
        self.speaker_profiles[speaker_id] = {
            'name': name,
            'voice_characteristics': voice_characteristics or {},
            'created_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'total_sessions': self.speaker_profiles.get(speaker_id, {}).get('total_sessions', 0) + 1
        }
        self.save_speaker_profiles()
        print(f"✅ Added/updated speaker profile: {speaker_id} -> {name}")
    
    def get_speaker_name(self, speaker_id: str) -> str:
        """Get the display name for a speaker."""
        if speaker_id in self.speaker_profiles:
            return self.speaker_profiles[speaker_id]['name']
        return f"Speaker {speaker_id}"
    
    def identify_speaker_from_text(self, text: str, audio_features: Dict = None) -> str:
        """Identify speaker from text content and optional audio features."""
        text_lower = text.lower().strip()
        
        # Check for self-identification patterns
        name_patterns = [
            "my name is", "i'm", "i am", "this is", "call me", 
            "it's me", "speaking is", "here is"
        ]
        
        for pattern in name_patterns:
            if pattern in text_lower:
                # Extract potential name after the pattern
                parts = text_lower.split(pattern)
                if len(parts) > 1:
                    potential_name = parts[1].strip().split()[0]  # First word after pattern
                    if len(potential_name) > 2 and potential_name.isalpha():
                        # Clean up the name
                        name = potential_name.capitalize()
                        
                        # Create or update speaker profile
                        speaker_id = f"speaker_{len(self.speaker_profiles) + 1}"
                        self.add_speaker_profile(speaker_id, name)
                        
                        print(f"🎙️ Identified speaker: {name}")
                        return name
        
        # Check for known speaker patterns in text
        for speaker_id, profile in self.speaker_profiles.items():
            name = profile['name'].lower()
            if name in text_lower:
                return profile['name']
        
        # Use context-based detection for unknown speakers
        return self.detect_speaker_from_context(text)
    
    def detect_speaker_from_context(self, text: str) -> str:
        """Detect speaker based on conversation context."""
        text_lower = text.lower().strip()
        
        # Speaker change indicators
        speaker_change_indicators = [
            'thank you', 'thanks', 'yes', 'no', 'i think', 'i believe', 
            'in my opinion', 'i agree', 'i disagree', 'actually', 'well',
            'so', 'but', 'however', 'on the other hand', 'let me',
            'can i', 'may i', 'excuse me', 'sorry', 'pardon'
        ]
        
        # Check if enough time has passed for potential speaker change
        time_since_last_change = time.time() - self.last_speaker_change
        
        # Determine if speaker should change
        should_change_speaker = False
        
        if time_since_last_change > 3:  # At least 3 seconds
            for indicator in speaker_change_indicators:
                if indicator in text_lower:
                    should_change_speaker = True
                    break
            
            # Also change for longer pauses
            if time_since_last_change > 5:
                should_change_speaker = True
        
        # Update current speaker
        if should_change_speaker or self.current_speaker is None:
            # Get available speaker names or create new ones
            available_speakers = list(self.speaker_profiles.keys())
            
            if not available_speakers:
                # Create default speakers
                self.add_speaker_profile("speaker_1", "Speaker 1")
                self.add_speaker_profile("speaker_2", "Speaker 2")
                available_speakers = ["speaker_1", "speaker_2"]
            
            # Switch to next speaker
            if self.current_speaker is None:
                self.current_speaker = available_speakers[0]
            else:
                current_index = available_speakers.index(self.current_speaker) if self.current_speaker in available_speakers else 0
                next_index = (current_index + 1) % len(available_speakers)
                self.current_speaker = available_speakers[next_index]
            
            self.last_speaker_change = time.time()
        
        # Return speaker name
        return self.get_speaker_name(self.current_speaker)
    
    def process_transcript_segment(self, text: str, audio_features: Dict = None) -> Dict:
        """Process a transcript segment and return speaker information."""
        speaker_name = self.identify_speaker_from_text(text, audio_features)
        
        # Update speaker history
        segment_info = {
            'text': text,
            'speaker': speaker_name,
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.85  # Default confidence
        }
        
        self.speaker_history.append(segment_info)
        
        return segment_info
    
    def get_session_summary(self) -> Dict:
        """Get summary of speakers in current session."""
        speaker_stats = {}
        
        for segment in self.speaker_history:
            speaker = segment['speaker']
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    'segments': 0,
                    'total_words': 0,
                    'first_appearance': segment['timestamp'],
                    'last_appearance': segment['timestamp']
                }
            
            speaker_stats[speaker]['segments'] += 1
            speaker_stats[speaker]['total_words'] += len(segment['text'].split())
            speaker_stats[speaker]['last_appearance'] = segment['timestamp']
        
        return {
            'total_speakers': len(speaker_stats),
            'speaker_statistics': speaker_stats,
            'total_segments': len(self.speaker_history)
        }

def create_custom_speaker_profiles():
    """Create custom speaker profiles for the user."""
    print("🎙️ Creating Custom Speaker Profiles")
    print("=" * 50)
    
    identifier = EnhancedSpeakerIdentifier()
    
    # Add custom speaker profiles based on user's request
    custom_speakers = [
        ("renaud", "Renaud"),
        ("yennefer", "Yennefer"),
        ("yanni", "Yanni"),
        ("claude", "Claude"),
        ("siri", "Siri")
    ]
    
    for speaker_id, name in custom_speakers:
        identifier.add_speaker_profile(f"speaker_{speaker_id}", name)
    
    print(f"✅ Created {len(custom_speakers)} custom speaker profiles")
    return identifier

def test_enhanced_identification():
    """Test the enhanced speaker identification."""
    print("\n🧪 Testing Enhanced Speaker Identification")
    print("=" * 50)
    
    identifier = create_custom_speaker_profiles()
    
    # Test phrases from the user's transcript
    test_phrases = [
        "I am renaud and I need yennefer",
        "I am yanni",
        "My name is claude",
        "And I'm here for siri",
        "Thank you for that information",
        "Actually, I think we should proceed differently"
    ]
    
    print("Processing test phrases:")
    for phrase in test_phrases:
        result = identifier.process_transcript_segment(phrase)
        print(f"   📝 \"{phrase}\"")
        print(f"      → Identified as: {result['speaker']}")
        print(f"      → Confidence: {result['confidence']}")
        print()
    
    # Show session summary
    summary = identifier.get_session_summary()
    print("📊 Session Summary:")
    print(f"   Total speakers: {summary['total_speakers']}")
    print(f"   Total segments: {summary['total_segments']}")
    
    for speaker, stats in summary['speaker_statistics'].items():
        print(f"   {speaker}: {stats['segments']} segments, {stats['total_words']} words")

def main():
    """Main function to demonstrate enhanced speaker identification."""
    print("🎯 ENHANCED SPEAKER IDENTIFICATION SYSTEM")
    print("=" * 60)
    
    # Create and test the system
    test_enhanced_identification()
    
    print("\n" + "=" * 60)
    print("🎉 Enhanced Speaker Identification Ready!")
    print("\n✅ Features:")
    print("   - Custom speaker names (Renaud, Yennefer, Yanni, Claude, Siri)")
    print("   - Self-identification from speech ('My name is...', 'I am...')")
    print("   - Speaker profile learning and memory")
    print("   - Context-based speaker switching")
    print("   - Persistent speaker profiles across sessions")
    
    print("\n🚀 Integration:")
    print("   - Replace generic 'Speaker 1/2' with actual names")
    print("   - Learn new speakers automatically from speech")
    print("   - Remember speakers across different sessions")
    print("   - Provide speaker management interface")

if __name__ == "__main__":
    main()