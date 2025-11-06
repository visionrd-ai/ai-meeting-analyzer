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

FULL_TRANSCRIPT = []

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

    # at top, keep your existing imports
    from assemblyai.streaming.v3 import (
        BeginEvent,
        StreamingClient,
        StreamingClientOptions,
        StreamingError,
        StreamingEvents,
        StreamingParameters,
        StreamingSessionParameters,
        TerminationEvent,
        TurnEvent,
    )

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
# --- ADDITIVE: AAI Streaming v3 state ---
        self._aai_streaming_enabled = False           # off by default
        self._aai_streaming_source = "mic"            # "mic" or "system"
        self._aai_include_partials = False            # finals only by default
        self._aai_prefix_speaker_in_text = True      # "Speaker N: ..." prefix

        self._aai_v3_client: Optional[StreamingClient] = None
        self._aai_v3_stream_thread: Optional[threading.Thread] = None
        self._aai_v3_stop = threading.Event()
        self._aai_stream_queue = queue.Queue(maxsize=50)  # PCM frames to send

        # optional: track raw->pretty speaker mapping if needed
        self._aai_speaker_map = {}
        self._aai_next_speaker_idx = 1



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
        self.user_id = None  # Will be set when user logs in
        self.recordings_dir = "recordings"
        
        # Create base recordings directory if it doesn't exist
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
                speaker_labels=True
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

        # Additional Initialization steps for Timestamps
        self._timestamping_enabled = False
        self._transcript_events = []      # combined across all sources
        self._transcript_lock = threading.Lock()
        self._recording_start_perf = None
        self._minute_mark_thread: Optional[threading.Thread] = None
        self._transcript_sink = 'memory'  # 'memory' | 'file' | 'both'
        self._transcript_file_path: Optional[str] = None

        self._end_mark_policy = "immediate"   # "immediate" | "align_to_last_event" | "drain_then_mark"
        self._post_stop_window_sec = 2.0
        self._final_mark_emitted = False
        self._finalizer_thread = None

        # track in-flight transcribe jobs for graceful drain
        self._active_transcribe_jobs = 0
    
    def enable_assemblyai_streaming(
        self,
        *,
        diarization: bool = True,
        source_preference: Literal["mic", "system"] = "mic",
        include_partials: bool = False,
        prefix_speaker_in_text: bool = True,
    ) -> None:
        """
        Opt into AssemblyAI realtime streaming (v3) with session-wide diarization.
        Backward compatible: if not called, batch mode remains as-is.
        """
        self._aai_streaming_enabled = True
        self._aai_streaming_source = source_preference
        self._aai_include_partials = include_partials
        self._aai_prefix_speaker_in_text = prefix_speaker_in_text



    def _aai_ws_connect(self):
        """
        Open a single realtime session with diarization, then spawn sender loop.
        """
        if not ASSEMBLYAI_AVAILABLE:
            raise RuntimeError("AssemblyAI SDK not installed")
        api_key = get_assemblyai_api_key()
        if not api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY missing")

        import websocket, json

        # AAI realtime WS endpoint; pass flags in query
        url = (
            "wss://api.assemblyai.com/v2/realtime/ws"
            f"?model={self._aai_model}"
            f"&sample_rate={RATE}"
            "&punctuate=true"
            "&format_text=true"
            "&enable_diarization=true"
        )

        headers = [f"Authorization: {api_key}"]

        def on_open(ws):
            # Clear queues and flags at (re)connect
            with self._transcript_lock:
                self._aai_speaker_map.clear()
                self._aai_next_speaker_idx = 1
            self._aai_ws_stop.clear()

            # Start sender loop once socket open
            self._aai_sender_thread = threading.Thread(
                target=self._aai_sender_loop, args=(ws,), daemon=True
            )
            self._aai_sender_thread.start()

        def on_message(ws, message: str):
            try:
                data = json.loads(message)
            except Exception:
                return

            # AAI uses a variety of message types; normalize
            msg_type = data.get("message_type") or data.get("type") or ""

            is_partial = "partial" in msg_type.lower() or data.get("partial", False)
            is_final = "final" in msg_type.lower() or data.get("final", False)

            text = data.get("text") or data.get("punctuated") or data.get("transcript") or ""
            if not text:
                # Some payloads use nested fields
                if "utterance" in data and isinstance(data["utterance"], dict):
                    text = data["utterance"].get("text", "")

            # Extract speaker label if present
            speaker = self._aai_extract_speaker(data)

            # Dispatch only finals unless partials requested
            if (is_final or (self._aai_include_partials and is_partial)) and text:
                display_text = text
                if speaker and self._aai_prefix_speaker_in_text:
                    display_text = f"{speaker}: {text}"

                # Preserve your original source label contract: 'Mic' or 'System'
                source_label = "Mic" if self._aai_streaming_source == "mic" else "System"

                # Callback + timeline
                self.transcript_callback(display_text, source_label)
                self._append_transcript_event(kind='text', text=display_text, source=source_label)

        def on_error(ws, err):
            print(f"AssemblyAI realtime error: {err}")

        def on_close(ws, code, reason):
            print(f"AssemblyAI realtime closed: code={code} reason={reason}")

        self._aai_ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        # Run the WS forever in a thread
        def _runner():
            # Reconnect loop (simple)
            while self.is_recording and self._aai_streaming_enabled and not self._aai_ws_stop.is_set():
                try:
                    self._aai_ws.run_forever(ping_interval=20, ping_timeout=10)
                except Exception as e:
                    print(f"AssemblyAI realtime run_forever error: {e}")
                    time.sleep(1.0)  # backoff
                finally:
                    # stop sender thread if still alive
                    if self._aai_sender_thread and self._aai_sender_thread.is_alive():
                        self._aai_ws_stop.set()
                        self._aai_sender_thread.join(timeout=1.0)

        self._aai_ws_thread = threading.Thread(target=_runner, daemon=True)
        self._aai_ws_thread.start()


    def _aai_sender_loop(self, ws):
        """
        Drain PCM frames from queue and send to AAI ~every 60-100ms.
        Payload must be base64-encoded 16-bit linear PCM.
        """
        import base64, json, time

        # 100 ms @ 16kHz mono = 1600 samples = 3200 bytes
        target_frame_samples = int(0.1 * RATE)
        buf = bytearray()

        while self.is_recording and not self._aai_ws_stop.is_set():
            try:
                # small timeout so we can flush periodically even if quiet
                chunk = self._aai_stream_queue.get(timeout=0.1)
                buf.extend(chunk)
            except queue.Empty:
                pass

            # Flush when enough samples, or when queue empty and we have some data
            if len(buf) >= target_frame_samples * 2 or (buf and self._aai_stream_queue.empty()):
                audio_b64 = base64.b64encode(bytes(buf)).decode("utf-8")
                buf.clear()

                try:
                    ws.send(json.dumps({"audio_data": audio_b64}))
                except Exception as e:
                    print(f"AssemblyAI send error: {e}")
                    time.sleep(0.1)

        # Graceful session end
        try:
            ws.send(json.dumps({"terminate_session": True}))
        except Exception:
            pass


    def _aai_extract_speaker(self, data: dict) -> str:
        """
        Normalize diarization from different payload shapes to 'Speaker N'.
        Priority:
        1) data['utterance']['speaker']
        2) majority speaker over data['words'][*]['speaker']
        3) data['speaker']
        """
        raw = None
        utter = data.get("utterance")
        if isinstance(utter, dict):
            raw = utter.get("speaker") or utter.get("speaker_label")

        if raw is None:
            words = data.get("words") or []
            counts = {}
            for w in words:
                sp = w.get("speaker") or w.get("speaker_label")
                if sp is None:
                    continue
                counts[sp] = counts.get(sp, 0) + 1
            if counts:
                raw = max(counts.items(), key=lambda kv: kv[1])[0]

        if raw is None:
            raw = data.get("speaker") or data.get("speaker_label")

        if raw is None:
            return None

        # Map raw IDs to stable 'Speaker N'
        key = str(raw)
        mapped = self._aai_speaker_map.get(key)
        if not mapped:
            mapped = f"Speaker {self._aai_next_speaker_idx}"
            self._aai_speaker_map[key] = mapped
            self._aai_next_speaker_idx += 1
        return mapped

    # -----------------------------------------------------------------------

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

        if self.transcription_engine == "assemblyai" and self._aai_streaming_enabled:
            print("🌐 Starting AssemblyAI realtime session (v3, diarization enabled)...")
            self._aai_v3_connect()

        import time  # local import to avoid global changes

        # --- ADDITIVE: kick off minute-mark thread if enabled ---
        if self._timestamping_enabled:
            self._recording_start_perf = time.perf_counter()
            with self._transcript_lock:
                self._transcript_events = []
            # Start the minute-marker thread
            self._minute_mark_thread = threading.Thread(
                target=self._minute_mark_loop,
                daemon=True
            )
            self._minute_mark_thread.start()

        
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
                
                # --- ADDITIVE: feed mic frames to AAI streaming (if enabled & selected) ---
                if (self.transcription_engine == "assemblyai" and self._aai_streaming_enabled
                    and self._aai_streaming_source == "mic"):
                    audio_bytes = (audio_np * 32767).astype(np.int16).tobytes()
                    try:
                        self._aai_stream_queue.put(audio_bytes, timeout=0.1)
                    except queue.Full:
                        pass  # drop to keep latency low
                    continue  # skip per-chunk ASR for this source


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
                
                # --- ADDITIVE: feed system frames to AAI streaming (if enabled & selected) ---
                if (self.transcription_engine == "assemblyai" and self._aai_streaming_enabled
                    and self._aai_streaming_source == "system"):
                    audio_bytes = (audio_np * 32767).astype(np.int16).tobytes()
                    try:
                        self._aai_stream_queue.put(audio_bytes, timeout=0.1)
                    except queue.Full:
                        pass
                    continue


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

        if self._timestamping_enabled:
            with self._transcript_lock:
                self._active_transcribe_jobs += 1
        
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
                    # --- ADDITIVE: log to combined transcript timeline ---
                    self._append_transcript_event(kind='text', text=transcript_text, source=source_label)

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

            if self._timestamping_enabled:
                with self._transcript_lock:
                    self._active_transcribe_jobs = max(0, self._active_transcribe_jobs - 1)
    
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
            
            # Improved Whisper transcription with fallback for compatibility
            try:
                segments, info = self.whisper_model.transcribe(
                    audio_np,
                    beam_size=3,  # Better accuracy
                    language="en",
                    vad_filter=True,  # Enable VAD for better segmentation
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=200
                    ),
                    temperature=0.0,
                    condition_on_previous_text=True,  # Better context
                    word_timestamps=False,
                    no_speech_threshold=0.3,
                    compression_ratio_threshold=2.4
                )
            except TypeError as e:
                # Fallback for older versions with fewer parameters
                print(f"⚠️ Using fallback transcription due to parameter compatibility: {e}")
                segments, info = self.whisper_model.transcribe(
                    audio_np,
                    beam_size=3,
                    language="en",
                    temperature=0.0
                )
            
            # Simple text extraction
            transcript_parts = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    transcript_parts.append(text)
            
            transcript_text = " ".join(transcript_parts)
            
            # Enhanced post-processing for better quality
            if transcript_text:
                # Remove common artifacts and repetitions
                transcript_text = transcript_text.replace(" uh ", " ")
                transcript_text = transcript_text.replace(" um ", " ")
                transcript_text = transcript_text.replace(" ah ", " ")
                transcript_text = transcript_text.replace("  ", " ")
                
                # Fix common repetition patterns
                words = transcript_text.split()
                cleaned_words = []
                prev_word = ""
                
                for word in words:
                    # Skip if same word repeated more than 2 times
                    if word.lower() != prev_word.lower() or len(cleaned_words) < 2 or cleaned_words[-1].lower() != word.lower():
                        cleaned_words.append(word)
                    prev_word = word
                
                transcript_text = " ".join(cleaned_words).strip()
            
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
    
    # ----------------- Timestamping and Transcript Logging -----------------
    def enable_minute_timestamps(self, *, sink: str = 'memory', file_path: Optional[str] = None) -> None:
        """
        Opt-in to minute marks + combined transcript logging.
        Args:
            sink: 'memory' (default), 'file', or 'both'
            file_path: where to append a rolling transcript if sink includes 'file'
        """
        self._timestamping_enabled = True
        self._transcript_sink = sink
        self._transcript_file_path = file_path

    def get_combined_transcript(self, as_text: bool = True):
        """
        Returns all events (minute marks + text) across Mic/System on one timeline.
        If as_text=True, returns a pretty string; else returns a list of dicts:
        {'t': float_seconds, 'ts': 'MM:SS', 'kind': 'mark'|'final_mark'|'text', 'source': str?, 'text': str?}
        """
        with self._transcript_lock:
            events = sorted(self._transcript_events, key=lambda e: e['t'])
        if not as_text:
            return events

        lines = []
        for e in events:
            if e['kind'] == 'mark':
                lines.append(f"[{e['ts']}] --- minute mark ---")
            elif e['kind'] == 'final_mark':
                lines.append(f"[{e['ts']}] --- end of recording ---")
            else:
                src = e.get('source', '')
                txt = (e.get('text') or '').replace('\n', ' ').strip()
                lines.append(f"[{e['ts']}][{src}] {txt}")
        return "\n".join(lines)

    # ----------------- Internals -----------------
    def _fmt_ts(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    def _append_transcript_event(self, *, kind: str, text: Optional[str] = None,
                                source: Optional[str] = None, t: Optional[float] = None) -> None:
        if not self._timestamping_enabled or self._recording_start_perf is None:
            return
        import time
        if t is None:
            t = time.perf_counter() - self._recording_start_perf
        event = {'t': float(t), 'ts': self._fmt_ts(float(t)), 'kind': kind}
        if text is not None:
            event['text'] = text
        if source is not None:
            event['source'] = source

        with self._transcript_lock:
            self._transcript_events.append(event)
            if self._transcript_sink in ('file', 'both') and self._transcript_file_path:
                self._append_event_to_file(event)

    def _append_event_to_file(self, event: dict) -> None:
        try:
            if not self._transcript_file_path:
                return
            os.makedirs(os.path.dirname(self._transcript_file_path), exist_ok=True)
            line = ""
            if event['kind'] == 'mark':
                line = f"[{event['ts']}] --- minute mark ---\n"
            elif event['kind'] == 'final_mark':
                line = f"[{event['ts']}] --- end of recording ---\n"
            else:
                src = event.get('source', '')
                txt = (event.get('text') or '').replace('\n', ' ').strip()
                line = f"[{event['ts']}][{src}] {txt}\n"
            with open(self._transcript_file_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"Transcript file write error: {e}")

    def _minute_mark_loop(self) -> None:
        """Emits [MM:00] marks exactly every 60s from recording start, and a final mark when recording stops."""
        import time
        # initial 00:00
        self._append_transcript_event(kind='mark', t=0.0)
        next_mark = 60.0
        # Sleep in small steps to be resilient to scheduling jitter
        while self.is_recording:
            now = time.perf_counter() - (self._recording_start_perf or time.perf_counter())
            # if we haven't reached the next minute, wait a bit
            if now + 0.01 < next_mark:
                time.sleep(min(0.5, max(0.0, next_mark - now)))
                continue
            # fire the mark at the exact scheduled boundary
            self._append_transcript_event(kind='mark', t=next_mark)
            next_mark += 60.0
        # after stop, add a final timestamp where the session ended
        # end_t = max(0.0, time.perf_counter() - (self._recording_start_perf or time.perf_counter()))
        # self._append_transcript_event(kind='final_mark', t=end_t)
        end_t = max(0.0, time.perf_counter() - (self._recording_start_perf or time.perf_counter()))
        self._schedule_final_mark(end_t)

    def set_end_mark_policy(self, policy: str = "align_to_last_event", window_sec: float = 2.0):
        """
        policy:
        - "immediate": (current behavior) mark at stop time instantly.
        - "align_to_last_event": wait a short window, then place end mark AFTER the last event seen.
        - "drain_then_mark": wait until queues empty and ASR jobs drop to zero (or timeout), then mark.
        """
        assert policy in ("immediate", "align_to_last_event", "drain_then_mark")
        self._end_mark_policy = policy
        self._post_stop_window_sec = float(window_sec)

    def _schedule_final_mark(self, stop_t: float):
        if self._end_mark_policy == "immediate":
            self._append_transcript_event(kind='final_mark', t=stop_t)
            self._final_mark_emitted = True
            return
        if self._finalizer_thread and self._finalizer_thread.is_alive():
            return
        self._finalizer_thread = threading.Thread(
            target=self._finalize_after_drain, args=(stop_t,), daemon=True
        )
        self._finalizer_thread.start()

    def _finalize_after_drain(self, stop_t: float):
        import time
        deadline = time.perf_counter() + self._post_stop_window_sec

        if self._end_mark_policy == "drain_then_mark":
            # wait until mic/system queues empty & jobs finish, or timeout
            while time.perf_counter() < deadline:
                if self.mic_queue.empty() and self.system_queue.empty() and self._active_transcribe_jobs == 0:
                    break
                time.sleep(0.05)
        else:
            # align_to_last_event: passive wait window only
            time.sleep(max(0.0, self._post_stop_window_sec))

        # place end mark after the last event we have
        with self._transcript_lock:
            last_t = stop_t
            if self._transcript_events:
                last_t = max(last_t, max(e['t'] for e in self._transcript_events if e['kind'] != 'final_mark'))
        self._append_transcript_event(kind='final_mark', t=last_t + 1e-3)  # epsilon so it prints last
        self._final_mark_emitted = True

    # ----------------- Recording File Management (Old Logic) -----------------
    def set_user_id(self, user_id):
        """Set user ID for user-specific recordings."""
        self.user_id = user_id
        # Create user-specific directory
        if user_id:
            user_dir = os.path.join(self.recordings_dir, f"user_{user_id}")
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
    
    def _start_recording_file(self):
        """Initialize recording file for this session."""
        try:
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use user-specific directory if user is set
            if self.user_id:
                user_dir = os.path.join(self.recordings_dir, f"user_{self.user_id}")
                self.recording_filename = os.path.join(user_dir, f"recording_{timestamp}.wav")
            else:
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
    
    def get_saved_recordings(self, user_id=None):
        """Get list of saved recording files, optionally filtered by user."""
        try:
            # If user_id is provided, look in user-specific directory
            if user_id and self.user_id == user_id:
                user_dir = os.path.join(self.recordings_dir, f"user_{user_id}")
                search_dir = user_dir if os.path.exists(user_dir) else self.recordings_dir
            else:
                search_dir = self.recordings_dir
            
            if not os.path.exists(search_dir):
                return []
            
            recordings = []
            for filename in os.listdir(search_dir):
                if filename.endswith('.wav'):
                    filepath = os.path.join(search_dir, filename)
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
    
    def delete_recording(self, filename, user_id=None):
        """Delete a saved recording file, optionally from user-specific directory."""
        try:
            # If user_id is provided, check user-specific directory first
            if user_id and self.user_id == user_id:
                user_dir = os.path.join(self.recordings_dir, f"user_{user_id}")
                user_filepath = os.path.join(user_dir, filename)
                if os.path.exists(user_filepath):
                    os.remove(user_filepath)
                    print(f"🗑️ Deleted user recording: {filename}")
                    return True
            
            # Fallback to main directory
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

        # --- ADDITIVE: stop AAI streaming v3 if running ---
        if self._aai_streaming_enabled and self._aai_v3_client:
            self._aai_v3_stop.set()
            try:
                # tell client to finish; terminate=True ends the session server-side
                self._aai_v3_client.disconnect(terminate=True)
            except Exception:
                pass
            if self._aai_v3_stream_thread and self._aai_v3_stream_thread.is_alive():
                self._aai_v3_stream_thread.join(timeout=3.0)
            self._aai_v3_client = None

        
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

    def _aai_v3_connect(self):
        """
        Open one continuous AAI Universal Streaming (v3) session and spawn a
        background thread that drains our PCM queue into .stream(...).
        """
        api_key = get_assemblyai_api_key()
        if not api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY missing")

        # Build client
        client = StreamingClient(
            StreamingClientOptions(
                api_key=api_key,
                api_host="streaming.assemblyai.com",  # Universal Streaming host
                enable_diarization=True,  # <— request diarization
                word_timestamps=True      # <— ensure words come with speaker tags
            )
        )
        self._aai_v3_client = client
        self._aai_v3_stop.clear()

        # ------------------ Event handlers ------------------
        def on_begin(_: StreamingClient, event: BeginEvent):
            print(f"AAI session started: {event.id}")
            # reset mapping per session
            with self._transcript_lock:
                self._aai_speaker_map.clear()
                self._aai_next_speaker_idx = 1

        def on_turn(sc: StreamingClient, event: TurnEvent):
            text = event.transcript or ""
            if not text:
                return

            is_final = bool(event.end_of_turn)
            is_partial = not is_final
            if is_partial and not self._aai_include_partials:
                return

            # --- DEDUP: request formatting, but DON'T emit the unformatted final ---
            if is_final and not event.turn_is_formatted:
                try:
                    sc.set_params(StreamingSessionParameters(format_turns=True))
                except Exception as e:
                    print(f"AAI set_params error: {e}")
                return  # wait for the formatted version of the same turn

            # From here: partials (if you opted in) or formatted finals

            # Prefer per-word speakers; if absent, fall back to a single speaker label.
            words = getattr(event, "words", None) or []

            # Helper to map raw speaker IDs to "Speaker N"
            def map_speaker(sp_raw: str) -> str:
                key = str(sp_raw)
                label = self._aai_speaker_map.get(key)
                if not label:
                    label = f"Speaker {self._aai_next_speaker_idx}"
                    self._aai_speaker_map[key] = label
                    self._aai_next_speaker_idx += 1
                return label

            # If we have speaker-tagged words, split by contiguous speaker runs
            has_speaker_words = any(
                getattr(w, "speaker", None) is not None or getattr(w, "speaker_label", None) is not None
                for w in words
            )

            emitted_any = False
            if words and has_speaker_words:
                seg_speaker = None
                seg_tokens = []

                def flush_segment():
                    nonlocal seg_speaker, seg_tokens, emitted_any
                    if not seg_tokens:
                        return
                    # Simple token join (words are already punctuated in formatted turns)
                    seg_text = " ".join(t for t in seg_tokens).strip()
                    if not seg_text:
                        seg_tokens = []
                        return
                    label = map_speaker(seg_speaker if seg_speaker is not None else "default")
                    display_text = f"{label}: {seg_text}" if self._aai_prefix_speaker_in_text else seg_text
                    source_label = "Mic" if self._aai_streaming_source == "mic" else "System"
                    self.transcript_callback(display_text, source_label)
                    self._append_transcript_event(kind='text', text=display_text, source=source_label)
                    emitted_any = True
                    seg_tokens = []

                for w in words:
                    sp = getattr(w, "speaker", None) or getattr(w, "speaker_label", None)
                    token = getattr(w, "text", None) or getattr(w, "punctuated", None) or getattr(w, "word", None) or ""
                    # start a new segment when speaker changes
                    if seg_speaker is None:
                        seg_speaker = sp
                    elif sp != seg_speaker:
                        flush_segment()
                        seg_speaker = sp
                    if token:
                        seg_tokens.append(token)

                flush_segment()

            # Fallback: no per-word speakers → try event-level speaker, else single line
            if not emitted_any:
                sp_raw = getattr(event, "speaker", None) or getattr(event, "speaker_label", None) or "default"
                label = map_speaker(sp_raw)
                display_text = f"{label}: {text}" if self._aai_prefix_speaker_in_text else text
                source_label = "Mic" if self._aai_streaming_source == "mic" else "System"
                self.transcript_callback(display_text, source_label)
                self._append_transcript_event(kind='text', text=display_text, source=source_label)


        def on_terminated(_: StreamingClient, event: TerminationEvent):
            print(f"AAI session terminated: processed {event.audio_duration_seconds} sec")

        def on_error(_: StreamingClient, error: StreamingError):
            print(f"AAI streaming error: {error}")

        # Register handlers
        client.on(StreamingEvents.Begin, on_begin)
        client.on(StreamingEvents.Turn, on_turn)
        client.on(StreamingEvents.Termination, on_terminated)
        client.on(StreamingEvents.Error, on_error)

        # Connect the session (enable diarization + formatted turns)
        client.connect(
            StreamingParameters(
                sample_rate=RATE,
                format_turns=True,     # request speaker-formatted turns
                enable_diarization=True,
                words_timestamps=True
            )
        )

        # Start the streaming thread that drains our PCM queue
        def _stream_runner():
            try:
                # generator that yields PCM bytes
                def gen():
                    while self.is_recording and not self._aai_v3_stop.is_set():
                        try:
                            chunk = self._aai_stream_queue.get(timeout=0.2)
                            if chunk:
                                yield chunk
                        except queue.Empty:
                            # allow loop to check stop flag
                            continue

                client.stream(gen())
            except Exception as e:
                print(f"AAI stream runner error: {e}")
            finally:
                try:
                    client.disconnect(terminate=True)
                except Exception:
                    pass

        self._aai_v3_stream_thread = threading.Thread(target=_stream_runner, daemon=True)
        self._aai_v3_stream_thread.start()


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":

    def on_transcript(text, source):
        global FULL_TRANSCRIPT
        FULL_TRANSCRIPT.append((source, text))
        print(f"\n{'='*60}")
        print(f"🎯 PERFECT [{source}] TRANSCRIPT: {text}")
        print('='*60 + "\n")
    
    print("\n" + "="*60)
    print("🚀 PERFECT AI AUDIO PROCESSOR TEST")
    print("="*60)
    
    mode = input("Select mode (1=Mic, 2=System, 3=Both): ").strip()
    mode_map = {"1": "mic", "2": "system", "3": "both"}
    selected_mode = mode_map.get(mode, "system")
    
    print(f"\n🎯 Testing PERFECT {selected_mode.upper()} mode for 30 seconds...")
    print("="*60 + "\n")
    
    try:
        processor = PerfectAIAudioProcessor(on_transcript, audio_source=selected_mode, transcription_engine="assemblyai")
        processor.enable_assemblyai_streaming(diarization=True, source_preference="system", include_partials=False, prefix_speaker_in_text=True)
        processor.enable_minute_timestamps(sink='memory')
        processor.set_end_mark_policy(policy="align_to_last_event", window_sec=2.0)
        if processor.start_recording():
            time.sleep(30)
            processor.stop_recording()
        else:
            print("❌ Failed to start perfect recording!")
    except Exception as e:
        print(f"❌ Perfect AI error: {e}")
    
    print("\n🎯 FULL TRANSCRIPT LOG:")
    print("-"*60)
    for src, txt in FULL_TRANSCRIPT:
        print(f"[{src}] {txt}")

    print("\n" + "="*60)
    print("🎯 PERFECT AI TEST COMPLETE!")
    print("="*60)