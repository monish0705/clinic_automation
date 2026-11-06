from datetime import date as DateType, datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.services.appointment_service import AppointmentService, DoubleBookingError, AppointmentNotFoundError
from app.repositories.doctor_repository import DoctorRepository
from app.utils.validators import parse_target_date, normalize_time_slot, normalize_phone_number
from app.core.logging import logger


# ── Tool Input Schemas ──────────────────────────────────────────

class CheckAvailabilityInput(BaseModel):
    doctor_name: str = Field(..., description="Doctor's name e.g. 'Dr. Sharma'")
    date: str = Field(..., description="Target date (YYYY-MM-DD, 'tomorrow', 'Monday')")


class GetDoctorDetailsInput(BaseModel):
    doctor_name: Optional[str] = Field(None, description="Doctor name to look up; if empty, returns all doctors")


class GetClinicInformationInput(BaseModel):
    query_type: str = Field(default="all", description="One of: 'timings', 'fees', 'location', 'all'")


class BookAppointmentInput(BaseModel):
    patient_phone: str = Field(..., description="Patient WhatsApp phone number")
    doctor_name: str = Field(..., description="Doctor's name")
    date: str = Field(..., description="Date of appointment (YYYY-MM-DD)")
    time: str = Field(..., description="Time slot (e.g. '10:00')")
    patient_name: Optional[str] = Field(None, description="Patient's full name")
    confirmed_by_patient: bool = Field(default=False, description="Whether patient explicitly confirmed")


class RescheduleAppointmentInput(BaseModel):
    appointment_code: str = Field(..., description="Appointment ID e.g. APT-10023")
    new_date: str = Field(..., description="New date (YYYY-MM-DD)")
    new_time: str = Field(..., description="New time slot (e.g. '11:00')")
    patient_phone: str = Field(..., description="Patient phone number for ownership verification")


class CancelAppointmentInput(BaseModel):
    appointment_code: str = Field(..., description="Appointment ID e.g. APT-10023")
    patient_phone: str = Field(..., description="Patient phone number for ownership verification")
    reason: Optional[str] = Field(None, description="Cancellation reason")


class GetPatientAppointmentsInput(BaseModel):
    patient_phone: str = Field(..., description="Patient WhatsApp phone number")


# ── Tool Implementations ────────────────────────────────────────

class ClinicTools:
    """Enterprise Tool Registry for LLM Agent. All actions execute against the verified backend."""

    @staticmethod
    def check_doctor_availability(db: Session, input_data: CheckAvailabilityInput) -> Dict[str, Any]:
        """Tool 1: Checks doctor's available slots on a given date."""
        logger.info(f"[TOOL] check_doctor_availability: doctor={input_data.doctor_name}, date={input_data.date}")
        doctor = DoctorRepository.get_by_name(db, input_data.doctor_name)
        if not doctor:
            return {
                "success": False,
                "error": f"Doctor '{input_data.doctor_name}' was not found in our directory.",
                "available_slots": []
            }

        target_date = parse_target_date(input_data.date)
        if not target_date:
            return {
                "success": False,
                "error": f"Could not understand the date '{input_data.date}'. Please specify a date like YYYY-MM-DD or 'tomorrow'.",
                "available_slots": []
            }

        today = datetime.utcnow().date()
        if target_date < today:
            return {
                "success": False,
                "error": f"The date '{target_date}' is in the past. Please choose a future date.",
                "available_slots": []
            }

        slots = AppointmentService.get_available_slots(db, doctor.id, target_date)
        return {
            "success": True,
            "doctor_id": doctor.id,
            "doctor_name": doctor.name,
            "speciality": doctor.speciality,
            "date": target_date.strftime("%Y-%m-%d"),
            "available_slots": slots,
            "message": f"{doctor.name} has {len(slots)} available slots on {target_date}." if slots else f"No free slots for {doctor.name} on {target_date}."
        }

    @staticmethod
    def get_doctor_details(db: Session, input_data: GetDoctorDetailsInput) -> Dict[str, Any]:
        """Tool 2: Retrieves doctor profiles, specialities, fees, and consultation schedules."""
        logger.info(f"[TOOL] get_doctor_details: doctor_name={input_data.doctor_name}")
        if input_data.doctor_name:
            doc = DoctorRepository.get_by_name(db, input_data.doctor_name)
            if not doc:
                return {"success": False, "error": f"Doctor '{input_data.doctor_name}' not found."}
            return {
                "success": True,
                "doctors": [{
                    "id": doc.id,
                    "name": doc.name,
                    "speciality": doc.speciality,
                    "fee": doc.fee,
                    "booking_type": doc.booking_type.value,
                    "available_days": doc.availabilities[0].day_of_week if doc.availabilities else "Mon-Fri"
                }]
            }

        all_docs = DoctorRepository.list_active(db)
        return {
            "success": True,
            "doctors": [{
                "id": d.id,
                "name": d.name,
                "speciality": d.speciality,
                "fee": d.fee,
                "booking_type": d.booking_type.value,
                "available_days": d.availabilities[0].day_of_week if d.availabilities else "Mon-Fri"
            } for d in all_docs]
        }

    @staticmethod
    def get_clinic_information(db: Session, input_data: GetClinicInformationInput) -> Dict[str, Any]:
        """Tool 3: Returns verified clinic metadata (timings, location, fees)."""
        logger.info(f"[TOOL] get_clinic_information: type={input_data.query_type}")
        info = AppointmentService.get_clinic_info(db)
        return {"success": True, "clinic_info": info}

    @staticmethod
    def book_appointment(db: Session, input_data: BookAppointmentInput) -> Dict[str, Any]:
        """
        Tool 4: Atomically books an appointment.
        SAFETY RULE: Requires explicit patient confirmation before booking!
        """
        logger.info(f"[TOOL] book_appointment: patient={input_data.patient_phone}, doctor={input_data.doctor_name}")
        if not input_data.confirmed_by_patient:
            return {
                "success": False,
                "requires_confirmation": True,
                "message": f"Please confirm if you want to book an appointment with {input_data.doctor_name} on {input_data.date} at {input_data.time}. Reply *YES* to confirm."
            }

        doctor = DoctorRepository.get_by_name(db, input_data.doctor_name)
        if not doctor:
            return {"success": False, "error": f"Doctor '{input_data.doctor_name}' not found."}

        target_date = parse_target_date(input_data.date)
        if not target_date:
            return {"success": False, "error": f"Invalid date: '{input_data.date}'"}

        norm_time = normalize_time_slot(input_data.time)
        if not norm_time:
            return {"success": False, "error": f"Invalid time: '{input_data.time}'"}

        try:
            appt = AppointmentService.book_appointment(
                db=db,
                patient_phone=input_data.patient_phone,
                doctor_id=doctor.id,
                appointment_date=target_date,
                time_slot=norm_time,
                patient_name=input_data.patient_name,
            )
            return {
                "success": True,
                "appointment_code": appt.appointment_code,
                "doctor_name": doctor.name,
                "date": appt.appointment_date.strftime("%Y-%m-%d"),
                "time": appt.time_slot,
                "status": appt.status.value,
                "booking_type": appt.booking_type.value,
                "message": f"Appointment {appt.appointment_code} successfully booked with {doctor.name} on {appt.appointment_date} at {appt.time_slot}."
            }
        except DoubleBookingError as dbe:
            return {"success": False, "error": str(dbe)}
        except Exception as exc:
            logger.error(f"[TOOL] Booking failed: {exc}")
            return {"success": False, "error": f"Booking could not be completed: {str(exc)}"}

    @staticmethod
    def reschedule_appointment(db: Session, input_data: RescheduleAppointmentInput) -> Dict[str, Any]:
        """Tool 5: Atomically reschedules an appointment with ownership verification."""
        logger.info(f"[TOOL] reschedule_appointment: code={input_data.appointment_code}")
        target_date = parse_target_date(input_data.new_date)
        if not target_date:
            return {"success": False, "error": f"Invalid new date: '{input_data.new_date}'"}

        norm_time = normalize_time_slot(input_data.new_time)
        if not norm_time:
            return {"success": False, "error": f"Invalid new time: '{input_data.new_time}'"}

        try:
            updated = AppointmentService.reschedule_appointment(
                db=db,
                appointment_code=input_data.appointment_code,
                new_date=target_date,
                new_time_slot=norm_time,
                patient_phone=input_data.patient_phone
            )
            return {
                "success": True,
                "appointment_code": updated.appointment_code,
                "doctor_name": updated.doctor.name,
                "new_date": updated.appointment_date.strftime("%Y-%m-%d"),
                "new_time": updated.time_slot,
                "message": f"Appointment {updated.appointment_code} successfully rescheduled to {updated.appointment_date} at {updated.time_slot}."
            }
        except PermissionError as pe:
            return {"success": False, "error": str(pe)}
        except DoubleBookingError as dbe:
            return {"success": False, "error": str(dbe)}
        except AppointmentNotFoundError as anfe:
            return {"success": False, "error": str(anfe)}
        except Exception as exc:
            return {"success": False, "error": f"Reschedule failed: {str(exc)}"}

    @staticmethod
    def cancel_appointment(db: Session, input_data: CancelAppointmentInput) -> Dict[str, Any]:
        """Tool 6: Cancels an appointment with ownership verification."""
        logger.info(f"[TOOL] cancel_appointment: code={input_data.appointment_code}")
        try:
            cancelled = AppointmentService.cancel_appointment(
                db=db,
                appointment_code=input_data.appointment_code,
                patient_phone=input_data.patient_phone,
                reason=input_data.reason
            )
            return {
                "success": True,
                "appointment_code": cancelled.appointment_code,
                "message": f"Appointment {cancelled.appointment_code} has been cancelled successfully."
            }
        except (PermissionError, AppointmentNotFoundError) as err:
            return {"success": False, "error": str(err)}
        except Exception as exc:
            return {"success": False, "error": f"Cancellation failed: {str(exc)}"}

    @staticmethod
    def get_patient_appointments(db: Session, input_data: GetPatientAppointmentsInput) -> Dict[str, Any]:
        """Tool 7: Returns verified upcoming appointments for the authenticated caller phone number."""
        logger.info(f"[TOOL] get_patient_appointments: phone={input_data.patient_phone}")
        appts = AppointmentService.get_patient_appointments(db, input_data.patient_phone)
        return {
            "success": True,
            "appointments": [{
                "appointment_code": a.appointment_code,
                "doctor_name": a.doctor.name,
                "speciality": a.doctor.speciality,
                "date": a.appointment_date.strftime("%Y-%m-%d"),
                "time": a.time_slot,
                "status": a.status.value,
            } for a in appts]
        }
