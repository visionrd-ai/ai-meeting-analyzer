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
    latest_transcript = """
[Meeting Title] InspectionAI OCR & Deployment Sync
[Date] 2025-10-27 11:00–11:25 (Asia/Karachi)
[Attendees] Aisha (PM), Talal (AI Lead), Bilal (ML Eng), Zara (DevOps), Hamza (Security), Noor (Data Eng)

[00:00:03] Aisha (PM): Quick status on OCR, deployment, and costs. Decisions today on metrics and security scope.

[00:01:20] Bilal (ML Eng): Current end-to-end OCR accuracy is **91.8%** on the Toyota doc set with PP-OCRv4 rec + HRNet32 det.

[00:02:05] Talal (AI Lead): My local eval shows **92.1%** after canonicalization and stricter table matching. Might be the GriTS config.

[00:03:10] Noor (Data Eng): The table grid extractor still throws “Weights sum to zero” on sparse lines; happens on ~7% of pages.

[00:04:00] Aisha (PM): Let’s pick a single metric stack today and lock it.

[00:05:40] Talal (AI Lead): Proposing: **GriTS (PubTables-1M)** for structure, **TEDS (PubTabNet)** for HTML fidelity, plus text F1 for body text.

[00:06:30] Bilal (ML Eng): Agree on GriTS + TEDS; I’ll align our eval scripts accordingly.

[00:07:50] Zara (DevOps): CI/CD: Staging pipeline is green. I can ship the “eval-on-merge” job once metrics finalize. Tentative by **Nov 2**.

[00:08:10] Talal (AI Lead): I’ll export PP-OCRv4 inference with `rec_image_shape=3,48,320` and push by **Oct 30**.

[00:09:00] Aisha (PM): We also need a GPU cost brief for leadership by **next Friday**.

[00:10:15] Zara (DevOps): Cost logging will include GPU mem/SM util and wall-time per batch; we’ll write partial JSON every 50 docs.

[00:11:10] Noor (Data Eng): I’ll add chunked processing (200 files per batch) and a `gc.collect()` + CUDA cache clear between batches to reduce RAM spikes.

[00:12:15] ⭐ HIGH PRIORITY Hamza (Security): CNICs must be masked in logs; storage for logs = **30 days**; encryption at rest on Azure; restrict SAS tokens to read-only.

[00:13:05] Talal (AI Lead): Acknowledge. We’ll mask CNIC before persisting logs.

[00:14:45] Zara (DevOps): Azure Pipelines for staging by **Nov 2** still stands, but infra freeze might push us to **Nov 1** if we rush.

[00:15:30] Aisha (PM): Prefer **Nov 2**; safer. Let’s not rush.

[00:16:00] Bilal (ML Eng): For the table bug, I’ll add epsilon to weights and switch to morphological line detection fallback. ETA **Oct 31**.

[00:17:20] Noor (Data Eng): I’ll write a regression test with 3 pathological samples.

[00:18:30] ⭐ HIGH PRIORITY Talal (AI Lead): Decision: canonicalization ON for tables; official metrics = GriTS + TEDS + text F1.

[00:19:40] Aisha (PM): Confirmed. That’s the decision.

[00:20:10] Zara (DevOps): Risk: batch tests spike RAM to 22GB; workaround is chunking + periodic JSON flush + CUDA cache clear.

[00:21:00] Bilal (ML Eng): Minor discrepancy: I still see **91.8%** vs Talal’s **92.1%**. We’ll re-run with the same seeds and metric config.

[00:22:10] Aisha (PM): Owners & dates are clear? Summarize actions before we close.

[00:23:00] Talal (AI Lead): Export inference by Oct 30 (me). Table bug fix by Oct 31 (Bilal). Staging CI/CD by Nov 2 (Zara). GPU cost brief by **next Friday** (Zara + Talal). CNIC masking + 30-day log retention (team).

[00:24:15] Hamza (Security): I’ll review the masking and token scopes post-merge.

[00:25:00] Aisha (PM): Thanks all—done.  
  """
    latest_analysis = """
[Section] Overview
The team aligned on a unified evaluation stack (GriTS + TEDS + text F1), locked canonicalization for tables, and outlined deployment, cost, and security steps. Two date clarifications were recorded.

[Section] Decisions
- D1: Use **GriTS + TEDS + text F1** as the official metrics for table/HTML/text evaluation. (Confirms Transcript 00:18:30, 00:19:40)
- D2: **Canonicalization ON** for tables. (Transcript 00:18:30)
- D3: Staging CI/CD delivery target: **Nov 2, 2025** (kept, despite a mention of Nov 1). (Transcript 00:14:45–00:15:30)

[Section] Action Items
- A1: **Export PP-OCRv4 inference** with `rec_image_shape=3,48,320` by **Oct 30, 2025** — Owner: Talal. (Transcript 00:08:10)
- A2: **Fix table grid bug** (“Weights sum to zero”) by adding epsilon + morphological fallback by **Oct 31, 2025** — Owner: Bilal. (Transcript 00:16:00)
- A3: **Staging CI/CD** (eval-on-merge job) by **Nov 2, 2025** — Owner: Zara. (Transcript 00:07:50, 00:14:45–00:15:30)
- A4: **GPU cost brief** by **Nov 7, 2025 (Friday)** — Owners: Zara + Talal. (Clarifies “next Friday” from Transcript 00:09:00)
- A5: **CNIC masking + 30-day log retention + Azure encryption at rest + read-only SAS** — Owner: Hamza to review post-merge. (Transcript 00:12:15, 00:24:15)
- A6: **Re-run accuracy** with identical seeds and metric configs to reconcile **91.8% vs 92.1%** — Owners: Bilal + Talal; no date set. (Transcript 00:21:00)

[Section] Risks
- R1: **RAM spikes during batch evaluations** (up to ~22GB). Mitigation: chunked processing, periodic JSON flush every 50 docs, CUDA cache clear between batches. (Transcript 00:20:10)
- R2: **Metric discrepancy** (91.8 vs 92.1). Plan: controlled re-run; track seeds + configs. (Transcript 00:21:00)

[Section] Security (⭐ HIGH PRIORITY)
- Mask CNICs in logs; retain logs for **30 days**; enforce encryption at rest on Azure; restrict SAS tokens to read-only. (Transcript 00:12:15)
- Post-merge review by Hamza. (Transcript 00:24:15)

[Section] Clarifications & Conflict Resolution
- “Next Friday” in transcript is resolved to **Nov 7, 2025**, based on the meeting date (Oct 27, 2025). This replaces the relative phrasing to avoid ambiguity.
- CI/CD date: **Nov 2, 2025** retained (Transcript 00:15:30), superseding the tentative Nov 1 mention.
- Accuracy: Record both **91.8%** and **92.1%**; pending re-run to converge.

[Section] Timeline (Key Moments)
- 00:05:40–00:07:50: Metric stack proposal and agreement.
- 00:08:10: Inference export commitment (Oct 30).
- 00:12:15: ⭐ HIGH PRIORITY security requirements recorded.
- 00:14:45–00:15:30: CI/CD date discussion; finalize Nov 2.
- 00:16:00–00:17:20: Table bug fix approach + regression tests.
- 00:20:10–00:21:00: RAM spike risk + accuracy discrepancy.
- 00:23:00–00:24:15: Action recap + security review assignment.

[Section] Owners
- PM: Aisha | AI Lead: Talal | ML Eng: Bilal | DevOps: Zara | Security: Hamza | Data Eng: Noor
"""

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
