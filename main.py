from fastapi import FastAPI, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.future import select
from contextlib import asynccontextmanager
import uuid
import os
import re
import sys
from db import AsyncSessionLocal, engine, Base
from models import ChatSession
from controller import handle_message, greeting_message, normalize_speech_text
from speaker import make_voice_friendly
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from fastapi.middleware.cors import CORSMiddleware

# ---------- APP STARTUP ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Hospital Voice Agent", lifespan=lifespan)


# middleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- UI STATIC FILES ----------

if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


#set home route to serve the UI

@app.get("/", response_class=HTMLResponse)
async def ui():
    try:
        with open("frontend/index.html") as f:
            return f.read()
    except:
        return "<h2>UI not found</h2>"


# ---------- REQUEST MODEL ----------

class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None


# ---------- HEALTH CHECK ----------

@app.get("/ping")
def ping():
    return {"status": "ok"}


# ---------- SAGEMAKER INVOCATION ----------

@app.post("/invocations")
def invoke():
    return {"message": "model working"}





# ---------- CHAT ENDPOINT ----------

@app.post("/agent/talk")
async def agent_talk(data: AgentRequest):
    async with AsyncSessionLocal() as db:
        
        current_session_id = data.session_id
        is_new_session = False

        if not current_session_id or current_session_id == "null":
            current_session_id = str(uuid.uuid4())
            is_new_session = True
        
        

        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == current_session_id)
        )

        session = result.scalar_one_or_none()   

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
            is_new_session = True   

        if is_new_session:
            reply = greeting_message()

            return {
                "reply": make_voice_friendly(reply),
                "session_id": current_session_id
            }


        reply = await handle_message(session, db, data.message)

        final_reply = make_voice_friendly(reply)

        session.history = (session.history or "") + \
            f"\nPatient: {data.message}\nAI: {reply}"

        await db.commit()

        return {
            "reply": final_reply,
            "session_id": current_session_id
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


# ---------- TWILIO CALL ----------

ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER")
MY_NUMBER = os.getenv("MY_NUMBER")
BASE_URL = os.getenv("BASE_URL")


# This endpoint is just for testing the call flow. In production, you would trigger calls based on your requirements.

@app.post("/make-call")
def make_call():

    # Client Initialization
    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    # Make the call
    call = client.calls.create(
        to=MY_NUMBER,
        from_=TWILIO_NUMBER,
        url=f"{BASE_URL}/voice"
    )

    return {"status": "Call initiated", "call_sid": call.sid}


# ---------- SERVER Execution ----------

if __name__ == "__main__":

    import uvicorn

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        uvicorn.run("main:app", host="0.0.0.0", port=8080)