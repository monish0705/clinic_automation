# System Architecture Document

**Platform:** AI-Powered Clinic Automation Platform  
**Architecture Style:** Layered Domain-Driven Clean Architecture  
**Runtime:** Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL / SQLite  

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    subgraph Channels["Ingestion Layer"]
        WA_User["WhatsApp Patient"] -->|Webhook POST| Meta_API["Meta WhatsApp Cloud API"]
        Twilio_User["Twilio Client"] -->|Webhook Form POST| Twilio_API["Twilio WhatsApp API"]
    end

    subgraph Gateway["API & Security Boundary"]
        Meta_API -->|X-Hub-Signature-256| Webhook_Route["/api/v1/webhooks/whatsapp"]
        Twilio_API -->|X-Twilio-Signature| Legacy_Route["/webhook"]
        Staff_UI["Admin / Receptionist Portal"] -->|JWT Bearer Token| REST_Routes["/api/v1/appointments\n/api/v1/doctors\n/api/v1/patients"]
    end

    subgraph CoreServices["Domain & Agent Orchestration"]
        Webhook_Route --> WA_Service["WhatsAppService (Idempotency Engine)"]
        Legacy_Route --> WA_Service
        WA_Service --> Clinic_Agent["ClinicAgent (State Machine)"]
        Clinic_Agent --> LLM_Engine["LLMService (Structured Extraction)"]
        Clinic_Agent --> Tools["ClinicTools Registry"]
    end

    subgraph BusinessLogic["Business Logic Layer"]
        REST_Routes --> Appt_Service["AppointmentService"]
        Tools --> Appt_Service
        Appt_Service --> Appt_Repo["AppointmentRepository (ACID Transactions)"]
        Appt_Service --> Doc_Repo["DoctorRepository"]
        Appt_Service --> Pat_Repo["PatientRepository"]
    end

    subgraph Persistence["Storage & Async Workers"]
        Appt_Repo --> RDBMS[("PostgreSQL / SQLite")]
        Doc_Repo --> RDBMS
        Pat_Repo --> RDBMS
        Worker["ReminderWorker (Background Cron)"] -->|24h & 2h checks| Appt_Repo
        Worker -->|Outbound Alert| WA_Service
    end
```

---

## 2. Layered Responsibilities

### 2.1 API Ingestion Layer (`app/api/`)
- Exposes typed REST endpoints using FastAPI and Pydantic v2 schemas.
- Ingests inbound webhooks from both Meta WhatsApp Cloud API and Twilio.
- Cryptographically validates webhook signatures prior to payload processing.
- Handles HTTP status codes, structured errors, and CORS middleware.

### 2.2 Security & Authentication Layer (`app/core/security.py`, `app/services/auth_service.py`)
- Bcrypt password hashing (cost factor 12).
- Signed JWT token issuance with role-based claims (`ADMIN`, `RECEPTIONIST`, `DOCTOR`).
- Enforces strict patient isolation: patients cannot cancel or reschedule appointments belonging to another phone number.

### 2.3 Agent & Tool Calling Architecture (`app/agents/`)
- **Strict Separation of Decision and Execution**: The LLM NEVER directly queries or alters the database.
- The LLM classifies user intent into structured Pydantic schemas (`IntentExtractionResult`).
- The backend orchestrator (`ClinicAgent`) maps intents to typed tools (`ClinicTools`), verifies permissions, and executes atomic database transactions.
- Explicit patient confirmation is mandatory prior to committing bookings or cancellations.

### 2.4 Data Repository & Concurrency Control (`app/repositories/`)
- Relational schema with foreign keys, indexes, and unique constraints.
- Prevents double booking via atomic slot queries within transactional boundaries (`SELECT ... FOR UPDATE` in PostgreSQL).
- Provides idempotency keys to ignore re-transmitted webhook payloads.

### 2.5 Background Asynchronous Worker (`app/workers/`)
- Evaluates appointments 24 hours and 2 hours prior to scheduled consultation times.
- Dispatches proactive WhatsApp reminder alerts.
- Transactionally records reminder state to guarantee zero duplicate messages.
- Filters out cancelled or rescheduled appointments automatically.
