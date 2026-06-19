import os
import time
import json
import sqlite3
import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Load env variables
load_dotenv(override=True)

# Import project files
import database
import config
from seed_db import seed_database

# Setup API Key & Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
if LLM_PROVIDER == "groq" and os.getenv("GROQ_API_KEY"):
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY")
    )
    MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
else:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    MODEL = "gpt-4o-mini"

print(f"Eval Harness initialized with Provider: {LLM_PROVIDER.upper()}, Model: {MODEL}")

# --- Tool Schemas for LLM ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_specialties_and_doctors",
            "description": "List all clinical specialties/departments and matching doctors available at Blackfriars Medical Practice."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check available appointment slots for a specific doctor and/or specific date. Date format must be YYYY-MM-DD. Doctor name can be partial (e.g. 'Kanabar' or 'Ami').",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {"type": "string", "description": "The name of the doctor (optional)"},
                    "date": {"type": "string", "description": "The date in YYYY-MM-DD format (optional)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment. Patient name, phone number, and slot ID are required. Optional appointment type like 'Consultation' or 'Follow-up'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "The patient's full name"},
                    "patient_phone": {"type": "string", "description": "The patient's phone number"},
                    "slot_id": {"type": "integer", "description": "The ID of the chosen slot"},
                    "appointment_type": {"type": "string", "description": "Type of appointment, e.g., Consultation, Follow-up"}
                },
                "required": ["patient_name", "patient_phone", "slot_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_appointments",
            "description": "Look up existing appointments for a patient using their phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_phone": {"type": "string", "description": "The patient's phone number"}
                },
                "required": ["patient_phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment. Requires the existing appointment ID and a new available slot ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "The ID of the existing appointment"},
                    "new_slot_id": {"type": "integer", "description": "The ID of the new slot to book"}
                },
                "required": ["appointment_id", "new_slot_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Requires the appointment ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "The ID of the appointment to cancel"}
                },
                "required": ["appointment_id"]
            }
        }
    }
]

# --- Helper to resolve doctor names ---
def find_doctor_id(doctor_name: str):
    if not doctor_name:
        return None
    clean_name = doctor_name.lower().replace("dr.", "").replace("dr", "").strip()
    doctors = database.get_doctors_by_specialty()
    for doc in doctors:
        if clean_name in doc["name"].lower():
            return doc["id"]
    return None

# --- Local Tool Executor ---
def execute_tool(name, arguments):
    print(f"   [Tool Call] {name}({arguments})")
    try:
        if name == "list_specialties_and_doctors":
            doctors = database.get_doctors_by_specialty()
            if not doctors:
                return "No doctors registered in the clinic system."
            result = "Specialties and Doctors at Blackfriars Medical Practice:\n"
            for doc in doctors:
                result += f"- {doc['name']} ({doc['gender']}), Specialty: {doc['specialty']}, Qualifications: {doc['qualifications']}\n"
            return result
            
        elif name == "check_availability":
            doc_name = arguments.get("doctor_name")
            date_val = arguments.get("date")
            doc_id = None
            if doc_name:
                doc_id = find_doctor_id(doc_name)
                if not doc_id:
                    return f"Could not find a doctor matching the name '{doc_name}'."
            slots = database.get_available_slots(doctor_id=doc_id, date_str=date_val)
            if not slots:
                return "No available slots found."
            result = "Available Slots:\n"
            for slot in slots[:6]:
                dt = datetime.datetime.fromisoformat(slot["start_time"])
                formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                result += f"- Slot ID {slot['id']}: {formatted_time} with {slot['doctor_name']} ({slot['specialty']})\n"
            return result
            
        elif name == "book_appointment":
            patient_name = arguments.get("patient_name")
            patient_phone = arguments.get("patient_phone")
            slot_id = arguments.get("slot_id")
            app_type = arguments.get("appointment_type", "Consultation")
            res = database.book_appointment(patient_name, patient_phone, slot_id, app_type)
            return res["message"]
            
        elif name == "lookup_appointments":
            phone = arguments.get("patient_phone")
            appointments = database.get_appointments_by_phone(phone)
            active = [a for a in appointments if a["status"] in ["booked", "rescheduled"]]
            if not active:
                return f"No active appointments found for phone number {phone}."
            result = "Found active appointments:\n"
            for app in active:
                dt = datetime.datetime.fromisoformat(app["start_time"])
                formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
                result += f"- Appointment ID {app['appointment_id']}: {app['appointment_type']} with {app['doctor_name']} on {formatted_time} (Status: {app['status']})\n"
            return result
            
        elif name == "reschedule_appointment":
            app_id = arguments.get("appointment_id")
            slot_id = arguments.get("new_slot_id")
            res = database.reschedule_appointment(app_id, slot_id)
            return res["message"]
            
        elif name == "cancel_appointment":
            app_id = arguments.get("appointment_id")
            res = database.cancel_appointment(app_id)
            return res["message"]
            
        return f"Error: Tool {name} not found."
    except Exception as e:
        return f"Error executing tool: {str(e)}"

# --- Conversation Runner ---
def run_conversation_simulation(scenario_name, user_turns):
    print(f"\n==================================================")
    print(f"RUNNING SCENARIO: {scenario_name}")
    print(f"==================================================")
    
    # Initialize messages list with system instructions
    now_str = datetime.datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
    system_instr = f"{config.SYSTEM_PROMPT}\n\n**IMPORTANT CURRENT CONTEXT:**\n- Today's date and time is: {now_str}.\n"
    
    messages = [
        {"role": "system", "content": system_instr}
    ]
    
    total_latency = 0.0
    turns_data = []
    
    for turn_idx, user_input in enumerate(user_turns):
        print(f"Patient: \"{user_input}\"")
        messages.append({"role": "user", "content": user_input})
        
        turn_start = time.time()
        
        # Call LLM loop to handle potential multiple tool executions
        while True:
            # Call completion API
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2
            )
            
            resp_msg = response.choices[0].message
            
            # If model requests tool calls
            if resp_msg.tool_calls:
                # Add assistant message containing the tool calls to history
                messages.append(resp_msg)
                
                # Execute tool calls and append results
                for tool_call in resp_msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_output = execute_tool(tool_name, tool_args)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": tool_output
                    })
                # Loop back to LLM to process tool outputs
                continue
            else:
                # LLM is ready with the final textual response
                turn_latency = time.time() - turn_start
                total_latency += turn_latency
                assistant_text = resp_msg.content or ""
                print(f"Sarah: \"{assistant_text}\" [Latency: {turn_latency:.2f}s]")
                messages.append({"role": "assistant", "content": assistant_text})
                turns_data.append({
                    "turn": turn_idx + 1,
                    "input": user_input,
                    "output": assistant_text,
                    "latency_sec": turn_latency
                })
                break
                
    avg_latency = total_latency / len(user_turns) if user_turns else 0.0
    print(f"\nScenario Completed. Total Latency: {total_latency:.2f}s, Avg Latency/Turn: {avg_latency:.2f}s")
    
    return {
        "scenario": scenario_name,
        "turns": turns_data,
        "total_latency": total_latency,
        "avg_latency": avg_latency
    }

# --- Main Evaluation Suites ---
def evaluate_agent():
    # Relative date calculations matching seed_db.py relative structure
    today = datetime.date.today()
    
    # Next Monday (weekday 0)
    days_to_monday = (0 - today.weekday()) % 7
    if days_to_monday == 0:
        days_to_monday = 7
    monday_date = today + datetime.timedelta(days=days_to_monday)
    monday_str = monday_date.strftime("%Y-%m-%d")
    monday_name = monday_date.strftime("%A, %B %d")
    
    # Next Tuesday (weekday 1)
    tuesday_date = monday_date + datetime.timedelta(days=1)
    tuesday_str = tuesday_date.strftime("%Y-%m-%d")
    tuesday_name = tuesday_date.strftime("%A, %B %d")
    
    # Next Wednesday (weekday 2)
    wednesday_date = monday_date + datetime.timedelta(days=2)
    wednesday_str = wednesday_date.strftime("%Y-%m-%d")
    wednesday_name = wednesday_date.strftime("%A, %B %d")

    # Next Thursday (weekday 3)
    thursday_date = monday_date + datetime.timedelta(days=3)
    thursday_str = thursday_date.strftime("%Y-%m-%d")
    thursday_name = thursday_date.strftime("%A, %B %d")

    results = []
    
    # =========================================================================
    # SUITE 1: Standard Booking
    # =========================================================================
    seed_database()
    suite1_turns = [
        "Hello, my name is Charles Babbage. I would like to book a general consultation with Dr. Alexander Warwick-Smith.",
        f"I want it for next Monday ({monday_name}) in the morning, please check if 10:30 AM is available.",
        "Yes, let's book that slot. My phone number is +447700900011."
    ]
    suite1_metrics = run_conversation_simulation("Standard Booking", suite1_turns)
    
    # Verify DB assertions
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.patient_name, a.patient_phone, a.status, s.start_time, d.name as doc_name
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        JOIN doctors d ON s.doctor_id = d.id
        WHERE a.patient_name = 'Charles Babbage' AND a.status = 'booked'
    """)
    charles_booking = cursor.fetchone()
    conn.close()
    
    s1_pass = (
        charles_booking is not None and 
        charles_booking["patient_phone"] == "+447700900011" and 
        f"{monday_str}T10:30:00" in charles_booking["start_time"] and
        charles_booking["doc_name"] == "Dr. Alexander Warwick-Smith"
    )
    suite1_metrics["passed"] = s1_pass
    print(f"SUITE 1 ASSERTION PASSED: {s1_pass}")
    results.append(suite1_metrics)

    # =========================================================================
    # SUITE 2: Slot Conflict Resolution
    # =========================================================================
    # Seed resets. Dr. Ami Kanabar's Monday 10:30 is pre-booked by John Doe in seed_db.py
    seed_database()
    suite2_turns = [
        "Hi, I'm Alice. Can I book a slot with Dr. Ami Kanabar next Monday at 10:30 AM?",
        "Ah, that slot is taken. Are there any other times available for Dr. Ami on that same Monday?",
        "Okay, let's book the 9:30 AM one instead. My phone number is +447700900022."
    ]
    suite2_metrics = run_conversation_simulation("Conflict Resolution", suite2_turns)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.patient_name, a.patient_phone, a.status, s.start_time, d.name as doc_name
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        JOIN doctors d ON s.doctor_id = d.id
        WHERE a.patient_name = 'Alice' AND a.status = 'booked'
    """)
    alice_booking = cursor.fetchone()
    conn.close()
    
    s2_pass = (
        alice_booking is not None and
        alice_booking["patient_phone"] == "+447700900022" and
        f"{monday_str}T09:30:00" in alice_booking["start_time"] and
        alice_booking["doc_name"] == "Dr. Ami Kanabar"
    )
    suite2_metrics["passed"] = s2_pass
    print(f"SUITE 2 ASSERTION PASSED: {s2_pass}")
    results.append(suite2_metrics)

    # =========================================================================
    # SUITE 3: Rescheduling Flow
    # =========================================================================
    seed_database()
    # Pre-book an appointment for Bob: Dr. Bethan Jones next Wednesday 10:30 AM
    conn = database.get_db_connection()
    cursor = conn.cursor()
    # Dr. Bethan Jones is id=2
    cursor.execute("SELECT id FROM slots WHERE doctor_id = 2 AND start_time = ?", (f"{wednesday_str}T10:30:00",))
    slot_row = cursor.fetchone()
    if slot_row:
        bob_slot_id = slot_row["id"]
        res = database.book_appointment("Bob", "+447700900088", bob_slot_id, "Routine Followup")
        bob_app_id = res["appointment_id"]
    conn.close()
    
    suite3_turns = [
        "Hi, I need to check my appointments. My phone is +447700900088.",
        f"I'd like to reschedule my appointment with Dr. Bethan Jones to next Thursday afternoon ({thursday_name}) at 2:30 PM."
    ]
    suite3_metrics = run_conversation_simulation("Rescheduling", suite3_turns)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_id, status FROM appointments WHERE id = ?", (bob_app_id,))
    bob_app = cursor.fetchone()
    
    # check new slot is indeed Wednesday slot released, Thursday slot booked
    cursor.execute("SELECT is_booked FROM slots WHERE id = ?", (bob_slot_id,))
    old_slot_state = cursor.fetchone()
    
    cursor.execute("SELECT is_booked, start_time FROM slots WHERE doctor_id = 2 AND start_time = ?", (f"{thursday_str}T14:30:00",))
    new_slot_state = cursor.fetchone()
    conn.close()
    
    s3_pass = (
        bob_app is not None and
        bob_app["status"] == "rescheduled" and
        old_slot_state["is_booked"] == 0 and # old slot freed
        new_slot_state["is_booked"] == 1 and # new slot booked
        f"{thursday_str}T14:30:00" in new_slot_state["start_time"]
    )
    suite3_metrics["passed"] = s3_pass
    print(f"SUITE 3 ASSERTION PASSED: {s3_pass}")
    results.append(suite3_metrics)

    # =========================================================================
    # SUITE 4: Cancellation Flow
    # =========================================================================
    seed_database()
    # Pre-book an appointment for Dave: Dr. Lily Topham Wednesday 10:30 AM
    conn = database.get_db_connection()
    cursor = conn.cursor()
    # Dr. Lily Topham is id=5
    cursor.execute("SELECT id FROM slots WHERE doctor_id = 5 AND start_time = ?", (f"{wednesday_str}T10:30:00",))
    slot_row = cursor.fetchone()
    if slot_row:
        dave_slot_id = slot_row["id"]
        res = database.book_appointment("Dave", "+447700900099", dave_slot_id, "Counseling Session")
        dave_app_id = res["appointment_id"]
    conn.close()
    
    suite4_turns = [
        "Hi, I need to cancel my appointment. My phone number is +447700900099.",
        "Yes, please cancel that appointment."
    ]
    suite4_metrics = run_conversation_simulation("Cancellation", suite4_turns)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM appointments WHERE id = ?", (dave_app_id,))
    dave_app = cursor.fetchone()
    cursor.execute("SELECT is_booked FROM slots WHERE id = ?", (dave_slot_id,))
    dave_slot = cursor.fetchone()
    conn.close()
    
    s4_pass = (
        dave_app is not None and
        dave_app["status"] == "cancelled" and
        dave_slot["is_booked"] == 0 # slot released
    )
    suite4_metrics["passed"] = s4_pass
    print(f"SUITE 4 ASSERTION PASSED: {s4_pass}")
    results.append(suite4_metrics)

    # =========================================================================
    # SUITE 5: Mid-Conversation Change of Mind
    # =========================================================================
    seed_database()
    suite5_turns = [
        f"Hi, my name is Emma. I'd like to book an appointment with Dr. Nolwenn Robin for my skin rash next Tuesday ({tuesday_name}) morning.",
        "Actually, can I see Dr. Bethan Jones instead on that Tuesday? My child needs a checkup, so Pediatrics would be better.",
        "Let's book the 10:30 AM slot. My phone is +447700900055."
    ]
    suite5_metrics = run_conversation_simulation("Change of Mind", suite5_turns)
    
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.patient_name, a.status, s.start_time, d.name as doc_name
        FROM appointments a
        JOIN slots s ON a.slot_id = s.id
        JOIN doctors d ON s.doctor_id = d.id
        WHERE a.patient_name = 'Emma' AND a.status = 'booked'
    """)
    emma_booking = cursor.fetchone()
    conn.close()
    
    s5_pass = (
        emma_booking is not None and
        f"{tuesday_str}T10:30:00" in emma_booking["start_time"] and
        emma_booking["doc_name"] == "Dr. Bethan Jones" # swapped from Nolwenn Robin to Bethan Jones
    )
    suite5_metrics["passed"] = s5_pass
    print(f"SUITE 5 ASSERTION PASSED: {s5_pass}")
    results.append(suite5_metrics)
    
    # Print Final Summary Report
    print_report(results)

def print_report(results):
    print("\n" + "="*80)
    print("                 BLACKFRIARS GP AI AGENT EVALUATION REPORT")
    print("="*80)
    print(f"{'Scenario Name':<30} | {'Status':<8} | {'Turns':<6} | {'Avg Turn Latency':<18}")
    print("-"*80)
    
    total_scenarios = len(results)
    passed_scenarios = 0
    total_latency_all = 0.0
    total_turns_all = 0
    
    for r in results:
        status_str = "PASSED" if r["passed"] else "FAILED"
        if r["passed"]:
            passed_scenarios += 1
        print(f"{r['scenario']:<30} | {status_str:<8} | {len(r['turns']):<6} | {r['avg_latency']:.2f}s")
        total_latency_all += r["total_latency"]
        total_turns_all += len(r["turns"])
        
    print("-"*80)
    print(f"Overall Success: {passed_scenarios}/{total_scenarios} ({passed_scenarios/total_scenarios*100:.1f}%)")
    if total_turns_all > 0:
        print(f"Overall Average Turn Latency: {total_latency_all/total_turns_all:.2f}s")
    print("="*80)

    # Write Markdown Report file
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_report.md")
    with open(report_path, "w") as f:
        f.write("# Blackfriars GP Voice AI Agent Evaluation Report\n\n")
        f.write(f"**Date run:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**LLM Provider:** {LLM_PROVIDER.upper()}\n")
        f.write(f"**LLM Model:** {MODEL}\n\n")
        
        f.write("## Executive Summary\n")
        f.write(f"- **Total Scenarios Run:** {total_scenarios}\n")
        f.write(f"- **Passed Scenarios:** {passed_scenarios}\n")
        f.write(f"- **Success Rate:** {passed_scenarios/total_scenarios*100:.1f}%\n")
        if total_turns_all > 0:
            f.write(f"- **Average Turn Latency:** {total_latency_all/total_turns_all:.2f} seconds\n\n")
            
        f.write("## Detailed Results\n\n")
        f.write("| Scenario Name | Status | Turns | Avg Turn Latency |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for r in results:
            status_str = "✅ PASSED" if r["passed"] else "❌ FAILED"
            f.write(f"| {r['scenario']} | {status_str} | {len(r['turns'])} | {r['avg_latency']:.2f}s |\n")
            
        f.write("\n## Scenario Walkthroughs\n\n")
        for r in results:
            f.write(f"### {r['scenario']}\n")
            f.write(f"- **Status:** {'✅ PASSED' if r['passed'] else '❌ FAILED'}\n")
            f.write(f"- **Avg Turn Latency:** {r['avg_latency']:.2f}s\n\n")
            f.write("#### Conversation Transcript\n")
            for t in r["turns"]:
                f.write(f"**Patient:** \"{t['input']}\"\n\n")
                f.write(f"**Sarah (Receptionist):** \"{t['output']}\" *(latency: {t['latency_sec']:.2f}s)*\n\n")
            f.write("---\n\n")

    print(f"Markdown report generated at: {report_path}")

if __name__ == "__main__":
    evaluate_agent()
