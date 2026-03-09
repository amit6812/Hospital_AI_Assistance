from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy.future import select
import random
import uuid
from contextlib import asynccontextmanager
from db import AsyncSessionLocal, engine, Base
from models import ChatSession
from controller import handle_message,greeting_message
from speaker import make_voice_friendly
from db import init_db
from twilio.rest import Client
import os
from dotenv import load_dotenv


# ---------- APP LIFESPAN ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown logic if needed

app = FastAPI(title="Hospital Voice Agent", lifespan=lifespan)


# ---------- REQUEST MODEL ----------
class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None


# ---------- RANDOM HOSPITAL LIST ----------





# ---------- MAIN CHAT ENDPOINT ----------
@app.post("/agent/talk")
async def agent_talk(data: AgentRequest):

    async with AsyncSessionLocal() as db:

        # Generate session if not provided
        current_session_id = data.session_id or str(uuid.uuid4())

        # Check if session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == current_session_id)
        )
        session = result.scalar_one_or_none()

        # ---------- NEW USER ----------
        if not session:
            session = ChatSession(
                session_id=current_session_id,
                patient_name="Guest",
                stage="ASK_SYMPTOM",
                history=""
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

            reply = greeting_message()

            return {
                "reply": make_voice_friendly(reply),
                "session_id": current_session_id
            }

        # ---------- EMPTY MESSAGE PROTECTION ----------
        if not data.message or not data.message.strip():
            return {
                "reply": "Please tell me your health concern.",
                "session_id": current_session_id
            }

        # ---------- EXISTING USER FLOW ----------
        reply = await handle_message(session, db, data.message)

        final_reply = make_voice_friendly(reply)

        # ---------- SAVE CHAT HISTORY ----------
        session.history = (session.history or "") + \
            f"\nPatient: {data.message}\nAI: {reply}"

        await db.commit()

        return {
            "reply": final_reply,
            "session_id": current_session_id
        }

from fastapi import Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather


import re

def normalize_speech_text(text: str) -> str:
    if not text:
        return text

    text = text.lower()

    # Fix common STT formatting issues
    text = text.replace("p.m.", "PM")
    text = text.replace("a.m.", "AM")

    # Fix weird spaced numbers like "23 0226"
    #text = re.sub(r"(\d{1,2})\s+0?(\d{2})(\d{2})", r"\1/\2/\3", text)
    text = re.sub(r"\s+", " ", text)  # Collapse multiple spaces

    return text.strip()

@app.post("/voice")
async def voice_handler(request: Request):

    form = await request.form()
    speech_text = form.get("SpeechResult")
    call_sid = form.get("CallSid")

    response = VoiceResponse()

    async with AsyncSessionLocal() as db:

        current_session_id = call_sid

        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == current_session_id)
        )
        session = result.scalar_one_or_none()

        # ---------- FIRST TIME CALLER ----------
        if not session:
            session = ChatSession(
                session_id=current_session_id,
                patient_name="Guest",
                stage="ASK_SYMPTOM",
                history=""
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

            gather = Gather(
                input="speech",
                timeout=5,
                speechTimeout="auto",
                language="en-IN",              # ✅ Indian English
                speechModel="phone_call",      # ✅ Better phone accuracy
                action="/voice",
                method="POST"
            )

            gather.say(greeting_message(), voice="Polly.Aditi")
            response.append(gather)

            return Response(str(response), media_type="application/xml")

        # ---------- USER SPOKE ----------
        if speech_text:

            print("SpeechResult:", speech_text)  # Debug
            clean_text = normalize_speech_text(speech_text)
            reply = await handle_message(session, db, clean_text)
            final_reply = make_voice_friendly(reply)

            session.history = (session.history or "") + \
                f"\nPatient: {speech_text}\nAI: {reply}"

            await db.commit()

            gather = Gather(
                input="speech",
                timeout=5,
                speechTimeout="auto",
                language="en-IN",          # ✅ Indian English
                speechModel="phone_call",  # ✅ Better recognition
                action="/voice",
                method="POST"
            )

            gather.say(final_reply, voice="Polly.Aditi")
            response.append(gather)

        else:
            gather = Gather(
                input="speech",
                timeout=5,
                speechTimeout="auto",
                language="en-IN",          # ✅ Indian English
                speechModel="phone_call",
                action="/voice",
                method="POST"
            )

            gather.say(
                "I did not hear anything. Please say that again.",
                voice="Polly.Aditi"
            )
            response.append(gather)

    return Response(str(response), media_type="application/xml")

from twilio.rest import Client

# .env file load karein
load_dotenv()

# Variables ko environment se fetch karein
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
MY_NUMBER = os.getenv("MY_NUMBER")
BASE_URL = os.getenv("BASE_URL")

@app.get("/make-call")
def make_call():
    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    call = client.calls.create(
        to=MY_NUMBER,
        from_=TWILIO_NUMBER,
        url=f"{BASE_URL}/voice"
    )

    return {"status": "Call initiated", "call_sid": call.sid}

