import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables with strong defaults."""

    # Project metadata
    APP_NAME: str = os.getenv("APP_NAME", "AI-Powered Clinic Automation Platform")
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Security & Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-clinic-key-for-jwt-signing-minimum-32-chars")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./clinic_platform.db")

    # Clinic Business Configuration
    CLINIC_NAME: str = os.getenv("CLINIC_NAME", os.getenv("HOSPITAL_NAME", "City Care Health Clinic"))
    CLINIC_ADDRESS: str = os.getenv("CLINIC_ADDRESS", "123 MG Road, Bangalore - 560001")
    CLINIC_PHONE: str = os.getenv("CLINIC_PHONE", "+91-98765-43210")
    CLINIC_TIMINGS: str = os.getenv("CLINIC_TIMINGS", "Mon–Sat: 9:00 AM – 8:00 PM | Sun: 10:00 AM – 2:00 PM")
    CLINIC_FEES_SUMMARY: str = os.getenv("CLINIC_FEES_SUMMARY", "₹500 (General) | ₹800 (Specialist)")

    # WhatsApp Provider Settings
    WHATSAPP_PROVIDER: str = os.getenv("WHATSAPP_PROVIDER", "meta").lower()

    # Meta WhatsApp Cloud API
    META_WA_PHONE_NUMBER_ID: str = os.getenv("META_WA_PHONE_NUMBER_ID", "")
    META_WA_ACCESS_TOKEN: str = os.getenv("META_WA_ACCESS_TOKEN", "")
    META_WA_VERIFY_TOKEN: str = os.getenv("META_WA_VERIFY_TOKEN", "clinic_webhook_verify_token")
    META_WA_APP_SECRET: str = os.getenv("META_WA_APP_SECRET", "")

    # Twilio WhatsApp API
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Background Reminders
    REMINDER_INTERVAL_MINUTES: int = int(os.getenv("REMINDER_INTERVAL_MINUTES", "15"))
    REMINDER_24H_HOURS_BEFORE: int = int(os.getenv("REMINDER_24H_HOURS_BEFORE", "24"))
    REMINDER_2H_HOURS_BEFORE: int = int(os.getenv("REMINDER_2H_HOURS_BEFORE", "2"))

    # Legacy Google Sheets
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
    GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")


settings = Settings()
