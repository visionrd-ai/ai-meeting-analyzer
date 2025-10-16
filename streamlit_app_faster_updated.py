import warnings
warnings.filterwarnings('ignore')
import os, time, json, pickle, tempfile
from datetime import datetime
from pathlib import Path
import streamlit as st
from audio_processor_faster_whisper import AudioProcessor
from summarizer import MeetingSummarizer

# ================================================================
# FILE STORAGE SETUP
# ================================================================

TEMP_DIR = tempfile.gettempdir()
TRANSCRIPT_FILE = os.path.join(TEMP_DIR, "meeting_transcripts.pkl")
METADATA_FILE = os.path.join(TEMP_DIR, "meeting_metadata.pkl")

def save_transcripts(segments):
    try:
        with open(TRANSCRIPT_FILE, 'wb') as f: pickle.dump(segments, f)
        return True
    except Exception as e:
        print(f"Error saving transcripts: {e}"); return False

def load_transcripts():
    try:
        if os.path.exists(TRANSCRIPT_FILE):
            with open(TRANSCRIPT_FILE, 'rb') as f: return pickle.load(f)
    except Exception as e: print(f"Error loading transcripts: {e}")
    return []

def save_metadata(data):
    try:
        with open(METADATA_FILE, 'wb') as f: pickle.dump(data, f)
        return True
    except Exception as e:
        print(f"Error saving metadata: {e}"); return False

def load_metadata():
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'rb') as f: return pickle.load(f)
    except Exception as e: print(f"Error loading metadata: {e}")
    return {}

def clear_storage():
    for f in [TRANSCRIPT_FILE, METADATA_FILE]:
        if os.path.exists(f): os.remove(f)

# ================================================================
# PAGE CONFIG
# ================================================================

st.set_page_config(
    page_title="AI IT Meeting Analyzer",
    page_icon="💻",
    layout="wide",
)

# ================================================================
# CUSTOM CSS
# ================================================================

st.markdown("""
<style>
:root {
    --primary: #0066CC;
    --secondary: #0099FF;
    --success: #00CC66;
    --warning: #FF9900;
    --danger: #CC0000;
    --bg: #F5F7FA;
}
.stApp {background: var(--bg); font-family: 'Inter', sans-serif;}
.hero {
    background: linear-gradient(135deg, #0066CC, #0099FF);
    color: white; text-align:center;
    border-radius:16px; padding:2.5rem 1.5rem; margin-bottom:2rem;
    box-shadow: 0 4px 12px rgba(0,102,204,0.3);
}
.hero h1 {margin:0; font-size:2.5rem; font-weight:700;}
.hero p {font-size:1.1rem; opacity:0.95; margin-top:0.5rem;}

.card {
    background:white; border-radius:12px;
    padding:1.5rem; box-shadow:0 2px 8px rgba(0,0,0,0.08);
    transition: all 0.3s ease; margin-bottom:1rem;
}
.card:hover {transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.12);}

.feature {
    background: linear-gradient(135deg, #f0f4ff, #e6f0ff);
    border-left: 5px solid var(--secondary);
    border-radius: 10px; padding:1.2rem; height:100%;
}
.feature h4 {color: var(--primary); margin-top:0;}

.recording {
    background:linear-gradient(90deg, var(--danger), #FF3333);
    color:white; text-align:center; padding:1rem;
    border-radius:10px; font-weight:700; font-size:1.1rem;
    animation:pulse 2s infinite; box-shadow: 0 4px 12px rgba(204,0,0,0.4);
}
@keyframes pulse {0%{opacity:1;}50%{opacity:0.85;}100%{opacity:1;}}

.analyzing-indicator {
    background: linear-gradient(90deg, #0099FF, #00CCFF);
    color: white; text-align: center; padding: 1rem;
    border-radius: 8px; font-weight: 600; margin-bottom: 1rem;
    animation: pulse 1.5s infinite;
    box-shadow: 0 2px 8px rgba(0, 153, 255, 0.3);
}

.analysis-mode-card {
    background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
    border-left: 5px solid var(--success);
    border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem;
}

.manual-mode-card {
    background: linear-gradient(135deg, #FFF3E0, #FFE0B2);
    border-left: 5px solid var(--warning);
    border-radius: 10px; padding: 1.2rem; margin-bottom: 1rem;
}

.issue-badge {
    background: #FFF3CD; color: #856404; 
    padding: 0.4rem 0.8rem; border-radius: 6px; 
    font-weight: 600; display: inline-block; margin: 0.3rem;
    border-left: 4px solid var(--warning);
}

.recommendation-badge {
    background: #D4EDDA; color: #155724;
    padding: 0.4rem 0.8rem; border-radius: 6px;
    font-weight: 600; display: inline-block; margin: 0.3rem;
    border-left: 4px solid var(--success);
}

.question-badge {
    background: #D1ECF1; color: #0C5460;
    padding: 0.4rem 0.8rem; border-radius: 6px;
    font-weight: 600; display: inline-block; margin: 0.3rem;
    border-left: 4px solid var(--secondary);
}

.footer {
    text-align:center; color:#6B7280; font-size:0.9rem; 
    margin-top:3rem; padding-top:2rem; border-top:1px solid #E5E7EB;
}

.analysis-indicator {
    background: linear-gradient(90deg, #00CC66, #00FF80);
    color: white; text-align: center; padding: 0.8rem;
    border-radius: 8px; font-weight: 600; margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0, 204, 102, 0.3);
}
</style>
""", unsafe_allow_html=True)

# ================================================================
# SESSION STATE
# ================================================================

defaults = {
    'is_recording': False,
    'current_analysis': None,
    'final_summary': None,
    'audio_processor': None,
    'summarizer': None,
    'start_time': None,
    'recording_session_id': None,
    'analysis_mode': 'automatic',  # 'automatic' or 'manual'
    'auto_words_count': 200,  # Default word count for automatic mode
    'last_manual_analysis_time': None,
    'manual_analysis_count': 0,
    'is_analyzing': False,  # NEW: Track if analysis is in progress
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ================================================================
# CORE CALLBACKS
# ================================================================

def on_new_transcript(text: str):
    segs = load_transcripts(); segs.append(text); save_transcripts(segs)

def start_recording():
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key:
        st.error("❌ Missing XAI_API_KEY! Set environment variable and rerun."); return
    try:
        clear_storage()
        
        # Determine words per analysis based on mode
        if st.session_state.analysis_mode == 'automatic':
            words_per_analysis = st.session_state.auto_words_count
        else:
            words_per_analysis = 999999  # Very high number for manual mode
        
        # Initialize summarizer with word threshold
        st.session_state.summarizer = MeetingSummarizer(xai_key, words_per_analysis=words_per_analysis)
        st.session_state.audio_processor = AudioProcessor(on_new_transcript)
        st.session_state.start_time = datetime.now()
        st.session_state.recording_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.manual_analysis_count = 0
        st.session_state.is_analyzing = False  # Reset analyzing flag
        
        save_metadata({
            'start_time': st.session_state.start_time,
            'session_id': st.session_state.recording_session_id,
            'analysis_mode': st.session_state.analysis_mode,
            'words_per_analysis': words_per_analysis if st.session_state.analysis_mode == 'automatic' else 'manual'
        })
        
        st.session_state.audio_processor.start_recording()
        st.session_state.is_recording = True
        
        mode_desc = f"every {words_per_analysis} words" if st.session_state.analysis_mode == 'automatic' else "on-demand"
        st.success(f"🎙️ Recording started in **{st.session_state.analysis_mode.upper()}** mode ({mode_desc})!")
    except Exception as e:
        st.error(f"Error: {e}")

def stop_recording():
    if st.session_state.audio_processor:
        st.session_state.audio_processor.stop_recording()
    time.sleep(2)
    segments = load_transcripts()
    if len(segments) == 0:
        st.warning("⚠️ No transcripts found! Did you speak during recording?")
        st.session_state.is_recording = False; return
    
    # Generate final summary with timeout handling
    xai_key = os.getenv("XAI_API_KEY")
    if xai_key:
        try:
            with st.spinner("🧠 Generating Final IT Analysis..."):
                fresh = MeetingSummarizer(xai_key)
                for seg in segments: 
                    if hasattr(fresh, 'add_transcript'):
                        try:
                            fresh.add_transcript(seg, auto_analyze=False)
                        except TypeError:
                            fresh.add_transcript(seg)
                    else:
                        fresh.add_transcript(seg)
                
                # Try to get final summary with timeout handling
                try:
                    st.session_state.final_summary = fresh.get_final_summary()
                except Exception as e:
                    error_msg = str(e)
                    if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                        st.warning("⚠️ API request timed out. Retrying with shorter context...")
                        # Retry with last 500 words only
                        fresh_retry = MeetingSummarizer(xai_key)
                        recent_segments = segments[-10:]  # Last 10 segments
                        for seg in recent_segments:
                            try:
                                fresh_retry.add_transcript(seg, auto_analyze=False)
                            except TypeError:
                                fresh_retry.add_transcript(seg)
                        st.session_state.final_summary = fresh_retry.get_final_summary()
                    else:
                        raise e
        except Exception as e:
            st.error(f"❌ Error generating final summary: {str(e)}")
            st.info("💡 Tip: You can still see the last live analysis below")
            # Keep the last analysis visible even if final summary fails
    
    st.session_state.is_recording = False
    st.session_state.is_analyzing = False  # Reset analyzing flag
    
    if st.session_state.final_summary:
        st.success("✅ Recording complete! Final IT analysis generated.")
    else:
        st.warning("⚠️ Recording stopped. Final summary failed, but last analysis is available.")

def trigger_manual_analysis():
    """Set flag to trigger analysis on next rerun."""
    if not st.session_state.summarizer:
        st.error("❌ No active recording session!")
        return
    
    segments = load_transcripts()
    if len(segments) == 0:
        st.warning("⚠️ No transcript available yet! Start speaking.")
        return
    
    # Check word count
    word_count = st.session_state.summarizer.word_count
    if word_count < 10:
        st.warning(f"⚠️ Only {word_count} words transcribed so far. Speak more for better analysis.")
        return
    
    # Set flag to trigger analysis
    st.session_state.is_analyzing = True

def perform_manual_analysis():
    """Actually perform the analysis (called during script run if flag is set)."""
    if not st.session_state.is_analyzing:
        return
    
    try:
        word_count = st.session_state.summarizer.word_count
        total_segments = len(st.session_state.summarizer.full_transcript)
        
        # Try to use force_analysis if available (new version)
        if hasattr(st.session_state.summarizer, 'force_analysis'):
            analysis = st.session_state.summarizer.force_analysis()
        else:
            # Fallback: use _analyze_current_state for old version
            analysis = st.session_state.summarizer._analyze_current_state()
        
        if analysis:
            st.session_state.current_analysis = analysis
            st.session_state.last_manual_analysis_time = datetime.now()
            st.session_state.manual_analysis_count += 1
            st.session_state.is_analyzing = False
            
            # More detailed success message
            st.success(f"""
            ✅ Comprehensive Analysis #{st.session_state.manual_analysis_count} Complete!
            
            📊 Analyzed: {word_count} words across {total_segments} transcript segments
            
            💡 View detailed results below (technical overview, issues, recommendations, questions)
            """)
        else:
            st.session_state.is_analyzing = False
            st.error("❌ Analysis failed. Please try again.")
    except Exception as e:
        st.session_state.is_analyzing = False
        st.error(f"❌ Analysis error: {str(e)}")

def update_live_analysis():
    """Update live analysis - adds transcripts to summarizer for both modes."""
    if not st.session_state.is_recording or not st.session_state.summarizer: return
    
    segs = load_transcripts()
    current = st.session_state.summarizer.full_transcript
    
    if len(segs) > len(current):
        for seg in segs[len(current):]:
            # Add transcript - check if add_transcript accepts auto_analyze parameter
            try:
                # Try new version with auto_analyze parameter
                auto_analyze = (st.session_state.analysis_mode == 'automatic')
                analysis = st.session_state.summarizer.add_transcript(seg, auto_analyze=auto_analyze)
            except TypeError:
                # Old version without auto_analyze parameter
                analysis = st.session_state.summarizer.add_transcript(seg)
            
            if analysis: 
                st.session_state.current_analysis = analysis

# ================================================================
# LIVE REFRESH
# ================================================================

if st.session_state.is_recording:
    update_live_analysis()

# Perform manual analysis if requested (non-blocking)
if st.session_state.is_analyzing and st.session_state.summarizer:
    perform_manual_analysis()

# ================================================================
# HEADER SECTION
# ================================================================

st.markdown("""
<div class="hero">
    <h1>💻 AI IT Meeting Analyzer</h1>
    <p>Real-time Technical Issue Identification & Best Practice Recommendations</p>
    <p style="font-size:0.9rem; margin-top:0.5rem;">Powered by Grok AI • Cloud • Security • DevOps • Infrastructure</p>
</div>
""", unsafe_allow_html=True)

# ================================================================
# ANALYSIS SETTINGS SECTION (BEFORE RECORDING STARTS)
# ================================================================

if not st.session_state.is_recording:
    st.markdown("### ⚙️ Analysis Settings")
    
    col_mode, col_config = st.columns([1, 2])
    
    with col_mode:
        analysis_mode = st.radio(
            "Select Analysis Mode:",
            options=['automatic', 'manual'],
            format_func=lambda x: "🤖 Automatic (Word-based)" if x == 'automatic' else "👆 Manual (On-demand)",
            key='analysis_mode_selector',
            help="Choose how you want analysis to be triggered"
        )
        st.session_state.analysis_mode = analysis_mode
    
    with col_config:
        if analysis_mode == 'automatic':
            st.markdown('<div class="analysis-mode-card">', unsafe_allow_html=True)
            st.markdown("**🤖 Automatic Analysis Mode**")
            st.markdown("Analysis triggers automatically after reaching word threshold")
            
            # Word count selector with preset options and custom input
            word_option = st.selectbox(
                "Word Count Threshold:",
                options=['200 words (Very Frequent)', '300 words (Frequent)', '500 words (Moderate)', '1000 words (Sparse)', 'Custom'],
                index=0
            )
            
            if word_option == 'Custom':
                custom_words = st.number_input(
                    "Enter custom word count:",
                    min_value=50,
                    max_value=5000,
                    value=200,
                    step=50,
                    help="Analysis will trigger after this many words"
                )
                st.session_state.auto_words_count = custom_words
            else:
                # Extract number from option
                st.session_state.auto_words_count = int(word_option.split()[0])
            
            st.info(f"📊 Analysis will trigger every **{st.session_state.auto_words_count} words**")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="manual-mode-card">', unsafe_allow_html=True)
            st.markdown("**👆 Manual Analysis Mode**")
            st.markdown("Analysis triggers only when you click the analysis button")
            st.info("💡 You have full control - analyze whenever you want during the meeting. Each analysis reviews **all accumulated transcripts** (not just new ones)")
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()

# ================================================================
# CONTROLS SECTION
# ================================================================

cols = st.columns([1, 1, 1, 1])

with cols[0]:
    if st.button("▶️ Start Recording", use_container_width=True, disabled=st.session_state.is_recording, type="primary"):
        start_recording()

with cols[1]:
    if st.button("⏹️ Stop Recording", use_container_width=True, disabled=not st.session_state.is_recording):
        stop_recording()

with cols[2]:
    # Manual analysis button - only show when recording and in manual mode OR when user wants to trigger extra analysis
    if st.session_state.is_recording:
        word_count_help = st.session_state.summarizer.word_count if st.session_state.summarizer else 0
        if st.button("🎯 Analyze Now", use_container_width=True, type="secondary", 
                     help=f"Comprehensive analysis of ALL {word_count_help} accumulated words (complete discussion so far)",
                     disabled=st.session_state.is_analyzing):
            trigger_manual_analysis()

with cols[3]:
    if st.button("🧹 Clear Data", use_container_width=True, disabled=st.session_state.is_recording):
        clear_storage()
        st.session_state.final_summary = None
        st.session_state.current_analysis = None
        st.session_state.manual_analysis_count = 0
        st.session_state.is_analyzing = False
        st.rerun()

# ================================================================
# RECORDING INDICATOR
# ================================================================

if st.session_state.is_recording:
    dur = (datetime.now() - st.session_state.start_time).seconds
    min_, sec = divmod(dur, 60)
    
    mode_indicator = ""
    if st.session_state.analysis_mode == 'automatic':
        mode_indicator = f"Auto-analysis every {st.session_state.auto_words_count} words"
    else:
        mode_indicator = f"Manual mode - {st.session_state.manual_analysis_count} analyses triggered"
    
    st.markdown(f"""
    <div class="recording">🔴 LIVE RECORDING - {min_:02d}:{sec:02d} | {mode_indicator}</div>
    """, unsafe_allow_html=True)
    
    # Show last analysis time for manual mode
    if st.session_state.analysis_mode == 'manual' and st.session_state.last_manual_analysis_time:
        seconds_ago = (datetime.now() - st.session_state.last_manual_analysis_time).seconds
        st.markdown(f"""
        <div class="analysis-indicator">
            ✅ Last analysis: {seconds_ago} seconds ago | Click "Analyze Now" for updated insights
        </div>
        """, unsafe_allow_html=True)

# ================================================================
# MAIN CONTENT LAYOUT
# ================================================================

left, right = st.columns([1, 1])
segments = load_transcripts()
full_text = " ".join(segments)

# -------- LEFT: Transcript --------
with left:
    st.markdown("### 📝 Live Transcript")
    
    # Show word count prominently
    if st.session_state.summarizer and st.session_state.is_recording:
        summarizer_words = st.session_state.summarizer.word_count
        st.info(f"📊 **{summarizer_words} words** accumulated in summarizer")
    
    if full_text:
        word_count = len(full_text.split())
        
        # Show progress for automatic mode
        if st.session_state.is_recording and st.session_state.analysis_mode == 'automatic':
            words_until_next = st.session_state.auto_words_count - (
                word_count - (st.session_state.summarizer.last_analysis_word_count if st.session_state.summarizer else 0)
            )
            if words_until_next > 0:
                progress = 1 - (words_until_next / st.session_state.auto_words_count)
                st.progress(progress, text=f"📊 {words_until_next} words until next auto-analysis")
        
        st.markdown(f"""
        <div class="card" style="max-height:500px;overflow-y:auto;">
            <small style="color:#6B7280;">{word_count} words • {len(segments)} segments</small>
            <p style="line-height:1.8; color:#111827; margin-top:1rem;">{full_text}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("🎙️ Waiting for IT discussion... Start talking about cloud infrastructure, security, DevOps, etc.")

# -------- RIGHT: IT Insights --------
with right:
    st.markdown("### 💡 IT Analysis & Insights")
    
    # Show loading indicator if analyzing (only in this panel)
    if st.session_state.is_analyzing:
        word_count = st.session_state.summarizer.word_count if st.session_state.summarizer else 0
        st.markdown(f"""
        <div class="analyzing-indicator">
            🔄 Comprehensive Analysis in Progress<br>
            <small>Analyzing ALL {word_count} words of your discussion...</small>
        </div>
        """, unsafe_allow_html=True)
    
    analysis = st.session_state.final_summary or st.session_state.current_analysis
    
    if analysis:
        # Show semi-transparent overlay if analyzing
        if st.session_state.is_analyzing:
            st.markdown("""
            <div style="background: rgba(0, 153, 255, 0.1); border: 2px dashed #0099FF; 
                        border-radius: 8px; padding: 1rem; text-align: center; margin-bottom: 1rem;">
                <p style="margin: 0; color: #0099FF; font-weight: 600;">
                    ⏳ Previous analysis shown below. New analysis in progress...
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Status badge
        if st.session_state.final_summary:
            st.success("✅ Meeting Complete - Final Analysis")
        else:
            if st.session_state.analysis_mode == 'automatic':
                st.info(f"🔄 Live Analysis - Auto-updates every {st.session_state.auto_words_count} words (incremental)")
            else:
                word_count = st.session_state.summarizer.word_count if st.session_state.summarizer else 0
                st.info(f"👆 Manual Mode - Analysis #{st.session_state.manual_analysis_count} (comprehensive review of {word_count} words)")
        
        # Technical Analysis Overview
        with st.expander("📊 Technical Overview", expanded=True):
            tech_analysis = analysis.get("technical_analysis", "No analysis yet.")
            st.markdown(f"**{tech_analysis}**")
        
        # Potential Issues (Most Important!)
        with st.expander("⚠️ Potential Issues", expanded=True):
            issues = analysis.get("potential_issues", [])
            if issues:
                for i, issue in enumerate(issues, 1):
                    st.markdown(f"""
                    <div class="issue-badge">
                        ⚠️ Issue {i}
                    </div>
                    <p style="margin-left:1rem; margin-top:0.5rem;">{issue}</p>
                    """, unsafe_allow_html=True)
            else:
                st.write("✅ No issues detected in current discussion")
        
        # Recommendations
        with st.expander("✅ Recommendations", expanded=True):
            recs = analysis.get("recommendations", [])
            if recs:
                for i, rec in enumerate(recs, 1):
                    st.markdown(f"""
                    <div class="recommendation-badge">
                        ✅ Recommendation {i}
                    </div>
                    <p style="margin-left:1rem; margin-top:0.5rem;">{rec}</p>
                    """, unsafe_allow_html=True)
            else:
                st.write("(No recommendations yet)")
        
        # Clarifying Questions
        with st.expander("❓ Clarifying Questions", expanded=False):
            questions = analysis.get("clarifying_questions", [])
            if questions:
                for i, q in enumerate(questions, 1):
                    st.markdown(f"""
                    <div class="question-badge">
                        ❓ Question {i}
                    </div>
                    <p style="margin-left:1rem; margin-top:0.5rem;">{q}</p>
                    """, unsafe_allow_html=True)
            else:
                st.write("(No questions)")
        
        # Action Items
        with st.expander("📋 Action Items", expanded=False):
            actions = analysis.get("action_items", [])
            if actions:
                for i, a in enumerate(actions, 1):
                    st.markdown(f"**{i}.** {a}")
            else:
                st.write("(No action items identified)")
    else:
        mode_text = "Click 'Analyze Now' to analyze all accumulated transcripts" if st.session_state.analysis_mode == 'manual' else f"will appear after {st.session_state.auto_words_count} words"
        st.info(f"""
        💬 IT insights {mode_text}.
        
        **Try discussing:**
        - Cloud infrastructure (AWS, Azure, GCP)
        - Security configurations
        - Kubernetes/container deployments
        - Database architecture
        - Network setup
        """)

# ================================================================
# STATS SECTION
# ================================================================

if segments:
    st.divider()
    st.markdown("### 📊 Meeting Statistics")
    duration = 0
    metadata = load_metadata()
    if metadata.get('start_time'):
        duration = (datetime.now() - metadata['start_time']).seconds // 60
    
    colx = st.columns(5)
    colx[0].metric("Duration", f"{duration} min")
    colx[1].metric("Words", len(full_text.split()))
    colx[2].metric("Segments", len(segments))
    
    if st.session_state.summarizer:
        stats = st.session_state.summarizer.get_stats()
        colx[3].metric("Issues Found", stats.get('issues_identified', 0))
        # Handle both old and new version of summarizer
        if 'analyses_performed' in stats:
            colx[4].metric("Analyses Done", stats.get('analyses_performed', 0))
        else:
            # Old version doesn't track this
            colx[4].metric("Analyses Done", st.session_state.manual_analysis_count if st.session_state.analysis_mode == 'manual' else 'Auto')
    
    with st.expander("🔧 Debug Info"):
        debug_info = {
            "Storage": TRANSCRIPT_FILE,
            "Segments": len(segments),
            "Session": st.session_state.recording_session_id,
            "Mode": st.session_state.analysis_mode,
            "Auto Words": st.session_state.auto_words_count if st.session_state.analysis_mode == 'automatic' else 'N/A',
            "Manual Count": st.session_state.manual_analysis_count
        }
        for key, val in debug_info.items():
            st.code(f"{key}: {val}")

# ================================================================
# FOOTER
# ================================================================

st.markdown("""
<div class="footer">
<p><strong>🔒 Privacy First:</strong> Local transcription with Faster-Whisper • Only analysis sent to Grok API</p>
<p><strong>💰 Cost Efficient:</strong> ~$0.02 per 10-minute meeting (transcription free, Grok analysis $0.02)</p>
<p><strong>🎯 IT Domains:</strong> Cloud (Azure/AWS/GCP) • Kubernetes • Security • DevOps • Networking • Database Architecture</p>
<p><strong>⚙️ Flexible Analysis:</strong> Choose between automatic (word-based) or manual (on-demand) analysis modes</p>
<p style="margin-top:1rem; font-size:0.85rem;">Developed for IT teams seeking real-time technical guidance during meetings</p>
</div>
""", unsafe_allow_html=True)

# ================================================================
# AUTO REFRESH FOR LIVE UPDATES
# ================================================================

if st.session_state.is_recording:
    time.sleep(2)
    st.rerun()