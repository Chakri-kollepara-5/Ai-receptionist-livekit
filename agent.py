import os
import certifi

# Fix for macOS SSL Certificate errors - MUST be before other imports
os.environ['SSL_CERT_FILE'] = certifi.where()

import logging
import json
from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    openai,
    cartesia,
    deepgram,
    sarvam,
)
from livekit.agents import llm
from typing import Annotated, Optional

# Load environment variables
load_dotenv(".env", override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-agent")

import config
import datetime
import database

# TRUNK ID - Now loaded from config.py
# You can find this by running 'python setup_trunk.py --list' or checking LiveKit Dashboard 


def _build_tts(config_provider: str = None, config_voice: str = None):
    """Configure the Text-to-Speech provider based on env vars or dynamic config."""
    # Priority: Config > Env Var > Default
    provider = (config_provider or os.getenv("TTS_PROVIDER", config.DEFAULT_TTS_PROVIDER)).lower()
    
    # If using Sarvam Voice names (Anushka/Aravind), force Sarvam provider
    if config_voice in ["anushka", "aravind", "amartya", "dhruv"]:
        provider = "sarvam"

    if provider == "cartesia":
        logger.info("Using Cartesia TTS")
        model = os.getenv("CARTESIA_TTS_MODEL", config.CARTESIA_MODEL)
        voice = os.getenv("CARTESIA_TTS_VOICE", config.CARTESIA_VOICE)
        return cartesia.TTS(model=model, voice=voice)
    
    if provider == "sarvam":
        logger.info(f"Using Sarvam TTS (Voice: {config_voice})")
        model = os.getenv("SARVAM_TTS_MODEL", config.SARVAM_MODEL)
        # Use dynamic voice or env var or default
        voice = config_voice or os.getenv("SARVAM_VOICE", "anushka")
        language = os.getenv("SARVAM_LANGUAGE", config.SARVAM_LANGUAGE)
        return sarvam.TTS(model=model, speaker=voice, target_language_code=language)

    if provider == "deepgram":
        logger.info("Using Deepgram TTS")
        model = os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en")
        return deepgram.TTS(model=model)

    # Default to OpenAI
    logger.info(f"Using OpenAI TTS (Voice: {config_voice})")
    model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
    voice = config_voice or os.getenv("OPENAI_TTS_VOICE", config.DEFAULT_TTS_VOICE)
    return openai.TTS(model=model, voice=voice)


def _build_llm(config_provider: str = None):
    """Configure the LLM provider based on config or env vars."""
    provider = (config_provider or os.getenv("LLM_PROVIDER", config.DEFAULT_LLM_PROVIDER)).lower()

    if provider == "groq":
        logger.info("Using Groq LLM")
        return openai.LLM(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", config.GROQ_MODEL),
            temperature=float(os.getenv("GROQ_TEMPERATURE", str(config.GROQ_TEMPERATURE))),
        )
    
    # Default to OpenAI
    logger.info("Using OpenAI LLM")
    return openai.LLM(model=config.DEFAULT_LLM_MODEL)



class ClinicReceptionistTools(llm.ToolContext):
    def __init__(self, ctx: agents.JobContext, phone_number: str = None):
        super().__init__(tools=[])
        self.ctx = ctx
        self.phone_number = phone_number

    def _find_doctor_id(self, doctor_name: str) -> Optional[int]:
        if not doctor_name:
            return None
        clean_name = doctor_name.lower().replace("dr.", "").replace("dr", "").strip()
        doctors = database.get_doctors_by_specialty()
        for doc in doctors:
            if clean_name in doc["name"].lower():
                return doc["id"]
        return None

    @llm.function_tool(description="List all clinical specialties/departments and matching doctors available at Blackfriars Medical Practice.")
    def list_specialties_and_doctors(self) -> str:
        """List all clinical specialties and their doctors."""
        logger.info("Listing specialties and doctors.")
        doctors = database.get_doctors_by_specialty()
        if not doctors:
            return "No doctors registered in the clinic system."
        
        result = "Specialties and Doctors at Blackfriars Medical Practice:\n"
        for doc in doctors:
            result += f"- {doc['name']} ({doc['gender']}), Specialty: {doc['specialty']}, Qualifications: {doc['qualifications']}\n"
        return result

    @llm.function_tool(description="Check available appointment slots for a specific doctor and/or specific date.")
    def check_availability(
        self,
        doctor_name: Optional[str] = None,
        date: Optional[str] = None
    ) -> str:
        """
        Check available slots in the clinic database.

        Args:
            doctor_name: The name of the doctor (optional, e.g. 'Kanabar' or 'Ami').
            date: The date in YYYY-MM-DD format (optional, e.g. '2026-06-22').
        """
        logger.info(f"Checking availability for doctor: {doctor_name}, date: {date}")
        
        doctor_id = None
        if doctor_name:
            doctor_id = self._find_doctor_id(doctor_name)
            if not doctor_id:
                return f"Could not find a doctor matching the name '{doctor_name}'. Please verify the spelling or check the doctor list."
                
        slots = database.get_available_slots(doctor_id=doctor_id, date_str=date)
        if not slots:
            doc_msg = f" for Dr. {doctor_name}" if doctor_name else ""
            date_msg = f" on {date}" if date else ""
            return f"No available slots found{doc_msg}{date_msg}. Please suggest another date or doctor."
            
        result = "Available Slots (please offer these specific options to the patient):\n"
        # Return at most 6 slots to prevent overwhelming the voice session / audio stream
        for slot in slots[:6]:
            dt = datetime.datetime.fromisoformat(slot["start_time"])
            formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
            result += f"- Slot ID {slot['id']}: {formatted_time} with {slot['doctor_name']} ({slot['specialty']})\n"
        return result

    @llm.function_tool(description="Book a new appointment. Patient name, phone number, and slot ID are required.")
    def book_appointment(
        self,
        patient_name: str,
        patient_phone: str,
        slot_id: int,
        appointment_type: str = "Consultation"
    ) -> str:
        """
        Book an appointment slot.

        Args:
            patient_name: The patient's full name.
            patient_phone: The patient's phone number.
            slot_id: The ID of the chosen slot.
            appointment_type: Type of appointment, e.g., Consultation, Follow-up.
        """
        logger.info(f"Booking appointment: name={patient_name}, phone={patient_phone}, slot_id={slot_id}")
        res = database.book_appointment(patient_name, patient_phone, slot_id, appointment_type)
        return res["message"]

    @llm.function_tool(description="Look up existing appointments for a patient using their phone number.")
    def lookup_appointments(
        self,
        patient_phone: str
    ) -> str:
        """
        Lookup active appointments by phone number.

        Args:
            patient_phone: The patient's phone number.
        """
        logger.info(f"Looking up appointments for phone: {patient_phone}")
        appointments = database.get_appointments_by_phone(patient_phone)
        active = [a for a in appointments if a["status"] in ["booked", "rescheduled"]]
        if not active:
            return f"No active appointments found for phone number {patient_phone}."
            
        result = "Found active appointments:\n"
        for app in active:
            dt = datetime.datetime.fromisoformat(app["start_time"])
            formatted_time = dt.strftime("%A, %B %d at %I:%M %p")
            result += f"- Appointment ID {app['appointment_id']}: {app['appointment_type']} with {app['doctor_name']} on {formatted_time} (Status: {app['status']})\n"
        return result

    @llm.function_tool(description="Reschedule an existing appointment. Requires the existing appointment ID and a new available slot ID.")
    def reschedule_appointment(
        self,
        appointment_id: int,
        new_slot_id: int
    ) -> str:
        """
        Reschedule an existing appointment to a new slot.

        Args:
            appointment_id: The ID of the existing appointment.
            new_slot_id: The ID of the new slot to book.
        """
        logger.info(f"Rescheduling appointment {appointment_id} to new slot {new_slot_id}")
        res = database.reschedule_appointment(appointment_id, new_slot_id)
        return res["message"]

    @llm.function_tool(description="Cancel an existing appointment. Requires the appointment ID.")
    def cancel_appointment(
        self,
        appointment_id: int
    ) -> str:
        """
        Cancel an existing appointment.

        Args:
            appointment_id: The ID of the appointment to cancel.
        """
        logger.info(f"Cancelling appointment {appointment_id}")
        res = database.cancel_appointment(appointment_id)
        return res["message"]

    @llm.function_tool(description="Transfer the call to a human support agent or another phone number.")
    async def transfer_call(self, destination: Optional[str] = None):
        """
        Transfer the call.
        """
        if destination is None:
            destination = config.DEFAULT_TRANSFER_NUMBER
            if not destination:
                 return "Error: No default transfer number configured."
        if "@" not in destination:
            if config.SIP_DOMAIN:
                clean_dest = destination.replace("tel:", "").replace("sip:", "")
                destination = f"sip:{clean_dest}@{config.SIP_DOMAIN}"
            else:
                if not destination.startswith("tel:") and not destination.startswith("sip:"):
                     destination = f"tel:{destination}"
        elif not destination.startswith("sip:"):
             destination = f"sip:{destination}"
        
        logger.info(f"Transferring call to {destination}")
        
        participant_identity = None
        if self.phone_number:
            participant_identity = f"sip_{self.phone_number}"
        else:
            for p in self.ctx.room.remote_participants.values():
                participant_identity = p.identity
                break
        
        if not participant_identity:
            logger.error("Could not determine participant identity for transfer")
            return "Failed to transfer: could not identify the caller."

        try:
            logger.info(f"Transferring participant {participant_identity} to {destination}")
            await self.ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=self.ctx.room.name,
                    participant_identity=participant_identity,
                    transfer_to=destination,
                    play_dialtone=False
                )
            )
            return "Transfer initiated successfully."
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return f"Error executing transfer: {e}"


class OutboundAssistant(Agent):
    """
    An AI agent tailored for outbound calls.
    Attempts to be helpful and concise.
    """
    def __init__(self, instructions: str, tools: list) -> None:
        super().__init__(
            instructions=instructions,
            tools=tools,
        )


async def entrypoint(ctx: agents.JobContext):
    """
    Main entrypoint for the agent.
    """
    logger.info(f"Connecting to room: {ctx.room.name}")
    
    phone_number = None
    config_dict = {}
    
    try:
        if ctx.job.metadata:
            data = json.loads(ctx.job.metadata)
            phone_number = data.get("phone_number")
            config_dict = data
    except Exception:
        pass
        
    try:
        if ctx.room.metadata:
            data = json.loads(ctx.room.metadata)
            if data.get("phone_number"):
                phone_number = data.get("phone_number")
            config_dict.update(data)
    except Exception:
        logger.warning("No valid JSON metadata found in Room.")

    # Initialize function context
    fnc_ctx = ClinicReceptionistTools(ctx, phone_number)

    # Inject current date and time dynamically
    now_str = datetime.datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
    system_instructions = f"{config.SYSTEM_PROMPT}\n\n**IMPORTANT CURRENT CONTEXT:**\n- Today's date and time is: {now_str}.\n"

    # Initialize the Agent Session with plugins
    session = AgentSession(
        stt=deepgram.STT(model=config.STT_MODEL, language=config.STT_LANGUAGE), 
        llm=_build_llm(config_dict.get("model_provider")),
        tts=_build_tts(config_dict.get("model_provider"), config_dict.get("voice_id")),
    )

    # Start the session
    await session.start(
        room=ctx.room,
        agent=OutboundAssistant(instructions=system_instructions, tools=list(fnc_ctx.function_tools.values())),
        room_input_options=RoomInputOptions(
            close_on_disconnect=True,
        ),
    )

    should_dial = False
    if phone_number:
        user_already_here = False
        for p in ctx.room.remote_participants.values():
            if f"sip_{phone_number}" in p.identity or "sip_" in p.identity:
                user_already_here = True
                break
        
        if not user_already_here:
            should_dial = True
            logger.info("User not in room. Agent will initiate dial-out.")
        else:
            logger.info("User already in room (Dashboard dispatched). output Only generated greeting.")

    if should_dial:
        logger.info(f"Initiating outbound SIP call to {phone_number}...")
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=config.SIP_TRUNK_ID,
                    sip_call_to=phone_number,
                    participant_identity=f"sip_{phone_number}",
                    wait_until_answered=True,
                )
            )
            logger.info("Call answered! Agent is now listening.")
            await session.generate_reply(
                instructions=config.INITIAL_GREETING
            )
        except Exception as e:
            logger.error(f"Failed to place outbound call: {e}")
            ctx.shutdown()
    else:
        logger.info("Detecting if we should greet...")
        await session.generate_reply(instructions=config.fallback_greeting)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller", 
            port=int(os.getenv("PORT", "8081")),
            num_idle_processes=0,  # Prevent memory limits overflow in 512MB free tier containers
        )
    )
