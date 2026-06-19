import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clinic.db")

def get_db_connection():
    """Create and return a database connection with dictionary cursor row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database with doctors, slots, and appointments tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Doctors table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        gender TEXT NOT NULL,
        specialty TEXT NOT NULL,
        qualifications TEXT NOT NULL
    );
    """)
    
    # Create Slots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER NOT NULL,
        start_time TEXT NOT NULL, -- Format: ISO8601 YYYY-MM-DDTHH:MM:SS
        end_time TEXT NOT NULL,   -- Format: ISO8601 YYYY-MM-DDTHH:MM:SS
        is_booked INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    );
    """)
    
    # Create Appointments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        patient_phone TEXT NOT NULL,
        slot_id INTEGER NOT NULL,
        appointment_type TEXT NOT NULL, -- e.g., Consultation, Follow-up, Check-up
        status TEXT NOT NULL DEFAULT 'booked', -- booked, rescheduled, cancelled
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(slot_id) REFERENCES slots(id)
    );
    """)
    
    conn.commit()
    conn.close()

def get_doctors_by_specialty(specialty=None):
    """Retrieve all doctors, optionally filtered by specialty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if specialty:
        cursor.execute("SELECT * FROM doctors WHERE specialty LIKE ?", (f"%{specialty}%",))
    else:
        cursor.execute("SELECT * FROM doctors")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_available_slots(doctor_id=None, date_str=None):
    """
    Retrieve all available (unbooked) slots.
    Optionally filter by doctor_id and/or date (YYYY-MM-DD).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT slots.id, slots.doctor_id, doctors.name as doctor_name, doctors.specialty, slots.start_time, slots.end_time 
        FROM slots 
        JOIN doctors ON slots.doctor_id = doctors.id 
        WHERE slots.is_booked = 0
    """
    params = []
    
    if doctor_id:
        query += " AND slots.doctor_id = ?"
        params.append(doctor_id)
        
    if date_str:
        # Match the date prefix (e.g. '2026-06-20%')
        query += " AND slots.start_time LIKE ?"
        params.append(f"{date_str}%")
        
    query += " ORDER BY slots.start_time ASC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def book_appointment(patient_name, patient_phone, slot_id, appointment_type="Consultation"):
    """
    Book an appointment for a specific slot.
    Checks for slot availability, books it, and logs the appointment in a transaction.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if slot exists and is available
        cursor.execute("SELECT is_booked, start_time FROM slots WHERE id = ?", (slot_id,))
        slot = cursor.fetchone()
        if not slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}
        if slot["is_booked"] == 1:
            return {"success": False, "message": "Slot is already booked."}
            
        # Update slot to booked
        cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?", (slot_id,))
        
        # Create appointment
        cursor.execute("""
            INSERT INTO appointments (patient_name, patient_phone, slot_id, appointment_type, status)
            VALUES (?, ?, ?, ?, 'booked')
        """, (patient_name, patient_phone, slot_id, appointment_type))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        return {
            "success": True, 
            "appointment_id": appointment_id, 
            "message": f"Appointment successfully booked for {slot['start_time']}."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        conn.close()

def get_appointments_by_phone(patient_phone):
    """Get active/historical appointments for a specific phone number."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT appointments.id as appointment_id, appointments.patient_name, appointments.patient_phone, 
               appointments.appointment_type, appointments.status, slots.id as slot_id, slots.start_time,
               doctors.name as doctor_name, doctors.specialty
        FROM appointments
        JOIN slots ON appointments.slot_id = slots.id
        JOIN doctors ON slots.doctor_id = doctors.id
        WHERE appointments.patient_phone = ?
        ORDER BY slots.start_time DESC
    """, (patient_phone,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def reschedule_appointment(appointment_id, new_slot_id):
    """
    Reschedule an existing appointment.
    In a single transaction:
    1. Releases the old slot associated with the appointment.
    2. Checks and books the new slot.
    3. Updates the appointment's slot_id and changes status to 'rescheduled'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch current appointment details
        cursor.execute("SELECT slot_id, status FROM appointments WHERE id = ?", (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            return {"success": False, "message": f"Appointment ID {appointment_id} not found."}
            
        if appointment["status"] == "cancelled":
            return {"success": False, "message": "Cannot reschedule a cancelled appointment."}
            
        old_slot_id = appointment["slot_id"]
        
        # Verify new slot is available
        cursor.execute("SELECT is_booked, start_time FROM slots WHERE id = ?", (new_slot_id,))
        new_slot = cursor.fetchone()
        if not new_slot:
            return {"success": False, "message": f"New Slot ID {new_slot_id} not found."}
        if new_slot["is_booked"] == 1:
            return {"success": False, "message": "The requested new slot is already booked."}
            
        # Release old slot
        cursor.execute("UPDATE slots SET is_booked = 0 WHERE id = ?", (old_slot_id,))
        
        # Book new slot
        cursor.execute("UPDATE slots SET is_booked = 1 WHERE id = ?", (new_slot_id,))
        
        # Update appointment record
        cursor.execute("""
            UPDATE appointments 
            SET slot_id = ?, status = 'rescheduled' 
            WHERE id = ?
        """, (new_slot_id, appointment_id))
        
        conn.commit()
        return {
            "success": True, 
            "message": f"Appointment successfully rescheduled to {new_slot['start_time']}."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        conn.close()

def cancel_appointment(appointment_id):
    """
    Cancel an appointment.
    Frees the slot and updates the appointment status to 'cancelled'.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT slot_id, status FROM appointments WHERE id = ?", (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            return {"success": False, "message": f"Appointment ID {appointment_id} not found."}
            
        if appointment["status"] == "cancelled":
            return {"success": False, "message": "Appointment is already cancelled."}
            
        slot_id = appointment["slot_id"]
        
        # Release slot
        cursor.execute("UPDATE slots SET is_booked = 0 WHERE id = ?", (slot_id,))
        
        # Update appointment status
        cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
        
        conn.commit()
        return {"success": True, "message": "Appointment successfully cancelled."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        conn.close()
