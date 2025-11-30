
"""
Call Structure Configuration for Trial Class Sales Calls

Defines the expected flow of a trial class sales call with:
- Stages
- Timing per stage
- Checklist items per stage
- Semantic keywords for LLM guidance (required + forbidden)

This structure is used for:
1. Real-time progress tracking
2. LLM semantic matching (conversation → checklist items)
3. Time-based stage detection
4. Settings UI (editable by user)

Version: 3.1 (with forbidden keywords)
"""

from typing import List, Dict, TypedDict, Any


class SemanticKeywords(TypedDict, total=False):
    """Semantic keywords for pre-filtering and LLM guidance"""
    required: List[str]  # Keywords that should be present
    forbidden: List[str]  # Keywords that invalidate detection


class ChecklistItem(TypedDict):
    """Single checklist item within a stage"""
    id: str
    type: str  # "discuss" or "say"
    content: str  # What to ask/discuss or what to say/explain
    extended_description: str # Detailed description for the LLM
    semantic_keywords: SemanticKeywords  # Keywords for pre-filtering


class CallStage(TypedDict):
    """Single stage in the call structure"""
    id: str
    name: str
    startOffsetSeconds: int  # When this stage should start (from call start)
    durationSeconds: int  # How long this stage should last
    items: List[ChecklistItem]


# Common forbidden keywords (promises, acknowledgments, fillers)
COMMON_FORBIDDEN = ["nanti", "akan", "mungkin", "coba", "hmm", "ehh", "emm"]
ACKNOWLEDGMENT_FORBIDDEN = ["oke", "ok", "baik", "ya", "iya", "yup", "siap"]


DEFAULT_CALL_STRUCTURE: List[CallStage] = [
    {
        "id": "stage_greeting",
        "name": "Greeting & Preparation",
        "startOffsetSeconds": 0,
        "durationSeconds": 180,
        "items": [
            {
                "id": "opening_greeting",
                "type": "say",
                "content": "Sapa dengan hangat dan perkenalkan diri dari Algonova",
                "extended_description": "The tutor must open warmly, greet both parent and child, and introduce themselves clearly. Look for a greeting ('hello', 'selamat pagi'), a self-introduction ('my name is…', 'nama saya…'), and a reference to Algonova. Simple acknowledgments like 'oke' or 'iya' are not sufficient.",
                "semantic_keywords": {
                    "required": ["halo", "hello", "selamat", "nama saya", "my name", "saya", "algonova"],
                    "forbidden": ["nanti", "akan", "sebentar", "tunggu"]  # Promises to greet later
                }
            },
            {
                "id": "confirm_child_parent",
                "type": "say",
                "content": "Konfirmasi nama anak dan orang tua",
                "extended_description": "The goal is to ensure the tutor correctly identifies both the child and the parent. The AI should detect explicit confirmation questions or statements such as 'betul dengan Mama…?', 'ini dengan Bapak…?', or 'nama anaknya…?' This must reference both parties, not just one.",
                "semantic_keywords": {
                    "required": ["nama", "betul", "anak", "child", "mama", "papa", "orang tua", "parent"],
                    "forbidden": ["nanti", "tunggu"]  # Promises to confirm later
                }
            },
            {
                "id": "confirm_companion",
                "type": "discuss",
                "content": "Konfirmasi bahwa orang tua akan mendampingi anak",
                "extended_description": "The tutor must verify that the parent will accompany the child during the session. AI should look for phrases like 'apakah Mama/Papa mendampingi?', 'akan berada di sini?', or confirmation replies indicating parent presence.",
                "semantic_keywords": {
                    "required": ["dampingi", "mendampingi", "temani", "orang tua", "mama", "papa", "parent"],
                    "forbidden": ["mungkin", "coba", "nanti"]  # Uncertain or delayed
                }
            },
            {
                "id": "explain_stages",
                "type": "say",
                "content": "Jelaskan tahapan dan agenda trial class",
                "extended_description": "The tutor must clearly outline the stages of the trial class. Look for sequential markers such as 'pertama', 'kedua', 'selanjutnya', 'first we will…', 'then we will…', and explicit agenda description. A simple 'kita mulai ya' is not enough.",
                "semantic_keywords": {
                    "required": ["agenda", "tahapan", "stages", "sesi", "session", "pertama", "kedua", "selanjutnya", "first", "then"],
                    "forbidden": ["nanti", "sebentar lagi", "tunggu"]  # Incomplete explanation
                }
            }
        ]
    },
    {
        "id": "stage_profiling",
        "name": "Profiling",
        "startOffsetSeconds": 180,
        "durationSeconds": 420,
        "items": [
            {
                "id": "profile_age",
                "type": "discuss",
                "content": "Konfirmasi usia dan tingkat sekolah anak",
                "extended_description": "The tutor must verify both age and school grade. AI should detect questions like 'umur berapa?', 'kelas berapa?', or answers such as '8 tahun', 'kelas 3 SD'. Mentioning only the child's name does not count.",
                "semantic_keywords": {
                    "required": ["umur", "usia", "tahun", "kelas", "grade", "sd", "smp", "sma", "age", "years"],
                    "forbidden": ["nanti", "sebentar"]  # Promises to ask later
                }
            },
            {
                "id": "profile_interests",
                "type": "discuss",
                "content": "Tanyakan minat anak (game, aktivitas, pelajaran)",
                "extended_description": "The tutor must ask about what the child likes. Look for explicit questions such as 'suka apa?', 'game favorit apa?', 'hobi apa?', or answers revealing interests like 'suka Roblox', 'hobi menggambar'.",
                "semantic_keywords": {
                    "required": ["suka", "hobi", "hobby", "favorit", "game", "main", "senang"],
                    "forbidden": ["nanti", "coba"]  # Promises to ask later
                }
            },
            {
                "id": "profile_learning_preferences",
                "type": "discuss",
                "content": "Tanyakan preferensi belajar anak",
                "extended_description": "Tutor must understand how the child prefers to learn: visual, hands-on, guided steps, independent exploration, etc. AI should detect questions like 'lebih suka belajar bagaimana?', 'lebih nyaman dengan cara apa?'",
                "semantic_keywords": {
                    "required": ["belajar", "cara", "preferensi", "comfortable", "suka belajar", "lebih suka"],
                    "forbidden": ["nanti", "mungkin"]
                }
            },
            {
                "id": "profile_hobbies_activities",
                "type": "discuss",
                "content": "Tanyakan aktivitas harian dan hobi anak",
                "extended_description": "Tutor must explore child's daily routine and other interests outside gaming, such as sports, reading, drawing, or extracurriculars. This helps build personalized recommendations.",
                "semantic_keywords": {
                    "required": ["aktivitas", "harian", "hobi", "kegiatan", "rutinitas", "les", "ekskul"],
                    "forbidden": ["nanti", "sebentar"]
                }
            }
        ]
    },
    {
        "id": "stage_real_points",
        "name": "Real Points",
        "startOffsetSeconds": 600,
        "durationSeconds": 300,
        "items": [
            {
                "id": "explain_difference_from_school",
                "type": "say",
                "content": "Jelaskan perbedaan Algonova dengan sekolah",
                "extended_description": "Tutor must explain how Algonova's approach differs from traditional school: project-based, creative, interactive, personalized pacing. Must be explicit comparison.",
                "semantic_keywords": {
                    "required": ["beda", "perbedaan", "sekolah", "school", "algonova", "pendekatan", "project"],
                    "forbidden": ["nanti", "akan", "mungkin"]  # Promises to explain later
                }
            },
            {
                "id": "explain_coding_design",
                "type": "say",
                "content": "Jelaskan secara sederhana apa itu coding atau design",
                "extended_description": "Tutor must give a simple, child-friendly explanation of coding or design. AI should detect explanatory phrases like 'coding itu…', 'design itu…', 'is like…', not just asking questions.",
                "semantic_keywords": {
                    "required": ["coding", "design", "buat", "membuat", "program", "code", "desain"],
                    "forbidden": ["nanti", "mau", "akan"]  # Asking, not explaining
                }
            },
            {
                "id": "imagination_role",
                "type": "say",
                "content": "Ajak anak membayangkan menjadi gamedev/animator muda",
                "extended_description": "Tutor must help the child imagine themselves creating something: being a young game developer or animator. Look for imaginative prompts like 'bayangkan…', 'imagine if…'.",
                "semantic_keywords": {
                    "required": ["bayangkan", "imajinasi", "imagine", "gamedev", "game developer", "animator"],
                    "forbidden": ["nanti", "sebentar lagi"]  # Promises for later
                }
            },
            {
                "id": "ask_what_to_create",
                "type": "discuss",
                "content": "Tanyakan anak ingin membuat apa",
                "extended_description": "Tutor must ask what the child wants to create: game, character, animation, world, etc. Evidence must include a direct question.",
                "semantic_keywords": {
                    "required": ["buat apa", "ingin buat", "mau buat", "create", "make", "membuat"],
                    "forbidden": ["nanti", "sebentar"]  # Promises to ask later
                }
            }
        ]
    },
    {
        "id": "stage_profiling_summary",
        "name": "Profiling Summary",
        "startOffsetSeconds": 900,
        "durationSeconds": 180,
        "items": [
            {
                "id": "summary_child",
                "type": "say",
                "content": "Ringkas profil anak berdasarkan jawaban",
                "extended_description": "Tutor must summarize: child's age, interests, preferences, strengths. A structured recap is required.",
                "semantic_keywords": {
                    "required": ["ringkas", "summary", "jadi", "berarti", "profil", "anak"],
                    "forbidden": ["nanti", "akan", "sebentar"]  # Incomplete summary
                }
            },
            {
                "id": "summary_parent",
                "type": "say",
                "content": "Ringkas sudut pandang dan harapan orang tua",
                "extended_description": "Tutor must summarize parent concerns and goals in one coherent statement.",
                "semantic_keywords": {
                    "required": ["orang tua", "parent", "harapan", "goal", "tujuan", "ingin"],
                    "forbidden": ["nanti", "mungkin"]
                }
            },
            {
                "id": "recommend_course",
                "type": "say",
                "content": "Rekomendasikan course yang paling sesuai",
                "extended_description": "Tutor must recommend a course based on profiling: coding, design, gamedev, etc., and explain why it matches the child.",
                "semantic_keywords": {
                    "required": ["rekomendasi", "course", "kelas", "cocok", "sesuai"],
                    "forbidden": ["mungkin", "coba", "nanti"]  # Uncertain recommendation
                }
            }
        ]
    },
    {
        "id": "stage_practical",
        "name": "Practical Session",
        "startOffsetSeconds": 1080,
        "durationSeconds": 1200,
        "items": [
            {
                "id": "guide_tasks",
                "type": "say",
                "content": "Pandu guide anak dalam menyelesaikan tugas",
                "extended_description": "Tutor must actively guide the child through tasks: giving instructions, hints, and steps.",
                "semantic_keywords": {
                    "required": ["klik", "coba", "ikut", "ikuti", "step", "langkah"],
                    "forbidden": ["nanti", "sebentar", "tunggu dulu"]  # Not actively guiding
                }
            },
            {
                "id": "ask_what_learned",
                "type": "discuss",
                "content": "Tanyakan apa yang anak pelajari",
                "extended_description": "Tutor must ask child to explain what they learned to reinforce understanding.",
                "semantic_keywords": {
                    "required": ["belajar", "apa yang", "yang kamu pelajari", "learn"],
                    "forbidden": ["nanti", "sebentar"]
                }
            },
            {
                "id": "ask_parent_feedback",
                "type": "discuss",
                "content": "Tanyakan feedback dari orang tua",
                "extended_description": "Tutor must request parent's feedback and respond with empathy. AI should detect references to 'bagaimana menurut Mama/Papa…?'",
                "semantic_keywords": {
                    "required": ["feedback", "pendapat", "menurut", "orang tua", "mama", "papa"],
                    "forbidden": ["nanti", "sebentar"]
                }
            }
        ]
    },
    {
        "id": "stage_presentation",
        "name": "Presentation",
        "startOffsetSeconds": 2280,
        "durationSeconds": 420,
        "items": [
            {
                "id": "introduce_school",
                "type": "say",
                "content": "Perkenalkan Algonova sebagai sekolah internasional",
                "extended_description": "Tutor must explicitly frame Algonova as an international school with global curriculum.",
                "semantic_keywords": {
                    "required": ["algonova", "international", "school", "sekolah"],
                    "forbidden": ["nanti", "mungkin"]
                }
            },
            {
                "id": "share_achievements",
                "type": "say",
                "content": "Ceritakan prestasi dan hasil karya murid",
                "extended_description": "Tutor must show or mention real student achievements, projects, or success stories.",
                "semantic_keywords": {
                    "required": ["prestasi", "achievement", "hasil karya", "project", "murid"],
                    "forbidden": ["nanti", "mungkin"]
                }
            },
            {
                "id": "explain_learning_path",
                "type": "say",
                "content": "Jelaskan course lain dan learning path jangka panjang",
                "extended_description": "Tutor must explain progression: from basic to advanced levels, different courses, and long-term path.",
                "semantic_keywords": {
                    "required": ["learning path", "kurikulum", "lanjutan", "course", "level"],
                    "forbidden": ["nanti", "mungkin"]
                }
            }
        ]
    },
    {
        "id": "stage_bridging",
        "name": "Bridging",
        "startOffsetSeconds": 2700,
        "durationSeconds": 300,
        "items": [
            {
                "id": "bridge_needs",
                "type": "say",
                "content": "Hubungkan hasil profiling dengan kebutuhan anak",
                "extended_description": "Tutor must explicitly link the parent's goals and the child's profile to the recommended class.",
                "semantic_keywords": {
                    "required": ["kebutuhan", "need", "tujuan", "profil", "cocok"],
                    "forbidden": ["nanti", "mungkin", "coba"]
                }
            },
            {
                "id": "bridge_results",
                "type": "say",
                "content": "Hubungkan hasil sesi praktik dengan potensi anak",
                "extended_description": "Tutor must describe what the child achieved in practical session and how this shows their potential.",
                "semantic_keywords": {
                    "required": ["hasil", "result", "praktik", "potensi", "bisa"],
                    "forbidden": ["nanti", "mungkin"]
                }
            }
        ]
    },
    {
        "id": "stage_negotiation",
        "name": "Negotiation",
        "startOffsetSeconds": 3000,
        "durationSeconds": 600,
        "items": [
            {
                "id": "recommend_class_type",
                "type": "say",
                "content": "Rekomendasikan tipe kelas (Private / Premium / Group)",
                "extended_description": "Tutor must recommend the class type clearly, not just list options.",
                "semantic_keywords": {
                    "required": ["private", "premium", "group", "rekomendasi", "kelas"],
                    "forbidden": ["mungkin", "coba", "terserah"]  # Uncertain or leaving it to client
                }
            },
            {
                "id": "handle_objections",
                "type": "discuss",
                "content": "Tanyakan keberatan dan jawab dengan empati",
                "extended_description": "Tutor must clarify and handle objections using empathetic responses.",
                "semantic_keywords": {
                    "required": ["kendala", "keberatan", "masalah", "harga", "waktu", "khawatir"],
                    "forbidden": ["tidak tahu", "tidak bisa", "maaf"]  # Weak responses
                }
            },
            {
                "id": "clarify_policies",
                "type": "say",
                "content": "Jelaskan refund, jadwal, dan harga dengan jelas",
                "extended_description": "Tutor must clearly explain refund policy, scheduling, and pricing.",
                "semantic_keywords": {
                    "required": ["refund", "jadwal", "schedule", "harga", "price", "policy"],
                    "forbidden": ["tidak tahu", "mungkin", "nanti"]  # Unclear explanations
                }
            }
        ]
    },
    {
        "id": "stage_closure",
        "name": "Closure",
        "startOffsetSeconds": 3600,
        "durationSeconds": 300,
        "items": [
            {
                "id": "close_call",
                "type": "say",
                "content": "Akhiri panggilan dengan profesional",
                "extended_description": "Tutor must end the call politely and clearly.",
                "semantic_keywords": {
                    "required": ["terima kasih", "thank you", "sampai jumpa", "see you"],
                    "forbidden": ["nanti", "tunggu"]  # Incomplete closing
                }
            },
            {
                "id": "closure_positive_if_paid",
                "type": "say",
                "content": "Jika sudah bayar, sambut dengan hangat dan beri arahan selanjutnya",
                "extended_description": "If payment is done, tutor must warmly welcome and explain next steps.",
                "semantic_keywords": {
                    "required": ["selamat", "welcome", "langkah berikutnya", "next step"],
                    "forbidden": ["mungkin", "nanti"]
                }
            },
            {
                "id": "closure_if_not_paid",
                "type": "say",
                "content": "Jika belum bayar, tetap tinggalkan kesan positif",
                "extended_description": "If not purchased yet, the tutor must leave a positive, encouraging impression.",
                "semantic_keywords": {
                    "required": ["tidak apa", "boleh nanti", "kapan saja", "positif"],
                    "forbidden": ["harus", "wajib"]  # Pressuring language
                }
            }
        ]
    }
]


def get_default_call_structure() -> List[CallStage]:
    """Get the default call structure configuration"""
    return DEFAULT_CALL_STRUCTURE


def get_stage_by_time(elapsed_seconds: int) -> str:
    """
    Determine current stage based on elapsed time (FALLBACK ONLY)
    
    NOTE: This is now a fallback. Use detect_stage_by_context() for AI-based detection.
    
    Args:
        elapsed_seconds: Seconds since call start
        
    Returns:
        Stage ID that should be active at this time
    """
    structure = get_default_call_structure()
    
    for stage in reversed(structure):  # Check from end to start
        if elapsed_seconds >= stage['startOffsetSeconds']:
            return stage['id']
    
    return structure[0]['id'] if structure else ""


def detect_stage_by_context(
    conversation_text: str,
    elapsed_seconds: int,
    analyzer,  # TrialClassAnalyzer instance
    previous_stage_id: str = None,
    min_confidence: float = 0.6
) -> str:
    """
    Detect current stage using AI analysis of conversation context
    
    Args:
        conversation_text: Recent conversation transcript
        elapsed_seconds: Current call time (for context only)
        analyzer: TrialClassAnalyzer instance with detect_current_stage method
        previous_stage_id: Last detected stage (to prevent jitter)
        min_confidence: Minimum confidence to accept stage change
        
    Returns:
        Stage ID that matches the current conversation context
    """
    structure = get_default_call_structure()
    if not structure:
        return ""
    
    # Guard: Skip if conversation too short
    if len(conversation_text.strip()) < 100:
        # At start, use first stage
        return structure[0]['id']
    
    try:
        # Use AI to detect stage
        detected_stage_id, confidence = analyzer.detect_current_stage(
            conversation_text=conversation_text,
            stages=structure,
            call_elapsed_seconds=elapsed_seconds
        )
        
        # If confident, use AI detection
        if confidence >= min_confidence:
            return detected_stage_id
        
        # Low confidence - check if should keep previous stage
        if previous_stage_id and confidence < min_confidence:
            # Don't change stage on low confidence
            return previous_stage_id
        
        # Fallback to time-based
        print(f"   ⚠️ Low confidence ({confidence:.0%}), using time-based fallback")
        return get_stage_by_time(elapsed_seconds)
        
    except Exception as e:
        print(f"   ⚠️ Stage detection error: {e}, using time-based fallback")
        return get_stage_by_time(elapsed_seconds)


def get_stage_timing_status(stage_id: str, elapsed_seconds: int) -> Dict[str, Any]:
    """
    Check if a stage is on time, late, or not started
    
    Args:
        stage_id: The stage to check
        elapsed_seconds: Current call time
        
    Returns:
        Dict with status: 'not_started' | 'on_time' | 'slightly_late' | 'very_late'
    """
    structure = get_default_call_structure()
    stage = next((s for s in structure if s['id'] == stage_id), None)
    
    if not stage:
        return {'status': 'unknown', 'message': 'Stage not found'}
    
    stage_start = stage['startOffsetSeconds']
    stage_end = stage_start + stage['durationSeconds']
    
    if elapsed_seconds < stage_start:
        return {
            'status': 'not_started',
            'message': f"Starts in {(stage_start - elapsed_seconds) // 60} min"
        }
    elif elapsed_seconds <= stage_end:
        return {
            'status': 'on_time',
            'message': 'On track'
        }
    elif elapsed_seconds <= stage_end + 120:  # 2 min grace period
        return {
            'status': 'slightly_late',
            'message': 'Slightly behind'
        }
    else:
        minutes_late = (elapsed_seconds - stage_end) // 60
        return {
            'status': 'very_late',
            'message': f"{minutes_late} min behind"
        }


def validate_call_structure(structure: List[Dict]) -> bool:
    """
    Validate a call structure configuration
    
    Args:
        structure: List of stage dictionaries
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    required_stage_fields = ['id', 'name', 'startOffsetSeconds', 'durationSeconds', 'items']
    required_item_fields = ['id', 'type', 'content', 'extended_description', 'semantic_keywords']
    
    if not isinstance(structure, list):
        raise ValueError("Structure must be a list or empty.")
    
    if not structure:
        return True # An empty structure is valid

    stage_ids = set()
    item_ids = set()
    
    for stage in structure:
        # Check required fields
        for field in required_stage_fields:
            if field not in stage:
                raise ValueError(f"Stage missing required field: {field}")
        
        # Check unique stage ID
        if stage['id'] in stage_ids:
            raise ValueError(f"Duplicate stage ID: {stage['id']}")
        stage_ids.add(stage['id'])
        
        # Validate items
        if not isinstance(stage['items'], list):
            raise ValueError(f"Stage {stage['id']} items must be a list")
        
        for item in stage['items']:
            for field in required_item_fields:
                if field not in item:
                    raise ValueError(f"Item missing required field: {field}")
            
            # Check unique item ID (globally)
            if item['id'] in item_ids:
                raise ValueError(f"Duplicate item ID: {item['id']}")
            item_ids.add(item['id'])
            
            # Validate item type
            if item['type'] not in ['discuss', 'say']:
                raise ValueError(f"Item type must be 'discuss' or 'say', got: {item['type']}")
            
            # Validate semantic_keywords structure
            if 'semantic_keywords' in item:
                keywords = item['semantic_keywords']
                if not isinstance(keywords, dict):
                    raise ValueError(f"semantic_keywords must be a dict in item {item['id']}")
                if 'required' in keywords and not isinstance(keywords['required'], list):
                    raise ValueError(f"semantic_keywords.required must be a list in item {item['id']}")
                if 'forbidden' in keywords and not isinstance(keywords['forbidden'], list):
                    raise ValueError(f"semantic_keywords.forbidden must be a list in item {item['id']}")
    
    return True
