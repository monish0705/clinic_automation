from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn

import config
import sheets_db
import whatsapp_sender as wa
import intent_engine
import booking_handler

app = FastAPI(title="Hospital WhatsApp Bot")

# ── Health check ─────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "running", "hospital": config.HOSPITAL_NAME}

# ── Main webhook — Twilio calls this for every inbound message ──
@app.post("/webhook")
async def webhook(
    request: Request,
    From: str = Form(...),          # e.g. whatsapp:+919876543210
    Body: str = Form(...),          # patient's message text
    ProfileName: str = Form(""),    # WhatsApp display name (optional)
):
    phone   = From.strip()
    message = Body.strip()
    today   = datetime.now().strftime("%Y-%m-%d")

    print(f"\n[IN] from={phone} | name={ProfileName} | msg={message!r}")

    # ── Session continuity: check if patient is mid-flow ──
    session = config.sessions.get(phone, {})
    state   = session.get("state", "")

    # ── If patient is in a multi-turn flow, append context ──
    if state == "awaiting_name":
        # Patient just sent their name as the next message
        session["patient_name"] = message
        config.sessions[phone]  = session
        reply = booking_handler.handle_intent(phone, {
            "intent": "BOOK_APPOINTMENT",
            "entities": {
                "doctor_name": session.get("doctor_name"),
                "date":        session.get("date"),
                "time":        session.get("time"),
                "patient_name": message,
                "appointment_id": None,
            }
        })
        wa.send_message(phone, reply)
        return PlainTextResponse("OK")

    if state == "awaiting_cancel_id":
        # Patient is replying with an appointment ID to cancel
        reply = booking_handler.handle_intent(phone, {
            "intent": "CANCEL_APPOINTMENT",
            "entities": {"appointment_id": message, "doctor_name": None,
                         "date": None, "time": None, "patient_name": None}
        })
        wa.send_message(phone, reply)
        return PlainTextResponse("OK")

    if state == "awaiting_reschedule_id":
        session["reschedule_appt_id"] = message
        config.sessions[phone] = session
        reply = booking_handler.handle_intent(phone, {
            "intent": "RESCHEDULE_APPOINTMENT",
            "entities": {"appointment_id": message, "doctor_name": None,
                         "date": None, "time": None, "patient_name": None}
        })
        wa.send_message(phone, reply)
        return PlainTextResponse("OK")

    # ── Standard flow: run intent extraction ─────────────
    intent_data = intent_engine.extract_intent(message, today)
    print(f"[INTENT] {intent_data}")

    # If mid-booking and patient sends partial info, merge with session
    if state in ("awaiting_date", "awaiting_time", "awaiting_doctor"):
        entities = intent_data.get("entities", {})
        intent_data["intent"] = "BOOK_APPOINTMENT"
        # Fill in session values for anything not in new message
        if not entities.get("doctor_name") and session.get("doctor_name"):
            entities["doctor_name"] = session["doctor_name"]
        if not entities.get("date") and session.get("date"):
            entities["date"] = session["date"]
        intent_data["entities"] = entities

    # ── Register/update patient record ────────────────────
    sheets_db.get_or_create_patient(phone, ProfileName or "")

    # ── Route to booking handler ──────────────────────────
    reply = booking_handler.handle_intent(phone, intent_data)

    print(f"[OUT] to={phone} | reply={reply[:80]}...")
    wa.send_message(phone, reply)

    return PlainTextResponse("OK")


# ── Reminder scheduler ────────────────────────────────────
def send_reminders():
    """Runs every hour. Checks for tomorrow's appointments and sends reminders."""
    print("[SCHEDULER] Checking for reminders...")
    appointments = sheets_db.get_appointments_for_reminder()
    for appt in appointments:
        msg = wa.msg_reminder(appt["doctor_name"], appt["date"], appt["time"])
        success = wa.send_message(f"whatsapp:{appt['patient_phone']}", msg)
        if success:
            sheets_db.mark_reminder_sent(appt["appointment_id"])
            print(f"[REMINDER] Sent for {appt['appointment_id']}")

scheduler = BackgroundScheduler()
scheduler.add_job(send_reminders, "interval", hours=1)
scheduler.start()


# ── Run server ────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting {config.HOSPITAL_NAME} WhatsApp Bot...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)