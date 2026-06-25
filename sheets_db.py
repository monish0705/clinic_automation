import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Connect once at startup ──────────────────────────────
def get_sheet_client():
    creds = Credentials.from_service_account_file(
        config.GOOGLE_CREDS_PATH, scopes=SCOPES
    )
    return gspread.authorize(creds)

_client = None
_workbook = None

def get_workbook():
    global _client, _workbook
    if _workbook is None:
        _client   = get_sheet_client()
        _workbook = _client.open_by_key(config.GOOGLE_SHEET_ID)
        _ensure_sheets_exist()
    return _workbook

def _ensure_sheets_exist():
    """Create the 3 required sheets if they don't exist yet."""
    wb = _workbook
    existing = [ws.title for ws in wb.worksheets()]

    if "Patients" not in existing:
        ws = wb.add_worksheet("Patients", rows=1000, cols=6)
        ws.append_row(["patient_id","name","phone","registered_at","last_seen","notes"])

    if "Appointments" not in existing:
        ws = wb.add_worksheet("Appointments", rows=2000, cols=10)
        ws.append_row([
            "appointment_id","patient_phone","patient_name",
            "doctor_name","date","time","status",
            "booking_type","created_at","reminder_sent"
        ])

    if "Doctors" not in existing:
        ws = wb.add_worksheet("Doctors", rows=50, cols=7)
        ws.append_row(["doctor_id","name","speciality","available_days",
                       "slots","booking_type","fee"])
        # Seed with sample doctors
        ws.append_row(["D001","Dr. Sharma","General Physician",
                       "Mon,Tue,Wed,Thu,Fri,Sat",
                       "09:00,09:30,10:00,10:30,11:00,11:30,14:00,14:30,15:00,15:30",
                       "auto_confirm","500"])
        ws.append_row(["D002","Dr. Patel","Cardiologist",
                       "Mon,Wed,Fri",
                       "10:00,11:00,12:00,15:00,16:00",
                       "manual_approval","800"])
        ws.append_row(["D003","Dr. Rao","Dermatologist",
                       "Tue,Thu,Sat",
                       "09:00,10:00,11:00,14:00,15:00,16:00",
                       "auto_confirm","700"])

# ── Patient operations ───────────────────────────────────
def get_or_create_patient(phone: str, name: str = "") -> dict:
    wb   = get_workbook()
    ws   = wb.worksheet("Patients")
    rows = ws.get_all_records()

    for row in rows:
        if str(row["phone"]) == phone:
            # Update last_seen
            cell = ws.find(phone)
            ws.update_cell(cell.row, 5, datetime.now().strftime("%Y-%m-%d %H:%M"))
            return row

    # New patient — create record
    patient_id = f"P{len(rows)+1:04d}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.append_row([patient_id, name, phone, now, now, ""])
    return {"patient_id": patient_id, "name": name, "phone": phone}

def update_patient_name(phone: str, name: str):
    wb   = get_workbook()
    ws   = wb.worksheet("Patients")
    cell = ws.find(phone)
    if cell:
        ws.update_cell(cell.row, 2, name)  # column 2 = name

# ── Doctor operations ────────────────────────────────────
def get_all_doctors() -> list[dict]:
    wb = get_workbook()
    ws = wb.worksheet("Doctors")
    return ws.get_all_records()

def get_doctor_by_name(name: str) -> dict | None:
    doctors = get_all_doctors()
    name_lower = name.lower()
    for doc in doctors:
        if name_lower in doc["name"].lower():
            return doc
    return None

def get_available_slots(doctor_name: str, date: str) -> list[str]:
    """
    Returns list of still-available time slots for a doctor on a given date.
    date format: YYYY-MM-DD
    """
    doc = get_doctor_by_name(doctor_name)
    if not doc:
        return []

    # Check if doctor works on this day of week
    try:
        day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%a")  # Mon, Tue, etc.
    except ValueError:
        return []

    # Map full day names to abbreviations
    day_map = {"Monday":"Mon","Tuesday":"Tue","Wednesday":"Wed",
               "Thursday":"Thu","Friday":"Fri","Saturday":"Sat","Sunday":"Sun"}
    available_days = [d.strip() for d in doc["available_days"].split(",")]

    if day_name not in available_days:
        return []

    all_slots = [s.strip() for s in doc["slots"].split(",")]

    # Remove already-booked slots
    booked = get_booked_slots(doctor_name, date)
    return [s for s in all_slots if s not in booked]

def get_booked_slots(doctor_name: str, date: str) -> list[str]:
    wb   = get_workbook()
    ws   = wb.worksheet("Appointments")
    rows = ws.get_all_records()
    return [
        str(row["time"]) for row in rows
        if str(row["doctor_name"]).lower() == doctor_name.lower()
        and str(row["date"]) == date
        and row["status"] in ("confirmed", "pending")
    ]

# ── Appointment operations ───────────────────────────────
def create_appointment(
    patient_phone: str,
    patient_name: str,
    doctor_name: str,
    date: str,
    time: str,
    booking_type: str = "auto_confirm"
) -> dict:
    wb = get_workbook()
    ws = wb.worksheet("Appointments")
    rows = ws.get_all_records()

    appt_id = f"A{len(rows)+1:05d}"
    status  = "confirmed" if booking_type == "auto_confirm" else "pending"
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")

    ws.append_row([
        appt_id, patient_phone, patient_name,
        doctor_name, date, time, status,
        booking_type, now, "no"
    ])
    return {
        "appointment_id": appt_id,
        "doctor": doctor_name,
        "date": date,
        "time": time,
        "status": status,
    }

def get_patient_appointments(phone: str) -> list[dict]:
    wb   = get_workbook()
    ws   = wb.worksheet("Appointments")
    rows = ws.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        row for row in rows
        if str(row["patient_phone"]) == phone
        and row["status"] != "cancelled"
        and str(row["date"]) >= today
    ]

def cancel_appointment(appointment_id: str) -> bool:
    wb   = get_workbook()
    ws   = wb.worksheet("Appointments")
    cell = ws.find(appointment_id)
    if cell:
        ws.update_cell(cell.row, 7, "cancelled")  # column 7 = status
        return True
    return False

def get_appointments_for_reminder() -> list[dict]:
    """Called by the scheduler — finds appointments tomorrow with no reminder sent."""
    wb   = get_workbook()
    ws   = wb.worksheet("Appointments")
    rows = ws.get_all_records()
    from datetime import timedelta
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return [
        row for row in rows
        if str(row["date"]) == tomorrow
        and row["status"] == "confirmed"
        and str(row["reminder_sent"]) == "no"
    ]

def mark_reminder_sent(appointment_id: str):
    wb   = get_workbook()
    ws   = wb.worksheet("Appointments")
    cell = ws.find(appointment_id)
    if cell:
        ws.update_cell(cell.row, 10, "yes")  # column 10 = reminder_sent