"""
Trial Class Call Analyzer

Real-time LLM analysis specifically for trial class sales calls.
Handles:
1. Checklist item completion detection
2. Client card field extraction
3. Uses Indonesian conversation context

Optimized for low latency and cost.
"""

import json
import os
from typing import Dict, List, Tuple, Optional
import requests
from dotenv import load_dotenv

from call_structure_config import get_default_call_structure
from client_card_config import get_default_client_card_fields, get_extraction_hint

load_dotenv()

# VERSION MARKER - If you see this, the latest code is loaded!
print("=" * 60)
print("🚀 TRIAL CLASS ANALYZER MODULE LOADED")
print("📦 Version: 2025-11-21 (Gemini 2.5 Flash HARDCODED)")
print("=" * 60)


class TrialClassAnalyzer:
    """LLM-based analyzer for trial class sales calls"""
    
    def __init__(self, model: str = None):
        """
        Initialize analyzer
        
        Args:
            model: IGNORED - model is hardcoded to Gemini 2.5 Flash
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # HARDCODED: Always use Gemini 2.5 Flash (ignores model parameter and env vars)
        self.model = "google/gemini-2.5-flash-preview-09-2025"
        print(f"🤖 Trial Class Analyzer initialized with model: {self.model}")
        
        # Load configs
        self.call_structure = get_default_call_structure()
        self.client_card_fields = get_default_client_card_fields()
    
    def check_checklist_item(
        self,
        item: Dict,
        conversation_text: str
    ) -> Tuple[bool, float, str, Dict]:
        """
        Check if a checklist item has been completed
        
        Args:
            item_id: Item identifier
            item_content: What should be discussed/said
            item_type: "discuss" or "say"
            conversation_text: Recent conversation (Indonesian)
            
        Returns:
            (completed: bool, confidence: float, evidence: str, debug_info: dict)
        """
        # Guard: Skip if conversation too short
        if len(conversation_text.strip()) < 30:
            debug_info = {
                "stage": "guard_context_too_short",
                "context_length": len(conversation_text.strip())
            }
            return False, 0.0, "Insufficient conversation context", debug_info
        
        item_id = item['id']
        item_content = item['content']
        item_type = item['type']
        extended_description = item.get('extended_description', '')

        # Build prompt based on item type
        if item_type == "discuss":
            action_description = "asked about or discussed"
        else:  # "say"
            action_description = "explained or mentioned"
        
        # Build specific instructions based on type
        if item_type == "discuss":
            type_specific = """
TYPE: DISCUSS/ASK
This means you must find:
✅ A QUESTION being asked, OR
✅ An ANSWER that proves the question was asked

GOOD examples for "discuss":
- Action: "Ask about child's age"
  Evidence: "Anaknya umur berapa?" ✓ (direct question)
  Evidence: "Anaknya 8 tahun" ✓ (answer proves question was asked)
  
BAD examples:
- Evidence: "Anak suka belajar" ✗ (no question about age)
- Evidence: "Oke, baik" ✗ (just acknowledgment)
- Evidence: "Nanti kita diskusi umur" ✗ (promise to discuss, not actual discussion)
"""
        else:  # "say"
            type_specific = """
TYPE: SAY/EXPLAIN
This means you must find:
✅ The manager STATING or EXPLAINING something
✅ NOT just asking about it, but actually TELLING

GOOD examples for "say":
- Action: "Explain how platform works"
  Evidence: "Platform kami seperti game interaktif untuk belajar coding" ✓ (actual explanation)
  
BAD examples:
- Evidence: "Mau tau cara kerja platform?" ✗ (asking, not explaining)
- Evidence: "Nanti saya jelaskan" ✗ (promise to explain, not explanation)
- Evidence: "Platform bagus" ✗ (opinion, not explanation)
"""

        prompt = f"""You are a STRICT quality checker analyzing a sales call in Bahasa Indonesia.

TASK: Check if this action was completed:
Action: "{item_content}"

ADDITIONAL CONTEXT: {extended_description}

Recent conversation (Bahasa Indonesia):
{conversation_text}

{type_specific}

CRITICAL VALIDATION RULES:
1. Evidence must be a DIRECT QUOTE from conversation
2. Evidence must CLEARLY AND OBVIOUSLY show the action was done
3. Generic phrases like "oke", "baik", "ya" are NEVER valid evidence
4. Greetings ("selamat pagi", "halo") are NEVER valid evidence
5. Promises to do something ("nanti", "akan") are NOT completion
6. If you're even 20% unsure → mark completed=false

CONFIDENCE GUIDELINES:
- 90-100%: Action CLEARLY done, evidence is perfect
- 70-89%: Likely done, evidence is good but not perfect
- 50-69%: Possibly done, evidence is weak
- <50%: Probably not done or no evidence

BE EXTREMELY CONSERVATIVE. When in doubt, mark as NOT completed.

Return ONLY valid JSON:
{{
  "completed": true/false,
  "confidence": 0.0-1.0,
  "evidence": "exact quote showing action (empty if not completed)",
  "reasoning": "WHY this evidence proves (or doesn't prove) the action"
}}
"""
        
        try:
            response = self._call_llm(prompt, temperature=0.2, max_tokens=200)
            result = json.loads(response)
            
            completed = result.get("completed", False)
            confidence = result.get("confidence", 0.0)
            evidence = result.get("evidence", "")
            reasoning = result.get("reasoning", "")
            
            debug_info = {
                "stage": "initial_check",
                "context_preview": conversation_text[-200:],  # Last 200 chars
                "first_completed": completed,
                "first_confidence": confidence,
                "first_evidence": evidence,
                "first_reasoning": reasoning,
                "guards_passed": []
            }
            
            # Guard 1: Only accept high confidence completions
            if completed and confidence < 0.8:
                debug_info["stage"] = "guard_1_low_confidence"
                debug_info["guards_passed"].append("confidence < 0.8")
                return False, confidence, "Confidence too low", debug_info
            
            # Guard 2: Evidence must exist and be substantial
            if completed and len(evidence.strip()) < 10:
                debug_info["stage"] = "guard_2_evidence_too_short"
                debug_info["guards_passed"].append("evidence length < 10")
                return False, confidence, "Evidence too short", debug_info
            
            # Guard 3: Validate evidence relevance with second LLM call
            # With stricter validation, we can check items with lower confidence
            validation_result = None
            if completed and confidence >= 0.7:
                validation_passed = self._validate_evidence_relevance(
                    item_content=item_content,
                    evidence=evidence,
                    reasoning=reasoning,
                    item_type=item_type
                )
                validation_result = validation_passed
                debug_info["validation_passed"] = validation_passed
                
                if not validation_passed:
                    print(f"   ⚠️ Evidence validation FAILED for '{item_content[:50]}...'")
                    debug_info["stage"] = "guard_3_validation_failed"
                    debug_info["guards_passed"].append("validation failed")
                    return False, confidence, f"Evidence not relevant: {evidence[:100]}", debug_info
            
            debug_info["stage"] = "accepted"
            debug_info["final_decision"] = "completed" if completed else "not_completed"
            return completed, confidence, evidence, debug_info
            
        except Exception as e:
            print(f"   ⚠️ Item check failed for {item_id}: {e}")
            debug_info = {
                "stage": "error",
                "error": str(e)
            }
            return False, 0.0, str(e), debug_info
    
    def _validate_evidence_relevance(
        self,
        item_content: str,
        evidence: str,
        reasoning: str,
        item_type: str = "discuss"
    ) -> bool:
        """
        Validate that evidence actually proves the action was completed
        This is a second-pass check to catch false positives
        
        Args:
            item_content: The action that should be completed
            evidence: The quote provided as proof
            reasoning: The reasoning from first check
            item_type: Type of action ("discuss" or "say")
            
        Returns:
            True if evidence is relevant, False if not
        """
        print(f"      🔍 VALIDATING Evidence for: '{item_content[:60]}...'")
        print(f"         Evidence: '{evidence[:100]}...'")
        
        if not evidence or len(evidence.strip()) < 5:
            print(f"      🚫 Rejected: Evidence too short or empty")
            return False
        
        # Hard-coded filters for obviously invalid evidence
        evidence_lower = evidence.lower().strip()
        
        # List of phrases that are NEVER valid evidence
        invalid_phrases = [
            "oke",
            "ok",
            "baik",
            "ya",
            "halo",
            "hai",
            "selamat pagi",
            "selamat siang", 
            "selamat datang",
            "terima kasih",
            "sama-sama",
            "silakan",
            "monggo",
            "gimana",
            "apa kabar"
        ]
        
        # Filter out self-introductions (these are NEVER evidence for questions/discussions)
        introduction_patterns = [
            "nama saya",
            "saya adalah",
            "perkenalkan",
            "kenalkan",
            "mr.",
            "ms.",
            "tutor",
            "teacher",
            "guru"
        ]
        
        # If evidence looks like an introduction, reject it
        if any(pattern in evidence_lower for pattern in introduction_patterns):
            # Exception: if the action is specifically about introductions
            action_lower = item_content.lower()
            if not any(word in action_lower for word in ["greet", "introduce", "perkenalkan", "salam"]):
                print(f"      🚫 Rejected: Evidence is self-introduction, not relevant to '{item_content[:50]}...'")
                print(f"         Evidence: '{evidence[:80]}...'")
                return False
        
        # If evidence is ONLY a generic phrase, reject immediately
        for phrase in invalid_phrases:
            if evidence_lower == phrase or evidence_lower == phrase + ".":
                print(f"      🚫 Rejected: Evidence is just generic phrase '{phrase}'")
                return False
        
        # If evidence is too short (less than 3 words), likely invalid
        word_count = len(evidence.split())
        if word_count < 3:
            print(f"      🚫 Rejected: Evidence too short ({word_count} words)")
            return False
        
        # CRITICAL: Keyword-based semantic check
        # Extract keywords from action to check evidence relevance
        action_lower = item_content.lower()
        
        # Define keyword mappings for common actions
        keyword_checks = [
            # Age/Grade questions
            {
                "triggers": ["age", "umur", "usia", "grade", "kelas", "tahun"],
                "required_in_evidence": ["umur", "usia", "tahun", "kelas", "grade", "sd", "smp", "sma", "tk"]
            },
            # Interests/Likes
            {
                "triggers": ["interest", "like", "suka", "hobi", "kesukaan", "favorite"],
                "required_in_evidence": ["suka", "hobi", "main", "game", "olahraga", "favorit", "senang"]
            },
            # Concerns/Problems
            {
                "triggers": ["concern", "challenge", "masalah", "khawatir", "kesulitan", "tantangan"],
                "required_in_evidence": ["khawatir", "masalah", "kesulitan", "concern", "tantangan", "susah", "kurang"]
            },
            # Goals
            {
                "triggers": ["goal", "tujuan", "harapan", "ingin", "mau"],
                "required_in_evidence": ["tujuan", "harapan", "ingin", "mau", "supaya", "agar", "bisa", "goals"]
            },
            # Experience
            {
                "triggers": ["experience", "pengalaman", "pernah", "sudah"],
                "required_in_evidence": ["pernah", "sudah", "pengalaman", "biasa", "sering", "belum"]
            }
        ]
        
        # Check if action matches any keyword pattern
        for check in keyword_checks:
            # If action contains trigger words
            if any(trigger in action_lower for trigger in check["triggers"]):
                # Evidence MUST contain at least one required word
                has_required = any(word in evidence_lower for word in check["required_in_evidence"])
                if not has_required:
                    print(f"      🚫 Rejected: Evidence lacks semantic keywords for '{item_content[:50]}...'")
                    print(f"         Evidence: '{evidence[:100]}...'")
                    print(f"         Required one of: {check['required_in_evidence'][:5]}")
                    return False
        
        # Build type-specific instructions
        if item_type == "discuss":
            type_check = """
ACTION TYPE: DISCUSS/ASK
The evidence MUST show either:
1. A QUESTION being asked (e.g., "berapa umur?", "apa yang...", "bagaimana...")
2. An ANSWER that implies the question was asked (e.g., "usia 8 tahun" for "ask about age")

REJECT if evidence is:
- Just acknowledgment ("oke", "baik")
- Unrelated statement that doesn't answer the question
- Promise to discuss later ("nanti kita bahas")
"""
        else:  # "say"
            type_check = """
ACTION TYPE: SAY/EXPLAIN
The evidence MUST show:
1. The manager STATING or EXPLAINING information
2. NOT asking a question, but GIVING information

REJECT if evidence is:
- A question instead of statement
- Just mentioning a topic without explaining
- Promise to explain later ("nanti saya jelaskan")
"""
        
        validation_prompt = f"""You are a STRICT evidence validator for a sales call checklist.

REQUIRED ACTION:
"{item_content}"

PROVIDED EVIDENCE:
"{evidence}"

ORIGINAL REASONING:
"{reasoning}"

{type_check}

CRITICAL CHECKS:
1. Does evidence contain actual content (not just "oke", "ya", "baik")?
2. Does evidence SEMANTICALLY match the action topic?
3. Is evidence specific enough to prove completion?
4. Does evidence match the action type (discuss vs explain)?

EXAMPLES OF INVALID MATCHING:
❌ Action: "Ask about child's age" 
   Evidence: "Oke, selamat datang" 
   → NO semantic connection to age

❌ Action: "Identify parent concerns"
   Evidence: "semisal cocok ya saya sih kedua-nya"
   → Doesn't express any concern

❌ Action: "Explain curriculum structure"
   Evidence: "Mau tau kurikulum kami?"
   → Asking, not explaining

EXAMPLES OF VALID MATCHING:
✅ Action: "Ask about child's age"
   Evidence: "Anaknya berapa tahun?"
   → Direct question about age

✅ Action: "Identify parent concerns"  
   Evidence: "Papa khawatir anak kurang fokus"
   → Clearly states a concern

BE EXTREMELY STRICT. If there's ANY doubt, mark as invalid.

Return ONLY valid JSON:
{{
  "is_valid": true/false,
  "explanation": "specific reason why evidence does/doesn't prove the action"
}}
"""
        
        try:
            response = self._call_llm(validation_prompt, temperature=0.05, max_tokens=150)
            result = json.loads(response)
            is_valid = result.get("is_valid", False)
            explanation = result.get("explanation", "")
            
            if not is_valid:
                print(f"      🔍 Validation REJECTED: {explanation}")
            else:
                print(f"      ✅ Validation PASSED: {explanation}")
            
            return is_valid
            
        except Exception as e:
            print(f"   ⚠️ Evidence validation error: {e}")
            # On error, be conservative - reject to avoid false positives
            return False
    
    def extract_client_card_fields(
        self,
        conversation_text: str,
        current_values: Dict[str, str]
    ) -> Dict[str, Dict[str, str]]:
        """
        Extract/update client card fields from conversation
        
        Args:
            conversation_text: Recent conversation in Indonesian
            current_values: Current field values (to avoid rewriting)
            
        Returns:
            Dict of field_id → {value: str, evidence: str} (only fields with new info)
        """
        # Guard: Skip if conversation too short (need substantial conversation)
        if len(conversation_text.strip()) < 200:
            return {}
        
        # Build field descriptions for LLM
        field_descriptions = []
        for field in self.client_card_fields:
            field_id = field['id']
            label = field['label']
            hint = get_extraction_hint(field_id)
            current = current_values.get(field_id, "")
            
            field_descriptions.append(f"- {field_id} ({label}): {hint}")
        
        fields_str = "\n".join(field_descriptions)
        
        prompt = f"""You are analyzing a sales call in Bahasa Indonesia to extract client information.

Conversation (Bahasa Indonesia):
{conversation_text}

Extract information for these fields (only if clearly mentioned):
{fields_str}

CRITICAL RULES:
1. Only extract if CONFIDENT and EXPLICITLY mentioned
2. Keep extractions brief (1-2 sentences max per field)
3. If not mentioned, DO NOT INCLUDE the field in response AT ALL
4. Conversation is in Indonesian, but respond in English
5. Evidence MUST be a direct quote that PROVES the information
6. DO NOT extract from greetings, acknowledgments, or unrelated text
7. NEVER use placeholder values like "Tidak disebutkan", "Not mentioned", "Unknown", "-", "N/A"
8. If unsure or information is vague, SKIP THE FIELD ENTIRELY

EVIDENCE MUST BE RELEVANT:
✅ GOOD:
   Field: child_name
   Value: "Andi"
   Evidence: "Nama anaknya Andi"

✅ GOOD:
   Field: child_interests
   Value: "Playing Roblox and Minecraft"
   Evidence: "Andi suka main Roblox dan Minecraft"

❌ BAD:
   Field: child_name
   Value: "Seki"
   Evidence: "Oke, selamat datang, Seki" ← Just greeting!

❌ BAD:
   Field: parent_goal
   Value: "Learning"
   Evidence: "Kita akan belajar hari ini" ← Not parent's goal!

❌ EXTREMELY BAD - NEVER DO THIS:
   {{
     "child_name": {{"value": "Tidak disebutkan", ...}},
     "child_interests": {{"value": "Tidak disebutkan", ...}},
     ...
   }}
   ← DON'T fill fields with "tidak disebutkan"! Just omit them!

CORRECT EXAMPLE when info is missing:
   {{}}  ← Return empty object, NOT fields with "tidak disebutkan"!

CORRECT EXAMPLE when only child_name is mentioned:
   {{
     "child_name": {{
       "value": "Andi",
       "evidence": "Nama anaknya Andi",
       "confidence": 0.95
     }}
   }}  ← Only include fields that are ACTUALLY mentioned!

Return ONLY valid JSON with confidence:
{{
  "field_id": {{
    "value": "extracted text (NEVER 'tidak disebutkan' or similar)",
    "evidence": "direct quote proving this information",
    "confidence": 0.0-1.0
  }}
}}

If no clear information found, return EMPTY object: {{}}
"""
        
        try:
            response = self._call_llm(prompt, temperature=0.3, max_tokens=800)
            result = json.loads(response)
            
            # Filter out fields that already have values (don't overwrite unless significantly different)
            updates = {}
            for field_id, field_data in result.items():
                if field_id in current_values and current_values[field_id]:
                    # Skip if we already have this field filled
                    continue
                
                # Handle both old format (string) and new format (dict with value/evidence)
                if isinstance(field_data, dict):
                    value = field_data.get('value', '')
                    evidence = field_data.get('evidence', '')
                    confidence = field_data.get('confidence', 1.0)
                else:
                    value = str(field_data)
                    evidence = ''
                    confidence = 1.0
                
                # Guard 0: Reject placeholder values (LLM hallucinations)
                value_lower = value.lower().strip()
                placeholder_values = [
                    "tidak disebutkan",
                    "not mentioned",
                    "unknown",
                    "tidak ada",
                    "tidak jelas",
                    "belum disebutkan",
                    "n/a",
                    "na",
                    "-",
                    "none"
                ]
                if value_lower in placeholder_values or any(placeholder in value_lower for placeholder in ["tidak di", "not men", "belum di"]):
                    print(f"   🚫 Rejected placeholder value for {field_id}: '{value}'")
                    continue
                
                # Guard 1: Value must be substantial
                if not value or len(value.strip()) <= 5:
                    continue
                
                # Guard 2: Confidence must be high
                if confidence < 0.7:
                    print(f"   ⚠️ Low confidence ({confidence:.0%}) for {field_id}, skipping")
                    continue
                
                # Guard 3: Evidence must exist
                if not evidence or len(evidence.strip()) < 10:
                    print(f"   ⚠️ Evidence too short for {field_id}, skipping")
                    continue
                
                # Guard 4: Validate evidence relevance
                # Get field label for validation
                field_label = next((f['label'] for f in self.client_card_fields if f['id'] == field_id), field_id)
                
                validation_passed = self._validate_client_field_evidence(
                    field_label=field_label,
                    value=value,
                    evidence=evidence
                )
                
                if not validation_passed:
                    print(f"   ⚠️ Evidence validation FAILED for {field_id}")
                    continue
                
                updates[field_id] = {
                    'value': value.strip(),
                    'evidence': evidence.strip(),
                    'confidence': confidence,
                    'label': field_label
                }
            
            return updates
            
        except Exception as e:
            print(f"   ⚠️ Client card extraction failed: {e}")
            return {}
    
    def _validate_client_field_evidence(
        self,
        field_label: str,
        value: str,
        evidence: str
    ) -> bool:
        """
        Validate that evidence actually proves the extracted client information
        This prevents false extractions from greetings or unrelated text
        
        Args:
            field_label: Human-readable field name (e.g. "Child's Name")
            value: The extracted value
            evidence: The quote provided as proof
            
        Returns:
            True if evidence is relevant, False if not
        """
        if not evidence or len(evidence.strip()) < 5:
            return False
        
        # Hard-coded filters for obviously invalid evidence
        evidence_lower = evidence.lower().strip()
        
        # Reject common greeting/acknowledgment phrases
        invalid_starts = [
            "oke,",
            "ok,",
            "baik,",
            "ya,",
            "halo,",
            "hai,",
            "selamat pagi",
            "selamat siang",
            "selamat datang",
            "terima kasih"
        ]
        
        for start in invalid_starts:
            if evidence_lower.startswith(start):
                print(f"      🚫 Client field rejected: Evidence starts with greeting '{start}'")
                return False
        
        # Evidence must be substantial (at least 3 words)
        word_count = len(evidence.split())
        if word_count < 3:
            print(f"      🚫 Client field rejected: Evidence too short ({word_count} words)")
            return False
        
        # Check if value appears in evidence (it should!)
        # This catches cases where LLM hallucinates
        value_lower = value.lower().strip()
        
        # For names and specific values, they should appear in evidence
        if len(value.split()) <= 3:  # Short values like names, ages
            # Allow some flexibility (partial match, transliteration)
            value_words = value_lower.split()
            matches = sum(1 for word in value_words if word in evidence_lower)
            if matches == 0 and len(value) > 3:
                print(f"      🚫 Client field rejected: Value '{value}' not found in evidence")
                return False
        
        validation_prompt = f"""You are a STRICT validator for client information extraction.

FIELD: {field_label}
EXTRACTED VALUE: "{value}"
PROVIDED EVIDENCE: "{evidence}"

TASK: Verify that the evidence DIRECTLY AND CLEARLY proves this specific information.

CRITICAL CHECKS:
1. Is evidence about the CLIENT (child/parent), not about the lesson?
2. Does evidence explicitly state or strongly imply the extracted value?
3. Is evidence specific, not just generic conversation?
4. Is the extracted value actually present (or clearly implied) in the evidence?

SPECIFIC FIELD CHECKS:

For NAME fields (child_name, parent_name):
✅ VALID: "Anaknya bernama Andi" → value: "Andi"
✅ VALID: "Saya Papa Budi" → value: "Budi"
❌ INVALID: "Oke, selamat datang, Seki" → value: "Seki" (greeting, not introduction)

For AGE/GRADE fields:
✅ VALID: "Andi kelas 5 SD" → value: "Grade 5"
✅ VALID: "Umurnya 10 tahun" → value: "10 years old"
❌ INVALID: "Kita akan belajar untuk kelas 5" → (about lesson, not child)

For INTERESTS/GOALS:
✅ VALID: "Andi suka main Roblox" → value: "Roblox"
✅ VALID: "Papa pengen anak bisa coding" → value: "Learn coding"
❌ INVALID: "Kita akan belajar coding hari ini" → (about lesson, not goal)

For SOURCE (how they found us):
✅ VALID: "Dari teman yang rekomendasikan" → value: "Friend referral"
✅ VALID: "Lihat di Instagram" → value: "Instagram"
❌ INVALID: "Papa awal tau" → (incomplete, not clear source)

BE EXTREMELY STRICT. Reject if there's ANY doubt.

Return ONLY valid JSON:
{{
  "is_valid": true/false,
  "explanation": "specific reason why evidence does/doesn't prove the information"
}}
"""
        
        try:
            response = self._call_llm(validation_prompt, temperature=0.05, max_tokens=150)
            result = json.loads(response)
            is_valid = result.get("is_valid", False)
            explanation = result.get("explanation", "")
            
            if not is_valid:
                print(f"      🔍 Client field REJECTED: {explanation}")
            else:
                print(f"      ✅ Client field PASSED: {explanation}")
            
            return is_valid
            
        except Exception as e:
            print(f"   ⚠️ Client field validation error: {e}")
            # On error, be conservative - reject to avoid false positives
            return False
    
    def batch_check_items(
        self,
        items: List[Dict],
        conversation_text: str
    ) -> Dict[str, Tuple[bool, float, str]]:
        """
        Batch check multiple items at once (more efficient)
        
        Args:
            items: List of {id, content, type} dicts
            conversation_text: Recent conversation
            
        Returns:
            Dict of item_id → (completed, confidence, evidence)
        """
        # For now, check items individually
        # TODO: Could optimize with a single LLM call for multiple items
        results = {}
        for item in items:
            completed, confidence, evidence, debug_info = self.check_checklist_item(
                item,
                conversation_text
            )
            results[item['id']] = (completed, confidence, evidence)
        
        return results
    
    def detect_current_stage(
        self,
        conversation_text: str,
        stages: List[Dict],
        call_elapsed_seconds: int
    ) -> Tuple[str, float]:
        """
        Detect which stage the conversation is currently in based on context
        
        Args:
            conversation_text: Recent conversation (last ~2000 chars)
            stages: List of stage definitions with names and items
            call_elapsed_seconds: Time elapsed (used as context, not decision)
            
        Returns:
            (stage_id: str, confidence: float)
        """
        # Guard: Skip if conversation too short
        if len(conversation_text.strip()) < 100:
            # At start, assume first stage
            return stages[0]['id'] if stages else '', 0.5
        
        # Build stage descriptions for LLM
        stage_descriptions = []
        for i, stage in enumerate(stages):
            items_summary = []
            for item in stage['items'][:3]:  # First 3 items as examples
                items_summary.append(f"- {item['content']}")
            items_text = "\n".join(items_summary)
            if len(stage['items']) > 3:
                items_text += f"\n- ...and {len(stage['items']) - 3} more"
            
            recommended_time = f"{stage['startOffsetSeconds']//60}-{(stage['startOffsetSeconds'] + stage['durationSeconds'])//60} min"
            
            stage_descriptions.append(
                f"{i+1}. **{stage['name']}** (recommended: {recommended_time})\n"
                f"   Focus: {items_text}"
            )
        
        stages_text = "\n\n".join(stage_descriptions)
        
        prompt = f"""You are analyzing a sales call in Bahasa Indonesia to determine the current stage.

Call elapsed time: {call_elapsed_seconds // 60} minutes {call_elapsed_seconds % 60} seconds (reference only)

Recent conversation:
{conversation_text}

Available stages:
{stages_text}

Based on the CONTENT and TOPICS being discussed (NOT just the time), which stage is the conversation currently in?

Rules:
- Focus on WHAT is being discussed, not how long has passed
- Look for keywords and topics matching the stage focus
- If transitioning between stages, pick the one that matches CURRENT topic
- Conversation is in Indonesian
- Be confident - avoid jumping between stages too quickly

Return ONLY valid JSON:
{{
  "stage_id": "stage_id_here",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of why this stage"
}}
"""
        
        try:
            response = self._call_llm(prompt, temperature=0.2, max_tokens=200)
            result = json.loads(response)
            
            stage_id = result.get("stage_id", "")
            confidence = result.get("confidence", 0.0)
            
            # Validate stage_id exists
            valid_ids = [s['id'] for s in stages]
            if stage_id not in valid_ids:
                print(f"   ⚠️ Invalid stage_id '{stage_id}', using first stage")
                return stages[0]['id'] if stages else '', 0.5
            
            return stage_id, confidence
            
        except Exception as e:
            print(f"   ⚠️ Stage detection failed: {e}")
            # Fallback to time-based detection
            for stage in stages:
                start = stage['startOffsetSeconds']
                end = start + stage['durationSeconds']
                if start <= call_elapsed_seconds < end:
                    return stage['id'], 0.3  # Low confidence = fallback
            return stages[0]['id'] if stages else '', 0.3
    
    def _call_llm(self, prompt: str, temperature: float = 0.5, max_tokens: int = 500) -> str:
        """
        Call OpenRouter API
        
        Args:
            prompt: The prompt
            temperature: Creativity level
            max_tokens: Max response length
            
        Returns:
            LLM response text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        # Try to extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        return content.strip()


# Global instance
_analyzer: Optional[TrialClassAnalyzer] = None


def get_trial_class_analyzer() -> TrialClassAnalyzer:
    """Get or create global analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = TrialClassAnalyzer()
    return _analyzer


def reset_analyzer():
    """Reset analyzer (for testing/new session)"""
    global _analyzer
    _analyzer = None

