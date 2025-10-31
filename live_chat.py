import json, time, random
from typing import Dict, List, Tuple, Any
from openai import OpenAI
from prompts.system.live_chat import LIVE_SYSTEM_PROMPT

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env file


GROK_MODEL = "grok-4-fast-reasoning"  # keep your existing model id

def _coerce_minute_keys(segments: Dict[str, str]) -> Dict[int, str]:
    out = {}
    for k, v in segments.items():
        try:
            out[int(k)] = v or ""
        except Exception:
            # ignore bad keys
            continue
    return out

def _build_window_text(
    segments: Dict[str, str],
    end_minute: int | None = None,
    window_min: int = 15
) -> Tuple[int, int, str]:
    """
    Returns (start_minute, end_minute, window_text) where both ends are inclusive.
    Picks the latest minute as end if not provided. Clamps to 0..max_minute.
    """
    segs = _coerce_minute_keys(segments)
    if not segs:
        return 0, 0, "[NO TRANSCRIPT PROVIDED]"
    if end_minute is None:
        end_minute = max(segs.keys())
    max_m = max(segs.keys())
    end_minute = min(end_minute, max_m)
    start_minute = max(0, end_minute - (window_min - 1))
    parts = []
    for m in range(start_minute, end_minute + 1):
        if m in segs:
            parts.append(f"[Minute {m}]\n{segs[m].strip()}\n")
    window_text = "\n".join(parts).strip() if parts else "[NO TRANSCRIPT IN WINDOW]"
    return start_minute, end_minute, window_text

def _messages_with_system(system_prompt: str, history: List[Dict[str, str]], user_message: str):
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    return msgs

def _safe_json_parse(s: str) -> Dict[str, Any] | None:
    try:
        return json.loads(s)
    except Exception:
        return None

def render_references(citations, *, quote_max=160):
    """Return a formatted 'References' block from list[dict|str]."""
    if not citations:
        return ""
    lines, seen = [], set()

    for c in citations:
        # Allow plain strings too
        if isinstance(c, str):
            s = c.strip()
            if s and ("str", s.lower()) not in seen:
                seen.add(("str", s.lower()))
                lines.append(f"• {s}")
            continue

        if not isinstance(c, dict):
            continue

        minute = c.get("minute")
        speaker = (c.get("speaker") or "").strip()
        quote = (c.get("quote") or "").replace("\n", " ").strip()

        if quote_max and len(quote) > quote_max:
            quote = quote[: quote_max - 1] + "…"

        key = (minute, speaker.lower(), quote.lower())
        if key in seen:
            continue
        seen.add(key)

        if minute is None:
            lines.append(f"• {speaker} \"{quote}\"".strip())
        else:
            lines.append(f"• [Minute {minute}] {speaker} \"{quote}\"".strip())

    # Sort by minute (lines without minute go last)
    import re
    def sort_key(line):
        m = re.search(r"\[Minute (\d+)\]", line)
        return int(m.group(1)) if m else 10**9

    lines.sort(key=sort_key)
    return "\n\nReferences:\n" + "\n".join(lines)

class LiveMeetingChatGrok:
    """
    Lightweight, CPU-only live chat:
      - Injects last 15 minutes of transcript into system prompt
      - Maintains chat history
      - Retries on API failure (max_retries)
      - Expands context window in 5-min steps when model signals older context needed
    """

    def __init__(self, api_key_grok: str, live_system_prompt: str = LIVE_SYSTEM_PROMPT):
        self.client = OpenAI(api_key=api_key_grok, base_url="https://api.x.ai/v1")
        self.live_system_template = live_system_prompt
        self.chat_history: List[Dict[str, str]] = []  # user/assistant only
        self.last_used_window: Tuple[int, int] | None = None

    def reset_chat(self):
        self.chat_history = []
        self.last_used_window = None

    def _call_grok_once(self, messages: List[Dict[str, str]]) -> str:
        # Single API attempt (no context expansion). Caller handles retries/backoff.
        resp = self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            temperature=0.2,      # tighter for concrete answers
            max_tokens=2000,       # live answers should be concise
        )
        return (resp.choices[0].message.content or "").strip()

    def ask(
        self,
        user_message: str,
        segments: Dict[str, str],
        *,
        base_window_min: int = 15,
        expand_step_min: int = 5,
        max_attempts: int = 3,
        api_retry_on_error: int = 3,
        api_retry_sleep_range: Tuple[float, float] = (0.6, 1.4),
    ) -> Dict[str, Any]:
        """
        Returns a dict:
          {
            "answer": str,
            "citations": [...],
            "needs_older_context": bool,
            "attempts": int,
            "used_window": [start_min, end_min],
            "raw": str,                    # raw model text (for debugging)
            "json": dict | None            # parsed json if any
          }
        """
        # Determine the initial end-minute: latest segment available
        segs_int = _coerce_minute_keys(segments)
        if not segs_int:
            final = {
                "answer": "No transcript available yet.",
                "citations": [],
                "needs_older_context": False,
                "attempts": 1,
                "used_window": [0, 0],
                "raw": "",
                "json": None,
            }
            # store turn
            self.chat_history.append({"role": "user", "content": user_message})
            self.chat_history.append({"role": "assistant", "content": final["answer"]})
            return final

        end_m = max(segs_int.keys())
        start_m, cur_end_m, window_text = _build_window_text(segments, end_minute=end_m, window_min=base_window_min)

        attempts = 0
        result_json = None
        raw_text = ""
        answer_text = ""
        needs_older = False

        while attempts < max_attempts:
            attempts += 1

            system_prompt = self.live_system_template.replace("{window_transcript_injected}", window_text)
            messages = _messages_with_system(system_prompt, self.chat_history, user_message)

            # transient API errors retry
            api_tries = 0
            last_err = None
            while api_tries < api_retry_on_error:
                try:
                    raw_text = self._call_grok_once(messages)
                    break
                except Exception as e:
                    last_err = e
                    api_tries += 1
                    time.sleep(random.uniform(*api_retry_sleep_range))
            if api_tries == api_retry_on_error and last_err is not None:
                # hard fail for this attempt — if we still have attempts left, loop; else return error text
                raw_text = f'{{"answer":"Temporary error contacting model.","citations":[],"needs_older_context":false,"suggested_shift_minutes":0}}'

            # Expect strict JSON per prompt; still be defensive
            result_json = _safe_json_parse(raw_text)
            if not result_json:
                # model deviated; coerce minimal result
                answer_text = raw_text
                needs_older = False
                break

            # Extract control signals
            answer_text = str(result_json.get("answer", "")).strip()
            needs_older = bool(result_json.get("needs_older_context", False))
            shift = int(result_json.get("suggested_shift_minutes", 0) or 0)

            # If the model says we need older context, expand window backwards
            if needs_older and start_m > 0:
                step = shift if shift in (5, 10, 15, 20, 25, 30) else expand_step_min
                new_start = max(0, start_m - step)
                if new_start == start_m:
                    # can't go further back
                    break
                start_m = new_start
                # rebuild window using the SAME end_m (latest minute), but a larger span
                _, _, window_text = _build_window_text(segments, end_minute=end_m, window_min=(end_m - start_m + 1))
                continue

            # Otherwise we’re done
            break

        # Persist only the final turn in chat history (clean)
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": answer_text})
        self.last_used_window = (start_m, end_m)

        return {
            "answer": answer_text,
            "citations": (result_json.get("citations", []) if result_json else []),
            "needs_older_context": needs_older,
            "attempts": attempts,
            "used_window": [start_m, end_m],
            "raw": raw_text,
            "json": result_json,
        }


if __name__ == "__main__":
    import os
    import sys
    import argparse
    from pathlib import Path
    import shutil
    import textwrap

    # Optional: nice output if available
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt
        USE_RICH = True
        console = Console()
    except Exception:
        USE_RICH = False

    def read_json_or_default(p: str, default: dict = None) -> dict:
        if p and Path(p).exists():
            with open(p, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    return default or {}
        return default or {}

    parser = argparse.ArgumentParser(description="Meeting Chat (Grok) – interactive CLI")
    parser.add_argument("--title", type=str, default="Meeting Chat (Grok)", help="Title for header")
    args = parser.parse_args()

    api_key = os.getenv("XAI_API_KEY", "your_xai_api_key_here")
    files_dir = Path("temp")
    latest_transcript = read_json_or_default(files_dir / "latest_segments.json", default={})

    # Instantiate your chat class (uses your existing __init__)
    chat = LiveMeetingChatGrok(api_key_grok=api_key)

    # ---- Pretty header ----
    if USE_RICH:
        console.rule(f"[bold]Chat With Grok[/bold]")
        console.print("[dim]Type your question. Commands: /exit, /history[/dim]")
    else:
        term_w = shutil.get_terminal_size().columns
        print("=" * term_w)
        print("Chat With Grok".center(term_w))
        print("=" * term_w)
        print("Type your question. Commands: /exit, /history")

    history = []  # (q, a) tuples for quick review

    # ---- REPL loop ----
    while True:
        try:
            q = Prompt.ask("[bold green]Q[/bold green]") if USE_RICH else input("Q> ")
            q = (q or "").strip()
            if not q:
                continue
            if q.lower() in {"/exit", "/quit"}:
                break
            if q.lower() == "/history":
                if USE_RICH:
                    if not history:
                        console.print("[dim]No history yet.[/dim]")
                    else:
                        for i, (qq, aa) in enumerate(history, 1):
                            console.print(Panel.fit(aa, title=f"#{i} A", subtitle=f"Q: {qq}"))
                else:
                    if not history:
                        print("[No history yet]")
                    else:
                        for i, (qq, aa) in enumerate(history, 1):
                            print(f"\n--- #{i} Q ---\n{qq}\n--- #{i} A ---\n{aa}\n")
                continue

            # ---- Query the model (non-streaming) ----
            a = chat.ask(q, segments=latest_transcript)
            answer = a["answer"]
            answer += render_references(a.get("citations", []))
            a = answer
            history.append((q, a))

            # ---- Pretty print the answer ----
            if USE_RICH:
                console.print(Panel.fit(a, title="Answer", subtitle="Grok", border_style="cyan"))
            else:
                term_w = shutil.get_terminal_size().columns
                print("-" * term_w)
                print("Answer".center(term_w))
                print("-" * term_w)
                wrapped = textwrap.fill(a, width=max(60, min(120, term_w - 4)))
                print(wrapped)
                print("-" * term_w)

        except KeyboardInterrupt:
            # graceful exit on Ctrl+C
            break
        except Exception as e:
            if USE_RICH:
                console.print(f"[red]Error:[/red] {e}")
            else:
                print(f"Error: {e}", file=sys.stderr)

    if USE_RICH:
        console.rule("[dim]Session ended[/dim]")
    else:
        print("\nSession ended.")