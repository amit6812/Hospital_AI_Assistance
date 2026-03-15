from fastapi import FastAPI, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.future import select
from contextlib import asynccontextmanager
import uuid
import os
import re

from db import AsyncSessionLocal, engine, Base
from models import ChatSession
from controller import handle_message, greeting_message
from speaker import make_voice_friendly

from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client

# ---------- APP STARTUP ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Hospital Voice Agent", lifespan=lifespan)

# ---------- REQUEST MODEL ----------

class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None


# ---------- HEALTH CHECK ----------

@app.get("/ping")
def ping():
    return {"status": "ok"}


# ---------- SAGEMAKER ENDPOINT ----------

# @app.post("/invocations")
# async def invocations(request: Request):
#     payload = await request.json()
#     data = AgentRequest(**payload)
#     return await agent_talk(data)

# SageMaker invocation endpoint
@app.post("/invocations")
async def invoke(data: AgentRequest):

    message = data.message.lower()

    if "hello" in message:
        reply = "Hello, how can I help you today?"

    elif "doctor" in message:
        reply = "Sure, I can help you book a doctor appointment."

    else:
        reply = "Please tell me your health concern."

    return {
        "reply": reply
    }

# ---------- TEXT NORMALIZATION ----------

def normalize_speech_text(text: str) -> str:
    if not text:
        return text

    text = text.lower()
    text = text.replace("p.m.", "PM")
    text = text.replace("a.m.", "AM")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ---------- CHAT ENDPOINT ----------

@app.post("/agent/talk")
async def agent_talk(data: AgentRequest):

    async with AsyncSessionLocal() as db:

        session_id = data.session_id or str(uuid.uuid4())

        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            session = ChatSession(
                session_id=session_id,
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
                "session_id": session_id
            }

        if not data.message or not data.message.strip():
            return {
                "reply": "Please tell me your health concern.",
                "session_id": session_id
            }

        reply = await handle_message(session, db, data.message)

        final_reply = make_voice_friendly(reply)

        session.history = (session.history or "") + \
            f"\nPatient: {data.message}\nAI: {reply}"

        await db.commit()

        return {
            "reply": final_reply,
            "session_id": session_id
        }


# ---------- TWILIO VOICE HANDLER ----------

@app.post("/voice")
async def voice_handler(request: Request):

    form = await request.form()
    speech_text = form.get("SpeechResult")
    call_sid = form.get("CallSid")

    response = VoiceResponse()

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == call_sid)
        )

        session = result.scalar_one_or_none()

        if not session:
            session = ChatSession(
                session_id=call_sid,
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
                language="en-IN",
                speechModel="phone_call",
                action="/voice",
                method="POST"
            )

            gather.say(greeting_message(), voice="Polly.Aditi")
            response.append(gather)

            return Response(str(response), media_type="application/xml")

        if speech_text:

            clean_text = normalize_speech_text(speech_text)

            reply = await handle_message(session, db, clean_text)

            final_reply = make_voice_friendly(reply)

            session.history += f"\nPatient: {speech_text}\nAI: {reply}"

            await db.commit()

            gather = Gather(
                input="speech",
                timeout=5,
                speechTimeout="auto",
                language="en-IN",
                speechModel="phone_call",
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
                language="en-IN",
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


# ---------- TWILIO CALL 

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


# ---------- SERVER ----------

if __name__ == "__main__":

    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port
    )