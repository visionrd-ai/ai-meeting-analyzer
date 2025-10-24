🎙️ AI IT Meeting Analyzer
<div align="center">
Real-time meeting transcription and intelligent IT analysis
Powered by Faster-Whisper (local) and Grok AI

🏢 Developed by VisionRD

🚀 Live Demo | 📖 Documentation | 🛠️ Installation
</div>
🎯 What's New - Multi-Source Audio Capture
🎵 Three Audio Source Modes
Mode	Description	Use Case
🎤 Microphone Only	Your voice only	Personal notes, solo recording
💻 System Audio Only Transcribing Google Meet/Zoom/Teams
📊 Both (Separate) Both sources simultaneously	Full meeting with speaker labels
🏷️ Smart Transcript Labeling
text
[Mic] I think we should migrate to Kubernetes
[System] That makes sense. What about the database?
[Mic] Let's use PostgreSQL on Azure
[System] Sounds good. I'll handle networking
🚀 Quick Start
bash
# Clone & setup
git clone --branch feat/meet https://github.com/visionrd-ai/ai-meeting-analyzer.git
cd ai-meeting-analyzer

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "XAI_API_KEY=xai-your-api-key-here" > .env

# Launch app
python app.py
🌐 Open: http://localhost:5000

🎯 Core Features
🔒 Privacy First
✅ 100% Local Transcription - Audio never leaves your device

✅ No Cloud Storage - Everything processed locally

✅ Secure Analysis - Only text sent to AI, never audio

🧠 AI-Powered Intelligence
✅ IT-Focused Analysis - Specialized for technical discussions

✅ Real-time Processing - Live transcription and analysis

✅ Smart Recommendations - Actionable insights and best practices

🎵 Audio Source Options
🎤 Microphone Only
Your voice only


💻 System Audio Only 
Captures computer audio output

Records colleagues from Google Meet/Zoom/Teams

Uses Windows WASAPI loopback

📊 Both (Separate) 
Captures BOTH sources simultaneously

Labels transcripts: [Mic] and [System]

Perfect for full meeting transcription

🛠️ System Audio Setup (Windows)
✅ Enable Stereo Mix (5 minutes)
Step 1: Open Sound Settings

Press Win + R

Type: mmsys.cpl

Press Enter

Step 2: Enable Stereo Mix

Go to "Recording" tab

Right-click in empty area → "Show Disabled Devices"

Look for "Stereo Mix" or "Wave Out Mix"

Right-click → Enable

Right-click → Set as Default Device

Click OK

🔄 Alternative: Download Driver
If Stereo Mix isn't available, download from: https://www.dell.com/support/home/en-pk/drivers/driversdetails?driverid=rr39g
🍎 macOS Users
⚠️ Mic works perfectly, System Audio needs setup

Mic Only: ✅ Works out of the box (no setup)
System Audio: Requires BlackHole installation (15 min)
See: "macOS Setup" section below for BlackHole instructions
Quick win: Start with Mic Only mode!

🐧 Linux Users
⚠️ Mic works perfectly, System Audio needs config

Mic Only: ✅ Works out of the box (no setup)
System Audio: Requires PulseAudio/PipeWire setup (30 min)
See: "Linux Setup" section below for audio configuration
Quick win: Start with Mic Only mode!

🌍 All Platforms
💡 Pro Tip: Microphone Only mode works everywhere without any setup. Perfect for personal meeting notes!
💡 How to Use
🎬 Simple Workflow
🎵 Select Audio Source

Choose between Microphone, System Audio, or Both

System Audio captures Google Meet/Zoom/Teams

🎙️ Start Recording

Click 🔴 Start Recording

Speak clearly or play meeting audio

👀 Monitor Transcript

Watch real-time transcription

See speaker labels in "Both" mode

🤖 Analyze

Click 🎯 Analyze Now or use automatic mode

View AI insights on analysis page

🎯 Pro Tips
💻 System Audio: Perfect for transcribing remote meetings

📊 Both Mode: Get complete meeting with speaker identification

🎤 Microphone Only: Best for personal notes and solo work

🔧 Setup: Enable Stereo Mix first for system audio capture

🔧 Requirements & Troubleshooting
🖥️ System Requirements
🐍 Python 3.8+

💾 4GB+ RAM (8GB recommended)

🎤 Microphone (for microphone modes)

🌐 Internet (for AI analysis only)


🎤 Common Audio Issues
System Audio Not Working?

✅ Enable Stereo Mix (see setup instructions above)

✅ Check audio permissions

✅ Ensure meeting audio is playing

✅ Test with YouTube video first

API Issues?

✅ Verify .env file contains XAI_API_KEY=your-key

✅ Check API status: status.x.ai

💰 Cost
🆓 Transcription - FREE
Local processing with Faster-Whisper

No limits, completely private

💸 AI Analysis - Ultra Low Cost
~$0.002 per 10-minute meeting

$25 free credits = 10,000+ meetings

📞 Support
📖 Documentation: Full Docs

🐛 Issues: GitHub Issues

🏢 Company: VisionRD

<div align="center">
🚀 Ready to transform your IT meetings?

⬇️ Clone Now | 🌟 Star on GitHub

Capture every voice in your meetings - yours and theirs

</div>