# WHY THIS FILE EXISTS
# ---------------------
# Two different things in this app need to email a patient: the scheduled
# reminder job (reminders.py, fires on a timer) and a booking confirmation
# (tools.py, fires synchronously the moment book_appointment succeeds). Both
# need identical SMTP plumbing (connect, STARTTLS, login, send) — this file is
# the one place that plumbing lives, so reminders.py and tools.py each stay
# focused on *when* to send an email, not *how*.
import os
import smtplib
from email.mime.text import MIMEText


def send_email(to_email: str, subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [to_email], message.as_string())


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
