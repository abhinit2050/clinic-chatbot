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

from database import get_connection
from email_utils import send_reminder_email

REMINDER_WINDOW_HOURS = int(os.getenv("REMINDER_WINDOW_HOURS", "24"))


def send_due_reminders() -> int:
    """Finds booked appointments within the reminder window that haven't been reminded yet, emails each patient, and marks them as reminded. Returns how many were sent — called both by the scheduled job and by the manual /admin/send-reminders test endpoint."""
    now = datetime.now()
    window_end = now + timedelta(hours=REMINDER_WINDOW_HOURS)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id AS appointment_id, p.email, p.name AS patient_name,
               d.name AS doctor_name, s.date, s.time
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        JOIN doctors d ON s.doctor_id = d.id
        JOIN patients p ON a.patient_id = p.id
        WHERE a.status = 'booked'
          AND a.reminder_sent = 0
          AND p.email IS NOT NULL AND p.email != ''
          AND (s.date || ' ' || s.time) BETWEEN ? AND ?
        """,
        (now.strftime("%Y-%m-%d %H:%M"), window_end.strftime("%Y-%m-%d %H:%M")),
    )
    due = cursor.fetchall()

    sent_count = 0
    for row in due:
        try:
            send_reminder_email(row["email"], row["patient_name"], row["doctor_name"], row["date"], row["time"])
        except Exception as e:
            # Don't mark reminder_sent on failure — a transient SMTP error
            # (bad credentials, network blip) should retry on the next run
            # rather than silently skipping that patient's reminder forever.
            print(f"Failed to send reminder for appointment {row['appointment_id']}: {e}")
            continue
        cursor.execute("UPDATE appointments SET reminder_sent=1 WHERE id=?", (row["appointment_id"],))
        sent_count += 1

    conn.commit()
    conn.close()
    return sent_count
