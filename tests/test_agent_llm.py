from datetime import datetime, timedelta
from app.agents.prompts import IntentExtractionResult
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
from app.agents.clinic_agent import ClinicAgent
from app.services.llm_service import LLMService


def get_future_weekday(min_days_ahead: int = 1):
    d = datetime.utcnow().date() + timedelta(days=min_days_ahead)
    while d.weekday() in (5, 6):  # Mon-Fri
        d += timedelta(days=1)
    return d


def test_intent_extraction_schema_validation():
    sample_json = {
        "intent": "BOOK_APPOINTMENT",
        "entities": {
            "doctor_name": "Dr. Sharma",
            "date": "2026-11-10",
            "time": "10:00",
            "appointment_code": None,
            "patient_name": "Jane Doe"
        },
        "confidence": 0.95,
        "missing_info": [],
        "reply_hint": "Confirm details"
    }
    validated = IntentExtractionResult.model_validate(sample_json)
    assert validated.intent == "BOOK_APPOINTMENT"
    assert validated.entities.doctor_name == "Dr. Sharma"
    assert validated.entities.time == "10:00"


def test_llm_fallback_on_unconfigured_api():
    fallback = LLMService._fallback_response("Can I cancel my appointment?")
    assert fallback["intent"] == "CANCEL_APPOINTMENT"

    fallback_book = LLMService._fallback_response("I want to book an appointment with Dr. Sharma")
    assert fallback_book["intent"] == "BOOK_APPOINTMENT"

    fallback_fees = LLMService._fallback_response("How much are the consultation fees?")
    assert fallback_fees["intent"] == "CLINIC_FAQ"


def test_clinic_tools_execution(db):
    target_date = get_future_weekday(2).strftime("%Y-%m-%d")

    # Tool 1: check_doctor_availability
    res_avail = ClinicTools.check_doctor_availability(
        db, CheckAvailabilityInput(doctor_name="Dr. Sharma", date=target_date)
    )
    assert res_avail["success"] is True
    assert len(res_avail["available_slots"]) > 0

    # Tool 2: get_doctor_details
    res_doc = ClinicTools.get_doctor_details(db, GetDoctorDetailsInput(doctor_name="Dr. Patel"))
    assert res_doc["success"] is True
    assert res_doc["doctors"][0]["speciality"] == "Cardiologist"

    # Tool 3: get_clinic_information
    res_info = ClinicTools.get_clinic_information(db, GetClinicInformationInput(query_type="all"))
    assert res_info["success"] is True
    assert "name" in res_info["clinic_info"]

    # Tool 4: book_appointment (Requires explicit patient confirmation)
    unconfirmed = ClinicTools.book_appointment(
        db, BookAppointmentInput(
            patient_phone="+919876543210",
            doctor_name="Dr. Sharma",
            date=target_date,
            time="09:00",
            confirmed_by_patient=False
        )
    )
    assert unconfirmed["requires_confirmation"] is True

    # Now confirm
    confirmed = ClinicTools.book_appointment(
        db, BookAppointmentInput(
            patient_phone="+919876543210",
            doctor_name="Dr. Sharma",
            date=target_date,
            time="09:00",
            patient_name="Alex Brown",
            confirmed_by_patient=True
        )
    )
    assert confirmed["success"] is True
    code = confirmed["appointment_code"]

    # Tool 5: get_patient_appointments
    res_appts = ClinicTools.get_patient_appointments(
        db, GetPatientAppointmentsInput(patient_phone="+919876543210")
    )
    assert res_appts["success"] is True
    assert len(res_appts["appointments"]) >= 1

    # Tool 6: reschedule_appointment
    new_date = get_future_weekday(3).strftime("%Y-%m-%d")
    res_resched = ClinicTools.reschedule_appointment(
        db, RescheduleAppointmentInput(
            appointment_code=code,
            new_date=new_date,
            new_time="10:00",
            patient_phone="+919876543210"
        )
    )
    assert res_resched["success"] is True

    # Tool 7: cancel_appointment
    res_cancel = ClinicTools.cancel_appointment(
        db, CancelAppointmentInput(
            appointment_code=code,
            patient_phone="+919876543210",
            reason="Change of plans"
        )
    )
    assert res_cancel["success"] is True


def test_conversational_multi_turn_booking_flow(db):
    phone = "+919444455555"
    target_date = get_future_weekday(2).strftime("%Y-%m-%d")

    # Turn 1: Patient starts booking
    msg1 = f"I want to book an appointment with Dr. Sharma on {target_date} at 10:00"
    reply1 = ClinicAgent.process_incoming_message(db, phone, msg1, profile_name="MultiTurn Patient")
    assert "Confirm Your Appointment" in reply1 or "YES" in reply1

    # Turn 2: Patient explicitly confirms
    reply2 = ClinicAgent.process_incoming_message(db, phone, "YES")
    assert "Appointment Confirmed" in reply2
    assert "APT-" in reply2
