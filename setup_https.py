#!/usr/bin/env python3
"""
Perfect AI HTTPS Setup Script
Generates SSL certificates and provides instructions for microphone access.
"""

import os
import sys
import subprocess
from pathlib import Path

def install_cryptography():
    """Install cryptography package if not available."""
    try:
        import cryptography
        print("✅ cryptography package is already installed")
        return True
    except ImportError:
        print("📦 Installing cryptography package...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography>=41.0.0"])
            print("✅ cryptography package installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install cryptography: {e}")
            return False

def generate_ssl_certificate():
    """Generate self-signed SSL certificate for HTTPS."""
    cert_file = 'cert.pem'
    key_file = 'key.pem'
    
    # Check if certificates already exist
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("✅ SSL certificates already exist")
        return True
    
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime
        import ipaddress
        
        print("🔒 Generating self-signed SSL certificate...")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Perfect AI"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key files
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        print("✅ SSL certificate generated successfully!")
        print(f"   Certificate: {cert_file}")
        print(f"   Private Key: {key_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate SSL certificate: {e}")
        return False

def print_browser_instructions():
    """Print instructions for browser setup."""
    print("\n" + "="*60)
    print("🌐 BROWSER SETUP INSTRUCTIONS")
    print("="*60)
    
    print("\n🔒 HTTPS ACCESS:")
    print("   1. Open https://localhost:5000 in your browser")
    print("   2. You'll see a security warning about the self-signed certificate")
    print("   3. Click 'Advanced' or 'Show Details'")
    print("   4. Click 'Proceed to localhost (unsafe)' or 'Accept Risk'")
    
    print("\n🎤 MICROPHONE PERMISSIONS:")
    print("   Chrome/Edge:")
    print("   1. Click the lock icon in the address bar")
    print("   2. Set Microphone to 'Allow'")
    print("   3. Refresh the page")
    
    print("\n   Firefox:")
    print("   1. Click the shield icon in the address bar")
    print("   2. Click 'Turn off Blocking for This Site'")
    print("   3. Allow microphone when prompted")
    
    print("\n   Safari:")
    print("   1. Go to Safari > Settings > Websites > Microphone")
    print("   2. Set localhost to 'Allow'")
    
    print("\n⚠️  TROUBLESHOOTING:")
    print("   - If microphone still doesn't work, try:")
    print("     1. Restart your browser completely")
    print("     2. Clear browser cache and cookies")
    print("     3. Check system microphone permissions")
    print("     4. Try a different browser")
    
    print("\n🔧 SYSTEM PERMISSIONS:")
    print("   Windows:")
    print("   1. Settings > Privacy > Microphone")
    print("   2. Enable 'Allow apps to access your microphone'")
    print("   3. Enable for your browser")
    
    print("\n   macOS:")
    print("   1. System Preferences > Security & Privacy > Microphone")
    print("   2. Check your browser in the list")
    
    print("\n   Linux:")
    print("   1. Check PulseAudio/ALSA settings")
    print("   2. Ensure microphone is not muted")
    print("   3. Test with: arecord -l")

def main():
    """Main setup function."""
    print("🎯 Perfect AI HTTPS Setup")
    print("="*40)
    
    # Install cryptography if needed
    if not install_cryptography():
        print("❌ Setup failed: Could not install cryptography package")
        return False
    
    # Generate SSL certificate
    if not generate_ssl_certificate():
        print("❌ Setup failed: Could not generate SSL certificate")
        return False
    
    # Print browser instructions
    print_browser_instructions()
    
    print("\n✅ HTTPS setup complete!")
    print("🚀 You can now run: python app_perfect_ai.py")
    print("🌐 Access at: https://localhost:5000")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)