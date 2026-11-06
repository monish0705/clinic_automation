# Database Design & Concurrency Model

**Database:** PostgreSQL 16+ (Production) / SQLite 3.38+ (Local Dev & Automated CI)  
**ORM:** SQLAlchemy 2.0  
**Migration Engine:** Alembic  

---

## 1. Entity-Relationship Model

```mermaid
erDiagram
    CLINIC ||--o{ DOCTOR : employs
    CLINIC ||--o{ APPOINTMENT : hosts
    DOCTOR ||--o{ DOCTOR_AVAILABILITY : schedules
    DOCTOR ||--o{ APPOINTMENT : attends
    PATIENT ||--o{ APPOINTMENT : books
    PATIENT ||--o{ CONVERSATION : conducts
    CONVERSATION ||--o{ MESSAGE : contains
    APPOINTMENT ||--o{ REMINDER_LOG : triggers
    DOCTOR ||--o| USER : associates

    CLINIC {
        int id PK
        string name
        string address
        string phone
        string timings
        string fees_summary
        boolean is_active
    }

    DOCTOR {
        int id PK
        int clinic_id FK
        string name
        string speciality
        float fee
        string booking_type
        boolean is_active
    }

    DOCTOR_AVAILABILITY {
        int id PK
        int doctor_id FK
        string day_of_week
        string available_slots
        boolean is_available
    }

    PATIENT {
        int id PK
        string phone UK
        string name
        string email
        datetime last_seen_at
    }

    APPOINTMENT {
        int id PK
        string appointment_code UK
        int clinic_id FK
        int doctor_id FK
        int patient_id FK
        date appointment_date
        string time_slot
        string status
        string booking_type
        boolean reminder_24h_sent
        boolean reminder_2h_sent
        string idempotency_key UK
    }

    CONVERSATION {
        int id PK
        int patient_id FK
        string phone
        string current_state
        json state_metadata
        datetime last_interaction_at
    }

    MESSAGE {
        int id PK
        int conversation_id FK
        int patient_id FK
        string direction
        string message_id UK
        text content
        string status
    }

    USER {
        int id PK
        string username UK
        string email UK
        string hashed_password
        string role
        int doctor_id FK
        boolean is_active
    }

    REMINDER_LOG {
        int id PK
        int appointment_id FK
        string reminder_type
        datetime scheduled_for
        datetime sent_at
        string status
        int attempts
    }
```

---

## 2. Concurrency Safety & Anti-Double-Booking Architecture

### The Problem in Legacy Prototypes:
In the original Google Sheets prototype, checking slot availability and appending an appointment were distinct, unsynchronized operations. Under concurrent requests:
1. Patient A and Patient B ask for Dr. Sharma at 10:00 AM on Monday.
2. Both requests read Google Sheets simultaneously; both see the slot as free.
3. Both append rows. The doctor is now double-booked.

### The Production Solution:
1. **Compound Index**: An index on `(doctor_id, appointment_date, time_slot)` provides indexed query speeds.
2. **Atomic Transaction Isolation**:
   - In `AppointmentRepository.create_atomic`, the slot check query executes inside an active database transaction.
   - For PostgreSQL engines, `with_for_update()` acquires a row-level lock on existing records matching the criteria.
   - Any concurrent transaction attempting to book the identical slot encounters a collision and aborts with `DoubleBookingError`.
3. **Idempotency Keys**: Requests carrying unique `idempotency_key` headers return the existing booking record rather than re-executing.
