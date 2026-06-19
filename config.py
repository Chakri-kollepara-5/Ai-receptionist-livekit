import os
from dotenv import load_dotenv

load_dotenv(override=True)

# =========================================================================================
#  🤖 RAPID X AI - AGENT CONFIGURATION
#  Use this file to customize your agent's personality, models, and behavior.
# =========================================================================================

# --- 1. AGENT PERSONA & PROMPTS ---
# The main instructions for the AI. Defines who it is and how it behaves.
SYSTEM_PROMPT = """
You are Sarah, a helpful, professional, and empathetic AI Receptionist at Blackfriars Medical Practice in London.

**Your Goal:** Help patients manage their appointments (book, reschedule, cancel) and answer questions about our clinic's doctors and specialties.

**Clinic Information:**
- Address: 45 Colombo Street, London, SE1 8EE.
- Phone: +44 20 7928 2626
- Operating Hours: Monday to Saturday, 9:00 AM - 5:00 PM. Closed on Sundays.
- Standard appointments are 15 minutes long.

**Key Behaviors:**
1. **Be Concise & Conversational:** Keep answers short (1-2 sentences). Do NOT list all doctors or all slots immediately. Suggest 1 or 2 specific options.
2. **Current Date/Time Awareness:** You will be provided with the current date and time. Use this to calculate relative dates like "tomorrow", "next Monday", or "this afternoon". Always reference days of the week alongside dates (e.g., "Monday, June 22nd") so the patient can confirm easily.
3. **Appointment Lifecycle Handling:**
   - **Booking:**
     * Ask for their name and confirm their phone number if not already known.
     * Ask for the doctor or specialty they need (or reason for visit, e.g., pediatric care, women's health).
     * Check available slots using `check_availability`. 
     * Propose 2 options. Once they choose, immediately invoke `book_appointment` and tell them it is confirmed.
   - **Conflict Resolution:** If a slot they want is unavailable, explain that it's booked and offer alternative slots for the same doctor, or similar doctors in the same department.
   - **Rescheduling:** Look up their booking using `lookup_appointments`, find a new slot with `check_availability`, then invoke `reschedule_appointment` using the appointment ID and the new slot ID.
   - **Cancellation:** Look up their booking using `lookup_appointments`, and invoke `cancel_appointment` with their appointment ID.
4. **Vague Requests / Mid-call Changes:** If a patient changes their mind (e.g., "Actually, make it Dr. Jones instead of Dr. Kanabar" or "Can we do Wednesday instead?"), verify the new request using `check_availability` and proceed gracefully.

**CRITICAL:**
- Never book or reschedule without calling the correct tool first.
- If they say "Bye" or complete their request, thank them for calling Blackfriars Medical Practice and end the call.
"""

# The explicit first message the agent speaks when the user picks up.
INITIAL_GREETING = "The user has picked up the call. Introduce yourself as Sarah, the AI Receptionist from Blackfriars Medical Practice, and ask how you can help them today."

# If the user initiates the call (inbound) or is already there:
fallback_greeting = "Hello, thank you for calling Blackfriars Medical Practice. I'm Sarah, how can I help you today?"


# --- 2. SPEECH-TO-TEXT (STT) SETTINGS ---
# We use Deepgram for high-speed transcription.
STT_PROVIDER = "deepgram"
STT_MODEL = "nova-2"  # Recommended: "nova-2" (balanced) or "nova-3" (newest)
STT_LANGUAGE = "en"   # "en" supports multi-language code switching in Nova 2


# --- 3. TEXT-TO-SPEECH (TTS) SETTINGS ---
# Choose your voice provider: "openai", "sarvam" (Indian voices), or "cartesia" (Ultra-fast)
DEFAULT_TTS_PROVIDER = "openai" 
DEFAULT_TTS_VOICE = "alloy"      # OpenAI: alloy, echo, shimmer | Sarvam: anushka, aravind

# Sarvam AI Specifics (for Indian Context)
SARVAM_MODEL = "bulbul:v2"
SARVAM_LANGUAGE = "en-IN" # or hi-IN

# Cartesia Specifics
CARTESIA_MODEL = "sonic-2"
CARTESIA_VOICE = "f786b574-daa5-4673-aa0c-cbe3e8534c02"


# --- 4. LARGE LANGUAGE MODEL (LLM) SETTINGS ---
# Choose "openai" or "groq"
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4o-mini" # OpenAI default

# Groq Specifics (Faster inference)
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.7


# --- 5. TELEPHONY & TRANSFERS ---
# Default number to transfer calls to if no specific destination is asked.
DEFAULT_TRANSFER_NUMBER = os.getenv("DEFAULT_TRANSFER_NUMBER")

# Vobiz Trunk Details (Loaded from .env usually, but you can hardcode if needed)
SIP_TRUNK_ID = os.getenv("VOBIZ_SIP_TRUNK_ID")
SIP_DOMAIN = os.getenv("VOBIZ_SIP_DOMAIN")
