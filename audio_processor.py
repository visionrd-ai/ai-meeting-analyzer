# ===================== Custom, Vendor-Agnostic Speaker ID (Additive) =====================
import threading, time
import numpy as np
from typing import Callable, Optional, Dict, List, Any
from datetime import datetime
from audio_processor_perfect_ai import PerfectAIAudioProcessor

def v2_l2_normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v) + 1e-8
    return v / n

def v2_cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = v2_l2_normalize(a)
    b = v2_l2_normalize(b)
    return float(np.dot(a, b))

def v2_naive_speaker_embedding(
    audio: np.ndarray,
    sample_rate: int = 16000,
    frame_ms: float = 25.0,
    hop_ms: float = 10.0,
    n_bands: int = 32,
) -> np.ndarray:
    """Lightweight 'voice' embedding; dependency-free."""
    if audio is None or len(audio) < int(0.1 * sample_rate):
        return np.zeros((n_bands * 2,), dtype=np.float32)

    x = np.asarray(audio, dtype=np.float32).copy()
    # pre-emphasis
    x[1:] = x[1:] - 0.97 * x[:-1]

    frame_len = int(sample_rate * (frame_ms / 1000.0))
    hop_len   = int(sample_rate * (hop_ms   / 1000.0))
    if frame_len <= 0 or hop_len <= 0:
        return np.zeros((n_bands * 2,), dtype=np.float32)

    num_frames = 1 + max(0, (len(x) - frame_len) // hop_len)
    if num_frames <= 1:
        return np.zeros((n_bands * 2,), dtype=np.float32)

    win = np.hamming(frame_len).astype(np.float32)
    n_fft = 1
    while n_fft < frame_len:
        n_fft <<= 1

    spec = np.empty((num_frames, n_fft // 2 + 1), dtype=np.float32)
    for i in range(num_frames):
        start = i * hop_len
        frame = x[start : start + frame_len]
        if len(frame) < frame_len:
            pad = np.zeros((frame_len - len(frame),), dtype=np.float32)
            frame = np.concatenate([frame, pad])
        frame = frame * win
        mag = np.abs(np.fft.rfft(frame, n=n_fft)).astype(np.float32) + 1e-8
        spec[i] = mag

    # log-energy by simple linear bands
    bins = spec.shape[1]
    band_sizes = [bins // n_bands] * n_bands
    for j in range(bins - sum(band_sizes)):
        band_sizes[j] += 1

    bands, idx = [], 0
    for sz in band_sizes:
        bands.append(np.log(spec[:, idx : idx + sz].sum(axis=1) + 1e-8))
        idx += sz
    bands = np.stack(bands, axis=1)  # (T, n_bands)

    mean = bands.mean(axis=0)
    std  = bands.std(axis=0)
    emb  = np.concatenate([mean, std]).astype(np.float32)
    return v2_l2_normalize(emb)


class PerfectAIAudioProcessorCustomDiarization(PerfectAIAudioProcessor):
    """
    Vendor-agnostic, online diarization layered on your processor.
    - Mic -> 'You'
    - System -> custom clustering (Speaker 1/2/…)
    - No reliance on API diarization
    - Anti-churn + multi-speaker detection inside a chunk
    - Strictly additive: original on_transcript path is preserved 1:1
    """

    def __init__(
        self,
        on_transcript: Callable[[str, str], None],
        audio_source: str = "mic",
        transcription_engine: str = "faster_whisper",
        *,
        enable_identification: bool = True,
        similarity_threshold: float = 0.70,        # accept match above this
        new_speaker_trigger_sim: float = 0.55,     # spawn new if best_sim below this
        low_sim_streak_trigger: int = 2,           # consecutive low sims to trigger new spk
        multi_spread_trigger: float = 0.35,        # spread (1 - cosine) across sub-embs to assume multi
        keep_same_boost: float = 0.07,             # bias to avoid ping-pong
        lock_after_new_sec: float = 1.2,           # short lock after a new speaker to stabilize
        max_remote_speakers: int = 8,              # cap
        expected_remote_speakers: Optional[int] = None,  # helps early stabilization
        identified_callback: Optional[Callable[[dict], None]] = None,
        local_user_name: str = "You",
        sample_rate_hint: int = 16000,
        debug_identification: bool = False,
        deepgram_init_shim: bool = True,
    ):
        self._user_callback = on_transcript
        self._identified_callback = identified_callback

        # Config
        self._id_enabled = bool(enable_identification)
        self._sim_thresh = float(similarity_threshold)
        self._new_trig   = float(new_speaker_trigger_sim)
        self._low_streak_trig = int(low_sim_streak_trigger)
        self._spread_trig = float(multi_spread_trigger)
        self._keep_same  = float(keep_same_boost)
        self._lock_after_new = float(lock_after_new_sec)
        self._max_remote = int(max_remote_speakers)
        self._expected_remote = expected_remote_speakers
        self._local_user_name = str(local_user_name)
        self._sr_hint = int(sample_rate_hint)
        self._id_debug = bool(debug_identification)

        # State
        self._lock = threading.Lock()
        self._segments: List[dict] = []
        self._speaker_map: Dict[str, str] = {"local": self._local_user_name}
        self._remote_centroids: Dict[str, np.ndarray] = {}      # spk_n -> centroid
        self._remote_counts: Dict[str, int] = {}
        self._remote_last_ts: Dict[str, float] = {}
        self._remote_counter = 0
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._last_remote_id: Optional[str] = None
        self._last_remote_time: float = 0.0
        self._low_sim_streak: int = 0

        # Shim Deepgram ctor crash in your base class
        requested_engine = transcription_engine
        safe_engine = "faster_whisper" if (deepgram_init_shim and requested_engine == "deepgram") else requested_engine

        super().__init__(
            on_transcript=self._wrapped_on_transcript,
            audio_source=audio_source,
            transcription_engine=safe_engine,
        )
        if requested_engine == "deepgram" and deepgram_init_shim:
            self.transcription_engine = "deepgram"

    # ---------- Public additive API ----------
    def set_speaker_name(self, speaker_id: str, display_name: str) -> None:
        with self._lock:
            self._speaker_map[str(speaker_id)] = str(display_name)

    def enroll_remote_speaker(self, speaker_id: str, ref_audio: np.ndarray, sample_rate: int = 16000) -> None:
        if not self._id_enabled or ref_audio is None or len(ref_audio) == 0:
            return
        emb = v2_naive_speaker_embedding(ref_audio, sample_rate)
        with self._lock:
            self._remote_centroids[str(speaker_id)] = emb
            self._remote_counts[str(speaker_id)] = 0
            self._remote_last_ts[str(speaker_id)] = 0.0
            self._speaker_map.setdefault(str(speaker_id), f"Speaker {speaker_id.split('_')[-1]}")

    def get_identified_segments(self) -> List[dict]:
        with self._lock:
            return list(self._segments)

    def get_speaker_map(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._speaker_map)

    # ---------- Internal wiring ----------
    def _wrapped_on_transcript(self, text: str, source_label: str) -> None:
        # 1) preserve original behavior
        try:
            self._user_callback(text, source_label)
        except Exception:
            pass

        if not self._id_enabled:
            return

        try:
            tid = threading.get_ident()
            pen = self._pending.pop(tid, None) or {}
            emb = pen.get("emb")
            sub_embs: List[np.ndarray] = pen.get("sub_embs") or []

            if source_label.lower() == "mic":
                spk_id, ui, conf = "local", self._speaker_map.get("local", self._local_user_name), 1.0
            else:
                spk_id, ui, conf = self._assign_remote_speaker(emb, sub_embs)

            seg = {
                "text": (text or "").strip(),
                "source_label": source_label,
                "speaker_id": spk_id,
                "speaker_ui": ui,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "confidence": float(conf),
            }
            with self._lock:
                self._segments.append(seg)

            if self._identified_callback:
                try:
                    self._identified_callback(seg)
                except Exception:
                    pass
        except Exception:
            pass

    def _best_match(self, emb: Optional[np.ndarray]):
        if emb is None or len(emb) == 0:
            return None, -1.0
        with self._lock:
            if not self._remote_centroids:
                return None, -1.0
            best_id = max(self._remote_centroids, key=lambda sid: v2_cosine(emb, self._remote_centroids[sid]))
            best_sim = v2_cosine(emb, self._remote_centroids[best_id])
            return best_id, float(best_sim)

    def _spread_of_sub_embs(self, sub_embs: List[np.ndarray]) -> float:
        """Return max(1 - cosine) across sub-embedding pairs; > threshold => likely multi-speaker."""
        if not sub_embs or len(sub_embs) < 2:
            return 0.0
        m = 0.0
        for i in range(len(sub_embs)):
            for j in range(i + 1, len(sub_embs)):
                a, b = sub_embs[i], sub_embs[j]
                if a is None or b is None or len(a) == 0 or len(b) == 0:
                    continue
                d = 1.0 - v2_cosine(a, b)
                if d > m:
                    m = d
        return float(m)

    def _assign_remote_speaker(self, emb: Optional[np.ndarray], sub_embs: List[np.ndarray]):
        now = time.monotonic()
        best_id, best_sim = self._best_match(emb)
        spread = self._spread_of_sub_embs(sub_embs)

        if self._id_debug:
            print(f"🧠 V2: best_id={best_id} sim={best_sim:.2f} spread={spread:.2f} "
                  f"last={self._last_remote_id} low_streak={self._low_sim_streak}")

        # lock window after creating a new speaker to avoid immediate flip
        if self._last_remote_id and (now - self._last_remote_time) < self._lock_after_new:
            if self._id_debug:
                print(f"🧷 V2: lock → sticking to {self._last_remote_id}")
            return self._commit_remote(self._last_remote_id, emb, conf=max(best_sim, 0.6), when=now)

        # maintain low-similarity streak counter
        if best_sim >= self._sim_thresh:
            self._low_sim_streak = 0
        else:
            self._low_sim_streak += 1

        # accept stable match (with keep-same bias)
        if best_id == self._last_remote_id and best_sim >= max(0.0, self._sim_thresh - self._keep_same):
            return self._commit_remote(best_id, emb, conf=best_sim, when=now)

        if best_id is not None and best_sim >= self._sim_thresh:
            return self._commit_remote(best_id, emb, conf=best_sim, when=now)

        # Decide if we should spawn a new speaker:
        spawn_cond = (
            (best_sim < self._new_trig) or
            (self._low_sim_streak >= self._low_streak_trig) or
            (spread >= self._spread_trig)
        )

        if spawn_cond:
            with self._lock:
                if self._expected_remote is not None and len(self._remote_centroids) < self._expected_remote:
                    new_id = self._new_remote_locked()
                    self._remote_centroids[new_id] = emb if emb is not None else np.zeros((64,), dtype=np.float32)
                    self._remote_counts[new_id] = 1
                    self._remote_last_ts[new_id] = now
                    ui = self._speaker_map.get(new_id, self._pretty_label_for(new_id))
                    if self._id_debug:
                        print(f"🌱 V2: spawn (meet expected / condition) → {new_id} ({ui})")
                    self._last_remote_id, self._last_remote_time = new_id, now
                    self._low_sim_streak = 0
                    return new_id, ui, 0.52

                if len(self._remote_centroids) < self._max_remote:
                    new_id = self._new_remote_locked()
                    self._remote_centroids[new_id] = emb if emb is not None else np.zeros((64,), dtype=np.float32)
                    self._remote_counts[new_id] = 1
                    self._remote_last_ts[new_id] = now
                    ui = self._speaker_map.get(new_id, self._pretty_label_for(new_id))
                    if self._id_debug:
                        print(f"🌱 V2: spawn new → {new_id} ({ui}) (sim={best_sim:.2f}, spread={spread:.2f})")
                    self._last_remote_id, self._last_remote_time = new_id, now
                    self._low_sim_streak = 0
                    return new_id, ui, 0.48

        # fallback: closest or seed spk_1
        with self._lock:
            fallback_id = best_id if best_id is not None else "spk_1"
            if fallback_id not in self._remote_centroids:
                self._remote_centroids[fallback_id] = np.zeros((64,), dtype=np.float32)
                self._remote_counts[fallback_id] = 0
                self._remote_last_ts[fallback_id] = 0.0
            ui = self._speaker_map.get(fallback_id, self._pretty_label_for(fallback_id))
        if self._id_debug:
            print(f"↩️ V2: fallback → {fallback_id} ({ui})")
        self._last_remote_id, self._last_remote_time = fallback_id, now
        return fallback_id, ui, max(0.20, best_sim)

    def _commit_remote(self, spk_id: str, emb: Optional[np.ndarray], conf: float, when: float):
        with self._lock:
            if emb is not None and spk_id in self._remote_centroids:
                self._remote_centroids[spk_id] = v2_l2_normalize(0.9 * self._remote_centroids[spk_id] + 0.1 * emb)
            self._remote_counts[spk_id] = self._remote_counts.get(spk_id, 0) + 1
            self._remote_last_ts[spk_id] = when
            ui = self._speaker_map.get(spk_id, self._pretty_label_for(spk_id))
        if self._id_debug:
            print(f"✅ V2: commit → {spk_id} ({ui}) conf={conf:.2f}")
        self._last_remote_id, self._last_remote_time = spk_id, when
        return spk_id, ui, float(conf)

    def _pretty_label_for(self, speaker_id: str) -> str:
        try:
            n = int(speaker_id.split("_")[-1])
            return f"Speaker {n}"
        except Exception:
            return speaker_id

    def _new_remote_locked(self) -> str:
        self._remote_counter += 1
        new_id = f"spk_{self._remote_counter}"
        self._speaker_map.setdefault(new_id, f"Speaker {self._remote_counter}")
        return new_id

    # ---- capture emb + sub-embs before deferring to base logic
    def _perfect_transcribe_buffer(self, buffer: np.ndarray, source_label: str):
        emb, sub_embs = None, []
        if self._id_enabled and isinstance(buffer, np.ndarray) and buffer.size > 0:
            try:
                emb = v2_naive_speaker_embedding(buffer, self._sr_hint)
                # make 3 sub-embeddings across the chunk to detect spread
                sr = self._sr_hint
                n = len(buffer)
                # split into 3 equal windows (>=0.5s if possible)
                thirds = [ (0, n//3), (n//3, 2*n//3), (2*n//3, n) ]
                for a,b in thirds:
                    if b - a >= int(0.5 * sr):
                        sub_embs.append(v2_naive_speaker_embedding(buffer[a:b], sr))
            except Exception:
                emb, sub_embs = None, []

        try:
            tid = threading.get_ident()
            entry = self._pending.get(tid, {})
            entry["emb"] = emb
            entry["sub_embs"] = sub_embs
            entry["source"] = source_label
            self._pending[tid] = entry
        except Exception:
            pass

        return super()._perfect_transcribe_buffer(buffer, source_label)