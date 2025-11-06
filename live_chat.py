import json, time, random
from typing import Dict, List, Tuple, Any, Optional
from openai import OpenAI
from prompts.system.live_chat import LIVE_SYSTEM_PROMPT, LIVE_SYSTEM_PROMPT_WITH_RAG

from dotenv import load_dotenv
load_dotenv()

from rag import RAGManager

GROK_MODEL = "grok-4-fast-reasoning"

def _coerce_minute_keys(segments: Dict[str, str]) -> Dict[int, str]:
    out = {}
    for k, v in segments.items():
        try:
            out[int(k)] = v or ""
        except Exception:
            continue
    return out

def _build_window_text(
    segments: Dict[str, str],
    end_minute: int | None = None,
    window_min: int = 15
) -> Tuple[int, int, str]:
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

def _fmt_ts_local(ts: Optional[float]) -> str:
    if ts is None:
        return "—"
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts), ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")

class LiveMeetingChatGrok:
    """
    Live chat that:
      - injects last N minutes of transcript,
      - expands window on demand,
      - falls back to RAG (old meetings) when the window lacks evidence.
    """

    def __init__(
        self,
        api_key_grok: str,
        live_system_prompt: str = LIVE_SYSTEM_PROMPT,
        rag_system_prompt: str = LIVE_SYSTEM_PROMPT_WITH_RAG,   # NEW
        rag_manager: RAGManager = RAGManager(),
    ):
        self.client = OpenAI(api_key=api_key_grok, base_url="https://api.x.ai/v1")
        self.live_system_template = live_system_prompt
        self.rag_system_template = rag_system_prompt              # NEW
        self.chat_history: List[Dict[str, str]] = []
        self.last_used_window: Tuple[int, int] | None = None
        self.rag_manager = rag_manager

    def reset_chat(self):
        self.chat_history = []
        self.last_used_window = None

    def _call_grok_once(self, messages: List[Dict[str, str]]) -> str:
        resp = self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=2000,
        )
        return (resp.choices[0].message.content or "").strip()

    # ---------- NEW: RAG helpers ----------
    def _rag_search(self, user_message: str, user_id: str, session_id: Optional[str] = None, *, k: int = 6) -> Dict[str, Any]:
        """Query RAG for top-k matches, return raw Chroma-shaped result."""
        try:
            return self.rag_manager.retrieve_query_results_smart(
                user_message=user_message,
                user_id=user_id,
                k=5, k_initial=32,
                time_window_sec=None,
                keyword_boost=1.0,
                mmr_lambda=0.6
            )
        except Exception as e:
            return {"error": str(e)}

    def _rag_evidence_block(self, rag_res: Dict[str, Any]) -> str:
        """Format a compact, human-readable RAG evidence section for the system prompt."""
        if not rag_res or "error" in rag_res:
            return "[NO RAG EVIDENCE]"
        ids = (rag_res.get("ids", [[]]) or [[]])[0] or []
        docs = (rag_res.get("documents", [[]]) or [[]])[0] or []
        metas = (rag_res.get("metadatas", [[]]) or [[]])[0] or []
        if not docs:
            return "[NO RAG EVIDENCE]"
        lines = []
        for i, doc in enumerate(docs[:10]):
            md = metas[i] if i < len(metas) else {}
            src = md.get("source_primary", "Unknown")
            ses = md.get("session_id", "—")
            when = _fmt_ts_local(md.get("start_ts"))
            snippet = (doc or "").replace("\n", " ").strip()
            if len(snippet) > 240:
                snippet = snippet[:239] + "…"
            lines.append(f"- {snippet}  (src={src}, session={ses}, when={when})")
        return "\n".join(lines) if lines else "[NO RAG EVIDENCE]"

    # ---------- main entry ----------
    def ask(
        self,
        user_message: str,
        segments: Dict[str, str],
        user_id: Optional[str] = None,
        *,
        base_window_min: int = 15,
        expand_step_min: int = 5,
        max_attempts: int = 3,
        api_retry_on_error: int = 3,
        api_retry_sleep_range: Tuple[float, float] = (0.6, 1.4),
        enable_rag_fallback: bool = True,                 # NEW
        rag_user_id: Optional[str] = None,                # NEW: whose RAG to search (defaults to same identity as chat)
        rag_session_hint: Optional[str] = None,           # NEW: optionally bias to a session
    ) -> Dict[str, Any]:

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
            self.chat_history += [{"role":"user","content":user_message},{"role":"assistant","content":final["answer"]}]
            return final

        end_m = max(segs_int.keys())
        start_m, cur_end_m, window_text = _build_window_text(segments, end_minute=end_m, window_min=base_window_min)

        attempts = 0
        result_json = None
        raw_text = ""
        answer_text = ""
        needs_older = False

        # ---- Try with live-only window (expanding backwards if needed) ----
        while attempts < max_attempts:
            attempts += 1
            system_prompt = self.live_system_template.replace("{window_transcript_injected}", window_text)
            messages = _messages_with_system(system_prompt, self.chat_history, user_message)

            api_tries, last_err = 0, None
            while api_tries < api_retry_on_error:
                try:
                    raw_text = self._call_grok_once(messages)
                    break
                except Exception as e:
                    last_err = e
                    api_tries += 1
                    time.sleep(random.uniform(*api_retry_sleep_range))
            if api_tries == api_retry_on_error and last_err is not None:
                raw_text = '{"answer":"Temporary error contacting model.","citations":[],"needs_older_context":false,"suggested_shift_minutes":0}'

            result_json = _safe_json_parse(raw_text)
            if not result_json:
                answer_text = raw_text
                needs_older = False
                break

            answer_text = str(result_json.get("answer", "")).strip()
            needs_older = bool(result_json.get("needs_older_context", False))
            shift = int(result_json.get("suggested_shift_minutes", 0) or 0)

            if needs_older and start_m > 0:
                step = shift if shift in (5,10,15,20,25,30) else expand_step_min
                new_start = max(0, start_m - step)
                if new_start == start_m:
                    break
                start_m = new_start
                _, _, window_text = _build_window_text(segments, end_minute=end_m, window_min=(end_m - start_m + 1))
                continue
            break

        used_live_only = bool(result_json and not needs_older)

        # ---- RAG fallback (only if enabled and live window was insufficient) ----
        if enable_rag_fallback and (not result_json or needs_older):
            # Query RAG
            rag_uid = user_id or "alice"  # <-- replace with your runtime user identity
            rag_res = self._rag_search(user_message, rag_uid, session_id="", k=6)
            rag_block = self._rag_evidence_block(rag_res)

            # If nothing in RAG either, keep previous outcome
            if rag_block and rag_block != "[NO RAG EVIDENCE]":
                # Build the RAG-aware prompt
                rag_system = self.rag_system_template \
                    .replace("{window_transcript_injected}", window_text) \
                    .replace("{rag_evidence_injected}", rag_block)

                messages = _messages_with_system(rag_system, self.chat_history, user_message)
                try:
                    raw_text_rag = self._call_grok_once(messages)
                except Exception:
                    raw_text_rag = '{"answer":"Insufficient evidence in current sources.","citations":[],"needs_older_context":true,"suggested_shift_minutes":10}'
                result_json_rag = _safe_json_parse(raw_text_rag) or {
                    "answer": raw_text_rag, "citations": [], "needs_older_context": False, "suggested_shift_minutes": 0
                }
                # Prefer RAG answer now
                result_json = result_json_rag
                answer_text = str(result_json.get("answer", "")).strip()
                needs_older = bool(result_json.get("needs_older_context", False))
                raw_text = raw_text_rag

        # Persist only the final turn
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": answer_text})
        self.last_used_window = (start_m, end_m)

        return {
            "answer": answer_text,
            "citations": (result_json.get("citations", []) if isinstance(result_json, dict) else []),
            "needs_older_context": needs_older,
            "attempts": attempts,
            "used_window": [start_m, end_m],
            "raw": raw_text,
            "json": result_json,
            "used_live_only": used_live_only,
        }


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