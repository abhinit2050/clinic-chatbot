import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from chat_router import router
from database import create_tables, get_connection
from reminders import send_due_reminders

create_tables()


def seed_if_empty():
    """Demo deploys start from a fresh, empty SQLite file every time the
    container restarts (Cloud Run's filesystem is ephemeral) — reseed so the
    doctors/slots/patients data the chatbot demos against always exists."""
    conn = get_connection()
    is_empty = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0
    conn.close()
    if is_empty:
        from seed import seed
        seed()


seed_if_empty()

# BackgroundScheduler runs its jobs on their own thread(s), separate from the
# FastAPI request/response cycle — the reminder job fires on a timer whether
# or not anyone is actively chatting. `lifespan` is FastAPI's hook for
# start-this-when-the-app-boots / stop-this-when-it-shuts-down setup, the
# equivalent of code you'd put around `app.listen(...)` in an Express app.
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    interval_minutes = int(os.getenv("REMINDER_CHECK_INTERVAL_MINUTES", "15"))
    scheduler.add_job(send_due_reminders, "interval", minutes=interval_minutes, id="reminder_job")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router)


@app.post("/admin/send-reminders")
def trigger_reminders():
    """Manual trigger for the reminder job, so it can be tested on demand
    instead of waiting for the real interval/window to elapse. Unauthenticated
    — fine for local dev, but this is exactly the kind of endpoint you'd lock
    behind an admin auth check before shipping anywhere real."""
    sent = send_due_reminders()
    return {"sent": sent}


# Serves the built React app (see Dockerfile) so the whole thing runs as one
# Cloud Run service. Mounted last so it doesn't shadow the API routes above —
# StaticFiles(html=True) falls back to index.html for unmatched paths.
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
