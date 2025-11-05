#!/usr/bin/env python3
"""
Simple speaker detection using local audio analysis.
This provides a fallback when AssemblyAI isn't working.
"""

import numpy as np
import librosa
import os
from scipy.signal import find_peaks
from sklearn.cluster import KMeans
import json
from datetime import datetime, timedelta

class SimpleSpeakerDetection:
    """
    Simple speaker detection using audio features.
    This is a fallback when AssemblyAI isn't available.
    """
    
    def __init__(self):
        self.sample_rate = 16000
        self.hop_length = 512
        self.n_mfcc = 13
    
    def extract_features(self, audio_segment):
        """Extract MFCC features from audio segment."""
        try:
            # Extract MFCC features
            mfccs = librosa.feature.mfcc(
                y=audio_segment, 
                sr=self.sample_rate, 
                n_mfcc=self.n_mfcc,
                hop_length=self.hop_length
            )
            
            # Calculate statistics
            mfcc_mean = np.mean(mfccs, axis=1)
            mfcc_std = np.std(mfccs, axis=1)
            
            # Extract pitch features
            pitches, magnitudes = librosa.piptrack(
                y=audio_segment, 
                sr=self.sample_rate,
                hop_length=self.hop_length
            )
            
            # Get fundamental frequency
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)
            
            avg_pitch = np.mean(pitch_values) if pitch_values else 0
            pitch_std = np.std(pitch_values) if pitch_values else 0
            
            # Combine features
            features = np.concatenate([mfcc_mean, mfcc_std, [avg_pitch, pitch_std]])
            
            return features
            
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return np.zeros(self.n_mfcc * 2 + 2)
    
    def detect_voice_segments(self, audio, transcript_segments):
        """Detect voice activity segments."""
        try:
            # Simple voice activity detection using energy
            frame_length = int(0.025 * self.sample_rate)  # 25ms frames
            hop_length = int(0.010 * self.sample_rate)    # 10ms hop
            
            # Calculate energy for each frame
            energy = []
            for i in range(0, len(audio) - frame_length, hop_length):
                frame = audio[i:i + frame_length]
                frame_energy = np.sum(frame ** 2)
                energy.append(frame_energy)
            
            energy = np.array(energy)
            
            # Find energy threshold
            energy_threshold = np.percentile(energy, 30)  # Bottom 30% is likely silence
            
            # Find voice segments
            voice_frames = energy > energy_threshold
            
            # Convert frame indices to time segments
            segments = []
            in_voice = False
            start_time = 0
            
            for i, is_voice in enumerate(voice_frames):
                time_sec = i * hop_length / self.sample_rate
                
                if is_voice and not in_voice:
                    # Start of voice segment
                    start_time = time_sec
                    in_voice = True
                elif not is_voice and in_voice:
                    # End of voice segment
                    if time_sec - start_time > 1.0:  # Only segments longer than 1 second
                        segments.append({
                            'start': start_time,
                            'end': time_sec,
                            'duration': time_sec - start_time
                        })
                    in_voice = False
            
            return segments
            
        except Exception as e:
            print(f"Voice segment detection error: {e}")
            return []
    
    def cluster_speakers(self, features_list, n_speakers=2):
        """Cluster audio features to identify speakers."""
        try:
            if len(features_list) < 2:
                return [0] * len(features_list)
            
            # Use KMeans clustering
            features_array = np.array(features_list)
            
            # Determine number of speakers (2-4 range)
            n_speakers = min(max(n_speakers, 2), min(4, len(features_list)))
            
            kmeans = KMeans(n_clusters=n_speakers, random_state=42, n_init=10)
            speaker_labels = kmeans.fit_predict(features_array)
            
            return speaker_labels.tolist()
            
        except Exception as e:
            print(f"Speaker clustering error: {e}")
            return [0] * len(features_list)
    
    def process_audio_file(self, audio_file_path, transcript_text=""):
        """Process audio file for simple speaker detection."""
        try:
            print(f"🎙️ Processing audio for speaker detection: {audio_file_path}")
            
            # Load audio file
            audio, sr = librosa.load(audio_file_path, sr=self.sample_rate)
            
            if len(audio) == 0:
                return {"success": False, "error": "Empty audio file"}
            
            duration = len(audio) / sr
            print(f"   Duration: {duration:.2f} seconds")
            
            # Split transcript into segments (rough approximation)
            transcript_segments = self._split_transcript(transcript_text, duration)
            
            # Detect voice segments
            voice_segments = self.detect_voice_segments(audio, transcript_segments)
            print(f"   Voice segments detected: {len(voice_segments)}")
            
            if len(voice_segments) < 2:
                return {
                    "success": False, 
                    "error": "Not enough voice segments for speaker detection"
                }
            
            # Extract features for each voice segment
            features_list = []
            segment_info = []
            
            for segment in voice_segments:
                start_sample = int(segment['start'] * sr)
                end_sample = int(segment['end'] * sr)
                
                if end_sample > len(audio):
                    end_sample = len(audio)
                
                audio_segment = audio[start_sample:end_sample]
                
                if len(audio_segment) > 0:
                    features = self.extract_features(audio_segment)
                    features_list.append(features)
                    segment_info.append(segment)
            
            if len(features_list) < 2:
                return {
                    "success": False,
                    "error": "Not enough audio features extracted"
                }
            
            # Cluster speakers
            speaker_labels = self.cluster_speakers(features_list, n_speakers=2)
            
            # Create formatted result
            formatted_segments = []
            speaker_stats = {}
            
            for i, (segment, speaker_id) in enumerate(zip(segment_info, speaker_labels)):
                speaker_name = f"Speaker {speaker_id + 1}"
                
                # Get corresponding transcript text (rough approximation)
                segment_text = self._get_segment_text(transcript_segments, segment, transcript_text)
                
                formatted_segment = {
                    "speaker": speaker_name,
                    "text": segment_text,
                    "start_time": int(segment['start'] * 1000),  # milliseconds
                    "end_time": int(segment['end'] * 1000),
                    "start_formatted": str(timedelta(seconds=int(segment['start']))),
                    "end_formatted": str(timedelta(seconds=int(segment['end']))),
                    "duration": segment['duration'],
                    "confidence": 0.75,  # Estimated confidence
                    "word_count": len(segment_text.split())
                }
                
                formatted_segments.append(formatted_segment)
                
                # Update speaker statistics
                if speaker_id not in speaker_stats:
                    speaker_stats[speaker_id] = {
                        "total_duration": 0,
                        "total_words": 0,
                        "segments_count": 0,
                        "avg_confidence": 0.75
                    }
                
                speaker_stats[speaker_id]["total_duration"] += segment['duration'] * 1000  # milliseconds
                speaker_stats[speaker_id]["total_words"] += len(segment_text.split())
                speaker_stats[speaker_id]["segments_count"] += 1
            
            # Generate formatted text
            formatted_text = "\n".join([
                f"[{seg['start_formatted']}] {seg['speaker']}: {seg['text']}"
                for seg in formatted_segments
            ])
            
            unique_speakers = len(set(speaker_labels))
            
            result = {
                "success": True,
                "segments": formatted_segments,
                "formatted_text": formatted_text,
                "speaker_statistics": speaker_stats,
                "summary": {
                    "total_speakers": unique_speakers,
                    "total_duration": duration,
                    "total_words": len(transcript_text.split()),
                    "total_segments": len(formatted_segments),
                    "confidence_score": 0.75
                },
                "metadata": {
                    "method": "local_clustering",
                    "audio_duration": duration,
                    "processing_time": datetime.now().isoformat()
                }
            }
            
            print(f"✅ Simple speaker detection completed: {unique_speakers} speakers detected")
            return result
            
        except Exception as e:
            print(f"❌ Simple speaker detection error: {e}")
            return {"success": False, "error": str(e)}
    
    def _split_transcript(self, transcript_text, duration):
        """Split transcript into time-based segments."""
        if not transcript_text:
            return []
        
        words = transcript_text.split()
        if not words:
            return []
        
        # Estimate words per second
        words_per_second = len(words) / duration if duration > 0 else 1
        
        # Create segments of roughly 5-10 seconds each
        segment_duration = 7  # seconds
        words_per_segment = int(words_per_second * segment_duration)
        
        segments = []
        for i in range(0, len(words), words_per_segment):
            start_time = i / words_per_second
            end_time = min((i + words_per_segment) / words_per_second, duration)
            segment_words = words[i:i + words_per_segment]
            
            segments.append({
                'start': start_time,
                'end': end_time,
                'text': ' '.join(segment_words)
            })
        
        return segments
    
    def _get_segment_text(self, transcript_segments, voice_segment, full_transcript):
        """Get transcript text for a voice segment."""
        if not transcript_segments:
            # Fallback: estimate based on time
            total_words = full_transcript.split()
            if not total_words:
                return "..."
            
            # Rough estimation
            start_ratio = voice_segment['start'] / voice_segment.get('total_duration', voice_segment['end'])
            end_ratio = voice_segment['end'] / voice_segment.get('total_duration', voice_segment['end'])
            
            start_word = int(start_ratio * len(total_words))
            end_word = int(end_ratio * len(total_words))
            
            segment_words = total_words[start_word:end_word]
            return ' '.join(segment_words) if segment_words else "..."
        
        # Find overlapping transcript segment
        for t_seg in transcript_segments:
            if (voice_segment['start'] <= t_seg['end'] and 
                voice_segment['end'] >= t_seg['start']):
                return t_seg['text']
        
        return "..."

# Test function
def test_simple_detection():
    """Test simple speaker detection with a recent recording."""
    print("🎯 Testing Simple Speaker Detection")
    print("=" * 50)
    
    # Find recent recording
    recordings_dir = "recordings"
    audio_files = []
    
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith('.wav'):
                filepath = os.path.join(root, file)
                audio_files.append(filepath)
    
    if not audio_files:
        print("❌ No audio files found")
        return False
    
    # Use most recent file
    latest_file = max(audio_files, key=os.path.getmtime)
    print(f"📁 Testing with: {os.path.basename(latest_file)}")
    
    # Sample transcript (you can replace with actual transcript)
    sample_transcript = "I am renaud and I need yennefer. I am yanni. Hello everyone this is our conversation."
    
    try:
        detector = SimpleSpeakerDetection()
        result = detector.process_audio_file(latest_file, sample_transcript)
        
        if result.get('success'):
            summary = result['summary']
            print(f"✅ Detection successful!")
            print(f"   Speakers detected: {summary['total_speakers']}")
            print(f"   Segments: {summary['total_segments']}")
            
            # Show sample segments
            segments = result.get('segments', [])
            for segment in segments[:3]:
                print(f"   {segment['speaker']}: {segment['text'][:60]}...")
            
            return True
        else:
            print(f"❌ Detection failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

if __name__ == "__main__":
    try:
        test_simple_detection()
    except KeyboardInterrupt:
        print("\n❌ Test cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()