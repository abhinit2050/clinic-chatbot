# WHY THIS FILE EXISTS
# ---------------------
# Two different things in this app need to email a patient: the scheduled
# reminder job (reminders.py, fires on a timer) and a booking confirmation
# (tools.py, fires synchronously the moment book_appointment succeeds). Both
# go through send_email() below, so reminders.py and tools.py each stay
# focused on *when* to send an email, not *how*.
#
# Actual sending is disabled for the hosted demo: Render's outbound network
# blocks SMTP entirely (ports 25, 465, and 587 all fail with "Network is
# unreachable" — confirmed via a diagnostic connectivity check), which is a
# common anti-abuse restriction on free PaaS tiers. Booking/cancellation
# still work fully; this just means no real email goes out. Swap the body of
# send_email() for an HTTP-based provider (Resend, SendGrid, etc.) to restore
# real delivery — those work here since they're plain HTTPS calls, not SMTP.


def send_email(to_email: str, subject: str, body: str) -> None:
    print(f"[email disabled — see email_utils.py] Would have sent to {to_email}: {subject}")


def send_confirmation_email(to_email: str, patient_name: str, doctor_name: str, appt_date: str, appt_time: str) -> None:
    body = (
        f"Hi {patient_name},\n\n"
        f"Your appointment with {doctor_name} on {appt_date} at {appt_time} is confirmed.\n\n"
        f"Super Clinic"
    )
    send_email(to_email, "Appointment Confirmed", body)


def send_reminder_email(to_email: str, patient_name: str, doctor_name: str, appt_date: str, appt_time: str) -> None:
    body = (
        f"Hi {patient_name},\n\n"
        f"This is a reminder that you have an appointment with {doctor_name} "
        f"on {appt_date} at {appt_time}.\n\n"
        f"See you then!\nSuper Clinic"
    )
    send_email(to_email, "Appointment Reminder", body)
