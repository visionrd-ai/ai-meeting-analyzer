import os, json, time, random
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
GROK_MODEL = "grok-4-fast-reasoning"

# ============================
# STRICT-JSON SYSTEM PROMPTS
# ============================

SYSTEM_PROMPT_JSON = """
You are the Meeting Analyst AI for ONE specific meeting.
Use ONLY the two sources below. Never use outside knowledge.

Return a STRICT JSON object with ONLY these keys:
{
  "answer": string,                       // max 6 sentences, concise, actionable
  "citations": [                          // cite exact evidence lines you used
    {"minute": int, "speaker": string, "quote": string}
  ],
  "needs_older_context": boolean,         // true if not found in these two sources
  "suggested_shift_minutes": integer,     // choose from: 0, 5, 10, 15, 20, 25, 30 (use 0 normally here)
  "missing_reason": string,               // <= 20 words; e.g. "not in this meeting’s sources"
  "follow_up": string                     // optional; one clarifying question if truly needed
}

Citation rules:
- Ground EVERY concrete claim with at least one citation.
- Use speaker labels:
  • "[Transcript]" when citing the transcript (put the correct minute or line number)
  • "[Final Analysis]" when citing the analysis
- If nothing relevant is found in these two sources, set:
  "answer": "Not in the provided meeting context.",
  "needs_older_context": true,
  "suggested_shift_minutes": 0,
  and briefly set "missing_reason".

FULL TRANSCRIPT:
{transcript_text_injected}

FINAL ANALYSIS:
{final_analysis_injected}
"""

SYSTEM_PROMPT_JSON_WITH_RAG = """
You are the Meeting Analyst AI for ONE specific meeting.
Prefer the meeting’s Full Transcript and Final Analysis, but you may consult the RAG Evidence provided for older/related context from the same user/tenant. Never use outside knowledge.

Return a STRICT JSON object with ONLY these keys:
{
  "answer": string,                       // max 6 sentences, concise, actionable
  "citations": [                          // cite exact evidence lines you used
    {"minute": int, "speaker": string, "quote": string}
  ],
  "needs_older_context": boolean,         // true only if even RAG is insufficient
  "suggested_shift_minutes": integer,     // choose from: 0, 5, 10, 15, 20, 25, 30
  "missing_reason": string,               // <= 20 words
  "follow_up": string                     // optional; one clarifying question if truly needed
}

Citation rules:
- Prefer Transcript and Final Analysis.
- If you use RAG, set speaker to "[RAG]" and minute to 0, with a short verbatim quote. Include session/time in the quote if present.
- Ground EVERY claim with at least one citation. If nothing relevant exists across all sources, set:
  "answer": "Not in the provided meeting context.",
  "needs_older_context": true,
  "suggested_shift_minutes": 10.

FULL TRANSCRIPT:
{transcript_text_injected}

FINAL ANALYSIS:
{final_analysis_injected}

RAG EVIDENCE (most relevant first; short excerpts with metadata):
{rag_evidence_injected}
"""

# ============================
# UTILS
# ============================

def _to_analysis_text(latest_analysis: Any) -> str:
    if isinstance(latest_analysis, dict):
        parts = []
        for key, value in latest_analysis.items():
            if isinstance(value, list):
                parts.append(f"{key.replace('_',' ').title()}:\n" + "\n".join(f"- {item}" for item in value))
            else:
                parts.append(f"{key.replace('_',' ').title()}: {value}")
        return "\n\n".join(parts)
    return (latest_analysis or "").strip()

def _safe_str(s: Optional[str]) -> str:
    return (s or "").strip()

def _safe_json_parse(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        return None

def _fmt_ts_local(ts: Optional[float]) -> str:
    if ts is None: return "—"
    try:
        from zoneinfo import ZoneInfo
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts), ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        import datetime as _dt
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")

# ============================
# RAG
# ============================

from rag import RAGManager  # assumes your RAGManager is importable

class MeetingChatGrok:
    """
    Final meeting chat with STRICT-JSON responses and RAG fallback:
      1) Ask using ONLY Full Transcript + Final Analysis.
      2) If model returns "Not in the provided meeting context." or needs_older_context: true → query RAG and retry.
      3) Returns JSON-like dict similar to Live chat.
    """

    def __init__(
        self,
        api_key_grok: str,
        latest_transcript: str,
        latest_analysis: Any,
        *,
        system_prompt_json: str = SYSTEM_PROMPT_JSON,
        system_prompt_json_with_rag: str = SYSTEM_PROMPT_JSON_WITH_RAG,
        rag_manager: RAGManager = RAGManager(),
        rag_user_id: Optional[str] = None,
        rag_session_hint: Optional[str] = None,
    ):
        self.client = OpenAI(api_key=api_key_grok, base_url="https://api.x.ai/v1")

        # Sources
        self.full_transcript: str = _safe_str(latest_transcript)
        self.latest_analysis_text: str = _to_analysis_text(latest_analysis)

        # Prompts
        self._base_system_prompt_template = system_prompt_json
        self._rag_system_prompt_template  = system_prompt_json_with_rag
        self.system_prompt = self._build_system_prompt()

        # RAG
        self.rag_manager = rag_manager or RAGManager()
        self.rag_user_id = rag_user_id or "default_user"
        self.rag_session_hint = rag_session_hint

        # Chat state
        self.chat_history: List[Dict[str, str]] = []
        self.start_time = datetime.now()

    # ----- prompt builders -----
    def _build_system_prompt(self) -> str:
        sp = self._base_system_prompt_template
        sp = sp.replace("{transcript_text_injected}", self.full_transcript if self.full_transcript else "[NO TRANSCRIPT PROVIDED]")
        sp = sp.replace("{final_analysis_injected}", self.latest_analysis_text if self.latest_analysis_text else "[NO FINAL ANALYSIS PROVIDED]")
        return sp

    def _build_system_prompt_with_rag(self, rag_block: str) -> str:
        sp = self._rag_system_prompt_template
        sp = sp.replace("{transcript_text_injected}", self.full_transcript if self.full_transcript else "[NO TRANSCRIPT PROVIDED]")
        sp = sp.replace("{final_analysis_injected}", self.latest_analysis_text if self.latest_analysis_text else "[NO FINAL ANALYSIS PROVIDED]")
        sp = sp.replace("{rag_evidence_injected}", rag_block if rag_block.strip() else "[NO RAG EVIDENCE]")
        return sp

    # ----- model call -----
    def _call_once(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1200) -> str:
        resp = self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    # ----- RAG helpers -----
    def _rag_search(self, user_message: str, *, k: int = 6) -> Dict[str, Any]:
        try:
            return self.rag_manager.retrieve_query_results_smart(
                user_message=user_message,
                user_id=self.rag_user_id,
                k=5, k_initial=32,
                time_window_sec=None,
                keyword_boost=1.0,
                mmr_lambda=0.6
            )
        except Exception as e:
            return {"error": str(e)}

    def _rag_evidence_block(self, rag_res: Dict[str, Any]) -> str:
        if not rag_res or "error" in rag_res:
            return "[NO RAG EVIDENCE]"
        docs = (rag_res.get("documents", [[]]) or [[]])[0] or []
        metas = (rag_res.get("metadatas", [[]]) or [[]])[0] or []
        if not docs:
            return "[NO RAG EVIDENCE]"
        lines = []
        for i, doc in enumerate(docs[:10]):
            md = metas[i] if i < len(metas) else {}
            ses = md.get("session_id", "—")
            when = _fmt_ts_local(md.get("start_ts"))
            snip = (doc or "").replace("\n", " ").strip()
            if len(snip) > 240: snip = snip[:239] + "…"
            lines.append(f"- {snip}  (session={ses}, when={when})")
        return "\n".join(lines) if lines else "[NO RAG EVIDENCE]"

    # ----- public API (JSON-like, live-chat style) -----
    def ask(
        self,
        user_message: str,
        *,
        max_attempts: int = 1,
        api_retry_on_error: int = 3,
        api_retry_sleep_range: Tuple[float, float] = (0.6, 1.2),
        enable_rag_fallback: bool = True,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "answer": str,
            "citations": list[dict],
            "needs_older_context": bool,
            "attempts": int,
            "used_rag": bool,
            "raw": str,
            "json": dict | None
          }
        """
        attempts = 0
        used_rag = False
        result_json = None
        raw_text = ""
        answer = ""
        needs_older = False

        # First pass: Transcript + Final Analysis only
        messages = [{"role": "system", "content": self.system_prompt}] + self.chat_history + [{"role": "user", "content": user_message}]
        while attempts < max_attempts:
            attempts += 1
            tries, last_err = 0, None
            while tries < api_retry_on_error:
                try:
                    raw_text = self._call_once(messages, temperature=0.2, max_tokens=1200)
                    break
                except Exception as e:
                    last_err = e
                    tries += 1
                    time.sleep(random.uniform(*api_retry_sleep_range))
            if tries == api_retry_on_error and last_err is not None:
                raw_text = '{"answer":"Temporary error contacting model.","citations":[],"needs_older_context":false,"suggested_shift_minutes":0}'

            result_json = _safe_json_parse(raw_text)
            if result_json:
                answer = (result_json.get("answer") or "").strip()
                needs_older = bool(result_json.get("needs_older_context", False))
            else:
                # Model deviated; treat as plain text answer (no fallback trigger unless explicitly says not found)
                answer = raw_text.strip()
                needs_older = answer.lower().startswith("not in the provided meeting context")
            break  # one attempt is enough for this pass

        # Decide RAG fallback
        trigger_fallback = enable_rag_fallback and (
            needs_older or (answer.strip().lower().startswith("not in the provided meeting context"))
        )

        if trigger_fallback:
            rag_res = self._rag_search(user_message, k=6)
            rag_block = self._rag_evidence_block(rag_res)
            if rag_block and rag_block != "[NO RAG EVIDENCE]":
                used_rag = True
                rag_prompt = self._build_system_prompt_with_rag(rag_block)
                messages_rag = [{"role": "system", "content": rag_prompt}] + self.chat_history + [{"role":"user","content": user_message}]
                try:
                    raw_text = self._call_once(messages_rag, temperature=0.25, max_tokens=1200)
                except Exception:
                    raw_text = '{"answer":"Not in the provided meeting context.","citations":[],"needs_older_context":true,"suggested_shift_minutes":10}'
                result_json = _safe_json_parse(raw_text) or {
                    "answer": raw_text, "citations": [], "needs_older_context": False, "suggested_shift_minutes": 0
                }
                answer = (result_json.get("answer") or "").strip()
                needs_older = bool(result_json.get("needs_older_context", False))

        # Persist the final turn (text only for history)
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": answer})

        return {
            "answer": answer,
            "citations": (result_json.get("citations", []) if isinstance(result_json, dict) else []),
            "needs_older_context": needs_older,
            "attempts": attempts,
            "used_rag": used_rag,
            "raw": raw_text,
            "json": result_json,
        }

    # Back-compat: return just the answer text
    def send_chat(self, user_message: str, **kwargs) -> str:
        out = self.ask(user_message, **kwargs)
        return out.get("answer", "")

    def chat(self, user_message: str, **kwargs) -> str:
        return self.send_chat(user_message, **kwargs)

    def reset_chat(self, transcript: str = "", analysis: Any = "", user_id: str = "", system_prompt_json: str = SYSTEM_PROMPT_JSON):
        self.chat_history = []
        self.full_transcript = _safe_str(transcript)
        self.latest_analysis_text = _to_analysis_text(analysis)
        self._base_system_prompt_template = system_prompt_json
        self.system_prompt = self._build_system_prompt()
        self.rag_user_id = user_id or self.rag_user_id

  
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

    def read_text_or_default(p: str, default: str = "") -> str:
        if p and Path(p).exists():
            return Path(p).read_text(encoding="utf-8")
        return default

    parser = argparse.ArgumentParser(description="Meeting Chat (Grok) – interactive CLI")
    parser.add_argument("--title", type=str, default="Meeting Chat (Grok)", help="Title for header")
    args = parser.parse_args()

    api_key = os.getenv("XAI_API_KEY", "your_xai_api_key_here")
    files_dir = Path("temp")
    latest_transcript = read_text_or_default(files_dir / "latest_transcript.txt", default="")
    latest_analysis = read_text_or_default(files_dir / "latest_analysis.txt", default="")

    # Instantiate your chat class (uses your existing __init__)
    chat = MeetingChatGrok(api_key_grok=api_key,
                           latest_transcript=latest_transcript,
                           latest_analysis=latest_analysis)

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
            a = chat.send_chat(q)
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
