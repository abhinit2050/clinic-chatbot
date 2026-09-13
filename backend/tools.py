# Each function below is decorated with @tool from langchain_core. That decorator
# reads the function's type hints + docstring and turns them into the JSON-schema
# tool definition the LLM needs to see (name, params, description) — the same
# information that used to be hand-duplicated in tool_definitions.py. One source
# of truth instead of two things that can drift apart.
#
# These are plain Python functions underneath (still hit SQLite directly via
# database.get_connection(), exactly like before) — @tool just wraps them so
# LangGraph's ToolNode can call them uniformly.
import json
import sqlite3
from typing import Annotated

from database import get_connection
from email_utils import send_confirmation_email
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

# Sent verbatim by the frontend's Yes button (see BookingConfirmation.jsx) —
# never typed by a real user, so matching this exact string is a reliable
# signal that the patient clicked "Yes" on the specific summary they were
# shown, not just that some message happened to follow a tool call.
BOOKING_CONFIRM_PHRASE = "Yes, please confirm the booking."


@tool
def list_doctors() -> list[dict]:
    """Return all available doctors with their id, name and specialty."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM doctors")
    doctors = cursor.fetchall()
    conn.close()
    return [{"id": row["id"], "name": row["name"], "specialty": row["specialty"]} for row in doctors]


@tool
def check_availability(doctor_id: int, date: str) -> list[dict]:
    """Check available (unbooked) time slots for a doctor on a given date (YYYY-MM-DD)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, time from slots WHERE doctor_id=? AND date=? AND is_booked=0
    """, (doctor_id, date))

    slots = cursor.fetchall()
    conn.close()

    results = []
    for row in slots:
        results.append({"slot_id": row["id"], "time": row["time"]})

    return results


def _get_confirmed_booking(messages: list) -> dict | None:
    """Returns the exact booking details the patient explicitly approved via
    the confirm_booking_details summary + Yes button — or None if there
    isn't a live confirmation right now.

    This walks the whole thread forward, tracking the most recent
    confirm_booking_details result. That "pending" summary only turns into a
    real confirmation if the very next human message is the Yes button's
    exact phrase (see BOOKING_CONFIRM_PHRASE) — any other reply (Cancel, a
    correction, small talk) clears it. Scoping it to "immediately next
    message" (not "any message, ever, after any confirm call") is what stops
    a confirmation from one attempt earlier in the thread — or from a
    completely different doctor/slot/name — from silently authorizing a
    later, different booking.
    """
    pending = None
    for message in messages:
        if isinstance(message, ToolMessage) and message.name == "confirm_booking_details":
            try:
                pending = json.loads(message.content)
            except (json.JSONDecodeError, TypeError):
                pending = None
        elif isinstance(message, HumanMessage):
            if pending is not None and message.content.strip() == BOOKING_CONFIRM_PHRASE:
                return pending
            pending = None
    return None


@tool
def confirm_booking_details(
    doctor_id: int,
    doctor_name: str,
    slot_id: int,
    date: str,
    time: str,
    name: str,
    phone: str,
    email: str | None = None,
    reason: str = "",
) -> dict:
    """Call this once you have ALL of: doctor, date, time slot, and the patient's name + phone (email optional, from request_patient_details). This shows the patient a summary card with Yes/Cancel buttons — it does NOT book anything by itself. Wait for their reply: only call book_appointment, with these exact same values, after they click Yes. If they click Cancel or want to change something, help them fix it and call this again with the corrected values — never call book_appointment without a fresh Yes on the current details."""
    # Echoing every field back (not just {"success": True}) is what lets
    # book_appointment later verify its own arguments against what the
    # patient actually saw and approved, and lets the frontend render the
    # summary card without re-deriving it from prose.
    return {
        "success": True,
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "slot_id": slot_id,
        "date": date,
        "time": time,
        "name": name,
        "phone": phone,
        "email": email,
        "reason": reason,
    }


@tool
def book_appointment(
    doctor_id: int,
    slot_id: int,
    name: str,
    phone: str,
    date: str,
    reason: str = "",
    email: str | None = None,
    state: Annotated[dict, InjectedState] = None,
) -> dict:
    """Book an appointment for a patient on a confirmed doctor/slot/date. Creates the patient record if they're new."""
    confirmed = _get_confirmed_booking((state or {}).get("messages", []))
    if not confirmed or (confirmed["doctor_id"], confirmed["slot_id"], confirmed["name"], confirmed["phone"]) != (
        doctor_id,
        slot_id,
        name,
        phone,
    ):
        return {
            "success": False,
            "message": "These exact details haven't been shown to and confirmed by the patient yet. Call confirm_booking_details with these values and wait for a Yes before booking — never invent or reuse patient details.",
        }

    conn = get_connection()
    cursor = conn.cursor()

    # Match on phone OR email, not phone alone — both are unique identifiers
    # for a patient now (see database.py), so a returning patient should be
    # recognized even if they give the email they registered with under a
    # different phone number, or vice versa. (SQLite's `email=?` bind never
    # matches when email is None/empty, so this safely degrades to a
    # phone-only lookup when no email is given, no special-casing needed.)
    cursor.execute("SELECT * from patients WHERE phone=? OR email=?", (phone, email))
    patient = cursor.fetchone()

    if not patient:
        try:
            cursor.execute("INSERT INTO patients (name, phone, email) VALUES (?,?,?)", (name, phone, email))
            effective_email = email
        except sqlite3.IntegrityError:
            # patients.email is UNIQUE (see database.py) — this fires if a
            # *different* patient already used this exact email. Rather than
            # fail the whole booking over an email collision, book them
            # without an email on file (no reminder for this patient, but the
            # appointment itself still goes through).
            cursor.execute("INSERT INTO patients (name, phone, email) VALUES (?,?,NULL)", (name, phone))
            effective_email = None
        patient_id = cursor.lastrowid
    else:
        patient_id = patient["id"]
        effective_email = patient["email"] or email
        # Backfill email for a returning patient who didn't have one on file yet —
        # without touching an email they'd already given us on a previous visit.
        if email and not patient["email"]:
            try:
                cursor.execute("UPDATE patients SET email=? WHERE id=?", (email, patient_id))
            except sqlite3.IntegrityError:
                effective_email = None

    cursor.execute("UPDATE slots SET is_booked=1 WHERE id=?", (slot_id,))
    cursor.execute(
        "INSERT INTO appointments (slot_id, patient_id, reason, status) VALUES (?,?,?,'booked')",
        (slot_id, patient_id, reason),
    )

    cursor.execute("SELECT name FROM doctors WHERE id=?", (doctor_id,))
    doctor = cursor.fetchone()
    cursor.execute("SELECT time FROM slots WHERE id=?", (slot_id,))
    slot = cursor.fetchone()

    conn.commit()
    conn.close()

    # Booking confirmation fires here, synchronously, as a direct side effect
    # of the booking succeeding — unlike the reminder email (reminders.py),
    # which fires later on an independent schedule. A failed send shouldn't
    # fail the booking itself (the appointment is already committed above),
    # so this is best-effort: log and move on rather than raising.
    if effective_email:
        try:
            send_confirmation_email(effective_email, name, doctor["name"], date, slot["time"])
        except Exception as e:
            print(f"Failed to send booking confirmation to {effective_email}: {e}")

    return {"success": True, "message": "Appointment booked successfully"}


@tool
def list_appointments(phone: str | None = None, email: str | None = None) -> dict:
    """List a patient's upcoming, non-cancelled appointments. Look them up by phone number, email, or both — either one alone is enough to find their record."""
    conn = get_connection()
    cursor = conn.cursor()

    # Same phone-OR-email matching as book_appointment, for the same reason:
    # either field alone uniquely identifies the patient.
    cursor.execute("SELECT id FROM patients WHERE phone=? OR email=?", (phone, email))
    patient = cursor.fetchone()

    if not patient:
        conn.close()
        # Distinguished from "found but nothing upcoming" below — the LLM needs
        # to react differently to each case (e.g. ask the patient to double-check
        # the number, vs. tell them they have no appointments booked).
        return {"patient_found": False, "appointments": []}

    cursor.execute("""
        SELECT a.id AS appointment_id, d.name AS doctor_name, d.specialty,
               s.date, s.time, a.reason
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        JOIN doctors d ON s.doctor_id = d.id
        WHERE a.patient_id = ? AND a.status = 'booked'
        ORDER BY s.date, s.time
    """, (patient["id"],))
    rows = cursor.fetchall()
    conn.close()

    appointments = [
        {
            "appointment_id": row["appointment_id"],
            "doctor_name": row["doctor_name"],
            "specialty": row["specialty"],
            "date": row["date"],
            "time": row["time"],
            "reason": row["reason"],
        }
        for row in rows
    ]
    return {"patient_found": True, "appointments": appointments}


@tool
def request_patient_details() -> dict:
    """Call this once the doctor, date, and time slot are all confirmed and you're ready to collect the patient's name, phone, and email. Do NOT ask for these in your text reply — calling this tool tells the interface to show the patient a proper form instead of expecting them to type it all out. Keep your accompanying message short, e.g. just letting them know a form is coming."""
    # No DB work here — this tool has no side effect of its own. It exists
    # purely as a signal the model can raise ("I'm ready for structured input
    # now"), which graph.py detects the same way it detects a successful
    # booking/cancellation, and which chat_router.py then passes to the
    # frontend so it can render an actual form instead of the model asking
    # for name/phone/email in plain text. Same idea as an app backend telling
    # its frontend "render this UI component now" instead of just prose.
    return {"success": True}


@tool
def cancel_appointment(appointment_id: int) -> dict:
    """Cancel a booked appointment by its id, freeing the associated time slot back up."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,))
    appointment = cursor.fetchone()

    if not appointment:
        conn.close()
        return {"success": False, "message": "Appointment not found."}

    if appointment["status"] == "cancelled":
        conn.close()
        return {"success": False, "message": "This appointment is already cancelled."}

    cursor.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,))
    cursor.execute("UPDATE slots SET is_booked=0 WHERE id=?", (appointment["slot_id"],))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Appointment cancelled successfully."}
