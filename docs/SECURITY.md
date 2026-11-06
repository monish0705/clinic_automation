# Security & Compliance Specification

This platform implements defense-in-depth principles across all API and messaging interfaces.

---

## 1. Security Architecture Matrix

| Security Domain | Implementation | Threat Mitigated |
| :--- | :--- | :--- |
| **Webhook Authenticity** | HMAC-SHA256 (`X-Hub-Signature-256`) and Twilio HMAC-SHA1 signature verification. | Replay attacks, spoofed webhooks, unauthorized booking triggers. |
| **Authentication** | Passwords hashed using bcrypt (12 rounds). Bearer JWTs signed via HMAC-SHA256 with expiration claims. | Credential stuffing, brute force, session hijacking. |
| **Role-Based Access Control** | FastAPI dependency injection enforcing `ADMIN`, `RECEPTIONIST`, and `DOCTOR` privileges. | Privilege escalation, unauthorized doctor/clinic modification. |
| **Data Isolation & Multi-Tenancy** | Phone numbers extracted directly from cryptographically signed webhook envelopes. Patients can only query, cancel, or reschedule appointments matching their verified caller ID. | IDOR (Insecure Direct Object Reference), cross-patient data leaks. |
| **SQL Injection** | Strict SQLAlchemy 2.0 ORM parameterization and type validation. | SQL injection vulnerabilities. |
| **Secret Management** | All credentials loaded through environment variables; `.gitignore` rules prevent secret leakage. | Credential exposure in source control. |
| **GenAI Clinical Guardrails** | Deterministic tool calling; zero direct database writes by LLMs; medical diagnosis refusal rules. | Hallucinated slots, unauthorized database modification, unsafe clinical guidance. |

---

## 2. Patient Identity Verification Flow

In traditional web applications, authentication relies on passwords and 2FA. In WhatsApp automation:
1. The platform **never trusts a phone number provided inside the message body text** (e.g. "cancel appointment for +919876543210").
2. The platform extracts the caller ID strictly from the verified provider webhook envelope (`from` or `From` field).
3. Any attempt by a caller to cancel or reschedule an appointment code registered under a different phone number fails with `PermissionError: Access denied`.
