# Blackfriars GP Clinic Voice AI Receptionist 🩺📞

A production-ready, ultra-low latency voice receptionist agent for a GP Clinic (modeled on the real-world **Blackfriars Medical Practice** in London). 

Patients can call in, speak naturally, and manage their appointments (booking, rescheduling, cancellation, and conflict resolution) without any human receptionist involved.

---

## 🛠️ Stack & Design Choices (Justification)

This project uses **LiveKit Agents SDK** integrated with **Deepgram** (for STT/TTS) and **Groq** running `llama-3.3-70b-versatile` (for reasoning/LLM).

### Why this stack?
1. **LiveKit Agents Framework:** Unlike standard LLM chatbots with a sluggish voice layer slapped on top, LiveKit handles WebRTC audio streaming, Voice Activity Detection (VAD), and tool calling in a single unified pipeline. This allows immediate interruption handling and seamless conversation flow.
2. **Groq (Llama 3.3 70B):** Groq's LPU architecture delivers text completion with sub-200ms latency. In voice agents, every millisecond counts; Groq prevents awkward conversational pauses.
3. **Deepgram STT & TTS:** Deepgram Nova-2 is the fastest STT on the market, transcribing audio streams in real-time. Aura TTS provides human-like speech output with sub-300ms time-to-first-audio latency.
4. **SQLite Database Backend:** A local SQLite database is chosen for storage. It requires zero setup/external infrastructure, is file-based, supports ACID-compliant transactions, and lets tool calls query real structured slots.

---

## 📂 Project Structure

- `database.py`: Handles connection, schemas (doctors, slots, appointments), and transaction-safe operations.
- `seed_db.py`: Database initialization script. Seeds real Blackfriars GP doctors, specialties, and schedules relative to the current date.
- `agent.py`: LiveKit agent worker running the receptionist prompt, dynamic date injection, and clinical tools context.
- `config.py`: Centralized prompts, personalities, clinical guidelines, and service details.
- `eval_harness.py`: Automated local test pipeline that simulates 5 complex multi-turn receptionist scenarios and evaluates performance.
- `make_call.py` / `setup_trunk.py`: Outbound telephony scripts.

---

## 🗄️ Database Schema & Real Data

We use real data from **Blackfriars Medical Practice** (Colombo St, London):
* **Doctors:** Sourced 8 real GPs (Dr. Ami Kanabar, Dr. Bethan Jones, Dr. Alexander Warwick-Smith, etc.) and mapped them to their real specialties.
* **Slots:** Seeding creates standard **15-minute slots** for the next 7 days (excluding Sundays).
* **Relative Seeding:** To ensure the database always remains active, slots are generated relative to the execution day (e.g. `today + 1`, `today + 2`).
* **Conflict Simulation:** Dr. Ami Kanabar's Monday morning 10:30 AM slot is pre-booked by default to test conflict resolution and alternative proposals.

---

## ⚡ The Latency Story (Performance Metrics)

Conversational speech requires a turnaround latency of **under 1.0 second** to feel natural. 

### Latency Breakdown (Voice-to-Voice)
* **Speech-to-Text (Deepgram Nova-2):** ~150ms – 250ms (from silence detection to final transcript)
* **LLM Reasoning (Groq Llama 3.3):** ~150ms – 250ms (from prompt processing to first token)
* **Text-to-Speech (Deepgram Aura):** ~250ms – 350ms (time-to-first-audio chunk)
* **Network & WebRTC Streaming:** ~50ms – 100ms
* **Total Turnaround Time (Voice-to-Voice):** **~600ms – 950ms**

If Groq is unavailable, the agent falls back to OpenAI `gpt-4o-mini`, which increases the LLM turn to ~400ms – 600ms, resulting in an overall latency of **~1.1s – 1.3s**.

---

## 🧪 Automated Evaluation Harness (`eval_harness.py`)

To ensure the agent behaves correctly under real-world messiness, we built an automated, repeatable evaluation pipeline.

### Test Scenarios
1. **Standard Booking:** Patient books a general slot successfully.
2. **Conflict Resolution:** Patient requests a pre-booked slot. The agent detects the block, offers alternatives, and books a correct alternative slot.
3. **Rescheduling:** Patient calls to look up their booking by phone number and reschedules it to a future slot.
4. **Cancellation:** Patient looks up their booking and cancels it, releasing the slot.
5. **Change of Mind:** Patient starts booking with Dr. Robin for a rash, then changes to Dr. Jones (Pediatrics) for their child mid-conversation.

### How to Run the Evaluation Harness
1. Ensure your virtual environment is active:
   ```powershell
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
2. Run the seed script:
   ```powershell
   python seed_db.py
   ```
3. Run the evaluation harness:
   ```powershell
   python eval_harness.py
   ```
*This will output a turn-by-turn log, database assertions, average turn latency, and output a detailed Markdown report at `eval_report.md`.*

---

## 🏃‍♂️ Telephony & Voice Agent Usage

1. **Activate Environment & Run Worker:**
   ```powershell
   python agent.py dev
   ```
2. **Initiate an Outbound Call:**
   In a separate terminal, run:
   ```powershell
   python make_call.py --to +91XXXXXXXXXX
   ```

---

## ⚠️ Known Limitations
* **Timezone Shifts:** The SQLite database stores dates in ISO8601 strings. Standard conversion matches local machine times.
* **Name Spelling:** If a caller speaks a doctor's name that is transcribed with a highly non-standard spelling (e.g., "Amy" instead of "Ami"), the string matching falls back to asking for clarification.
* **In-Room Concurrency:** SQLite file locking might block writes if multiple agents attempt to write to the database at the exact same millisecond. (In a larger scale deployment, this would be replaced with PostgreSQL).
Run this command to start the agent:

powershell
..\venv\Scripts\python.exe agent.py dev

Step 2: Start the Live Agent Worker
In your first terminal, run:

powershell
cd c:\Users\Asus\Downloads\LIvekitAIVoice-main\LIvekitAIVoice-main
..\venv\Scripts\python.exe agent.py dev

 Trigger the Call to Your Phone
Open a second terminal and trigger the call (replace +91XXXXXXXXXX with your actual phone number, including country code):

powershell
cd c:\Users\Asus\Downloads\LIvekitAIVoice-main\LIvekitAIVoice-main
..\venv\Scripts\python.exe make_call.py --to +91XXXXXXXXXX