#!/usr/bin/env python3
# diarize_wav.py — vendor-agnostic diarization (ECAPA + AHC + VAD + smoothing)

import argparse, os, json, sys, math, warnings
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional

import numpy as np
import soundfile as sf

from dotenv import load_dotenv
load_dotenv()

# ----- optional imports with helpful errors -----
def _need(pkg, hint):
    raise RuntimeError(f"Missing dependency '{pkg}'. Install it: {hint}")

try:
    import librosa
except Exception:
    librosa = None

try:
    import webrtcvad
except Exception:
    webrtcvad = None

try:
    import torchaudio  # must happen before importing speechbrain
    if not hasattr(torchaudio, "list_audio_backends"):
        # Some newer torchaudio builds removed this; older speechbrain expects it.
        def _ta_list_audio_backends():
            return []  # we don't rely on torchaudio I/O anyway
        torchaudio.list_audio_backends = _ta_list_audio_backends
        print("⚠️ Patched torchaudio.list_audio_backends = [] (compat shim)")
except Exception as _e:
    # We can still run without torchaudio if speechbrain doesn't require its I/O
    print(f"⚠️ torchaudio import issue (continuing): {_e}")

try:
    import torch
    from speechbrain.inference.classifiers import EncoderClassifier
except Exception as e:
    torch = None
    EncoderClassifier = None
    print(f"Error importing torch or EncoderClassifier: {e}")

try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
except Exception:
    AgglomerativeClustering = None
    silhouette_score = None

try:
    from scipy.signal import resample_poly
except Exception:
    resample_poly = None


# ---------------- data model ----------------
@dataclass
class Segment:
    start: float
    end: float
    speaker: str
    conf: float = 1.0


# ---------------- I/O + resample ----------------
def load_wav_mono_16k(path: str) -> Tuple[np.ndarray, int]:
    """Load audio -> mono float32, resample to 16 kHz."""
    try:
        audio, sr = sf.read(path, always_2d=True)
        audio = audio.mean(axis=1)
    except TypeError:
        audio, sr = sf.read(path)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
    audio = audio.astype(np.float32, copy=False)
    if sr != 16000:
        if librosa is not None:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        elif resample_poly is not None:
            from fractions import Fraction
            frac = Fraction(16000, sr).limit_denominator()
            audio = resample_poly(audio, frac.numerator, frac.denominator).astype(np.float32)
        else:
            _need("librosa/scipy", "pip install librosa or scipy")
        sr = 16000
    # light peak guard
    mx = float(np.max(np.abs(audio)) or 1.0)
    if mx > 1.0:
        audio = audio / mx
    return audio, 16000


# ---------------- VAD (WebRTC with hangover) ----------------
def vad_segments(audio: np.ndarray, sr: int = 16000, mode: int = 2,
                 frame_ms: int = 30, pad_ms: int = 300) -> List[Tuple[float, float]]:
    """
    Return [(start, end), ...] speech regions using WebRTC VAD.
    mode: 0-3 (3 most aggressive)
    pad_ms: hangover/hang-before to glue short gaps.
    """
    if webrtcvad is None:
        # fallback: whole audio as one region
        dur = len(audio)/sr
        return [(0.0, dur)]
    vad = webrtcvad.Vad(mode)
    frame_len = int(sr * frame_ms / 1000)
    step = frame_len
    # int16 PCM
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16).tobytes()

    speech_flags = []
    for i in range(0, len(audio)-frame_len+1, step):
        frame = pcm[2*i:2*(i+frame_len)]
        speech_flags.append(vad.is_speech(frame, sr))
    # hangover smoothing
    pad_frames = int(pad_ms / frame_ms)
    smooth = [False]*len(speech_flags)
    for i, is_sp in enumerate(speech_flags):
        if not is_sp:
            continue
        start = max(0, i - pad_frames)
        end   = min(len(speech_flags), i + pad_frames + 1)
        for j in range(start, end):
            smooth[j] = True

    # to regions
    regions = []
    in_region = False
    st = 0
    for idx, flag in enumerate(smooth):
        if flag and not in_region:
            in_region = True
            st = idx * frame_ms / 1000.0
        if not flag and in_region:
            en = idx * frame_ms / 1000.0
            if en - st >= 0.1:
                regions.append((st, en))
            in_region = False
    if in_region:
        en = len(smooth) * frame_ms / 1000.0
        if en - st >= 0.1:
            regions.append((st, en))
    # merge very short gaps
    merged = []
    for s, e in regions:
        if not merged:
            merged.append([s, e])
        else:
            if s - merged[-1][0] < 0:  # guard
                s = merged[-1][1]
            if s - merged[-1][1] <= 0.2:
                merged[-1][1] = e
            else:
                merged.append([s, e])
    return [(float(s), float(e)) for s, e in merged]


# ---------------- ECAPA embeddings ----------------
_ECAPA = None
def get_ecapa(device: str = "cpu"):
    global _ECAPA
    if _ECAPA is None:
        if EncoderClassifier is None or torch is None:
            _need("speechbrain/torch", "pip install speechbrain torch torchvision torchaudio")
        _ECAPA = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": device}
        )
    return _ECAPA

def embed_windows(windows: List[np.ndarray], sr: int = 16000, device: str = "cpu") -> np.ndarray:
    ecapa = get_ecapa(device)
    with torch.no_grad():
        # Pad to same length in a batch for speed
        max_len = max(len(w) for w in windows)
        batch = []
        for w in windows:
            if len(w) < max_len:
                pad = np.zeros((max_len - len(w),), dtype=np.float32)
                w2 = np.concatenate([w, pad], axis=0)
            else:
                w2 = w
            batch.append(w2)
        wavs = torch.tensor(np.stack(batch)).to(device)
        wavs = wavs.unsqueeze(1)  # [B, 1, T]
        embs = _ECAPA.encode_batch(wavs).squeeze(0)  # [B, D] or [1,B,D] depending on version
        if embs.ndim == 3:
            embs = embs.squeeze(0)
        embs = torch.nn.functional.normalize(embs, p=2, dim=1)
        return embs.cpu().numpy().astype(np.float32)


# ---------------- clustering helpers ----------------
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a)+1e-8); b = b / (np.linalg.norm(b)+1e-8)
    return float(np.dot(a, b))

def pairwise_cosine(E: np.ndarray) -> np.ndarray:
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-8)
    return E @ E.T  # [N,N]

def choose_k_by_silhouette(E: np.ndarray, kmin: int, kmax: int) -> int:
    if silhouette_score is None:
        return max(2, kmin)
    sims = pairwise_cosine(E)
    # convert to distances for sklearn silhouette with metric='precomputed'
    D = 1.0 - sims
    best_k, best_score = None, -1.0
    for k in range(max(2, kmin), max(3, kmax+1)):
        try:
            # Agglomerative with precomputed distance
            try:
                ac = AgglomerativeClustering(n_clusters=k, affinity='precomputed', linkage='average')
            except TypeError:
                ac = AgglomerativeClustering(n_clusters=k, metric='precomputed', linkage='average')
            labels = ac.fit_predict(D)
            s = silhouette_score(1.0 - D, labels, metric="cosine")
            if s > best_score:
                best_k, best_score = k, s
        except Exception:
            continue
    if best_k is None:
        return max(2, kmin)
    return best_k

def cluster_ahc(E: np.ndarray, k: int) -> np.ndarray:
    # prefer precomputed cosine distances (average linkage)
    sims = pairwise_cosine(E)
    D = 1.0 - sims
    try:
        ac = AgglomerativeClustering(n_clusters=k, affinity='precomputed', linkage='average')
    except TypeError:
        ac = AgglomerativeClustering(n_clusters=k, metric='precomputed', linkage='average')
    labels = ac.fit_predict(D)
    return labels


# ---------------- timeline utils ----------------
def windows_over_regions(audio: np.ndarray, sr: int, regions: List[Tuple[float, float]],
                         win_s: float = 1.5, hop_s: float = 0.75) -> Tuple[List[Tuple[float,float]], List[np.ndarray]]:
    times, chunks = [], []
    for s0, s1 in regions:
        t = s0
        while t + win_s <= s1:
            a = int(t * sr)
            b = int((t + win_s) * sr)
            chunk = audio[a:b]
            if len(chunk) >= int(0.5 * sr):
                times.append((t, t + win_s))
                chunks.append(chunk)
            t += hop_s
    return times, chunks

def merge_consecutive(labels: np.ndarray, times: List[Tuple[float,float]], prefix="spk_") -> List[Segment]:
    out: List[Segment] = []
    cur_lab, cur_s, cur_e = None, None, None
    for lab, (s0, s1) in zip(labels, times):
        if cur_lab is None:
            cur_lab, cur_s, cur_e = int(lab), s0, s1
            continue
        if int(lab) == cur_lab and abs(s0 - cur_e) < 1e-6:
            cur_e = s1
        else:
            out.append(Segment(cur_s, cur_e, f"{prefix}{cur_lab+1}", 0.9))
            cur_lab, cur_s, cur_e = int(lab), s0, s1
    if cur_lab is not None:
        out.append(Segment(cur_s, cur_e, f"{prefix}{cur_lab+1}", 0.9))
    return out

def repair_min_duration(segments: List[Segment], min_dur: float = 1.0) -> List[Segment]:
    """Merge segments shorter than min_dur into neighbors (greedy)."""
    if not segments:
        return segments
    segs = segments[:]
    i = 0
    while i < len(segs):
        dur = segs[i].end - segs[i].start
        if dur < min_dur:
            # prefer merging to the neighbor that creates the longest contiguous span (or same speaker)
            if i > 0 and (i == len(segs)-1 or (segs[i-1].end - segs[i-1].start) >= (segs[i+1].end - segs[i+1].start)):
                # merge into previous
                if segs[i-1].speaker == segs[i].speaker:
                    segs[i-1].end = segs[i].end
                    del segs[i]
                    continue
                else:
                    # relabel short segment as previous speaker
                    spk = segs[i-1].speaker
                    segs[i].speaker = spk
            else:
                # merge into next
                if i < len(segs)-1 and segs[i+1].speaker == segs[i].speaker:
                    segs[i+1].start = segs[i].start
                    del segs[i]
                    continue
                else:
                    # relabel short segment as next speaker
                    if i < len(segs)-1:
                        spk = segs[i+1].speaker
                        segs[i].speaker = spk
        i += 1
    # final re-merge of identical neighbors
    merged: List[Segment] = []
    for s in segs:
        if merged and merged[-1].speaker == s.speaker and abs(s.start - merged[-1].end) < 1e-6:
            merged[-1].end = s.end
        else:
            merged.append(s)
    return merged


# ---------------- main diarizer (ECAPA + AHC) ----------------
def diarize_ecapa_ahc(audio: np.ndarray, sr: int,
                      min_speakers: Optional[int], max_speakers: Optional[int],
                      debug: bool = False, device: str = "cpu") -> List[Segment]:
    if AgglomerativeClustering is None:
        _need("scikit-learn", "pip install scikit-learn")
    if EncoderClassifier is None or torch is None:
        _need("speechbrain/torch", "pip install speechbrain torch torchvision torchaudio")

    # 1) VAD
    regions = vad_segments(audio, sr=sr, mode=2, frame_ms=30, pad_ms=300)
    if debug:
        dur = len(audio)/sr
        print(f"[VAD] found {len(regions)} regions over {dur:.1f}s")

    # 2) Windows & embeddings
    times, chunks = windows_over_regions(audio, sr, regions, win_s=1.5, hop_s=0.75)
    if len(chunks) < 2:
        # too little speech; assign single speaker
        return [Segment(0.0, len(audio)/sr, "spk_1", 0.8)]
    E = embed_windows(chunks, sr=sr, device=device)  # [N, D]

    # 3) Choose K
    kmin = max(2, min_speakers or 2)
    kmax = max(kmin, max_speakers or min(8, max(3, kmin+3)))
    k = choose_k_by_silhouette(E, kmin, kmax)
    if min_speakers is not None:
        k = max(k, min_speakers)
    if max_speakers is not None:
        k = min(k, max_speakers)
    if debug:
        print(f"[CLUSTER] K* = {k} (search in [{kmin},{kmax}])")

    # 4) Cluster
    labels = cluster_ahc(E, k)  # [N]

    # 5) Build segments + smoothing
    segs = merge_consecutive(labels, times, prefix="spk_")
    segs = repair_min_duration(segs, min_dur=1.0)

    # 6) Clip to audio duration and sanity tidying
    end_all = len(audio)/sr
    for s in segs:
        s.start = max(0.0, float(s.start))
        s.end = min(end_all, float(s.end))
        if s.end < s.start:
            s.end = s.start
    # Remove zero-lengths
    segs = [s for s in segs if (s.end - s.start) >= 1e-3]

    if debug:
        speakers = sorted({s.speaker for s in segs})
        print(f"[OUT] segments={len(segs)} speakers={speakers}")
    return segs


# ---------------- (Optional) pyannote path ----------------
def diarize_pyannote(audio: np.ndarray, sr: int,
                     min_speakers: Optional[int], max_speakers: Optional[int],
                     debug: bool = False) -> List[Segment]:
    """
    Requires: pip install pyannote.audio torch
    And a HF token for pretrained pipeline.
    """
    try:
        import torch
        from pyannote.audio import Pipeline
    except Exception as e:
        _need("pyannote.audio", "pip install pyannote-audio")

    # You must export HF token (or pass here)
    token = os.environ.get("HUGGINGFACE_TOKEN", None)
    if token is None:
        _need("HUGGINGFACE_TOKEN", "export HUGGINGFACE_TOKEN=YOUR_TOKEN (env var)")

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization", use_auth_token=token)

    with torch.no_grad():
        # Build a mono waveform tensor
        waveform = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        diar = pipeline({"waveform": waveform, "sample_rate": sr},
                        min_speakers=min_speakers, max_speakers=max_speakers)

    segs: List[Segment] = []
    for turn, _, speaker in diar.itertracks(yield_label=True):
        segs.append(Segment(float(turn.start), float(turn.end), str(speaker), 0.9))

    # Merge adjacent equal speakers
    segs = sorted(segs, key=lambda s: (s.start, s.end))
    merged: List[Segment] = []
    for s in segs:
        if merged and merged[-1].speaker == s.speaker and abs(s.start - merged[-1].end) < 1e-6:
            merged[-1].end = s.end
        else:
            merged.append(s)
    if debug:
        spks = sorted({s.speaker for s in merged})
        print(f"[pyannote] {len(merged)} segments | speakers={spks}")
    return merged


# ---------------- saving ----------------
def save_json(segments: List[Segment], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in segments], f, indent=2)

def save_rttm(segments: List[Segment], path: str, recording_id: Optional[str]=None) -> None:
    rid = recording_id or os.path.splitext(os.path.basename(path))[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for s in segments:
            dur = max(0.0, s.end - s.start)
            f.write(f"SPEAKER {rid} 1 {s.start:.3f} {dur:.3f} <NA> <NA> {s.speaker} {s.conf:.3f}\n")


# ---------------- CLI ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--strategy", choices=["ecapa_ahc", "pyannote"], default="ecapa_ahc")
    ap.add_argument("--min_speakers", type=int, default=None)
    ap.add_argument("--max_speakers", type=int, default=None)
    ap.add_argument("--device", default="cpu")  # "cuda" if you have it
    ap.add_argument("--out_json", default="out/segments.json")
    ap.add_argument("--out_rttm", default="out/segments.rttm")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    audio, sr = load_wav_mono_16k(args.wav)
    if args.debug:
        print(f"Loaded {args.wav} @ {sr} Hz | duration={len(audio)/sr:.2f}s")

    if args.strategy == "ecapa_ahc":
        segs = diarize_ecapa_ahc(audio, sr, args.min_speakers, args.max_speakers,
                                  debug=args.debug, device=args.device)
    else:
        segs = diarize_pyannote(audio, sr, args.min_speakers, args.max_speakers,
                                 debug=args.debug)

    save_json(segs, args.out_json)
    rid = os.path.splitext(os.path.basename(args.wav))[0]
    save_rttm(segs, args.out_rttm, recording_id=rid)

    if args.debug:
        spk_set = sorted({s.speaker for s in segs})
        print(f"Speakers: {spk_set} | Segments: {len(segs)}")
        for s in segs[:10]:
            print(f"{s.start:7.2f}–{s.end:7.2f}  {s.speaker}")

if __name__ == "__main__":
    main()
