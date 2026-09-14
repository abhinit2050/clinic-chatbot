# Each function below is decorated with @tool from langchain_core. That decorator
# reads the function's type hints + docstring and turns them into the JSON-schema
# tool definition the LLM needs to see (name, params, description) — the same
# information that used to be hand-duplicated in tool_definitions.py. One source
# of truth instead of two things that can drift apart.
#
# These are plain Python functions underneath (hit MongoDB via database.get_db(),
# see database.py) — @tool just wraps them so LangGraph's ToolNode can call
# them uniformly.
import json
from typing import Annotated

from database import get_db, next_id
from email_utils import send_confirmation_email
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pymongo.errors import DuplicateKeyError

# Sent verbatim by the frontend's Yes button (see BookingConfirmation.jsx) —
# never typed by a real user, so matching this exact string is a reliable
# signal that the patient clicked "Yes" on the specific summary they were
# shown, not just that some message happened to follow a tool call.
BOOKING_CONFIRM_PHRASE = "Yes, please confirm the booking."


@tool
def list_doctors() -> list[dict]:
    """Return all available doctors with their id, name and specialty."""
    db = get_db()
    return [
        {"id": doc["id"], "name": doc["name"], "specialty": doc["specialty"]}
        for doc in db.doctors.find({}, {"_id": 0})
    ]


@tool
def check_availability(doctor_id: int, date: str) -> list[dict]:
    """Check available (unbooked) time slots for a doctor on a given date (YYYY-MM-DD)."""
    db = get_db()
    slots = db.slots.find({"doctor_id": doctor_id, "date": date, "is_booked": False}, {"_id": 0})
    return [{"slot_id": slot["id"], "time": slot["time"]} for slot in slots]


def _find_patient(db, phone: str | None, email: str | None):
    """Same "either field alone identifies the patient" matching used by
    book_appointment and list_appointments. Built as an explicit $or over
    only the fields actually provided, rather than always including both —
    passing a bare {"email": None} would match documents where email is
    literally null, unlike SQLite's `email=?` bind, which never matches on a
    NULL parameter regardless of the column's value."""
    conditions = []
    if phone:
        conditions.append({"phone": phone})
    if email:
        conditions.append({"email": email})
    if not conditions:
        return None
    return db.patients.find_one({"$or": conditions})


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

    db = get_db()

    # Match on phone OR email, not phone alone — both are unique identifiers
    # for a patient now (see database.py), so a returning patient should be
    # recognized even if they give the email they registered with under a
    # different phone number, or vice versa.
    patient = _find_patient(db, phone, email)

    if not patient:
        patient_id = next_id("patients")
        try:
            db.patients.insert_one({"id": patient_id, "name": name, "phone": phone, "email": email})
            effective_email = email
        except DuplicateKeyError:
            # patients.email has a unique index (see database.py) — this fires
            # if a *different* patient already used this exact email. Rather
            # than fail the whole booking over an email collision, book them
            # without an email on file (no reminder for this patient, but the
            # appointment itself still goes through).
            db.patients.insert_one({"id": patient_id, "name": name, "phone": phone, "email": None})
            effective_email = None
    else:
        patient_id = patient["id"]
        effective_email = patient.get("email") or email
        # Backfill email for a returning patient who didn't have one on file yet —
        # without touching an email they'd already given us on a previous visit.
        if email and not patient.get("email"):
            try:
                db.patients.update_one({"id": patient_id}, {"$set": {"email": email}})
            except DuplicateKeyError:
                effective_email = None

    db.slots.update_one({"id": slot_id}, {"$set": {"is_booked": True}})
    appointment_id = next_id("appointments")
    db.appointments.insert_one(
        {
            "id": appointment_id,
            "slot_id": slot_id,
            "patient_id": patient_id,
            "reason": reason,
            "status": "booked",
            "reminder_sent": False,
        }
    )

    doctor = db.doctors.find_one({"id": doctor_id})
    slot = db.slots.find_one({"id": slot_id})

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
    db = get_db()
    patient = _find_patient(db, phone, email)

    if not patient:
        # Distinguished from "found but nothing upcoming" below — the LLM needs
        # to react differently to each case (e.g. ask the patient to double-check
        # the number, vs. tell them they have no appointments booked).
        return {"patient_found": False, "appointments": []}

    # No JOIN in MongoDB — a demo's worth of appointments per patient is tiny,
    # so a straightforward per-appointment lookup of its slot/doctor is far
    # more readable than an aggregation $lookup pipeline for the same result.
    appointments = []
    for appt in db.appointments.find({"patient_id": patient["id"], "status": "booked"}):
        slot = db.slots.find_one({"id": appt["slot_id"]})
        doctor = db.doctors.find_one({"id": slot["doctor_id"]})
        appointments.append(
            {
                "appointment_id": appt["id"],
                "doctor_name": doctor["name"],
                "specialty": doctor["specialty"],
                "date": slot["date"],
                "time": slot["time"],
                "reason": appt.get("reason"),
            }
        )
    appointments.sort(key=lambda a: (a["date"], a["time"]))
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
    db = get_db()
    appointment = db.appointments.find_one({"id": appointment_id})

    if not appointment:
        return {"success": False, "message": "Appointment not found."}

    if appointment["status"] == "cancelled":
        return {"success": False, "message": "This appointment is already cancelled."}

    db.appointments.update_one({"id": appointment_id}, {"$set": {"status": "cancelled"}})
    db.slots.update_one({"id": appointment["slot_id"]}, {"$set": {"is_booked": False}})

    return {"success": True, "message": "Appointment cancelled successfully."}
