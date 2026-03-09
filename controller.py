import json
import re
from datetime import datetime, timedelta
from utils import (
    extract_time,
    book_slot,
    has_existing_booking,
    cancel_appointment,
    load_data
)
from response_builder import build_response
from ai import medical_chat
from google_sheets_utils import log_booking
import random
import dateparser

# ---------------------------------------------------
# Helper: Get Available Doctors for Specialist
# ---------------------------------------------------

def get_available_doctors(specialist: str):
    data = load_data()
    today = datetime.now()
    available = []

    for doc in data.get("doctors", []):
        if doc["specialty"].lower() != specialist.lower():
            continue

        for sch in doc.get("weekly_schedule", []):
            if sch["status"] not in ["Available", "Half Day"]:
                continue

            try:
                sch_date = datetime.strptime(sch["date"], "%d/%m/%y")
            except:
                continue

            if sch_date >= today and sch.get("slots"):
                available.append(doc)
                break

    return available


# ---------------------------------------------------
# Helper: Get Next Available Slots
# ---------------------------------------------------

def get_doctor_availability(doc):
    today = datetime.now()
    available_list = []

    for sch in doc.get("weekly_schedule", []):
        if sch["status"] not in ["Available", "Half Day"]:
            continue

        try:
            sch_date = datetime.strptime(sch["date"], "%d/%m/%y")
        except:
            continue

        if sch_date < today:
            continue

        booked = sch.get("booked_slots", [])
        free = [
            s for s in sch["slots"]
            if f"{sch['date']}_{s.replace(' ','')}" not in booked
        ]

        if free:
            available_list.append({
                "date": sch["date"],
                "slots": free
            })

    return available_list


# ---------------------------------------------------
# Hospitals
# ---------------------------------------------------

HOSPITALS = [
    "CityCare Hospital",
    "LifeLine Medical Center",
    "Sunrise Multispeciality Hospital",
    "HealthyWay Clinic",
    "Green Valley Hospital"
]


def greeting_message() -> str:
    hospital = random.choice(HOSPITALS)
    return (
        f"Hello! You are speaking with {hospital}. "
        f"Please tell me what can I assist you with today."
    )


# ---------------------------------------------------
# NEW: Direct Appointment Intent Detector
# ---------------------------------------------------

def is_direct_appointment_request(msg: str) -> bool:
    keywords = [
        "appointment",
        "book appointment",
        "doctor appointment",
        "i want appointment",
        "i want to book",
        "consult doctor",
        "see doctor",
        "book doctor",
    ]
    return any(word in msg for word in keywords)



def confirmation_yes(msg:str)->bool:
    text = msg.lower().strip()
    return bool(re.search(r"\b(yes|confirm|book|appointment|sure|yeah|yep)\b", text))

def confirmation_no(msg:str)->bool:
    text = msg.lower().strip()
    return bool(re.search(r"\b(no|cancel|nevermind|nope|nah)\b", text))

# Helper Function For Mobile Number Validation

def normalize_mobile_number(mobile:str)->str:
    number = re.findall(r"\d", mobile)
    return "".join(number)

# ---------------------------------------------------
# Helper: Repeat Request Detector
# ---------------------------------------------------

def is_repeat_request(msg: str) -> bool:
    msg = msg.lower()
    return any(word in msg for word in [
        "repeat",
        "again",
        "say again",
        "show again",
        "once more",
        "once again",
        "come again",
        "sorry repeat",
        "what were",
        "available again",
        "tell me again"
    ])


# ---------------------------------------------------
# Helper: Universal Repeat Handler
# ---------------------------------------------------

def handle_repeat(session):

    # DIRECT_SPECIALIST / CHOOSE_DOCTOR repeat
    if session.stage in ["DIRECT_SPECIALIST", "CHOOSE_DOCTOR"] and session.last_specialist:
        doctors = get_available_doctors(session.last_specialist)

        if not doctors:
            return None

        reply = f"Sure! Available {session.last_specialist}s:\n"

        for d in doctors:
            reply += f"\n {d['name']} ({d['experience']} exp, Fee: {d['fee']})"

        reply += "\n\nWhich doctor would you like to take an appointment?"
        return reply


    # SHOW_SLOTS repeat
    if session.stage == "SHOW_SLOTS" and session.options:
        reply = f"Sure! Available slots for {session.temp_doctor_name}:\n"

        for item in session.options:
            reply += f"\n {item['date']}: {', '.join(item['slots'])}"

        reply += "\n\nPlease tell me your preferred date and time."
        return reply


    # ASK_NAME repeat
    if session.stage == "ASK_NAME":
        return "Please enter patient name."


    # ASK_AGE repeat
    if session.stage == "ASK_AGE":
        return "Please enter patient age."


    # ASK_MOBILE repeat
    if session.stage == "ASK_MOBILE":
        return "Please enter mobile number."


    # ASK_ADDRESS repeat
    if session.stage == "ASK_ADDRESS":
        return "Please enter address."


    # CONFIRM_DETAILS repeat
    if session.stage == "CONFIRM_DETAILS":
        return (
            "Please confirm your appointment:\n"
            "Say YES to confirm or NO to cancel."
        )

    return None

# ---------------------------------------------------
# MAIN CONTROLLER
# ---------------------------------------------------

async def handle_message(session, db, user_msg):

    msg = user_msg.lower().strip()

     # =================================================
     # REPEAT HANDLER (GLOBAL)
     # =================================================

    if is_repeat_request(msg):
        repeat_response = handle_repeat(session)
        if repeat_response:
            return repeat_response

    # =================================================
    # GLOBAL COMMANDS
    # =================================================

    if "reschedule" in msg:
        session.stage = "RESCHEDULE_ID"
        await db.commit()
        return "Please provide your Booking ID to reschedule."

    if "cancel" in msg and session.stage != "CONFIRM_DETAILS":
        session.stage = "CANCEL_ID"
        await db.commit()
        return "Please provide your Booking ID to cancel."

    # =================================================
    # GREETING
    # =================================================

    if session.stage == "GREETING":

        if is_direct_appointment_request(msg):
            session.stage = "DIRECT_SPECIALIST"
            await db.commit()
            return "Sure! Which specialist doctor would you like to consult? (e.g., Cardiologist, Dentist, Orthopedic)"

        session.stage = "ASK_SYMPTOM"
        await db.commit()
        return greeting_message()

    # =================================================
    # DIRECT SPECIALIST FLOW
    # =================================================

    if session.stage == "DIRECT_SPECIALIST":

        specialist = user_msg.strip()
        session.last_specialist = specialist

        doctors = get_available_doctors(specialist)

        if not doctors:
            return f"Sorry, no {specialist} is currently available."

        session.stage = "CHOOSE_DOCTOR"
        await db.commit()

        reply = f"Available doctor for {specialist}s:\n"

        for idx, d in enumerate(doctors, start=1):
            reply += (
                f"\n\n{idx} {d['name']}"
                f"\n He has {d['experience']} of experience"
                f"\n and his consultation charges are ₹{d['fee']}"
            )

        reply += "\n\nSo Which doctor would you like to take an appointment?"

        return reply

    # =================================================
    # SYMPTOM TRIAGE FLOW (AI)
    # =================================================

    if session.stage == "ASK_SYMPTOM":

        if is_direct_appointment_request(msg):
            session.stage = "DIRECT_SPECIALIST"
            await db.commit()
            return "Sure! Please tell me which specialist doctor you want to consult."

        if msg in ["hi", "hello", "hey"]:
            return "Please describe your symptoms."

        ai_reply = medical_chat(user_msg, session.history or "")

        # Check if AI is suggesting a specialist doctor

        if "SUGGEST_DOCTOR:" in ai_reply:

            specialist = ai_reply.split("SUGGEST_DOCTOR:")[1].strip()
            session.last_specialist = specialist

            # Stage change and ask confirmation
            session.stage = "CONFIRM_APPOINTMENT"
            await db.commit()

            #doctors = get_available_doctors(specialist)

            # if not doctors:
            #     return f"Sorry, no {specialist} is currently available."

            # session.stage = "CHOOSE_DOCTOR"
            # await db.commit()

            clean_reply = ai_reply.replace(f"SUGGEST_DOCTOR:{specialist}", "").strip()
            return f"{clean_reply}\n\nWould you like to book an appointment with our {specialist}? Please say YES to confirm or NO to decline."
        return ai_reply

    if session.stage == "CONFIRM_APPOINTMENT":
        if any(word in msg for word in ["yes", "confirm", "sure", "yeah", "yep", "ok", "okay","agree","appointment"]):
            specialist = session.last_specialist
            doctors = get_available_doctors(specialist)


            if not doctors:
                return f"Sorry, no {specialist} is currently available."
            

            session.stage = "CHOOSE_DOCTOR"
            await db.commit()

            reply = f"That's great!  here are the available doctor for {specialist}s:\n"

            for idx, d in enumerate(doctors, start=1):
                reply += (
                    f"\n\n{idx} {d['name']}"
                    f"\n He has {d['experience']} of experience"
                    f"\n and his consultation charges are ₹{d['fee']}"
                )
            reply += "\n\nPlease tell me which doctor you would like to take an appointment with."
               # reply += "\n\nSo Which doctor would you like to take an appointment?"

            return reply
        else:
            session.stage = "GREETING" # Reset to greeting for any response other than confirmation
            await db.commit()
            return "No problem! Let me know if you need anything else. Take care!"

        #return ai_reply

    # =================================================
    # DOCTOR SELECTION

    if session.stage == "CHOOSE_DOCTOR":

        data = load_data()

        def normalize(name):
            return (
                name.lower()
                .replace("dr.", "")
                .replace("doctor", "")
                .replace("please", "")
                .strip()
            )

        cleaned_input = normalize(msg)
        selected_doc = None

        for d in data["doctors"]:
            if session.last_specialist.lower() != d["specialty"].lower():
                continue

            doctor_name = normalize(d["name"])

            if doctor_name in cleaned_input or cleaned_input in doctor_name:
                selected_doc = d
                break

        if not selected_doc:
            return "Please type a valid doctor name from the list."

        session.temp_doctor_name = selected_doc["name"]
        session.temp_doctor_id = selected_doc["id"]

        availability = get_doctor_availability(selected_doc)

        if not availability:
            return f"Sorry, {session.temp_doctor_name} has no future slots."

        session.stage = "SHOW_SLOTS"
        session.options = availability
        await db.commit()

        reply = f"Available slots for {session.temp_doctor_name}:\n"

        for item in availability:
            reply += f"\n date {item['date']} and time {', '.join(item['slots'])}"

        # reply += (
        #     f"\n\nPlease type Date and Time "
        #     f"(Example: {availability[0]['date']} at {availability[0]['slots'][0]})."
        # )

        return reply

    # =================================================
    # SLOT SELECTION (FIXED SECTION)

    if session.stage == "SHOW_SLOTS":

        date = dateparser.parse(user_msg)
        if not date:
            return "I could not understand please saylike this, Example: 25 feb at 11 AM"
        


        # pattern = r"(\d{2}/\d{2}/\d{2})[:\s]*at\s*(\d{1,2}:\d{2}\s*(AM|PM))"

        # match = re.search(pattern, user_msg, re.IGNORECASE)

        # if not match:
        #     return "Please type in format: DD/MM/YY at HH:MM AM/PM\nExample: 25/02/26 at 11:00 AM"

        date_input = date.strftime("%d/%m/%y")
        time_input = date.strftime("%I:%M %p").upper().replace(" ", "")
        #time_input = match.group(2).upper().replace(" ", "")

        valid = False

        for item in session.options:
            if item["date"] == date_input:
                available_times = [s.replace(" ", "") for s in item["slots"]]
                if time_input in available_times:
                    valid = True 
                    break

        if not valid:
            return "Selected slot is not available. Please choose from listed slots."

        session.temp_date = date_input
        session.temp_slot = time_input
        session.stage = "ASK_NAME"
        await db.commit()

        return "Please enter patient name:"

    # =================================================
    # PATIENT DETAILS FLOW
    

    if session.stage == "ASK_NAME":
        session.patient_name = user_msg.strip()
        session.stage = "ASK_AGE"
        await db.commit()
        return "Please enter patient age:"

    if session.stage == "ASK_AGE":

        if not user_msg.isdigit():
            return "Please enter valid age (numbers only)."

        session.patient_age = int(user_msg)
        session.stage = "ASK_MOBILE"
        await db.commit()
        return "Please enter mobile number:"

    if session.stage == "ASK_MOBILE":
        phone = normalize_mobile_number(user_msg)

        if len(phone) < 10 or len(phone) > 15:
            return "Please enter valid mobile number with country code if applicable."
        # if not user_msg.isdigit() or len(user_msg) < 10:
        #     return "Please enter valid mobile number."

        session.patient_mobile = phone
        session.stage = "ASK_ADDRESS"
        await db.commit()
        return "Please enter address:"

    if session.stage == "ASK_ADDRESS":
        session.patient_address = user_msg.strip()
        session.stage = "CONFIRM_DETAILS"
        await db.commit()

        return (
            "Please confirm your appointment:\n\n"
            f"Doctor: {session.temp_doctor_name}\n"
            f"Date: {session.temp_date}\n"
            f"Time: {session.temp_slot}\n"
            f"Name: {session.patient_name}\n"
            f"Age: {session.patient_age}\n"
            f"Mobile: {session.patient_mobile}\n"
            f"Address: {session.patient_address}\n\n"
            " Say YES to confirm or NO to cancel. For Example:\n"
            "'YES, confirm my appointment' or 'No, cancel it.'"
        )

    # =================================================
    # CONFIRM BOOKING
    # =================================================

    if session.stage == "CONFIRM_DETAILS":

        #if msg == "yes":
        if confirmation_yes(msg):
            success, booking_id = book_slot(
                session.temp_doctor_id,
                session.temp_date,
                session.temp_slot
            )

            if not success:
                return "Slot booking failed. It may already be booked."

            try:
                log_booking(
                    booking_id,
                    session.temp_doctor_name,
                    session.temp_date,
                    session.temp_slot,
                    session.patient_name,
                    session.patient_age,
                    session.patient_mobile,
                    session.patient_address
                )
            except Exception as e:
                print("Google Sheet Logging Error:", e)

            session.stage = "GREETING"
            await db.commit()

            return (
                f"Appointment Confirmed!\n\n"
                f"Booking ID: {booking_id}\n"
                f"Doctor: {session.temp_doctor_name}\n"
                f"Date: {session.temp_date}\n"
                f"Time: {session.temp_slot}\n\n"
                f"Thank you!"
            )

        #if msg == "no":
        elif confirmation_no(msg):
            session.stage = "GREETING"
            await db.commit()
            return "Appointment cancelled. How else may I help you?"
        
        else:
            return "i did not understand. say YES to confirm or NO to cancel."