import os
from openai import OpenAI
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION - Now configurable via constructor
# ============================================================================

# Default values
DEFAULT_WORDS_PER_ANALYSIS = 200
DEFAULT_WORDS_PER_ROLLING_SUMMARY = 300
MAX_PRIOR_SUMMARY_WORDS = 1000
GROK_MODEL = "grok-4-fast-reasoning"

# ============================================================================

# IT-FOCUSED SYSTEM PROMPT
SYSTEM_PROMPT = """
You are a Meeting Analyst AI for ONE SPECIFIC MEETING. You must answer using ONLY the following two sources:
1) Full Meeting Transcript (verbatim, possibly with timestamps/speaker tags)
2) Final Analysis of Meeting (post-meeting summary)

No other information, assumptions, prior memory, or web knowledge is allowed. If a user asks for anything outside these two sources, say you don't have that context and ask for the relevant passage.

YOUR GOALS
1. ANSWER MEETING QUESTIONS: Decisions, action items, owners, dates, blockers, metrics, rationales, who-said-what, etc.
2. PRODUCE ANALYSES ON DEMAND: Summaries, risks, recommendations, contradictions, timelines, participant lists.
3. STAY WITHIN SCOPE: This chat is scoped to this single meeting. Do not import info from other meetings or general knowledge.

CONTEXT & EVIDENCE RULES
- Retrieve ONLY from the two sources above.
- Every concrete claim MUST include in-text evidence showing exactly where it came from.
- Evidence format (use at least one per key claim):
  • [Transcript 00:12:34 — "short quote…"]  (use timestamp if available; else use line/turn number like [Transcript L123 — "…"])
  • [Final Analysis §Decisions — "short quote…"]  (use section/heading if available)
- If the two sources conflict, prefer explicit corrections in the Final Analysis; otherwise, use the Transcript and clearly flag the discrepancy.
- If the answer cannot be found in these sources, reply exactly: Not in the provided meeting context. Optionally ask for a specific excerpt.

INTERACTION STYLE
- TEXT-ONLY OUTPUT. No JSON, no code blocks unless quoting text from sources.
- Be concise but complete; prioritize clarity and actionability.
- Build iteratively on prior turns in THIS chat; do not repeat unchanged points.
- PRIORITIZE USER-FLAGGED TOPICS: If the user marks something as important (e.g., "focus on this"), analyze it in extra depth and include the sentence: The user flagged this as important, so extra attention is given.
- Dates/Times: Use the exact dates/times stated in the sources. Do not infer missing dates.

WHAT YOU CAN DO
- Summarize the meeting or parts of it.
- Extract decisions, owners, due dates, risks, open questions, follow-ups.
- Build a timeline of key moments.
- Compare Transcript vs Final Analysis to find contradictions or omissions.
- Answer specific queries like "who decided X" or "what's the due date for Y" strictly from the sources.

WHAT YOU MUST NOT DO
- No outside knowledge or speculation.
- No hidden assumptions. If ambiguous, ask a precise clarifying question.
- Do not fabricate participants, metrics, or dates.

RESPONSE STYLE (TEXT ONLY)
- Start with the direct answer or summary in 1-3 sentences.
- Follow with brief supporting details as needed.
- Include evidence inline after the claims using the formats above.
- If listing items (e.g., action items), simple bullet points are fine—each bullet must include evidence tags.
- If nothing relevant exists, reply: Not in the provided meeting context.

FAIL-SAFE BEHAVIOR
- If sources are missing or incomplete, state what's missing and request the exact excerpt needed (timestamp, line, or section).
- If asked about unrelated topics, respond: This chat is restricted to the provided meeting's Transcript and Final Analysis.

BELOW IS THE FULL TRANSCRIPT AND FINAL ANALYSIS FOR YOUR REFERENCE.

FULL TRANSCRIPT:
{transcript_text_injected}

FINAL ANALYSIS:
{final_analysis_injected}
"""



class MeetingChatGrok:
  def __init__(self, api_key_grok: str, latest_transcript: str, latest_analysis: str, system_prompt: str = SYSTEM_PROMPT):
    self.client = OpenAI(
        api_key=api_key_grok,
        base_url="https://api.x.ai/v1"
    )
    
    
    # Transcript accumulation
    self.full_transcript: str = latest_transcript

    # Latest analysis
    self.latest_analysis: str = latest_analysis
    
    self.system_prompt = self._inject_meeting_context(system_prompt)
    
    # Meeting metadata
    self.start_time = datetime.now()
        
    self.chat_history: List[Dict[str, str]] = []  # For future chat features

  def _inject_meeting_context(self, system_prompt: str) -> str:
      transcript = (self.full_transcript or "").strip()
      # Handle both string and dict analysis
      if isinstance(self.latest_analysis, dict):
          # Convert dict to formatted string
          analysis_parts = []
          for key, value in self.latest_analysis.items():
              if isinstance(value, list):
                  analysis_parts.append(f"{key.replace('_', ' ').title()}:\n" + "\n".join(f"- {item}" for item in value))
              else:
                  analysis_parts.append(f"{key.replace('_', ' ').title()}: {value}")
          analysis = "\n\n".join(analysis_parts)
      else:
          analysis = (self.latest_analysis or "").strip()

      template = system_prompt or ""
      injected = template

      # Detect placeholders
      has_transcript_token = "{transcript_text_injected}" in template
      has_analysis_token = "{final_analysis_injected}" in template

      # Replace placeholders if present
      if has_transcript_token:
          injected = injected.replace(
              "{transcript_text_injected}",
              transcript if transcript else "[NO TRANSCRIPT PROVIDED]"
          )
      if has_analysis_token:
          injected = injected.replace(
              "{final_analysis_injected}",
              analysis if analysis else "[NO FINAL ANALYSIS PROVIDED]"
          )

      # If a token was missing, append that section
      append_parts = []
      if not has_transcript_token:
          append_parts.append(
              "\n\nFULL TRANSCRIPT:\n" + (transcript if transcript else "[NO TRANSCRIPT PROVIDED]")
          )
      if not has_analysis_token:
          append_parts.append(
              "\n\nFINAL ANALYSIS:\n" + (analysis if analysis else "[NO FINAL ANALYSIS PROVIDED]")
          )

      if append_parts:
          injected = f"{injected.rstrip()}{''.join(append_parts)}"

      # Persist and return
      return injected

  def send_chat(self, user_message: str) -> str:
    # Ensure a sane history container: a flat list of {"role","content"} dicts
    if not hasattr(self, "chat_history") or self.chat_history is None:
        self.chat_history = []

    # Build the message list to send: [system] + history + new user turn
    messages = []
    if self.system_prompt:  # add once per request; don't store it in chat_history
        messages.append({"role": "system", "content": self.system_prompt})

    # Append prior turns (user/assistant)
    messages.extend(self.chat_history)

    # Append the new user turn
    messages.append({"role": "user", "content": user_message})

    try:
        response = self.client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=2000,  # More tokens for comprehensive
        )
        assistant_text = response.choices[0].message.content or ""
        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": assistant_text})
    except Exception as e:
        print(f"Error communicating with Grok API: {e}")

    # Persist the new turn to history (store only user & assistant roles)


    return assistant_text

  def reset_chat(self, transcript: str = "", analysis: str = "", system_prompt: str = SYSTEM_PROMPT):
    self.chat_history = []
    self.full_transcript = transcript
    self.latest_analysis = analysis
    self.system_prompt = self._inject_meeting_context(system_prompt)

  
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
