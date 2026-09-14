# WHY THIS FILE EXISTS
# ---------------------
# Booking/cancellation happen synchronously inside a chat turn — the patient
# is right there, waiting for a reply. A reminder is different: nobody is
# "in the room" when it needs to fire, it has to happen on its own schedule
# (e.g. 24h before an appointment), regardless of whether anyone is chatting
# with the bot at that moment. That's why this isn't a tool the LLM calls —
# it's a background job, started once at server startup (see main.py) and
# run on a timer by APScheduler, similar in spirit to a cron job or a
# node-cron/agenda job in a Node backend. The actual SMTP mechanics live in
# email_utils.py (shared with the synchronous booking-confirmation email) —
# this file is just the scheduling/query logic for *reminder* emails specifically.
import os
from datetime import datetime, timedelta

from database import get_db
from email_utils import send_reminder_email

REMINDER_WINDOW_HOURS = int(os.getenv("REMINDER_WINDOW_HOURS", "24"))


def send_due_reminders() -> int:
    """Finds booked appointments within the reminder window that haven't been reminded yet, emails each patient, and marks them as reminded. Returns how many were sent — called both by the scheduled job and by the manual /admin/send-reminders test endpoint."""
    now = datetime.now()
    window_end = now + timedelta(hours=REMINDER_WINDOW_HOURS)
    now_str = now.strftime("%Y-%m-%d %H:%M")
    window_end_str = window_end.strftime("%Y-%m-%d %H:%M")

    db = get_db()
    sent_count = 0
    # No JOIN in MongoDB — a demo's worth of pending appointments is tiny, so
    # a per-appointment lookup of its slot/doctor/patient is far more
    # readable than an aggregation $lookup pipeline for the same result.
    for appt in db.appointments.find({"status": "booked", "reminder_sent": False}):
        patient = db.patients.find_one({"id": appt["patient_id"]})
        if not patient or not patient.get("email"):
            continue

        slot = db.slots.find_one({"id": appt["slot_id"]})
        appt_datetime_str = f"{slot['date']} {slot['time']}"
        if not (now_str <= appt_datetime_str <= window_end_str):
            continue

        doctor = db.doctors.find_one({"id": slot["doctor_id"]})
        try:
            send_reminder_email(patient["email"], patient["name"], doctor["name"], slot["date"], slot["time"])
        except Exception as e:
            # Don't mark reminder_sent on failure — a transient SMTP error
            # (bad credentials, network blip) should retry on the next run
            # rather than silently skipping that patient's reminder forever.
            print(f"Failed to send reminder for appointment {appt['id']}: {e}")
            continue
        db.appointments.update_one({"id": appt["id"]}, {"$set": {"reminder_sent": True}})
        sent_count += 1

    return sent_count
