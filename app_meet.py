import warnings
warnings.filterwarnings('ignore')

import os
import time
import pickle
import tempfile
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from audio_processor_faster_whisper_meet import EnhancedAudioProcessor
from summarizer import MeetingSummarizer
import threading
from grok_chat import MeetingChatGrok

# Load environment variables from .env file
load_dotenv()

# ================================================================
# FLASK APPLICATION SETUP
# ================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize SocketIO for real-time updates with performance optimizations
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000,  # 1MB buffer for better performance
    logger=False,  # Disable logging for better performance
    engineio_logger=False
)

# Global application state
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
    'analysis_mode': 'automatic',  # 'automatic' or 'manual'
    'words_threshold': 200,  # Default word count for automatic mode
    'is_analyzing': False,  # Track if analysis is in progress
    'analysis_start_time': None,  # Track when analysis started
    'audio_source': 'mic',  # 'mic', 'system', or 'both'
    'transcription_engine': 'faster_whisper',  # 'faster_whisper' or 'assemblyai'
    'chatbot': None,  # Meeting chatbot instance
    'chat_locked': False,  # Chat is always available (removed lock system)
    'chat_history': [],  # For future chat features
    'first_recording_done': False,  # To track first recording completion
    'chat_instance': None,  # To hold MeetingChatGrok instance
    'sent_questions': set(),  # Track sent proactive questions to avoid duplicates
    'question_index': 0  # Index for rotating through questions
}

# ================================================================
# FILE STORAGE CONFIGURATION
# ================================================================

TEMP_DIR = tempfile.gettempdir()
TRANSCRIPT_FILE = os.path.join(TEMP_DIR, "meeting_transcripts.pkl")
METADATA_FILE = os.path.join(TEMP_DIR, "meeting_metadata.pkl")
STATS_FILE = os.path.join(TEMP_DIR, "app_stats.pkl")

# ================================================================
# DATA PERSISTENCE FUNCTIONS
# ================================================================

def save_transcripts(segments):
    """Save transcript segments to persistent storage."""
    try:
        with open(TRANSCRIPT_FILE, 'wb') as f:
            pickle.dump(segments, f)
        return True
    except Exception as e:
        print(f"Error saving transcripts: {e}")
        return False

def load_transcripts():
    """Load transcript segments from persistent storage."""
    try:
        if os.path.exists(TRANSCRIPT_FILE):
            with open(TRANSCRIPT_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading transcripts: {e}")
    return []

def save_metadata(data):
    """Save session metadata to persistent storage."""
    try:
        with open(METADATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        return True
    except Exception as e:
        print(f"Error saving metadata: {e}")
        return False

def load_metadata():
    """Load session metadata from persistent storage."""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading metadata: {e}")
    return {}

def save_app_stats():
    """Save application statistics."""
    try:
        stats = {
            'total_sessions': app_state['total_sessions'],
            'total_meetings_analyzed': app_state['total_meetings_analyzed'],
            'last_updated': datetime.now()
        }
        with open(STATS_FILE, 'wb') as f:
            pickle.dump(stats, f)
    except Exception as e:
        print(f"Error saving app stats: {e}")

def load_app_stats():
    """Load application statistics."""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'rb') as f:
                stats = pickle.load(f)
                app_state['total_sessions'] = stats.get('total_sessions', 0)
                app_state['total_meetings_analyzed'] = stats.get('total_meetings_analyzed', 0)
    except Exception as e:
        print(f"Error loading app stats: {e}")

def clear_storage():
    """Clear all persistent storage files."""
    for f in [TRANSCRIPT_FILE, METADATA_FILE]:
        if os.path.exists(f):
            os.remove(f)

# ================================================================
# CORE BUSINESS LOGIC
# ================================================================

def on_new_transcript(text: str, source_label: str = "Mic"):
    """
    Callback function for new transcript segments with performance optimization.
    
    Args:
        text: Transcribed text
        source_label: "Mic" or "System" indicating audio source
    """
    start_time = time.time()
    try:
        # Format transcript with source label for dual mode
        if app_state['audio_source'] == 'both':
            formatted_text = f"[{source_label}] {text}"
        else:
            formatted_text = text
        
        segments = load_transcripts()
        segments.append(formatted_text)
        save_transcripts(segments)
        
        # Calculate current metrics for real-time updates (optimized)
        metrics = calculate_metrics()
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        print(f"[{source_label}] {text[:50]}... (processed in {processing_time:.1f}ms)")
        
        # Emit real-time transcript update to all connected clients (optimized for speed)
        socketio.emit('transcript_update', {
            'new_text': formatted_text,
            'full_text': metrics['full_text'],
            'word_count': metrics['word_count'],
            'segments_count': metrics['segments_count'],
            'duration': metrics['duration'],
            'wpm': metrics['wpm'],
            'source_label': source_label,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })  # Remove broadcast parameter for compatibility
        
        # Trigger live analysis update (only for automatic mode)
        if app_state['is_recording'] and app_state['summarizer'] and app_state['analysis_mode'] == 'automatic':
            try:
                # Add transcript - will auto-analyze if threshold reached
                analysis = app_state['summarizer'].add_transcript(text, auto_analyze=True)
                if analysis:
                    app_state['current_analysis'] = analysis
                    print("✅ Automatic analysis updated")
                    
                    # Emit real-time analysis update (optimized for speed)
                    socketio.emit('analysis_update', {
                        'analysis': analysis,
                        'is_final': False,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    })
                    
                    # Send proactive clarifying questions during recording
                    send_proactive_clarifying_questions(analysis)
            except Exception as e:
                print(f"Error updating live analysis: {e}")
        elif app_state['is_recording'] and app_state['summarizer']:
            # Manual mode - just add transcript without analyzing
            try:
                app_state['summarizer'].add_transcript(text, auto_analyze=False)
                print("Transcript added (manual mode - no auto-analysis)")
            except Exception as e:
                print(f"Error adding transcript: {e}")
                
    except Exception as e:
        print(f"Error in transcript callback: {e}")
        import traceback
        traceback.print_exc()

def start_recording(mode='automatic', words_threshold=200, audio_source='mic', transcription_engine='faster_whisper'):
    """
    Start the recording session with audio processing and AI analysis.
    
    Args:
        mode: 'automatic' or 'manual' analysis mode
        words_threshold: Word count threshold for automatic analysis
        audio_source: 'mic', 'system', or 'both'
        transcription_engine: 'faster_whisper' or 'assemblyai'
    """
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key:
        return {
            "success": False, 
            "message": "Missing XAI_API_KEY! Please set your API key in the .env file."
        }
    
    try:
        # Clear previous session data
        clear_storage()
        
        # Chat is now always available (removed lock)
        app_state['chat_locked'] = False
        
        app_state['analysis_mode'] = mode
        app_state['words_threshold'] = words_threshold
        app_state['audio_source'] = audio_source
        app_state['transcription_engine'] = transcription_engine
        app_state['chat_history'] = []
        app_state['sent_questions'] = set()  # Reset sent questions for new session
        app_state['question_index'] = 0
        
        # Initialize AI components with appropriate settings
        print(f"Initializing AI components in {mode} mode with {audio_source} audio source...")
        
        if mode == 'automatic':
            # Automatic mode: set word threshold
            app_state['summarizer'] = MeetingSummarizer(xai_key, words_per_analysis=words_threshold)
            print(f"âœ“ Automatic mode: analysis every {words_threshold} words")
        else:
            # Manual mode: disable automatic analysis
            app_state['summarizer'] = MeetingSummarizer(xai_key, words_per_analysis=0)
            print(f"âœ“ Manual mode: on-demand analysis only")
        
        print(f"Initializing audio processor with {transcription_engine.upper()}...")
        app_state['audio_processor'] = EnhancedAudioProcessor(
            on_new_transcript,
            audio_source=audio_source,
            transcription_engine=transcription_engine
        )
        
        # Set session metadata
        app_state['start_time'] = datetime.now()
        app_state['recording_session_id'] = datetime.now().strftime("%Y%m%d_%H%M%S")
        app_state['is_analyzing'] = False
        
        # Save session metadata
        metadata = {
            'start_time': app_state['start_time'],
            'session_id': app_state['recording_session_id'],
            'xai_model': 'grok-4-fast-reasoning',
            'analysis_mode': mode,
            'words_threshold': words_threshold,
            'audio_source': audio_source,
            'transcription_engine': transcription_engine
        }
        save_metadata(metadata)
        
        # Start audio processing
        print("Starting audio recording...")
        app_state['audio_processor'].start_recording()
        
        # Check if recording actually started
        if not app_state['audio_processor'].is_recording:
            return {
                "success": False,
                "message": "Failed to start audio recording. Please check your microphone permissions."
            }
        
        app_state['is_recording'] = True
        
        # Update statistics
        app_state['total_sessions'] += 1
        save_app_stats()
        
        mode_desc = f"every {words_threshold} words" if mode == 'automatic' else "on-demand"
        print("âœ“ Recording started successfully!")
        return {
            "success": True, 
            "message": f"Recording started with {transcription_engine.replace('_', '-').title()} in {mode.upper()} mode ({mode_desc})!"
        }
        
    except Exception as e:
        print(f"Error starting recording: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False, 
            "message": f"Error starting recording: {str(e)}"
        }

def stop_recording():
    """Stop the recording session and generate final analysis."""
    try:
        # Stop audio processing
        if app_state['audio_processor']:
            app_state['audio_processor'].stop_recording()
        
        # Mark as analyzing
        app_state['is_analyzing'] = True
        app_state['analysis_start_time'] = datetime.now()
        
        # Emit recording stopped event
        socketio.emit('recording_stopped', {
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        # Emit final analysis start event
        socketio.emit('final_analysis_start', {
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        # Allow time for final processing
        time.sleep(2)
        
        # Get all transcript segments
        segments = load_transcripts()

        if len(segments) == 0:
            app_state['is_recording'] = False
            app_state['is_analyzing'] = False
            return {
                "success": False, 
                "message": "No transcripts found! Please ensure you spoke during the recording."
            }
        
        # Generate final analysis in background thread
        def generate_final_analysis():
            try:
                xai_key = os.getenv("XAI_API_KEY")
                if xai_key:
                    fresh_summarizer = MeetingSummarizer(xai_key)
                    for segment in segments:
                        fresh_summarizer.add_transcript(segment, auto_analyze=False)
                    app_state['final_summary'] = fresh_summarizer.get_final_summary()
                    full_transcript = " ".join(segments)
                    if app_state['first_recording_done']:
                        if not app_state['chat_instance']:
                            app_state['chat_instance'] = MeetingChatGrok(xai_key, full_transcript, app_state['final_summary'])
                        else:
                            app_state['chat_instance'].reset_chat(full_transcript, app_state['final_summary'])
                    else:
                        app_state['first_recording_done'] = True
                    print("✅ Final summary generated")
                    
                    # Chat remains unlocked (removed lock system)
                    app_state['chat_locked'] = False
                    
                    # Emit final analysis complete event
                    socketio.emit('final_analysis_complete', {
                        'analysis': app_state['final_summary'],
                        'is_final': True,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    })
                    
                    # Emit chat unlock event
                    socketio.emit('chat_unlocked', {
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'message': 'Chat is now available! Ask me about your meeting.'
                    })
                else:
                    print("No API key for final summary")
            except Exception as e:
                print(f"Error generating final summary: {e}")
                app_state['first_recording_done'] = False
                import traceback
                traceback.print_exc()
            finally:
                app_state['is_analyzing'] = False
                app_state['is_recording'] = False
                app_state['total_meetings_analyzed'] += 1
                save_app_stats()
                
                # Emit session complete event
                socketio.emit('session_complete', {
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'total_meetings_analyzed': app_state['total_meetings_analyzed']
                })
        
        # Start analysis in background
        thread = threading.Thread(target=generate_final_analysis, daemon=True)
        thread.start()
        
        return {
            "success": True, 
            "message": "Recording stopped. Generating final analysis..."
        }
        
    except Exception as e:
        app_state['is_recording'] = False
        app_state['is_analyzing'] = False
        return {
            "success": False, 
            "message": f" Error stopping recording: {str(e)}"
        }

def trigger_manual_analysis():
    """Trigger on-demand analysis (for manual mode)."""
    if not app_state['is_recording'] or not app_state['summarizer']:
        return {
            "success": False,
            "message": "No active recording session!"
        }
    
    if app_state['is_analyzing']:
        return {
            "success": False,
            "message": " Analysis already in progress. Please wait..."
        }
    
    segments = load_transcripts()
    if len(segments) == 0:
        return {
            "success": False,
            "message": " No transcript available yet! Start speaking."
        }
    
    # Check word count
    word_count = app_state['summarizer'].word_count
    if word_count < 10:
        return {
            "success": False,
            "message": f" Only {word_count} words transcribed. Speak more for better analysis."
        }
    
    # Mark as analyzing
    app_state['is_analyzing'] = True
    app_state['analysis_start_time'] = datetime.now()
    
    # Emit analysis start event
    socketio.emit('analysis_start', {
        'word_count': word_count,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })
    
    # Perform analysis in background thread
    def perform_analysis():
        try:
            print(f"🎯 Manual analysis triggered ({word_count} words)")
            start_time = time.time()
            
            # Use force_analysis which is optimized for comprehensive analysis
            analysis = app_state['summarizer'].force_analysis()
            
            elapsed = time.time() - start_time
            print(f"✅ Manual analysis complete in {elapsed:.2f} seconds")
            
            if analysis:
                app_state['current_analysis'] = analysis
                
                # Emit analysis complete event
                socketio.emit('analysis_complete', {
                    'analysis': analysis,
                    'is_final': False,
                    'generation_time': elapsed,
                    'timestamp': datetime.now().strftime("%H:%M:%S")
                })
                
                # Send proactive clarifying questions for manual analysis too
                send_proactive_clarifying_questions(analysis)
        except Exception as e:
            print(f"Error in manual analysis: {e}")
            import traceback
            traceback.print_exc()
        finally:
            app_state['is_analyzing'] = False
            
            # Emit analysis end event
            socketio.emit('analysis_end', {
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
    
    thread = threading.Thread(target=perform_analysis, daemon=True)
    thread.start()
    
    return {
        "success": True,
        "message": f"ðŸ§  Analyzing {word_count} words..."
    }

def calculate_metrics():
    """Calculate real-time metrics for the dashboard."""
    segments = load_transcripts()
    full_text = " ".join(segments)
    metadata = load_metadata()
    
    # Calculate duration
    duration = 0
    if metadata.get('start_time'):
        duration = (datetime.now() - metadata['start_time']).seconds
    
    # Calculate basic metrics
    word_count = len(full_text.split()) if full_text else 0
    wpm = round(word_count / (duration / 60)) if duration > 0 else 0
    
    # Calculate confidence
    confidence = min(95, 75 + (word_count // 10)) if word_count > 0 else 0
    
    # Calculate momentum
    momentum = min(100, word_count // 10) if word_count > 0 else 0
    
    # Calculate technical depth
    tech_keywords = ['cloud', 'aws', 'azure', 'kubernetes', 'docker', 'security', 'api', 'database', 
                    'server', 'network', 'infrastructure', 'devops', 'ci/cd', 'deployment']
    tech_mentions = sum(1 for word in full_text.lower().split() if word in tech_keywords)
    tech_depth = min(100, tech_mentions * 5) if full_text else 0
    
    # Calculate insights count
    insights = 0
    if app_state['current_analysis']:
        insights += len(app_state['current_analysis'].get('potential_issues', []))
        insights += len(app_state['current_analysis'].get('recommendations', []))
    
    return {
        'duration': duration,
        'word_count': word_count,
        'wpm': wpm,
        'confidence': confidence,
        'momentum': momentum,
        'tech_depth': tech_depth,
        'insights': insights,
        'segments_count': len(segments),
        'full_text': full_text
    }

def send_proactive_clarifying_questions(analysis):
    """Send proactive clarifying questions to the chatbot during recording."""
    try:
        if not app_state['is_recording']:
            return
            
        clarifying_questions = analysis.get('clarifying_questions', [])
        if not clarifying_questions:
            return
        
        # Find a question that hasn't been sent yet
        unsent_questions = [q for q in clarifying_questions if q not in app_state['sent_questions']]
        
        if not unsent_questions:
            # If all questions have been sent, reset and start over with new questions
            app_state['sent_questions'].clear()
            unsent_questions = clarifying_questions
        
        # Select question based on rotation index
        question_index = app_state['question_index'] % len(unsent_questions)
        question = unsent_questions[question_index]
        
        # Mark question as sent and update index
        app_state['sent_questions'].add(question)
        app_state['question_index'] += 1
        
        # Emit proactive question to frontend
        socketio.emit('proactive_question', {
            'question': question,
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'analysis_context': {
                'word_count': len(" ".join(load_transcripts()).split()),
                'issues_count': len(analysis.get('potential_issues', [])),
                'recommendations_count': len(analysis.get('recommendations', [])),
                'question_number': len(app_state['sent_questions']),
                'total_questions': len(clarifying_questions)
            }
        })
        
        print(f"🤖 Proactive question #{len(app_state['sent_questions'])} sent: {question[:50]}...")
        
    except Exception as e:
        print(f"Error sending proactive question: {e}")

def perform_chat(user_message: str) -> str:
    """Handle chat interactions (future feature)."""
    if not app_state['chat_instance']:
        return "Chat feature is not initialized yet."
    
    try:
        response = app_state['chat_instance'].send_chat(user_message)
        app_state['chat_history'].append({"user": user_message, "response": response})
        return response
    except Exception as e:
        print(f"Error in chat interaction: {e}")
        return "Error processing chat message."
# ================================================================
# FLASK ROUTES
# ================================================================

@app.route('/')
def index():
    """Page 1: Configuration & Recording Controls."""
    # Calculate current metrics
    metrics = calculate_metrics()
    
    # Determine status
    status_text = "READY TO RECORD"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    # Prepare template data
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
    
    return render_template('page1_config_controls.html', **template_data)

@app.route('/transcript')
def transcript():
    """Page 2: Live Transcript."""
    # Calculate current metrics
    metrics = calculate_metrics()
    
    # Determine status
    status_text = "READY TO RECORD"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    # Prepare template data
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
    
    return render_template('page2_live_transcript.html', **template_data)

@app.route('/analysis')
def analysis():
    """Page 3: AI Analysis."""
    # Calculate current metrics
    metrics = calculate_metrics()
    
    # Determine status
    status_text = "READY TO RECORD"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    # Prepare template data
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
    
    return render_template('page3_ai_analysis.html', **template_data)

@app.route('/old')
def old_interface():
    """Legacy combined interface (for backward compatibility)."""
    # Calculate current metrics
    metrics = calculate_metrics()
    
    # Determine status
    status_text = "READY TO RECORD"
    status_color = "#10B981"
    if app_state['is_recording']:
        mode_text = f"({app_state['analysis_mode'].upper()} MODE)"
        status_text = f"RECORDING IN PROGRESS {mode_text}"
        status_color = "#EF4444"
    
    # Prepare template data
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
    
    return render_template('index_obaid.html', **template_data)

@app.route('/start_recording', methods=['POST'])
def start_recording_route():
    """API endpoint to start recording."""
    # Get mode, threshold, audio source, and transcription engine from request
    data = request.get_json() or {}
    mode = data.get('mode', 'automatic')
    words_threshold = data.get('words_threshold', 200)
    audio_source = data.get('audio_source', 'mic')
    transcription_engine = data.get('transcription_engine', 'faster_whisper')
    
    result = start_recording(
        mode=mode, 
        words_threshold=words_threshold, 
        audio_source=audio_source,
        transcription_engine=transcription_engine
    )
    return jsonify(result)

@app.route('/stop_recording', methods=['POST'])
def stop_recording_route():
    """API endpoint to stop recording."""
    result = stop_recording()
    return jsonify(result)

@app.route('/trigger_analysis', methods=['POST'])
def trigger_analysis_route():
    """API endpoint to trigger manual analysis."""
    result = trigger_manual_analysis()
    return jsonify(result)

@app.route('/clear_data', methods=['POST'])
def clear_data_route():
    """API endpoint to clear all session data."""
    if not app_state['is_recording']:
        clear_storage()
        app_state['final_summary'] = None
        app_state['current_analysis'] = None
        app_state['is_analyzing'] = False
        app_state['chat_locked'] = False  # Chat remains available (removed lock)
        app_state['chatbot'] = None  # Reset chatbot instance
        return jsonify({
            "success": True, 
            "message": "ðŸ—‘ï¸ All data cleared successfully!"
        })
    return jsonify({
        "success": False, 
        "message": "âŒ Cannot clear data while recording is in progress."
    })

@app.route('/api/status')
def get_status():
    """API endpoint to get current status and metrics."""
    metrics = calculate_metrics()
    
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
        'audio_source': app_state['audio_source'],
        **metrics
    })

@app.route('/api/transcript')
def get_transcript():
    """API endpoint to get current transcript."""
    segments = load_transcripts()
    return jsonify({
        'segments': segments,
        'full_text': " ".join(segments),
        'segment_count': len(segments)
    })

@app.route('/export/summary')
def export_summary():
    """Export final summary as JSON."""
    if app_state['final_summary']:
        return jsonify({
            'session_id': app_state['recording_session_id'],
            'timestamp': datetime.now().isoformat(),
            'summary': app_state['final_summary'],
            'transcript': " ".join(load_transcripts()),
            'analysis_mode': app_state['analysis_mode'],
            'words_threshold': app_state['words_threshold']
        })
    return jsonify({'error': 'No summary available'}), 404

@app.route('/api/chat', methods=['POST'])
def chat_with_meeting():
    """Chat with the meeting using Grok AI."""
    try:
        # Chat is now always available (removed lock system)
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        # Get current transcript and analysis
        segments = load_transcripts()
        transcript_text = " ".join(segments) if segments else ""
        current_analysis = app_state.get('final_summary') or app_state.get('current_analysis')
        
        if not transcript_text and not current_analysis:
            # Provide a helpful response even without data
            return jsonify({
                'success': True,
                'response': "I'm ready to help! I don't have any meeting data yet, but you can start recording and I'll analyze your discussion in real-time. Once you have some transcript data, I can help you with insights, summaries, and answer questions about your meeting.",
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
        
        # Initialize or update chatbot
        xai_key = os.getenv("XAI_API_KEY")
        if not xai_key:
            return jsonify({
                'success': False,
                'error': 'XAI API key not configured'
            }), 500
        
        # Create or update chatbot instance
        if not app_state['chatbot']:
            app_state['chatbot'] = MeetingChatGrok(
                api_key_grok=xai_key,
                latest_transcript=transcript_text,
                latest_analysis=current_analysis if current_analysis else ""
            )
        else:
            # Update chatbot with latest data
            app_state['chatbot'].reset_chat(
                transcript=transcript_text,
                analysis=current_analysis if current_analysis else ""
            )
        
        # Get response from chatbot
        response = app_state['chatbot'].send_chat(user_message)
        
        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
    except Exception as e:
        print(f"Chat error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Chat error: {str(e)}'
        }), 500

@app.route('/api/chat/reset', methods=['POST'])
def reset_chat():
    """Reset the chat history."""
    try:
        if app_state['chatbot']:
            segments = load_transcripts()
            transcript_text = " ".join(segments) if segments else ""
            current_analysis = app_state.get('final_summary') or app_state.get('current_analysis')
            
            app_state['chatbot'].reset_chat(
                transcript=transcript_text,
                analysis=current_analysis if current_analysis else ""
            )
        
        return jsonify({
            'success': True,
            'message': 'Chat history reset successfully'
        })
        
    except Exception as e:
        print(f"Chat reset error: {e}")
        return jsonify({
            'success': False,
            'error': f'Reset error: {str(e)}'
        }), 500

@app.route('/api/chat/status')
def get_chat_status():
    """Get current chat lock status."""
    try:
        is_locked = False  # Chat is always available now
        is_recording = app_state.get('is_recording', False)
        has_data = bool(load_transcripts() or app_state.get('final_summary') or app_state.get('current_analysis'))
        
        reason = None
        if has_data:
            message = 'Chat is available! Ask me about your meeting.'
        else:
            message = 'Chat is available! Start recording to have data to discuss.'
        
        return jsonify({
            'locked': is_locked,
            'is_recording': is_recording,
            'has_data': has_data,
            'reason': reason,
            'message': message,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
    except Exception as e:
        print(f"Chat status error: {e}")
        return jsonify({
            'locked': True,
            'reason': 'error',
            'message': 'Unable to determine chat status',
            'error': str(e)
        }), 500



@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template('500.html'), 500

# ================================================================
# APPLICATION INITIALIZATION
# ================================================================

def initialize_app():
    """Initialize the application on startup."""
    print("Initializing AI IT Meeting Analyzer...")
    
    # Load application statistics
    load_app_stats()
    
    # Check for required API key
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key:
        print("WARNING: XAI_API_KEY not found in environment variables!")
        print("   Please set your xAI API key in the .env file.")
        print("   Get your API key from: https://console.x.ai")
    else:
        print("XAI API key loaded successfully")
    
    # Create templates directory if it doesn't exist
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"Created templates directory: {templates_dir}")
    
    print(f" Total sessions: {app_state['total_sessions']}")
    print(f"Total meetings analyzed: {app_state['total_meetings_analyzed']}")
    print("AI IT Meeting Analyzer is ready!")
    print("Open http://localhost:5000 in your browser to start")

# ================================================================
# MAIN APPLICATION ENTRY POINT
# ================================================================

# ================================================================
# SOCKETIO EVENT HANDLERS
# ================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"🔗 Client connected: {request.sid}")
    
    # Send current status to newly connected client
    metrics = calculate_metrics()
    emit('status_update', {
        'is_recording': app_state['is_recording'],
        'is_analyzing': app_state['is_analyzing'],
        'session_id': app_state['recording_session_id'],
        'analysis_mode': app_state['analysis_mode'],
        'audio_source': app_state['audio_source'],
        'chat_locked': app_state.get('chat_locked', True),
        **metrics
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"❌ Client disconnected: {request.sid}")

@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client."""
    metrics = calculate_metrics()
    emit('status_update', {
        'is_recording': app_state['is_recording'],
        'is_analyzing': app_state['is_analyzing'],
        'session_id': app_state['recording_session_id'],
        'analysis_mode': app_state['analysis_mode'],
        'audio_source': app_state['audio_source'],
        'current_analysis': app_state['current_analysis'],
        'final_summary': app_state['final_summary'],
        'chat_locked': app_state.get('chat_locked', True),
        **metrics
    })

# ================================================================
# MAIN APPLICATION ENTRY POINT
# ================================================================

if __name__ == '__main__':
    # Initialize the application
    initialize_app()
    
    # Run the SocketIO server
    print("🚀 Starting SocketIO server...")
    socketio.run(
        app,
        debug=True,
        host='0.0.0.0',
        port=5000,
       
    )