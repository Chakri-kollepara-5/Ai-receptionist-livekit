# Rapid X AI - Outbound Voice Agent Workflow & Architecture

This document provides a comprehensive overview of the Outbound AI Voice Agent. It explains the entire workflow, the technologies used, and serves as a guide to explain the system architecture to others.

---

## 1. System Overview

The system is a real-time, conversational AI voice agent capable of making **outbound phone calls** to physical mobile phones or landlines. When the call connects, the AI acts as a human-like receptionist capable of answering questions, handling interruptions, and responding with ultra-low latency.

### The Tech Stack (Tools Used)
* **LiveKit:** The core WebRTC infrastructure and Agent Framework. It manages the audio rooms, handles the streaming, and dispatches tasks to our Python worker.
* **Groq (Llama 3.3 70B):** The "Brain" (LLM). We use Groq because its LPU architecture provides incredibly fast text generation, which is crucial for natural voice conversations without awkward pauses.
* **Deepgram:** Handles both **Speech-to-Text (STT)** and **Text-to-Speech (TTS)**. Deepgram translates the user's spoken audio into text for Groq, and translates Groq's text responses back into human-sounding audio.
* **Twilio (or Vobiz):** The **SIP Provider (Telephony)**. This acts as the bridge between the internet (LiveKit) and the traditional phone network (PSTN). It dials the physical phone numbers.
* **Python (`asyncio`):** The language running our local agent worker, allowing it to handle multiple concurrent asynchronous streams (audio in, audio out, LLM processing).

---

## 2. Step-by-Step Workflow (How a Call Happens)

When you explain this to someone else, use this 5-step sequence to describe exactly what happens when you hit "Enter":

### Step 1: The Trigger (`make_call.py`)
You run `make_call.py --to +91XXXXXXXXXX`. This script sends an API request to the LiveKit Cloud saying: *"Create a new virtual room and dispatch the outbound-caller agent to it. Tell the agent to call this phone number."*

### Step 2: The Worker Wakes Up (`agent.py`)
Your local terminal running `agent.py` is constantly listening to LiveKit. It receives the dispatch request, accepts the job, and joins the virtual LiveKit room.

### Step 3: The SIP Connection
Inside `agent.py`, the AI uses the **SIP Trunk ID** (configured in `.env`) to ask LiveKit to bring a SIP Participant into the room. LiveKit securely connects to **Twilio**, and Twilio dials the physical phone number over the traditional cell network. 

### Step 4: The Conversation Loop
The person picks up their phone and says "Hello?".
1. **Listen:** The audio travels from their phone -> Twilio -> LiveKit -> Deepgram (STT).
2. **Think:** Deepgram converts it to text ("Hello?") and sends it to Groq (LLM). Groq processes the system prompt and generates a response ("Hi! I am the Rapid X Receptionist...").
3. **Speak:** Groq's text is streamed to Deepgram (TTS), which generates human-like audio and sends it back through LiveKit to the user's ear.

### Step 5: Disconnect
The agent actively listens for the user to say "Goodbye" or hang up. Once the SIP connection drops, the LiveKit room closes, and the Python worker goes back to sleep waiting for the next dispatch.

---

## 3. How to Set This Up (For a New Developer)

If you hand this code off to another developer, here is the exact process they must follow:

### A. Environment Setup
1. Create a Python Virtual Environment: `python -m venv venv`
2. Activate it: `.\venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`

### B. API Keys & Configuration
The system requires API keys for all the tools mentioned above. Create a `.env` file in the root directory:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_key
LIVEKIT_API_SECRET=your_secret
DEEPGRAM_API_KEY=your_key
GROQ_API_KEY=your_key
```

### C. SIP Trunking Setup
To make real phone calls, a SIP Trunk must be configured.
1. Create a SIP Trunk in Twilio (Elastic SIP Trunking).
2. Get the **SIP URI**, **Username**, and **Password**.
3. Put them into the `.env` file under `VOBIZ_SIP_DOMAIN`, `VOBIZ_USERNAME`, and `VOBIZ_PASSWORD`.
4. Run `python create_trunk.py`. This script securely links the LiveKit Cloud to the Twilio SIP Trunk.
5. Copy the generated `ST_XXXXXXXX` Trunk ID and put it into the `.env` file (`VOBIZ_SIP_TRUNK_ID`).

### D. Running the System
You need **two** terminal windows open:
1. **Terminal 1 (The Worker):** Run `python agent.py dev`. This must stay running. It connects to LiveKit and waits for jobs.
2. **Terminal 2 (The Trigger):** Run `python make_call.py --to +1234567890`. This dispatches the actual call.

---

## 4. Important Gotchas & Troubleshooting

When explaining this to clients or other developers, mention these common pitfalls:

* **Telecom Spam Filters (The +1 Issue):** If you use a US Twilio Trial number (`+1`) to call an Indian mobile number (`+91`), Indian telecom carriers (Jio, Airtel) will often block the call silently to prevent spam. Twilio will say "Completed", but the phone will never ring. **Solution:** You must purchase a local `+91` Virtual Number in Twilio.
* **SIP Passwords are Case Sensitive:** A wrong uppercase letter in the SIP password will cause a `403 Forbidden` error. If you change the password in `.env`, you **must** run `python setup_trunk.py` again to sync it to the cloud.
* **Cached Environment Variables:** If you update the `.env` file, you must completely stop (`Ctrl + C`) and restart `agent.py dev` so it loads the new keys into memory.
* **Twilio Trial Restrictions:** On a free Twilio trial, you can ONLY make outbound calls to phone numbers that you have explicitly verified in your Twilio dashboard. Calling an unverified number will fail instantly.
