# 🔧 YouTube Debug Troubleshooting Guide

## Problem: "Error: Failed to fetch"

When you see this error after clicking "🔍 Analyze Video", it means the frontend cannot connect to the backend.

---

## ✅ Step-by-Step Diagnosis

### **1. Check Backend Status** 🖥️

**Option A: Local Development**
```bash
# Make sure the backend is running
cd /Users/pavelloucker/SalesBestFriend
./start_backend.sh
```

You should see:
```
✅ Backend started at http://localhost:8000
```

**Option B: Railway Production**

Visit: https://salesbestfriend-production.up.railway.app/

✅ **If you see:** `{"message":"Trial Class Assistant API"}`  
→ Backend is running!

❌ **If you see:** `502 Bad Gateway` or timeout  
→ Backend is down! Check Railway logs.

---

### **2. Check Frontend `.env` File** ⚙️

**Location:** `/Users/pavelloucker/SalesBestFriend/frontend/.env`

**For Local Backend:**
```env
VITE_API_WS=ws://localhost:8000
VITE_API_HTTP=http://localhost:8000
```

**For Railway Backend:**
```env
VITE_API_WS=wss://salesbestfriend-production.up.railway.app
VITE_API_HTTP=https://salesbestfriend-production.up.railway.app
```

⚠️ **Important:** After changing `.env`, **restart the frontend**:
```bash
cd frontend
npm run dev
```

---

### **3. Check Browser Console** 🔍

Open browser DevTools (F12) → Console tab

**Good signs:**
```
🔍 Connecting to backend: https://salesbestfriend-production.up.railway.app
📤 Sending YouTube URL: https://youtube.com/...
📡 Response status: 200 OK
📦 Response data: {success: true, ...}
```

**Bad signs:**
```
❌ YouTube processing error: Failed to fetch
```

This means:
- ❌ Backend is not accessible
- ❌ CORS issue (should not happen with our setup)
- ❌ Network issue

---

### **4. Test Backend Manually** 🧪

**Test with curl:**
```bash
curl https://salesbestfriend-production.up.railway.app/
```

Expected response:
```json
{"message":"Trial Class Assistant API"}
```

**Test YouTube endpoint:**
```bash
curl -X POST https://salesbestfriend-production.up.railway.app/api/process-youtube \
  -F "url=https://www.youtube.com/watch?v=yQvcBDNw1Do" \
  -F "language=id"
```

If this returns an error → backend problem!

---

## 🐛 Common Issues & Solutions

### Issue 1: "Connection refused" (Local)
**Problem:** Backend is not running  
**Solution:**
```bash
cd /Users/pavelloucker/SalesBestFriend
./start_backend.sh
```

---

### Issue 2: "502 Bad Gateway" (Railway)
**Problem:** Railway container crashed or not deployed  
**Solution:**
1. Check Railway logs: https://railway.app/project/your-project
2. Redeploy if needed
3. Check `python-multipart` is installed (see previous fixes)

---

### Issue 3: "CORS error"
**Problem:** Rare, but possible with strict browsers  
**Solution:**
Backend already has:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Issue 4: "Mixed content" (HTTPS/HTTP mismatch)
**Problem:** Frontend on HTTPS trying to access HTTP backend  
**Solution:**
- Frontend on Vercel (HTTPS) → Backend must be HTTPS (Railway)
- Frontend local (HTTP) → Backend can be HTTP (local)

---

## 🚀 Quick Test Workflow

1. **Open Browser DevTools** (F12)
2. **Open Console tab**
3. **Click "🔍 Analyze Video"**
4. **Watch logs:**
   - ✅ "Connecting to backend: ..." → Good
   - ✅ "Response status: 200" → Great!
   - ❌ "Failed to fetch" → Backend issue

---

## 📞 Still Not Working?

1. Copy error from browser console
2. Copy backend URL from logs
3. Test backend URL in browser
4. Check Railway/backend logs for errors

---

## ✅ Success Checklist

- [ ] Backend is running (test in browser)
- [ ] Frontend `.env` has correct backend URL
- [ ] Frontend restarted after `.env` change
- [ ] Browser console shows "Connecting to backend: ..."
- [ ] No CORS errors in console
- [ ] Backend returns valid JSON response

---

**Last Updated:** 2025-11-20  
**Related Docs:** `YOUTUBE_DEBUG_GUIDE.md`, `DEPLOY_NOW.md`

