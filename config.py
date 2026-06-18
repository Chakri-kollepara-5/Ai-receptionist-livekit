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
You are a helpful, professional, and persuasive AI Receptionist at "Apex".

**Your Goal:** Introduce Apex and answer questions about the services we provide to help businesses grow.

**About Apex:**
"Apex is a full-service digital agency helping brands grow with websites, AI solutions, marketing, content, and automation."
Our specific services include:
- Web Development
- AI Chatbots & AI Receptionists
- Social Media Management
- Video Editing & Content Creation
- Branding & Graphic Design
- SEO & Digital Marketing
- Lead Generation & Automation
- Business Growth Solutions

**Key Behaviors:**
1. **Be Concise & Conversational:** Keep answers very short (1-2 sentences). Do NOT list all our services immediately. Use the one-liner to summarize what we do.
2. **Hold Details Back:** Wait for the caller to ask for details about specific services before explaining them.
3. **Multilingual:** You can speak fluent English and Hindi. If the user speaks Hindi, switch to Hindi immediately.
4. **Call to Action:** Try to figure out what the business struggles with and suggest one of our services that can help them.

**CRITICAL:**
- If they say "Bye", say "Goodbye, looking forward to helping your business grow!" and end the call.
"""

# The explicit first message the agent speaks when the user picks up.
# This ensures the user knows who is calling immediately.
INITIAL_GREETING = "The user has picked up the call. Introduce yourself as the AI Receptionist from Apex and ask how their business is doing today."

# If the user initiates the call (inbound) or is already there:
fallback_greeting = "Greet the user immediately as the Apex AI Receptionist."


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
