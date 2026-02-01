# Answerly Workflow Overview

## Project Summary
**Answerly** is an AI-powered voice assistant system designed for healthcare clinics to handle inbound and outbound phone calls. It integrates with multiple practice management systems (Nookal, Cliniko, CorePlus, GoHighLevel) to manage appointments, patient data, and clinic operations through natural language conversations.

---

## Architecture Overview

### Core Technology Stack
- **Backend Framework**: FastAPI (Python)
- **Voice AI Platform**: Retell AI
- **Telephony**: Twilio
- **Database**: Firebase Firestore
- **LLM**: OpenAI GPT-4
- **Deployment**: Docker + Docker Compose

### Key Components
```
Answerly/
├── src/
│   ├── __init__.py              # Main FastAPI app & routes
│   ├── components/               # Integration modules
│   │   ├── nookal/              # Nookal PMS integration
│   │   ├── cliniko/             # Cliniko PMS integration
│   │   ├── coreplus/            # CorePlus PMS integration
│   │   ├── gohighlevel/         # GoHighLevel CRM integration
│   │   └── prompts/             # AI conversation prompts
│   ├── db/                      # Database operations
│   ├── routes/                  # API endpoints
│   ├── utils/                   # Helper functions
│   └── schemas/                 # Data models
├── app.py                       # Application entry point
└── requirements.txt             # Dependencies
```

---

## Call Flow Workflow

### 1. Inbound Calls (Patients    the Clinic)

#### Call Initiation
```
Patient calls clinic → Twilio receives call
    ↓
Twilio webhook hits: /twilio-voice-webhook/{agent_id}
    ↓
System determines call type (inbound/outbound)
    ↓
Registers call with Retell AI
    ↓
Twilio SIP dials Retell AI server
    ↓
WebSocket connection established: /llm/{call_id}
```

#### Real-time Conversation
1. **WebSocket Handler** (`src/__init__.py:190-267`)
   - Opens WebSocket connection for each call
   - Retrieves call metadata (patient info, appointment details, etc.)
   - Sends initial greeting
   - Maintains conversation loop

2. **LLM Client** (Nookal/Cliniko/CorePlus)
   - Receives transcript from Retell AI
   - Uses OpenAI GPT-4 to generate responses
   - Calls appropriate functions based on user intent
   - Returns conversational responses

3. **Function Calling** (Examples from Nookal LLM)
   - `create_appointment_new_patient_nookal` - Book new patient
   - `create_appointment_existing_patient_nookal` - Book returning patient
   - `update_appointment_nookal` - Reschedule appointment
   - `cancel_appointment_nookal` - Cancel appointment
   - `get_patient_appointment_nookal` - Check existing appointments
   - `get_patient_data_from_dynamo_nookal` - Retrieve patient records
   - `get_specific_day_slots_nookal` - Check availability
   - `transfer_call_nookal` - Transfer to human staff
   - `send_email` - Send email notifications

4. **PMS Integration**
   - Each function makes API calls to the respective PMS (Nookal/Cliniko/etc.)
   - Handles API responses, errors, and conflicts
   - Returns natural language responses to the caller

### 2. Outbound Calls (Clinic Calling Patients)

#### Call Initiation
```
Admin triggers outbound call via API: POST /outbound/reschedule
    ↓
Twilio creates outbound call with metadata
    ↓
WebSocket established: /outbound/reschedule/{call_id}
    ↓
Agent delivers context-specific message
    ↓
LLM handles conversation & actions
```

#### Outbound Use Cases
- **Rescheduling**: Doctor cancelled appointment
- **Appointment Confirmation**: Reminder calls
- **Patient Review**: Post-treatment follow-up
- **Patient Outreach**: Health check reminders

---

## Database Architecture

### Firestore Collections

1. **`users_auth`** - Clinic/user configuration
   - Clinic details
   - API keys for PMS systems
   - Agent IDs (Retell)
   - Prompts configuration
   - Working hours
   - Timezone settings

2. **`credits`** - Usage tracking
   - Call count, minutes, costs
   - Subscription plan
   - Payment status

3. **`calls_tracking`** - Call history
   - Call duration, status, transcript
   - Cost tracking
   - Patient information

4. **`transactions`** - Payment records

---

## Integration Architecture

### Practice Management Systems (PMS)

#### 1. **Nookal Integration** (`src/components/nookal/`)
- **Client**: `nookal_client.py` - API wrapper
- **LLM**: `llm.py` - Conversation handler
- **Functions**: Appointment CRUD, patient lookup, availability checks

#### 2. **Cliniko Integration** (`src/components/cliniko/`)
- **Client**: `cliniko_client.py` - API wrapper
- **LLM**: `llm_cliniko.py` (inbound), `outbound_llm.py` (outbound)
- **Functions**: Similar to Nookal with Cliniko-specific endpoints

#### 3. **CorePlus Integration** (`src/components/coreplus/`)
- Similar structure to other integrations

#### 4. **GoHighLevel Integration** (`src/components/gohighlevel/`)
- CRM-focused integration

### How Integration Works

1. **Dynamic Selection**: Based on `agent_id`, system selects:
   - Which PMS to use (Nookal/Cliniko/etc.)
   - Which prompts to use
   - Which API keys to use

2. **Function Execution**:
   ```
   User asks to book appointment
       ↓
   LLM decides to call: create_appointment_new_patient_nookal
       ↓
   Function extracts parameters (name, DOB, date, doctor)
       ↓
   Makes API call to Nookal with credentials
       ↓
   Handles response (success/conflict/error)
       ↓
   Returns natural language feedback to user
   ```

---

## Key Features

### 1. **Multi-PMS Support**
- Works with Nookal, Cliniko, CorePlus, GoHighLevel
- Dynamically loads clinic-specific configurations
- Handles different API schemas per system

### 2. **Smart Appointment Management**
- Books new and existing patients
- Handles scheduling conflicts intelligently
- Suggests alternative time slots
- Validates appointment dates (no past dates)

### 3. **Patient Lookup**
- Searches by phone number, name, DOB
- Handles multiple profiles per phone number
- Verifies patient identity conversationally

### 4. **Availability Checking**
- Real-time slot availability per doctor
- Suggests closest available times
- Filters by clinic, practitioner, date

### 5. **Error Handling**
- Graceful degradation when APIs fail
- Natural language error messages
- Fallback to email when call transfer unavailable

### 6. **Time Management**
- Clinic-specific timezone handling
- Working hours validation
- Break time detection

### 7. **Call Transfer**
- Transfers to clinic staff during business hours
- Checks working hours before transferring
- Email fallback when clinic closed

---

## API Endpoints

### Public Routes
- `GET /` - Health check
- `GET /health` - Service status

### Phone System Routes
- `POST /twilio-voice-webhook/{agent_id}` - Incoming call handler
- `WebSocket /llm/{call_id}` - Inbound conversation handler
- `WebSocket /outbound/reschedule/{call_id}` - Outbound conversation handler

### API Routes
- `POST /call-tracking/{user_id}` - Get call history
- `GET /credits/{user_id}` - Get usage credits

### Outbound Routes
- `POST /outbound/reschedule` - Trigger outbound call

### PMS-Specific Routes
- `/nookal/*` - Nookal-specific endpoints
- `/cliniko/*` - Cliniko-specific endpoints
- `/coreplus/*` - CorePlus-specific endpoints
- `/gohighlevel/*` - GoHighLevel-specific endpoints

---

## Environment Configuration

### Required Environment Variables
```bash
# OpenAI
OPENAI_API_KEY=your_key

# Retell AI
RETELL_API_KEY=your_key

# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token

# Clinic APIs (dynamically loaded per clinic)
NOOKAL_API_KEY=your_key        # Per clinic
CLINIKO_API_KEY=your_key       # Per clinic
COREPLUS_API_KEY=your_key      # Per clinic
GOHIGHLEVEL_API_KEY=your_key   # Per clinic

# Email
EMAIL_PASSWORD=your_password

# Database
FIREBASE_CREDENTIALS_PATH=path/to/secrets.json
```

---

## Deployment

### Local Development
```bash
# 1. Setup virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run ngrok for Twilio webhooks
ngrok http 8000

# 4. Configure .env file with ngrok URL
# 5. Update Retell AI dashboard with ngrok URL

# 6. Start application
python app.py
```

### Docker Deployment
```bash
# Build image
docker build -t answerly:latest .

# Run with docker-compose
docker-compose up -d

# Or run standalone
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your_key \
  -e RETELL_API_KEY=your_key \
  answerly:latest
```

---

## Key Workflows in Detail

### Scenario 1: Patient Books New Appointment

1. **Call Starts**
   - Patient calls clinic
   - System greets: "Thank you for calling [Clinic]. How may I help you?"

2. **Intent Recognition**
   - User: "I'd like to book an appointment"
   - LLM extracts intent → `create_appointment_new_patient_nookal`

3. **Information Gathering**
   - LLM asks for: First name, last name, DOB, desired date/time, doctor preference
   - Validates each piece of information

4. **Patient Check**
   - Checks if patient exists in DynamoDB
   - If exists → switches to existing patient flow
   - If not → continues with new patient

5. **Availability Check**
   - Queries Nookal API for available slots
   - Validates requested time against clinic schedule
   - Checks for conflicts

6. **Booking**
   - Creates appointment via API
   - Handles errors (conflict, unavailable, etc.)
   - Confirms with natural language response

7. **Call Ends**
   - Confirms appointment details
   - Offers additional help
   - Says goodbye and ends call

### Scenario 2: Clinic Reschedules Appointment (Outbound)

1. **Trigger**
   - Admin sends POST request to `/outbound/reschedule` with:
     - Patient phone number
     - Reason (doctor unavailable)
     - Old appointment details
     - New suggested times

2. **Call Initiation**
   - Twilio makes outbound call
   - WebSocket connects to `/outbound/reschedule/{call_id}`

3. **Context Setup**
   - Agent knows patient name, original appointment, reason
   - Delivers personalized message

4. **Conversation**
   - Patient responds
   - LLM suggests alternative times
   - Patient selects preferred time

5. **Update Appointment**
   - Calls `update_outbound_appointment` function
   - Updates appointment in PMS
   - Confirms new appointment

---

## Security & Multi-tenancy

### Per-Clinic Configuration
- Each clinic has unique `agent_id`
- Firebase lookup loads clinic-specific:
  - API keys
  - Prompts
  - Timezone
  - Working hours
  - Clinic name/agent name

### Authentication
- Firestore stores credentials per clinic
- API keys isolated per tenant
- No cross-clinic data access

---

## Monitoring & Logging

### Logs
- `logs/running_logs.log` - General application logs
- `logs/error_logs.log` - Error-specific logs

### Tracking
- Call duration, cost per call
- API usage tracking
- Credit management
- Payment processing

---

## Developer Notes

### Adding New PMS Integration
1. Create new directory: `src/components/newpms/`
2. Implement `newpms_client.py` with API wrapper
3. Implement `llm_newpms.py` with LLM handlers
4. Create function schemas in `newpms_function_calls_schema.py`
5. Add prompts in `src/components/prompts/`
6. Register routes in `src/__init__.py`

### Adding New Functions
1. Define function schema (parameters, descriptions)
2. Implement function in respective LLM client
3. Handle all response scenarios
4. Add natural language responses
5. Update `initialize_functions()` method

### Testing
- Use Retell AI dashboard for testing
- Check logs in `logs/` directory
- Monitor Firestore for data consistency
- Test with real phone numbers

---

## Troubleshooting

### Common Issues

1. **Call not connecting**
   - Check Twilio webhook configuration
   - Verify ngrok URL for local dev
   - Check Retell agent settings

2. **Appointments not booking**
   - Verify PMS API credentials
   - Check timezone handling
   - Review function parameters

3. **Wrong clinic loaded**
   - Verify `agent_id` mapping
   - Check Firestore `users_auth` collection
   - Confirm `inboundAgent` field

---

## Next Steps for New Developers

1. **Understand the flow**: Read this document thoroughly
2. **Set up environment**: Install dependencies, configure .env
3. **Explore code**: Start with `src/__init__.py` to see main flow
4. **Test locally**: Use ngrok + Retell dashboard
5. **Review one integration**: Deep dive into Nookal or Cliniko
6. **Check logs**: Understand error patterns
7. **Read Firestore**: Examine data structure

---

## Contact & Support

- **Contributor**: Ashley Alex Jacob
- **Project**: Answerly
- **License**: Not licensed yet



