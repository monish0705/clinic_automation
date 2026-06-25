import os
from dotenv import load_dotenv

load_dotenv()

# ── Twilio ──────────────────────────────────────────────
TWILIO_ACCOUNT_SID    = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN     = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_NUMBER      = os.getenv("TWILIO_WHATSAPP_NUMBER")  # whatsapp:+14155238886

# ── OpenAI / LLM ────────────────────────────────────────
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")
LLM_MODEL             = "gpt-4o-mini"   # cheap + fast; swap for gpt-4o or gemini later

# ── Google Sheets ────────────────────────────────────────
GOOGLE_SHEET_ID       = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_PATH     = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# ── Hospital config ──────────────────────────────────────
HOSPITAL_NAME         = os.getenv("HOSPITAL_NAME", "City Care Clinic")
HOSPITAL_ADDRESS      = "123 MG Road, Bangalore - 560001"
HOSPITAL_TIMINGS      = "Mon–Sat: 9:00 AM – 8:00 PM | Sun: 10:00 AM – 2:00 PM"
CONSULTATION_FEE      = "₹500 (General) | ₹800 (Specialist)"
HOSPITAL_PHONE        = "+91-98765-43210"

# ── In-memory session store ──────────────────────────────
# Stores ongoing conversation state per patient phone number.
# Format: { "whatsapp:+919876543210": { "state": "awaiting_date", "doctor": "Dr. Sharma", ... } }
# This resets when the server restarts. Step 6 will persist this in Sheets.
sessions = {}

# ── Intent definitions (used by LLM prompt) ──────────────
INTENTS = [
    "BOOK_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "CANCEL_APPOINTMENT",
    "CHECK_AVAILABILITY",
    "CHECK_MY_APPOINTMENTS",
    "FAQ_FEES",
    "FAQ_TIMINGS",
    "FAQ_LOCATION",
    "FAQ_DOCTORS",
    "GREET",
    "UNKNOWN",
]