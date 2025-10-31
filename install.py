#!/usr/bin/env python3
"""
Perfect AI Meeting Analyzer - Installation Script
Automated setup for different environments
"""

import os
import sys
import subprocess
import platform
import argparse

def run_command(command, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=check, 
                              capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ is required")
        print(f"Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def install_system_dependencies():
    """Install system-level dependencies based on platform."""
    system = platform.system().lower()
    
    print(f"🔧 Installing system dependencies for {system}...")
    
    if system == "darwin":  # macOS
        print("Installing macOS dependencies...")
        if not run_command("brew --version", check=False):
            print("❌ Homebrew not found. Please install Homebrew first:")
            print("https://brew.sh/")
            return False
        return run_command("brew install portaudio")
        
    elif system == "linux":
        # Try to detect Linux distribution
        try:
            with open("/etc/os-release") as f:
                os_info = f.read().lower()
        except:
            os_info = ""
            
        if "ubuntu" in os_info or "debian" in os_info:
            print("Installing Ubuntu/Debian dependencies...")
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y build-essential",
                "sudo apt-get install -y portaudio19-dev",
                "sudo apt-get install -y python3-dev",
                "sudo apt-get install -y ffmpeg"
            ]
        elif "centos" in os_info or "rhel" in os_info or "fedora" in os_info:
            print("Installing CentOS/RHEL/Fedora dependencies...")
            commands = [
                "sudo yum groupinstall -y 'Development Tools'",
                "sudo yum install -y portaudio-devel",
                "sudo yum install -y python3-devel",
                "sudo yum install -y ffmpeg"
            ]
        else:
            print("⚠️ Unknown Linux distribution. Please install manually:")
            print("- build-essential or Development Tools")
            print("- portaudio development headers")
            print("- python3 development headers")
            print("- ffmpeg")
            return True
            
        for cmd in commands:
            if not run_command(cmd):
                print(f"❌ Failed to run: {cmd}")
                return False
        return True
        
    elif system == "windows":
        print("Windows detected. Please ensure you have:")
        print("- Microsoft Visual C++ Build Tools")
        print("- Windows SDK")
        print("These are usually installed with Visual Studio or Build Tools for Visual Studio")
        return True
        
    else:
        print(f"⚠️ Unknown system: {system}")
        return True

def create_virtual_environment():
    """Create and activate virtual environment."""
    print("🐍 Creating virtual environment...")
    
    if os.path.exists("venv"):
        print("Virtual environment already exists")
        return True
        
    if not run_command(f"{sys.executable} -m venv venv"):
        print("❌ Failed to create virtual environment")
        return False
        
    print("✅ Virtual environment created")
    return True

def get_pip_command():
    """Get the correct pip command for the platform."""
    system = platform.system().lower()
    if system == "windows":
        return "venv\\Scripts\\pip"
    else:
        return "venv/bin/pip"

def install_python_dependencies(env_type="base"):
    """Install Python dependencies."""
    pip_cmd = get_pip_command()
    
    # Upgrade pip first
    print("📦 Upgrading pip...")
    if not run_command(f"{pip_cmd} install --upgrade pip"):
        print("⚠️ Failed to upgrade pip, continuing anyway...")
    
    # Choose requirements file
    req_files = {
        "base": "requirements.txt",
        "minimal": "requirements-minimal.txt", 
        "dev": "requirements-dev.txt",
        "prod": "requirements-prod.txt"
    }
    
    req_file = req_files.get(env_type, "requirements.txt")
    
    if not os.path.exists(req_file):
        print(f"❌ Requirements file not found: {req_file}")
        return False
    
    print(f"📦 Installing Python dependencies from {req_file}...")
    return run_command(f"{pip_cmd} install -r {req_file}")

def setup_database():
    """Initialize the database."""
    print("🗄️ Setting up database...")
    
    # Create .env file if it doesn't exist
    if not os.path.exists(".env"):
        print("Creating .env file...")
        env_content = """# Perfect AI Meeting Analyzer Configuration
SECRET_KEY=your-secret-key-here-change-in-production
DATABASE_URL=sqlite:///perfect_ai.db

# API Keys (Optional)
OPENAI_API_KEY=your-openai-key-here
XAI_API_KEY=your-xai-key-here
ASSEMBLYAI_API_KEY=your-assemblyai-key-here
DEEPGRAM_API_KEY=your-deepgram-key-here

# App Settings
FLASK_ENV=development
FLASK_DEBUG=True
"""
        with open(".env", "w") as f:
            f.write(env_content)
        print("✅ .env file created")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Install Perfect AI Meeting Analyzer")
    parser.add_argument("--env", choices=["base", "minimal", "dev", "prod"], 
                       default="base", help="Environment type")
    parser.add_argument("--skip-system", action="store_true", 
                       help="Skip system dependency installation")
    parser.add_argument("--skip-venv", action="store_true",
                       help="Skip virtual environment creation")
    
    args = parser.parse_args()
    
    print("🎯 Perfect AI Meeting Analyzer Installation")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install system dependencies
    if not args.skip_system:
        if not install_system_dependencies():
            print("❌ System dependency installation failed")
            sys.exit(1)
        print("✅ System dependencies installed")
    
    # Create virtual environment
    if not args.skip_venv:
        if not create_virtual_environment():
            sys.exit(1)
    
    # Install Python dependencies
    if not install_python_dependencies(args.env):
        print("❌ Python dependency installation failed")
        sys.exit(1)
    print("✅ Python dependencies installed")
    
    # Setup database
    if not setup_database():
        print("❌ Database setup failed")
        sys.exit(1)
    print("✅ Database setup complete")
    
    print("\n🎉 Installation completed successfully!")
    print("\nNext steps:")
    print("1. Activate virtual environment:")
    
    system = platform.system().lower()
    if system == "windows":
        print("   venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    
    print("2. Edit .env file with your API keys")
    print("3. Run the application:")
    print("   python app_perfect_ai.py")
    print("\n🚀 Enjoy Perfect AI Meeting Analyzer!")

if __name__ == "__main__":
    main()