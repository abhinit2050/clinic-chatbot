from database import get_connection
from faker import Faker
import random
from datetime import date, timedelta

fake = Faker()

def seed_doctors(cursor):
    doctors = [
         ("Dr. Ramesh Sharma", "Cardiology"),
        ("Dr. Priya Mehta", "Dermatology"),
        ("Dr. Anil Kapoor", "Orthopedics"),
        ("Dr. Sunita Rao", "Neurology"),
        ("Dr. Vikram Nair", "General Physician"),
    ]
    
    cursor.executemany(""" 
        INSERT INTO doctors (name, specialty) VALUES (?,?)
     """, doctors)

def seed_slots(cursor):
    
    cursor.execute("SELECT id FROM doctors")
    doctors = cursor.fetchall()

    times = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    start_date = date.today()

    for doctor in doctors:
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            for time in times:
                is_booked = random.choice([0, 0, 0, 1])
                cursor.execute("""
                    INSERT INTO slots (doctor_id, date, time, is_booked)
                    VALUES (?, ?, ?, ?)
                """, (doctor["id"], str(current_date), time, is_booked))

def seed_patients(cursor):
    for _ in range(10):
        name = fake.name()
        phone = fake.phone_number()
        cursor.execute("""
            INSERT INTO patients (name, phone) VALUES (?, ?)
        """, (name, phone))

def seed():
    conn = get_connection()
    cursor = conn.cursor()

    seed_doctors(cursor)
    seed_slots(cursor)
    seed_patients(cursor)

    conn.commit()
    conn.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    seed()