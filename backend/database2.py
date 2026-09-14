# App-data schema (doctors/slots/patients/appointments) for the clinic itself.
# This is deliberately separate from checkpoints.db (see graph.py), which holds
# conversation/session state managed by LangGraph — two different concerns, two DBs.
#
# Schema changes here use plain `ALTER`/`CREATE IF NOT EXISTS`, not a migration
# framework (e.g. Alembic). That's a fine tradeoff for a demo project where
# clinic.db is throwaway, reseedable data (see seed.py) with no real patients —
# in a real production system you'd want versioned migrations instead of relying
# on "just delete the DB and recreate it".
import sqlite3

DB_PATH = "clinic.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            is_booked INTEGER DEFAULT 0,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE
        )
    """)
    # Note: SQLite treats every NULL as distinct from every other NULL, even
    # under UNIQUE — so any number of patients can still have no email on
    # file. The constraint only fires if two *different* patients (different
    # phone numbers) end up with the same non-null email. See tools.py's
    # book_appointment for how that collision is handled gracefully.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'booked',
            reminder_sent INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (slot_id) REFERENCES slots(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    print("Tables created successfully!")
