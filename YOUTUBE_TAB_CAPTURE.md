# 🎬 YouTube Tab Capture - Live Analysis

## ✅ Use YouTube Video as Live Audio Source

Instead of Zoom call, you can analyze YouTube video in **real-time** using Chrome Tab Capture!

---

## 🚀 Quick Start (2 minutes)

### **Step 1: Open YouTube Video**

1. Open **NEW Chrome Tab**
2. Go to YouTube video:
   ```
   https://www.youtube.com/watch?v=YOUR_VIDEO_ID
   ```
3. **Don't play yet!** Wait for Step 6.

---

### **Step 2: Open Application**

```
https://sales-best-friend-tkoj.vercel.app/
```

---

### **Step 3: Click "🎤 Start Recording"**

---

### **Step 4: Select "Chrome Tab"**

Chrome will show "Share your screen" dialog:

```
┌─────────────────────────────┐
│ Share your screen           │
├─────────────────────────────┤
│ ● Entire Screen             │
│ ○ Window                    │
│ ○ Chrome Tab   ← SELECT THIS│
└─────────────────────────────┘
```

---

### **Step 5: Select YouTube Tab**

```
┌─────────────────────────────┐
│ Choose what to share        │
├─────────────────────────────┤
│ 📺 YouTube - Video Title    │ ← Click this
│ 📄 SalesBestFriend App      │
│ 📄 Other tabs...            │
└─────────────────────────────┘
```

---

### **Step 6: ✅ ENABLE "Share tab audio"**

```
┌─────────────────────────────┐
│ ✅ Share tab audio          │ ← CHECK THIS!
│                             │
│        [Cancel] [Share]     │
└─────────────────────────────┘
```

**⚠️ CRITICAL:** If you don't check "Share tab audio", no sound will be captured!

---

### **Step 7: Click "Share"**

---

### **Step 8: Play YouTube Video**

1. Switch to YouTube tab
2. Click **PLAY** ▶️
3. Watch the magic happen! ✨

---

## 📊 What Happens:

```
YouTube Tab Audio
    ↓
Chrome Tab Capture
    ↓
Frontend (PCM 16kHz)
    ↓
WebSocket → Railway Backend
    ↓
Whisper Transcription (every 10s)
    ↓
LLM Analysis (Claude/Llama)
    ↓
✅ Checklist updates
✅ Client card fills
✅ Stage tracking
```

---

## ✅ Advantages:

1. **No YouTube download issues** (no bot detection!)
2. **Real-time streaming** (exactly like live call)
3. **Same analysis pipeline** (Whisper + LLM)
4. **Works with any YouTube video**
5. **No cookies/authentication needed**

---

## 🎯 Best Practices:

### **Choose Short Videos for Testing:**
- ✅ 1-5 minutes long
- ✅ Clear audio
- ✅ Bahasa Indonesia content
- ✅ Sales call/conversation format

### **Optimal Setup:**
- ✅ Close unnecessary tabs
- ✅ Good internet connection
- ✅ Keep YouTube tab active (not minimized)
- ✅ Normal playback speed (1x, not 1.5x or 2x)

---

## 🐛 Troubleshooting:

### **Problem: "No audio track"**
**Solution:** 
- ✅ Check "Share tab audio" checkbox
- ✅ Make sure YouTube video has audio
- ✅ Try another video

### **Problem: No transcription appearing**
**Wait:** 
- First transcription appears after **10 seconds**
- Check console (F12) for logs

### **Problem: Video plays but no analysis**
**Check:**
- ✅ WebSocket connections (console should show "/coach connected", "/ingest connected")
- ✅ Backend is running: https://salesbestfriend-production.up.railway.app/health

---

## 📝 Example Videos to Test:

### **Short (Good for quick test):**
```
https://www.youtube.com/watch?v=jNQXAC9IVRw  (19 seconds)
```

### **Medium (Better for analysis):**
```
Find any 3-5 minute Indonesian sales call recording on YouTube
```

---

## 💡 Pro Tips:

### **Fast Testing:**
1. Use **1-minute** video
2. Check if transcription works
3. Check if checklist updates
4. Then test with longer video

### **Multiple Tests:**
- Stop recording (click Stop button)
- Select different YouTube tab
- Start recording again

### **Simulate Real Call:**
- Use actual sales call recording
- Let it play at normal speed
- Watch real-time analysis!

---

## 🔧 Technical Details:

### **Audio Format:**
- **Source:** YouTube tab audio (any format)
- **Captured:** MediaStream from Chrome
- **Converted:** PCM 16kHz mono (Web Audio API)
- **Sent:** WebSocket binary chunks (8KB)
- **Processed:** Whisper transcription (every 10s buffer)

### **Browser Requirements:**
- ✅ Chrome 72+ (getDisplayMedia support)
- ✅ HTTPS required (or localhost)
- ✅ Tab audio capture permission

---

## 🎓 Why This Works Better Than YouTube Download:

| Method | YouTube Download | Tab Capture |
|--------|-----------------|-------------|
| **Bot Detection** | ❌ Often blocked | ✅ No issues |
| **Cookies** | ❌ Required | ✅ Not needed |
| **Speed** | ❌ Download + process | ✅ Real-time |
| **Realistic** | ❌ Batch processing | ✅ Same as live call |
| **Setup** | ❌ Complex | ✅ 2 clicks |

---

## ✅ Summary:

**YouTube Tab Capture = Best Way to Test!**

1. Open YouTube video in tab
2. Click "Start Recording"
3. Select **Chrome Tab**
4. **✅ Check "Share tab audio"**
5. Click Share
6. Play video!

---

**Last Updated:** 2025-11-20  
**Status:** ✅ Fully Working

