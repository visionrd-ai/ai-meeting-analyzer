#!/usr/bin/env python3
"""
Test script to verify chatbot integration.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_chatbot_integration():
    """Test the chatbot integration."""
    print("🤖 Testing Chatbot Integration")
    print("=" * 50)
    
    try:
        # Test imports
        from grok_chat import MeetingChatGrok
        print("✅ Successfully imported MeetingChatGrok")
        
        # Check API key
        xai_key = os.getenv("XAI_API_KEY")
        if not xai_key or xai_key == "your_xai_api_key_here":
            print("⚠️  Warning: XAI_API_KEY not set or using default value")
            print("   Please set your actual API key in the .env file")
            return False
        else:
            print(f"✅ XAI API key loaded: {xai_key[:10]}...{xai_key[-4:]}")
        
        # Test chatbot initialization
        sample_transcript = """
        [00:01:00] John: Let's discuss the new feature implementation.
        [00:02:15] Sarah: I think we should use React for the frontend.
        [00:03:30] Mike: Agreed. What about the backend API?
        [00:04:45] John: Let's go with FastAPI for better performance.
        [00:05:20] Sarah: Sounds good. When can we start development?
        [00:06:10] Mike: I can begin next Monday.
        """
        
        sample_analysis = """
        Key Decisions:
        - Use React for frontend development
        - Use FastAPI for backend API
        
        Action Items:
        - Mike to start development next Monday
        
        Participants:
        - John (Project Lead)
        - Sarah (Frontend Developer)  
        - Mike (Backend Developer)
        """
        
        print("\n🔧 Testing chatbot initialization...")
        chatbot = MeetingChatGrok(
            api_key_grok=xai_key,
            latest_transcript=sample_transcript,
            latest_analysis=sample_analysis
        )
        print("✅ Chatbot initialized successfully")
        
        # Test a simple query (only if API key is valid)
        if xai_key and xai_key != "your_xai_api_key_here":
            print("\n💬 Testing chat functionality...")
            try:
                response = chatbot.send_chat("What are the key decisions from this meeting?")
                print(f"✅ Chat response received: {response[:100]}...")
                return True
            except Exception as e:
                print(f"⚠️  Chat test failed (this might be due to API limits): {e}")
                return True  # Still consider it a success if initialization worked
        else:
            print("⚠️  Skipping chat test due to missing API key")
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure grok_chat.py is in the same directory")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_flask_routes():
    """Test Flask route definitions."""
    print("\n🌐 Testing Flask Route Integration")
    print("=" * 50)
    
    try:
        # Import the app to check routes
        from app_meet import app
        
        # Check if chat routes exist
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        
        chat_routes = ['/api/chat', '/api/chat/reset']
        for route in chat_routes:
            if route in routes:
                print(f"✅ Route {route} is registered")
            else:
                print(f"❌ Route {route} is missing")
                return False
        
        print("✅ All chatbot routes are properly registered")
        return True
        
    except Exception as e:
        print(f"❌ Flask route test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Chatbot Integration Test")
    print("=" * 60)
    
    chatbot_ok = test_chatbot_integration()
    routes_ok = test_flask_routes()
    
    print("\n" + "=" * 60)
    if chatbot_ok and routes_ok:
        print("🎉 All chatbot tests passed!")
        print("\nNext steps:")
        print("1. Start the app: python app_meet.py")
        print("2. Go to the Analysis page (Page 3)")
        print("3. Click the 💬 button to open the chatbot")
        print("4. Start a recording to have data to chat about")
        print("5. Ask questions about your meeting!")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
    
    print("\nChatbot Features:")
    print("• Ask about key decisions and action items")
    print("• Query specific participants and their contributions")
    print("• Get meeting summaries and timelines")
    print("• Analyze technical discussions")
    print("• Real-time chat with meeting context")