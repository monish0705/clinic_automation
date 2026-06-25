# Hospital WhatsApp Bot

A lightweight FastAPI-based WhatsApp chatbot that helps patients book, cancel, reschedule, and check appointments for a hospital or clinic.

## What it does

- Handles incoming WhatsApp messages via a Twilio webhook
- Uses an LLM-based intent extractor to understand user requests
- Books appointments through Google Sheets as the backend database
- Sends appointment reminders automatically
- Supports FAQ responses for fees, timings, location, and doctor availability

## Key components

- `main.py`
  - FastAPI web server with `/` health check and `/webhook` endpoint
  - Routes inbound WhatsApp messages through intent processing and booking logic
  - Starts a background scheduler to send reminders every hour

- `intent_engine.py`
  - Sends user messages to OpenAI to extract structured intent and entities
  - Returns normalized `doctor_name`, `date`, `time`, `appointment_id`, and `patient_name`

- `booking_handler.py`
  - Main router for booking, canceling, rescheduling, availability checks, and FAQs
  - Manages multi-step conversational flows using in-memory `sessions`

- `sheets_db.py`
  - Google Sheets integration using `gspread`
  - Stores patients, doctors, and appointments
  - Reads doctor schedules, available slots, and appointment records

- `whatsapp_sender.py`
  - Sends WhatsApp messages using Twilio
  - Contains reusable message templates for confirmations, reminders, FAQs, and errors

- `config.py`
  - Loads environment variables and project settings
  - Stores Twilio, OpenAI, and Google Sheets configuration
  - Defines hospital metadata and session storage

## Setup

1. Install dependencies

```powershell
pip install -r requirements.txt
```

If `requirements.txt` is not present, install at least:

```powershell
pip install fastapi uvicorn apscheduler openai gspread google-auth twilio python-dotenv
```

2. Create a `.env` file with the following values:

```text
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
OPENAI_API_KEY=your_openai_api_key
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_CREDENTIALS_PATH=credentials.json
HOSPITAL_NAME=Your Hospital Name
```

3. Provide Google service account credentials in `credentials.json` and grant access to the target Google Sheet.

4. Run the app locally

```powershell
python main.py
```

5. Configure Twilio WhatsApp webhook

Point the Twilio WhatsApp sandbox or number webhook to:

```text
http://<your-server-host>:8000/webhook
```

## How it works

1. Patient sends a WhatsApp message
2. Twilio forwards the message to `/webhook`
3. `intent_engine` extracts intent and entities from the text
4. `booking_handler` decides the action and interacts with `sheets_db`
5. `whatsapp_sender` sends back a reply through Twilio
6. A scheduled job sends reminders for tomorrow's confirmed appointments

## Notes

- Current session state is stored in memory and resets on server restart.
- Google Sheets is used as the persistent storage backend for patients, doctors, and appointments.
- The bot is designed for simple natural-language interactions and will ask follow-up questions when additional information is needed.

## Extending the project

- Add richer NLP handling or fallback rules
- Persist conversational state to Google Sheets or a database
- Add support for images, documents, or richer WhatsApp templates
- Add admin endpoints for reviewing or approving manual bookings
