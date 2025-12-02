# 🎯 Техническое Описание: Как Работает Детекция Выполнения Чеклиста

**Версия:** 2.0 (с NowItWorks changes)  
**Дата:** 30 ноября 2025

---

## 📋 Оглавление

1. [High-Level Overview](#1-high-level-overview)
2. [Детальный Flow](#2-детальный-flow)
3. [LLM Prompt Engineering](#3-llm-prompt-engineering)
4. [Multi-Layer Validation](#4-multi-layer-validation)
5. [Code Walkthrough](#5-code-walkthrough)
6. [Performance Metrics](#6-performance-metrics)
7. [Примеры](#7-примеры)

---

## 1. High-Level Overview

### 1.1 Общая Схема

```
┌──────────────────────────────────────────────────────────────┐
│ 1. AUDIO CAPTURE                                             │
│    Browser MediaRecorder → WebSocket /ingest                │
└───────────────────┬──────────────────────────────────────────┘
                    │ WebM audio chunks (every 3s)
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. TRANSCRIPTION                                             │
│    Faster-Whisper (Indonesian) → Text                        │
└───────────────────┬──────────────────────────────────────────┘
                    │ Indonesian text
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. ACCUMULATION                                              │
│    accumulated_transcript (last 1000 words)                  │
└───────────────────┬──────────────────────────────────────────┘
                    │ Every 5 seconds
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. ANALYSIS LOOP                                             │
│    Check incomplete items in current stage                   │
└───────────────────┬──────────────────────────────────────────┘
                    │ For each incomplete item
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. LLM CHECK (First Pass)                                    │
│    TrialClassAnalyzer.check_checklist_item()                 │
│    ├─ Build prompt with item details + extended_description │
│    ├─ Call Gemini 2.5 Flash                                 │
│    └─ Parse JSON: {completed, confidence, evidence}         │
└───────────────────┬──────────────────────────────────────────┘
                    │ If completed == True
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. GUARDS (Multi-Layer)                                      │
│    ├─ Guard 1: Confidence >= 0.8?                           │
│    ├─ Guard 2: Evidence length >= 10 chars?                 │
│    └─ Guard 3: Validate evidence with second LLM call       │
└───────────────────┬──────────────────────────────────────────┘
                    │ If all guards pass
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. MARK AS COMPLETED                                         │
│    checklist_progress[item_id] = True                        │
│    checklist_evidence[item_id] = evidence                    │
└───────────────────┬──────────────────────────────────────────┘
                    │ Broadcast update
                    ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. FRONTEND UPDATE                                           │
│    StageChecklist component → Shows ✅ with evidence         │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Детальный Flow

### 2.1 Шаг 1: Audio Capture → Transcription

**Файл:** `backend/main_trial_class.py`

```python
# WebSocket /ingest принимает аудио
@app.websocket("/ingest")
async def websocket_ingest(websocket: WebSocket):
    while True:
        # Получаем binary chunk (WebM)
        data = await websocket.receive_bytes()
        
        # Добавляем в буфер
        await audio_buffer.append(data)
        
        # Триггер транскрипции (если буфер >= 5 chunks ИЛИ 10s прошло)
        if should_transcribe():
            chunks = await audio_buffer.get_all_and_clear()
            
            # Запускаем транскрипцию
            await transcribe_audio_buffer(
                buffer=audio_buffer,
                language=transcription_language,  # "id"
                callback=handle_transcription
            )
```

**Результат:** 
- Каждые 3-10 секунд получаем новый текст
- Добавляется в `accumulated_transcript`

---

### 2.2 Шаг 2: Analysis Loop (каждые 5 секунд)

**Файл:** `backend/main_trial_class.py`

```python
async def analyze_conversation_loop():
    """Background task: анализ каждые 5 секунд"""
    while True:
        await asyncio.sleep(5)
        
        if not is_live_recording:
            continue
        
        # Получаем текущую стадию
        current_stage = get_current_stage()
        
        # Находим НЕвыполненные пункты в текущей стадии
        incomplete_items = [
            item for item in current_stage['items']
            if not checklist_progress.get(item['id'], False)
        ]
        
        # Проверяем каждый невыполненный пункт
        for item in incomplete_items:
            completed, confidence, evidence, debug_info = \
                analyzer.check_checklist_item(
                    item_id=item['id'],
                    item_content=item['content'],
                    item_type=item['type'],  # "discuss" or "say"
                    conversation_text=accumulated_transcript
                )
            
            if completed:
                # Отмечаем как выполненный
                checklist_progress[item['id']] = True
                checklist_evidence[item['id']] = evidence
                print(f"✅ Item completed: {item['content'][:50]}...")
```

**Важно:**
- Проверяются ТОЛЬКО невыполненные пункты (оптимизация)
- Проверяются ТОЛЬКО пункты текущей стадии
- Используется последние 1000 слов транскрипта (context window)

---

### 2.3 Шаг 3: LLM Check (First Pass)

**Файл:** `backend/trial_class_analyzer.py`

**Функция:** `check_checklist_item()`

#### 3.1 Построение Промпта

```python
def check_checklist_item(
    self,
    item_id: str,
    item_content: str,
    item_type: str,  # "discuss" or "say"
    conversation_text: str
) -> Tuple[bool, float, str, Dict]:
    
    # Guard 0: Слишком мало текста?
    if len(conversation_text.strip()) < 30:
        return False, 0.0, "Insufficient context", {...}
    
    # Строим промпт в зависимости от типа
    if item_type == "discuss":
        type_specific = """
        TYPE: DISCUSS/ASK
        You must find:
        ✅ A QUESTION being asked, OR
        ✅ An ANSWER that proves the question was asked
        
        GOOD examples:
        - "Anaknya umur berapa?" ✓ (direct question)
        - "Anaknya 8 tahun" ✓ (answer proves question)
        
        BAD examples:
        - "Oke, baik" ✗ (just acknowledgment)
        - "Nanti kita diskusi" ✗ (promise, not actual)
        """
    else:  # "say"
        type_specific = """
        TYPE: SAY/EXPLAIN
        You must find:
        ✅ The manager STATING or EXPLAINING something
        
        GOOD examples:
        - "Platform kami seperti game interaktif" ✓
        
        BAD examples:
        - "Mau tau cara kerja?" ✗ (asking, not explaining)
        - "Nanti saya jelaskan" ✗ (promise, not explanation)
        """
    
    # ⭐ НОВОЕ В NowItWorks: Используем extended_description
    extended_desc = item.get('extended_description', '')
    
    prompt = f"""You are a STRICT quality checker analyzing a sales call.

TASK: Check if this action was completed:
Action: "{item_content}"

{type_specific}

📝 ADDITIONAL CONTEXT (from call script):
{extended_desc}

Recent conversation (Bahasa Indonesia):
{conversation_text}

CRITICAL VALIDATION RULES:
1. Evidence must be DIRECT QUOTE from conversation
2. Evidence must CLEARLY show the action was done
3. Generic phrases ("oke", "baik", "ya") are NEVER valid
4. Greetings are NEVER valid evidence
5. If you're even 20% unsure → mark completed=false

CONFIDENCE GUIDELINES:
- 90-100%: Action CLEARLY done, perfect evidence
- 70-89%: Likely done, good evidence
- 50-69%: Possibly done, weak evidence
- <50%: Probably not done

BE EXTREMELY CONSERVATIVE. When in doubt, mark as NOT completed.

Return ONLY valid JSON:
{{
  "completed": true/false,
  "confidence": 0.0-1.0,
  "evidence": "exact quote (empty if not completed)",
  "reasoning": "WHY this proves (or doesn't prove) the action"
}}
"""
    
    # Вызываем LLM
    response = self._call_llm(prompt, temperature=0.2, max_tokens=200)
    result = json.loads(response)
```

#### 3.2 LLM API Call

```python
def _call_llm(self, prompt: str, temperature: float, max_tokens: int):
    """Call OpenRouter API with Gemini 2.5 Flash"""
    
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "google/gemini-2.5-flash-preview-09-2025",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    
    # Extract JSON if wrapped in markdown
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    
    return content
```

**Ответ LLM (пример):**

```json
{
  "completed": true,
  "confidence": 0.92,
  "evidence": "Selamat pagi Budi dan Mama. Saya Miss Sarah dari Algonova",
  "reasoning": "The tutor clearly greeted both child and parent, introduced herself in professional manner matching the greeting requirement"
}
```

---

### 2.4 Шаг 4: Multi-Layer Validation

После получения ответа от LLM применяются **3 уровня guards**:

#### Guard 1: Confidence Threshold

```python
completed = result.get("completed", False)
confidence = result.get("confidence", 0.0)
evidence = result.get("evidence", "")

debug_info = {
    "stage": "initial_check",
    "first_completed": completed,
    "first_confidence": confidence,
    "first_evidence": evidence
}

# Guard 1: Only accept high confidence
if completed and confidence < 0.8:
    debug_info["stage"] = "guard_1_low_confidence"
    return False, confidence, "Confidence too low", debug_info
```

**Цель:** Отсеять случаи, где LLM не уверена.

---

#### Guard 2: Evidence Length

```python
# Guard 2: Evidence must be substantial
if completed and len(evidence.strip()) < 10:
    debug_info["stage"] = "guard_2_evidence_too_short"
    return False, confidence, "Evidence too short", debug_info
```

**Цель:** Отсеять hallucinations (LLM говорит "completed", но не может дать evidence).

---

#### Guard 3: Evidence Validation (Second LLM Call)

```python
# Guard 3: Validate evidence relevance
if completed and confidence >= 0.7:
    validation_passed = self._validate_evidence_relevance(
        item_content=item_content,
        evidence=evidence,
        reasoning=reasoning,
        item_type=item_type
    )
    
    if not validation_passed:
        debug_info["stage"] = "guard_3_validation_failed"
        return False, confidence, "Evidence not relevant", debug_info
```

**Цель:** Double-check, что evidence действительно доказывает completion.

---

### 2.5 Шаг 5: Evidence Validation (Детально)

**Функция:** `_validate_evidence_relevance()`

#### 5.1 Hard-Coded Filters

```python
def _validate_evidence_relevance(
    self,
    item_content: str,
    evidence: str,
    reasoning: str,
    item_type: str
) -> bool:
    
    print(f"🔍 VALIDATING: '{item_content[:60]}...'")
    print(f"   Evidence: '{evidence[:100]}...'")
    
    # Filter 1: Empty evidence
    if not evidence or len(evidence.strip()) < 5:
        print(f"🚫 Rejected: Evidence too short")
        return False
    
    evidence_lower = evidence.lower().strip()
    
    # Filter 2: Generic phrases (NEVER valid)
    invalid_phrases = [
        "oke", "ok", "baik", "ya", 
        "halo", "hai", "selamat pagi",
        "terima kasih", "sama-sama"
    ]
    
    for phrase in invalid_phrases:
        if evidence_lower == phrase or evidence_lower == phrase + ".":
            print(f"🚫 Rejected: Generic phrase '{phrase}'")
            return False
    
    # Filter 3: Self-introductions (unless action is about greetings)
    introduction_patterns = [
        "nama saya", "saya adalah", 
        "perkenalkan", "mr.", "ms."
    ]
    
    if any(p in evidence_lower for p in introduction_patterns):
        action_lower = item_content.lower()
        if not any(w in action_lower for w in ["greet", "introduce", "perkenalkan"]):
            print(f"🚫 Rejected: Self-introduction, not relevant")
            return False
    
    # Filter 4: Too short (< 3 words)
    word_count = len(evidence.split())
    if word_count < 3:
        print(f"🚫 Rejected: Too short ({word_count} words)")
        return False
```

#### 5.2 Semantic Keyword Check

```python
    # Filter 5: Semantic keyword matching
    action_lower = item_content.lower()
    
    keyword_checks = [
        # Age/Grade questions
        {
            "triggers": ["age", "umur", "usia", "grade", "kelas"],
            "required_in_evidence": ["umur", "tahun", "kelas", "sd", "smp"]
        },
        # Interests
        {
            "triggers": ["interest", "suka", "hobi"],
            "required_in_evidence": ["suka", "hobi", "main", "game", "favorit"]
        },
        # Concerns
        {
            "triggers": ["concern", "masalah", "khawatir"],
            "required_in_evidence": ["khawatir", "masalah", "kesulitan", "susah"]
        },
        # Goals
        {
            "triggers": ["goal", "tujuan", "harapan"],
            "required_in_evidence": ["tujuan", "ingin", "mau", "supaya", "bisa"]
        }
    ]
    
    for check in keyword_checks:
        if any(trigger in action_lower for trigger in check["triggers"]):
            has_required = any(
                word in evidence_lower 
                for word in check["required_in_evidence"]
            )
            
            if not has_required:
                print(f"🚫 Rejected: Missing semantic keywords")
                return False
```

**Цель:** Убедиться, что evidence семантически связана с action.

**Пример:**
- Action: "Ask about child's age"
- Evidence: "Oke, baik" ❌ — нет слов про возраст
- Evidence: "Anaknya umur 8 tahun" ✅ — есть "umur" или "tahun"

---

#### 5.3 Second LLM Validation Call

```python
    # Final validation: Second LLM call
    validation_prompt = f"""You are a STRICT evidence validator.

REQUIRED ACTION:
"{item_content}"

PROVIDED EVIDENCE:
"{evidence}"

ORIGINAL REASONING:
"{reasoning}"

{type_check}  # Type-specific instructions

CRITICAL CHECKS:
1. Evidence contains actual content (not "oke", "ya")?
2. Evidence SEMANTICALLY matches the action?
3. Evidence is specific enough?
4. Evidence matches action type (discuss vs explain)?

EXAMPLES OF INVALID MATCHING:
❌ Action: "Ask child's age"
   Evidence: "Oke, selamat datang"
   → NO semantic connection

❌ Action: "Explain curriculum"
   Evidence: "Mau tau kurikulum?"
   → Asking, not explaining

EXAMPLES OF VALID MATCHING:
✅ Action: "Ask child's age"
   Evidence: "Anaknya berapa tahun?"
   → Direct question

✅ Action: "Identify concerns"
   Evidence: "Papa khawatir anak kurang fokus"
   → Clearly states concern

BE EXTREMELY STRICT. If ANY doubt, mark as invalid.

Return ONLY valid JSON:
{{
  "is_valid": true/false,
  "explanation": "why evidence does/doesn't prove action"
}}
"""
    
    response = self._call_llm(validation_prompt, temperature=0.05, max_tokens=150)
    result = json.loads(response)
    
    is_valid = result.get("is_valid", False)
    explanation = result.get("explanation", "")
    
    if not is_valid:
        print(f"🔍 Validation REJECTED: {explanation}")
    else:
        print(f"✅ Validation PASSED: {explanation}")
    
    return is_valid
```

**Ответ LLM (пример REJECTED):**

```json
{
  "is_valid": false,
  "explanation": "Evidence 'Oke, selamat datang' is just greeting acknowledgment with no semantic connection to asking about child's age. No age-related keywords present."
}
```

**Ответ LLM (пример PASSED):**

```json
{
  "is_valid": true,
  "explanation": "Evidence 'Anaknya berapa tahun sekarang?' is direct question about child's age, matching the required action perfectly. Contains age keyword 'tahun'."
}
```

---

### 2.6 Шаг 6: Mark as Completed

Если все guards пройдены:

```python
# All guards passed!
debug_info["stage"] = "accepted"
debug_info["final_decision"] = "completed"

# Mark as completed globally
checklist_progress[item['id']] = True
checklist_evidence[item['id']] = evidence
checklist_last_check[item['id']] = time.time()

# Add to debug log
debug_logs.append({
    "timestamp": datetime.now().isoformat(),
    "type": "checklist_check",
    "item_id": item['id'],
    "item_content": item['content'][:50],
    "completed": True,
    "confidence": confidence,
    "evidence": evidence,
    "debug_info": debug_info
})

return True, confidence, evidence, debug_info
```

---

### 2.7 Шаг 7: Broadcast to Frontend

```python
# Build update message
update = {
    "type": "update",
    "callElapsedSeconds": int(time.time() - call_start_time),
    "currentStageId": current_stage_id,
    "stages": build_stages_with_progress(),  # Includes completed status
    "clientCard": client_card_data,
    "debugLog": debug_logs[-20:]  # Last 20 logs
}

# Send to all connected /coach WebSockets
for ws in coach_connections:
    try:
        await ws.send_json(update)
    except Exception as e:
        print(f"⚠️ Failed to send update: {e}")
```

---

### 2.8 Шаг 8: Frontend Display

**Файл:** `frontend/src/components/StageChecklist.tsx`

```typescript
{stage.items.map(item => (
    <div className={`checklist-item ${item.completed ? 'completed' : ''}`}>
        <input 
            type="checkbox" 
            checked={item.completed}
            disabled
        />
        
        <span className="item-content">
            {item.content}
        </span>
        
        {item.completed && item.evidence && (
            <div className="evidence-popup">
                💬 Evidence: {item.evidence}
            </div>
        )}
    </div>
))}
```

**UI эффект:**
- ✅ Чекбокс становится активным
- 🟢 Элемент подсвечивается зеленым
- 💬 При hover показывается evidence quote

---

## 3. LLM Prompt Engineering

### 3.1 Ключевые Компоненты Промпта

#### 1. Type-Specific Instructions

**Для "discuss" (вопросы):**
```
You must find:
✅ A QUESTION being asked, OR
✅ An ANSWER that proves the question was asked

REJECT if:
- Just acknowledgment ("oke")
- Promise to discuss ("nanti")
```

**Для "say" (объяснения):**
```
You must find:
✅ Manager STATING or EXPLAINING

REJECT if:
- Asking a question (not stating)
- Promise to explain ("nanti saya jelaskan")
```

---

#### 2. Extended Description (NEW в NowItWorks)

Каждый item теперь имеет детальное описание:

```python
{
    "id": "item_greet_client",
    "type": "say",
    "content": "Greet client warmly and introduce yourself",
    "extended_description": """
    The core objective is to ensure tutor starts with positive demeanor.
    
    AI should look for keywords:
    - Greetings: 'hello', 'selamat pagi', 'welcome'
    - Introduction: 'nama saya', 'saya adalah'
    - Professional tone: 'Algonova', 'International School'
    
    GOOD example:
    'Selamat pagi! Saya Miss Sarah dari Algonova International IT School'
    
    BAD example:
    'Oke' (just acknowledgment, not greeting)
    """
}
```

**Цель:** Дать LLM больше контекста о том, что именно искать.

---

#### 3. Anti-Hallucination Rules

```
CRITICAL VALIDATION RULES:
1. Evidence MUST be direct quote
2. Evidence MUST clearly show action done
3. Generic phrases are NEVER valid
4. Greetings (alone) are NEVER valid for non-greeting actions
5. If 20% unsure → mark as NOT completed
```

---

#### 4. Confidence Guidelines

```
- 90-100%: CLEARLY done, perfect evidence
- 70-89%: Likely done, good evidence
- 50-69%: Possibly done, weak evidence
- <50%: Probably not done
```

**Важно:** Используется в Guard 1 (threshold = 0.8).

---

#### 5. Few-Shot Examples

```
EXAMPLES:

✅ GOOD:
Action: "Ask about child's age"
Evidence: "Anaknya berapa tahun?"
Reasoning: Direct question about age

❌ BAD:
Action: "Ask about child's age"
Evidence: "Oke, selamat datang"
Reasoning: Just greeting, no age question
```

---

### 3.2 Prompt Evolution

**Версия 1.0 (старая):**
- Простой prompt без type-specific instructions
- Нет extended_description
- Только 1 LLM call
- Много false positives

**Версия 2.0 (текущая, NowItWorks):**
- ✅ Type-specific instructions (discuss vs say)
- ✅ Extended descriptions из CSV
- ✅ Multi-layer validation (3 guards)
- ✅ Second LLM call для validation
- ✅ Hard-coded filters
- ✅ Semantic keyword matching

**Результат:** 
- Меньше false positives (~80% reduction)
- Выше precision, но немного ниже recall
- Больше latency (+1-2s per item), но лучше качество

---

## 4. Multi-Layer Validation

### 4.1 Зачем Нужна Multi-Layer?

**Проблема:** LLM может hallucinate или ошибаться.

**Примеры ошибок:**
1. **False Positive:** "Oke, baik" → "Greet client" ✓ ❌
2. **Weak Evidence:** "Nanti saya jelaskan" → "Explain platform" ✓ ❌
3. **Wrong Context:** "Miss Sarah perkenalkan" → "Ask child's name" ✓ ❌

**Решение:** Несколько уровней проверки.

---

### 4.2 Уровни Validation

```
┌─────────────────────────────────────────────────────┐
│ Level 0: Context Length Check                       │
│ ├─ conversation_text < 30 chars? → REJECT          │
│ └─ Purpose: Skip if not enough context             │
└────────────────┬────────────────────────────────────┘
                 │ PASS
                 ▼
┌─────────────────────────────────────────────────────┐
│ Level 1: First LLM Call                             │
│ ├─ Build prompt with type-specific + extended desc │
│ ├─ Call Gemini 2.5 Flash                          │
│ └─ Get: {completed, confidence, evidence}          │
└────────────────┬────────────────────────────────────┘
                 │ completed == True?
                 ▼
┌─────────────────────────────────────────────────────┐
│ Level 2: Confidence Threshold                       │
│ ├─ confidence >= 0.8? → PASS                       │
│ └─ confidence < 0.8? → REJECT                      │
└────────────────┬────────────────────────────────────┘
                 │ PASS
                 ▼
┌─────────────────────────────────────────────────────┐
│ Level 3: Evidence Length                            │
│ ├─ len(evidence) >= 10? → PASS                     │
│ └─ len(evidence) < 10? → REJECT                    │
└────────────────┬────────────────────────────────────┘
                 │ PASS
                 ▼
┌─────────────────────────────────────────────────────┐
│ Level 4: Hard-Coded Filters                         │
│ ├─ Generic phrases? ("oke", "baik") → REJECT      │
│ ├─ Self-intro? (not greeting action) → REJECT     │
│ ├─ Too short? (< 3 words) → REJECT                │
│ └─ Missing semantic keywords? → REJECT             │
└────────────────┬────────────────────────────────────┘
                 │ PASS
                 ▼
┌─────────────────────────────────────────────────────┐
│ Level 5: Second LLM Validation                      │
│ ├─ Build validation prompt                         │
│ ├─ Call Gemini 2.5 Flash (temperature=0.05)       │
│ ├─ Get: {is_valid, explanation}                   │
│ └─ is_valid == True? → ACCEPT                     │
└────────────────┬────────────────────────────────────┘
                 │ ALL PASSED
                 ▼
┌─────────────────────────────────────────────────────┐
│ ✅ MARK AS COMPLETED                                │
└─────────────────────────────────────────────────────┘
```

---

### 4.3 Trade-offs

| Параметр | Single-Layer | Multi-Layer (current) |
|----------|--------------|----------------------|
| **Precision** | 60-70% | 85-95% |
| **Recall** | 90-95% | 75-85% |
| **False Positives** | High | Very Low |
| **False Negatives** | Low | Medium |
| **Latency** | ~1-2s | ~2-4s |
| **Cost** | Low | Medium |

**Вывод:** Мы жертвуем recall (некоторые valid items не детектируются) ради высокой precision (почти нет false positives).

**Rationale:** Лучше пропустить некоторые items, чем показывать fake completions.

---

## 5. Code Walkthrough

### 5.1 Entry Point

**Файл:** `backend/main_trial_class.py`

```python
# Background task запускается при старте FastAPI
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(analyze_conversation_loop())

async def analyze_conversation_loop():
    """Main analysis loop - runs every 5 seconds"""
    while True:
        await asyncio.sleep(5)
        
        if not is_live_recording:
            continue
        
        # Get current stage
        current_stage = next(
            (s for s in call_structure if s['id'] == current_stage_id),
            None
        )
        
        if not current_stage:
            continue
        
        # Find incomplete items
        incomplete_items = [
            item for item in current_stage['items']
            if not checklist_progress.get(item['id'], False)
        ]
        
        # Check each item
        for item in incomplete_items:
            await check_and_update_item(item)
```

---

### 5.2 Item Checking

```python
async def check_and_update_item(item: Dict):
    """Check single item and update if completed"""
    
    # Get analyzer
    analyzer = get_trial_class_analyzer()
    
    # Check item
    completed, confidence, evidence, debug_info = \
        analyzer.check_checklist_item(
            item_id=item['id'],
            item_content=item['content'],
            item_type=item['type'],
            conversation_text=accumulated_transcript
        )
    
    # Log debug info
    debug_logs.append({
        "timestamp": datetime.now().isoformat(),
        "type": "checklist_check",
        "item_id": item['id'],
        "completed": completed,
        "confidence": confidence,
        "evidence": evidence,
        "debug_info": debug_info
    })
    
    # Update if completed
    if completed:
        checklist_progress[item['id']] = True
        checklist_evidence[item['id']] = evidence
        checklist_last_check[item['id']] = time.time()
        
        print(f"✅ COMPLETED: {item['content'][:60]}...")
        print(f"   Evidence: {evidence[:100]}...")
        
        # Broadcast update to frontend
        await broadcast_update()
```

---

### 5.3 LLM Analyzer

**Файл:** `backend/trial_class_analyzer.py`

**Класс:** `TrialClassAnalyzer`

```python
class TrialClassAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = "google/gemini-2.5-flash-preview-09-2025"
        self.call_structure = get_default_call_structure()
    
    def check_checklist_item(self, ...):
        # 1. Build prompt
        prompt = self._build_check_prompt(...)
        
        # 2. Call LLM
        response = self._call_llm(prompt, temperature=0.2, max_tokens=200)
        result = json.loads(response)
        
        # 3. Apply guards
        if not self._apply_guards(result):
            return False, ...
        
        # 4. Validate evidence
        if not self._validate_evidence_relevance(...):
            return False, ...
        
        # 5. Return success
        return True, confidence, evidence, debug_info
```

---

## 6. Performance Metrics

### 6.1 Timing

| Этап | Время | Частота |
|------|-------|---------|
| Audio chunk | 3s | Continuous |
| Transcription | 3-5s | Every 5-10s |
| Analysis loop | - | Every 5s |
| Single item check (LLM #1) | 1-2s | Per incomplete item |
| Validation check (LLM #2) | 0.5-1s | If completed=True |
| **Total per item** | **1.5-3s** | Max 5-10 items/cycle |
| Frontend update | <100ms | After each analysis |

### 6.2 Cost

**Per Item Check:**
- First LLM call: ~300-400 tokens
  - Prompt: ~250-350 tokens (with extended_description)
  - Response: ~50 tokens
- Validation LLM call: ~200 tokens
  - Prompt: ~150 tokens
  - Response: ~50 tokens

**Total: ~500-600 tokens per item check**

**Cost per item:** $0.10 / 1M × 600 = **$0.00006** (0.006 cents)

**Typical call:**
- 30 items total
- 5-10 items checked per cycle
- 10 cycles before completion
- Total: 50-100 LLM calls
- **Cost: $0.003 - $0.006 per call** (0.3-0.6 cents)

---

### 6.3 Accuracy Metrics (estimated)

| Метрика | Значение | Комментарий |
|---------|----------|-------------|
| **Precision** | 85-95% | Few false positives |
| **Recall** | 75-85% | Some items missed |
| **F1 Score** | ~0.80 | Balanced |
| **False Positive Rate** | <5% | Very low |
| **False Negative Rate** | 15-25% | Conservative approach |

**Note:** Метрики основаны на manual testing, не на formal evaluation dataset.

---

## 7. Примеры

### 7.1 Пример: Успешная Детекция

**Item:**
```json
{
  "id": "ask_child_age",
  "type": "discuss",
  "content": "Ask about the child's age and current grade",
  "extended_description": "Look for questions like 'berapa tahun', 'kelas berapa', or answers that indicate age was asked"
}
```

**Transcript:**
```
TCM: "Halo Budi! Selamat siang Mama. Saya Miss Sarah dari Algonova."
Parent: "Halo Miss Sarah."
TCM: "Budi sekarang umurnya berapa tahun ya?"
Parent: "Budi 10 tahun, kelas 5 SD."
```

**LLM Response #1:**
```json
{
  "completed": true,
  "confidence": 0.95,
  "evidence": "Budi sekarang umurnya berapa tahun ya?",
  "reasoning": "TCM directly asked about child's age using 'umurnya berapa tahun', and got answer '10 tahun, kelas 5 SD'"
}
```

**Guard Results:**
- ✅ Confidence: 0.95 >= 0.8
- ✅ Evidence length: 42 chars >= 10
- ✅ Hard-coded filters: Contains "umur", "tahun" (age keywords)

**LLM Validation #2:**
```json
{
  "is_valid": true,
  "explanation": "Evidence contains direct question about age with keyword 'umurnya berapa tahun', which perfectly matches the required action"
}
```

**Result:** ✅ **COMPLETED**

---

### 7.2 Пример: Отклонение (Generic Phrase)

**Item:**
```json
{
  "id": "greet_client",
  "type": "say",
  "content": "Greet the client warmly and introduce yourself"
}
```

**Transcript:**
```
Parent: "Halo?"
TCM: "Oke, baik."
```

**LLM Response #1:**
```json
{
  "completed": true,
  "confidence": 0.75,
  "evidence": "Oke, baik",
  "reasoning": "Tutor responded to parent's greeting"
}
```

**Guard Results:**
- ✅ Confidence: 0.75 >= 0.8 ❌ **REJECTED at Guard 1**

**Result:** ❌ **NOT COMPLETED** (low confidence)

---

### 7.3 Пример: Отклонение (Evidence Validation Failed)

**Item:**
```json
{
  "id": "explain_platform",
  "type": "say",
  "content": "Explain how the learning platform works"
}
```

**Transcript:**
```
TCM: "Mama mau tau platform kami seperti apa?"
Parent: "Iya, boleh dijelaskan."
```

**LLM Response #1:**
```json
{
  "completed": true,
  "confidence": 0.85,
  "evidence": "Mama mau tau platform kami seperti apa?",
  "reasoning": "TCM mentioned the platform"
}
```

**Guard Results:**
- ✅ Confidence: 0.85 >= 0.8
- ✅ Evidence length: 39 chars >= 10
- ✅ Hard-coded filters: No generic phrases

**LLM Validation #2:**
```json
{
  "is_valid": false,
  "explanation": "Evidence is a QUESTION ('mau tau...seperti apa?'), not an EXPLANATION. Action requires EXPLAINING how platform works, not ASKING if parent wants to know. Wrong type."
}
```

**Result:** ❌ **NOT COMPLETED** (validation failed - question, not explanation)

---

### 7.4 Пример: Edge Case (Self-Introduction)

**Item:**
```json
{
  "id": "ask_child_name",
  "type": "discuss",
  "content": "Ask and confirm the child's name"
}
```

**Transcript:**
```
TCM: "Selamat pagi! Nama saya Miss Sarah dari Algonova."
```

**LLM Response #1:**
```json
{
  "completed": true,
  "confidence": 0.80,
  "evidence": "Nama saya Miss Sarah dari Algonova",
  "reasoning": "Name is mentioned in the conversation"
}
```

**Guard Results:**
- ✅ Confidence: 0.80 >= 0.8
- ✅ Evidence length: 35 chars >= 10
- ❌ Hard-coded filters: Contains "nama saya" (self-introduction pattern)
  - Action is "ask child's name", not "introduce yourself"
  - **REJECTED at Guard 4**

**Result:** ❌ **NOT COMPLETED** (self-introduction, not asking child's name)

---

## 📊 Summary

### Ключевые Компоненты:

1. **Real-time Transcription** (Whisper)
2. **Context Window** (last 1000 words)
3. **Analysis Loop** (every 5s)
4. **LLM First Pass** (Gemini 2.5 Flash)
5. **Multi-Layer Guards** (5 levels)
6. **Evidence Validation** (Second LLM call)
7. **Frontend Update** (WebSocket broadcast)

### Преимущества:

- ✅ Высокая precision (85-95%)
- ✅ Низкий false positive rate (<5%)
- ✅ Extended descriptions дают контекст
- ✅ Multi-layer validation предотвращает hallucinations
- ✅ Type-aware (discuss vs say)
- ✅ Semantic keyword matching

### Недостатки:

- ⚠️ Latency 2-4s per item (2 LLM calls)
- ⚠️ Cost ~0.5 cents per call
- ⚠️ Recall 75-85% (некоторые items пропускаются)
- ⚠️ Зависимость от качества transcript

### Возможные Улучшения:

1. **Batch checking** — проверять несколько items одним LLM call
2. **Caching** — не перепроверять недавно проверенные items
3. **Adaptive thresholds** — динамические confidence thresholds
4. **Fine-tuned model** — специализированная модель для detection
5. **Streaming LLM** — использовать streaming для меньшей latency

---

**Документ обновлен:** 30 ноября 2025  
**Версия:** 2.0 (NowItWorks)  
**Статус:** Production



