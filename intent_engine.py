from openai import OpenAI
import json
import config

_llm_client = None

def get_llm_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _llm_client

SYSTEM_PROMPT = """You are an intent and entity extractor for a hospital WhatsApp chatbot.

Your ONLY job is to analyse a patient's message and return a JSON object.
Never reply conversationally. Always return valid JSON and nothing else.

Return this exact structure:
{
  "intent": "<one of the intents below>",
  "entities": {
    "doctor_name": "<extracted or null>",
    "date": "<YYYY-MM-DD or null>",
    "time": "<HH:MM 24hr format or null>",
    "appointment_id": "<extracted or null>",
    "patient_name": "<extracted or null>"
  },
  "confidence": <0.0 to 1.0>,
  "missing_info": ["list", "of", "missing", "required", "fields"],
  "reply_hint": "<short note on what to ask next if info is missing>"
}

Valid intents:
- BOOK_APPOINTMENT       → patient wants to book
- RESCHEDULE_APPOINTMENT → patient wants to change date/time
- CANCEL_APPOINTMENT     → patient wants to cancel
- CHECK_AVAILABILITY     → wants to know free slots
- CHECK_MY_APPOINTMENTS  → wants to see their bookings
- FAQ_FEES               → asking about fees/charges
- FAQ_TIMINGS            → asking about open hours
- FAQ_LOCATION           → asking about address/directions
- FAQ_DOCTORS            → asking which doctors are available
- GREET                  → hi/hello/hey type message
- UNKNOWN                → cannot determine intent

Date parsing rules:
- "tomorrow" → calculate actual date (today is {today})
- "Monday", "next Friday" → calculate actual date
- "15th", "15 Jan" → parse to YYYY-MM-DD
- Always output dates as YYYY-MM-DD

Time parsing rules:
- "11am" → "11:00"
- "3:30 pm" → "15:30"
- "morning" → null (too vague, add to missing_info)
- "afternoon" → null (too vague, add to missing_info)
"""

def extract_intent(user_message: str, today_date: str) -> dict:
    """
    Sends user message to LLM and returns structured intent dict.
    Falls back gracefully if LLM fails.
    """
    prompt = SYSTEM_PROMPT.replace("{today}", today_date)

    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": user_message}
            ],
            temperature=0.1,       # low temp = more deterministic extraction
            max_tokens=300,
            response_format={"type": "json_object"}   # force JSON output
        )
        raw = response.choices[0].message.content
        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"[INTENT] JSON parse error: {e} | raw={raw}")
        return _fallback_intent()
    except Exception as e:
        print(f"[INTENT] LLM call failed: {e}")
        return _fallback_intent()

def _fallback_intent() -> dict:
    return {
        "intent": "UNKNOWN",
        "entities": {
            "doctor_name": None, "date": None, "time": None,
            "appointment_id": None, "patient_name": None
        },
        "confidence": 0.0,
        "missing_info": [],
        "reply_hint": "I didn't understand that."
    }

def generate_conversational_reply(
    user_message: str,
    context: str,
    session: dict
) -> str:
    """
    Used for follow-up questions within a booking flow —
    e.g. asking which doctor, which date, confirming slot.
    More natural than rigid menus.
    """
    system = f"""You are a friendly, professional hospital receptionist for {config.HOSPITAL_NAME}.
You are helping a patient over WhatsApp complete a task.

Current context: {context}
Patient session data: {json.dumps(session)}

Rules:
- Be warm but concise (max 3 sentences)
- Use simple language (patient may not be tech-savvy)
- Always in English unless patient writes in another language
- Never mention you are an AI
- End with a clear question or action
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_message}
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[CONV] LLM reply failed: {e}")
        return "I'm having trouble right now. Please try again in a moment."