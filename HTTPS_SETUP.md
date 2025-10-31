# 🔒 HTTPS Setup for Perfect AI Meeting Analyzer

## Why HTTPS is Required

Modern browsers require HTTPS (secure connection) for microphone access due to security policies. This ensures your audio data is protected and prevents unauthorized access to your microphone.

## Quick Setup

### Option 1: Automatic Setup (Recommended)
Run the setup script to automatically generate SSL certificates:

```bash
python setup_https.py
```

### Option 2: Manual Setup
1. Install the cryptography package:
   ```bash
   pip install cryptography>=41.0.0
   ```

2. Run the application - it will automatically generate SSL certificates:
   ```bash
   python app_perfect_ai.py
   ```

## Accessing the Application

1. **Open your browser and go to:** `https://localhost:5000`
2. **Accept the security warning** (this is normal for self-signed certificates)
3. **Allow microphone access** when prompted

## Browser-Specific Instructions

### Chrome/Edge
1. You'll see "Your connection is not private"
2. Click **"Advanced"**
3. Click **"Proceed to localhost (unsafe)"**
4. When prompted for microphone, click **"Allow"**

### Firefox
1. You'll see "Warning: Potential Security Risk Ahead"
2. Click **"Advanced..."**
3. Click **"Accept the Risk and Continue"**
4. Allow microphone when prompted

### Safari
1. You'll see "This Connection Is Not Private"
2. Click **"Show Details"**
3. Click **"visit this website"**
4. Click **"Visit Website"**
5. Go to Safari > Settings > Websites > Microphone
6. Set localhost to "Allow"

## Troubleshooting

### ❌ "Site Not Safe" Error
- **Solution:** Use `https://localhost:5000` instead of `http://localhost:5000`
- The app automatically generates SSL certificates for secure access

### ❌ Microphone Not Working
1. **Check browser permissions:**
   - Click the lock icon in the address bar
   - Set Microphone to "Allow"
   - Refresh the page

2. **Check system permissions:**
   - **Windows:** Settings > Privacy > Microphone > Allow apps to access microphone
   - **macOS:** System Preferences > Security & Privacy > Microphone
   - **Linux:** Check PulseAudio/ALSA settings

3. **Try a different browser** (Chrome, Firefox, Safari all work)

4. **Clear browser cache and cookies**

5. **Restart your browser completely**

### ❌ SSL Certificate Errors
If you get persistent SSL errors:

1. Delete existing certificates:
   ```bash
   del cert.pem key.pem  # Windows
   rm cert.pem key.pem   # Mac/Linux
   ```

2. Restart the application to generate new certificates

### ❌ "cryptography package not found"
Install the required package:
```bash
pip install cryptography>=41.0.0
```

## Security Notes

- The SSL certificates are **self-signed** and only valid for localhost
- This is **safe for local development** but not for production
- Your audio data **never leaves your computer** - all processing is local
- The "unsafe" warning is normal for self-signed certificates

## Production Deployment

For production deployment, you'll need:
1. A real domain name
2. Valid SSL certificates (Let's Encrypt, etc.)
3. Proper firewall configuration
4. Environment-specific security headers

## Need Help?

If you're still having issues:
1. Check the console for error messages (F12 in most browsers)
2. Try the test route: `https://localhost:5000/test`
3. Ensure no other applications are using port 5000
4. Check your antivirus/firewall settings

## Files Generated

The setup creates these files:
- `cert.pem` - SSL certificate (safe to commit to private repos)
- `key.pem` - Private key (**never commit this to public repos**)

Add to your `.gitignore`:
```
cert.pem
key.pem
```