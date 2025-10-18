AI IT Meeting Analyzer
Real-time meeting transcription and intelligent analysis using Faster-Whisper (local) and Grok AI.

Features:
Local real-time transcription with Faster-Whisper (no cloud costs, privacy-focused)
IT-focused analysis with Grok AI for technical issue identification

Two analysis modes:
Automatic: Analysis triggers after specified word count (200/300/500/1000 or custom)
Manual: On-demand analysis with "Analyze Now" button

Best practice recommendations for cloud infrastructure, security, and DevOps
Clean web interface with live transcript and AI analysis views
Persistent storage across sessions

System Requirements

Python 3.8 or higher
4GB+ RAM (8GB recommended)
Microphone for audio input
Internet connection for Grok API

Installation
Step 1: Install System Dependencies
macOS:
bashbrew install portaudio
Ubuntu/Debian:
bashsudo apt-get update
sudo apt-get install portaudio19-dev python3-pyaudio
Windows:
PyAudio will be installed via pip. No additional system packages required.
Step 2: Install Python Dependencies
bashpip install -r requirements.txt
Step 3: Configure API Keys
Create a .env file in the project root:
bashXAI_API_KEY=xai-your-api-key-here
Get your xAI API key from https://console.x.ai

Usage
Web Interface
bashpython app.py
Open http://localhost:5000 in your browser.

Analysis Modes
Automatic Mode:
Select word count threshold (200, 300, 500, 1000, or custom)
Analysis automatically triggers when threshold is reached
Continues analyzing throughout the meeting

Manual Mode:
Click "Analyze Now" button whenever you want analysis
Full control over when analysis occurs
Analyzes all accumulated transcript content

Recording Workflow

Select analysis mode and configure word threshold (if automatic)
Click "Start Recording"
Speak clearly into your microphone
View live transcript in real-time
For manual mode: Click "Analyze Now" when ready
For automatic mode: Analysis triggers automatically at word threshold
Click "Stop Recording" when finished
View final comprehensive analysis

Configuration
Audio Settings
Edit audio_processor_faster_whisper.py:
pythonCHUNK_DURATION_SECONDS = 2    # Process audio every 2 seconds
OVERLAP_SECONDS = 1           # 1-second overlap for continuity
WHISPER_MODEL_SIZE = "tiny"   # Options: tiny, base, small, medium, large
DEVICE = "cpu"                # Use "cuda" for GPU acceleration
Analysis Settings
Edit summarizer.py:
pythonDEFAULT_WORDS_PER_ANALYSIS = 200        # Default word threshold
DEFAULT_WORDS_PER_ROLLING_SUMMARY = 300 # Rolling summary interval
MAX_PRIOR_SUMMARY_WORDS = 1000          # Context window size
GROK_MODEL = "grok-4-fast-reasoning"    # Grok model
```

## What the System Analyzes

**Technical Overview:** Summary of technical discussion

**Potential Issues:** Security risks, misconfigurations, architectural problems

**Recommendations:** Best practices and specific solutions

**Clarifying Questions:** Probes for missing details

**Action Items:** Actionable tasks from the discussion

## IT Domains Covered

- Cloud Services (Azure, AWS, GCP)
- Kubernetes and Container Orchestration
- Infrastructure and Networking
- DevOps and CI/CD
- Cybersecurity and Compliance
- Software Architecture
- Database Design
- System Administration

## API Costs

**Transcription (Faster-Whisper):**
- Cost: Free (runs locally)
- No internet required
- Audio never leaves your device

**Analysis (Grok API):**
- Model: grok-4-fast-reasoning
- Cost: ~$0.0002 per 1,000 tokens
- Average 10-minute meeting: ~$0.002
- Free credits: $25 (10,000+ meetings)

## Troubleshooting

**Microphone Issues:**
1. Check no other application is using the microphone
2. Grant microphone permissions to your terminal
3. Verify microphone is working system-wide

**No Transcripts Appearing:**
1. Speak clearly and at normal volume
2. Check audio levels are adequate
3. Test audio processor: `python audio_processor_faster_whisper.py`

**API Connection Issues:**
1. Verify XAI_API_KEY is set correctly in .env
2. Check internet connection
3. Verify API key at https://console.x.ai

**Analysis Taking Too Long:**
1. Check internet connection stability
2. For large transcripts, analysis may take 5-15 seconds
3. Use automatic mode with lower word thresholds for faster updates

**Tab Switching Back:**
The system now maintains your current tab during page refreshes using browser storage.

## File Structure
```
project/
├── app.py                              # Flask backend
├── templates/
│   └── index_obaid.html                      # Web interface
├── audio_processor_faster_whisper.py   # Audio capture and transcription
├── summarizer.py                       # Grok AI analysis
├── requirements.txt                    # Python dependencies
├── .env                                # API keys (create this)
└── README.md                           # This file
```

## Requirements
```
Flask==3.0.0
pyaudio==0.2.14
numpy==1.26.4
faster-whisper==1.0.2
openai==1.40.0
python-dotenv==1.0.1
Privacy and Security

Audio transcription is entirely local
Audio data never leaves your device
Only transcript text is sent to Grok API
No audio recordings stored
API keys stored in .env (add to .gitignore)


Terminal Interface (Alternative)
For command-line usage:
bashpython terminal_meeting_analyzer.py
Provides colored terminal output without browser interface.
Support

Check troubleshooting section
Verify all dependencies installed
Test components individually
Check Grok API status at https://status.x.ai