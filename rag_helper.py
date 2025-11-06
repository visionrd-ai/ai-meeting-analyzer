# --- Build segments from a flat transcript that uses DOUBLE SPACES as line breaks ---
import re
import datetime as _dt
from typing import List, Dict, Tuple, Optional

# Detect optional inline tags like [System] / [Mic] if you ever include them later
_TAG_RE = re.compile(r"^\s*\[(System|Mic)\]\s*", re.IGNORECASE)

def _strip_tag_and_source(sentence: str, default_source: str = "System") -> Tuple[str, str]:
    m = _TAG_RE.match(sentence)
    if m:
        src = m.group(1).title()
        return sentence[m.end():].strip(), src
    return sentence.strip(), default_source

def _split_sentences_resilient(text: str) -> List[str]:
    """
    Robust sentence split:
      - split on [.?!…] + space/end
      - merge ultra-short fragments
      - shatter very long runs by ; : , or hard word cap
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    # primary split
    parts = re.split(r"(?<=[\.\?\!…])\s+(?=[^\s])", text)
    out: List[str] = []

    def _shatter_long(s: str, max_words: int = 40) -> List[str]:
        # try ; and : first
        tmp = [c.strip() for c in re.split(r"\s*[;:]\s*", s) if c.strip()] or [s]
        shards: List[str] = []
        for piece in tmp:
            words = piece.split()
            if len(words) <= max_words:
                shards.append(piece)
                continue
            # try commas to group
            buf, grouped = [], []
            for chunk in [c.strip() for c in piece.split(",") if c.strip()]:
                if len((" ".join(buf + [chunk])).split()) > max_words:
                    if buf:
                        grouped.append(" ".join(buf))
                        buf = []
                buf.append(chunk)
            if buf:
                grouped.append(" ".join(buf))
            # hard cut if still long
            for g in grouped:
                w = g.split()
                if len(w) > max_words:
                    for i in range(0, len(w), max_words):
                        shards.append(" ".join(w[i:i+max_words]))
                else:
                    shards.append(g)
        return [x for x in shards if x]

    carry = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p.split()) < 3:
            carry = (carry + " " + p).strip()
            continue
        if carry:
            p = (carry + " " + p).strip()
            carry = ""
        out.extend(_shatter_long(p, max_words=40))
    if carry:
        out.append(carry)
    return out

def build_segments_from_double_space_transcript(
    full_text: str,
    *,
    start_iso: Optional[str] = None,
    default_source: str = "System",
    seconds_per_word: float = 0.32,
    gap_seconds: float = 0.9,
    treat_double_space_as_break: bool = True,
) -> List[Dict]:
    """
    Convert a single flat transcript (where original newlines became DOUBLE SPACES)
    into [{text, source, timestamp}] segments suitable for create_embeddings_from_segments.

    Strategy:
      - Split by DOUBLE (or 2+)-spaces as soft blocks (if enabled).
      - Within each block, do sentence splitting with robustness.
      - Merge tiny bits; break very long runs.
      - Infer [System]/[Mic] if present at the start of a sentence, else use default_source.
      - Assign synthetic timestamps: t += words*seconds_per_word + gap_seconds.
    """
    if not full_text or not full_text.strip():
        return []

    # Normalize: collapse 3+ spaces to exactly 2 so the break detector fires
    text = re.sub(r"\s{3,}", "  ", full_text.strip())

    blocks = [text]  # fallback: whole text as one block
    if treat_double_space_as_break and "  " in text:
        blocks = [b.strip() for b in re.split(r"\s{2,}", text) if b.strip()]

    # Seed time
    t = _dt.datetime.fromisoformat(start_iso) if start_iso else _dt.datetime.now()

    segs: List[Dict] = []
    last_source = default_source

    for block in blocks:
        sentences = _split_sentences_resilient(block) or [block]
        # Merge ultra-short sentences into neighbors to avoid “It.”, “So.” as isolated segments
        merged: List[str] = []
        buf = ""
        for s in sentences:
            if len(s.split()) < 4:
                buf = (buf + " " + s).strip()
                continue
            if buf:
                merged.append((buf + " " + s).strip())
                buf = ""
            else:
                merged.append(s.strip())
        if buf:
            # append any leftover short tail
            if merged:
                merged[-1] = (merged[-1] + " " + buf).strip()
            else:
                merged.append(buf)

        for sent in merged:
            clean_text, src = _strip_tag_and_source(sent, default_source=last_source or default_source)
            last_source = src
            if not clean_text:
                continue
            segs.append({
                "text": clean_text,
                "source": src,
                "timestamp": t.isoformat(timespec="microseconds"),
            })
            w = max(1, len(clean_text.split()))
            t += _dt.timedelta(seconds=(w * seconds_per_word + gap_seconds))

    return segs
