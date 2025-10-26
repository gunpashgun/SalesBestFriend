"""
LLM-based semantic analyzer for conversation understanding
Uses Claude via OpenRouter for deep semantic analysis
"""

import json
import os
from typing import Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()


class LLMAnalyzer:
    """Uses LLM to analyze conversation semantics"""
    
    def __init__(self, model: str = None):
        """
        Initialize LLM analyzer
        
        Args:
            model: OpenRouter model name. Recommended options:
                - anthropic/claude-3-haiku (fast, cheap, recommended for MVP)
                - anthropic/claude-3.5-sonnet (best quality, default)
                - openai/gpt-4o-mini (cheap alternative)
                - meta-llama/llama-3.3-70b-instruct:free (FREE!)
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # Use env var or provided model, default to Haiku for cost efficiency
        self.model = model or os.getenv("LLM_MODEL", "anthropic/claude-3-haiku")
        print(f"🤖 LLM Analyzer initialized with model: {self.model}")
    
    def identify_speakers(self, transcript: str) -> List[Dict]:
        """
        Identify who is speaking (client vs sales) using LLM
        
        Args:
            transcript: Raw transcript text
            
        Returns:
            List of segments with speaker labels
            Example: [
                {"speaker": "sales", "text": "Hello, my name is John"},
                {"speaker": "client", "text": "Hi, nice to meet you"}
            ]
        """
        prompt = f"""Analyze this sales call transcript and identify who is speaking for each sentence.
Label each sentence as either "sales" (sales manager) or "client" (customer).

Transcript:
{transcript}

Return ONLY valid JSON in this format:
{{
  "segments": [
    {{"speaker": "sales", "text": "Hello, my name is John"}},
    {{"speaker": "client", "text": "Hi, nice to meet you"}}
  ]
}}

Consider:
- Sales person introduces themselves, asks questions, explains products
- Client responds to questions, asks their own questions, expresses concerns
- If unclear, make best guess based on context
"""
        
        try:
            response = self._call_llm(prompt, temperature=0.3)
            result = json.loads(response)
            return result.get("segments", [])
        except Exception as e:
            print(f"⚠️ Speaker identification failed: {e}")
            # Fallback: treat all as client
            return [{"speaker": "client", "text": transcript}]
    
    def analyze_client_sentiment(self, client_text: str, full_transcript_context: str) -> Dict:
        """
        Analyze client sentiment, interests, objections, needs, and emotional state using LLM
        Returns comprehensive insights based on semantic understanding
        """
        # GUARD: Skip if text is too short (incomplete utterances like "Ternyata gini. Saiket")
        if len(client_text.strip()) < 20:
            print(f"   ⏭️ Text too short ({len(client_text)} chars), using minimal analysis")
            return {
                "emotion": "neutral",
                "objections": [],
                "interests": [],
                "needs": None,
                "engagement_level": 0.3,
                "stage_hint": "profiling",
                "buying_signals": [],
                "reasoning": "Text too short for analysis"
            }
        
        print(f"\n🔍 ANALYZING CLIENT TEXT:")
        print(f"   📝 Input ({len(client_text)} chars): {client_text[:100]}...")
        
        prompt = f"""You are analyzing a sales call to understand the client's interests, objections, needs, and emotional state.

Client speech segment:
{client_text}

Full conversation context (last messages):
{full_transcript_context}

Analyze and provide:
1. EMOTION: How is the client feeling? (engaged, curious, hesitant, defensive, negative, neutral)
2. INTERESTS: What topics interest them? (e.g., "game-based learning", "future skills", "logic", "creativity", "confidence")
3. OBJECTIONS: What are their concerns or obstacles? (e.g., "price", "time", "family", "value", "feasibility")
4. NEEDS: What is their core need or pain point?
5. ENGAGEMENT_LEVEL: 0.0-1.0 scale of how engaged they seem
6. STAGE_HINT: What stage of the call is this? (greeting, profiling, presentation, objection, closing)

CONFIDENCE: Only extract interests/objections if you are confident they were explicitly mentioned.
Avoid false positives from unclear or partial utterances.

Return ONLY valid JSON with no extra text:
{{
  "emotion": "engaged|curious|hesitant|defensive|negative|neutral",
  "interests": ["topic1", "topic2"],
  "objections": ["concern1", "concern2"],
  "needs": "core need or pain point",
  "engagement_level": 0.75,
  "stage_hint": "profiling|presentation|objection|closing",
  "buying_signals": ["signal1", "signal2"],
  "reasoning": "Brief explanation of the analysis"
}}

Focus on MEANING and CONTEXT, not just keywords. Understand what the client truly cares about."""
        
        try:
            response = self._call_llm(prompt, temperature=0.5)
            result = json.loads(response)
            
            # Log the detailed extraction
            print(f"   ✅ LLM Analysis:")
            print(f"      Emotion: {result.get('emotion')}")
            print(f"      Interests: {result.get('interests')}")
            print(f"      Objections: {result.get('objections')}")
            print(f"      Needs: {result.get('needs')}")
            print(f"      Engagement: {result.get('engagement_level')}")
            print(f"      Reasoning: {result.get('reasoning')}")
            
            # Ensure all required fields
            if "engagement_level" not in result:
                result["engagement_level"] = 0.5
            if "interests" not in result:
                result["interests"] = []
            if "objections" not in result:
                result["objections"] = []
            
            return result
        except Exception as e:
            print(f"⚠️ Sentiment analysis failed: {e}")
            return {
                "emotion": "neutral",
                "objections": [],
                "interests": [],
                "needs": None,
                "engagement_level": 0.5,
                "stage_hint": "profiling",
                "buying_signals": [],
                "reasoning": "Analysis failed, using defaults"
            }
    
    def check_checklist_item_semantic(
        self, 
        item_description: str, 
        conversation_text: str,
        language: str = "id"
    ) -> Tuple[bool, str]:
        """
        Check if a checklist item is completed using semantic understanding
        
        Args:
            item_description: What the sales person should do (e.g. "Introduce yourself")
            conversation_text: Recent conversation text
            language: Language of the conversation
            
        Returns:
            (completed: bool, reason: str)
        """
        # GUARD: Skip if conversation text is too short (incomplete/partial utterances)
        if len(conversation_text.strip()) < 30:
            print(f"   ⏭️ Skipping - conversation too short ({len(conversation_text)} chars)")
            return False, "Insufficient context"
        
        prompt = f"""You are analyzing a sales call to check if the sales manager completed a specific action.

Required action: {item_description}

Recent conversation (language: {language}):
{conversation_text}

Did the sales manager complete this action? Consider:
- The MEANING and INTENT, not just specific words
- Actions can be completed in different ways
- Be STRICT: require clear and explicit evidence
- Avoid false positives from partial/incomplete utterances

CONFIDENCE THRESHOLD: Only return true if you are 80%+ confident.

Return ONLY valid JSON:
{{
  "completed": true/false,
  "reason": "Brief explanation of why completed or not",
  "confidence": 0.0-1.0,
  "evidence": "Quote from conversation that shows completion"
}}
"""
        
        try:
            response = self._call_llm(prompt, temperature=0.3)
            result = json.loads(response)
            completed = result.get("completed", False)
            confidence = result.get("confidence", 0.0)
            reason = result.get("reason", "No clear evidence")
            
            # GUARD: Only accept if confidence >= 0.8
            if completed and confidence < 0.8:
                print(f"   ⏭️ Low confidence ({confidence:.0%}), marking as incomplete")
                return False, f"Low confidence: {reason}"
            
            if completed:
                print(f"   ✅ Completed: {item_description}")
                print(f"      Reason: {reason} (confidence: {confidence:.0%})")
            
            return completed, reason
        except Exception as e:
            print(f"   ⚠️ LLM check failed: {e}")
            return False, str(e)
    
    def generate_next_step(
        self,
        current_stage: str,
        client_insights: Dict,
        checklist_progress: Dict,
        recent_conversation: str
    ) -> str:
        """
        Generate contextual next step recommendation
        
        Args:
            current_stage: Current call stage
            client_insights: Client sentiment and interests
            checklist_progress: What's been completed
            recent_conversation: Last few exchanges
            
        Returns:
            Next step recommendation string
        """
        completed_items = [k for k, v in checklist_progress.items() if v]
        
        prompt = f"""You are coaching a sales manager during a live call. Give them ONE actionable next step.

Current situation:
- Stage: {current_stage}
- Client emotion: {client_insights.get('emotion', 'unknown')}
- Client objections: {client_insights.get('objections', [])}
- Client interests: {client_insights.get('interests', [])}
- Completed checklist items: {len(completed_items)} items
- Recent conversation: {recent_conversation[-200:]}

Give ONE specific, actionable recommendation (max 15 words) for what to say/do next.
Focus on:
- Moving the conversation forward
- Addressing client concerns
- Following sales best practices
- Being natural and conversational

Return ONLY the recommendation text, no JSON.
"""
        
        try:
            return self._call_llm(prompt, temperature=0.7)
        except Exception as e:
            print(f"⚠️ Next step generation failed: {e}")
            return "Listen actively and ask open-ended questions."
    
    def _call_llm(self, prompt: str, temperature: float = 0.5) -> str:
        """
        Call OpenRouter API with Claude
        
        Args:
            prompt: System + user prompt
            temperature: Creativity level
            
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
            "max_tokens": 2000
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
_analyzer: Optional[LLMAnalyzer] = None


def get_llm_analyzer() -> LLMAnalyzer:
    """Get or create global LLM analyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = LLMAnalyzer()
    return _analyzer

