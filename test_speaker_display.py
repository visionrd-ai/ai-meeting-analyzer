#!/usr/bin/env python3
"""
Test script to simulate speaker diarization data and verify display functionality.
"""

import json
import requests
import time
from datetime import datetime

def create_test_speaker_data():
    """Create test speaker diarization data."""
    return {
        "success": True,
        "segments": [
            {
                "speaker": "Speaker 1",
                "text": "Hello everyone, welcome to today's meeting. I'd like to start by reviewing our agenda.",
                "start_time": 0,
                "end_time": 5000,
                "start_formatted": "00:00:00",
                "end_formatted": "00:00:05",
                "duration": 5.0,
                "confidence": 0.95,
                "word_count": 15
            },
            {
                "speaker": "Speaker 2", 
                "text": "Thank you for organizing this. I have some updates on the project status to share.",
                "start_time": 5500,
                "end_time": 10000,
                "start_formatted": "00:00:05",
                "end_formatted": "00:00:10",
                "duration": 4.5,
                "confidence": 0.92,
                "word_count": 14
            },
            {
                "speaker": "Speaker 1",
                "text": "Great! Let's hear your updates first, then we can discuss the next steps.",
                "start_time": 10500,
                "end_time": 15000,
                "start_formatted": "00:00:10",
                "end_formatted": "00:00:15",
                "duration": 4.5,
                "confidence": 0.94,
                "word_count": 13
            },
            {
                "speaker": "Speaker 2",
                "text": "We've completed the initial phase and are now moving into testing. The results look promising so far.",
                "start_time": 15500,
                "end_time": 22000,
                "start_formatted": "00:00:15",
                "end_formatted": "00:00:22",
                "duration": 6.5,
                "confidence": 0.96,
                "word_count": 17
            }
        ],
        "speaker_statistics": {
            "Speaker 1": {
                "total_duration": 9500,
                "total_words": 28,
                "segments_count": 2,
                "avg_confidence": 0.945
            },
            "Speaker 2": {
                "total_duration": 11000,
                "total_words": 31,
                "segments_count": 2,
                "avg_confidence": 0.94
            }
        },
        "summary": {
            "total_speakers": 2,
            "total_duration": 22.0,
            "total_words": 59,
            "total_segments": 4,
            "confidence_score": 0.9425
        },
        "metadata": {
            "job_id": "test_job_123",
            "audio_duration": 22.0,
            "language_model": "assemblyai_default",
            "acoustic_model": "assemblyai_default"
        }
    }

def test_speaker_display():
    """Test the speaker diarization display functionality."""
    print("🎯 Testing Speaker Diarization Display")
    print("=" * 50)
    
    # Create test data
    test_data = create_test_speaker_data()
    
    print("✅ Test speaker diarization data created:")
    print(f"   - {test_data['summary']['total_speakers']} speakers detected")
    print(f"   - {test_data['summary']['total_segments']} segments")
    print(f"   - {test_data['summary']['total_duration']} seconds duration")
    print(f"   - {test_data['summary']['confidence_score']:.1%} confidence")
    
    # Display segments
    print("\n📝 Speaker Segments:")
    for i, segment in enumerate(test_data['segments'], 1):
        print(f"   {i}. [{segment['start_formatted']}] {segment['speaker']}: {segment['text'][:50]}...")
    
    # Display statistics
    print("\n📊 Speaker Statistics:")
    for speaker, stats in test_data['speaker_statistics'].items():
        duration_sec = stats['total_duration'] / 1000
        print(f"   {speaker}:")
        print(f"     - Speaking time: {duration_sec:.1f}s")
        print(f"     - Words spoken: {stats['total_words']}")
        print(f"     - Segments: {stats['segments_count']}")
        print(f"     - Confidence: {stats['avg_confidence']:.1%}")
    
    return test_data

def simulate_live_transcript_with_speakers():
    """Simulate live transcript updates with speaker information."""
    print("\n🎙️ Simulating Live Transcript with Speaker Labels")
    print("=" * 50)
    
    # Sample transcript segments with speakers
    live_segments = [
        {"speaker": "Speaker 1", "text": "Let's begin the meeting", "source": "Mic"},
        {"speaker": "Speaker 2", "text": "I have the quarterly report ready", "source": "Mic"},
        {"speaker": "Speaker 1", "text": "Perfect, please go ahead and present", "source": "Mic"},
        {"speaker": "Speaker 2", "text": "Our revenue increased by 15% this quarter", "source": "Mic"},
        {"speaker": "Speaker 1", "text": "That's excellent news! What drove the growth?", "source": "Mic"},
    ]
    
    print("Simulating real-time transcript updates:")
    for i, segment in enumerate(live_segments, 1):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"   [{timestamp}] {segment['speaker']}: {segment['text']}")
        
        # Simulate the data structure that would be sent to frontend
        update_data = {
            'new_text': segment['text'],
            'speaker': segment['speaker'],
            'source_label': segment['source'],
            'timestamp': timestamp,
            'word_count': len(segment['text'].split()),
            'segments_count': i,
            'duration': i * 3,  # Simulate 3 seconds per segment
            'wpm': 120
        }
        
        print(f"      → Frontend update: {json.dumps(update_data, indent=8)}")
        time.sleep(1)  # Simulate real-time delay
    
    print("\n✅ Live transcript simulation complete")

def main():
    """Main test function."""
    print("🎯 Speaker Diarization Display Test")
    print("=" * 60)
    
    # Test 1: Static speaker diarization data
    test_data = test_speaker_display()
    
    # Test 2: Live transcript simulation
    simulate_live_transcript_with_speakers()
    
    print("\n" + "=" * 60)
    print("🎉 All speaker display tests completed!")
    print("\nTo test in the web interface:")
    print("1. Start the Flask app: python app_perfect_ai.py")
    print("2. Go to Live Transcript page")
    print("3. Start recording to see speaker labels")
    print("4. Check AI Analysis page for speaker statistics")

if __name__ == "__main__":
    main()