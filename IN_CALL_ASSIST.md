# 🎯 In-Call Assist - Real-Time Coaching Hints

## Overview

**In-Call Assist** is an MVP feature that provides real-time, context-aware coaching hints to sales managers during active calls. When the system detects specific trigger phrases in the transcript, it instantly displays a coaching card with actionable advice.

## Architecture

```
Live Transcript (Real-time stream)
    ↓
Intent Detector (keyword + pattern matching)
    ↓
Trigger Match (lookup in playbook)
    ↓
WebSocket Message (assist_trigger)
    ↓
InCallAssist Component (UI card)
```

## Components

### 1. **Backend: Intent Detector** (`backend/utils/intent_detector.py`)

Detects trigger phrases in the transcript and returns coaching hints.

**Key Features:**
- Load triggers from `playbook.json`
- Regex-based keyword matching with word boundaries
- Priority-based selection (highest priority wins)
- Anti-spam: prevents same trigger from repeating within 30 seconds
- Extensible: no code changes needed to add new triggers

**Usage:**
```python
from utils.intent_detector import get_intent_detector

detector = get_intent_detector()
trigger = detector.detect_trigger("это дорого", language="id")
# Returns: {
#   "id": "price_objection",
#   "title": "💰 Клиент говорит, что дорого",
#   "hint": "Подчеркни ценность, а не цену...",
#   "priority": 10
# }
```

### 2. **Playbook** (`backend/playbook.json`)

Configuration file with all triggers and coaching hints.

**Structure:**
```json
[
  {
    "id": "price_objection",
    "match": ["дорого", "цена", "маhal", "expensive"],
    "title": "💰 Клиент говорит, что дорого",
    "hint": "Подчеркни ценность...",
    "priority": 10,
    "isPositive": false
  }
]
```

**To Add New Triggers:**
1. Edit `backend/playbook.json`
2. Add new object with: `id`, `match` (keywords), `title`, `hint`, `priority`
3. Restart backend (or trigger auto-reload)
4. No code changes needed! ✨

### 3. **Frontend: InCallAssist Component** (`frontend/src/components/InCallAssist.tsx`)

Beautiful, reactive UI component that displays coaching hints.

**Features:**
- Fade-in/fade-out animations (smooth UX)
- Auto-dismiss after 10 seconds
- Manual close button
- Visual timer bar
- Two styles: `attention` (red/orange) and `positive` (green)
- Responsive design

**Usage:**
```tsx
<InCallAssist trigger={assistTrigger} />
```

### 4. **Backend Integration** (`backend/main.py`)

Trigger detection happens in `websocket_ingest`:

```python
# Detect triggers in real-time transcript
assist_trigger = None
if transcript and len(transcript) > 10:
  assist_trigger = intent_detector.detect_trigger(transcript, transcription_language)

# Send via WebSocket
message_data = {
  ...
  "assist_trigger": assist_trigger
}
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ LIVE SALES CALL (Google Meet Tab Captured)                 │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ Real-time Transcription (5s intervals, 16kHz PCM)          │
│ Example: "это дорого, я не могу позволить..."              │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ BACKEND: websocket_ingest                                   │
│ → intent_detector.detect_trigger(transcript)                │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ TRIGGER MATCH: "дорого" → price_objection (priority 10)    │
│ ✅ Anti-spam check passed (not shown in last 30s)           │
│ ✅ Load hint from playbook                                  │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ WebSocket /coach Message                                    │
│ {                                                            │
│   "assist_trigger": {                                       │
│     "id": "price_objection",                                │
│     "title": "💰 Клиент говорит, что дорого",               │
│     "hint": "Подчеркни ценность, а не цену...",             │
│     "priority": 10                                          │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND: App.tsx receives message                          │
│ setAssistTrigger(data.assist_trigger)                       │
└─────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────┐
│ UI: InCallAssist Component                                  │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 💰 Клиент говорит, что дорого              [✕]      │   │
│ │ Подчеркни ценность, а не цену. Расскажи  │   │
│ │ про результаты детей.                      │   │
│ │                                [OK]                 │
│ └──────────────────────────────────────────────────────┘   │
│ ⏳ Auto-dismiss in 10 seconds (or click OK)                 │
└─────────────────────────────────────────────────────────────┘
```

## Current Triggers (Playbook)

| ID | Title | Keywords | Priority |
|-----|-------|----------|----------|
| `price_objection` | 💰 Цена | дорого, цена, маhal, expensive | 10 |
| `competitor_mention` | 🏆 Конкурент | coursera, udemy, stepik | 9 |
| `not_interested` | 😟 Не видит ценности | неинтересно, скучно, bosan | 8 |
| `need_to_think` | ⏰ Откладывает | подумаю, позже, nanti | 7 |
| `time_constraint` | 🕐 Проблема: время | не хватает времени, sibuk | 6 |
| `family_decision` | 👨‍👩‍👧 Семья | спрошу у жены, keluarga | 5 |
| `budget_limit` | 💸 Бюджет | бюджет, лимит, afford | 4 |
| `quality_doubt` | ✅ Сомнения | качество, результаты, hasil | 8 |
| `age_mismatch` | 👶 Возраст | возраст, usia, age | 5 |
| `technical_concern` | 💻 Техника | техника, компьютер, technical | 3 |
| `positive_signal` | ✨ Позитив | ок, согласен, setuju | 10 |

## Configuration

### Language Support

Intent Detector works with multiple languages:
- Russian: "дорого", "подумаю"
- Bahasa Indonesia: "маhal", "pikirkan"
- English: "expensive", "think about"

Mixed-language calls are supported naturally.

### Customization

Edit `backend/playbook.json` to:
1. **Add new trigger:** Add new object to JSON array
2. **Update hint:** Change `hint` field
3. **Change priority:** Adjust `priority` (higher = more important)
4. **Add keywords:** Add to `match` array
5. **Change tone:** Toggle `isPositive` (red vs green UI)

Restart backend to reload playbook.

## UI Behavior

### Appearance
- **Position:** Fixed top, centered
- **Animation:** Fade-in (0.4s), Fade-out (0.3s)
- **Duration:** Auto-dismiss after 10 seconds
- **Manual close:** Click X or OK button

### Styles
- **Attention (default):** Orange/red gradient for objections/problems
- **Positive:** Green gradient for buying signals

### Timer
- Visual timer bar at bottom shows countdown
- Animates from 100% to 0% over 10 seconds

## Performance & Reliability

### Anti-Spam
- Same trigger won't show twice within 30 seconds
- Prevents notification fatigue

### Graceful Degradation
- If trigger detection fails → no card shown (silent)
- If WebSocket fails → no assist hints (but coaching still works)

### Resource Usage
- Minimal: only regex matching on new transcript
- No LLM call (uses playbook only)
- CPU: <1ms per trigger check

## Testing

### Manual Test with Backend
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Manual Test with Frontend
```bash
cd frontend
npm run dev
```

### Trigger Test
1. Start recording
2. Say: "это очень дорого"
3. See: 💰 Red card appears with price objection hint

### Positive Trigger Test
1. Say: "звучит интересно"
2. See: ✨ Green card appears with next step hint

## Future Enhancements

- [ ] LLM-based trigger detection (semantic, not just keywords)
- [ ] Trigger analytics: which triggers most common?
- [ ] A/B testing: measure which hints most effective
- [ ] Personalization: different hints for different sales styles
- [ ] Multi-language UI (currently English fixed)
- [ ] Trigger history: show what was triggered in call
- [ ] Custom playbooks per sales team/product

## Troubleshooting

### Trigger Not Showing
1. Check backend logs: `🎯 TRIGGER DETECTED: ...`
2. Verify keyword in playbook.json
3. Check if same trigger shown in last 30s (anti-spam)
4. Restart backend to reload playbook

### Wrong Trigger Showing
- Keyword may be too generic
- Check priority (if multiple matches, highest wins)
- Edit playbook.json to adjust keywords or priority

### UI Not Appearing
1. Check frontend console for errors
2. Verify WebSocket connection (`/coach`)
3. Check `assistTrigger` state in App.tsx

## Files

```
backend/
  ├── playbook.json              ← Triggers & hints (edit this!)
  ├── utils/
  │   └── intent_detector.py     ← Detection logic
  └── main.py                    ← Integration in websocket_ingest

frontend/
  ├── src/
  │   ├── components/
  │   │   ├── InCallAssist.tsx   ← React component
  │   │   └── InCallAssist.css   ← Styling
  │   └── App.tsx                ← Integration
```

## References

- [Playbook JSON](#current-triggers-playbook) - All current triggers
- [Architecture](#architecture) - How it works
- [Config](#configuration) - How to customize
