from datetime import datetime, date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.agents.prompts import (
    INTENT_PROMPT_TEMPLATE,
    CONVERSATIONAL_RECEPTIONIST_PROMPT,
    IntentExtractionResult
)
from app.agents.tools import (
    ClinicTools,
    CheckAvailabilityInput,
    GetDoctorDetailsInput,
    GetClinicInformationInput,
    BookAppointmentInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput,
    GetPatientAppointmentsInput,
)
from app.services.llm_service import LLMService
from app.services.conversation_service import ConversationService
from app.services.appointment_service import AppointmentService
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.models.conversation import Conversation
from app.models.patient import Patient
from app.utils.validators import parse_target_date, normalize_time_slot
from app.core.config import settings
from app.core.logging import logger


class ClinicAgent:
    """
    Deterministic conversational agent orchestrator with typed tool execution.
    Adheres strictly to the 10 safety and reliability mandates.
    """

    @classmethod
    def process_incoming_message(
        cls,
        db: Session,
        phone: str,
        message_text: str,
        profile_name: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """
        Main entry point for incoming WhatsApp text messages.
        Returns the formatted response string to send to the patient.
        """
        logger.info(f"[AGENT] Incoming from {phone}: {message_text!r}")

        # 1. Fetch or create conversational session
        conv, patient = ConversationService.get_or_create_session(db, phone, profile_name)

        # 2. Record incoming message for audit trail
        ConversationService.record_inbound(db, conv, patient, message_text, message_id=message_id)

        clean_text = message_text.strip()
        state = conv.current_state or "IDLE"
        metadata = dict(conv.state_metadata or {})

        # 3. Check for cancellation / reset keywords
        if clean_text.lower() in ("reset", "restart", "start over", "abort"):
            ConversationService.reset_state(db, conv.id)
            return (
                f"🔄 Conversation reset.\n\n"
                f"Hello! Welcome to *{settings.CLINIC_NAME}*. How can I help you today?\n"
                f"• Book an appointment\n"
                f"• Check doctor availability\n"
                f"• Reschedule or cancel\n"
                f"• Clinic fees and timings"
            )

        # 4. Handle Active Multi-Turn States
        if state == "AWAITING_CONFIRMATION":
            return cls._handle_awaiting_confirmation(db, conv, patient, clean_text, metadata)

        if state == "AWAITING_NAME":
            metadata["patient_name"] = clean_text
            PatientRepository.update_name(db, phone, clean_text)
            return cls._continue_booking_flow(db, conv, patient, metadata)

        if state == "AWAITING_CANCEL_CODE":
            return cls._execute_cancellation(db, conv, patient, clean_text)

        if state == "AWAITING_RESCHEDULE_CODE":
            metadata["appointment_code"] = clean_text.upper()
            ConversationService.update_state(db, conv.id, "AWAITING_RESCHEDULE_DATE", metadata)
            return "Got it. Which *new date* would you like to reschedule to? (e.g. *tomorrow*, *Monday*)"

        if state == "AWAITING_RESCHEDULE_DATE":
            parsed_date = parse_target_date(clean_text)
            if not parsed_date:
                return "I couldn't understand that date. Please try again (e.g. *tomorrow*, *2026-11-10*)."
            metadata["new_date"] = parsed_date.strftime("%Y-%m-%d")
            ConversationService.update_state(db, conv.id, "AWAITING_RESCHEDULE_TIME", metadata)
            return "What *time* works best for you? (e.g. *11:00*, *3:30 pm*)"

        if state == "AWAITING_RESCHEDULE_TIME":
            norm_time = normalize_time_slot(clean_text)
            if not norm_time:
                return "Please provide a valid time like *10:00* or *3:30 pm*."
            metadata["new_time"] = norm_time
            return cls._execute_reschedule(db, conv, patient, metadata)

        # 5. Intent Classification & Entity Extraction via Structured LLM
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        today_day = datetime.utcnow().strftime("%A")
        system_prompt = INTENT_PROMPT_TEMPLATE.format(
            clinic_name=settings.CLINIC_NAME,
            today_date=today_str,
            today_day=today_day
        )

        extraction = LLMService.call_structured(
            system_prompt=system_prompt,
            user_message=clean_text,
            response_schema=IntentExtractionResult
        )

        intent = extraction.get("intent", "UNKNOWN")
        entities = extraction.get("entities", {})
        logger.info(f"[AGENT] Extracted intent: {intent} | Entities: {entities}")

        # If in a slot collection flow and patient gave date/time
        if state in ("AWAITING_DOCTOR", "AWAITING_DATE", "AWAITING_TIME"):
            if entities.get("doctor_name"):
                metadata["doctor_name"] = entities["doctor_name"]
            if entities.get("date"):
                metadata["date"] = entities["date"]
            if entities.get("time"):
                metadata["time"] = entities["time"]
            return cls._continue_booking_flow(db, conv, patient, metadata)

        # 6. Route Intents
        if intent == "BOOK_APPOINTMENT":
            metadata.update({
                "doctor_name": entities.get("doctor_name") or metadata.get("doctor_name"),
                "date": entities.get("date") or metadata.get("date"),
                "time": entities.get("time") or metadata.get("time"),
                "patient_name": entities.get("patient_name") or patient.name or metadata.get("patient_name"),
            })
            return cls._continue_booking_flow(db, conv, patient, metadata)

        elif intent == "CHECK_AVAILABILITY":
            return cls._handle_check_availability(db, entities)

        elif intent == "GET_APPOINTMENT_DETAILS":
            return cls._handle_get_appointments(db, patient.phone)

        elif intent == "CANCEL_APPOINTMENT":
            code = entities.get("appointment_code")
            if code:
                return cls._execute_cancellation(db, conv, patient, code)
            # Show active bookings to choose from
            tool_res = ClinicTools.get_patient_appointments(
                db, GetPatientAppointmentsInput(patient_phone=patient.phone)
            )
            appts = tool_res.get("appointments", [])
            if not appts:
                return "You have no upcoming appointments to cancel."

            lines = ["📋 *Your Upcoming Appointments:*\n"]
            for a in appts:
                lines.append(f"• *{a['appointment_code']}* — {a['doctor_name']} on {a['date']} at {a['time']}")
            lines.append("\nPlease reply with the *Appointment ID* (e.g. *APT-XXXXX*) to cancel.")

            ConversationService.update_state(db, conv.id, "AWAITING_CANCEL_CODE", metadata)
            return "\n".join(lines)

        elif intent == "RESCHEDULE_APPOINTMENT":
            code = entities.get("appointment_code")
            if code:
                metadata["appointment_code"] = code.upper()
                ConversationService.update_state(db, conv.id, "AWAITING_RESCHEDULE_DATE", metadata)
                return f"Rescheduling *{code.upper()}*. What *new date* would you prefer? (e.g. *tomorrow*, *Monday*)"

            tool_res = ClinicTools.get_patient_appointments(
                db, GetPatientAppointmentsInput(patient_phone=patient.phone)
            )
            appts = tool_res.get("appointments", [])
            if not appts:
                return "You have no upcoming appointments to reschedule."

            lines = ["📋 *Which appointment would you like to reschedule?*\n"]
            for a in appts:
                lines.append(f"• *{a['appointment_code']}* — {a['doctor_name']} on {a['date']} at {a['time']}")
            lines.append("\nPlease reply with the *Appointment ID* to reschedule.")

            ConversationService.update_state(db, conv.id, "AWAITING_RESCHEDULE_CODE", metadata)
            return "\n".join(lines)

        elif intent == "CLINIC_FAQ":
            return cls._handle_faq(db, clean_text)

        else:
            return (
                f"Hello! I am the automated assistant for *{settings.CLINIC_NAME}*.\n\n"
                f"I can assist you with:\n"
                f"1️⃣ *Book an appointment* (e.g. *'Book Dr. Sharma tomorrow'*)\n"
                f"2️⃣ *Check doctor availability* (e.g. *'Slots for Dr. Patel on Friday'*)\n"
                f"3️⃣ *View your upcoming bookings*\n"
                f"4️⃣ *Reschedule or cancel an appointment*\n"
                f"5️⃣ *Consultation fees, timings, and location*\n\n"
                f"How may I help you today?"
            )

    # ── Flow Helpers ────────────────────────────────────────────────

    @classmethod
    def _continue_booking_flow(
        cls,
        db: Session,
        conv: Conversation,
        patient: Patient,
        metadata: Dict[str, Any]
    ) -> str:
        doctor_name = metadata.get("doctor_name")
        date_str = metadata.get("date")
        time_str = metadata.get("time")
        patient_name = metadata.get("patient_name") or patient.name

        # Step 1: Doctor Check
        if not doctor_name:
            ConversationService.update_state(db, conv.id, "AWAITING_DOCTOR", metadata)
            docs_res = ClinicTools.get_doctor_details(db, GetDoctorDetailsInput())
            doc_lines = [f"• *{d['name']}* ({d['speciality']}) — ₹{int(d['fee'])}" for d in docs_res.get("doctors", [])]
            return f"Which doctor would you like to consult with?\n\n" + "\n".join(doc_lines)

        doctor = DoctorRepository.get_by_name(db, doctor_name)
        if not doctor:
            ConversationService.update_state(db, conv.id, "AWAITING_DOCTOR", metadata)
            docs_res = ClinicTools.get_doctor_details(db, GetDoctorDetailsInput())
            doc_lines = [f"• *{d['name']}* ({d['speciality']})" for d in docs_res.get("doctors", [])]
            return f"I couldn't find *{doctor_name}*. Please choose from our active doctors:\n\n" + "\n".join(doc_lines)

        metadata["doctor_name"] = doctor.name

        # Step 2: Date Check
        if not date_str:
            ConversationService.update_state(db, conv.id, "AWAITING_DATE", metadata)
            days = doctor.availabilities[0].day_of_week if doctor.availabilities else "Mon-Sat"
            return (
                f"*{doctor.name}* is available on: *{days}*.\n\n"
                f"What date works for you? (e.g. *tomorrow*, *Monday*, *2026-11-10*)"
            )

        parsed_date = parse_target_date(date_str)
        if not parsed_date:
            ConversationService.update_state(db, conv.id, "AWAITING_DATE", metadata)
            return f"I couldn't understand '{date_str}'. Please give a date like *tomorrow* or *2026-11-10*."

        today = datetime.utcnow().date()
        if parsed_date < today:
            ConversationService.update_state(db, conv.id, "AWAITING_DATE", metadata)
            return f"*{date_str}* is in the past. Please choose a future date."

        metadata["date"] = parsed_date.strftime("%Y-%m-%d")

        # Step 3: Time Slot Check
        if not time_str:
            avail_res = ClinicTools.check_doctor_availability(
                db, CheckAvailabilityInput(doctor_name=doctor.name, date=metadata["date"])
            )
            slots = avail_res.get("available_slots", [])
            if not slots:
                ConversationService.update_state(db, conv.id, "AWAITING_DATE", metadata)
                return f"😔 No slots available for *{doctor.name}* on *{metadata['date']}*.\nWould you like to try another date?"

            slots_preview = "  ".join([f"*{s}*" for s in slots[:8]])
            ConversationService.update_state(db, conv.id, "AWAITING_TIME", metadata)
            return f"Available slots for *{doctor.name}* on *{metadata['date']}*:\n\n{slots_preview}\n\nWhich time slot suits you?"

        norm_time = normalize_time_slot(time_str)
        if not norm_time:
            ConversationService.update_state(db, conv.id, "AWAITING_TIME", metadata)
            return f"Could not understand the time '{time_str}'. Please specify like *10:00* or *3:30 pm*."

        # Verify slot availability
        avail_res = ClinicTools.check_doctor_availability(
            db, CheckAvailabilityInput(doctor_name=doctor.name, date=metadata["date"])
        )
        slots = avail_res.get("available_slots", [])
        if norm_time not in slots:
            slots_preview = "  ".join([f"*{s}*" for s in slots[:8]])
            ConversationService.update_state(db, conv.id, "AWAITING_TIME", metadata)
            return f"Sorry, *{norm_time}* is already booked or unavailable.\nAvailable slots: {slots_preview}\nPlease choose a different time."

        metadata["time"] = norm_time

        # Step 4: Patient Name
        if not patient_name:
            ConversationService.update_state(db, conv.id, "AWAITING_NAME", metadata)
            return "May I have the patient's full name for this appointment?"

        metadata["patient_name"] = patient_name

        # Step 5: Explicit Patient Confirmation (SAFETY RULE 4)
        ConversationService.update_state(db, conv.id, "AWAITING_CONFIRMATION", metadata)
        return (
            f"📋 *Please Confirm Your Appointment:*\n\n"
            f"🏥 *Clinic:* {settings.CLINIC_NAME}\n"
            f"👨‍⚕️ *Doctor:* {doctor.name} ({doctor.speciality})\n"
            f"📅 *Date:* {metadata['date']}\n"
            f"⏰ *Time:* {metadata['time']}\n"
            f"👤 *Patient:* {patient_name}\n"
            f"💰 *Fee:* ₹{int(doctor.fee)}\n\n"
            f"Reply *YES* to confirm your booking, or *NO* to cancel."
        )

    @classmethod
    def _handle_awaiting_confirmation(
        cls,
        db: Session,
        conv: Conversation,
        patient: Patient,
        reply: str,
        metadata: Dict[str, Any]
    ) -> str:
        clean = reply.strip().lower()
        if clean in ("yes", "y", "confirm", "ok", "sure", "proceed"):
            # Execute booking tool
            book_input = BookAppointmentInput(
                patient_phone=patient.phone,
                doctor_name=metadata["doctor_name"],
                date=metadata["date"],
                time=metadata["time"],
                patient_name=metadata.get("patient_name"),
                confirmed_by_patient=True
            )
            result = ClinicTools.book_appointment(db, book_input)
            ConversationService.reset_state(db, conv.id)

            if result.get("success"):
                return (
                    f"✅ *Appointment Confirmed!*\n\n"
                    f"🔖 *ID:* {result['appointment_code']}\n"
                    f"👨‍⚕️ *Doctor:* {result['doctor_name']}\n"
                    f"📅 *Date:* {result['date']}\n"
                    f"⏰ *Time:* {result['time']}\n"
                    f"📍 *Location:* {settings.CLINIC_ADDRESS}\n\n"
                    f"Please arrive 10 minutes prior. You can reply *CANCEL* or *RESCHEDULE* anytime."
                )
            else:
                return f"❌ {result.get('error', 'Booking failed. Please try again.')}"

        elif clean in ("no", "cancel", "stop", "abort"):
            ConversationService.reset_state(db, conv.id)
            return "Booking cancelled. Let me know whenever you would like to book again!"
        else:
            return "Please reply with *YES* to confirm this booking or *NO* to cancel."

    @classmethod
    def _handle_check_availability(cls, db: Session, entities: Dict[str, Any]) -> str:
        doc_name = entities.get("doctor_name")
        target_date = entities.get("date")

        if not doc_name or not target_date:
            return (
                "To check slot availability, please let me know:\n"
                "• Which *doctor*?\n"
                "• Which *date*?\n\n"
                "Example: *'Check slots for Dr. Sharma tomorrow'*"
            )

        res = ClinicTools.check_doctor_availability(
            db, CheckAvailabilityInput(doctor_name=doc_name, date=target_date)
        )
        if not res.get("success"):
            return f"❌ {res.get('error')}"

        slots = res.get("available_slots", [])
        if not slots:
            return f"😔 No slots available for *{res['doctor_name']}* on *{res['date']}*."

        slots_text = "  ".join([f"*{s}*" for s in slots])
        return (
            f"Available slots for *{res['doctor_name']}* on *{res['date']}*:\n\n"
            f"{slots_text}\n\n"
            f"To book, reply: *'Book {res['doctor_name']} on {res['date']} at {slots[0]}'*."
        )

    @classmethod
    def _handle_get_appointments(cls, db: Session, phone: str) -> str:
        tool_res = ClinicTools.get_patient_appointments(
            db, GetPatientAppointmentsInput(patient_phone=phone)
        )
        appts = tool_res.get("appointments", [])
        if not appts:
            return (
                "You have no upcoming appointments scheduled.\n\n"
                "Would you like to book one? Just say *'Book an appointment'*!"
            )

        lines = ["📋 *Your Upcoming Appointments:*\n"]
        for a in appts:
            lines.append(
                f"🔖 *{a['appointment_code']}*\n"
                f"   👨‍⚕️ {a['doctor_name']} ({a['speciality']})\n"
                f"   📅 {a['date']} at {a['time']}\n"
                f"   Status: *{a['status']}*\n"
            )
        lines.append("To cancel or reschedule, reply with the *Appointment ID*.")
        return "\n".join(lines)

    @classmethod
    def _execute_cancellation(cls, db: Session, conv: Conversation, patient: Patient, code: str) -> str:
        res = ClinicTools.cancel_appointment(
            db, CancelAppointmentInput(appointment_code=code, patient_phone=patient.phone)
        )
        ConversationService.reset_state(db, conv.id)
        if res.get("success"):
            return f"✅ {res['message']}\nNeed to book another time? Just let me know!"
        return f"❌ {res.get('error')}"

    @classmethod
    def _execute_reschedule(cls, db: Session, conv: Conversation, patient: Patient, metadata: Dict[str, Any]) -> str:
        code = metadata.get("appointment_code", "")
        new_date = metadata.get("new_date", "")
        new_time = metadata.get("new_time", "")

        res = ClinicTools.reschedule_appointment(
            db, RescheduleAppointmentInput(
                appointment_code=code,
                new_date=new_date,
                new_time=new_time,
                patient_phone=patient.phone
            )
        )
        ConversationService.reset_state(db, conv.id)
        if res.get("success"):
            return (
                f"✅ *Appointment Rescheduled!*\n\n"
                f"🔖 *ID:* {res['appointment_code']}\n"
                f"👨‍⚕️ *Doctor:* {res['doctor_name']}\n"
                f"📅 *New Date:* {res['new_date']}\n"
                f"⏰ *New Time:* {res['new_time']}\n\n"
                f"Your appointment is updated. See you then!"
            )
        return f"❌ {res.get('error')}"

    @classmethod
    def _handle_faq(cls, db: Session, text: str) -> str:
        info = AppointmentService.get_clinic_info(db)
        t = text.lower()
        if any(w in t for w in ["fee", "cost", "charge", "price"]):
            return (
                f"💰 *Consultation Fees at {info['name']}:*\n\n"
                f"{info['fees_summary']}\n\n"
                f"Payment options: Cash, UPI, Debit/Credit Card\n"
                f"📞 Phone: {info['phone']}"
            )
        if any(w in t for w in ["timing", "hour", "open", "close"]):
            return (
                f"🕐 *Clinic Timings:*\n\n"
                f"{info['timings']}\n\n"
                f"📞 Questions? Call {info['phone']}"
            )
        if any(w in t for w in ["address", "location", "direction", "where", "map"]):
            return (
                f"📍 *Clinic Location:*\n\n"
                f"*{info['name']}*\n"
                f"{info['address']}\n"
                f"🗺️ Maps: https://maps.google.com\n"
                f"📞 Phone: {info['phone']}"
            )
        if any(w in t for w in ["doctor", "specialist"]):
            docs = DoctorRepository.list_active(db)
            lines = [f"👨‍⚕️ *Doctors at {info['name']}:*\n"]
            for d in docs:
                lines.append(f"• *{d.name}* — {d.speciality} (Fee: ₹{int(d.fee)})")
            lines.append("\nSay *'Book [Doctor Name]'* to schedule an appointment.")
            return "\n".join(lines)

        return (
            f"🏥 *{info['name']}*\n"
            f"📍 {info['address']}\n"
            f"🕐 {info['timings']}\n"
            f"💰 {info['fees_summary']}\n"
            f"📞 {info['phone']}"
        )
