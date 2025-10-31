#!/usr/bin/env python3
"""
Troubleshooting script for Perfect AI connection issues.
"""

import socket
import ssl
import requests
import subprocess
import sys
from urllib3.exceptions import InsecureRequestWarning
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(InsecureRequestWarning)

def test_port_connection(host, port):
    """Test if we can connect to the port."""
    print(f"🔍 Testing connection to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is open on {host}")
            return True
        else:
            print(f"❌ Cannot connect to {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_https_response(url):
    """Test if we can get an HTTPS response."""
    print(f"🔍 Testing HTTPS response from {url}...")
    try:
        response = requests.get(url, verify=False, timeout=10)
        print(f"✅ HTTPS response received (Status: {response.status_code})")
        return True
    except requests.exceptions.SSLError as e:
        print(f"🔒 SSL Error (this might be normal): {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def check_certificate(host, port):
    """Check the SSL certificate."""
    print(f"🔍 Checking SSL certificate for {host}:{port}...")
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                print(f"✅ SSL certificate found")
                print(f"   Subject: {cert.get('subject', 'Unknown')}")
                print(f"   Issuer: {cert.get('issuer', 'Unknown')}")
                return True
    except Exception as e:
        print(f"❌ Certificate check failed: {e}")
        return False

def check_firewall_windows():
    """Check Windows firewall status."""
    print("🔍 Checking Windows Firewall...")
    try:
        result = subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles', 'state'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            if "ON" in result.stdout:
                print("⚠️ Windows Firewall is ON - this might block connections")
                print("   Consider adding an exception for port 5000")
            else:
                print("✅ Windows Firewall appears to be OFF")
        return True
    except Exception as e:
        print(f"❌ Could not check firewall status: {e}")
        return False

def suggest_solutions():
    """Provide solution suggestions."""
    print("\n" + "="*60)
    print("💡 SUGGESTED SOLUTIONS")
    print("="*60)
    
    print("\n1. 🌐 Try Different URLs:")
    print("   - https://localhost:5000")
    print("   - https://127.0.0.1:5000")
    print("   - http://localhost:5000 (as fallback)")
    
    print("\n2. 🔓 Browser Bypass Methods:")
    print("   - Type 'thisisunsafe' on the warning page")
    print("   - Try a different browser (Chrome, Firefox, Edge)")
    print("   - Enable chrome://flags/#allow-insecure-localhost")
    
    print("\n3. 🛡️ Security Software:")
    print("   - Temporarily disable antivirus")
    print("   - Add firewall exception for port 5000")
    print("   - Check if corporate firewall is blocking")
    
    print("\n4. 🔄 Server Restart:")
    print("   - Stop the server (Ctrl+C)")
    print("   - Run: python app_perfect_ai.py")
    print("   - Check console output for correct URLs")
    
    print("\n5. 🆘 Alternative Access:")
    print("   - Try HTTP instead: http://localhost:5000")
    print("   - Use incognito/private browsing mode")
    print("   - Clear browser cache and cookies")

def main():
    """Run all diagnostic tests."""
    print("🎯 Perfect AI Connection Troubleshooter")
    print("="*50)
    
    # Test different hosts and URLs
    hosts_to_test = [
        ("localhost", 5000),
        ("127.0.0.1", 5000),
        ("192.168.100.175", 5000)
    ]
    
    urls_to_test = [
        "https://localhost:5000",
        "https://127.0.0.1:5000",
        "https://192.168.100.175:5000"
    ]
    
    print("\n📡 CONNECTIVITY TESTS")
    print("-" * 30)
    
    connection_results = []
    for host, port in hosts_to_test:
        result = test_port_connection(host, port)
        connection_results.append((host, port, result))
    
    print("\n🔒 HTTPS RESPONSE TESTS")
    print("-" * 30)
    
    https_results = []
    for url in urls_to_test:
        result = test_https_response(url)
        https_results.append((url, result))
    
    print("\n📜 SSL CERTIFICATE TESTS")
    print("-" * 30)
    
    cert_results = []
    for host, port in hosts_to_test:
        if any(r[2] for r in connection_results if r[0] == host):  # Only test if connection works
            result = check_certificate(host, port)
            cert_results.append((host, port, result))
    
    print("\n🛡️ SYSTEM CHECKS")
    print("-" * 30)
    
    if sys.platform == "win32":
        check_firewall_windows()
    
    # Summary
    print("\n" + "="*60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*60)
    
    working_connections = [r for r in connection_results if r[2]]
    working_https = [r for r in https_results if r[1]]
    
    if working_connections:
        print(f"✅ {len(working_connections)} working connections found:")
        for host, port, _ in working_connections:
            print(f"   - {host}:{port}")
    else:
        print("❌ No working connections found")
    
    if working_https:
        print(f"✅ {len(working_https)} working HTTPS endpoints found:")
        for url, _ in working_https:
            print(f"   - {url}")
        print("\n🎉 Try accessing these URLs in your browser!")
    else:
        print("❌ No working HTTPS endpoints found")
        print("⚠️ The server might not be running or there's a configuration issue")
    
    suggest_solutions()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Diagnostic cancelled by user")
    except Exception as e:
        print(f"\n❌ Diagnostic error: {e}")
        suggest_solutions()