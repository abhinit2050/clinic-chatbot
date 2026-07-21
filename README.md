# Clinic Appointment Chatbot

A conversational AI chatbot that lets patients book clinic appointments using natural language. Instead of filling out forms, patients simply chat — the AI figures out the rest.

Built as a learning project to explore LLM integration patterns, specifically OpenAI's function calling and the Responses API.

---

## Demo

> Patient: "I'd like to book an appointment with a dermatologist"
> 
> Bot: "Sure! Dr. Priya Mehta specialises in Dermatology. What date works for you?"
>
> Patient: "Tomorrow"
>
> Bot: "Dr. Mehta has slots available at 9am, 10am, 11am and 2pm on July 22nd. Which would you prefer?"
>
> Patient: "10am. My name is Abhinit and my number is 98XXXXXXXX"
>
> Bot: "Your appointment was booked successfully!"

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite) |
| Backend | FastAPI (Python) |
| Database | SQLite |
| LLM | OpenAI GPT-4o via Responses API |

---

## Features

- Natural language booking — patients describe what they need in plain English
- Function calling — the LLM decides when to query the database and when to write a booking, without any hardcoded decision logic
- Real-time availability — slot availability is always fetched live from the database, never fabricated by the model
- Patient identification by phone — returning patients are recognised by phone number; new patients are created automatically
- Session-based context management — conversation history is maintained on the backend, keyed by session ID. The frontend only sends the latest message
- Context pruning via summarisation — once an appointment is booked, the full conversation history is replaced with a concise summary using a secondary LLM call. This keeps the context window lean and reduces token usage on subsequent turns
- Dark / Light mode
- Error handling — HTTP and network errors surface as styled error bubbles in the chat UI

---

## Architecture

```
React Frontend
     │
     │  POST /chat  { session_id, message }
     ▼
FastAPI Backend (chat_router.py)
     │
     ▼
chat.py  ◄──────────────────────────────────┐
     │                                       │
     │  history + tool definitions           │  tool result
     ▼                                       │
OpenAI Responses API                         │
     │                                       │
     ├── text reply  ──► return to frontend  │
     │                                       │
     └── tool_call  ──► tools.py ───────────┘
                            │
                            ▼
                        SQLite (clinic.db)
```

### How function calling works

The backend defines three tools for the LLM:

- `list_doctors` — returns all doctors with their IDs and specialties
- `check_availability(doctor_id, date)` — returns available time slots for a doctor on a given date
- `book_appointment(doctor_id, slot_id, name, phone, date, reason)` — writes the appointment to the database

The LLM decides when to call each tool based on what information has been collected. The backend executes the actual Python functions and returns the results to the LLM, which then continues the conversation naturally.

### Context management

Conversation history is stored server-side in a Python dictionary keyed by `session_id` (a UUID generated on the frontend at session start). The frontend never sends history — only the latest message.

After a successful booking, a summarisation call is made to OpenAI which condenses the entire conversation into a few sentences. This summary replaces the full history in the store, pruning irrelevant small talk and tool call exchanges from future context.

---

## Project Structure

```
clinic-chatbot/
│
├── backend/
│   ├── main.py                 # FastAPI app, CORS, router registration
│   ├── database.py             # SQLite connection and table creation
│   ├── seed.py                 # Mock data population script
│   ├── tools.py                # Functions executed when LLM makes a tool call
│   ├── tool_definitions.py     # JSON schemas describing tools to OpenAI
│   ├── chat.py                 # LLM orchestration loop and session management
│   ├── chat_router.py          # POST /chat endpoint
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── App.jsx             # Root component, session ID, dark mode
│       ├── App.css
│       └── components/
│           ├── ChatWindow.jsx  # Renders conversation history
│           ├── ChatWindow.css
│           ├── InputBar.jsx    # Text input and send button
│           └── InputBar.css
│
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- An OpenAI API key with available credits

### Backend

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Add your OpenAI API key
echo "OPENAI_API_KEY=your-key-here" > .env

# Create tables and seed mock data
python3 database.py
python3 seed.py

# Start the server
uvicorn main:app --reload
```

The backend runs on `http://localhost:8000`.

### Frontend

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend runs on `http://localhost:5173`.

---

## Database Schema

```
doctors       — id, name, specialty
slots         — id, doctor_id, date, time, is_booked
patients      — id, name, phone (unique)
appointments  — id, slot_id, patient_id, reason
```

Slots are pre-generated for 5 doctors across 30 days with 8 hourly slots per day (09:00–16:00), totalling 1,200 records. ~25% are randomly pre-booked to simulate a realistic calendar.

---

## Key Design Decisions

Why SQLite? This is a demo project. SQLite requires zero setup and ships as a single file, making it easy to reset and reseed during development.

Why session history on the backend? Keeping history server-side means the frontend never sends the full conversation on every request — only the latest message. This is cleaner, more scalable, and prevents the frontend from being the source of truth for LLM context.

Why summarise after booking? A clinic chatbot session has a natural end point — the booking confirmation. Summarising at that moment prunes small talk, redundant exchanges, and raw tool call data from the history, keeping the context window lean without losing any meaningful information.

Why store tool results in conversation history? The LLM loses IDs (doctor ID, slot ID) between turns if tool results aren't persisted in the conversation store. Saving them as plain text ensures the model references real database IDs rather than hallucinating them.

---

## What I Learned

- How to wire OpenAI function calling into a real backend — defining tool schemas, handling tool call responses, and sending results back to the model
- The importance of session management when the LLM has no memory between API calls
- How LLMs can hallucinate database IDs across conversation turns and how persisting tool results in history fixes it
- Context pruning as a practical technique for managing token costs in multi-turn conversations
- FastAPI request validation with Pydantic and CORS setup for local development
