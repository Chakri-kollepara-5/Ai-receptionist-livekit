import datetime
from database import init_db, get_db_connection, book_appointment

DOCTORS = [
    {"name": "Dr. Ami Kanabar", "gender": "Female", "specialty": "Women's Health, Family Medicine", "qualifications": "MBChB, DFSRH, MRCP, MRCGP"},
    {"name": "Dr. Bethan Jones", "gender": "Female", "specialty": "Pediatrics, Family Medicine", "qualifications": "MBBS, BSc, MRCGP, DFSRH"},
    {"name": "Dr. Alexander Warwick-Smith", "gender": "Male", "specialty": "Cardiovascular Health, Family Medicine", "qualifications": "BA, MSc, MBBS, MRCGP"},
    {"name": "Dr. Nolwenn Robin", "gender": "Female", "specialty": "Dermatology, Family Medicine", "qualifications": "MD"},
    {"name": "Dr. Lily Topham", "gender": "Female", "specialty": "Mental Health, Family Medicine", "qualifications": "MBBS, BSc, MRCGP"},
    {"name": "Dr. Ana-Marie Gafita", "gender": "Female", "specialty": "Diabetes & Endocrinology, Family Medicine", "qualifications": "MD, MRCGP"},
    {"name": "Dr. Isabel Sousa", "gender": "Female", "specialty": "Elderly Care, Family Medicine", "qualifications": "MD"},
    {"name": "Dr. Jasmine Nagpal", "gender": "Female", "specialty": "Reproductive Health & Gynecology, Family Medicine", "qualifications": "MBBS, iBSc Psychology, DFSRH, DRCOG, MRCGP"}
]

def seed_database():
    print("Initializing database...")
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear existing data to make it idempotent
    cursor.execute("DELETE FROM appointments")
    cursor.execute("DELETE FROM slots")
    cursor.execute("DELETE FROM doctors")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('doctors', 'slots', 'appointments')")
    
    print("Seeding doctors...")
    doctor_ids = []
    for doc in DOCTORS:
        cursor.execute("""
            INSERT INTO doctors (name, gender, specialty, qualifications)
            VALUES (?, ?, ?, ?)
        """, (doc["name"], doc["gender"], doc["specialty"], doc["qualifications"]))
        doctor_ids.append(cursor.lastrowid)
    
    print(f"Successfully seeded {len(doctor_ids)} doctors.")
    
    # Seed slots for the next 7 days (including today)
    print("Seeding available slots for the next 7 days...")
    today = datetime.date.today()
    slots_inserted = 0
    
    # We will seed slots for each doctor
    # Standard times: 09:30-09:45, 10:30-10:45, 14:30-14:45
    slot_times = [
        ("09:30:00", "09:45:00"),
        ("10:30:00", "10:45:00"),
        ("14:30:00", "14:45:00")
    ]
    
    for i in range(7):
        current_date = today + datetime.timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Don't seed Sunday slots (Sunday is usually closed, except for emergencies, to make it realistic)
        if current_date.weekday() == 6: # 6 is Sunday
            continue
            
        for doc_id in doctor_ids:
            for start_t, end_t in slot_times:
                start_datetime = f"{date_str}T{start_t}"
                end_datetime = f"{date_str}T{end_t}"
                
                cursor.execute("""
                    INSERT INTO slots (doctor_id, start_time, end_time, is_booked)
                    VALUES (?, ?, ?, 0)
                """, (doc_id, start_datetime, end_datetime))
                slots_inserted += 1
                
    conn.commit()
    print(f"Successfully seeded {slots_inserted} slots.")
    
    # Pre-book specific slots to test conflict resolution
    # Let's pre-book Dr. Ami Kanabar's 10:30 slot for Day 3 (Monday if today is Friday)
    # Dr. Ami Kanabar is doctor_id = 1
    day_3_date = today + datetime.timedelta(days=3)
    day_3_str = day_3_date.strftime("%Y-%m-%d")
    
    cursor.execute("""
        SELECT id FROM slots 
        WHERE doctor_id = 1 AND start_time = ?
    """, (f"{day_3_str}T10:30:00",))
    
    slot_row = cursor.fetchone()
    if slot_row:
        slot_id = slot_row["id"]
        # Use book_appointment to book it under a fake name/phone
        book_appointment(
            patient_name="John Doe", 
            patient_phone="+447700900077", 
            slot_id=slot_id, 
            appointment_type="Routine Checkup"
        )
        print(f"Pre-booked Dr. Ami Kanabar's slot (ID: {slot_id}) at {day_3_str} 10:30 AM to simulate a scheduling conflict.")
        
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    seed_database()
