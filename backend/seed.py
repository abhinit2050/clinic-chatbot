from database import get_db, next_id
from faker import Faker
import random
from datetime import date, timedelta

fake = Faker()

def seed_doctors(db):
    doctors = [
         ("Dr. Ramesh Sharma", "Cardiology"),
        ("Dr. Priya Mehta", "Dermatology"),
        ("Dr. Anil Kapoor", "Orthopedics"),
        ("Dr. Sunita Rao", "Neurology"),
        ("Dr. Vikram Nair", "General Physician"),
    ]

    db.doctors.insert_many(
        [{"id": next_id("doctors"), "name": name, "specialty": specialty} for name, specialty in doctors]
    )

def seed_slots(db):
    doctors = list(db.doctors.find())

    times = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    start_date = date.today()

    slots = []
    for doctor in doctors:
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            for time in times:
                is_booked = random.choice([False, False, False, True])
                slots.append({
                    "id": next_id("slots"),
                    "doctor_id": doctor["id"],
                    "date": str(current_date),
                    "time": time,
                    "is_booked": is_booked,
                })
    db.slots.insert_many(slots)

def seed_patients(db):
    patients = []
    for _ in range(10):
        patients.append({
            "id": next_id("patients"),
            "name": fake.name(),
            "phone": fake.phone_number(),
            "email": fake.email(),
        })
    db.patients.insert_many(patients)

def seed():
    db = get_db()

    seed_doctors(db)
    seed_slots(db)
    seed_patients(db)

    print("Database seeded successfully!")

if __name__ == "__main__":
    seed()
