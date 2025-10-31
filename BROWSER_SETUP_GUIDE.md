# 🌐 Browser Setup Guide - Accessing Your Secure Site

## ✅ Your HTTPS Server is Working!

Your server is running correctly on:
- `https://127.0.0.1:5000` (localhost)
- `https://192.168.100.175:5000` (network access)

The "not secure" warning you're seeing is **normal** for self-signed certificates and doesn't mean your site is broken.

## 🔒 How to Access Your Secure Site

### Step 1: Open the Correct URL
Use **HTTPS** (not HTTP):
```
https://localhost:5000
OR
https://127.0.0.1:5000
```

### Step 2: Accept the Security Warning

#### Chrome/Edge:
1. You'll see a scary warning:
   ```
   ⚠️ Attackers might be trying to steal your information from 192.168.100.175
   net::ERR_CERT_AUTHORITY_INVALID
   This server couldn't prove that it's 192.168.100.175
   ```
2. **Don't worry!** Click **"Advanced"** at the bottom
3. Click **"Continue to [IP address] (unsafe)"**
4. ✅ You're now on the secure site!

#### Firefox:
1. You'll see "Warning: Potential Security Risk Ahead"
2. Click **"Advanced..."**
3. Click **"Accept the Risk and Continue"**
4. ✅ You're now on the secure site!

#### Safari:
1. You'll see "This Connection Is Not Private"
2. Click **"Show Details"**
3. Click **"visit this website"**
4. Click **"Visit Website"**
5. ✅ You're now on the secure site!

### Step 3: Enable Microphone Access

Once you're on the secure site:

1. **Look for the microphone permission prompt** (usually appears automatically)
2. **Click "Allow"** when asked for microphone access
3. **If no prompt appears:**
   - Click the **lock icon** in your address bar
   - Set **Microphone** to "Allow"
   - **Refresh the page**

## 🎤 Microphone Permission Troubleshooting

### If microphone still doesn't work:

#### Option 1: Browser Settings
**Chrome/Edge:**
1. Go to `chrome://settings/content/microphone`
2. Add `https://localhost:5000` to "Allow" list

**Firefox:**
1. Go to `about:preferences#privacy`
2. Scroll to "Permissions" → "Microphone"
3. Find localhost and set to "Allow"

#### Option 2: System Permissions
**Windows:**
1. Settings → Privacy → Microphone
2. Enable "Allow apps to access your microphone"
3. Enable for your browser

**macOS:**
1. System Preferences → Security & Privacy → Microphone
2. Check your browser in the list

## 🔍 How to Verify It's Working

### 1. Check the Lock Icon
- In your address bar, you should see a lock icon (🔒)
- It might show as "Not Secure" but that's OK for self-signed certificates
- The important thing is that it's using HTTPS

### 2. Check the URL
- Make sure it starts with `https://` (not `http://`)
- The URL should be `https://localhost:5000`

### 3. Test Microphone Access
- On the main page, you should see a microphone status indicator
- It should show "Microphone access granted" if working correctly
- Try clicking "Start AI Recording" to test

## ❓ Why "Not Secure" Warning?

The "not secure" warning appears because:
- We're using a **self-signed certificate** (not from a trusted authority)
- This is **normal for local development**
- Your connection **IS actually encrypted** and secure
- It's just not verified by a certificate authority

## 🚀 Quick Test

1. Open: `https://localhost:5000`
2. Accept the security warning
3. Allow microphone access
4. Look for "🎤 Microphone access granted" on the page
5. Try starting a recording

## 🆘 Still Having Issues?

If you're still having problems:

1. **Clear browser cache and cookies**
2. **Try a different browser** (Chrome, Firefox, Safari)
3. **Restart your browser completely**
4. **Check if any antivirus is blocking the connection**
5. **Try the network URL:** `https://192.168.100.175:5000`

## ✅ Success Indicators

You'll know it's working when:
- ✅ URL shows `https://localhost:5000`
- ✅ Page loads (even with security warning)
- ✅ Microphone status shows "granted"
- ✅ Recording button is enabled
- ✅ You can start recording successfully

Remember: The "not secure" warning is cosmetic - your connection is actually encrypted and your microphone will work!