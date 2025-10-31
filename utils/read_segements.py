import os
import re
from typing import Dict, Optional

_TS      = re.compile(r'^\[(\d{2}):(\d{2})\]')
_CONTENT = re.compile(r'^\[(\d{2}):(\d{2})\]\[(Mic|System)\]\s*(.*)$')

def read_minute_segments_snapshot(
    path: str,
    include_empty_minutes: bool = True,
    max_bytes: Optional[int] = None,   # e.g., 2_000_000 to tail ~last 2MB for long sessions
) -> Dict[str, str]:
    """
    Non-blocking, read-only snapshot of the transcript file, segmented by minute.
    - Opens the file once, reads a fixed number of bytes (no loops, no sleeps).
    - Never acquires locks; won't interfere with the writer.
    - Drops an unterminated trailing line (if the writer is mid-append).
    - Combines Mic/System lines into paragraphs per minute.

    Returns { "0": "...", "1": "...", ... }.
    """
    try:
        st = os.stat(path)
        size = st.st_size
    except FileNotFoundError:
        return {}
    except OSError:
        # If file is being swapped/rotated at the exact moment—fail fast, don't block.
        return {}

    # Tail mode if max_bytes is set (avoid huge reads)
    start = 0
    if max_bytes is not None and size > max_bytes:
        start = size - max_bytes

    try:
        with open(path, "rb") as f:
            if start:
                f.seek(start, os.SEEK_SET)
                # Skip a potentially partial first line when tailing
                _ = f.readline()
            data = f.read()
    except (FileNotFoundError, PermissionError, OSError):
        # Fail fast; reader should never block the writer
        return {}

    text = data.decode("utf-8", "replace")
    # If last line is incomplete (no newline), drop it to avoid partial parses
    if text and not text.endswith("\n"):
        text = text[:text.rfind("\n")+1] if ("\n" in text) else ""

    per_minute = {}  # minute(int) -> {'Mic': [str], 'System': [str]}
    last_minute_seen = -1

    for line in text.splitlines():
        m_ts = _TS.match(line)
        if not m_ts:
            continue
        mm, ss = int(m_ts.group(1)), int(m_ts.group(2))
        last_minute_seen = max(last_minute_seen, mm)

        m_ct = _CONTENT.match(line)
        if not m_ct:
            # It's a minute mark or end-of-recording marker; contributes only to coverage.
            continue

        src = m_ct.group(3)                 # "Mic" | "System"
        txt = (m_ct.group(4) or "").strip()
        if not txt:
            continue

        bucket = per_minute.setdefault(mm, {"Mic": [], "System": []})
        bucket[src].append(txt)

    if last_minute_seen < 0:
        return {}

    # Build output paragraphs
    out: Dict[str, str] = {}
    for m in range(0, last_minute_seen + 1):
        bucket = per_minute.get(m, {"Mic": [], "System": []})
        parts = []

        if bucket["System"]:
            sys_text = re.sub(r"\s+", " ", " ".join(bucket["System"])).strip()
            parts.append(f"[System] {sys_text}")

        if bucket["Mic"]:
            mic_text = re.sub(r"\s+", " ", " ".join(bucket["Mic"])).strip()
            parts.append(f"[Mic] {mic_text}")

        paragraph = "\n\n".join(parts) if parts else ""
        if paragraph or include_empty_minutes:
            out[str(m)] = paragraph

    return out


if __name__ == "__main__":
    file_path = r"E:\VisionRD\ai-meeting-analyzer\recordings\user_1\11_227fde2a-e6ac-48a8-956d-94c4991d727f.txt"
    segments = read_minute_segments_snapshot(file_path,include_empty_minutes=True ,max_bytes=100_000_000)

    for minute, text in segments.items():
        print(f"Minute {minute}:\n{text}\n{'-'*40}\n")
