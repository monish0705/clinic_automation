# API Reference & OpenAPI Specification

All endpoints are prefixed with `/api/v1` except for health checks (`/health`) and legacy webhooks (`/webhook`). Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## 1. Authentication (`/api/v1/auth`)

### POST `/api/v1/auth/login`
Authenticates a staff member and returns a signed JWT.

**Request Body:**
```json
{
  "username": "admin",
  "password": "Admin@12345"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "role": "ADMIN",
  "username": "admin"
}
```

---

## 2. Appointments (`/api/v1/appointments`)

### POST `/api/v1/appointments`
Atomically books an appointment.

**Request Body:**
```json
{
  "patient_phone": "+919876543210",
  "patient_name": "Rohan Gupta",
  "doctor_id": 1,
  "appointment_date": "2026-11-12",
  "time_slot": "10:00",
  "notes": "Routine checkup"
}
```

**Response (201 Created):**
```json
{
  "id": 14,
  "appointment_code": "APT-73F9A",
  "clinic_id": 1,
  "doctor_id": 1,
  "patient_id": 4,
  "appointment_date": "2026-11-12",
  "time_slot": "10:00",
  "status": "CONFIRMED",
  "booking_type": "AUTO_CONFIRM",
  "notes": "Routine checkup",
  "created_at": "2026-11-06T18:00:00",
  "updated_at": "2026-11-06T18:00:00"
}
```

**Error Responses:**
- `409 Conflict`: `{"detail": "Time slot 10:00 is not available for Dr. Sharma on 2026-11-12."}`
- `400 Bad Request`: `{"detail": "Cannot book appointment on a past date."}`

### GET `/api/v1/appointments`
Lists clinic appointments with optional filters for `doctor_id`, `appointment_date`, and `status_filter`. (Staff JWT required).

### PATCH `/api/v1/appointments/{code}/reschedule`
Reschedules an appointment to a new date and time.

**Request Body:**
```json
{
  "new_date": "2026-11-15",
  "new_time_slot": "11:30"
}
```

### DELETE `/api/v1/appointments/{code}`
Cancels an appointment.

---

## 3. Doctors & Schedules (`/api/v1/doctors`)

### GET `/api/v1/doctors`
Returns list of all active doctors.

### GET `/api/v1/doctors/{id}/availability?date=YYYY-MM-DD`
Calculates available slots for a doctor on a specific date.

**Response (200 OK):**
```json
{
  "doctor_id": 1,
  "doctor_name": "Dr. Sharma",
  "target_date": "2026-11-12",
  "available_slots": ["09:00", "09:30", "10:30", "11:00", "14:00", "15:00"]
}
```

---

## 4. Webhooks (`/api/v1/webhooks`)

### GET `/api/v1/webhooks/whatsapp`
Meta WhatsApp Cloud API verification handshake responding with `hub.challenge`.

### POST `/api/v1/webhooks/whatsapp`
Meta WhatsApp Cloud API incoming message handler with `X-Hub-Signature-256` signature verification.

### POST `/webhook`
Legacy Twilio WhatsApp form payload endpoint preserving backward compatibility.
