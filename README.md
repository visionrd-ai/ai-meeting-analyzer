# 🎯 Perfect AI Meeting Analyzer

Advanced AI-powered meeting analysis with voice recording, real-time transcription, and intelligent insights.

## ✨ Features

- 🎤 **High-Quality Voice Recording** - Crystal clear audio capture
- 🤖 **AI Transcription** - Multiple engines (Whisper, AssemblyAI, Deepgram)
- 📊 **Intelligent Analysis** - AI-powered meeting insights and summaries
- 👥 **User Authentication** - Secure login with separated user data
- 💬 **AI Chat Assistant** - Ask questions about your meetings
- 📁 **Recording Management** - Automatic file saving and organization
- 🌐 **Real-time Updates** - Live transcription and analysis
- 📱 **Responsive Design** - Works on desktop and mobile

## 🚀 Quick Start

### Option 1: Automated Installation (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd perfect-ai-meeting-analyzer

# Run the installation script
python install.py

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Set up HTTPS for microphone access
python setup_https.py

# Start the application
python app_perfect_ai.py

# Open https://localhost:5000 in your browser
```

### Option 2: Manual Installation

#### Prerequisites

**Python 3.8+** is required.

**System Dependencies:**

- **Windows:** Microsoft Visual C++ Build Tools
- **macOS:** `brew install portaudio`
- **Ubuntu/Debian:** `sudo apt-get install build-essential portaudio19-dev python3-dev ffmpeg`
- **CentOS/RHEL:** `sudo yum groupinstall "Development Tools" && sudo yum install portaudio-devel python3-devel ffmpeg`

#### Installation Steps

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   
   # Activate it
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   # Full installation
   pip install -r requirements.txt
   
   # OR minimal installation
   pip install -r requirements-minimal.txt
   ```

3. **Configure environment:**
   ```bash
   # Copy and edit environment file
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application:**
   ```bash
   python app_perfect_ai.py
   ```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///perfect_ai.db

# Optional API Keys
OPENAI_API_KEY=your-openai-key
XAI_API_KEY=your-xai-key
ASSEMBLYAI_API_KEY=your-assemblyai-key
DEEPGRAM_API_KEY=your-deepgram-key

# App Settings
FLASK_ENV=development
FLASK_DEBUG=True
```

### Default Login

- **Username:** `admin`
- **Password:** `admin123`

*Change this immediately in production!*

## 📋 Requirements Files

- `requirements.txt` - Complete installation with all features
- `requirements-minimal.txt` - Basic functionality only
- `requirements-dev.txt` - Development tools and testing
- `requirements-prod.txt` - Production deployment

## 🎯 Usage

1. **Sign Up/Login** - Create your account or use default admin
2. **Configure Settings** - Choose transcription engine and analysis mode
3. **Start Recording** - Click "Start AI Recording" 
4. **Real-time Transcription** - View live transcript on the transcript page
5. **AI Analysis** - Get intelligent insights and summaries
6. **Chat with AI** - Ask questions about your meeting
7. **Download Recordings** - Access your saved audio files

## 🔒 HTTPS Setup (Required for Microphone Access)

✅ **Your HTTPS server is working!** It's running on:
- `https://localhost:5000`
- `https://127.0.0.1:5000` 
- `https://192.168.100.175:5000`

### 🚨 Security Warnings are Normal!
When you see scary browser warnings like:
- **"Attackers might be trying to steal your information"**
- **"net::ERR_CERT_AUTHORITY_INVALID"** 
- **"This server couldn't prove that it's [IP address]"**

**Don't panic!** This is completely normal for self-signed certificates. Your connection is actually encrypted and secure - browsers just don't recognize our "homemade" certificate.

### Quick Access
```bash
# Start the server
python app_perfect_ai.py

# Open in browser (Windows)
open_app.bat

# Or manually open: https://localhost:5000
```

### Browser Setup
1. **Open:** `https://localhost:5000` (note the **https**)
2. **Accept security warning:** Click "Advanced" → "Proceed to localhost"
3. **Allow microphone:** Click "Allow" when prompted

### ✅ Success Indicators
- URL shows `https://localhost:5000`
- "🔒 Secure HTTPS connection active" message appears
- "🎤 Microphone access granted" status shows
- Recording button is enabled

### 📚 Detailed Guides
- [QUICK_START.md](QUICK_START.md) - Simple setup instructions
- [BROWSER_SETUP_GUIDE.md](BROWSER_SETUP_GUIDE.md) - Browser-specific help
- [HTTPS_SETUP.md](HTTPS_SETUP.md) - Technical details

## 🏗️ Architecture

```
Perfect AI Meeting Analyzer/
├── app_perfect_ai.py          # Main Flask application
├── models.py                  # Database models
├── auth.py                    # Authentication routes
├── audio_processor_perfect_ai.py  # Audio processing engine
├── summarizer.py              # AI analysis engine
├── grok_chat.py              # AI chat functionality
├── templates/                 # HTML templates
│   ├── auth/                 # Authentication pages
│   ├── perfect_ai_config.html    # Main configuration
│   ├── perfect_ai_transcript.html # Live transcript
│   └── perfect_ai_analysis.html  # AI analysis
├── recordings/               # User audio files
│   └── user_*/              # User-specific directories
└── requirements*.txt         # Dependency files
```

## 🔒 Security Features

- **Password Hashing** - Secure Werkzeug password hashing
- **User Isolation** - Complete data separation between users
- **Session Management** - Flask-Login secure sessions
- **Input Validation** - Comprehensive form validation
- **CSRF Protection** - Built-in Flask security

## 🚀 Deployment

### Development
```bash
python app_perfect_ai.py
```

### Production
```bash
# Install production dependencies
pip install -r requirements-prod.txt

# Use Gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app_perfect_ai:app
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License.

## 🆘 Support

If you encounter issues:

1. Check the [troubleshooting guide](#troubleshooting)
2. Review system requirements
3. Ensure all dependencies are installed
4. Check the logs for error messages

## 🔧 Troubleshooting

### Common Issues

**Audio not working:**
- Check microphone permissions
- Verify audio device is connected
- Try different audio source settings

**Installation fails:**
- Ensure Python 3.8+ is installed
- Install system dependencies first
- Use virtual environment

**Database errors:**
- Check file permissions
- Ensure SQLite is available
- Try deleting and recreating database

**API errors:**
- Verify API keys in .env file
- Check internet connection
- Ensure API quotas aren't exceeded

## 🎉 Enjoy Perfect AI!

Transform your meetings with intelligent AI analysis and crystal-clear recordings!