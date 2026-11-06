from datetime import datetime, timedelta
from app.services.appointment_service import AppointmentService
from app.repositories.doctor_repository import DoctorRepository
from app.workers.reminder_worker import ReminderWorker
from app.models.reminder import ReminderLog
from app.models.enums import ReminderStatus


def test_24h_reminder_dispatch_and_deduplication(db, mock_wa):
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    tomorrow = datetime.utcnow().date() + timedelta(days=1)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919876543210",
        doctor_id=doc.id,
        appointment_date=tomorrow,
        time_slot="10:00",
        patient_name="Reminder Test"
    )

    # 1. Run reminder worker for the first time
    summary1 = ReminderWorker.process_all_reminders(db)
    assert summary1["sent_24h"] == 1
    assert len(mock_wa.sent_messages) == 1
    assert "24 Hours Prior" in mock_wa.sent_messages[0]["message"]

    # 2. Re-run worker immediately (Deduplication test: must NOT re-send)
    summary2 = ReminderWorker.process_all_reminders(db)
    assert summary2["sent_24h"] == 0
    assert len(mock_wa.sent_messages) == 1  # Still 1, zero duplicates!

    # 3. Check ReminderLog
    logs = db.query(ReminderLog).filter(ReminderLog.appointment_id == appt.id).all()
    assert len(logs) == 1
    assert logs[0].status == ReminderStatus.SENT


def test_cancelled_appointment_no_reminder(db, mock_wa):
    """
    SAFETY TEST:
    Cancelled appointments must NEVER receive reminders.
    """
    doc = DoctorRepository.get_by_name(db, "Dr. Sharma")
    tomorrow = datetime.utcnow().date() + timedelta(days=1)

    appt = AppointmentService.book_appointment(
        db=db,
        patient_phone="+919876543210",
        doctor_id=doc.id,
        appointment_date=tomorrow,
        time_slot="11:00",
        patient_name="Cancel Reminder Test"
    )

    # Cancel the appointment
    AppointmentService.cancel_appointment(db, appt.appointment_code, patient_phone="+919876543210")

    # Run reminder worker
    summary = ReminderWorker.process_all_reminders(db)
    assert summary["sent_24h"] == 0
    assert len(mock_wa.sent_messages) == 0
