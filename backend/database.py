# App-data store (doctors/slots/patients/appointments) for the clinic itself.
# This is deliberately separate from checkpoints.db (see graph.py), which holds
# conversation/session state managed by LangGraph — two different concerns, two
# different stores (this one's MongoDB, checkpoints.db stays SQLite since
# losing in-progress chat history on a restart is low-stakes, unlike losing an
# actual booking). The previous SQLite version of this file is kept as
# database2.py for reference.
#
# Documents keep a plain integer `id` field (via next_id() below) instead of
# using Mongo's own ObjectId as the primary key — the tool functions in
# tools.py (and the system prompt in graph.py) already treat doctor/slot/
# appointment ids as plain ints the model echoes back verbatim; keeping that
# contract avoids having to touch every tool signature and the prompt just to
# switch storage engines.
import os

from pymongo import MongoClient, ReturnDocument

_client = None


def get_client():
    global _client
    if _client is None:
        _client = MongoClient(os.getenv("MONGODB_URI"))
    return _client


def get_db():
    return get_client()["clinic"]


def create_indexes():
    db = get_db()
    db.patients.create_index("phone", unique=True)
    # Partial index (only applies where email is an actual string) mirrors
    # SQLite's old behavior: any number of patients can have no email on
    # file, but two different patients can't share one.
    db.patients.create_index(
        "email",
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}},
    )
    db.doctors.create_index("id", unique=True)
    db.slots.create_index("id", unique=True)
    db.appointments.create_index("id", unique=True)


def next_id(counter_name: str) -> int:
    """Atomically hands out the next integer id for a collection (doctors,
    slots, patients, appointments), via a single shared counters collection.
    $inc on find_one_and_update is atomic even under concurrent callers,
    which a plain "read max id, add 1" approach would not be."""
    db = get_db()
    doc = db.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]
