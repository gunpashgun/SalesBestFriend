# 🚀 Deployment Guide - Trial Class Assistant

## 📋 Overview

This app consists of **two parts** that need separate deployment:

1. **Frontend (React)** → Deploy to **Vercel** ✅
2. **Backend (Python/FastAPI)** → Deploy to **Railway/Render** ✅

---

## 🎨 Part 1: Frontend Deployment (Vercel)

### **Option A: Via Vercel CLI**

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel

# Follow prompts:
# - Project name: sales-assistant (or your choice)
# - Root directory: ./
# - Build command: cd frontend && npm run build
# - Output directory: frontend/dist
```

### **Option B: Via Vercel Dashboard**

1. Go to https://vercel.com
2. Click "Add New Project"
3. Import from Git (connect your GitHub repo)
4. Configure:
   - **Root Directory:** `./`
   - **Build Command:** `cd frontend && npm install && npm run build`
   - **Output Directory:** `frontend/dist`
   - **Install Command:** `cd frontend && npm install`

5. Add Environment Variables:
   ```
   VITE_API_WS=wss://your-backend.railway.app
   VITE_API_HTTP=https://your-backend.railway.app
   ```
   ⚠️ Replace with your actual backend URL (see Part 2)

6. Click "Deploy"

---

## 🐍 Part 2: Backend Deployment

Backend (Python/FastAPI) **cannot** run on Vercel. Use one of these:

### **Option A: Railway (Recommended, Easy)**

1. Go to https://railway.app
2. Click "Start a New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Railway will auto-detect Python
6. Configure:
   - **Root Directory:** `backend`
   - **Start Command:** `uvicorn main_trial_class:app --host 0.0.0.0 --port $PORT`

7. Add Environment Variables:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   PORT=8000
   ```

8. Deploy!

9. Copy the generated URL (e.g., `https://your-app.railway.app`)

10. Update Vercel environment variables with this URL

### **Option B: Render**

1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect GitHub repository
4. Configure:
   - **Name:** sales-assistant-backend
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main_trial_class:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   PYTHON_VERSION=3.11.0
   ```

6. Deploy!

### **Option C: Heroku**

```bash
# Install Heroku CLI
brew install heroku/brew/heroku  # Mac
# or download from heroku.com

# Login
heroku login

# Create app
heroku create sales-assistant-backend

# Set buildpack
heroku buildpacks:set heroku/python

# Set config
heroku config:set OPENROUTER_API_KEY=sk-or-v1-...

# Deploy
cd backend
git subtree push --prefix backend heroku main

# Or if using main repo:
git push heroku main
```

---

## 🔗 Linking Frontend & Backend

After deploying both:

1. **Get backend URL** (from Railway/Render/Heroku)
   - Example: `https://sales-assistant.railway.app`

2. **Update Vercel environment variables:**
   - Go to Vercel Dashboard → Your Project → Settings → Environment Variables
   - Update:
     ```
     VITE_API_WS=wss://sales-assistant.railway.app
     VITE_API_HTTP=https://sales-assistant.railway.app
     ```
   - **Important:** Change `https://` to `wss://` for WebSocket URL

3. **Redeploy Vercel** (to pick up new env vars)
   ```bash
   vercel --prod
   ```

---

## ⚙️ Backend Requirements File

Make sure `backend/requirements.txt` is complete:

```txt
fastapi
uvicorn[standard]
websockets
python-dotenv
requests
faster-whisper
yt-dlp
ffmpeg-python
```

---

## 🔧 Deployment Checklist

### **Before Deploying:**

- [ ] Backend `requirements.txt` is complete
- [ ] Backend `.env.example` has all variables
- [ ] Frontend builds locally: `cd frontend && npm run build`
- [ ] Backend runs locally: `cd backend && python main_trial_class.py`
- [ ] OpenRouter API key is ready

### **After Deploying:**

- [ ] Backend URL is accessible (visit in browser)
- [ ] Frontend URL is accessible
- [ ] Frontend can connect to backend (check Network tab in DevTools)
- [ ] WebSocket connection works
- [ ] Test with YouTube Debug mode
- [ ] Test with live recording (if possible)

---

## 🐛 Troubleshooting

### **Frontend deploys but shows blank page**

Check Vercel logs:
```bash
vercel logs
```

Common issues:
- Build command incorrect
- Output directory incorrect
- Missing dependencies

### **Backend won't start**

Check logs on Railway/Render:
- Missing `requirements.txt` packages
- Wrong start command
- Missing environment variables

### **Frontend can't connect to backend**

Check:
1. Backend URL is correct in Vercel env vars
2. Backend allows CORS (already configured in `main_trial_class.py`)
3. Using `wss://` for WebSocket (not `ws://`)
4. Backend is actually running (visit URL in browser)

### **WebSocket connection fails**

Backend must support WebSocket upgrades. Railway/Render do this automatically.

If still fails:
- Check backend logs for errors
- Verify `wss://` (not `ws://`) in production
- Test backend WebSocket directly: https://www.websocket.org/echo.html

---

## 💰 Cost Estimate

### **Free Tier:**

| Service | Free Tier | Our Usage |
|---------|-----------|-----------|
| **Vercel** | 100GB bandwidth/month | ~1-2GB/month ✅ |
| **Railway** | $5 credit/month | ~$3-5/month ⚠️ |
| **Render** | 750 hours/month | ~720 hours/month ✅ |

**Recommended for production:** Render (free tier) or Railway (pay-as-go)

### **Paid:**

- **Railway:** ~$5-10/month (with usage)
- **Render:** $7/month (standard plan)
- **Heroku:** $7/month (basic dyno)

---

## 📊 Performance

### **Expected Response Times:**

- Frontend (Vercel CDN): **< 50ms**
- Backend (Railway/Render): **100-300ms**
- WebSocket latency: **50-100ms**
- Transcription: **2-3 seconds** (depends on audio length)

### **Scaling:**

- **Vercel:** Auto-scales (free tier)
- **Railway:** Auto-scales (pay per usage)
- **Render:** Fixed instances (configure manually)

---

## 🎯 Quick Deploy Commands

### **Deploy Everything:**

```bash
# 1. Deploy backend to Railway
railway login
railway link
railway up

# 2. Get backend URL
railway domain

# 3. Update Vercel env with backend URL
vercel env add VITE_API_WS production
# Enter: wss://your-backend.railway.app

vercel env add VITE_API_HTTP production
# Enter: https://your-backend.railway.app

# 4. Deploy frontend to Vercel
vercel --prod
```

---

## 🔄 CI/CD (Optional)

### **Automatic Deployment:**

Both Vercel and Railway support automatic deployments:

1. **Push to GitHub main branch**
2. **Vercel auto-deploys** frontend
3. **Railway auto-deploys** backend

No manual commands needed!

---

## 📚 Next Steps

After successful deployment:

1. Test all features in production
2. Set up custom domain (optional)
3. Configure monitoring (Vercel Analytics, Railway logs)
4. Set up error tracking (Sentry)
5. Create staging environment

---

## 🆘 Need Help?

**Vercel Support:**
- Docs: https://vercel.com/docs
- Discord: https://vercel.com/discord

**Railway Support:**
- Docs: https://docs.railway.app
- Discord: https://discord.gg/railway

**Render Support:**
- Docs: https://render.com/docs
- Community: https://community.render.com

---

**Good luck with deployment! 🚀**

*Last updated: 2025-11-19*

