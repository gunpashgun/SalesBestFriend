"""
Trial Class Sales Assistant - FastAPI Backend

Real-time sales coaching for Zoom trial class calls.
Focused on:
- Indonesian conversation transcription
- Real-time checklist progress tracking
- Client card field extraction
- Time-based stage guidance

Minimal, focused on live assistance only.
"""

import asyncio
import json
import time
from typing import Set, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os

# New configs
from call_structure_config import (
    get_default_call_structure,
    get_stage_by_time,
    detect_stage_by_context,
    get_stage_timing_status,
    validate_call_structure
)
from client_card_config import (
    get_default_client_card_fields,
    validate_client_card_config
)
from trial_class_analyzer import get_trial_class_analyzer, reset_analyzer

# Existing utilities
from utils.audio_buffer import AudioBuffer
from utils.realtime_transcriber import transcribe_audio_buffer

load_dotenv()

app = FastAPI()

# CORS - Allow all origins for development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (Vercel, localhost, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers
    max_age=3600,  # Cache preflight requests for 1 hour
)

# ===== GLOBAL STATE =====
coach_connections: Set[WebSocket] = set()
accumulated_transcript: str = ""
transcription_language: str = "id"  # Bahasa Indonesia by default
is_live_recording: bool = False

# Call structure & progress
call_structure = get_default_call_structure()
client_card_fields = get_default_client_card_fields()

# Progress tracking
checklist_progress: Dict[str, bool] = {}  # item_id → completed
checklist_evidence: Dict[str, str] = {}  # item_id → evidence text
checklist_last_check: Dict[str, float] = {}  # item_id → timestamp

# Client card data
client_card_data: Dict[str, Dict[str, str]] = {}  # field_id → {value, evidence, extractedAt}

# Call timing
call_start_time: Optional[float] = None  # Timestamp when call started

# Stage tracking
current_stage_id: str = ""  # Track current stage to prevent jitter
stage_start_time: Optional[float] = None  # Timestamp when current stage started

# Debug logging
debug_log: List[Dict] = []  # Stores all AI decisions for debugging


def log_decision(decision_type: str, data: Dict):
    """Add a decision to the debug log"""
    global debug_log
    timestamp = datetime.now().isoformat()
    entry = {
        "timestamp": timestamp,
        "type": decision_type,
        **data
    }
    debug_log.append(entry)
    # Keep only last 500 entries to avoid memory issues
    if len(debug_log) > 500:
        debug_log = debug_log[-500:]


# Analyzer
analyzer = get_trial_class_analyzer()

# ===== CONFIGURATION ENDPOINTS =====

@app.get("/api/config/call-structure")
async def get_call_structure_config():
    """Get current call structure configuration"""
    return {
        "structure": call_structure
    }


@app.post("/api/config/call-structure")
async def update_call_structure_config(data: Dict = None):
    """Update call structure configuration"""
    global call_structure
    
    if not data or 'structure' not in data:
        return JSONResponse({"error": "Missing structure field"}, status_code=400)
    
    try:
        new_structure = data['structure']
        validate_call_structure(new_structure)
        call_structure = new_structure
        
        return {
            "success": True,
            "message": "Call structure updated"
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/config/client-card")
async def get_client_card_config():
    """Get current client card field configuration"""
    return {
        "fields": client_card_fields
    }


@app.post("/api/config/client-card")
async def update_client_card_config(data: Dict = None):
    """Update client card field configuration"""
    global client_card_fields
    
    if not data or 'fields' not in data:
        return JSONResponse({"error": "Missing fields"}, status_code=400)
    
    try:
        new_fields = data['fields']
        validate_client_card_config(new_fields)
        client_card_fields = new_fields
        
        return {
            "success": True,
            "message": "Client card fields updated"
        }
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ===== WEBSOCKET: /ingest (Audio Input) =====

@app.websocket("/ingest")
async def websocket_ingest(websocket: WebSocket):
    """
    Accept audio stream and transcribe in real-time
    """
    global transcription_language, is_live_recording, call_start_time
    global checklist_progress, checklist_evidence, checklist_last_check
    global client_card_data, accumulated_transcript
    global current_stage_id, stage_start_time
    
    # Reset state for new session
    is_live_recording = True
    call_start_time = time.time()
    stage_start_time = time.time()  # Start with first stage
    current_stage_id = call_structure[0]['id'] if call_structure else ""  # Initialize to first stage
    checklist_progress = {}
    checklist_evidence = {}
    checklist_last_check = {}
    client_card_data = {}  # Will be filled as data is extracted
    accumulated_transcript = ""
    reset_analyzer()
    
    await websocket.accept()
    print("🎤 /ingest connected - starting trial class session")
    print(f"   Language: {transcription_language}")
    print(f"   Call start time: {datetime.now().isoformat()}")
    
    # Audio buffer (transcribe every 10 seconds)
    audio_buffer = AudioBuffer(interval_seconds=10.0)
    
    try:
        while True:
            message = await websocket.receive()
            
            # Handle text messages (settings)
            if 'text' in message:
                try:
                    data = json.loads(message['text'])
                    if data.get('type') == 'set_language':
                        transcription_language = data.get('language', 'id')
                        print(f"🌍 Language set to: {transcription_language}")
                except Exception as e:
                    print(f"⚠️ Failed to process setting: {e}")
                continue
            
            # Handle audio data
            elif 'bytes' in message:
                data = message['bytes']
                ready = audio_buffer.add_chunk(data)
                
                if ready:
                    print(f"\n🎯 Transcription triggered (10s buffer ready)")
                    
                    try:
                        # Get audio
                        buffer_data = audio_buffer.get_audio_data()
                        
                        # Transcribe
                        loop = asyncio.get_event_loop()
                        transcript = await loop.run_in_executor(
                            None,
                            transcribe_audio_buffer,
                            buffer_data,
                            transcription_language
                        )
                        
                        if transcript:
                            print(f"📝 Transcript ({len(transcript)} chars):")
                            print(f"   {transcript[:200]}...")
                            
                            # Accumulate
                            accumulated_transcript += " " + transcript
                            # Keep last 1000 words for context
                            words = accumulated_transcript.split()
                            if len(words) > 1000:
                                accumulated_transcript = " ".join(words[-1000:])
                            
                            # ===== ANALYZE: Check checklist items =====
                            # Guard against None (happens when WebSocket reconnects)
                            if call_start_time is None:
                                print("⚠️ call_start_time is None, skipping analysis")
                                audio_buffer.clear()
                                continue
                            
                            elapsed = time.time() - call_start_time
                            
                            # Detect stage from conversation context (AI-based)
                            global current_stage_id
                            detected_stage = detect_stage_by_context(
                                conversation_text=accumulated_transcript[-2000:],  # Last 2000 chars
                                elapsed_seconds=int(elapsed),
                                analyzer=analyzer,
                                previous_stage_id=current_stage_id if current_stage_id else None,
                                min_confidence=0.6
                            )
                            
                            # Update current stage
                            if detected_stage != current_stage_id:
                                print(f"🔄 Stage transition: {current_stage_id or '(start)'} → {detected_stage}")
                                # Reset stage timer on transition
                                global stage_start_time
                                stage_start_time = time.time()
                                print(f"   ⏱️ Stage timer reset")
                            current_stage_id = detected_stage
                            
                            print(f"\n📋 Checking checklist items...")
                            newly_completed = []
                            
                            for stage in call_structure:
                                for item in stage['items']:
                                    item_id = item['id']
                                    
                                    # Skip if already completed
                                    if checklist_progress.get(item_id, False):
                                        continue
                                    
                                    # Skip if checked recently (30s cooldown)
                                    if item_id in checklist_last_check:
                                        if time.time() - checklist_last_check[item_id] < 30:
                                            continue
                                    
                                    # Update last check time
                                    checklist_last_check[item_id] = time.time()
                                    
                                    # Check with LLM
                                    completed, confidence, evidence, debug_info = analyzer.check_checklist_item(
                                        item_id,
                                        item['content'],
                                        item['type'],
                                        accumulated_transcript[-1500:]  # Last 1500 chars
                                    )
                                    
                                    # Log decision
                                    log_decision("checklist_item", {
                                        "item_id": item_id,
                                        "item_content": item['content'],
                                        "completed": completed,
                                        "confidence": confidence,
                                        "evidence": evidence,
                                        **debug_info
                                    })
                                    
                                    if completed:
                                        # Guard: Check for duplicate evidence (same evidence used for multiple items)
                                        duplicate_evidence = False
                                        if evidence:
                                            for existing_id, existing_evidence in checklist_evidence.items():
                                                if existing_evidence == evidence:
                                                    duplicate_evidence = True
                                                    print(f"   ⚠️ DUPLICATE EVIDENCE detected!")
                                                    print(f"      Same evidence already used for: {existing_id}")
                                                    print(f"      Evidence: {evidence[:100]}")
                                                    log_decision("duplicate_evidence", {
                                                        "item_id": item_id,
                                                        "duplicate_of": existing_id,
                                                        "evidence": evidence
                                                    })
                                                    break
                                        
                                        if not duplicate_evidence:
                                            checklist_progress[item_id] = True
                                            checklist_evidence[item_id] = evidence
                                            newly_completed.append(item['content'])
                                            print(f"   ✅ {item['content']}")
                                        else:
                                            print(f"   ❌ {item['content']} - REJECTED (duplicate evidence)")
                                    else:
                                        print(f"   ❌ {item['content']} (confidence: {confidence:.0%})")
                            
                            if newly_completed:
                                print(f"\n🎯 Newly completed: {len(newly_completed)} items")
                            
                            # ===== ANALYZE: Extract client card info =====
                            print(f"\n👤 Extracting client info...")
                            # Get current values (just the value strings for comparison)
                            current_values = {k: v.get('value', '') if isinstance(v, dict) else v for k, v in client_card_data.items()}
                            new_client_info = analyzer.extract_client_card_fields(
                                accumulated_transcript[-1000:],  # Last 1000 chars
                                current_values
                            )
                            
                            if new_client_info:
                                print(f"   ✅ Extracted {len(new_client_info)} fields:")
                                for field_id, field_data in new_client_info.items():
                                    field_data['extractedAt'] = datetime.utcnow().isoformat() + 'Z'
                                    print(f"      - {field_id}: {field_data.get('value', '')[:50]}...")
                                    client_card_data[field_id] = field_data
                            else:
                                print(f"   ⏭️ No new client info extracted")
                            
                            # ===== BUILD AND SEND RESPONSE =====
                            elapsed = time.time() - call_start_time
                            # current_stage_id already set above by detect_stage_by_context()
                            
                            # Build stages with progress and timing
                            stages_with_progress = []
                            for stage in call_structure:
                                stage_items = []
                                for item in stage['items']:
                                    stage_items.append({
                                        "id": item['id'],
                                        "type": item['type'],
                                        "content": item['content'],
                                        "completed": checklist_progress.get(item['id'], False),
                                        "evidence": checklist_evidence.get(item['id'], "")
                                    })
                                
                                timing_status = get_stage_timing_status(stage['id'], int(elapsed))
                                
                                stages_with_progress.append({
                                    "id": stage['id'],
                                    "name": stage['name'],
                                    "startOffsetSeconds": stage['startOffsetSeconds'],
                                    "durationSeconds": stage['durationSeconds'],
                                    "items": stage_items,
                                    "isCurrent": stage['id'] == current_stage_id,
                                    "timingStatus": timing_status['status'],
                                    "timingMessage": timing_status['message']
                                })
                            
                            # Send to all clients
                            # Calculate stage elapsed time
                            stage_elapsed = 0
                            if stage_start_time is not None:
                                stage_elapsed = int(time.time() - stage_start_time)
                            
                            message_data = {
                                "type": "update",
                                "callElapsedSeconds": int(elapsed),
                                "stageElapsedSeconds": stage_elapsed,
                                "currentStageId": current_stage_id,
                                "stages": stages_with_progress,
                                "clientCard": client_card_data,
                                "transcriptPreview": accumulated_transcript[-300:],
                                "debugLog": debug_log[-50:]  # Last 50 entries for debugging
                            }
                            
                            message_json = json.dumps(message_data)
                            
                            disconnected = set()
                            for ws in coach_connections:
                                try:
                                    await ws.send_text(message_json)
                                except Exception as e:
                                    print(f"❌ Send error: {e}")
                                    disconnected.add(ws)
                            
                            coach_connections.difference_update(disconnected)
                            
                            print(f"✅ Update sent to {len(coach_connections)} clients\n")
                        
                        # Clear buffer
                        audio_buffer.clear()
                        
                    except Exception as e:
                        print(f"❌ Analysis error: {e}")
                        import traceback
                        traceback.print_exc()
                        audio_buffer.clear()
    
    except WebSocketDisconnect:
        print("🎤 /ingest disconnected")
        is_live_recording = False
        call_start_time = None
    except Exception as e:
        print(f"❌ /ingest error: {e}")
        is_live_recording = False
        call_start_time = None
        import traceback
        traceback.print_exc()


# ===== WEBSOCKET: /coach (Data Output) =====

@app.websocket("/coach")
async def websocket_coach(websocket: WebSocket):
    """
    Send real-time coaching data to frontend
    """
    await websocket.accept()
    coach_connections.add(websocket)
    print(f"👥 /coach connected (total: {len(coach_connections)})")
    
    # Send initial state
    initial_data = {
        "type": "initial",
        "callElapsedSeconds": 0,
        "currentStageId": call_structure[0]['id'] if call_structure else None,
        "stages": [
            {
                "id": stage['id'],
                "name": stage['name'],
                "startOffsetSeconds": stage['startOffsetSeconds'],
                "durationSeconds": stage['durationSeconds'],
                "items": [
                    {
                        "id": item['id'],
                        "type": item['type'],
                        "content": item['content'],
                        "completed": False,
                        "evidence": ""
                    }
                    for item in stage['items']
                ],
                "isCurrent": False,
                "timingStatus": "not_started",
                "timingMessage": "Not started"
            }
            for stage in call_structure
        ],
        "clientCard": client_card_data,
        "transcriptPreview": ""
    }
    
    await websocket.send_text(json.dumps(initial_data))
    
    try:
        while True:
            # Keep connection open, listen for settings
            text_data = await websocket.receive_text()
            message = json.loads(text_data)
            
            if message.get('type') == 'set_language':
                global transcription_language
                transcription_language = message.get('language', 'id')
                print(f"🌍 Language set to: {transcription_language}")
            
            elif message.get('type') == 'manual_toggle_item':
                # Allow manual checkbox toggle
                item_id = message.get('item_id')
                if item_id:
                    checklist_progress[item_id] = not checklist_progress.get(item_id, False)
                    print(f"✋ Manual toggle: {item_id} = {checklist_progress[item_id]}")
            
            elif message.get('type') == 'update_client_card':
                # Allow manual client card updates
                field_id = message.get('field_id')
                value = message.get('value')
                if field_id and field_id in client_card_data:
                    client_card_data[field_id] = value
                    print(f"✋ Manual update: {field_id}")
    
    except WebSocketDisconnect:
        coach_connections.discard(websocket)
        print(f"👥 /coach disconnected (remaining: {len(coach_connections)})")
    except Exception as e:
        coach_connections.discard(websocket)
        print(f"❌ /coach error: {e}")


# ===== HTTP ENDPOINTS =====

@app.options("/api/process-youtube")
async def options_process_youtube():
    """Handle CORS preflight for YouTube endpoint"""
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.get("/")
async def root():
    return {
        "service": "Trial Class Sales Assistant",
        "version": "2.0.0",
        "focus": "Real-time Zoom trial class coaching",
        "language": "Bahasa Indonesia (id)",
        "endpoints": {
            "ingest": "ws://localhost:8000/ingest",
            "coach": "ws://localhost:8000/coach",
            "config": {
                "call_structure": "/api/config/call-structure",
                "client_card": "/api/config/client-card"
            }
        }
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "coach_connections": len(coach_connections),
        "is_live_recording": is_live_recording,
        "call_elapsed": int(time.time() - call_start_time) if call_start_time else 0,
        "items_completed": sum(1 for v in checklist_progress.values() if v),
        "total_items": sum(len(stage['items']) for stage in call_structure)
    }


@app.get("/api/debug-log")
async def get_debug_log():
    """Get debug log of all AI decisions"""
    return {
        "log": debug_log[-100:],  # Last 100 entries
        "total_entries": len(debug_log),
        "is_recording": is_live_recording,
        "message": "No logs yet - start recording to see AI decisions" if len(debug_log) == 0 else f"Showing last {min(100, len(debug_log))} of {len(debug_log)} entries"
    }


# For backward compatibility / debugging
@app.post("/api/process-transcript")
async def process_transcript(transcript: str = Form(...), language: str = Form("id")):
    """Process a text transcript (for testing)"""
    global accumulated_transcript, call_start_time, current_stage_id, stage_start_time
    
    if not call_start_time:
        call_start_time = time.time()
        stage_start_time = time.time()
        current_stage_id = call_structure[0]['id'] if call_structure else ""
    
    accumulated_transcript = transcript
    
    # Quick analysis
    elapsed = time.time() - call_start_time
    global current_stage_id
    detected_stage = detect_stage_by_context(
        conversation_text=transcript[-2000:],
        elapsed_seconds=int(elapsed),
        analyzer=analyzer,
        previous_stage_id=current_stage_id if current_stage_id else None,
        min_confidence=0.6
    )
    current_stage_id = detected_stage
    
    # Check items
    for stage in call_structure:
        for item in stage['items']:
            if not checklist_progress.get(item['id'], False):
                completed, conf, evidence, debug_info = analyzer.check_checklist_item(
                    item['id'],
                    item['content'],
                    item['type'],
                    transcript
                )
                
                # Log decision
                log_decision("checklist_item", {
                    "item_id": item['id'],
                    "item_content": item['content'],
                    "completed": completed,
                    "confidence": conf,
                    "evidence": evidence,
                    **debug_info
                })
                
                if completed:
                    checklist_progress[item['id']] = True
                    checklist_evidence[item['id']] = evidence
    
    # Extract client info
    # Get current values (just the value strings for comparison)
    current_values = {k: v.get('value', '') if isinstance(v, dict) else v for k, v in client_card_data.items()}
    new_info = analyzer.extract_client_card_fields(transcript, current_values)
    for field_id, field_data in new_info.items():
        field_data['extractedAt'] = datetime.utcnow().isoformat() + 'Z'
        client_card_data[field_id] = field_data
    
    return {
        "success": True,
        "currentStage": current_stage_id,
        "itemsCompleted": sum(1 for v in checklist_progress.values() if v),
        "clientCardFields": len([v for v in client_card_data.values() if v and v.get('value')])
    }


@app.post("/api/process-youtube")
async def process_youtube(url: str = Form(...), language: str = Form("id"), real_time: bool = Form(True)):
    """
    Process YouTube video for debugging (STREAMING MODE)
    Simulates real-time call by streaming audio chunks like live recording
    
    Args:
        url: YouTube video URL
        language: Transcription language (default: "id")
        real_time: If True, simulate real-time playback with delays (default: True)
    """
    global accumulated_transcript, call_start_time, transcription_language
    global checklist_progress, checklist_evidence, client_card_data
    global is_live_recording
    
    try:
        from utils.youtube_streamer import get_streamer
        from utils.audio_buffer import AudioBuffer
        from utils.realtime_transcriber import transcribe_audio_buffer
        
        print(f"🎬 Processing YouTube (STREAMING MODE): {url}")
        print(f"   Language: {language}")
        print(f"   Real-time: {real_time}")
        
        # Reset state for new session (like live recording)
        global current_stage_id, stage_start_time
        is_live_recording = True
        call_start_time = time.time()
        stage_start_time = time.time()
        current_stage_id = call_structure[0]['id'] if call_structure else ""
        checklist_progress = {}
        checklist_evidence = {}
        client_card_data = {}  # Will be filled as data is extracted
        accumulated_transcript = ""
        transcription_language = language
        reset_analyzer()
        
        # Create audio buffer (same as live ingest)
        audio_buffer = AudioBuffer(interval_seconds=10.0)
        
        # Get streamer
        streamer = get_streamer(chunk_duration=1.0)  # 1 second chunks
        
        print(f"📥 Downloading and streaming YouTube video...")
        
        # Stream audio chunks (simulating live call)
        chunk_count = 0
        async for audio_chunk in streamer.stream_youtube_url(url, real_time=real_time):
            chunk_count += 1
            
            # Add to buffer (same as live ingest)
            ready = audio_buffer.add_chunk(audio_chunk)
            
            if ready:
                print(f"\n🎯 Transcription triggered (10s buffer ready, chunk #{chunk_count})")
                
                try:
                    # Get buffered audio
                    buffer_data = audio_buffer.get_audio_data()
                    
                    # Transcribe (same as live ingest)
                    loop = asyncio.get_event_loop()
                    transcript = await loop.run_in_executor(
                        None,
                        transcribe_audio_buffer,
                        buffer_data,
                        transcription_language
                    )
                    
                    if transcript:
                        print(f"📝 Transcript ({len(transcript)} chars):")
                        print(f"   {transcript[:200]}...")
                        
                        # Accumulate transcript
                        accumulated_transcript += " " + transcript
                        words = accumulated_transcript.split()
                        if len(words) > 1000:
                            accumulated_transcript = " ".join(words[-1000:])
                        
                        # ===== ANALYZE: Check checklist items =====
                        elapsed = time.time() - call_start_time
                        
                        # Detect stage from conversation context
                        global current_stage_id
                        detected_stage = detect_stage_by_context(
                            conversation_text=accumulated_transcript[-2000:],
                            elapsed_seconds=int(elapsed),
                            analyzer=analyzer,
                            previous_stage_id=current_stage_id if current_stage_id else None,
                            min_confidence=0.6
                        )
                        if detected_stage != current_stage_id:
                            print(f"🔄 Stage transition: {current_stage_id or '(start)'} → {detected_stage}")
                            # Reset stage timer on transition
                            global stage_start_time
                            stage_start_time = time.time()
                            print(f"   ⏱️ Stage timer reset")
                        current_stage_id = detected_stage
                        
                        print(f"\n📋 Checking checklist items (stage: {current_stage_id})...")
                        
                        for stage in call_structure:
                            for item in stage['items']:
                                item_id = item['id']
                                
                                # Skip if already completed
                                if checklist_progress.get(item_id, False):
                                    continue
                                
                                # Check with LLM
                                completed, confidence, evidence, debug_info = analyzer.check_checklist_item(
                                    item_id,
                                    item['content'],
                                    item['type'],
                                    accumulated_transcript[-500:]  # Last 500 chars
                                )
                                
                                # Log decision
                                log_decision("checklist_item", {
                                    "item_id": item_id,
                                    "item_content": item['content'],
                                    "completed": completed,
                                    "confidence": confidence,
                                    "evidence": evidence,
                                    **debug_info
                                })
                                
                                if completed and confidence > 0.7:
                                    checklist_progress[item_id] = True
                                    checklist_evidence[item_id] = evidence
                                    print(f"   ✅ {item['content']} (confidence: {confidence:.2f})")
                        
                        # ===== ANALYZE: Extract client info =====
                        print(f"\n👤 Extracting client information...")
                        
                        new_info = analyzer.extract_client_card_fields(
                            accumulated_transcript,
                            client_card_data
                        )
                        
                        if new_info:
                            for field_id, value in new_info.items():
                                if value and not client_card_data.get(field_id):
                                    client_card_data[field_id] = value
                                    print(f"   ✅ {field_id}: {value[:50]}...")
                        
                except Exception as e:
                    print(f"⚠️ Analysis error: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\n✅ YouTube streaming complete!")
        print(f"   Total chunks: {chunk_count}")
        print(f"   Transcript length: {len(accumulated_transcript)} chars")
        
        # Mark as done
        is_live_recording = False
        
        # Analyze
        elapsed = time.time() - call_start_time
        global current_stage_id
        detected_stage = detect_stage_by_context(
            conversation_text=accumulated_transcript[-2000:],
            elapsed_seconds=int(elapsed),
            analyzer=analyzer,
            previous_stage_id=current_stage_id if current_stage_id else None,
            min_confidence=0.6
        )
        current_stage_id = detected_stage
        
        print(f"\n📋 Checking all checklist items...")
        
        # Check all items
        for stage in call_structure:
            for item in stage['items']:
                item_id = item['id']
                
                completed, conf, evidence, debug_info = analyzer.check_checklist_item(
                    item_id,
                    item['content'],
                    item['type'],
                    transcript
                )
                
                # Log decision
                log_decision("checklist_item", {
                    "item_id": item_id,
                    "item_content": item['content'],
                    "completed": completed,
                    "confidence": conf,
                    "evidence": evidence,
                    **debug_info
                })
                
                if completed:
                    checklist_progress[item_id] = True
                    checklist_evidence[item_id] = evidence
                    print(f"   ✅ {item['content']}")
                else:
                    print(f"   ❌ {item['content']}")
        
        print(f"\n👤 Extracting client information...")
        
        # Extract client info
        # Get current values (just the value strings for comparison)
        current_values = {k: v.get('value', '') if isinstance(v, dict) else v for k, v in client_card_data.items()}
        new_info = analyzer.extract_client_card_fields(transcript, current_values)
        
        if new_info:
            print(f"   ✅ Extracted {len(new_info)} fields:")
            for field_id, field_data in new_info.items():
                field_data['extractedAt'] = datetime.utcnow().isoformat() + 'Z'
                client_card_data[field_id] = field_data
                print(f"      - {field_id}: {field_data.get('value', '')[:50]}...")
        
        # Build response
        stages_with_progress = []
        for stage in call_structure:
            stage_items = []
            for item in stage['items']:
                stage_items.append({
                    "id": item['id'],
                    "type": item['type'],
                    "content": item['content'],
                    "completed": checklist_progress.get(item['id'], False),
                    "evidence": checklist_evidence.get(item['id'], "")
                })
            
            timing_status = get_stage_timing_status(stage['id'], int(elapsed))
            
            stages_with_progress.append({
                "id": stage['id'],
                "name": stage['name'],
                "startOffsetSeconds": stage['startOffsetSeconds'],
                "durationSeconds": stage['durationSeconds'],
                "items": stage_items,
                "isCurrent": stage['id'] == current_stage_id,
                "timingStatus": timing_status['status'],
                "timingMessage": timing_status['message']
            })
        
        # Broadcast to connected clients
        # Calculate stage elapsed time
        stage_elapsed = 0
        if stage_start_time is not None:
            stage_elapsed = int(time.time() - stage_start_time)
        
        message_data = {
            "type": "update",
            "callElapsedSeconds": int(elapsed),
            "stageElapsedSeconds": stage_elapsed,
            "currentStageId": current_stage_id,
            "stages": stages_with_progress,
            "clientCard": client_card_data,
            "transcriptPreview": transcript[-300:],
            "debugLog": debug_log[-50:]  # Last 50 entries for debugging
        }
        
        message_json = json.dumps(message_data)
        
        disconnected = set()
        for ws in coach_connections:
            try:
                await ws.send_text(message_json)
            except Exception as e:
                print(f"❌ Send error: {e}")
                disconnected.add(ws)
        
        coach_connections.difference_update(disconnected)
        
        print(f"✅ YouTube analysis complete and sent to {len(coach_connections)} clients")
        
        return {
            "success": True,
            "transcriptLength": len(transcript),
            "currentStage": current_stage_id,
            "itemsCompleted": sum(1 for v in checklist_progress.values() if v),
            "totalItems": sum(len(stage['items']) for stage in call_structure),
            "clientCardFields": len([v for v in client_card_data.values() if v]),
            "message": "Analysis complete"
        }
        
    except Exception as e:
        print(f"❌ YouTube processing error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

