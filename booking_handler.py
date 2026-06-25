from datetime import datetime
import sheets_db
import whatsapp_sender as wa
import config

def handle_intent(phone: str, intent_data: dict) -> str:
    """
    Master router — takes extracted intent and decides what to do.
    Returns the reply string to send back to the patient.
    """
    intent   = intent_data.get("intent", "UNKNOWN")
    entities = intent_data.get("entities", {})
    session  = config.sessions.get(phone, {})

    # ── Greeting ─────────────────────────────────────────
    if intent == "GREET":
        patient = sheets_db.get_or_create_patient(phone)
        name = patient.get("name", "")
        return wa.msg_welcome(name)

    # ── FAQ handlers ─────────────────────────────────────
    if intent == "FAQ_FEES":
        return wa.msg_faq_fees()
    if intent == "FAQ_TIMINGS":
        return wa.msg_faq_timings()
    if intent == "FAQ_LOCATION":
        return wa.msg_faq_location()
    if intent == "FAQ_DOCTORS":
        return _handle_faq_doctors()

    # ── Check my appointments ─────────────────────────────
    if intent == "CHECK_MY_APPOINTMENTS":
        return _handle_check_appointments(phone)

    # ── Check availability ────────────────────────────────
    if intent == "CHECK_AVAILABILITY":
        return _handle_check_availability(entities)

    # ── Book appointment ──────────────────────────────────
    if intent == "BOOK_APPOINTMENT":
        return _handle_booking(phone, entities, session)

    # ── Cancel ───────────────────────────────────────────
    if intent == "CANCEL_APPOINTMENT":
        return _handle_cancel(phone, entities)

    # ── Reschedule ────────────────────────────────────────
    if intent == "RESCHEDULE_APPOINTMENT":
        return _handle_reschedule(phone, entities, session)

    # ── Unknown ───────────────────────────────────────────
    return (
        "I'm sorry, I didn't quite understand that. 😊\n\n"
        "You can ask me to:\n"
        "• *Book* an appointment\n"
        "• *Cancel* or *reschedule*\n"
        "• Check *fees*, *timings*, or *location*\n\n"
        "Or just say *Hi* to see all options!"
    )

# ─────────────────────────────────────────────────────────
# BOOKING FLOW
# ─────────────────────────────────────────────────────────
def _handle_booking(phone: str, entities: dict, session: dict) -> str:
    doctor_name = entities.get("doctor_name") or session.get("doctor_name")
    date        = entities.get("date")        or session.get("date")
    time        = entities.get("time")        or session.get("time")
    patient_name = entities.get("patient_name") or session.get("patient_name")

    # ── Step 1: Need doctor name ──────────────────────────
    if not doctor_name:
        config.sessions[phone] = {"state": "awaiting_doctor", **session}
        doctors = sheets_db.get_all_doctors()
        doc_list = "\n".join(
            [f"• *{d['name']}* ({d['speciality']}) — ₹{d['fee']}" for d in doctors]
        )
        return f"Which doctor would you like to book with?\n\n{doc_list}"

    # Validate doctor exists
    doctor = sheets_db.get_doctor_by_name(doctor_name)
    if not doctor:
        return (
            f"I couldn't find *{doctor_name}* in our system.\n"
            "Please check the name and try again, or say *doctors* to see the full list."
        )

    # Save doctor to session
    config.sessions[phone] = {**session, "doctor_name": doctor["name"], "state": "awaiting_date"}

    # ── Step 2: Need date ─────────────────────────────────
    if not date:
        days = doctor["available_days"]
        return (
            f"*{doctor['name']}* is available on: {days}\n\n"
            "Which date works for you? (e.g. *tomorrow*, *Monday*, *15 Jan*)"
        )

    # Validate date is not in the past
    try:
        appt_date = datetime.strptime(date, "%Y-%m-%d")
        if appt_date.date() < datetime.now().date():
            return f"*{date}* is in the past. Please choose a future date."
    except ValueError:
        return "I couldn't understand that date. Please try again (e.g. *15 Jan* or *tomorrow*)."

    config.sessions[phone] = {**session, "doctor_name": doctor["name"],
                               "date": date, "state": "awaiting_time"}

    # ── Step 3: Need time slot ────────────────────────────
    if not time:
        available_slots = sheets_db.get_available_slots(doctor["name"], date)
        if not available_slots:
            return wa.msg_no_slots(doctor["name"], date)
        slots_text = "  ".join([f"*{s}*" for s in available_slots])
        return (
            f"Available slots for *{doctor['name']}* on *{date}*:\n\n"
            f"{slots_text}\n\n"
            "Which time works for you?"
        )

    # Validate slot is available
    available = sheets_db.get_available_slots(doctor["name"], date)
    # Normalize time (patient might say 9:00 or 09:00)
    time_norm = time if ":" in time else time + ":00"
    if time_norm not in available and time not in available:
        slots_text = "  ".join([f"*{s}*" for s in available]) if available else "none"
        return (
            f"Sorry, *{time}* is not available.\n"
            f"Available slots: {slots_text}\n\n"
            "Please choose a different time."
        )

    # ── Step 4: Need patient name (first booking) ─────────
    if not patient_name:
        config.sessions[phone] = {
            **session,
            "doctor_name": doctor["name"],
            "date": date, "time": time_norm,
            "state": "awaiting_name"
        }
        patient = sheets_db.get_or_create_patient(phone)
        if patient.get("name"):
            # We already have their name — skip asking
            patient_name = patient["name"]
        else:
            return "What is the patient's full name for this appointment?"

    # ── Step 5: All info collected — CREATE BOOKING ───────
    booking_type = doctor.get("booking_type", "auto_confirm")

    appt = sheets_db.create_appointment(
        patient_phone=phone,
        patient_name=patient_name,
        doctor_name=doctor["name"],
        date=date,
        time=time_norm or time,
        booking_type=booking_type
    )

    # Save name for future bookings
    sheets_db.update_patient_name(phone, patient_name)

    # Clear session
    config.sessions.pop(phone, None)

    if booking_type == "auto_confirm":
        return wa.msg_appointment_confirmed(
            doctor["name"], date, appt["time"], appt["appointment_id"]
        )
    else:
        return wa.msg_appointment_pending(doctor["name"], date, appt["time"])


# ─────────────────────────────────────────────────────────
# CANCEL FLOW
# ─────────────────────────────────────────────────────────
def _handle_cancel(phone: str, entities: dict) -> str:
    appt_id = entities.get("appointment_id")

    if not appt_id:
        # Show their upcoming appointments so they can pick
        appointments = sheets_db.get_patient_appointments(phone)
        if not appointments:
            return "You have no upcoming appointments to cancel."

        appt_list = "\n".join([
            f"• *{a['appointment_id']}* — {a['doctor_name']} on {a['date']} at {a['time']}"
            for a in appointments
        ])
        config.sessions[phone] = {"state": "awaiting_cancel_id"}
        return (
            f"Your upcoming appointments:\n\n{appt_list}\n\n"
            "Reply with the *appointment ID* (e.g. *A00001*) to cancel."
        )

    success = sheets_db.cancel_appointment(appt_id.upper())
    config.sessions.pop(phone, None)

    if success:
        return (
            f"✅ Appointment *{appt_id.upper()}* has been cancelled.\n\n"
            "Need to rebook? Just say *Book appointment* anytime."
        )
    return (
        f"I couldn't find appointment *{appt_id}*.\n"
        "Please check the ID and try again."
    )


# ─────────────────────────────────────────────────────────
# RESCHEDULE FLOW
# ─────────────────────────────────────────────────────────
def _handle_reschedule(phone: str, entities: dict, session: dict) -> str:
    appointments = sheets_db.get_patient_appointments(phone)
    if not appointments:
        return "You have no upcoming appointments to reschedule."

    appt_id = entities.get("appointment_id") or session.get("reschedule_appt_id")

    if not appt_id:
        appt_list = "\n".join([
            f"• *{a['appointment_id']}* — {a['doctor_name']} on {a['date']} at {a['time']}"
            for a in appointments
        ])
        config.sessions[phone] = {"state": "awaiting_reschedule_id"}
        return (
            f"Which appointment would you like to reschedule?\n\n{appt_list}\n\n"
            "Reply with the *appointment ID*."
        )

    # Cancel old and book new
    sheets_db.cancel_appointment(appt_id.upper())
    config.sessions[phone] = {
        "state": "awaiting_date",
        "reschedule_from": appt_id,
        "doctor_name": next(
            (a["doctor_name"] for a in appointments
             if a["appointment_id"] == appt_id.upper()), None
        )
    }
    return (
        f"Appointment *{appt_id}* cancelled. Let's book a new slot.\n\n"
        "What date works for you?"
    )


# ─────────────────────────────────────────────────────────
# CHECK AVAILABILITY
# ─────────────────────────────────────────────────────────
def _handle_check_availability(entities: dict) -> str:
    doctor_name = entities.get("doctor_name")
    date        = entities.get("date")

    if not doctor_name or not date:
        return (
            "To check availability, please tell me:\n"
            "• Which *doctor*?\n"
            "• Which *date*?\n\n"
            "Example: *'Show slots for Dr. Sharma on Monday'*"
        )

    doctor = sheets_db.get_doctor_by_name(doctor_name)
    if not doctor:
        return f"Doctor *{doctor_name}* not found. Say *doctors* to see our full list."

    slots = sheets_db.get_available_slots(doctor["name"], date)
    if not slots:
        return wa.msg_no_slots(doctor["name"], date)

    slots_text = "  ".join([f"*{s}*" for s in slots])
    return (
        f"Available slots for *{doctor['name']}* on *{date}*:\n\n"
        f"{slots_text}\n\n"
        "To book, say: *'Book {doctor['name']} on {date} at 10:00'*"
    )


# ─────────────────────────────────────────────────────────
# MY APPOINTMENTS
# ─────────────────────────────────────────────────────────
def _handle_check_appointments(phone: str) -> str:
    appointments = sheets_db.get_patient_appointments(phone)
    if not appointments:
        return (
            "You have no upcoming appointments.\n\n"
            "Would you like to book one? Just say *Book appointment*!"
        )

    lines = [f"📋 *Your Upcoming Appointments*\n"]
    for a in appointments:
        status_icon = "✅" if a["status"] == "confirmed" else "⏳"
        lines.append(
            f"{status_icon} *{a['appointment_id']}*\n"
            f"   👨‍⚕️ {a['doctor_name']}\n"
            f"   📅 {a['date']} at {a['time']}\n"
        )
    lines.append("Reply with an ID to *cancel* or *reschedule*.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# DOCTORS LIST
# ─────────────────────────────────────────────────────────
def _handle_faq_doctors() -> str:
    doctors = sheets_db.get_all_doctors()
    lines = [f"👨‍⚕️ *Doctors at {config.HOSPITAL_NAME}*\n"]
    for d in doctors:
        lines.append(
            f"• *{d['name']}* — {d['speciality']}\n"
            f"   Days: {d['available_days']} | Fee: ₹{d['fee']}"
        )
    lines.append("\nSay *'Book with Dr. [name]'* to get started!")
    return "\n".join(lines)