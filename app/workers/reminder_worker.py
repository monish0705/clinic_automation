from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.models.appointment import Appointment
from app.models.reminder import ReminderLog
from app.models.enums import AppointmentStatus, ReminderType, ReminderStatus
from app.services.whatsapp_service import WhatsAppService
from app.core.config import settings
from app.core.logging import logger


class ReminderWorker:
    """
    Background worker processing pre-appointment WhatsApp reminders.
    Ensures zero duplicate dispatches, handles retries, and ignores cancelled appointments.
    """

    @classmethod
    def process_all_reminders(cls, db: Session) -> Dict[str, int]:
        """Runs the reminder pipeline for 24-hour and 2-hour pre-appointment reminders."""
        logger.info("[REMINDER_WORKER] Checking for due appointment reminders...")
        today = datetime.utcnow().date()
        date_24h = today + timedelta(days=1)

        sent_24h = cls._process_24h_reminders(db, date_24h)
        sent_2h = cls._process_2h_reminders(db, today)

        logger.info(f"[REMINDER_WORKER] Summary: {sent_24h} 24h reminders sent, {sent_2h} 2h reminders sent.")
        return {"sent_24h": sent_24h, "sent_2h": sent_2h}

    @classmethod
    def _process_24h_reminders(cls, db: Session, target_date) -> int:
        # Fetch confirmed appointments for tomorrow where 24h reminder has NOT been sent
        appts = db.query(Appointment).filter(
            Appointment.appointment_date == target_date,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminder_24h_sent.is_(False)
        ).all()

        sent_count = 0
        for appt in appts:
            patient_phone = appt.patient.phone
            doctor_name = appt.doctor.name
            msg_text = (
                f"⏰ *Appointment Reminder (24 Hours Prior)*\n\n"
                f"Hello {appt.patient.name or 'there'}!\n"
                f"This is a reminder for your upcoming appointment at *{settings.CLINIC_NAME}*:\n\n"
                f"👨‍⚕️ *Doctor:* {doctor_name}\n"
                f"📅 *Date:* Tomorrow ({appt.appointment_date})\n"
                f"⏰ *Time:* {appt.time_slot}\n"
                f"🔖 *ID:* {appt.appointment_code}\n"
                f"📍 *Location:* {settings.CLINIC_ADDRESS}\n\n"
                f"Reply *CANCEL* if you cannot make it, or *RESCHEDULE* to pick another time."
            )

            result = WhatsAppService.send_message(patient_phone, msg_text)
            if result.get("success"):
                appt.reminder_24h_sent = True
                log = ReminderLog(
                    appointment_id=appt.id,
                    reminder_type=ReminderType.HOURS_24,
                    scheduled_for=datetime.utcnow(),
                    sent_at=datetime.utcnow(),
                    status=ReminderStatus.SENT,
                    attempts=1
                )
                db.add(log)
                db.commit()
                sent_count += 1
                logger.info(f"[REMINDER_WORKER] 24h reminder sent for {appt.appointment_code}")
            else:
                log = ReminderLog(
                    appointment_id=appt.id,
                    reminder_type=ReminderType.HOURS_24,
                    scheduled_for=datetime.utcnow(),
                    status=ReminderStatus.FAILED,
                    attempts=1,
                    error_message=result.get("error")
                )
                db.add(log)
                db.commit()

        return sent_count

    @classmethod
    def _process_2h_reminders(cls, db: Session, target_date) -> int:
        now = datetime.utcnow()
        # Find appointments today where 2h reminder has NOT been sent
        appts = db.query(Appointment).filter(
            Appointment.appointment_date == target_date,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminder_2h_sent.is_(False)
        ).all()

        sent_count = 0
        for appt in appts:
            # Parse slot time e.g. "10:30"
            try:
                slot_hour, slot_min = map(int, appt.time_slot.split(":"))
                appt_datetime = datetime(
                    appt.appointment_date.year,
                    appt.appointment_date.month,
                    appt.appointment_date.day,
                    slot_hour,
                    slot_min
                )
                # If appointment is between 0 and 2.5 hours away
                time_diff = (appt_datetime - now).total_seconds() / 3600.0
                if 0 <= time_diff <= 2.5:
                    patient_phone = appt.patient.phone
                    doctor_name = appt.doctor.name
                    msg_text = (
                        f"⏰ *Urgent: Appointment in 2 Hours!*\n\n"
                        f"Your consultation with *{doctor_name}* is scheduled for today at *{appt.time_slot}*.\n"
                        f"📍 *Location:* {settings.CLINIC_ADDRESS}\n"
                        f"🔖 *ID:* {appt.appointment_code}\n\n"
                        f"Please arrive 10 minutes prior to complete registration."
                    )
                    result = WhatsAppService.send_message(patient_phone, msg_text)
                    if result.get("success"):
                        appt.reminder_2h_sent = True
                        log = ReminderLog(
                            appointment_id=appt.id,
                            reminder_type=ReminderType.HOURS_2,
                            scheduled_for=now,
                            sent_at=now,
                            status=ReminderStatus.SENT,
                            attempts=1
                        )
                        db.add(log)
                        db.commit()
                        sent_count += 1
                        logger.info(f"[REMINDER_WORKER] 2h reminder sent for {appt.appointment_code}")
            except Exception as exc:
                logger.error(f"[REMINDER_WORKER] Error evaluating 2h reminder for {appt.appointment_code}: {exc}")

        return sent_count


def run_reminder_cycle():
    """Standalone worker execution function callable from background schedulers."""
    db = SessionLocal()
    try:
        ReminderWorker.process_all_reminders(db)
    finally:
        db.close()
