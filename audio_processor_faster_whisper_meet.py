"""
Enhanced Audio Processor Module - Windows System Audio + Microphone Support
Handles real-time audio capture from multiple sources with Faster-Whisper transcription.

New Features:
1. Microphone capture (existing)
2. System audio loopback (Google Meet/Zoom/Teams)
3. Dual capture mode (Mic + System separately)

Supported on Windows 10/11 with WASAPI loopback
"""

# Suppress warnings
import os
os.environ["ORT_DISABLE_DEVICE_DISCOVERY"] = "1"

import pyaudio
import threading
import queue
import numpy as np
from faster_whisper import WhisperModel
import time
from typing import Callable, Optional, Literal
import soundcard as sc
from datetime import datetime
import scipy.signal
from scipy.signal import butter, filtfilt, wiener
import noisereduce as nr
import assemblyai as aai
import tempfile
import wave
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Audio recording settings - Optimized for speed and quality
CHUNK_SIZE = 4096  # Reduced for lower latency
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# Transcription settings - Optimized for real-time performance
CHUNK_DURATION_SECONDS = 1.5  # Reduced for faster processing
OVERLAP_SECONDS = 0.3  # Reduced overlap for speed

# Whisper model settings - Optimized for speed
WHISPER_MODEL_SIZE = "base"  # Changed to tiny for maximum speed
DEVICE = "cpu"  # Use GPU if available for better performance
COMPUTE_TYPE = "int8"  # Fastest computation type

# Noise cancellation settings
NOISE_REDUCTION_ENABLED = True
VOICE_ACTIVITY_DETECTION = True
HIGH_PASS_FILTER_ENABLED = True
ADAPTIVE_NOISE_GATE = True

# Voice frequency range (human speech is typically 85-255 Hz fundamental, 300-3400 Hz total)
VOICE_LOW_FREQ = 300   # Hz - Remove low frequency noise
VOICE_HIGH_FREQ = 3400 # Hz - Remove high frequency noise
NOISE_GATE_THRESHOLD = 0.02  # Amplitude threshold for voice activity

# Audio source types
AudioSourceType = Literal["mic", "system", "both"]

# Transcription engine types
TranscriptionEngine = Literal["faster_whisper", "assemblyai"]

# AssemblyAI configuration
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
if ASSEMBLYAI_API_KEY:
    aai.settings.api_key = ASSEMBLYAI_API_KEY

# ============================================================================
# AUDIO PROCESSING FUNCTIONS
# ============================================================================

def apply_noise_cancellation(audio_data: np.ndarray, sample_rate: int = RATE) -> np.ndarray:
    """
    Apply advanced noise cancellation to audio data.
    
    Args:
        audio_data: Raw audio data as numpy array
        sample_rate: Sample rate of the audio
    
    Returns:
        Cleaned audio data
    """
    try:
        # Convert to float for processing
        audio_float = audio_data.astype(np.float32)
        
        # 1. High-pass filter to remove low-frequency noise (AC hum, rumble)
        if HIGH_PASS_FILTER_ENABLED:
            nyquist = sample_rate * 0.5
            low_cutoff = VOICE_LOW_FREQ / nyquist
            b, a = butter(4, low_cutoff, btype='high')
            audio_float = filtfilt(b, a, audio_float)
        
        # 2. Band-pass filter for human voice range
        nyquist = sample_rate * 0.5
        low = VOICE_LOW_FREQ / nyquist
        high = min(VOICE_HIGH_FREQ / nyquist, 0.99)  # Ensure it's below Nyquist
        b, a = butter(4, [low, high], btype='band')
        audio_float = filtfilt(b, a, audio_float)
        
        # 3. Spectral noise reduction
        if NOISE_REDUCTION_ENABLED and len(audio_float) > 1024:
            # Use noisereduce library for spectral subtraction
            audio_float = nr.reduce_noise(
                y=audio_float, 
                sr=sample_rate,
                stationary=False,  # Non-stationary noise reduction
                prop_decrease=0.8  # Aggressive noise reduction
            )
        
        # 4. Adaptive noise gate
        if ADAPTIVE_NOISE_GATE:
            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_float**2))
            if rms < NOISE_GATE_THRESHOLD:
                audio_float *= 0.1  # Heavily attenuate low-energy segments
        
        # 5. Normalize audio to prevent clipping
        max_val = np.max(np.abs(audio_float))
        if max_val > 0:
            audio_float = audio_float / max_val * 0.8
        
        # Ensure output is float32
        return audio_float.astype(np.float32)
        
    except Exception as e:
        print(f"Error in noise cancellation: {e}")
        # Fallback to basic normalization
        try:
            audio_float = audio_data.astype(np.float32)
            if np.max(np.abs(audio_float)) > 0:
                audio_float = audio_float / np.max(np.abs(audio_float)) * 0.8
            return audio_float
        except:
            return audio_data.astype(np.float32)

def detect_voice_activity(audio_data: np.ndarray, threshold: float = NOISE_GATE_THRESHOLD) -> bool:
    """
    Simple voice activity detection based on energy and spectral characteristics.
    
    Args:
        audio_data: Audio data as numpy array
        threshold: Energy threshold for voice detection
    
    Returns:
        True if voice is detected, False otherwise
    """
    try:
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_data**2))
        
        # Calculate spectral centroid (brightness indicator)
        fft = np.fft.rfft(audio_data)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(len(audio_data), 1/RATE)
        
        if np.sum(magnitude) > 0:
            spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
            
            # Voice typically has spectral centroid in 500-2000 Hz range
            voice_like = (spectral_centroid > 500) and (spectral_centroid < 2000)
            energy_sufficient = rms > threshold
            
            return voice_like and energy_sufficient
        
        return False
        
    except Exception as e:
        print(f"Error in voice activity detection: {e}")
        return True  # Default to processing if detection fails

def optimize_audio_for_speech(audio_data: np.ndarray) -> np.ndarray:
    """
    Optimize audio specifically for speech recognition.
    
    Args:
        audio_data: Raw audio data
    
    Returns:
        Optimized audio data
    """
    try:
        # Apply noise cancellation
        cleaned_audio = apply_noise_cancellation(audio_data)
        
        # Apply dynamic range compression for consistent levels
        # This helps with varying microphone distances
        compressed_audio = np.tanh(cleaned_audio * 2.0) * 0.8
        
        # Pre-emphasis filter to boost high frequencies (improves speech clarity)
        pre_emphasis = 0.97
        emphasized_audio = np.append(compressed_audio[0], compressed_audio[1:] - pre_emphasis * compressed_audio[:-1])
        
        # Ensure output is float32
        return emphasized_audio.astype(np.float32)
        
    except Exception as e:
        print(f"Error in speech optimization: {e}")
        # Fallback to basic normalization
        try:
            audio_float = audio_data.astype(np.float32)
            if np.max(np.abs(audio_float)) > 0:
                audio_float = audio_float / np.max(np.abs(audio_float)) * 0.8
            return audio_float
        except:
            return audio_data.astype(np.float32)

# ============================================================================


class EnhancedAudioProcessor:
    """
    Enhanced audio processor supporting:
    - Microphone capture (PyAudio)
    - System audio loopback (soundcard - WASAPI)
    - Dual capture mode (both sources separately)
    - Multiple transcription engines (Faster-Whisper, AssemblyAI)
    """
    
    def __init__(
        self, 
        on_transcript: Callable[[str, str], None],  # (text, source_label)
        audio_source: AudioSourceType = "mic",
        transcription_engine: TranscriptionEngine = "faster_whisper"
    ):
        """
        Initialize audio processor.
        
        Args:
            on_transcript: Callback(text, source_label) where source_label is "Mic" or "System"
            audio_source: "mic", "system", or "both"
            transcription_engine: "faster_whisper" or "assemblyai"
        """
        self.audio_source = audio_source
        self.transcription_engine = transcription_engine
        self.transcript_callback = on_transcript
        
        # PyAudio for microphone
        self.audio = pyaudio.PyAudio()
        self.mic_stream: Optional[pyaudio.Stream] = None
        
        # Soundcard for system audio
        self.system_recorder = None
        
        # Threading components
        self.is_recording = False
        self.mic_queue = queue.Queue()
        self.system_queue = queue.Queue()
        
        # Audio buffers with overlap
        self.mic_buffer = []
        self.mic_buffer_duration = 0.0
        self.system_buffer = []
        self.system_buffer_duration = 0.0
        
        # Processing threads
        self.mic_processing_thread: Optional[threading.Thread] = None
        self.system_processing_thread: Optional[threading.Thread] = None
        self.system_capture_thread: Optional[threading.Thread] = None
        
        # Initialize transcription engine
        self.whisper_model = None
        self.assemblyai_transcriber = None
        
        if self.transcription_engine == "faster_whisper":
            print("Loading optimized Faster-Whisper model for real-time processing...")
            self.whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                cpu_threads=4,  # Optimize CPU usage
                num_workers=1   # Single worker for lower latency
            )
            print("✓ Faster-Whisper model loaded for real-time performance")
        
        elif self.transcription_engine == "assemblyai":
            if not ASSEMBLYAI_API_KEY:
                raise ValueError("AssemblyAI API key not found. Please set ASSEMBLYAI_API_KEY in .env file")
            
            print("Initializing AssemblyAI transcriber...")
            print(f"API Key loaded: {ASSEMBLYAI_API_KEY[:10]}...{ASSEMBLYAI_API_KEY[-4:]}")
            
            # Configure AssemblyAI for real-time transcription
            config = aai.TranscriptionConfig(
                language_detection=True,
                punctuate=True,
                format_text=True,
                filter_profanity=False,
                redact_pii=False,
                speaker_labels=False
            )
            self.assemblyai_transcriber = aai.Transcriber(config=config)
            print("✓ AssemblyAI transcriber initialized successfully")
        
        # Validate audio source availability
        self._validate_audio_sources()
    
    def _validate_audio_sources(self):
        """Check if requested audio sources are available."""
        if self.audio_source in ["mic", "both"]:
            # Check mic availability
            try:
                device_info = self.audio.get_default_input_device_info()
                print(f"✓ Microphone available: {device_info['name']}")
            except Exception as e:
                print(f"⚠ Microphone not available: {e}")
                if self.audio_source == "mic":
                    raise RuntimeError("Microphone not available but required")
        
        if self.audio_source in ["system", "both"]:
            # Check system audio availability
            try:
                loopback = self._get_system_loopback()
                if loopback:
                    print(f"✓ System audio loopback available: {loopback.name}")
                else:
                    raise RuntimeError("No loopback device found")
            except Exception as e:
                print(f"⚠ System audio not available: {e}")
                print("\n" + "="*60)
                print("SYSTEM AUDIO SETUP REQUIRED")
                print("="*60)
                print("To capture system audio (Google Meet/Zoom):")
                print("1. Open Windows Sound settings (Win+R → mmsys.cpl)")
                print("2. Go to Recording tab")
                print("3. Right-click → Show Disabled Devices")
                print("4. Enable 'Stereo Mix' if available")
                print("\nSee WINDOWS_AUDIO_SETUP.md for detailed instructions.")
                print("="*60 + "\n")
                if self.audio_source == "system":
                    raise RuntimeError("System audio not available but required")
    
    def _get_system_loopback(self):
        """Get system audio loopback device (Windows WASAPI)."""
        try:
            # Get all microphones including loopback devices
            all_mics = sc.all_microphones(include_loopback=True)
            
            if not all_mics:
                print("❌ No recording devices found")
                return None
            
            # Get default speaker name to find matching loopback
            try:
                default_speaker = sc.default_speaker()
                speaker_name = default_speaker.name
                print(f"Looking for loopback of: {speaker_name}")
            except:
                speaker_name = ""
            
            # Find loopback device
            loopback_device = None
            
            # Method 1: Look for explicit loopback or stereo mix
            for mic in all_mics:
                mic_name_lower = mic.name.lower()
                if any(keyword in mic_name_lower for keyword in ['loopback', 'stereo mix', 'wave out', 'what u hear']):
                    loopback_device = mic
                    print(f"✓ Found loopback device: {mic.name}")
                    break
            
            # Method 2: Look for device matching speaker name
            if not loopback_device and speaker_name:
                for mic in all_mics:
                    if speaker_name.lower() in mic.name.lower() and mic.isloopback:
                        loopback_device = mic
                        print(f"✓ Found speaker loopback: {mic.name}")
                        break
            
            # Method 3: Use any device marked as loopback
            if not loopback_device:
                for mic in all_mics:
                    if hasattr(mic, 'isloopback') and mic.isloopback:
                        loopback_device = mic
                        print(f"✓ Using loopback device: {mic.name}")
                        break
            
            # Method 4: Fallback - try to get default speaker as microphone
            if not loopback_device and speaker_name:
                try:
                    loopback_device = sc.get_microphone(id=speaker_name, include_loopback=True)
                    if loopback_device:
                        print(f"✓ Got speaker as microphone: {speaker_name}")
                except Exception as e:
                    print(f"Could not get speaker as microphone: {e}")
            
            if not loopback_device:
                print("❌ No loopback device found!")
                print("Available devices:")
                for i, mic in enumerate(all_mics):
                    is_loop = " (loopback)" if hasattr(mic, 'isloopback') and mic.isloopback else ""
                    print(f"  {i+1}. {mic.name}{is_loop}")
                print("\nPlease enable 'Stereo Mix' in Windows Sound settings.")
                print("See WINDOWS_AUDIO_SETUP.md for detailed instructions.")
                return None
            
            return loopback_device
            
        except Exception as e:
            print(f"Error getting system loopback: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def start_recording(self):
        """Start recording based on selected audio source."""
        if self.is_recording:
            print("Already recording!")
            return False
        
        print(f"\n{'='*60}")
        print(f"Starting recording mode: {self.audio_source.upper()}")
        print('='*60)
        
        self.is_recording = True
        success = False
        
        try:
            if self.audio_source == "mic":
                success = self._start_mic_recording()
            elif self.audio_source == "system":
                success = self._start_system_recording()
            elif self.audio_source == "both":
                success = self._start_dual_recording()
            
            if not success:
                self.is_recording = False
                return False
            
            print(f"✓ Recording started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            import traceback
            traceback.print_exc()
            self.is_recording = False
            return False
    
    def _start_mic_recording(self) -> bool:
        """Start microphone-only recording."""
        try:
            # Find best microphone device
            device_index = self._find_best_mic_device()
            
            # Open microphone stream
            self.mic_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._mic_callback
            )
            self.mic_stream.start_stream()
            print("✓ Microphone stream started")
            
            # Start mic processing thread
            self.mic_buffer = []
            self.mic_buffer_duration = 0.0
            self.mic_processing_thread = threading.Thread(
                target=self._mic_processing_loop,
                daemon=True
            )
            self.mic_processing_thread.start()
            print("✓ Mic processing thread started")
            
            return True
            
        except Exception as e:
            print(f"❌ Mic recording error: {e}")
            return False
    
    def _start_system_recording(self) -> bool:
        """Start system audio-only recording."""
        try:
            loopback = self._get_system_loopback()
            if not loopback:
                return False
            
            self.system_recorder = loopback
            
            # Start system capture thread
            self.system_buffer = []
            self.system_buffer_duration = 0.0
            self.system_capture_thread = threading.Thread(
                target=self._system_capture_loop,
                daemon=True
            )
            self.system_capture_thread.start()
            
            # Start system processing thread
            self.system_processing_thread = threading.Thread(
                target=self._system_processing_loop,
                daemon=True
            )
            self.system_processing_thread.start()
            
            print("✓ System audio recording started")
            return True
            
        except Exception as e:
            print(f"❌ System audio error: {e}")
            return False
    
    def _start_dual_recording(self) -> bool:
        """Start both mic and system audio recording."""
        print("Starting dual capture mode...")
        
        # Start microphone
        mic_ok = self._start_mic_recording()
        if not mic_ok:
            print("⚠ Failed to start microphone, continuing with system only")
        
        # Start system audio
        system_ok = self._start_system_recording()
        if not system_ok:
            print("⚠ Failed to start system audio, continuing with mic only")
        
        if not mic_ok and not system_ok:
            print("❌ Both sources failed!")
            return False
        
        print("✓ Dual capture mode active")
        return True
    
    def _find_best_mic_device(self) -> Optional[int]:
        """Find the best microphone device."""
        device_index = None
        
        # Look for default or PipeWire device
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name_lower = info['name'].lower()
                if 'pipewire' in name_lower or 'default' in name_lower:
                    device_index = i
                    print(f"✓ Using audio device: {info['name']}")
                    break
        
        # Fallback to default
        if device_index is None:
            try:
                device_index = self.audio.get_default_input_device_info()['index']
                print("✓ Using default audio device")
            except:
                device_index = None
        
        return device_index
    
    def _mic_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for microphone data."""
        if status and status != pyaudio.paInputOverflow:
            pass  # Ignore overflow warnings
        self.mic_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def _system_capture_loop(self):
        """Thread that captures system audio using soundcard."""
        print("System audio capture thread started")
        
        try:
            # Record from the loopback microphone device
            with self.system_recorder.recorder(samplerate=RATE) as recorder:
                while self.is_recording:
                    # Capture audio chunk
                    data = recorder.record(numframes=CHUNK_SIZE)
                    
                    # Handle stereo -> mono conversion
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    
                    # Convert to int16 bytes
                    audio_int16 = (data * 32767).astype(np.int16)
                    audio_bytes = audio_int16.tobytes()
                    
                    # Add to queue
                    self.system_queue.put(audio_bytes)
                    
        except AttributeError as e:
            print(f"❌ System capture error: {e}")
            print("The loopback device doesn't support recording.")
            print("Please enable 'Stereo Mix' in Windows Sound settings.")
            print("See WINDOWS_AUDIO_SETUP.md for instructions.")
        except Exception as e:
            print(f"System capture error: {e}")
            import traceback
            traceback.print_exc()
    
    def _mic_processing_loop(self):
        """Process microphone audio queue with optimized real-time performance."""
        print("Optimized mic processing loop started")
        
        while self.is_recording:
            try:
                # Reduced timeout for faster response
                audio_data = self.mic_queue.get(timeout=0.1)
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                
                self.mic_buffer.extend(audio_np)
                self.mic_buffer_duration += len(audio_np) / RATE
                
                # Process in smaller chunks for lower latency
                if self.mic_buffer_duration >= CHUNK_DURATION_SECONDS:
                    # Process in background thread to avoid blocking
                    buffer_copy = self.mic_buffer.copy()
                    threading.Thread(
                        target=self._transcribe_buffer, 
                        args=(buffer_copy, "Mic"),
                        daemon=True
                    ).start()
                    
                    # Keep overlap for continuity
                    overlap_samples = int(OVERLAP_SECONDS * RATE)
                    if len(self.mic_buffer) > overlap_samples:
                        self.mic_buffer = self.mic_buffer[-overlap_samples:]
                        self.mic_buffer_duration = OVERLAP_SECONDS
                    else:
                        self.mic_buffer = []
                        self.mic_buffer_duration = 0.0
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Mic processing error: {e}")
    
    def _system_processing_loop(self):
        """Process system audio queue with optimized real-time performance."""
        print("Optimized system processing loop started")
        
        while self.is_recording:
            try:
                # Reduced timeout for faster response
                audio_data = self.system_queue.get(timeout=0.1)
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                
                self.system_buffer.extend(audio_np)
                self.system_buffer_duration += len(audio_np) / RATE
                
                # Process in smaller chunks for lower latency
                if self.system_buffer_duration >= CHUNK_DURATION_SECONDS:
                    # Process in background thread to avoid blocking
                    buffer_copy = self.system_buffer.copy()
                    threading.Thread(
                        target=self._transcribe_buffer, 
                        args=(buffer_copy, "System"),
                        daemon=True
                    ).start()
                    
                    # Keep overlap for continuity
                    overlap_samples = int(OVERLAP_SECONDS * RATE)
                    if len(self.system_buffer) > overlap_samples:
                        self.system_buffer = self.system_buffer[-overlap_samples:]
                        self.system_buffer_duration = OVERLAP_SECONDS
                    else:
                        self.system_buffer = []
                        self.system_buffer_duration = 0.0
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"System processing error: {e}")
    
    def _transcribe_buffer(self, buffer: list, source_label: str):
        """Transcribe audio buffer with selected engine and advanced noise cancellation."""
        try:
            # Convert to float32 and normalize
            audio_np = np.array(buffer, dtype=np.float32)
            audio_np = audio_np / 32768.0
            
            # Apply voice activity detection
            try:
                if VOICE_ACTIVITY_DETECTION and not detect_voice_activity(audio_np):
                    return  # Skip processing if no voice detected
            except Exception as e:
                print(f"Voice activity detection error: {e}")
                # Continue processing if VAD fails
            
            # Apply advanced noise cancellation and speech optimization
            try:
                audio_np = optimize_audio_for_speech(audio_np)
            except Exception as e:
                print(f"Audio optimization error: {e}")
                # Fallback to basic normalization
                audio_np = audio_np.astype(np.float32)
                if np.max(np.abs(audio_np)) > 1.0:
                    audio_np = audio_np / np.max(np.abs(audio_np))
            
            # Transcribe based on selected engine
            if self.transcription_engine == "faster_whisper":
                transcript_text = self._transcribe_with_whisper(audio_np)
            elif self.transcription_engine == "assemblyai":
                transcript_text = self._transcribe_with_assemblyai(audio_np)
            else:
                print(f"Unknown transcription engine: {self.transcription_engine}")
                return
            
            if transcript_text:
                # Add timestamp and source label
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] [{source_label}] [{self.transcription_engine.upper()}] {transcript_text}")
                
                # Call callback with source label
                self.transcript_callback(transcript_text, source_label)
            
        except Exception as e:
            print(f"Transcription error: {e}")
    
    def _transcribe_with_whisper(self, audio_np: np.ndarray) -> str:
        """Transcribe using Faster-Whisper."""
        try:
            # Ensure audio is float32 for ONNX compatibility
            if audio_np.dtype != np.float32:
                audio_np = audio_np.astype(np.float32)
            
            # Ensure audio is in the correct range [-1, 1]
            if np.max(np.abs(audio_np)) > 1.0:
                audio_np = audio_np / np.max(np.abs(audio_np))
            
            segments, info = self.whisper_model.transcribe(
                audio_np,
                beam_size=1,  # Reduced beam size for speed
                language="en",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,  # Reduced for faster response
                    speech_pad_ms=200  # Reduced padding
                ),
                no_speech_threshold=0.3,  # Lower threshold for better detection
                compression_ratio_threshold=2.4,  # Optimized for speech
                temperature=0.0  # Deterministic output for consistency
            )
            
            # Combine segments
            transcript_text = ""
            for segment in segments:
                transcript_text += segment.text + " "
            
            return transcript_text.strip()
            
        except Exception as e:
            print(f"Faster-Whisper transcription error: {e}")
            return ""
    
    def _transcribe_with_assemblyai(self, audio_np: np.ndarray) -> str:
        """Transcribe using AssemblyAI."""
        try:
            # Convert float32 audio to int16 for WAV file
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                # Write WAV file
                with wave.open(temp_filename, 'wb') as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(2)  # 2 bytes for int16
                    wav_file.setframerate(RATE)
                    wav_file.writeframes(audio_int16.tobytes())
            
            # Transcribe with AssemblyAI
            transcript = self.assemblyai_transcriber.transcribe(temp_filename)
            
            # Clean up temporary file
            os.unlink(temp_filename)
            
            if transcript.status == aai.TranscriptStatus.completed:
                return transcript.text or ""
            else:
                print(f"AssemblyAI transcription failed: {transcript.status}")
                return ""
                
        except Exception as e:
            print(f"AssemblyAI transcription error: {e}")
            return ""
    
    def stop_recording(self):
        """Stop all recording streams."""
        print("Stopping recording...")
        self.is_recording = False
        
        # Stop microphone stream
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
            self.mic_stream = None
            print("✓ Mic stream closed")
        
        # Stop threads
        if self.mic_processing_thread:
            self.mic_processing_thread.join(timeout=5.0)
            print("✓ Mic processing stopped")
        
        if self.system_capture_thread:
            self.system_capture_thread.join(timeout=5.0)
            print("✓ System capture stopped")
        
        if self.system_processing_thread:
            self.system_processing_thread.join(timeout=5.0)
            print("✓ System processing stopped")
        
        # Process remaining audio
        if self.mic_buffer and self.mic_buffer_duration > 1.0:
            print("Processing remaining mic audio...")
            self._transcribe_buffer(self.mic_buffer, "Mic")
        
        if self.system_buffer and self.system_buffer_duration > 1.0:
            print("Processing remaining system audio...")
            self._transcribe_buffer(self.system_buffer, "System")
        
        print("✓ Recording stopped")
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'audio'):
            self.audio.terminate()


# ============================================================================
# TESTING CODE
# ============================================================================

if __name__ == "__main__":
    """Test the enhanced audio processor."""
    
    def on_transcript(text, source):
        print(f"\n{'='*60}")
        print(f"[{source} TRANSCRIPT] {text}")
        print('='*60 + "\n")
    
    # Test system audio detection
    print("\n" + "="*60)
    print("ENHANCED AUDIO PROCESSOR TEST")
    print("="*60)
    
    print("\nAvailable audio sources:")
    print("1. Microphone only")
    print("2. System audio only (Google Meet/Zoom)")
    print("3. Both (separate streams)")
    
    # Show available devices
    try:
        import soundcard as sc
        print("\n" + "-"*60)
        print("DETECTED AUDIO DEVICES:")
        print("-"*60)
        
        # Show speakers
        speakers = sc.all_speakers()
        if speakers:
            print("\nOutput Devices (Speakers):")
            for i, spk in enumerate(speakers, 1):
                default = " (default)" if spk == sc.default_speaker() else ""
                print(f"  {i}. {spk.name}{default}")
        
        # Show microphones with loopback
        mics = sc.all_microphones(include_loopback=True)
        if mics:
            print("\nInput Devices (Microphones + Loopback):")
            for i, mic in enumerate(mics, 1):
                is_loop = " [LOOPBACK]" if hasattr(mic, 'isloopback') and mic.isloopback else ""
                print(f"  {i}. {mic.name}{is_loop}")
        print("-"*60)
    except Exception as e:
        print(f"\nCould not enumerate devices: {e}")
    
    choice = input("\nSelect mode (1/2/3): ").strip()
    
    mode_map = {"1": "mic", "2": "system", "3": "both"}
    mode = mode_map.get(choice, "mic")
    
    print(f"\nTesting {mode.upper()} mode for 30 seconds...")
    print("="*60 + "\n")
    
    try:
        processor = EnhancedAudioProcessor(on_transcript, audio_source=mode)
        
        if processor.start_recording():
            time.sleep(30)
            processor.stop_recording()
        else:
            print("\n❌ Failed to start recording!")
            print("If system audio failed, you may need to enable Stereo Mix.")
            print("See WINDOWS_AUDIO_SETUP.md for instructions.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60)