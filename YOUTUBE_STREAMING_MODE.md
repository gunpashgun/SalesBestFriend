# 🎬 YouTube Streaming Mode - Real-Time Simulation

## 📋 Проблема (БЫЛО):

**Старый YouTube Debug:**
```
1. ❌ Скачивает ВСЁ видео
2. ❌ Транскрибирует ВЕСЬ файл разом
3. ❌ Анализирует ВЕСЬ текст сразу
```

**Результат:** Не похоже на реальный звонок! ❌

---

## ✅ Решение (СТАЛО):

**Новый YouTube Streaming Mode:**
```
1. ✅ Скачивает видео и конвертирует в PCM 16kHz mono
2. ✅ Стримит аудио ЧАНКАМИ (по 1 секунде), как live звонок
3. ✅ Буферизует 10 секунд → транскрибирует → анализирует
4. ✅ Использует ТЕ ЖЕ обработчики что и live запись
```

**Результат:** Максимально близко к боевым условиям! ✅

---

## 🎯 Архитектура

### **Старая схема (batch processing):**
```
YouTube URL
    ↓
Download FULL video
    ↓
Transcribe ALL at once
    ↓
Analyze ALL text
    ↓
Return result
```

**Время:** ~2-5 минут для 20-минутного видео

---

### **Новая схема (streaming):**
```
YouTube URL
    ↓
Download + Convert to PCM 16kHz mono
    ↓
┌─────────────────────────────────┐
│  YouTubeStreamer                │
│  ├─ Read 1s chunk from WAV      │
│  ├─ Yield PCM chunk             │
│  ├─ Sleep 1s (simulate real-time) │
│  └─ Repeat...                   │
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│  AudioBuffer (10s)              │
│  ├─ Accumulate chunks           │
│  └─ Trigger when 10s ready      │
└─────────────────────────────────┘
    ↓
Transcribe 10s buffer (Whisper)
    ↓
┌─────────────────────────────────┐
│  Trial Class Analyzer (LLM)     │
│  ├─ Check checklist items       │
│  ├─ Extract client info         │
│  └─ Update progress             │
└─────────────────────────────────┘
    ↓
Continue streaming...
```

**Время:** ~20 минут для 20-минутного видео (real-time!)

---

## 📁 Новые файлы

### **`backend/utils/youtube_streamer.py`**

**Основной класс:**
```python
class YouTubeStreamer:
    def download_audio_as_wav(self, youtube_url: str) -> str:
        """
        Download from YouTube and convert to WAV PCM 16kHz mono
        Uses yt-dlp + FFmpeg
        """
    
    async def stream_audio_chunks(
        self, 
        wav_path: str, 
        real_time: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Read WAV file and yield PCM chunks (1 second each)
        
        If real_time=True:
            - Sleep 1 second between chunks (simulates live playback)
        
        If real_time=False:
            - No sleep (fast processing for testing)
        """
    
    async def stream_youtube_url(
        self, 
        youtube_url: str, 
        real_time: bool = True
    ) -> AsyncGenerator[bytes, None]:
        """
        Complete pipeline: download + stream
        """
```

**Usage:**
```python
from utils.youtube_streamer import get_streamer

streamer = get_streamer(chunk_duration=1.0)

async for pcm_chunk in streamer.stream_youtube_url(url, real_time=True):
    # Process chunk (same as live recording)
    audio_buffer.add_chunk(pcm_chunk)
```

---

## 🔄 Обновленный Endpoint

### **`POST /api/process-youtube`**

**Новые параметры:**
```
url: str           - YouTube video URL (required)
language: str      - Transcription language (default: "id")
real_time: bool    - Simulate real-time playback (default: True)
```

**Behavior:**

**If `real_time=True` (default):**
- Стримит аудио с задержками (1s между чанками)
- Симулирует реальный звонок
- Занимает ~20 минут для 20-минутного видео
- **Идеально для тестирования в боевых условиях**

**If `real_time=False`:**
- Стримит аудио БЕЗ задержек
- Обрабатывает максимально быстро
- Занимает ~3-5 минут для 20-минутного видео
- **Полезно для быстрой отладки**

---

## 🎯 Преимущества нового подхода

### **1. Реалистичное тестирование** 🎬
- Симулирует live звонок
- Те же буферы (10s)
- Те же задержки транскрипции
- Та же логика анализа

### **2. Единая кодовая база** 📦
- `/ingest` (live) и `/api/process-youtube` (debug) используют **одинаковую логику**:
  - `AudioBuffer` для буферизации
  - `transcribe_audio_buffer()` для транскрипции
  - `TrialClassAnalyzer` для анализа
  - Одинаковые checklist checks
  - Одинаковая client card extraction

### **3. Обнаружение проблем** 🐛
- Если что-то не работает в streaming mode → не будет работать в live!
- Можно тестировать без Zoom звонка
- Воспроизводимые тесты (один и тот же YouTube URL)

### **4. Гибкость** ⚙️
- `real_time=True` → максимально реалистично
- `real_time=False` → быстрое тестирование

---

## 📊 Пример использования

### **Frontend (YouTubeDebugPanel):**
```typescript
const formData = new FormData()
formData.append('url', 'https://youtube.com/watch?v=...')
formData.append('language', 'id')
formData.append('real_time', 'true')  // 🎯 Real-time mode!

const response = await fetch(`${API_HTTP}/api/process-youtube`, {
  method: 'POST',
  body: formData
})
```

### **Backend flow:**
```
1. Download YouTube video
2. Convert to WAV PCM 16kHz mono
3. Stream chunks:
   - Read 1s of audio
   - Yield PCM chunk
   - Sleep 1s (if real_time=true)
4. Buffer 10s of audio
5. When buffer ready:
   - Transcribe with Whisper
   - Check checklist items (LLM)
   - Extract client info (LLM)
6. Repeat until video ends
```

---

## 🔧 Technical Details

### **Audio Format:**
- **Sample Rate:** 16kHz (required by Whisper)
- **Channels:** 1 (mono)
- **Bit Depth:** 16-bit signed PCM
- **Format:** WAV → raw PCM bytes

### **Chunk Size:**
- **Duration:** 1 second
- **Frames:** 16,000 (16kHz × 1s)
- **Bytes:** 32,000 (16,000 frames × 2 bytes/sample)

### **Buffer Size:**
- **Duration:** 10 seconds
- **Trigger:** Every 10s of accumulated audio
- **Purpose:** Whisper works best with 10-30s segments

### **Dependencies:**
- `yt-dlp` - Download YouTube videos
- `FFmpeg` - Convert audio to PCM
- `wave` - Read WAV files
- `asyncio` - Async streaming

---

## 🚀 Testing Workflow

### **Step 1: Find YouTube test video**
```
Find a recorded sales call (20-30 minutes)
Example: https://youtube.com/watch?v=NikP6phDVgw
```

### **Step 2: Process with streaming mode**
```bash
# Real-time mode (simulates live call)
curl -X POST http://localhost:8000/api/process-youtube \
  -F "url=https://youtube.com/watch?v=NikP6phDVgw" \
  -F "language=id" \
  -F "real_time=true"

# Fast mode (quick testing)
curl -X POST http://localhost:8000/api/process-youtube \
  -F "url=https://youtube.com/watch?v=NikP6phDVgw" \
  -F "language=id" \
  -F "real_time=false"
```

### **Step 3: Watch console logs**
```
📥 Downloading YouTube video: ...
✅ Downloaded: ... (1234s)
📁 WAV file: /tmp/.../audio.wav
🎬 Starting audio stream from: /tmp/.../audio.wav
   Real-time mode: True
   Chunk duration: 1.0s
📊 Audio format: 1 ch, 2 bytes/sample, 16000 Hz
   Frames per chunk: 16000
   Bytes per chunk: 32000

🎯 Transcription triggered (10s buffer ready, chunk #10)
📝 Transcript (145 chars):
   Selamat pagi, nama saya...

📋 Checking checklist items (stage: greeting)...
   ✅ Introduce yourself & company (confidence: 0.92)

👤 Extracting client information...
   ✅ child_age: 8 years old

   Streamed: 10 chunks (10.1s)
   Streamed: 20 chunks (20.2s)
   ...
```

### **Step 4: Compare with live recording**
- ✅ Same buffer behavior
- ✅ Same transcription timing
- ✅ Same checklist checking logic
- ✅ Same client info extraction

---

## ⚠️ Important Notes

### **1. Real-time mode is SLOW (by design)**
- 20-minute video = 20 minutes processing
- This is **intentional** - simulates live call!
- Use `real_time=false` for quick testing

### **2. Uses same AudioBuffer as live ingest**
- 10-second buffer before transcription
- Same behavior as real Zoom call

### **3. Memory efficient**
- Streams chunks, doesn't load full video in RAM
- Cleans up WAV file after processing

### **4. FFmpeg required**
- Used by yt-dlp to convert audio
- Already installed in Dockerfile

---

## 📚 Related Files

- `backend/utils/youtube_streamer.py` - **NEW:** Streaming implementation
- `backend/utils/youtube_processor.py` - **OLD:** Batch processing (deprecated)
- `backend/utils/audio_buffer.py` - Audio buffering (used by both live + streaming)
- `backend/utils/realtime_transcriber.py` - Whisper transcription
- `backend/main_trial_class.py` - `/api/process-youtube` endpoint

---

## 🎓 Summary

### **Before:**
- YouTube debug was **completely different** from live recording
- Batch processing, no simulation of real-time conditions
- Hard to find bugs that only appear in live calls

### **After:**
- YouTube debug **uses same code path** as live recording
- Streaming mode simulates real-time conditions
- If it works in streaming → it will work live!

---

**Last Updated:** 2025-11-20  
**Status:** ✅ Implemented and tested

