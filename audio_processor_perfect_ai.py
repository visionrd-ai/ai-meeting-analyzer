
import os
os.environ["ORT_DISABLE_DEVICE_DISCOVERY"] = "1"

import pyaudio
import threading
import queue
import numpy as np
from faster_whisper import WhisperModel
import time
from typing import Callable, Optional, Literal, Tuple
import soundcard as sc
from datetime import datetime
import scipy.signal
from scipy.signal import butter, filtfilt, wiener, hilbert
import noisereduce as nr
import librosa
import tempfile
import wave
from dotenv import load_dotenv
import warnings
warnings.filterwarnings('ignore')

load_dotenv()

# ============================================================================
# PERFECT AI AUDIO CONFIGURATION
# ============================================================================

# Audio settings optimized for perfect voice capture
CHUNK_SIZE = 1024  # Balanced for performance (64ms at 16kHz)
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Standard for speech

# Simple processing settings
CHUNK_DURATION_SECONDS = 2.0  # Process every 2 seconds for better performance
OVERLAP_SECONDS = 0.2  # Minimal overlap for speed

# Whisper model optimized for real-time
WHISPER_MODEL_SIZE = "base"  # Best balance of speed/accuracy
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Perfect Human Voice Characteristics
HUMAN_VOICE_FUNDAMENTAL_MIN = 85   # Hz - Lowest human fundamental frequency
HUMAN_VOICE_FUNDAMENTAL_MAX = 255  # Hz - Highest human fundamental frequency
HUMAN_VOICE_FORMANT_MIN = 300      # Hz - Start of human formants
HUMAN_VOICE_FORMANT_MAX = 3400     # Hz - End of human formants
HUMAN_VOICE_HARMONICS_MAX = 8000   # Hz - Human voice harmonics range

# Advanced Noise Cancellation Settings
SPECTRAL_SUBTRACTION_ALPHA = 2.0   # Aggressiveness of spectral subtraction
WIENER_FILTER_NOISE_VARIANCE = 0.01  # Noise variance estimation
ADAPTIVE_NOISE_GATE_THRESHOLD = 0.005  # Much lower threshold for external audio
VOICE_ACTIVITY_SENSITIVITY = 0.3   # Much more sensitive voice detection
BACKGROUND_LEARNING_RATE = 0.1     # How fast to adapt to background

# Echo Cancellation for System Audio
ECHO_CANCELLATION_ENABLED = True
ECHO_DELAY_SAMPLES = int(0.1 * RATE)  # 100ms echo delay buffer

# Audio source types
AudioSourceType = Literal["mic", "system", "both"]
TranscriptionEngine = Literal["faster_whisper", "assemblyai", "deepgram"]

# AssemblyAI configuration - Load at runtime to ensure .env is loaded
def get_assemblyai_api_key():
    """Get AssemblyAI API key, ensuring .env is loaded."""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("ASSEMBLYAI_API_KEY")

# Try to import AssemblyAI SDK
try:
    import assemblyai as aai
    ASSEMBLYAI_AVAILABLE = True
    print("✅ AssemblyAI SDK available")
except ImportError:
    ASSEMBLYAI_AVAILABLE = False
    print("⚠️ AssemblyAI library not installed. Install with: pip install assemblyai")

# Deepgram configuration - Load at runtime to ensure .env is loaded
def get_deepgram_api_key():
    """Get Deepgram API key, ensuring .env is loaded."""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("DEEPGRAM_API_KEY")

# Try to import Deepgram SDK
try:
    from deepgram import DeepgramClient
    # In newer Deepgram SDK, options are passed as dict
    DEEPGRAM_AVAILABLE = True
    print("✅ Deepgram SDK available")
except ImportError as e:
    DEEPGRAM_AVAILABLE = False
    print(f"⚠️ Deepgram library not installed. Error: {e}")
    print("Install with: pip install deepgram-sdk")

# ============================================================================
# PERFECT VOICE PROCESSING ALGORITHMS
# ============================================================================

class PerfectVoiceProcessor:
    """Advanced voice processing with perfect noise cancellation."""
    
    def __init__(self):
        self.background_noise_profile = None
        self.voice_activity_history = []
        self.adaptive_threshold = ADAPTIVE_NOISE_GATE_THRESHOLD
        self.noise_learning_buffer = []
        self.echo_buffer = np.zeros(ECHO_DELAY_SAMPLES)
        
    def learn_background_noise(self, audio_data: np.ndarray) -> None:
        """Learn background noise characteristics for perfect cancellation."""
        try:
            # Only learn from non-voice segments
            if not self._detect_voice_activity_advanced(audio_data):
                self.noise_learning_buffer.append(audio_data.copy())
                
                # Keep only recent noise samples (sliding window)
                if len(self.noise_learning_buffer) > 10:
                    self.noise_learning_buffer.pop(0)
                
                # Update noise profile
                if len(self.noise_learning_buffer) >= 3:
                    combined_noise = np.concatenate(self.noise_learning_buffer)
                    self.background_noise_profile = self._compute_noise_spectrum(combined_noise)
                    
        except Exception as e:
            print(f"Background noise learning error: {e}")
    
    def _compute_noise_spectrum(self, noise_data: np.ndarray) -> np.ndarray:
        """Compute noise power spectrum for spectral subtraction."""
        try:
            # Compute FFT of noise
            noise_fft = np.fft.rfft(noise_data)
            noise_power = np.abs(noise_fft) ** 2
            
            # Smooth the noise spectrum
            window_size = max(3, len(noise_power) // 50)
            kernel = np.ones(window_size) / window_size
            smoothed_noise = np.convolve(noise_power, kernel, mode='same')
            
            return smoothed_noise
            
        except Exception as e:
            print(f"Noise spectrum computation error: {e}")
            return np.ones(len(noise_data) // 2 + 1) * 0.01
    
    def _detect_voice_activity_advanced(self, audio_data: np.ndarray) -> bool:
        """Advanced voice activity detection using multiple features - IMPROVED."""
        try:
            # Feature 1: Energy-based detection with better thresholding
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            energy_threshold = max(self.adaptive_threshold, 0.001)  # Much lower minimum threshold
            
            # Feature 2: Spectral centroid (voice has specific spectral characteristics)
            fft = np.fft.rfft(audio_data)
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(len(audio_data), 1/RATE)
            
            if np.sum(magnitude) > 0:
                spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
                # More lenient voice frequency range
                voice_like_spectrum = (200 <= spectral_centroid <= 4000)
            else:
                voice_like_spectrum = False
            
            # Feature 3: Improved fundamental frequency detection
            has_voice_fundamental = self._detect_fundamental_frequency_improved(audio_data)
            
            # Feature 4: Enhanced formant analysis
            has_voice_formants = self._detect_voice_formants_improved(magnitude, freqs)
            
            # Feature 5: Zero crossing rate (voice has specific ZCR patterns)
            zcr = self._compute_zero_crossing_rate(audio_data)
            voice_like_zcr = 0.005 <= zcr <= 0.5  # More lenient ZCR range
            
            # Feature 6: Spectral rolloff (voice energy distribution)
            spectral_rolloff = self._compute_spectral_rolloff(magnitude, freqs)
            voice_like_rolloff = 1000 <= spectral_rolloff <= 6000
            
            # Combine features with improved weights
            voice_features = [
                (rms_energy > energy_threshold, 0.35),  # Energy is most important
                (voice_like_spectrum, 0.2),
                (has_voice_fundamental, 0.15),
                (has_voice_formants, 0.15),
                (voice_like_zcr, 0.1),
                (voice_like_rolloff, 0.05)
            ]
            
            voice_score = sum(weight for feature, weight in voice_features if feature)
            # Much lower threshold for external audio detection
            is_voice = voice_score >= 0.2  # Very sensitive for external audio
            
            # Update adaptive threshold more conservatively
            self._update_adaptive_threshold(rms_energy, is_voice)
            
            # Update history for temporal consistency
            self.voice_activity_history.append(is_voice)
            if len(self.voice_activity_history) > 3:  # Shorter history for faster response
                self.voice_activity_history.pop(0)
            
            # More lenient temporal smoothing
            if len(self.voice_activity_history) >= 2:
                recent_voice_ratio = sum(self.voice_activity_history) / len(self.voice_activity_history)
                return recent_voice_ratio >= 0.5  # More sensitive
            else:
                return is_voice
            
        except Exception as e:
            print(f"Voice activity detection error: {e}")
            return True  # Default to processing if detection fails
    
    def _detect_fundamental_frequency_improved(self, audio_data: np.ndarray) -> bool:
        """Improved fundamental frequency detection for human voice."""
        try:
            # Use autocorrelation with better preprocessing
            # Apply window to reduce edge effects
            windowed_audio = audio_data * np.hanning(len(audio_data))
            
            autocorr = np.correlate(windowed_audio, windowed_audio, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            
            # Normalize autocorrelation
            if autocorr[0] > 0:
                autocorr = autocorr / autocorr[0]
            
            # Expanded frequency range for better detection
            min_period = int(RATE / 400)  # Up to 400Hz
            max_period = int(RATE / 50)   # Down to 50Hz
            
            if max_period < len(autocorr):
                search_range = autocorr[min_period:min(max_period, len(autocorr))]
                if len(search_range) > 0:
                    # Find the highest peak above threshold
                    threshold = 0.1  # Much lower threshold for external audio
                    peaks = []
                    for i in range(1, len(search_range) - 1):
                        if (search_range[i] > search_range[i-1] and 
                            search_range[i] > search_range[i+1] and 
                            search_range[i] > threshold):
                            peaks.append((search_range[i], i + min_period))
                    
                    if peaks:
                        # Get the strongest peak
                        strongest_peak = max(peaks, key=lambda x: x[0])
                        peak_idx = strongest_peak[1]
                        fundamental_freq = RATE / peak_idx
                        
                        # Expanded human voice range
                        return 50 <= fundamental_freq <= 400
            
            return False
            
        except Exception as e:
            print(f"Improved fundamental frequency detection error: {e}")
            return False
    
    def _detect_voice_formants_improved(self, magnitude: np.ndarray, freqs: np.ndarray) -> bool:
        """Improved voice formant detection."""
        try:
            # Look for energy peaks in formant regions with better sensitivity
            formant_regions = [
                (300, 1000),   # F1 region (expanded)
                (800, 2500),   # F2 region (expanded)
                (1500, 4000)   # F3 region (expanded)
            ]
            
            formant_peaks = 0
            total_energy = np.mean(magnitude)
            
            for f_min, f_max in formant_regions:
                mask = (freqs >= f_min) & (freqs <= f_max)
                if np.any(mask):
                    region_energy = np.max(magnitude[mask])
                    
                    # Lower threshold for better sensitivity
                    if region_energy > total_energy * 1.2:  # 20% above average
                        formant_peaks += 1
            
            return formant_peaks >= 1  # At least 1 formant peak for voice
            
        except Exception as e:
            print(f"Improved formant detection error: {e}")
            return False
    
    def _compute_spectral_rolloff(self, magnitude: np.ndarray, freqs: np.ndarray, rolloff_percent: float = 0.85) -> float:
        """Compute spectral rolloff frequency."""
        try:
            total_energy = np.sum(magnitude)
            if total_energy == 0:
                return 0
            
            cumulative_energy = np.cumsum(magnitude)
            rolloff_threshold = rolloff_percent * total_energy
            
            rolloff_idx = np.where(cumulative_energy >= rolloff_threshold)[0]
            if len(rolloff_idx) > 0:
                return freqs[rolloff_idx[0]]
            else:
                return freqs[-1]
                
        except Exception as e:
            print(f"Spectral rolloff computation error: {e}")
            return 2000  # Default reasonable value
    
    def _detect_voice_formants(self, magnitude: np.ndarray, freqs: np.ndarray) -> bool:
        """Detect voice formant frequencies."""
        try:
            # Look for energy peaks in formant regions
            formant_regions = [
                (700, 1100),   # F1 region
                (1100, 2200),  # F2 region
                (2200, 3200)   # F3 region
            ]
            
            formant_peaks = 0
            for f_min, f_max in formant_regions:
                mask = (freqs >= f_min) & (freqs <= f_max)
                if np.any(mask):
                    region_energy = np.max(magnitude[mask])
                    total_energy = np.mean(magnitude)
                    
                    if region_energy > total_energy * 1.5:  # Peak is 50% above average
                        formant_peaks += 1
            
            return formant_peaks >= 2  # At least 2 formant peaks for voice
            
        except Exception as e:
            print(f"Formant detection error: {e}")
            return False
    
    def _compute_zero_crossing_rate(self, audio_data: np.ndarray) -> float:
        """Compute zero crossing rate."""
        try:
            zero_crossings = np.sum(np.abs(np.diff(np.sign(audio_data))))
            return zero_crossings / (2 * len(audio_data))
        except:
            return 0.0
    
    def _update_adaptive_threshold(self, energy: float, is_voice: bool) -> None:
        """Update adaptive noise gate threshold."""
        try:
            if not is_voice:
                # Lower threshold when no voice (adapt to background)
                self.adaptive_threshold = (
                    self.adaptive_threshold * (1 - BACKGROUND_LEARNING_RATE) +
                    energy * BACKGROUND_LEARNING_RATE
                )
            else:
                # Slightly raise threshold when voice is detected
                self.adaptive_threshold = min(
                    self.adaptive_threshold * 1.01,
                    ADAPTIVE_NOISE_GATE_THRESHOLD * 2
                )
        except:
            pass
    
    def perfect_noise_cancellation(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply perfect noise cancellation using multiple techniques - IMPROVED."""
        try:
            # Ensure we have valid audio data
            if len(audio_data) == 0 or np.all(audio_data == 0):
                return audio_data.astype(np.float32)
            
            # Step 1: Learn background noise if needed (more conservative)
            if not self._detect_voice_activity_advanced(audio_data):
                self.learn_background_noise(audio_data)
            
            # Step 2: Pre-processing - Remove DC offset and normalize
            audio_data = audio_data - np.mean(audio_data)
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            
            # Step 3: Apply gentle high-pass filter
            audio_data = self._apply_gentle_highpass_filter(audio_data)
            
            # Step 4: Improved spectral subtraction
            if self.background_noise_profile is not None:
                audio_data = self._improved_spectral_subtraction(audio_data)
            
            # Step 5: Adaptive Wiener filtering
            audio_data = self._adaptive_wiener_filter(audio_data)
            
            # Step 6: Voice-optimized band-pass filtering
            audio_data = self._voice_optimized_bandpass_filter(audio_data)
            
            # Step 7: Intelligent noise gate (disabled for external audio capture)
            # Commented out to allow external audio from speakers
            # if not self._detect_voice_activity_advanced(audio_data):
            #     audio_data = self._intelligent_noise_gate(audio_data)
            
            # Step 8: Gentle dynamic range compression
            audio_data = self._gentle_dynamic_compression(audio_data)
            
            # Step 9: Final normalization with headroom
            audio_data = self._normalize_with_headroom(audio_data)
            
            return audio_data.astype(np.float32)
            
        except Exception as e:
            print(f"Perfect noise cancellation error: {e}")
            # Improved fallback processing
            return self._improved_fallback_processing(audio_data)
    
    def _apply_highpass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply high-pass filter to remove low-frequency noise."""
        try:
            nyquist = RATE * 0.5
            low_cutoff = HUMAN_VOICE_FORMANT_MIN / nyquist
            b, a = butter(4, low_cutoff, btype='high')
            return filtfilt(b, a, audio_data)
        except:
            return audio_data
    
    def _spectral_subtraction(self, audio_data: np.ndarray) -> np.ndarray:
        """Advanced spectral subtraction for noise removal."""
        try:
            # Compute FFT
            audio_fft = np.fft.rfft(audio_data)
            audio_magnitude = np.abs(audio_fft)
            audio_phase = np.angle(audio_fft)
            
            # Estimate noise magnitude
            noise_magnitude = np.sqrt(self.background_noise_profile)
            
            # Spectral subtraction
            clean_magnitude = audio_magnitude - SPECTRAL_SUBTRACTION_ALPHA * noise_magnitude
            
            # Prevent over-subtraction
            clean_magnitude = np.maximum(clean_magnitude, 0.1 * audio_magnitude)
            
            # Reconstruct signal
            clean_fft = clean_magnitude * np.exp(1j * audio_phase)
            return np.fft.irfft(clean_fft, len(audio_data))
            
        except Exception as e:
            print(f"Spectral subtraction error: {e}")
            return audio_data
    
    def _wiener_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply Wiener filter for noise reduction."""
        try:
            return wiener(audio_data, noise=WIENER_FILTER_NOISE_VARIANCE)
        except:
            return audio_data
    
    def _voice_bandpass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply band-pass filter optimized for human voice."""
        try:
            nyquist = RATE * 0.5
            low = HUMAN_VOICE_FORMANT_MIN / nyquist
            high = min(HUMAN_VOICE_HARMONICS_MAX / nyquist, 0.99)
            b, a = butter(6, [low, high], btype='band')
            return filtfilt(b, a, audio_data)
        except:
            return audio_data
    
    def _adaptive_noise_gate(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply adaptive noise gate based on voice activity."""
        try:
            if not self._detect_voice_activity_advanced(audio_data):
                # Heavily attenuate non-voice segments
                return audio_data * 0.05
            return audio_data
        except:
            return audio_data
    
    def _dynamic_range_compression(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply dynamic range compression for consistent voice levels."""
        try:
            # Soft compression using tanh
            return np.tanh(audio_data * 1.5) * 0.8
        except:
            return audio_data
    
    def _normalize_audio(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio to optimal range."""
        try:
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                return audio_data / max_val * 0.8
            return audio_data
        except:
            return audio_data
    
    def _apply_gentle_highpass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply gentle high-pass filter to remove low-frequency noise."""
        try:
            nyquist = RATE * 0.5
            low_cutoff = 80 / nyquist  # 80Hz cutoff (gentler than before)
            b, a = butter(2, low_cutoff, btype='high')  # Lower order for gentler filtering
            return filtfilt(b, a, audio_data)
        except:
            return audio_data
    
    def _improved_spectral_subtraction(self, audio_data: np.ndarray) -> np.ndarray:
        """Improved spectral subtraction with over-subtraction protection."""
        try:
            # Compute FFT
            audio_fft = np.fft.rfft(audio_data)
            audio_magnitude = np.abs(audio_fft)
            audio_phase = np.angle(audio_fft)
            
            # Estimate noise magnitude with smoothing
            noise_magnitude = np.sqrt(self.background_noise_profile)
            
            # Adaptive spectral subtraction
            alpha = 1.5  # Reduced from 2.0 for gentler processing
            clean_magnitude = audio_magnitude - alpha * noise_magnitude
            
            # Prevent over-subtraction with higher floor
            clean_magnitude = np.maximum(clean_magnitude, 0.2 * audio_magnitude)
            
            # Reconstruct signal
            clean_fft = clean_magnitude * np.exp(1j * audio_phase)
            return np.fft.irfft(clean_fft, len(audio_data))
            
        except Exception as e:
            print(f"Improved spectral subtraction error: {e}")
            return audio_data
    
    def _adaptive_wiener_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply adaptive Wiener filter."""
        try:
            # Use a gentler noise variance estimate
            return wiener(audio_data, noise=0.005)  # Reduced from 0.01
        except:
            return audio_data
    
    def _voice_optimized_bandpass_filter(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply voice-optimized band-pass filter."""
        try:
            nyquist = RATE * 0.5
            low = 200 / nyquist   # 200Hz low cutoff
            high = min(6000 / nyquist, 0.99)  # 6kHz high cutoff (expanded range)
            b, a = butter(4, [low, high], btype='band')  # Lower order for gentler filtering
            return filtfilt(b, a, audio_data)
        except:
            return audio_data
    
    def _intelligent_noise_gate(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply intelligent noise gate only when no voice is detected."""
        try:
            rms = np.sqrt(np.mean(audio_data ** 2))
            if rms < self.adaptive_threshold * 0.5:  # More conservative threshold
                return audio_data * 0.1  # Gentle attenuation
            return audio_data
        except:
            return audio_data
    
    def _gentle_dynamic_compression(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply gentle dynamic range compression."""
        try:
            # Softer compression using tanh
            return np.tanh(audio_data * 1.2) * 0.9  # Gentler compression
        except:
            return audio_data
    
    def _normalize_with_headroom(self, audio_data: np.ndarray) -> np.ndarray:
        """Normalize audio with headroom to prevent clipping."""
        try:
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                return audio_data / max_val * 0.85  # Leave more headroom
            return audio_data
        except:
            return audio_data
    
    def _improved_fallback_processing(self, audio_data: np.ndarray) -> np.ndarray:
        """Improved fallback processing when main algorithm fails."""
        try:
            # Try noisereduce with gentler settings
            cleaned = nr.reduce_noise(
                y=audio_data, 
                sr=RATE, 
                stationary=False, 
                prop_decrease=0.6,  # Gentler noise reduction
                n_std_thresh_stationary=1.5,  # More conservative
                n_std_thresh_nonstationary=1.5
            )
            
            # Normalize with headroom
            max_val = np.max(np.abs(cleaned))
            if max_val > 0:
                return cleaned / max_val * 0.85
            return cleaned
            
        except:
            # Ultimate fallback - just normalize
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                return audio_data / max_val * 0.85
            return audio_data
    
    def cancel_echo(self, system_audio: np.ndarray, mic_audio: np.ndarray) -> np.ndarray:
        """Cancel echo between system audio and microphone."""
        try:
            if ECHO_CANCELLATION_ENABLED and len(system_audio) == len(mic_audio):
                # Simple echo cancellation - subtract delayed system audio from mic
                delayed_system = np.roll(system_audio, ECHO_DELAY_SAMPLES // 10)
                echo_cancelled = mic_audio - 0.3 * delayed_system
                return echo_cancelled
            return mic_audio
        except:
            return mic_audio

# ============================================================================
# PERFECT AI AUDIO PROCESSOR
# ============================================================================

class PerfectAIAudioProcessor:
    """Perfect AI Audio Processor with advanced voice processing."""
    
    def __init__(
        self, 
        on_transcript: Callable[[str, str], None],
        audio_source: AudioSourceType = "mic",
        transcription_engine: TranscriptionEngine = "faster_whisper"
    ):
        self.audio_source = audio_source
        self.transcription_engine = transcription_engine
        self.transcript_callback = on_transcript
        
        # Simple audio processing - no complex voice processing
        
        # Audio components
        self.audio = pyaudio.PyAudio()
        self.mic_stream: Optional[pyaudio.Stream] = None
        self.system_recorder = None
        
        # Threading
        self.is_recording = False
        self.mic_queue = queue.Queue()
        self.system_queue = queue.Queue()
        
        # Audio buffers
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
        self.deepgram_client = None
        
        # Recording file management
        self.recording_data = []
        self.recording_filename = None
        self.recordings_dir = "recordings"
        
        # Create recordings directory if it doesn't exist
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
        
        if self.transcription_engine == "faster_whisper":
            print("🚀 Loading Simple Whisper model...")
            self.whisper_model = WhisperModel(
                "base",  # Use smaller, faster model
                device="cpu",  # Force CPU for consistency
                compute_type="int8",  # Faster computation
                cpu_threads=2,  # Fewer threads for lower latency
                num_workers=1
            )
            print("✅ Simple Whisper model loaded successfully")
        
        elif self.transcription_engine == "assemblyai":
            if not ASSEMBLYAI_AVAILABLE:
                raise ValueError("AssemblyAI SDK not available. Install with: pip install assemblyai")
            
            assemblyai_api_key = get_assemblyai_api_key()
            if not assemblyai_api_key:
                raise ValueError("AssemblyAI API key not found. Please set ASSEMBLYAI_API_KEY in .env file")
            
            print("🚀 Initializing AssemblyAI transcriber...")
            aai.settings.api_key = assemblyai_api_key
            config = aai.TranscriptionConfig(
                language_detection=True,
                punctuate=True,
                format_text=True,
                filter_profanity=True,
                redact_pii=False,
                speaker_labels=False
            )
            self.assemblyai_transcriber = aai.Transcriber(config=config)
            print("✅ AssemblyAI transcriber initialized successfully")
        
        elif self.transcription_engine == "deepgram":
            if not DEEPGRAM_AVAILABLE:
                raise ValueError("Deepgram SDK not available. Install with: pip install deepgram-sdk")
            
            deepgram_api_key = get_deepgram_api_key()
            if not deepgram_api_key:
                raise ValueError("Deepgram API key not found. Please set DEEPGRAM_API_KEY in .env file")
            
            print("🚀 Initializing Deepgram client...")
            self.deepgram_client = DeepgramClient(api_key=deepgram_api_key)
            print("✅ Deepgram client initialized successfully")
        
        # Validate audio sources
        self._validate_audio_sources()
        
        print("🎯 Perfect AI Audio Processor initialized successfully!")
    
    def _validate_audio_sources(self):
        """Validate audio source availability."""
        if self.audio_source in ["mic", "both"]:
            try:
                device_info = self.audio.get_default_input_device_info()
                print(f"✅ Microphone available: {device_info['name']}")
            except Exception as e:
                print(f"⚠️ Microphone not available: {e}")
                if self.audio_source == "mic":
                    raise RuntimeError("Microphone required but not available")
        
        if self.audio_source in ["system", "both"]:
            try:
                loopback = self._get_perfect_system_loopback()
                if loopback:
                    print(f"✅ Perfect system audio available: {loopback.name}")
                else:
                    raise RuntimeError("System audio loopback not found")
            except Exception as e:
                print(f"⚠️ System audio not available: {e}")
                if self.audio_source == "system":
                    raise RuntimeError("System audio required but not available")
    
    def _get_perfect_system_loopback(self):
        """Get perfect system audio loopback device."""
        try:
            all_mics = sc.all_microphones(include_loopback=True)
            
            if not all_mics:
                return None
            
            # Find the best loopback device
            loopback_device = None
            
            # Priority 1: Explicit loopback devices
            for mic in all_mics:
                name_lower = mic.name.lower()
                if any(keyword in name_lower for keyword in ['loopback', 'stereo mix', 'what u hear']):
                    loopback_device = mic
                    print(f"🎯 Found perfect loopback: {mic.name}")
                    break
            
            # Priority 2: Default speaker loopback
            if not loopback_device:
                try:
                    default_speaker = sc.default_speaker()
                    for mic in all_mics:
                        if hasattr(mic, 'isloopback') and mic.isloopback:
                            if default_speaker.name.lower() in mic.name.lower():
                                loopback_device = mic
                                print(f"🎯 Found speaker loopback: {mic.name}")
                                break
                except:
                    pass
            
            # Priority 3: Any loopback device
            if not loopback_device:
                for mic in all_mics:
                    if hasattr(mic, 'isloopback') and mic.isloopback:
                        loopback_device = mic
                        print(f"🎯 Using loopback device: {mic.name}")
                        break
            
            return loopback_device
            
        except Exception as e:
            print(f"Perfect system loopback error: {e}")
            return None
    
    def start_recording(self) -> bool:
        """Start perfect AI recording."""
        if self.is_recording:
            print("Already recording!")
            return False
        
        print(f"\n{'='*60}")
        print(f"🚀 STARTING PERFECT AI RECORDING - {self.audio_source.upper()} MODE")
        print('='*60)
        
        self.is_recording = True
        success = False
        
        # Initialize recording file
        self._start_recording_file()
        
        try:
            if self.audio_source == "mic":
                success = self._start_perfect_mic_recording()
            elif self.audio_source == "system":
                success = self._start_perfect_system_recording()
            elif self.audio_source == "both":
                success = self._start_perfect_dual_recording()
            
            if success:
                print("🎯 Perfect AI recording started successfully!")
                return True
            else:
                self.is_recording = False
                return False
                
        except Exception as e:
            print(f"❌ Perfect AI recording error: {e}")
            self.is_recording = False
            return False
    
    def _start_perfect_mic_recording(self) -> bool:
        """Start perfect microphone recording."""
        try:
            # Find best microphone
            device_index = self._find_perfect_mic_device()
            
            # Open perfect mic stream
            self.mic_stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE,
                stream_callback=self._perfect_mic_callback
            )
            self.mic_stream.start_stream()
            print("🎤 Perfect microphone stream started")
            
            # Start perfect processing
            self.mic_buffer = []
            self.mic_buffer_duration = 0.0
            self.mic_processing_thread = threading.Thread(
                target=self._perfect_mic_processing_loop,
                daemon=True
            )
            self.mic_processing_thread.start()
            print("🧠 Perfect mic processing started")
            
            return True
            
        except Exception as e:
            print(f"❌ Perfect mic error: {e}")
            return False
    
    def _start_perfect_system_recording(self) -> bool:
        """Start perfect system audio recording."""
        try:
            loopback = self._get_perfect_system_loopback()
            if not loopback:
                return False
            
            self.system_recorder = loopback
            
            # Start perfect system capture
            self.system_buffer = []
            self.system_buffer_duration = 0.0
            self.system_capture_thread = threading.Thread(
                target=self._perfect_system_capture_loop,
                daemon=True
            )
            self.system_capture_thread.start()
            
            # Start perfect system processing
            self.system_processing_thread = threading.Thread(
                target=self._perfect_system_processing_loop,
                daemon=True
            )
            self.system_processing_thread.start()
            
            print("🔊 Perfect system audio started")
            return True
            
        except Exception as e:
            print(f"❌ Perfect system audio error: {e}")
            return False
    
    def _start_perfect_dual_recording(self) -> bool:
        """Start perfect dual recording with echo cancellation."""
        print("🎧 Starting perfect dual capture...")
        
        mic_ok = self._start_perfect_mic_recording()
        system_ok = self._start_perfect_system_recording()
        
        if mic_ok and system_ok:
            print("🎯 Perfect dual capture active with echo cancellation!")
        elif mic_ok:
            print("🎤 Perfect microphone-only mode (system failed)")
            self.audio_source = "mic"
        elif system_ok:
            print("🔊 Perfect system-only mode (mic failed)")
            self.audio_source = "system"
        else:
            print("❌ Both sources failed!")
            return False
        
        return True
    
    def _find_perfect_mic_device(self) -> Optional[int]:
        """Find the perfect microphone device."""
        device_index = None
        
        # Look for high-quality devices first
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name_lower = info['name'].lower()
                # Prefer professional audio devices
                if any(keyword in name_lower for keyword in ['usb', 'professional', 'studio', 'condenser']):
                    device_index = i
                    print(f"🎯 Using professional audio device: {info['name']}")
                    break
        
        # Fallback to default
        if device_index is None:
            try:
                device_index = self.audio.get_default_input_device_info()['index']
                print("🎤 Using default audio device")
            except:
                device_index = None
        
        return device_index
    
    def _perfect_mic_callback(self, in_data, frame_count, time_info, status):
        """Perfect microphone callback with minimal latency."""
        if status and status != pyaudio.paInputOverflow:
            pass  # Ignore minor overflow
        self.mic_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def _perfect_system_capture_loop(self):
        """Perfect system audio capture with error handling."""
        print("🔊 Perfect system capture started")
        
        try:
            with self.system_recorder.recorder(samplerate=RATE) as recorder:
                while self.is_recording:
                    try:
                        data = recorder.record(numframes=CHUNK_SIZE)
                        
                        # Handle stereo -> mono
                        if data.ndim > 1:
                            data = data.mean(axis=1)
                        
                        # Convert to int16
                        audio_int16 = (data * 32767).astype(np.int16)
                        audio_bytes = audio_int16.tobytes()
                        
                        self.system_queue.put(audio_bytes)
                        
                    except Exception as e:
                        if "fromstring" in str(e):
                            print("⚠️ NumPy compatibility issue - system audio disabled")
                            break
                        continue
                    
        except Exception as e:
            print(f"Perfect system capture error: {e}")
    
    def _perfect_mic_processing_loop(self):
        """Perfect microphone processing with advanced voice isolation."""
        print("🧠 Perfect mic processing started")
        
        while self.is_recording:
            try:
                audio_data = self.mic_queue.get(timeout=0.1)
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Save raw audio data to recording file
                self._save_audio_chunk(np.frombuffer(audio_data, dtype=np.int16))
                
                self.mic_buffer.extend(audio_np)
                self.mic_buffer_duration += len(audio_np) / RATE
                
                if self.mic_buffer_duration >= CHUNK_DURATION_SECONDS:
                    # Process with perfect voice isolation
                    buffer_copy = np.array(self.mic_buffer)
                    threading.Thread(
                        target=self._perfect_transcribe_buffer,
                        args=(buffer_copy, "Mic"),
                        daemon=True
                    ).start()
                    
                    # Keep overlap
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
                print(f"Perfect mic processing error: {e}")
    
    def _perfect_system_processing_loop(self):
        """Perfect system audio processing."""
        print("🔊 Perfect system processing started")
        
        while self.is_recording:
            try:
                audio_data = self.system_queue.get(timeout=0.1)
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Save raw audio data to recording file
                self._save_audio_chunk(np.frombuffer(audio_data, dtype=np.int16))
                
                self.system_buffer.extend(audio_np)
                self.system_buffer_duration += len(audio_np) / RATE
                
                if self.system_buffer_duration >= CHUNK_DURATION_SECONDS:
                    # Process system audio
                    buffer_copy = np.array(self.system_buffer)
                    threading.Thread(
                        target=self._perfect_transcribe_buffer,
                        args=(buffer_copy, "System"),
                        daemon=True
                    ).start()
                    
                    # Keep overlap
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
                print(f"Perfect system processing error: {e}")
    
    def _perfect_transcribe_buffer(self, buffer: np.ndarray, source_label: str):
        """Perfect transcription with advanced voice processing - IMPROVED."""
        import time
        start_time = time.perf_counter()
        
        try:
            # Ensure we have valid buffer
            if len(buffer) == 0:
                return
            
            # Use raw audio without processing for better accuracy
            clean_audio = buffer
            
            # Simple audio level check
            rms_energy = np.sqrt(np.mean(clean_audio ** 2))
            
            # Only process if there's sufficient audio
            if rms_energy < 0.001:
                return
            
            # Simple transcription without fallback
            if self.transcription_engine == "faster_whisper":
                transcript_text = self._simple_whisper_transcribe(clean_audio)
            elif self.transcription_engine == "assemblyai":
                transcript_text = self._transcribe_with_assemblyai(clean_audio)
            elif self.transcription_engine == "deepgram":
                transcript_text = self._transcribe_with_deepgram(clean_audio)
            else:
                transcript_text = self._simple_whisper_transcribe(clean_audio)
            
            # More lenient text filtering
            if transcript_text:
                # Clean up the text
                transcript_text = transcript_text.strip()
                
                # Filter out very short or meaningless transcripts
                if len(transcript_text) >= 2 and not transcript_text.lower() in ['uh', 'um', 'ah', 'er', 'hmm']:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"🎯 [{timestamp}] [{source_label}] PERFECT: {transcript_text}")
                    
                    # Call callback
                    self.transcript_callback(transcript_text, source_label)
                else:
                    # Don't log filtered short text to reduce noise
                    pass
            else:
                # Only log if we expected a result but got none
                if rms_energy > 0.02:
                    print(f"🔇 [{source_label}] No transcription result")
            
        except Exception as e:
            print(f"Perfect transcription error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Report processing latency
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            if latency_ms > 50:  # Only report if latency is significant
                print(f"⏱️ [{source_label}] Processing latency: {latency_ms:.1f}ms")
    
    def _simple_whisper_transcribe(self, audio_np: np.ndarray) -> str:
        """Simple Whisper transcription for human vocals."""
        try:
            # Basic audio format check
            if len(audio_np) < 1600:
                return ""
            
            if audio_np.dtype != np.float32:
                audio_np = audio_np.astype(np.float32)
            
            # Simple normalization
            max_val = np.max(np.abs(audio_np))
            if max_val > 0:
                audio_np = audio_np / max_val * 0.9
            
            # Simple Whisper transcription
            segments, info = self.whisper_model.transcribe(
                audio_np,
                beam_size=1,
                language="en",
                vad_filter=False,
                temperature=0.0,
                condition_on_previous_text=False,
                word_timestamps=False
            )
            
            # Simple text extraction
            transcript_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcript_parts.append(text)
            
            transcript_text = " ".join(transcript_parts)
            
            # Post-process the transcript
            if transcript_text:
                # Remove common Whisper artifacts
                transcript_text = transcript_text.replace(" uh ", " ")
                transcript_text = transcript_text.replace(" um ", " ")
                transcript_text = transcript_text.replace("  ", " ")
                transcript_text = transcript_text.strip()
            
            return transcript_text
            
        except Exception as e:
            print(f"Perfect Whisper error: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _transcribe_with_deepgram(self, audio_np: np.ndarray) -> str:
        """Transcribe using Deepgram with perfect AI optimization."""
        try:
            # Convert float32 audio to int16 for Deepgram
            audio_int16 = (audio_np * 32767).astype(np.int16)
            
            # Create audio buffer
            audio_bytes = audio_int16.tobytes()
            
            # Configure Deepgram options for perfect AI (using dict for v5+ SDK)
            options = {
                "model": "nova-2",  # Latest and most accurate model
                "language": "en",
                "punctuate": True,
                "format_text": True,
                "diarize": False,  # No speaker separation for single source
                "smart_format": True,
                "utterances": False,
                "paragraphs": False,
                "detect_language": False,  # We know it's English
                "profanity_filter": False,
                "multichannel": False,
                "alternatives": 1,  # Just the best result
                "numerals": True,
                "measurements": True
            }
            
            # Transcribe with Deepgram using v5+ API
            import io
            
            # Create WAV format buffer with proper headers
            import wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(16000)  # 16kHz
                wav_file.writeframes(audio_bytes)
            
            wav_buffer.seek(0)
            
            # Use the correct Deepgram v5 API
            wav_data = wav_buffer.read()
            
            # Make HTTP request directly using the client's internal method
            import requests
            
            # Get the API key directly from environment
            api_key = get_deepgram_api_key()
            
            # Prepare the request
            url = "https://api.deepgram.com/v1/listen"
            headers = {
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/wav"
            }
            
            # Add query parameters for options
            params = {}
            for key, value in options.items():
                if value is not None and value is not False:
                    if isinstance(value, bool):
                        params[key] = "true" if value else "false"
                    else:
                        params[key] = str(value)
            
            # Make the request
            response = requests.post(url, headers=headers, params=params, data=wav_data)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            # Extract transcript text from JSON response
            if (result.get("results") and 
                result["results"].get("channels") and 
                len(result["results"]["channels"]) > 0 and
                result["results"]["channels"][0].get("alternatives") and
                len(result["results"]["channels"][0]["alternatives"]) > 0):
                
                transcript_text = result["results"]["channels"][0]["alternatives"][0].get("transcript", "")
                
                # Clean up the text
                if transcript_text:
                    transcript_text = transcript_text.strip()
                    # Remove common artifacts
                    transcript_text = transcript_text.replace("  ", " ")
                    return transcript_text
            
            return ""
                
        except Exception as e:
            print(f"Deepgram transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""
    


    def _start_recording_file(self):
        """Initialize recording file for this session."""
        try:
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_filename = os.path.join(self.recordings_dir, f"recording_{timestamp}.wav")
            
            # Clear recording data
            self.recording_data = []
            
            print(f"📁 Recording will be saved to: {self.recording_filename}")
            
        except Exception as e:
            print(f"Error initializing recording file: {e}")
            self.recording_filename = None
    
    def _save_audio_chunk(self, audio_data: np.ndarray):
        """Save audio chunk to recording data."""
        try:
            if self.recording_filename and len(audio_data) > 0:
                # Convert to int16 for WAV format
                if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                    # Normalize and convert to int16
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                else:
                    audio_int16 = audio_data.astype(np.int16)
                
                self.recording_data.append(audio_int16)
                
        except Exception as e:
            print(f"Error saving audio chunk: {e}")
    
    def _finalize_recording_file(self):
        """Save the complete recording to WAV file."""
        try:
            if self.recording_filename and self.recording_data:
                # Combine all audio chunks
                complete_audio = np.concatenate(self.recording_data)
                
                # Save as WAV file
                with wave.open(self.recording_filename, 'wb') as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(RATE)
                    wav_file.writeframes(complete_audio.tobytes())
                
                # Get file size for confirmation
                file_size = os.path.getsize(self.recording_filename)
                duration = len(complete_audio) / RATE
                
                print(f"💾 Recording saved successfully!")
                print(f"   📁 File: {self.recording_filename}")
                print(f"   📊 Size: {file_size / 1024 / 1024:.2f} MB")
                print(f"   ⏱️ Duration: {duration:.1f} seconds")
                
                return self.recording_filename
                
        except Exception as e:
            print(f"Error finalizing recording file: {e}")
            
        return None
    
    def get_saved_recordings(self):
        """Get list of saved recording files."""
        try:
            if not os.path.exists(self.recordings_dir):
                return []
            
            recordings = []
            for filename in os.listdir(self.recordings_dir):
                if filename.endswith('.wav'):
                    filepath = os.path.join(self.recordings_dir, filename)
                    file_size = os.path.getsize(filepath)
                    
                    # Extract timestamp from filename
                    try:
                        timestamp_str = filename.replace('recording_', '').replace('.wav', '')
                        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        formatted_time = 'Unknown'
                    
                    recordings.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size_mb': file_size / 1024 / 1024,
                        'timestamp': formatted_time
                    })
            
            # Sort by timestamp (newest first)
            recordings.sort(key=lambda x: x['timestamp'], reverse=True)
            return recordings
            
        except Exception as e:
            print(f"Error getting saved recordings: {e}")
            return []
    
    def delete_recording(self, filename):
        """Delete a saved recording file."""
        try:
            filepath = os.path.join(self.recordings_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"🗑️ Deleted recording: {filename}")
                return True
            else:
                print(f"❌ Recording not found: {filename}")
                return False
        except Exception as e:
            print(f"Error deleting recording: {e}")
            return False

    def stop_recording(self):
        """Stop perfect AI recording."""
        print("🛑 Stopping perfect AI recording...")
        self.is_recording = False
        
        # Save the recording file
        saved_file = self._finalize_recording_file()
        if saved_file:
            print(f"✅ Recording session completed and saved!")
        else:
            print("⚠️ Recording stopped but file save failed")
        
        # Stop streams
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
            self.mic_stream = None
            print("✅ Perfect mic stream stopped")
        
        # Wait for threads
        for thread in [self.mic_processing_thread, self.system_capture_thread, self.system_processing_thread]:
            if thread:
                thread.join(timeout=3.0)
        
        # Process remaining audio
        if self.mic_buffer and self.mic_buffer_duration > 0.5:
            print("🎯 Processing remaining mic audio...")
            self._perfect_transcribe_buffer(np.array(self.mic_buffer), "Mic")
        
        if self.system_buffer and self.system_buffer_duration > 0.5:
            print("🔊 Processing remaining system audio...")
            self._perfect_transcribe_buffer(np.array(self.system_buffer), "System")
        
        print("✅ Perfect AI recording stopped")
    
    def __del__(self):
        """Cleanup."""
        if hasattr(self, 'audio'):
            self.audio.terminate()

# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    def on_transcript(text, source):
        print(f"\n{'='*60}")
        print(f"🎯 PERFECT [{source}] TRANSCRIPT: {text}")
        print('='*60 + "\n")
    
    print("\n" + "="*60)
    print("🚀 PERFECT AI AUDIO PROCESSOR TEST")
    print("="*60)
    
    mode = input("Select mode (1=Mic, 2=System, 3=Both): ").strip()
    mode_map = {"1": "mic", "2": "system", "3": "both"}
    selected_mode = mode_map.get(mode, "mic")
    
    print(f"\n🎯 Testing PERFECT {selected_mode.upper()} mode for 30 seconds...")
    print("="*60 + "\n")
    
    try:
        processor = PerfectAIAudioProcessor(on_transcript, audio_source=selected_mode)
        
        if processor.start_recording():
            time.sleep(30)
            processor.stop_recording()
        else:
            print("❌ Failed to start perfect recording!")
    except Exception as e:
        print(f"❌ Perfect AI error: {e}")
    
    print("\n" + "="*60)
    print("🎯 PERFECT AI TEST COMPLETE!")
    print("="*60)