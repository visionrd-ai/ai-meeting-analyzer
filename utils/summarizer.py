import os
from openai import OpenAI
from typing import Dict, List, Optional
import json
from datetime import datetime

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
You are an expert IT consultant AI analyzing a live technical meeting. Your role is to:

1. **IDENTIFY POTENTIAL ISSUES**: Proactively spot technical problems, misconfigurations, security risks, or architectural pitfalls based on IT best practices.

2. **PROVIDE ACTIONABLE SUGGESTIONS**: Offer specific, concrete recommendations to resolve or optimize the discussed setup.

3. **ASK CLARIFYING QUESTIONS**: When details are ambiguous or incomplete, raise intelligent questions to help the team make informed decisions.

4. **FOCUS ON IT DOMAINS**:
   - Cloud Services (Azure, AWS, GCP)
   - Infrastructure & Networking
   - Kubernetes & Container Orchestration
   - DevOps & CI/CD
   - Cybersecurity & Compliance
   - Software Architecture
   - Database Design
   - and other if discussed

5. **BE ITERATIVE**: Build on previous context. Avoid repeating the same issues/suggestions.

6. **BE CONCISE**: Keep feedback actionable and to-the-point.

**OUTPUT FORMAT (JSON):**
{
  "technical_analysis": "Brief summary of what's being discussed technically (1-2 sentences)",
  "potential_issues": [
    "Issue 1: Clear description of the problem/risk",
    "Issue 2: Another potential problem"
  ],
  "recommendations": [
    "Recommendation 1: Specific actionable suggestion",
    "Recommendation 2: Another best practice to follow"
  ],
  "clarifying_questions": [
    "Question 1: What additional info is needed?",
    "Question 2: Another clarifying question"
  ],
  "action_items": [
    "Action 1: Task with owner if mentioned",
    "Action 2: Another action item"
  ]
}

**IMPORTANT RULES:**
- Only flag issues that are actually mentioned or implied in the transcript
- Don't repeat issues/suggestions from previous analyses unless new context changes them
- If the discussion is non-technical (greetings, scheduling), simply summarize without forcing technical issues
- Be specific with service names (e.g., "AWS Security Groups" not just "firewall")
- Reference actual best practices and standards where applicable
"""


class MeetingSummarizer:
    """
    Handles IT meeting analysis using Grok API.
    Focuses on proactive technical issue identification and suggestions.
    Now supports configurable analysis intervals and on-demand analysis.
    """
    
    def __init__(self, api_key_grok: str, words_per_analysis: int = DEFAULT_WORDS_PER_ANALYSIS):
        """
        Initialize Grok API client.
        
        Args:
            api_key_grok: xAI API key
            words_per_analysis: Number of words before automatic analysis (0 = manual only)
        """
        self.client = OpenAI(
            api_key=api_key_grok,
            base_url="https://api.x.ai/v1"
        )
        
        # Configurable analysis threshold
        self.words_per_analysis = words_per_analysis
        
        # Transcript accumulation
        self.full_transcript: List[str] = []
        self.word_count = 0
        self.last_analysis_word_count = 0
        
        # Rolling summaries for context
        self.rolling_summaries: List[str] = []
        self.last_summary_word_count = 0
        
        # Track previously identified issues to avoid repetition
        self.previous_issues: List[str] = []
        self.previous_recommendations: List[str] = []
        
        # Latest analysis
        self.latest_analysis: Optional[Dict] = None
        
        # Meeting metadata
        self.start_time = datetime.now()
        
        # Analysis counter
        self.analysis_count = 0
    
    def set_words_per_analysis(self, words: int):
        """Update the automatic analysis threshold."""
        self.words_per_analysis = words
        print(f"Analysis threshold updated to {words} words")
    
    def add_transcript(self, text: str, auto_analyze: bool = True) -> Optional[Dict]:
        """
        Add new transcript and analyze if threshold reached.
        
        Args:
            text: Transcript segment
            auto_analyze: Whether to trigger automatic analysis
            
        Returns:
            Analysis dict if threshold reached, None otherwise
        """
        self.full_transcript.append(text)
        words = text.split()
        self.word_count += len(words)
        
        # Only auto-analyze if enabled and threshold reached
        if auto_analyze and self.words_per_analysis > 0:
            words_since_last_analysis = self.word_count - self.last_analysis_word_count
            
            if words_since_last_analysis >= self.words_per_analysis:
                print(f"🔄 Auto-analyzing at {self.word_count} words...")
                return self._perform_analysis(is_comprehensive=False)  # Incremental for automatic
        
        return None
    
    def force_analysis(self) -> Dict:
        """
        Force an immediate analysis regardless of word count.
        Used for on-demand button clicks.
        
        Returns:
            Analysis dict with comprehensive context
        """
        print(f"🎯 On-demand analysis triggered ({self.word_count} words)")
        return self._perform_analysis(is_comprehensive=True)  # Pass flag for comprehensive analysis
    
    def _perform_analysis(self, is_comprehensive: bool = False) -> Dict:
        """
        Internal method to perform analysis.
        
        Args:
            is_comprehensive: If True, includes ALL transcripts for thorough analysis
        
        Updates last analysis word count and returns results.
        """
        if self.word_count == 0:
            return self._get_error_response("No transcript to analyze yet")
        
        analysis = self._analyze_current_state(is_comprehensive=is_comprehensive)
        self.last_analysis_word_count = self.word_count
        self.analysis_count += 1
        return analysis
    
    def _analyze_current_state(self, is_comprehensive: bool = False) -> Dict:
        """
        Analyze current meeting state with IT focus.
        
        Args:
            is_comprehensive: If True, includes ALL transcripts for manual analysis
        """
        # Create rolling summary if needed
        words_since_last_summary = self.word_count - self.last_summary_word_count
        
        if words_since_last_summary >= DEFAULT_WORDS_PER_ROLLING_SUMMARY:
            print("📝 Creating rolling summary...")
            self._create_rolling_summary()
            self.last_summary_word_count = self.word_count
        
        # Build context (comprehensive or incremental)
        context = self._build_context(is_comprehensive=is_comprehensive)
        
        # Use different system prompt for comprehensive analysis
        system_prompt = SYSTEM_PROMPT
        if is_comprehensive:
            system_prompt = SYSTEM_PROMPT + """

**COMPREHENSIVE ANALYSIS MODE:**
This is a manual/on-demand analysis of ALL accumulated discussion. Provide:
- Detailed technical analysis (4-6 sentences covering all major topics discussed)
- All significant issues identified throughout the conversation
- Comprehensive recommendations for the entire discussion
- Key clarifying questions for any ambiguous topics
- All action items mentioned

Be thorough - this is a strategic checkpoint, not just incremental feedback.
"""
        
        # Call Grok API
        try:
            response = self.client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=0.3,
                max_tokens=2000 if is_comprehensive else 1500,  # More tokens for comprehensive
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            analysis = json.loads(response_text)
            
            # Filter out repeated issues/recommendations
            analysis = self._deduplicate_analysis(analysis)
            
            # Validate response structure
            required_keys = [
                "technical_analysis", 
                "potential_issues", 
                "recommendations", 
                "clarifying_questions",
                "action_items"
            ]
            for key in required_keys:
                if key not in analysis:
                    if key == "technical_analysis":
                        analysis[key] = "No technical discussion detected yet"
                    else:
                        analysis[key] = []
            
            # Store latest analysis
            self.latest_analysis = analysis
            
            # Track issues/recommendations for deduplication
            self.previous_issues.extend(analysis.get("potential_issues", []))
            self.previous_recommendations.extend(analysis.get("recommendations", []))
            
            # Print token usage
            if hasattr(response, 'usage'):
                print(f"💰 Tokens: {response.usage.total_tokens} "
                      f"(in: {response.usage.prompt_tokens}, "
                      f"out: {response.usage.completion_tokens})")
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response: {response_text}")
            return self._get_error_response("Invalid JSON from API")
        
        except Exception as e:
            print(f"Grok API error: {e}")
            import traceback
            traceback.print_exc()
            return self._get_error_response(str(e))
    
    def _deduplicate_analysis(self, analysis: Dict) -> Dict:
        """Remove duplicate issues/recommendations that were mentioned before."""
        def is_duplicate(new_item: str, previous_items: List[str]) -> bool:
            new_lower = new_item.lower()
            for prev in previous_items[-10:]:
                prev_lower = prev.lower()
                if new_lower in prev_lower or prev_lower in new_lower:
                    return True
            return False
        
        if "potential_issues" in analysis:
            analysis["potential_issues"] = [
                issue for issue in analysis["potential_issues"]
                if not is_duplicate(issue, self.previous_issues)
            ]
        
        if "recommendations" in analysis:
            analysis["recommendations"] = [
                rec for rec in analysis["recommendations"]
                if not is_duplicate(rec, self.previous_recommendations)
            ]
        
        return analysis
    
    def _build_context(self, is_comprehensive: bool = False) -> str:
        """
        Build context for Grok analysis.
        
        Args:
            is_comprehensive: If True, includes ALL transcripts (for manual analysis)
                            If False, only includes recent segments (for incremental analysis)
        """
        context_parts = []
        
        duration = (datetime.now() - self.start_time).seconds // 60
        context_parts.append(
            f"MEETING METADATA:\n"
            f"- Duration: {duration} minutes\n"
            f"- Total words: {self.word_count}\n"
            f"- Analysis count: {self.analysis_count}\n"
            f"- Type: IT Technical Discussion\n"
            f"- Analysis mode: {'COMPREHENSIVE (Manual)' if is_comprehensive else 'INCREMENTAL (Automatic)'}\n"
        )
        
        if self.previous_issues:
            context_parts.append(
                f"\n--- PREVIOUSLY IDENTIFIED ISSUES (DON'T REPEAT) ---\n" +
                "\n".join(f"- {issue}" for issue in self.previous_issues[-5:])
            )
        
        if self.rolling_summaries:
            context_parts.append("\n--- PREVIOUS DISCUSSION (SUMMARIES) ---")
            for i, summary in enumerate(self.rolling_summaries):
                context_parts.append(f"\nPhase {i+1}:\n{summary}")
        
        # CRITICAL DIFFERENCE: How much transcript to include
        if is_comprehensive:
            # COMPREHENSIVE: Include ALL transcripts (for manual "Analyze Now")
            full_text = " ".join(self.full_transcript)
            words = full_text.split()
            
            # If too long, use last 800 words to stay within token limits
            if len(words) > 800:
                context_parts.append(f"\n--- FULL DISCUSSION (LAST 800 WORDS OF {len(words)} TOTAL) ---")
                context_parts.append(" ".join(words[-800:]))
            else:
                context_parts.append(f"\n--- COMPLETE DISCUSSION ({len(words)} WORDS) ---")
                context_parts.append(full_text)
            
            print(f"📊 Comprehensive analysis: {len(words)} total words, {min(len(words), 800)} sent to API")
        else:
            # INCREMENTAL: Only recent segments (for automatic periodic analysis)
            recent_segments = self.full_transcript[-3:]
            if recent_segments:
                context_parts.append("\n--- CURRENT DISCUSSION (RECENT) ---")
                context_parts.append(" ".join(recent_segments))
                print(f"📊 Incremental analysis: Last 3 segments")
        
        return "\n".join(context_parts)
    
    def _create_rolling_summary(self):
        """Create compressed summary of recent discussion."""
        recent_text = " ".join(self.full_transcript[-5:])
        
        try:
            response = self.client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize this IT discussion segment concisely in 2-3 sentences. Focus on technical decisions, infrastructure discussed, and any issues raised."
                    },
                    {
                        "role": "user",
                        "content": recent_text
                    }
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            summary = response.choices[0].message.content
            self.rolling_summaries.append(summary)
            
            total_summary_words = sum(len(s.split()) for s in self.rolling_summaries)
            
            while total_summary_words > MAX_PRIOR_SUMMARY_WORDS:
                removed = self.rolling_summaries.pop(0)
                total_summary_words -= len(removed.split())
            
            print(f"✓ Rolling summary created ({len(self.rolling_summaries)} total)")
            
        except Exception as e:
            print(f"⚠️ Rolling summary error: {e}")
    
    def get_final_summary(self) -> Dict:
        """Generate comprehensive final IT analysis of entire meeting."""
        print("🔍 Generating final IT analysis...")
        
        context_parts = [
            f"MEETING COMPLETED - FINAL ANALYSIS\n"
            f"Duration: {(datetime.now() - self.start_time).seconds // 60} minutes\n"
            f"Total words: {self.word_count}\n"
            f"Total analyses performed: {self.analysis_count}\n"
        ]
        
        if self.rolling_summaries:
            context_parts.append("\n--- MEETING PROGRESSION ---")
            for i, summary in enumerate(self.rolling_summaries):
                context_parts.append(f"\nPhase {i+1}:\n{summary}")
        
        full_text = " ".join(self.full_transcript)
        words = full_text.split()
        if len(words) > 1000:
            full_text = " ".join(words[-1000:])
            context_parts.append("\n--- RECENT TRANSCRIPT (LAST 1000 WORDS) ---")
        else:
            context_parts.append("\n--- FULL TRANSCRIPT ---")
        
        context_parts.append(full_text)
        context = "\n".join(context_parts)
        
        try:
            response = self.client.chat.completions.create(
                model=GROK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT + "\n\n**THIS IS THE FINAL SUMMARY.** Provide a comprehensive analysis of the ENTIRE meeting. Include all major technical issues discussed, all key recommendations, and all important decisions/action items."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            analysis = json.loads(response_text)
            
            required_keys = [
                "technical_analysis",
                "potential_issues",
                "recommendations",
                "clarifying_questions",
                "action_items"
            ]
            for key in required_keys:
                if key not in analysis:
                    if key == "technical_analysis":
                        analysis[key] = "No technical analysis available"
                    else:
                        analysis[key] = []
            
            print("✓ Final IT analysis complete")
            return analysis
            
        except Exception as e:
            print(f"Final summary error: {e}")
            return self._get_error_response(str(e))
    
    def _get_error_response(self, error_msg: str) -> Dict:
        """Return error response in expected format."""
        return {
            "technical_analysis": f"Error: {error_msg}",
            "potential_issues": [],
            "recommendations": [],
            "clarifying_questions": [],
            "action_items": []
        }
    
    def get_stats(self) -> Dict:
        """Get meeting statistics."""
        return {
            "duration_minutes": (datetime.now() - self.start_time).seconds // 60,
            "word_count": self.word_count,
            "summary_count": len(self.rolling_summaries),
            "transcript_segments": len(self.full_transcript),
            "issues_identified": len(self.previous_issues),
            "recommendations_given": len(self.previous_recommendations),
            "analyses_performed": self.analysis_count
        }


# ============================================================================
# TESTING CODE
# ============================================================================

if __name__ == "__main__":
    """Test with IT-specific scenarios."""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("❌ XAI_API_KEY not set")
        exit(1)
    
    print("\n" + "="*70)
    print("IT-FOCUSED SUMMARIZER TEST")
    print("="*70)
    
    summarizer = MeetingSummarizer(api_key)
    
    # Test scenario: Azure AKS deployment discussion
    test_transcript = [
        "We're planning to deploy an AKS cluster in Azure for our microservices.",
        "The jump box will be set up on a separate subnet for security reasons.",
        "We'll connect it via VNet peering to access the cluster.",
        "For the database, we're thinking of using MongoDB on EC2 instances.",
        "We should open port 22 from any IP to make remote access easier during testing.",
        "The AKS cluster will have 3 nodes initially, all in the same availability zone.",
        "We need to set up CI/CD pipeline with Jenkins on a t2.micro instance.",
        "Let's use admin credentials hardcoded in the application for now.",
        "Bob will handle the deployment by Friday.",
        "We should also set up logging at some point."
    ]
    
    print("\nSimulating IT meeting transcript...\n")
    
    for i, segment in enumerate(test_transcript):
        print(f"[{i+1}] {segment}")
        analysis = summarizer.add_transcript(segment)
        
        if analysis:
            print("\n" + "-"*70)
            print("📊 GROK IT ANALYSIS:")
            print("-"*70)
            print(json.dumps(analysis, indent=2))
            print("-"*70 + "\n")
    
    # Test comprehensive analysis
    print("\n🎯 TESTING COMPREHENSIVE ANALYSIS (force_analysis)...\n")
    comprehensive = summarizer.force_analysis()
    
    print("="*70)
    print("COMPREHENSIVE ANALYSIS (ALL TRANSCRIPTS)")
    print("="*70)
    print(json.dumps(comprehensive, indent=2))
    
    # Final summary
    print("\n\nGenerating final IT analysis...\n")
    final = summarizer.get_final_summary()
    
    print("="*70)
    print("FINAL IT ANALYSIS")
    print("="*70)
    print(json.dumps(final, indent=2))
    
    # Stats
    stats = summarizer.get_stats()
    print("\n" + "="*70)
    print("📊 STATISTICS")
    print("="*70)
    for key, value in stats.items():
        print(f"{key}: {value}")