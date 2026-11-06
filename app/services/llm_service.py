import json
import time
import re
from typing import Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
from app.core.logging import logger

_openai_client = None


def get_openai_client() -> Optional[OpenAI]:
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=10.0)
    return _openai_client


class LLMService:
    """Service wrapping LLM calls with timeouts, exponential backoff retries, and schema parsing."""

    @classmethod
    def call_structured(
        cls,
        system_prompt: str,
        user_message: str,
        response_schema: Optional[type] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Calls LLM to generate structured JSON.
        Implements retries and falls back to a safe fallback payload if API fails or keys are missing.
        """
        client = get_openai_client()
        if not client:
            logger.warning("[LLM] No OpenAI API key configured. Executing fallback.")
            return cls._fallback_response(user_message)

        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.0,
                    max_tokens=400,
                    response_format={"type": "json_object"}
                )
                raw_content = response.choices[0].message.content or "{}"
                parsed = json.loads(raw_content)

                if response_schema:
                    # Validate against Pydantic schema
                    validated = response_schema.model_validate(parsed)
                    return validated.model_dump()
                return parsed

            except json.JSONDecodeError as exc:
                logger.error(f"[LLM] Failed to parse JSON response: {exc}")
                return cls._fallback_response(user_message)
            except Exception as exc:
                logger.warning(f"[LLM] API call attempt {attempt + 1} failed: {exc}")
                if attempt < max_retries:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    return cls._fallback_response(user_message)

        return cls._fallback_response(user_message)

    @classmethod
    def generate_conversational_reply(
        cls,
        system_prompt: str,
        context: str,
        user_message: str
    ) -> str:
        """Generates natural conversational follow-ups within clinical guardrails."""
        client = get_openai_client()
        if not client:
            return context

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context: {context}\nPatient message: {user_message}"}
                ],
                temperature=0.3,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error(f"[LLM] Conversational completion error: {exc}")
            return context

    @staticmethod
    def _fallback_response(user_message: str) -> Dict[str, Any]:
        """Deterministic heuristic fallback when LLM API is unavailable or unconfigured."""
        msg_lower = user_message.lower()

        # Rule-based fallback matching
        if any(w in msg_lower for w in ["fee", "cost", "charge", "price", "timing", "hours", "open", "address", "location", "where"]):
            intent = "CLINIC_FAQ"
        elif any(w in msg_lower for w in ["cancel", "drop appointment"]):
            intent = "CANCEL_APPOINTMENT"
        elif any(w in msg_lower for w in ["reschedule", "change time", "change date", "postpone"]):
            intent = "RESCHEDULE_APPOINTMENT"
        elif any(w in msg_lower for w in ["my appointment", "my bookings", "status"]):
            intent = "GET_APPOINTMENT_DETAILS"
        elif any(w in msg_lower for w in ["slot", "available", "availability", "free"]):
            intent = "CHECK_AVAILABILITY"
        elif any(w in msg_lower for w in ["book", "appointment", "schedule", "consult"]):
            intent = "BOOK_APPOINTMENT"
        else:
            intent = "UNKNOWN"

        # Regex heuristic entity extraction
        doc_match = re.search(r"\b(dr\.?\s+[a-z]+)\b", msg_lower)
        doctor_name = doc_match.group(1).title() if doc_match else None

        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", msg_lower)
        date_val = date_match.group(1) if date_match else None
        if not date_val:
            for day_word in ["tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
                if day_word in msg_lower:
                    date_val = day_word
                    break

        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", msg_lower)
        time_val = time_match.group(1) if time_match else None

        code_match = re.search(r"\b(apt-[a-z0-9]+)\b", msg_lower)
        code_val = code_match.group(1).upper() if code_match else None

        return {
            "intent": intent,
            "entities": {
                "doctor_name": doctor_name,
                "date": date_val,
                "time": time_val,
                "appointment_code": code_val,
                "patient_name": None
            },
            "confidence": 0.5 if intent != "UNKNOWN" else 0.0,
            "missing_info": [],
            "reply_hint": "Heuristic fallback applied"
        }
