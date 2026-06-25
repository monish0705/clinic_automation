from twilio.rest import Client
import config

_twilio_client = None

def get_twilio_client():
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    return _twilio_client

def send_message(to_number: str, message: str):
    """
    to_number: must be in format 'whatsapp:+919876543210'
    message: plain text (WhatsApp supports basic formatting with * for bold)
    """
    try:
        client = get_twilio_client()
        msg = client.messages.create(
            from_=config.TWILIO_WA_NUMBER,
            to=to_number,
            body=message
        )
        print(f"[SENT] to={to_number} | sid={msg.sid} | status={msg.status}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send to {to_number}: {e}")
        return False

# ── Pre-built message templates ──────────────────────────
def msg_welcome(name: str = "") -> str:
    greeting = f"Hello {name}! " if name else "Hello! "
    return (
        f"{greeting}Welcome to *{config.HOSPITAL_NAME}* 🏥\n\n"
        "I can help you with:\n"
        "1️⃣ Book an appointment\n"
        "2️⃣ Reschedule appointment\n"
        "3️⃣ Cancel appointment\n"
        "4️⃣ Check available slots\n"
        "5️⃣ My upcoming appointments\n"
        "6️⃣ Fees, timings & location\n\n"
        "Just type naturally — e.g. *'Book with Dr. Sharma tomorrow'*"
    )

def msg_appointment_confirmed(doctor: str, date: str, time: str, appt_id: str) -> str:
    return (
        f"✅ *Appointment Confirmed!*\n\n"
        f"🏥 {config.HOSPITAL_NAME}\n"
        f"👨‍⚕️ Doctor: {doctor}\n"
        f"📅 Date: {date}\n"
        f"⏰ Time: {time}\n"
        f"🔖 ID: {appt_id}\n\n"
        f"📍 {config.HOSPITAL_ADDRESS}\n\n"
        "Please arrive 10 minutes early. Reply *CANCEL* anytime to cancel."
    )

def msg_appointment_pending(doctor: str, date: str, time: str) -> str:
    return (
        f"⏳ *Appointment Request Received*\n\n"
        f"👨‍⚕️ Doctor: {doctor}\n"
        f"📅 Date: {date}\n"
        f"⏰ Time: {time}\n\n"
        "Your request has been sent for *manual approval*.\n"
        "You'll receive a confirmation within 2 hours.\n\n"
        "Need to change anything? Just reply here."
    )

def msg_reminder(doctor: str, date: str, time: str) -> str:
    return (
        f"⏰ *Appointment Reminder*\n\n"
        f"You have an appointment *tomorrow* at {config.HOSPITAL_NAME}!\n\n"
        f"👨‍⚕️ {doctor}\n"
        f"📅 {date} at {time}\n"
        f"📍 {config.HOSPITAL_ADDRESS}\n\n"
        "Reply *CANCEL* if you can't make it."
    )

def msg_no_slots(doctor: str, date: str) -> str:
    return (
        f"😔 No available slots for *{doctor}* on *{date}*.\n\n"
        "Would you like to:\n"
        "• Try a *different date*?\n"
        "• See *other available doctors*?\n\n"
        "Just let me know!"
    )

def msg_faq_fees() -> str:
    return (
        f"💰 *Consultation Fees at {config.HOSPITAL_NAME}*\n\n"
        f"{config.CONSULTATION_FEE}\n\n"
        "Payment accepted: Cash, UPI, Card\n"
        f"📞 Questions? Call us: {config.HOSPITAL_PHONE}"
    )

def msg_faq_timings() -> str:
    return (
        f"🕐 *Hospital Timings*\n\n"
        f"{config.HOSPITAL_TIMINGS}\n\n"
        f"📞 {config.HOSPITAL_PHONE}"
    )

def msg_faq_location() -> str:
    return (
        f"📍 *{config.HOSPITAL_NAME}*\n\n"
        f"{config.HOSPITAL_ADDRESS}\n\n"
        "🗺️ Google Maps: https://maps.google.com\n"
        f"📞 {config.HOSPITAL_PHONE}\n\n"
        "Nearest landmark: MG Road Metro Station (200m)"
    )