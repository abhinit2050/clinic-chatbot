from database import get_connection

def list_doctors():
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("SELECT * FROM doctors")
    doctors = cursor.fetchall()
    conn.close()
    return [{"id":row["id"],"name":row["name"],"specialty":row["specialty"]} for row in doctors]

def check_availability(doctor_id, date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, time from slots WHERE doctor_id=? AND date=? AND is_booked=0
    """,(doctor_id,date))

    slots = cursor.fetchall()
    conn.close()

    results=[]

    for row in slots:
        results.append({"slot_id":row["id"],"time":row["time"]})
    
    return results  

def book_appointment(name, phone, reason, doctor_id,date, slot_id):
    # check if patient exists and add if they don't
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * from patients WHERE phone=?",(phone,))
    patient = cursor.fetchone()

    if not patient:
        cursor.execute("INSERT INTO patients (name, phone) VALUES (?,?)",(name, phone))
        patient = {"id": cursor.lastrowid}
    cursor.execute("UPDATE slots SET is_booked=1 WHERE id=?",(slot_id,))

    #now insert into appointments table
    cursor.execute("INSERT INTO appointments (slot_id, patient_id, reason) VALUES (?,?,?)",(slot_id, patient["id"],reason))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Appointment booked successfully"}
