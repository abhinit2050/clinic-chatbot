import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from chat_router import router
from database import create_tables
from reminders import send_due_reminders

create_tables()

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
