#!/usr/bin/env python3
"""
AssemblyAI Speaker Diarization Module for Perfect AI Meeting Analyzer
Integrates speaker identification without disturbing existing functionality.
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

load_dotenv()

class AssemblyAISpeakerDiarization:
    """
    AssemblyAI Speaker Diarization handler for Perfect AI.
    Provides speaker identification and labeling for audio files.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize AssemblyAI client."""
        self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
        if not self.api_key:
            raise ValueError("AssemblyAI API key is required. Set ASSEMBLYAI_API_KEY in .env file.")
        
        self.base_url = "https://api.assemblyai.com/v2"
        self.headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
        
        print("✅ AssemblyAI Speaker Diarization initialized")
    
    def upload_audio_file(self, file_path: str) -> str:
        """
        Upload audio file to AssemblyAI and get upload URL.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Upload URL for the audio file
        """
        print(f"📤 Uploading audio file: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        # Upload file
        upload_url = f"{self.base_url}/upload"
        
        with open(file_path, 'rb') as f:
            response = requests.post(
                upload_url,
                headers={"authorization": self.api_key},
                files={"file": f}
            )
        
        if response.status_code == 200:
            upload_response = response.json()
            audio_url = upload_response["upload_url"]
            print(f"✅ Audio uploaded successfully: {audio_url}")
            return audio_url
        else:
            raise Exception(f"Failed to upload audio: {response.status_code} - {response.text}")
    
    def start_transcription_with_diarization(self, audio_url: str, **kwargs) -> str:
        """
        Start transcription with speaker diarization.
        
        Args:
            audio_url: URL of the audio file (uploaded or direct URL)
            **kwargs: Additional transcription options
            
        Returns:
            Transcription job ID
        """
        print(f"🎯 Starting transcription with speaker diarization...")
        
        # Default transcription config with speaker diarization
        config = {
            "audio_url": audio_url,
            "speaker_labels": True,  # Enable speaker diarization
            "speakers_expected": kwargs.get("speakers_expected"),  # Optional: expected number of speakers
            "auto_highlights": True,  # Get key highlights
            "sentiment_analysis": True,  # Analyze sentiment per speaker
            "entity_detection": True,  # Detect entities
            "punctuate": True,
            "format_text": True,
            "dual_channel": kwargs.get("dual_channel", False),
            "webhook_url": kwargs.get("webhook_url"),
            "word_boost": kwargs.get("word_boost", []),  # Boost specific words
            "boost_param": kwargs.get("boost_param", "default")
        }
        
        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}
        
        print(f"📋 Transcription config: {json.dumps(config, indent=2)}")
        
        # Start transcription
        response = requests.post(
            f"{self.base_url}/transcript",
            headers=self.headers,
            json=config
        )
        
        if response.status_code == 200:
            transcript_response = response.json()
            job_id = transcript_response["id"]
            print(f"✅ Transcription started. Job ID: {job_id}")
            return job_id
        else:
            raise Exception(f"Failed to start transcription: {response.status_code} - {response.text}")
    
    def get_transcription_status(self, job_id: str) -> Dict:
        """
        Get transcription status and results.
        
        Args:
            job_id: Transcription job ID
            
        Returns:
            Transcription status and results
        """
        response = requests.get(
            f"{self.base_url}/transcript/{job_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get transcription status: {response.status_code} - {response.text}")
    
    def wait_for_completion(self, job_id: str, timeout: int = 600) -> Dict:
        """
        Wait for transcription to complete.
        
        Args:
            job_id: Transcription job ID
            timeout: Maximum wait time in seconds
            
        Returns:
            Completed transcription results
        """
        print(f"⏳ Waiting for transcription to complete...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.get_transcription_status(job_id)
            status = result["status"]
            
            print(f"📊 Status: {status}")
            
            if status == "completed":
                print(f"✅ Transcription completed successfully!")
                return result
            elif status == "error":
                error_msg = result.get("error", "Unknown error")
                raise Exception(f"Transcription failed: {error_msg}")
            
            # Wait before checking again
            time.sleep(5)
        
        raise TimeoutError(f"Transcription timed out after {timeout} seconds")
    
    def format_diarized_transcript(self, transcript_result: Dict) -> Dict:
        """
        Format the diarized transcript into a readable format.
        
        Args:
            transcript_result: Raw transcription result from AssemblyAI
            
        Returns:
            Formatted transcript with speaker labels and timestamps
        """
        print(f"📝 Formatting diarized transcript...")
        
        if not transcript_result.get("utterances"):
            return {
                "error": "No speaker diarization data available",
                "raw_text": transcript_result.get("text", "")
            }
        
        formatted_segments = []
        speaker_stats = {}
        
        for utterance in transcript_result["utterances"]:
            speaker = utterance["speaker"]
            text = utterance["text"]
            start_time = utterance["start"]
            end_time = utterance["end"]
            confidence = utterance["confidence"]
            
            # Format timestamp
            start_formatted = self._format_timestamp(start_time)
            end_formatted = self._format_timestamp(end_time)
            duration = end_time - start_time
            
            # Create formatted segment
            segment = {
                "speaker": f"Speaker {speaker}",
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "start_formatted": start_formatted,
                "end_formatted": end_formatted,
                "duration": duration,
                "confidence": confidence,
                "word_count": len(text.split())
            }
            
            formatted_segments.append(segment)
            
            # Update speaker statistics
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    "total_duration": 0,
                    "total_words": 0,
                    "segments_count": 0,
                    "avg_confidence": 0
                }
            
            speaker_stats[speaker]["total_duration"] += duration
            speaker_stats[speaker]["total_words"] += len(text.split())
            speaker_stats[speaker]["segments_count"] += 1
            speaker_stats[speaker]["avg_confidence"] = (
                speaker_stats[speaker]["avg_confidence"] * (speaker_stats[speaker]["segments_count"] - 1) + confidence
            ) / speaker_stats[speaker]["segments_count"]
        
        # Generate formatted text output
        formatted_text = self._generate_formatted_text(formatted_segments)
        
        # Calculate overall statistics
        total_duration = transcript_result.get("audio_duration", 0)
        total_words = len(transcript_result.get("text", "").split())
        
        return {
            "success": True,
            "segments": formatted_segments,
            "formatted_text": formatted_text,
            "speaker_statistics": speaker_stats,
            "summary": {
                "total_speakers": len(speaker_stats),
                "total_duration": total_duration,
                "total_words": total_words,
                "total_segments": len(formatted_segments),
                "confidence_score": transcript_result.get("confidence", 0)
            },
            "metadata": {
                "job_id": transcript_result.get("id"),
                "audio_duration": transcript_result.get("audio_duration"),
                "language_model": transcript_result.get("language_model"),
                "acoustic_model": transcript_result.get("acoustic_model")
            }
        }
    
    def _format_timestamp(self, milliseconds: int) -> str:
        """Format timestamp from milliseconds to HH:MM:SS format."""
        seconds = milliseconds / 1000
        return str(timedelta(seconds=int(seconds)))
    
    def _generate_formatted_text(self, segments: List[Dict]) -> str:
        """Generate formatted text output with speaker labels."""
        formatted_lines = []
        
        for segment in segments:
            timestamp = segment["start_formatted"]
            speaker = segment["speaker"]
            text = segment["text"]
            
            formatted_lines.append(f"[{timestamp}] {speaker}: {text}")
        
        return "\n".join(formatted_lines)
    
    def process_audio_file(self, file_path: str, **kwargs) -> Dict:
        """
        Complete pipeline: upload, transcribe, and format audio file.
        
        Args:
            file_path: Path to audio file
            **kwargs: Additional options
            
        Returns:
            Complete diarized transcript results
        """
        try:
            print(f"🎯 Processing audio file with speaker diarization: {file_path}")
            
            # Step 1: Upload audio file
            audio_url = self.upload_audio_file(file_path)
            
            # Step 2: Start transcription
            job_id = self.start_transcription_with_diarization(audio_url, **kwargs)
            
            # Step 3: Wait for completion
            result = self.wait_for_completion(job_id)
            
            # Step 4: Format results
            formatted_result = self.format_diarized_transcript(result)
            
            print(f"✅ Speaker diarization completed successfully!")
            return formatted_result
            
        except Exception as e:
            print(f"❌ Error processing audio file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_audio_url(self, audio_url: str, **kwargs) -> Dict:
        """
        Process audio from URL with speaker diarization.
        
        Args:
            audio_url: Direct URL to audio file
            **kwargs: Additional options
            
        Returns:
            Complete diarized transcript results
        """
        try:
            print(f"🎯 Processing audio URL with speaker diarization: {audio_url}")
            
            # Step 1: Start transcription
            job_id = self.start_transcription_with_diarization(audio_url, **kwargs)
            
            # Step 2: Wait for completion
            result = self.wait_for_completion(job_id)
            
            # Step 3: Format results
            formatted_result = self.format_diarized_transcript(result)
            
            print(f"✅ Speaker diarization completed successfully!")
            return formatted_result
            
        except Exception as e:
            print(f"❌ Error processing audio URL: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Utility functions for integration
def get_available_audio_files(recordings_dir: str = "recordings") -> List[Dict]:
    """Get list of available audio files for diarization."""
    audio_files = []
    
    if not os.path.exists(recordings_dir):
        return audio_files
    
    for root, dirs, files in os.walk(recordings_dir):
        for file in files:
            if file.endswith(('.wav', '.mp3', '.m4a', '.flac', '.ogg')):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                
                audio_files.append({
                    "filename": file,
                    "path": file_path,
                    "size_mb": round(file_size / 1024 / 1024, 2),
                    "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return sorted(audio_files, key=lambda x: x['modified'], reverse=True)

def save_diarization_result(result: Dict, output_dir: str = "diarization_results") -> str:
    """Save diarization result to file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"speaker_diarization_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    return filepath

# Test function
def test_speaker_diarization():
    """Test speaker diarization functionality."""
    try:
        # Initialize diarization
        diarizer = AssemblyAISpeakerDiarization()
        
        # Get available audio files
        audio_files = get_available_audio_files()
        
        if not audio_files:
            print("⚠️ No audio files found for testing")
            return False
        
        print(f"📁 Found {len(audio_files)} audio files")
        for i, file in enumerate(audio_files[:3]):  # Show first 3
            print(f"  {i+1}. {file['filename']} ({file['size_mb']} MB)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🎯 AssemblyAI Speaker Diarization Module")
    print("=" * 50)
    test_speaker_diarization()