import asyncio
import json
import time
from typing import Set, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
from dotenv import load_dotenv
import os

from insights.client_insight import analyze_client_text, reset_analyzer
from utils.youtube_processor import process_youtube_url
from utils.audio_buffer import AudioBuffer
from utils.realtime_transcriber import transcribe_audio_buffer
from utils.llm_analyzer import get_llm_analyzer
from utils.intent_detector import get_intent_detector
from sales_checklist import (
    detect_stage_from_text,
    check_checklist_item,
    generate_next_step_recommendation,
    get_checklist_structure
)

load_dotenv()

app = FastAPI()

# CORS для локалки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальное состояние
coach_connections: Set[WebSocket] = set()
last_hint: str = ""
last_prob: float = 0.0
last_llm_call: float = 0.0
last_response_time: float = 0.0
cached_response: Optional[Dict] = None
last_client_insight: Optional[Dict] = None
current_stage: str = "greeting"
checklist_progress: Dict[str, bool] = {}  # Чеклист заполняется ТОЛЬКО реальной транскрипцией
checklist_completion_cache: Dict[str, float] = {}  # Cache for when items were completed (to prevent duplicates)
checklist_evidence: Dict[str, str] = {}  # Evidence text for each completed item
checklist_llm_cache: Dict[str, Dict] = {}  # Cache LLM responses for 60 seconds (item_id -> {timestamp, result})
accumulated_transcript: str = ""
transcription_language: str = "id"  # Default: Bahasa Indonesia
is_live_recording: bool = False  # Флаг живой записи
use_llm_analysis: bool = os.getenv("USE_LLM_ANALYSIS", "true").lower() == "true"
llm_analyzer = get_llm_analyzer()  # Initialize LLM analyzer
intent_detector = get_intent_detector() # Initialize Intent Detector

# Мок-диалог (пока ASR не подключён)
mock_dialogue = [
    "Client: My child is 10 years old and loves Minecraft.",
    "Manager: Have you done coding before?",
    "Client: No, but it sounds fun and interesting for future.",
    "Manager: What are your goals?",
    "Client: I want him to think logically and be more creative.",
    "Manager: Great! Let me show you our program...",
    "Client: How much does it cost? We're on a budget.",
]

# Симуляция клиентских высказываний для анализа
mock_client_utterances = [
    "My child is 10 years old and loves Minecraft",
    "No, but it sounds fun and interesting for future",
    "I want him to think logically and be more creative",
    "How much does it cost? We're on a budget",
]
current_mock_index = 0

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def calculate_fallback_prob() -> float:
    """Простая заглушка для вероятности"""
    slots_filled = 2  # пример
    slots_total = 5
    prob = min(1.0, 0.2 * slots_filled / slots_total + 0.8 * 0.7)
    return round(prob, 2)


def call_openrouter(dialogue: str) -> Dict:
    """Вызов OpenRouter API с Claude Sonnet 4.5"""
    if not OPENROUTER_API_KEY:
        print("⚠️  OPENROUTER_API_KEY не установлен, используем фолбэк")
        return {
            "hint": "Уточните у клиента опыт ребёнка и предложите пробный урок",
            "prob": calculate_fallback_prob()
        }
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "Ты коуч для сейлз-менеджера. Отвечай ТОЛЬКО валидным JSON "
        "{\"hint\":\"...\",\"prob\":0..1}. Если данных мало — всё равно выдай "
        "валидный JSON с осмысленным hint. Никакого текста вне JSON."
    )
    
    payload = {
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Диалог:\n{dialogue}\nВыдай JSON."}
        ],
        "temperature": 0.2,
        "max_tokens": 120,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        
        # Валидация ключей
        if "hint" not in result:
            result["hint"] = "Продолжайте задавать уточняющие вопросы"
        if "prob" not in result or not isinstance(result["prob"], (int, float)):
            result["prob"] = calculate_fallback_prob()
        
        # Нормализация prob
        result["prob"] = max(0.0, min(1.0, float(result["prob"])))
        result["prob"] = round(result["prob"], 2)
        
        return result
        
    except Exception as e:
        print(f"❌ OpenRouter error: {e}")
        return {
            "hint": "Уточните потребности клиента и предложите решение",
            "prob": calculate_fallback_prob()
        }


def should_send_hint(new_hint: str, old_hint: str) -> bool:
    """Проверка дедупликации: слать только если разница > 10 символов"""
    if not old_hint:
        return True
    
    # Простая проверка по длине разницы
    diff = abs(len(new_hint) - len(old_hint))
    if diff > 10:
        return True
    
    # Проверка по содержимому (если длина похожа)
    if new_hint != old_hint:
        # Подсчёт различающихся символов
        max_len = max(len(new_hint), len(old_hint))
        differences = sum(1 for i in range(max_len) 
                         if i >= len(new_hint) or i >= len(old_hint) 
                         or new_hint[i] != old_hint[i])
        return differences > 10
    
    return False


async def orchestrate():
    """
    Оркестрация ТОЛЬКО для демо-режима (когда нет живой записи)
    При реальной транскрипции эта функция НЕ используется!
    """
    global last_hint, last_prob, last_llm_call, last_response_time, cached_response
    global last_client_insight, current_mock_index
    global current_stage, checklist_progress, accumulated_transcript
    
    # Эта функция вызывается ТОЛЬКО в демо-режиме
    # Не используется при live recording!
    pass


@app.websocket("/ingest")
async def websocket_ingest(websocket: WebSocket):
    """Принимает audio chunks и транскрибирует в реальном времени"""
    global transcription_language, is_live_recording, checklist_progress, current_stage
    global last_client_insight, last_hint, last_prob, accumulated_transcript
    global checklist_completion_cache
    
    # Очищаем состояние при новой записи
    is_live_recording = True
    checklist_progress = {}
    checklist_completion_cache = {}  # Clear cache on new session
    checklist_evidence = {}  # Clear evidence on new session
    checklist_llm_cache = {}  # Clear LLM cache on new session
    current_stage = "greeting"
    last_client_insight = {}  # Reset insights
    accumulated_transcript = ""  # Reset accumulated transcript
    reset_analyzer() # Reset analyzer when starting a new recording session
    
    await websocket.accept()
    print("🎤 /ingest подключен - real-time transcription enabled")
    print("🔄 Checklist reset for new live recording")
    
    # Создаем буфер для накопления аудио
    audio_buffer = AudioBuffer(interval_seconds=5.0)  # Транскрибируем каждые 5 секунд (быстрее!)
    last_orchestrate = 0.0
    ready_for_transcription = False
    
    print(f"🎧 Audio buffer initialized: transcribing every {audio_buffer.interval_seconds}s")
    
    try:
        while True:
            # Принимаем данные универсально
            message = await websocket.receive()
            ready_for_transcription = False  # Сбрасываем флаг
            
            # Проверяем тип сообщения
            if 'text' in message:
                # Это текстовое сообщение (настройки)
                try:
                    data = json.loads(message['text'])
                    if data.get('type') == 'set_language':
                        transcription_language = data.get('language', 'id')
                        print(f"🌍 Language set to: {transcription_language}")
                except Exception as e:
                    print(f"⚠️ Не удалось обработать настройку: {e}")
                continue
                
            elif 'bytes' in message:
                # Это бинарные аудио данные
                data = message['bytes']
                print(f"📥 Получен audio chunk: {len(data)} bytes")
                
                # Добавляем в буфер
                ready_for_transcription = audio_buffer.add_chunk(data)
            else:
                continue
            
            # Если накопилось достаточно аудио - транскрибируем
            if ready_for_transcription:
                print(f"🎯 Triggering real-time transcription...")
                system_status.audio_capture_active = True
                system_status.last_audio_chunk_time = datetime.now().isoformat()
                
                try:
                    # Получаем аудио данные
                    buffer_data = audio_buffer.get_audio_data()
                    
                    # Проверяем что данных достаточно
                    if len(buffer_data) < 80000:
                        print(f"⚠️ Buffer too small: {len(buffer_data)} bytes, skipping")
                        audio_buffer.clear()
                        continue
                    
                    print(f"🎯 Starting transcription: {len(buffer_data)} bytes")
                    
                    # Запускаем транскрипцию асинхронно чтобы не блокировать WebSocket
                    import asyncio
                    loop = asyncio.get_event_loop()
                    
                    # Транскрибируем в отдельном потоке с выбранным языком
                    transcript = await loop.run_in_executor(
                        None,
                        transcribe_audio_buffer,
                        buffer_data,
                        transcription_language  # Используем глобальный язык
                    )
                    
                    if transcript:
                        system_status.transcription_count += 1
                        system_status.last_transcription_time = datetime.now().isoformat()
                        print(f"\n🎯 TRANSCRIPTION #{system_status.transcription_count}:")
                        print(f"\n{'='*60}")
                        print(f"📝 REAL-TIME TRANSCRIPT ({len(transcript)} chars):")
                        print(f"{'='*60}")
                        print(transcript)
                        print(f"{'='*60}\n")
                        
                        # Накапливаем транскрипцию
                        accumulated_transcript += " " + transcript
                        words = accumulated_transcript.split()
                        if len(words) > 500:
                            accumulated_transcript = " ".join(words[-500:])
                        
                        # Initialize variables for this iteration
                        next_step = "Listen and understand client needs"
                        local_use_llm = use_llm_analysis  # Local copy of global flag
                        
                        # === SPEAKER DIARIZATION (LLM-based) ===
                        if local_use_llm:
                            print("🧠 LLM SEMANTIC ANALYSIS:")
                            try:
                                segments = llm_analyzer.identify_speakers(transcript)
                                system_status.lm_analysis_count += 1
                                client_segments = [s['text'] for s in segments if s.get('speaker') == 'client']
                                sales_segments = [s['text'] for s in segments if s.get('speaker') == 'sales']
                                
                                print(f"   👤 Client: {len(client_segments)} segments")
                                print(f"   💼 Sales: {len(sales_segments)} segments")
                                
                                # Analyze ONLY client speech
                                client_text = " ".join(client_segments)
                                if client_text:
                                    print(f"\n   👤 CLIENT TEXT FOR ANALYSIS ({len(client_text)} chars):")
                                    print(f"   '{client_text}'")
                                    print("🧠 Analyzing client sentiment with LLM...")
                                    last_client_insight = llm_analyzer.analyze_client_sentiment(
                                        client_text, 
                                        accumulated_transcript[-500:]
                                    )
                                    print(f"   Emotion: {last_client_insight.get('emotion')}")
                                    print(f"   Objections: {last_client_insight.get('objections')}")
                                    print(f"   Interests: {last_client_insight.get('interests')}")
                            except Exception as e:
                                print(f"⚠️ LLM analysis failed: {e}")
                                system_status.lm_analysis_errors += 1
                                system_status.last_error = str(e)
                                local_use_llm = False
                        
                        if not local_use_llm:
                            # Fallback: keyword-based analysis
                            # For INSIGHTS: analyze only CLIENT speech
                            sentences = [s.strip() for s in transcript.split('.') if s.strip()]
                            
                            client_text_parts = []
                            for sentence in sentences:
                                # Check if this looks like client speaking (not "Sales:" or similar)
                                lower_sentence = sentence.lower()
                                is_client_speaking = (
                                    not any(prefix in lower_sentence for prefix in ['sales:', 'seller:', 'manager:', 'i ', 'we ']) or
                                    any(prefix in lower_sentence for prefix in ['client:', 'customer:', 'you:', 'me:', 'my ', 'i need', 'i want', 'i think'])
                                )
                                
                                if is_client_speaking and len(sentence) > 10:
                                    client_text_parts.append(sentence)
                            
                            # Analyze only accumulated client text for INSIGHTS
                            if client_text_parts:
                                combined_client_text = " ".join(client_text_parts)
                                # Use LLM for comprehensive analysis
                                try:
                                    last_client_insight = llm_analyzer.analyze_client_sentiment(
                                        combined_client_text,
                                        accumulated_transcript[-500:]
                                    )
                                    system_status.lm_analysis_count += 1
                                except Exception as e:
                                    print(f"   ⚠️ LLM sentiment analysis failed: {e}")
                                    system_status.lm_analysis_errors += 1
                                    # Fallback: use keyword analysis
                                    last_client_insight = analyze_client_text(combined_client_text, is_client=True)
                        
                        # Определяем текущий этап
                        if local_use_llm and last_client_insight:
                            current_stage = last_client_insight.get('stage_hint', 'profiling')
                        else:
                            current_stage = detect_stage_from_text(accumulated_transcript)
                        
                        # === CHECKLIST (LLM-based semantic matching) ===
                        checklist = get_checklist_structure()
                        newly_completed = []
                        checked_items = []
                        current_time = time.time()
                        cache_timeout = 30  # Don't re-check the same item for 30 seconds
                        
                        print(f"\n📋 Checking checklist (LLM={local_use_llm})...")
                        
                        for stage_key, stage_data in checklist.items():
                            for item in stage_data['items']:
                                item_id = item['id']
                                
                                # Skip if already completed - NEVER check again!
                                if item_id in checklist_progress and checklist_progress[item_id]:
                                    continue
                                
                                # Skip if checked too recently (within cache_timeout)
                                if item_id in checklist_completion_cache:
                                    time_since_check = current_time - checklist_completion_cache[item_id]
                                    if time_since_check < cache_timeout:
                                        print(f"   ⏳ Skipping {item_id} (checked {time_since_check:.0f}s ago)")
                                        continue
                                
                                # Update cache - mark as "last checked at this time"
                                checklist_completion_cache[item_id] = current_time
                                
                                # Use ALL speech for checklist checking (both client AND sales)
                                # Because checklist items include:
                                # - Sales actions: "Introduce yourself", "Ask about budget"
                                # - Client responses: understood by checking for affirmations in full text
                                check_text = accumulated_transcript[-2000:]  # Use full recent transcript, not just client speech
                                
                                # Check LLM cache first (60 second TTL)
                                llm_cache_ttl = 60
                                if item_id in checklist_llm_cache:
                                    cache_entry = checklist_llm_cache[item_id]
                                    time_since_cache = current_time - cache_entry['timestamp']
                                    if time_since_cache < llm_cache_ttl:
                                        completed = cache_entry['result']
                                        if completed:
                                            checklist_progress[item_id] = True
                                            newly_completed.append(item['text'])
                                            evidence_sentences = [s.strip() for s in check_text.split('.') if s.strip()]
                                            evidence = '. '.join(evidence_sentences[-2:]) if evidence_sentences else "Item completed"
                                            checklist_evidence[item_id] = evidence
                                            print(f"   ✅ COMPLETED (cached): {item['text']}")
                                        else:
                                            print(f"   ❌ Not yet (cached): {item['text']}")
                                        continue  # Skip LLM call
                                
                                if local_use_llm:
                                    # LLM semantic check
                                    try:
                                        completed, reason = llm_analyzer.check_checklist_item_semantic(
                                            item['text'],
                                            check_text,  # Use only client speech
                                            transcription_language
                                        )
                                        if completed:
                                            checklist_progress[item_id] = True
                                            newly_completed.append(item['text'])
                                            # Extract evidence from the check_text
                                            evidence_sentences = [s.strip() for s in check_text.split('.') if s.strip()]
                                            evidence = '. '.join(evidence_sentences[-2:]) if evidence_sentences else "Item completed"
                                            checklist_evidence[item_id] = evidence
                                            print(f"   ✅ COMPLETED: {item['text']}")
                                        else:
                                            print(f"   ❌ Not yet: {item['text']}")
                                        
                                        # Cache the result
                                        checklist_llm_cache[item_id] = {
                                            'timestamp': current_time,
                                            'result': completed
                                        }
                                    except Exception as e:
                                        print(f"   ⚠️ LLM check failed for '{item['text']}': {e}")
                                        system_status.lm_analysis_errors += 1
                                        system_status.last_error = str(e)
                                else:
                                    # CHANGED: Use LLM instead of keywords (even without local_use_llm flag)
                                    # This ensures better accuracy for all checklist items
                                    try:
                                        completed, reason = llm_analyzer.check_checklist_item_semantic(
                                            item['text'],
                                            check_text,
                                            transcription_language
                                        )
                                        if completed:
                                            checklist_progress[item_id] = True
                                            newly_completed.append(item['text'])
                                            # Extract evidence from the check_text
                                            evidence_sentences = [s.strip() for s in check_text.split('.') if s.strip()]
                                            evidence = '. '.join(evidence_sentences[-2:]) if evidence_sentences else "Item completed"
                                            checklist_evidence[item_id] = evidence
                                            print(f"   ✅ COMPLETED: {item['text']}")
                                        else:
                                            print(f"   ❌ Not yet: {item['text']}")
                                        
                                        # Cache the result
                                        checklist_llm_cache[item_id] = {
                                            'timestamp': current_time,
                                            'result': completed
                                        }
                                    except Exception as e:
                                        print(f"   ⚠️ LLM fallback check failed: {e}")
                                        system_status.lm_analysis_errors += 1
                                        system_status.last_error = str(e)
                        
                        if newly_completed:
                            print(f"\n🎯 Newly completed items: {len(newly_completed)}")
                        else:
                            print(f"\n⏳ Checked {len(checked_items)} items, none completed yet")
                        
                        # Разбиваем на предложения
                        sentences = [s.strip() for s in transcript.split('.') if s.strip()]
                        
                        for sentence in sentences:
                            if len(sentence) > 10:  # Игнорируем слишком короткие
                                # Use LLM for comprehensive analysis
                                try:
                                    last_client_insight = llm_analyzer.analyze_client_sentiment(
                                        sentence,
                                        accumulated_transcript[-500:]
                                    )
                                    system_status.lm_analysis_count += 1
                                except Exception as e:
                                    print(f"   ⚠️ LLM sentiment analysis failed: {e}")
                                    system_status.lm_analysis_errors += 1
                                    # Fallback: use keyword analysis
                                    last_client_insight = analyze_client_text(sentence, is_client=True)
                        
                        # Получаем подсказку от LLM
                        if local_use_llm:
                            try:
                                next_step = llm_analyzer.generate_next_step(
                                    current_stage,
                                    last_client_insight or {},
                                    checklist_progress,
                                    accumulated_transcript[-500:]
                                )
                                last_hint = next_step
                                system_status.recommendation_count += 1
                                
                                # Calculate probability based on progress
                                completed_count = sum(1 for v in checklist_progress.values() if v)
                                total_items = len(get_checklist_structure())
                                engagement = last_client_insight.get('engagement_level', 0.5)
                                last_prob = min(1.0, (completed_count / max(total_items, 1)) * 0.5 + engagement * 0.5)
                            except Exception as e:
                                print(f"⚠️ LLM hint generation failed: {e}")
                                system_status.recommendation_errors += 1
                                system_status.last_error = str(e)
                                # Fallback
                                llm_result = call_openrouter(transcript)
                                last_hint = llm_result.get("hint", "")
                                last_prob = llm_result.get("prob", 0.0)
                                next_step = generate_next_step_recommendation(
                                    current_stage,
                                    checklist_progress,
                                    last_client_insight or {}
                                )
                        else:
                            # Use old OpenRouter call
                            llm_result = call_openrouter(transcript)
                            last_hint = llm_result.get("hint", "")
                            last_prob = llm_result.get("prob", 0.0)
                            next_step = generate_next_step_recommendation(
                                current_stage,
                                checklist_progress,
                                last_client_insight or {}
                            )
                    else:
                        print("⏳ Transcript empty, using cached data")
                    
                    # ===== DETECT IN-CALL TRIGGERS =====
                    assist_trigger = None
                    if transcript and len(transcript) > 10:
                        # Use recent transcript for trigger detection
                        assist_trigger = intent_detector.detect_trigger(transcript, transcription_language)
                        if assist_trigger:
                            print(f"🎯 ASSIST TRIGGER: {assist_trigger.get('id')} - {assist_trigger.get('title')}")
                    
                    # ===== ALWAYS SEND MESSAGE (even if transcript empty) =====
                    print(f"📊 Sending update: hint={bool(last_hint)}, stage={current_stage}, checklist_items={len(checklist_progress)}, trigger={bool(assist_trigger)}")
                    
                    # Отправляем через WebSocket всем клиентам
                    message_data = {
                        "hint": last_hint,
                        "prob": last_prob,
                        "client_insight": last_client_insight,
                        "next_step": next_step,
                        "current_stage": current_stage,
                        "checklist_progress": checklist_progress,
                        "checklist_evidence": checklist_evidence,  # Add evidence for each item
                        "transcript_preview": accumulated_transcript[-500:] if accumulated_transcript else "",  # Последние 500 символов
                        "assist_trigger": assist_trigger  # Add in-call assist trigger
                    }
                    message = json.dumps(message_data)
                    
                    disconnected = set()
                    for ws in coach_connections:
                        try:
                            await ws.send_text(message)
                        except Exception as e:
                            print(f"❌ Ошибка отправки: {e}")
                            disconnected.add(ws)
                    
                    coach_connections.difference_update(disconnected)
                    
                    print(f"✅ Real-time analysis sent to {len(coach_connections)} clients")
                    
                    # Очищаем буфер
                    audio_buffer.clear()
                    
                except Exception as e:
                    print(f"❌ Real-time transcription error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Очищаем буфер даже при ошибке
                    audio_buffer.clear()
            
            # НЕ используем мок-данные при живой записи!
            # Только реальная транскрипция определяет checklist
                
    except WebSocketDisconnect:
        print("🎤 /ingest отключен")
        is_live_recording = False
    except Exception as e:
        print(f"❌ /ingest error: {e}")
        is_live_recording = False
        import traceback
        traceback.print_exc()


@app.websocket("/coach")
async def websocket_coach(websocket: WebSocket):
    """Отправляет подсказки и client insights клиенту"""
    global current_stage, checklist_progress, last_client_insight, transcription_language
    
    await websocket.accept()
    coach_connections.add(websocket)
    print(f"👥 /coach подключен (всего: {len(coach_connections)})")
    
    # Генерируем начальный next_step
    initial_next_step = generate_next_step_recommendation(
        current_stage,
        checklist_progress,
        last_client_insight or {}
    )
    
    # Отправляем текущее состояние сразу при подключении
    # Показываем ПУСТОЙ checklist при старте (без мок-данных)
    initial = json.dumps({
        "hint": last_hint or "Start speaking or select input mode below",
        "prob": last_prob,
        "client_insight": last_client_insight,
        "next_step": initial_next_step,
        "current_stage": current_stage,
        "checklist_progress": {}  # Пустой checklist на старте
    })
    await websocket.send_text(initial)
    
    try:
        while True:
            # Держим соединение открытым и слушаем настройки
            text_data = await websocket.receive_text()
            message = json.loads(text_data)
            
            if message.get('type') == 'set_language':
                transcription_language = message.get('language', 'id')
                print(f"🌍 Language set to: {transcription_language}")
                
    except WebSocketDisconnect:
        coach_connections.discard(websocket)
        print(f"👥 /coach отключен (осталось: {len(coach_connections)})")
    except Exception as e:
        coach_connections.discard(websocket)
        print(f"❌ /coach error: {e}")


@app.get("/")
async def root():
    return {
        "service": "SalesBestFriend MVP Voice Coach",
        "version": "0.1.0",
        "endpoints": {
            "ingest": "ws://localhost:8000/ingest",
            "coach": "ws://localhost:8000/coach"
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "coach_connections": len(coach_connections),
        "last_hint": last_hint,
        "last_prob": last_prob
    }


@app.post("/api/process-transcript")
async def process_transcript(transcript: str = Form(...)):
    """
    Обработка текстового транскрипта для отладки
    """
    global last_client_insight, last_hint, last_prob
    
    try:
        # Разбиваем транскрипт на строки
        lines = transcript.strip().split('\n')
        
        # Извлекаем клиентские высказывания
        client_utterances = []
        for line in lines:
            line = line.strip()
            if line.lower().startswith('client:') or line.lower().startswith('клиент:'):
                # Убираем префикс "Client:" или "Клиент:"
                text = line.split(':', 1)[1].strip()
                client_utterances.append(text)
        
        # Если нет явных меток, анализируем весь текст
        if not client_utterances:
            client_utterances = [line.strip() for line in lines if line.strip()]
        
        # Анализируем каждое высказывание через LLM
        insights_list = []
        for utterance in client_utterances:
            try:
                insight = llm_analyzer.analyze_client_sentiment(
                    utterance,
                    transcript  # Full context
                )
                insights_list.append(insight)
            except Exception as e:
                print(f"   ⚠️ LLM analysis failed for utterance: {e}")
                # Fallback
                insight = analyze_client_text(utterance, is_client=True)
                insights_list.append(insight)
        
        # Берем последний insight как текущий
        if insights_list:
            last_client_insight = insights_list[-1]
        
        # Формируем диалог для LLM
        dialogue = transcript
        result = call_openrouter(dialogue)
        
        last_hint = result.get("hint", "")
        last_prob = result.get("prob", 0.0)
        
        # Отправляем всем подключенным клиентам
        message_data = {
            "hint": last_hint,
            "prob": last_prob,
            "client_insight": last_client_insight
        }
        message = json.dumps(message_data)
        
        disconnected = set()
        for ws in coach_connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
                disconnected.add(ws)
        
        coach_connections.difference_update(disconnected)
        
        print(f"📝 Обработан transcript, найдено {len(client_utterances)} клиентских высказываний")
        print(f"🧠 Client Insight: {last_client_insight}")
        
        return JSONResponse({
            "success": True,
            "message": f"Обработано {len(client_utterances)} высказываний",
            "client_insight": last_client_insight,
            "hint": last_hint,
            "prob": last_prob
        })
        
    except Exception as e:
        print(f"❌ Ошибка обработки transcript: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/process-video")
async def process_video(file: UploadFile = File(...), language: str = Form("id")):
    """
    Обработка видео файла (извлечение аудио + транскрипция)
    Поддерживает: mp4, avi, mov, webm, mkv
    """
    global last_client_insight, last_hint, last_prob, transcription_language
    transcription_language = language
    
    try:
        import tempfile
        import os
        import subprocess
        
        print(f"🎬 Processing video file: {file.filename}")
        
        # Сохраняем видео файл временно
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, file.filename)
            audio_path = os.path.join(temp_dir, "audio.wav")
            
            # Сохраняем загруженный файл
            content = await file.read()
            with open(video_path, "wb") as f:
                f.write(content)
            
            print(f"📹 Saved video: {len(content)} bytes")
            
            # Извлекаем аудио с помощью FFmpeg
            print("🔊 Extracting audio with FFmpeg...")
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # Без видео
                "-acodec", "pcm_s16le",  # PCM 16-bit
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",  # Mono
                "-y",  # Overwrite
                audio_path
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=300  # 5 минут максимум
                )
                if result.returncode != 0:
                    error_msg = result.stderr.decode('utf-8', errors='ignore')
                    print(f"❌ FFmpeg error: {error_msg}")
                    return JSONResponse({
                        "success": False,
                        "error": f"Failed to extract audio: {error_msg[:200]}"
                    }, status_code=400)
            except subprocess.TimeoutExpired:
                return JSONResponse({
                    "success": False,
                    "error": "Video processing took too long (> 5 min)"
                }, status_code=408)
            
            print(f"✅ Audio extracted: {audio_path}")
            
            # Транскрибируем аудио
            print(f"🎤 Transcribing with language: {language}")
            from utils.realtime_transcriber import transcribe_audio_buffer
            
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                transcribe_audio_buffer,
                audio_data,
                language
            )
            
            if not transcript:
                return JSONResponse({
                    "success": False,
                    "error": "No speech detected in video"
                }, status_code=400)
            
            print(f"✅ Transcription complete: {len(transcript)} chars")
            
            # Анализируем как обычный текст
            sentences = [s.strip() for s in transcript.split('.') if s.strip()]
            
            client_text_parts = []
            for sentence in sentences:
                lower_sentence = sentence.lower()
                is_client_speaking = (
                    not any(prefix in lower_sentence for prefix in ['sales:', 'seller:', 'manager:', 'i ', 'we ']) or
                    any(prefix in lower_sentence for prefix in ['client:', 'customer:', 'you:', 'me:', 'my ', 'i need', 'i want'])
                )
                if is_client_speaking and len(sentence) > 10:
                    client_text_parts.append(sentence)
            
            if client_text_parts:
                combined_client_text = " ".join(client_text_parts)
                # Use LLM for comprehensive analysis
                try:
                    last_client_insight = llm_analyzer.analyze_client_sentiment(
                        combined_client_text,
                        transcript
                    )
                except Exception as e:
                    print(f"   ⚠️ LLM analysis failed: {e}")
                    # Fallback
                    last_client_insight = analyze_client_text(combined_client_text, is_client=True)
            
            # LLM анализ
            llm_result = call_openrouter(transcript)
            last_hint = llm_result.get("hint", "")
            last_prob = llm_result.get("prob", 0.0)
            
            return JSONResponse({
                "success": True,
                "transcript": transcript,
                "duration_chars": len(transcript),
                "client_insight": last_client_insight,
                "hint": last_hint,
                "prob": last_prob,
                "language": language
            })
        
    except Exception as e:
        print(f"❌ Video processing error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.post("/api/process-youtube")
async def process_youtube(url: str = Form(...), language: str = Form("id")):
    """
    Обработка YouTube видео - скачивание и транскрипция
    """
    global last_client_insight, last_hint, last_prob, transcription_language
    transcription_language = language
    
    try:
        print(f"🎬 Processing YouTube: {url} (language: {language})")
        
        # Скачиваем и транскрибируем с выбранным языком
        transcript = process_youtube_url(url, language=transcription_language)
        
        if not transcript:
            return JSONResponse({
                "success": False,
                "error": "Failed to transcribe video. Video might be empty or audio unavailable."
            }, status_code=400)
        
        print(f"📝 Got transcript: {len(transcript)} chars")
        
        # Обрабатываем как обычный transcript
        lines = transcript.strip().split('\n')
        
        # Извлекаем клиентские высказывания
        client_utterances = []
        for line in lines:
            line = line.strip()
            if line.lower().startswith('client:') or line.lower().startswith('клиент:'):
                text = line.split(':', 1)[1].strip()
                client_utterances.append(text)
        
        # Если нет явных меток, анализируем все строки
        if not client_utterances:
            client_utterances = [line.strip() for line in lines if line.strip()]
        
        # Анализируем каждое высказывание через LLM
        insights_list = []
        for utterance in client_utterances:
            try:
                insight = llm_analyzer.analyze_client_sentiment(
                    utterance,
                    transcript  # Full context
                )
                insights_list.append(insight)
            except Exception as e:
                print(f"   ⚠️ LLM analysis failed: {e}")
                # Fallback
                insight = analyze_client_text(utterance, is_client=True)
                insights_list.append(insight)
        
        if insights_list:
            last_client_insight = insights_list[-1]
        
        # LLM анализ
        result = call_openrouter(transcript)
        
        last_hint = result.get("hint", "")
        last_prob = result.get("prob", 0.0)
        
        # Broadcast через WebSocket
        message_data = {
            "hint": last_hint,
            "prob": last_prob,
            "client_insight": last_client_insight
        }
        message = json.dumps(message_data)
        
        disconnected = set()
        for ws in coach_connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                print(f"❌ Ошибка отправки: {e}")
                disconnected.add(ws)
        
        coach_connections.difference_update(disconnected)
        
        print(f"✅ YouTube processed: {len(client_utterances)} utterances")
        print(f"🧠 Client Insight: {last_client_insight}")
        
        return JSONResponse({
            "success": True,
            "message": f"Обработано YouTube видео: {len(client_utterances)} высказываний",
            "transcript": transcript[:500] + "..." if len(transcript) > 500 else transcript,
            "client_insight": last_client_insight,
            "hint": last_hint,
            "prob": last_prob
        })
        
    except Exception as e:
        print(f"❌ YouTube processing error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


# ===== LOGGING & STATUS TRACKING =====
import time
from datetime import datetime

class SystemStatus:
    """Track system health and performance"""
    def __init__(self):
        self.audio_capture_active = False
        self.last_audio_chunk_time = None
        self.transcription_count = 0
        self.last_transcription_time = None
        self.lm_analysis_count = 0
        self.lm_analysis_errors = 0
        self.recommendation_count = 0
        self.recommendation_errors = 0
        self.last_error = None
        self.start_time = datetime.now()
    
    def to_dict(self):
        return {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "audio_active": self.audio_capture_active,
            "last_audio_chunk": self.last_audio_chunk_time,
            "transcription_count": self.transcription_count,
            "last_transcription": self.last_transcription_time,
            "lm_analysis": {
                "count": self.lm_analysis_count,
                "errors": self.lm_analysis_errors
            },
            "recommendations": {
                "count": self.recommendation_count,
                "errors": self.recommendation_errors
            },
            "last_error": self.last_error
        }

system_status = SystemStatus()

@app.get("/api/status")
async def get_status():
    """Get system health and performance metrics"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "metrics": system_status.to_dict()
    }

