#!/usr/bin/env python3
"""
Test script to verify HTTPS setup is working correctly.
"""

import os
import sys
import ssl
import socket
from pathlib import Path

def test_ssl_certificates():
    """Test if SSL certificates exist and are valid."""
    cert_file = 'cert.pem'
    key_file = 'key.pem'
    
    print("🔍 Checking SSL certificates...")
    
    if not os.path.exists(cert_file):
        print(f"❌ Certificate file not found: {cert_file}")
        return False
    
    if not os.path.exists(key_file):
        print(f"❌ Private key file not found: {key_file}")
        return False
    
    try:
        # Test loading the certificate
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        print("✅ SSL certificates are valid")
        return True
    except Exception as e:
        print(f"❌ SSL certificate error: {e}")
        return False

def test_port_availability():
    """Test if port 5000 is available."""
    print("🔍 Checking port 5000 availability...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("⚠️ Port 5000 is already in use")
            return False
        else:
            print("✅ Port 5000 is available")
            return True
    except Exception as e:
        print(f"❌ Port check error: {e}")
        return False

def test_cryptography_package():
    """Test if cryptography package is available."""
    print("🔍 Checking cryptography package...")
    
    try:
        import cryptography
        print(f"✅ cryptography package available (version: {cryptography.__version__})")
        return True
    except ImportError:
        print("❌ cryptography package not found")
        print("   Install with: pip install cryptography>=41.0.0")
        return False

def test_flask_imports():
    """Test if Flask and required packages are available."""
    print("🔍 Checking Flask and dependencies...")
    
    try:
        import flask
        import flask_socketio
        import flask_login
        print("✅ Flask and dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing Flask dependency: {e}")
        return False

def main():
    """Run all tests."""
    print("🎯 Perfect AI HTTPS Test Suite")
    print("=" * 40)
    
    tests = [
        ("Cryptography Package", test_cryptography_package),
        ("Flask Dependencies", test_flask_imports),
        ("SSL Certificates", test_ssl_certificates),
        ("Port Availability", test_port_availability),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    print("=" * 40)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 All tests passed! HTTPS setup is ready.")
        print("🚀 You can now run: python app_perfect_ai.py")
        print("🌐 Then open: https://localhost:5000")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("💡 Try running: python setup_https.py")
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)