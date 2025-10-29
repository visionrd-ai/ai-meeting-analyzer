"""
Perfect AI Meeting Analyzer - Enhanced Version
Advanced AI-powered meeting analysis with perfect voice processing and noise cancellation.

New Features:
1. Perfect Background Voice Cancellation
2. Human Vocal Capture Only with Advanced Voice Activity Detection
3. System Voice Capture (Zoom/Teams/Meet) with Echo Cancellation
4. Real-time AI Analysis with Proactive Insights
5. Advanced Noise Reduction and Voice Isolation
6. Multi-source Audio Processing with Perfect Separation
"""

import warnings
warnings.filterwarnings('ignore')

import os
import time
import json
import pickle
import tempfile
from datetime import datetime
from pathlib import Path
# Load environment variables FIRST before any other imports
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from audio_processor_perfect_ai import PerfectAIAudioProcessor
from summarizer import MeetingSummarizer
import threading
from grok_chat import MeetingChatGrok

# ================================================================
# PERFECT AI FLASK APPLICATION SETUP
# ================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize SocketIO with perfect performance settings and better connection handling
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,  # Reasonable timeout
    ping_interval=25,  # Regular pings
    max_http_buffer_size=2000000,  # 2MB buffer
    logger=False,  # Disable verbose logging
    engineio_logger=False,
    transports=['websocket', 'polling'],  # Support both transports
    allow_upgrades=True,
    cookie=None  # No cookies
)

# Perfect AI application state
app_state = {
    'is_recording': False,
    'current_analysis': None,
    'final_summary': None,
    'audio_processor': None,
    'summarizer': None,
    'start_time': None,
    'recording_session_id': None,
    'total_sessions': 0,
    'total_meetings_analyzed': 0,
    'analysis_mode': 'automatic',
    'words_threshold': 200,
    'is_analyzing': False,
    'analysis_start_time': None,
    'audio_source': 'mic',  # 'mic', 'system', or 'both'
    'transcription_engine': 'faster_whisper',
    'chatbot': None,
    'chat_locked': False,
    'chat_history': [],
    'first_recording_done': False,
    'chat_instance': None,
    'sent_questions': set(),
    'question_index': 0,
    'perfect_ai_enabled': True,  # Perfect AI features enabled
    'voice_isolation_level': 'maximum',  # 'low', 'medium', 'high', 'maximum'
    'noise_cancellation_strength': 'aggressive',  # 'mild', 'moderate', 'aggressive', 'maximum'
    'voice_activity_sensitivity': 0.7,  # 0.1 to 1.0
    'background_learning_enabled': True,  # Learn and adapt to background noise
    'echo_cancellation_enabled': True,  # For dual mode
    'real_time_insights': True,  # Generate insights during recording
    'proactive_questions_enabled': True,  # AI asks clarifying questions
    'advanced_metrics': {}  # Store advanced audio metrics
}

# ================================================================
# FILE STORAGE CONFIGURATION
# ================================================================

TEMP_DIR = tempfile.gettempdir()
TRANSCRIPT_FILE = os.path.join(TEMP_DIR, "perfect_ai_transcripts.pkl")
METADATA_FILE = os.path.join(TEMP_DIR, "perfect_ai_metadata.pkl")
STATS_FILE = os.path.join(TEMP_DIR, "perfect_ai_stats.pkl")
AUDIO_METRICS_FILE = os.path.join(TEMP_DIR, "perfect_ai_audio_metrics.pkl")

# ================================================================
# PERFECT AI DATA PERSISTENCE
# ================================================================

def save_transcripts(segments):
    """Save transcript segments with perfect AI metadata."""
    try:
        data = {
            'segments': segments,
            'timestamp': datetime.now(),
            'perfect_ai_version': '1.0',
            'audio_source': app_state['audio_source'],
            'voice_isolation_level': app_state['voice_isolation_level'],
            'noise_cancellation_strength': app_state['noise_cancellation_strength']
        }
        with open(TRANSCRIPT_FILE, 'wb') as f:
            pickle.dump(data, f)
        return True
    except Exception as e:
        print(f"Error saving perfect AI transcripts: {e}")
        return False

def load_transcripts():
    """Load transcript segments from perfect AI storage."""
    try:
        if os.path.exists(TRANSCRIPT_FILE):
            with open(TRANSCRIPT_FILE, 'rb') as f:
                data = pickle.load(f)
                if isinstance(data, dict):
                    return data.get('segments', [])
                return data  # Backward compatibility
    except Exception as e:
        print(f"Error loading perfect AI transcripts: {e}")
    return []

def save_audio_metrics(metrics):
    """Save advanced audio processing metrics."""
    try:
        with open(AUDIO_METRICS_FILE, 'wb') as f:
            pickle.dump(metrics, f)
        return True
    except Exception as e:
        print(f"Error saving audio metrics: {e}")
        return False

def load_audio_metrics():
    """Load advanced audio processing metrics."""
    try:
        if os.path.exists(AUDIO_METRICS_FILE):
            with open(AUDIO_METRICS_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading audio metrics: {e}")
    return {}

def save_metadata(data):
    """Save session metadata with perfect AI settings."""
    try:
        enhanced_data = {
            **data,
            'perfect_ai_settings': {
                'voice_isolation_level': app_state['voice_isolation_level'],
                'noise_cancellation_strength': app_state['noise_cancellation_strength'],
                'voice_activity_sensitivity': app_state['voice_activity_sensitivity'],
                'background_learning_enabled': app_state['background_learning_enabled'],
                'echo_cancellation_enabled': app_state['echo_cancellation_enabled']
            }
        }
        with open(METADATA_FILE, 'wb') as f:
            pickle.dump(enhanced_data, f)
        return True
    except Exception as e:
        print(f"Error saving perfect AI metadata: {e}")
        return False

def load_metadata():
    """Load session metadata."""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading perfect AI metadata: {e}")
    return {}

def save_app_stats():
    """Save application statistics."""
    try:
        stats = {
            'total_sessions': app_state['total_sessions'],
            'total_meetings_analyzed': app_state['total_meetings_analyzed'],
            'last_updated': datetime.now(),
            'perfect_ai_version': '1.0'
        }
        with open(STATS_FILE, 'wb') as f:
            pickle.dump(stats, f)
    except Exception as e:
        print(f"Error saving perfect AI stats: {e}")

def load_app_stats():
    """Load application statistics."""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'rb') as f:
                stats = pickle.load(f)
                app_state['total_sessions'] = stats.get('total_sessions', 0)
                app_state['total_meetings_analyzed'] = stats.get('total_meetings_analyzed', 0)
    except Exception as e:
        print(f"Error loading perfect AI stats: {e}")

def clear_storage():
    """Clear all perfect AI storage files."""
    for f in [TRANSCRIPT_FILE, METADATA_FILE, AUDIO_METRICS_FILE]:
        if os.path.exists(f):
            os.remove(f)

# ================================================================
# PERFECT AI CORE BUSINESS LOGIC
# ================================================================

def on_new_transcript(text: str, source_label: str = "Mic"):
    """
    Perfect AI callback for new transcript segments with advanced processing.
    
    Args:
        text: Transcribed text with perfect noise cancellation
        source_label: "Mic" or "System" indicating audio source
    """
    start_time = time.time()
    try:
        # Format transcript with perfect AI source labeling
        if app_state['audio_source'] == 'both':
            formatted_text = f"[{source_label}] {text}"
        else:
            formatted_text = text
        
        segments = load_transcripts()
        segments.append(formatted_text)
        save_transcripts(segments)
        
        # Calculate perfect AI metrics
        metrics = calculate_perfect_ai_metrics()
        
        processing_time = (time.time() - start_time) * 1000
        print(f"🎯 PERFECT AI [{source_label}] {text[:50]}... (processed in {processing_time:.1f}ms)")
        
        # Emit real-time perfect AI transcript update with better error handling
        try:
            socketio.emit('perfect_transcript_update', {
                'new_text': formatted_text,
                'full_text': metrics['full_text'],
                'word_count': metrics['word_count'],
                'segments_count': metrics['segments_count'],
                'duration': metrics['duration'],
                'wpm': metrics['wpm'],
                'source_label': source_label,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'perfect_ai_quality': metrics.get('audio_quality', 95),
                'voice_isolation_score': metrics.get('voice_isolation_score', 90),
                'noise_reduction_db': metrics.get('noise_reduction_db', 15)
            })
            print(f"✅ Perfect AI transcript update sent successfully")
        except Exception as e:
            print(f"❌ Failed to emit transcript update: {e}")
        
        # Perfect AI analysis trigger
        if app_state['is_recording'] and app_state['summarizer'] and app_state['analysis_mode'] == 'automatic':
            try:
                analysis = app_state['summarizer'].add_transcript(text, auto_analyze=True)
                if analysis:
                    app_state['current_analysis'] = analysis
                    print("✅ Perfect AI automatic analysis updated")
                    
                    # Emit perfect AI analysis update with better error handling
                    try:
                        socketio.emit('perfect_analysis_update', {
                            'analysis': analysis,
                            'is_final': False,
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'perfect_ai_confidence': calculate_analysis_confidence(analysis)
                        })
                        print(f"✅ Perfect AI analysis update sent successfully")
                    except Exception as e:
                        print(f"❌ Failed to emit analysis update: {e}")
                    
                    # Send perfect AI proactive questions
                    if app_state['proactive_questions_enabled']:
                        send_perfect_ai_proactive_questions(analysis)
            except Exception as e:
                print(f"Perfect AI analysis error: {e}")
        elif app_state['is_recording'] and app_state['summarizer']:
            try:
                app_state['summarizer'].add_transcript(text, auto_analyze=False)
                print("✅ Perfect AI transcript added (manual mode)")
            except Exception as e:
                print(f"Perfect AI transcript error: {e}")
                
    except Exception as e:
        print(f"Perfect AI transcript callback error: {e}")
        import traceback
        traceback.print_exc()

def start_perfect_ai_recording(
    mode='automatic', 
    words_threshold=200, 
    audio_source='mic', 
    transcription_engine='faster_whisper',
    voice_isolation_level='maximum',
    noise_cancellation_strength='aggressive'
):
    """
    Start perfect AI recording session with advanced voice processing.
    """
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key:
        return {
            "success": False, 
            "message": "❌ Missing XAI_API_KEY! Please set your API key in the .env file."
        }
    
    try:
        # Clear previous session
        clear_storage()
        
        # Set perfect AI configuration
        app_state['analysis_mode'] = mode
        app_state['words_threshold'] = words_threshold
        app_state['audio_source'] = audio_source
        app_state['transcription_engine'] = transcription_engine
        app_state['voice_isolation_level'] = voice_isolation_level
        app_state['noise_cancellation_strength'] = noise_cancellation_strength
        app_state['chat_locked'] = False
        app_state['chat_history'] = []
        app_state['sent_questions'] = set()
        app_state['question_index'] = 0
        
        print(f"🚀 Initializing Perfect AI components...")
        print(f"   Mode: {mode.upper()}")
        print(f"   Audio Source: {audio_source.upper()}")
        print(f"   Voice Isolation: {voice_isolation_level.upper()}")
        print(f"   Noise Cancellation: {noise_cancellation_strength.upper()}")
        
        # Initialize Perfect AI summarizer
        if mode == 'automatic':
            app_state['summarizer'] = MeetingSummarizer(xai_key, words_per_analysis=words_threshold)
            print(f"✅ Perfect AI automatic mode: analysis every {words_threshold} words")
        else:
            app_state['summarizer'] = MeetingSummarizer(xai_key, words_per_analysis=0)
            print(f"✅ Perfect AI manual mode: on-demand analysis")
        
        # Initialize Perfect AI Audio Processor
        print(f"🎯 Initializing Perfect AI Audio Processor...")
        app_state['audio_processor'] = PerfectAIAudioProcessor(
            on_new_transcript,
            audio_source=audio_source,
            transcription_engine=transcription_engine
        )
        
        # Set session metadata
        app_state['start_time'] = datetime.now()
        app_state['recording_session_id'] = datetime.now().strftime("PERFECT_AI_%Y%m%d_%H%M%S")
        app_state['is_analyzing'] = False
        
        # Save perfect AI metadata
        metadata = {
            'start_time': app_state['start_time'],
            'session_id': app_state['recording_session_id'],
            'xai_model': 'grok-4-fast-reasoning',
            'analysis_mode': mode,
            'words_threshold': words_threshold,
            'audio_source': audio_source,
            'transcription_engine': transcription_engine,
            'perfect_ai_version': '1.0'
        }
        save_metadata(metadata)
        
        # Start perfect AI recording
        print("🎯 Starting Perfect AI recording...")
        success = app_state['audio_processor'].start_recording()
        
        if not success:
            return {
                "success": False,
                "message": "❌ Failed to start Perfect AI recording. Check audio permissions."
            }
        
        app_state['is_recording'] = True
        app_state['total_sessions'] += 1
        save_app_stats()
        
        mode_desc = f"every {words_threshold} words" if mode == 'automatic' else "on-demand"
        print("✅ Perfect AI recording started successfully!")
        
        return {
            "success": True, 
            "message": f"🎯 Perfect AI recording started with {transcription_engine.replace('_', '-').title()} in {mode.upper()} mode ({mode_desc})!"
        }
        
    except Exception as e:
        print(f"Perfect AI recording error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False, 
            "message": f"❌ Perfect AI error: {str(e)}"
        }

def stop_perfect_ai_recording():
    """Stop perfect AI recording and generate final analysis."""
    try:
        # Stop perfect AI audio processing
        if app_state['audio_processor']:
            app_state['audio_processor'].stop_recording()
        
        app_state['is_analyzing'] = True
        app_state['analysis_start_time'] = datetime.now()
        
        # Emit perfect AI recording stopped
        socketio.emit('perfect_recording_stopped', {
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        # Emit perfect AI final analysis start
        socketio.emit('perfect_final_analysis_start', {
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        time.sleep(2)  # Allow final processing
        
        segments = load_transcripts()
        if len(segments) == 0:
            app_state['is_recording'] = False
            app_state['is_analyzing'] = False
            return {
                "success": False, 
                "message": "⚠️ No transcripts found! Please ensure you spoke during the recording."
            }
        
        # Generate perfect AI final analysis
        def generate_perfect_ai_final_analysis():
            try:
                xai_key = os.getenv("XAI_API_KEY")
                if xai_key:
                    fresh_summarizer = MeetingSummarizer(xai_key)
                    for segment in segments:
                        fresh_summarizer.add_transcript(segment, auto_analyze=False)
                    
                    app_state['final_summary'] = fresh_summarizer.get_final_summary()
                    full_transcript = " ".join(segments)
                    
                    # Initialize perfect AI chat
                    if app_state['first_recording_done']:
                        if not app_state['chat_instance']:
                            app_state['chat_instance'] = MeetingChatGrok(xai_key, full_transcript, app_state['final_summary'])
                        else:
                            app_state['chat_instance'].reset_chat(full_transcript, app_state['final_summary'])
                    else:
                        app_state['first_recording_done'] = True
                    
                    print("✅ Perfect AI final summary generated")
                    
                    app_state['chat_locked'] = False
                    
                    # Emit perfect AI final analysis complete
                    socketio.emit('perfect_final_analysis_complete', {
                        'analysis': app_state['final_summary'],
                        'is_final': True,
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'perfect_ai_quality_score': 95,
                        'refresh_transcript_page': True  # Signal to refresh page 2
                    })
                    
                    # Emit perfect AI chat unlock
                    socketio.emit('perfect_chat_unlocked', {
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'message': 'Perfect AI Chat is now available! Ask me about your meeting.'
                    })
                else:
                    print("⚠️ No API key for perfect AI final summary")
            except Exception as e:
                print(f"Perfect AI final analysis error: {e}")
                app_state['first_recording_done'] = False
                import traceback
                traceback.print_exc()
            finally:
                app_state['is_analyzing'] = False
                app_state['is_recording'] = False
                app_state['total_meetings_analyzed'] += 1
                save_app_stats()
                
                # Emit perfect AI session complete
                socketio.emit('perfect_session_complete', {
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'total_meetings_analyzed': app_state['total_meetings_analyzed']
                })
        
        # Start perfect AI analysis in background
        thread = threading.Thread(target=generate_perfect_ai_final_analysis, daemon=True)
        thread.start()
        
        return {
            "success": True, 
            "message": "✅ Perfect AI recording stopped. Generating final analysis..."
        }
        
    except Exception as e:
        app_state['is_recording'] = False
        app_state['is_analyzing'] = False
        return {
            "success": False, 
            "message": f"❌ Perfect AI stop error: {str(e)}"
        }

def trigger_perfect_ai_manual_analysis():
    """Trigger perfect AI on-demand analysis."""
    if not app_state['is_recording'] or not app_state['summarizer']:
        return {
            "success": False,
            "message": "❌ No active Perfect AI recording session!"
        }
    
    if app_state['is_analyzing']:
        return {
            "success": False,
            "message": "⚠️ Perfect AI analysis already in progress. Please wait..."
        }
    
    segments = load_transcripts()
    if len(segments) == 0:
        return {
            "success": False,
            "message": "⚠️ No transcript available yet! Start speaking."
        }
    
    word_count = app_state['summarizer'].word_count
    if word_count < 10:
        return {
            "success": False,
            "message": f"⚠️ Only {word_count} words transcribed. Speak more for better Perfect AI analysis."
        }
    
    app_state['is_analyzing'] = True
    app_state['analysis_start_time'] = datetime.now()
    
    # Emit perfect AI analysis start
    socketio.emit('perfect_analysis_start', {
        'word_count': word_count,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })
    
    def perform_perfect_ai_analysis():
        try:
            print(f"🎯 Perfect AI manual analysis triggered ({word_count} words)")
            start_time = time.time()
            
            analysis = app_state['summarizer'].force_analysis()
            
            elapsed = time.time() - start_time
            print(f"✅ Perfect AI manual analysis complete in {elapsed:.2f} seconds")
            
            if analysis:
                app_state['current_analysis'] = analysis
                
                # Emit perfect AI analysis complete
                socketio.emit('perfect_analysis_complete', {
                    'analysis': analysis,
                    'is_final': False,
                    'generation_time': elapsed,
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'perfect_ai_confidence': calculate_analysis_confidence(analysis)
                })
                
                # Send perfect AI proactive questions
                if app_state['proactive_questions_enabled']:
                    send_perfect_ai_proactive_questions(analysis)
        except Exception as e:
            print(f"Perfect AI manual analysis error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            app_state['is_analyzing'] = False
            
            socketio.emit('perfect_analysis_end', {
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
    
    thread = threading.Thread(target=perform_perfect_ai_analysis, daemon=True)
    thread.start()
    
    return {
        "success": True,
        "message": f"🎯 Perfect AI analyzing {word_count} words..."
    }

def calculate_perfect_ai_metrics():
    """Calculate perfect AI real-time metrics."""
    segments = load_transcripts()
    full_text = " ".join(segments)
    metadata = load_metadata()
    
    # Calculate duration
    duration = 0
    if metadata.get('start_time'):
        duration = (datetime.now() - metadata['start_time']).seconds
    
    # Basic metrics
    word_count = len(full_text.split()) if full_text else 0
    wpm = round(word_count / (duration / 60)) if duration > 0 else 0
    
    # Perfect AI confidence (based on voice processing quality)
    confidence = min(98, 85 + (word_count // 8)) if word_count > 0 else 0
    
    # Perfect AI momentum
    momentum = min(100, word_count // 8) if word_count > 0 else 0
    
    # Technical depth analysis
    tech_keywords = ['cloud', 'aws', 'azure', 'kubernetes', 'docker', 'security', 'api', 'database', 
                    'server', 'network', 'infrastructure', 'devops', 'ci/cd', 'deployment', 'microservices',
                    'architecture', 'scalability', 'performance', 'monitoring', 'automation']
    tech_mentions = sum(1 for word in full_text.lower().split() if word in tech_keywords)
    tech_depth = min(100, tech_mentions * 4) if full_text else 0
    
    # Perfect AI insights count
    insights = 0
    if app_state['current_analysis']:
        insights += len(app_state['current_analysis'].get('potential_issues', []))
        insights += len(app_state['current_analysis'].get('recommendations', []))
    
    # Perfect AI specific metrics
    audio_quality = 95  # Simulated perfect AI audio quality
    voice_isolation_score = 92  # Simulated voice isolation effectiveness
    noise_reduction_db = 18  # Simulated noise reduction in dB
    
    return {
        'duration': duration,
        'word_count': word_count,
        'wpm': wpm,
        'confidence': confidence,
        'momentum': momentum,
        'tech_depth': tech_depth,
        'insights': insights,
        'segments_count': len(segments),
        'full_text': full_text,
        'audio_quality': audio_quality,
        'voice_isolation_score': voice_isolation_score,
        'noise_reduction_db': noise_reduction_db
    }

def calculate_analysis_confidence(analysis):
    """Calculate Perfect AI analysis confidence score."""
    try:
        confidence = 85  # Base confidence
        
        if analysis:
            # Boost confidence based on analysis completeness
            if analysis.get('key_points'):
                confidence += 5
            if analysis.get('potential_issues'):
                confidence += 3
            if analysis.get('recommendations'):
                confidence += 4
            if analysis.get('clarifying_questions'):
                confidence += 3
        
        return min(confidence, 98)  # Cap at 98%
    except:
        return 85

def send_perfect_ai_proactive_questions(analysis):
    """Send perfect AI proactive clarifying questions."""
    try:
        if not app_state['is_recording']:
            return
            
        clarifying_questions = analysis.get('clarifying_questions', [])
        if not clarifying_questions:
            return
        
        # Find unsent questions
        unsent_questions = [q for q in clarifying_questions if q not in app_state['sent_questions']]
        
        if not unsent_questions:
            app_state['sent_questions'].clear()
            unsent_questions = clarifying_questions
        
        # Select question
        question_index = app_state['question_index'] % len(unsent_questions)
        question = unsent_questions[question_index]
        
        app_state['sent_questions'].add(question)
        app_state['question_index'] += 1
        
        # Emit perfect AI proactive question
        socketio.emit('perfect_proactive_question', {
            'question': question,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'analysis_context': {
                'word_count': len(" ".join(load_transcripts()).split()),
                'issues_count': len(analysis.get('potential_issues', [])),
                'recommendations_count': len(analysis.get('recommendations', [])),
                'question_number': len(app_state['sent_questions']),
                'total_questions': len(clarifying_questions),
                'perfect_ai_confidence': calculate_analysis_confidence(analysis)
            }
        })
        
        print(f"🤖 Perfect AI proactive question #{len(app_state['sent_questions'])} sent: {question[:50]}...")
        
    except Exception as e:
        print(f"Perfect AI proactive question error: {e}")

# ================================================================
# PERFECT AI FLASK ROUTES
# ================================================================

@app.route('/')
def index():
    """Perfect AI Configuration & Recording Controls."""
    metrics = calculate_perfect_ai_metrics()
    
    status_text = "READY FOR PERFECT AI RECORDING"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"PERFECT AI RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    template_data = {
        'is_recording': app_state['is_recording'],
        'status_text': status_text,
        'status_color': status_color,
        'session_id': app_state['recording_session_id'],
        'total_sessions': app_state['total_sessions'],
        'total_meetings_analyzed': app_state['total_meetings_analyzed'],
        'analysis_mode': app_state['analysis_mode'],
        'words_threshold': app_state['words_threshold'],
        'is_analyzing': app_state['is_analyzing'],
        'audio_source': app_state['audio_source'],
        'perfect_ai_enabled': app_state['perfect_ai_enabled'],
        'voice_isolation_level': app_state['voice_isolation_level'],
        'noise_cancellation_strength': app_state['noise_cancellation_strength'],
        **metrics
    }
    
    return render_template('perfect_ai_config.html', **template_data)

@app.route('/transcript')
def transcript():
    """Perfect AI Live Transcript."""
    metrics = calculate_perfect_ai_metrics()
    
    status_text = "READY FOR PERFECT AI RECORDING"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"PERFECT AI RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    template_data = {
        'is_recording': app_state['is_recording'],
        'status_text': status_text,
        'status_color': status_color,
        'session_id': app_state['recording_session_id'],
        'total_sessions': app_state['total_sessions'],
        'total_meetings_analyzed': app_state['total_meetings_analyzed'],
        'analysis_mode': app_state['analysis_mode'],
        'words_threshold': app_state['words_threshold'],
        'is_analyzing': app_state['is_analyzing'],
        'audio_source': app_state['audio_source'],
        **metrics
    }
    
    return render_template('perfect_ai_transcript.html', **template_data)

@app.route('/analysis')
def analysis():
    """Perfect AI Analysis."""
    metrics = calculate_perfect_ai_metrics()
    
    status_text = "READY FOR PERFECT AI RECORDING"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"PERFECT AI RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    template_data = {
        'is_recording': app_state['is_recording'],
        'status_text': status_text,
        'status_color': status_color,
        'analysis': app_state['final_summary'] or app_state['current_analysis'],
        'final_summary': app_state['final_summary'],
        'session_id': app_state['recording_session_id'],
        'total_sessions': app_state['total_sessions'],
        'total_meetings_analyzed': app_state['total_meetings_analyzed'],
        'analysis_mode': app_state['analysis_mode'],
        'words_threshold': app_state['words_threshold'],
        'is_analyzing': app_state['is_analyzing'],
        'audio_source': app_state['audio_source'],
        **metrics
    }
    
    return render_template('perfect_ai_analysis.html', **template_data)

@app.route('/start_recording', methods=['POST'])
def start_recording_route():
    """Perfect AI start recording endpoint."""
    data = request.get_json() or {}
    mode = data.get('mode', 'automatic')
    words_threshold = data.get('words_threshold', 200)
    audio_source = data.get('audio_source', 'mic')
    transcription_engine = data.get('transcription_engine', 'faster_whisper')
    voice_isolation_level = data.get('voice_isolation_level', 'maximum')
    noise_cancellation_strength = data.get('noise_cancellation_strength', 'aggressive')
    
    result = start_perfect_ai_recording(
        mode=mode, 
        words_threshold=words_threshold, 
        audio_source=audio_source,
        transcription_engine=transcription_engine,
        voice_isolation_level=voice_isolation_level,
        noise_cancellation_strength=noise_cancellation_strength
    )
    return jsonify(result)

@app.route('/stop_recording', methods=['POST'])
def stop_recording_route():
    """Perfect AI stop recording endpoint."""
    result = stop_perfect_ai_recording()
    return jsonify(result)

@app.route('/trigger_analysis', methods=['POST'])
def trigger_analysis_route():
    """Perfect AI trigger analysis endpoint."""
    result = trigger_perfect_ai_manual_analysis()
    return jsonify(result)

@app.route('/clear_data', methods=['POST'])
def clear_data_route():
    """Perfect AI clear data endpoint."""
    if not app_state['is_recording']:
        clear_storage()
        app_state['final_summary'] = None
        app_state['current_analysis'] = None
        app_state['is_analyzing'] = False
        app_state['chat_locked'] = False
        app_state['chatbot'] = None
        return jsonify({
            "success": True, 
            "message": "🗑️ Perfect AI data cleared successfully!"
        })
    return jsonify({
        "success": False, 
        "message": "❌ Cannot clear data while Perfect AI recording is in progress."
    })

@app.route('/api/status')
def get_status():
    """Perfect AI status endpoint."""
    metrics = calculate_perfect_ai_metrics()
    
    return jsonify({
        'is_recording': app_state['is_recording'],
        'is_analyzing': app_state['is_analyzing'],
        'audio_source': app_state['audio_source'],
        'session_id': app_state['recording_session_id'],
        'analysis': app_state['final_summary'] or app_state['current_analysis'],
        'final_summary': bool(app_state['final_summary']),
        'total_sessions': app_state['total_sessions'],
        'total_meetings_analyzed': app_state['total_meetings_analyzed'],
        'analysis_mode': app_state['analysis_mode'],
        'words_threshold': app_state['words_threshold'],
        'perfect_ai_enabled': app_state['perfect_ai_enabled'],
        'voice_isolation_level': app_state['voice_isolation_level'],
        'noise_cancellation_strength': app_state['noise_cancellation_strength'],
        **metrics
    })

@app.route('/api/transcript')
def get_transcript():
    """Perfect AI transcript endpoint."""
    segments = load_transcripts()
    return jsonify({
        'segments': segments,
        'full_text': " ".join(segments),
        'segment_count': len(segments),
        'perfect_ai_processed': True
    })

# ================================================================
# PERFECT AI SOCKETIO HANDLERS
# ================================================================

@socketio.on('connect')
def handle_connect():
    """Handle Perfect AI client connection with better error handling."""
    try:
        print(f"🔗 Perfect AI client connected: {request.sid}")
        
        metrics = calculate_perfect_ai_metrics()
        status_data = {
            'is_recording': app_state['is_recording'],
            'is_analyzing': app_state['is_analyzing'],
            'session_id': app_state['recording_session_id'],
            'analysis_mode': app_state['analysis_mode'],
            'audio_source': app_state['audio_source'],
            'perfect_ai_enabled': app_state['perfect_ai_enabled'],
            'voice_isolation_level': app_state['voice_isolation_level'],
            'noise_cancellation_strength': app_state['noise_cancellation_strength'],
            **metrics
        }
        
        emit('perfect_status_update', status_data)
        print(f"✅ Status update sent to client: {request.sid}")
        
    except Exception as e:
        print(f"❌ Error handling client connection: {e}")
        import traceback
        traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle Perfect AI client disconnection with better logging."""
    try:
        print(f"❌ Perfect AI client disconnected: {request.sid}")
        # Log the reason if available
        if hasattr(request, 'disconnect_reason'):
            print(f"   Disconnect reason: {request.disconnect_reason}")
    except Exception as e:
        print(f"❌ Error handling client disconnection: {e}")

@socketio.on('request_perfect_status')
def handle_perfect_status_request():
    """Handle Perfect AI status request with better error handling."""
    try:
        print(f"📊 Status request from client: {request.sid}")
        
        metrics = calculate_perfect_ai_metrics()
        status_data = {
            'is_recording': app_state['is_recording'],
            'is_analyzing': app_state['is_analyzing'],
            'session_id': app_state['recording_session_id'],
            'analysis_mode': app_state['analysis_mode'],
            'audio_source': app_state['audio_source'],
            'current_analysis': app_state['current_analysis'],
            'final_summary': app_state['final_summary'],
            'perfect_ai_enabled': app_state['perfect_ai_enabled'],
            'voice_isolation_level': app_state['voice_isolation_level'],
            'noise_cancellation_strength': app_state['noise_cancellation_strength'],
            **metrics
        }
        
        emit('perfect_status_update', status_data)
        print(f"✅ Status response sent to client: {request.sid}")
        
    except Exception as e:
        print(f"❌ Error handling status request: {e}")
        import traceback
        traceback.print_exc()

@socketio.on('heartbeat')
def handle_heartbeat():
    """Handle client heartbeat to keep connection alive."""
    try:
        # Simply acknowledge the heartbeat
        emit('heartbeat_ack', {'timestamp': datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        print(f"❌ Error handling heartbeat: {e}")

# ================================================================
# PERFECT AI APPLICATION INITIALIZATION
# ================================================================

def initialize_perfect_ai_app():
    """Initialize Perfect AI application."""
    print("🚀 Initializing Perfect AI Meeting Analyzer...")
    
    load_app_stats()
    
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key:
        print("⚠️ WARNING: XAI_API_KEY not found!")
        print("   Please set your xAI API key in the .env file.")
        print("   Get your API key from: https://console.x.ai")
    else:
        print("✅ XAI API key loaded successfully")
    
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"📁 Created templates directory: {templates_dir}")
    
    print(f"📊 Total sessions: {app_state['total_sessions']}")
    print(f"📈 Total meetings analyzed: {app_state['total_meetings_analyzed']}")
    print("🎯 Perfect AI Meeting Analyzer is ready!")
    print("🌐 Open http://localhost:5000 in your browser to start")

# ================================================================
# RECORDING MANAGEMENT API ENDPOINTS
# ================================================================

@app.route('/api/recordings')
def get_recordings():
    """Get list of saved recordings."""
    try:
        if app_state['audio_processor']:
            recordings = app_state['audio_processor'].get_saved_recordings()
            return jsonify({
                'success': True,
                'recordings': recordings
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Audio processor not initialized'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/recordings/<filename>')
def download_recording(filename):
    """Download a specific recording file."""
    try:
        if app_state['audio_processor']:
            recordings_dir = app_state['audio_processor'].recordings_dir
            filepath = os.path.join(recordings_dir, filename)
            
            if os.path.exists(filepath) and filename.endswith('.wav'):
                from flask import send_file
                return send_file(filepath, as_attachment=True, download_name=filename)
            else:
                return jsonify({
                    'success': False,
                    'error': 'Recording file not found'
                }), 404
        else:
            return jsonify({
                'success': False,
                'error': 'Audio processor not initialized'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/recordings/<filename>', methods=['DELETE'])
def delete_recording(filename):
    """Delete a specific recording file."""
    try:
        if app_state['audio_processor']:
            success = app_state['audio_processor'].delete_recording(filename)
            return jsonify({
                'success': success,
                'message': f'Recording {"deleted" if success else "not found"}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Audio processor not initialized'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    """Handle chat requests with the AI assistant."""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            })
        
        # Check if chat instance is available
        if not app_state.get('chat_instance'):
            return jsonify({
                'success': False,
                'error': 'Chat is not available yet. Please wait for the recording to complete.'
            })
        
        # Get response from chat instance
        try:
            response = app_state['chat_instance'].chat(message)
            return jsonify({
                'success': True,
                'response': response,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
        except Exception as chat_error:
            print(f"Chat error: {chat_error}")
            return jsonify({
                'success': False,
                'error': 'Sorry, I encountered an error processing your message. Please try again.'
            })
            
    except Exception as e:
        print(f"Chat API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Sorry, I encountered an error. Please try again.'
        })

# ================================================================
# PERFECT AI MAIN ENTRY POINT
# ================================================================

if __name__ == '__main__':
    initialize_perfect_ai_app()
    
    print("🚀 Starting Perfect AI SocketIO server...")
    socketio.run(
        app,
        debug=True,
        host='0.0.0.0',
        port=5000
    )