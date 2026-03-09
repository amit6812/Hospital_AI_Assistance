import re, random, string, json
from datetime import datetime
from sqlalchemy.future import select
from models import Appointment 

FILE = "details.json"

def load_data():
    try:
        with open(FILE, "r") as f: return json.load(f)
    except: return {"doctors": [], "disease_map": {}}

def save_data(data):
    with open(FILE, "w") as f: json.dump(data, f, indent=4)

def extract_time(text: str):
    text = text.upper().replace(".", ":")
    match = re.search(r"(\d{1,2})[:\s]?(\d{2})\s*(AM|PM)", text)
    if match:
        hr, mt, period = match.groups()
        return f"{hr.zfill(2)}:{mt} {period}"
    return None

def get_available_slots(specialty: str, date_str: str):
    data = load_data()
    available_options = []
    for doc in data["doctors"]:
        if doc["specialty"].lower() == specialty.lower():
            for schedule in doc.get("weekly_schedule", []):
                if schedule.get("date") == date_str and schedule["status"] in ["Available", "Half Day"]:
                    booked = schedule.get("booked_slots", [])
                    free_slots = [s for s in schedule.get("slots", []) if f"{date_str}_{s.replace(' ','')}" not in booked]
                    if free_slots:
                        available_options.append({"doctor": doc["name"], "doctor_id": doc["id"], "slots": free_slots})
    return available_options

def book_slot(doctor_id: int, date_str: str, time_slot: str):
    data = load_data()
    clean_time = time_slot.replace(" ", "").upper()
    for doc in data["doctors"]:
        if doc["id"] == doctor_id:
            for schedule in doc["weekly_schedule"]:
                if schedule.get("date") == date_str:
                    tag = f"{date_str}_{clean_time}"
                    if "booked_slots" not in schedule: schedule["booked_slots"] = []
                    if tag in schedule["booked_slots"]: return False, "Already booked"
                    schedule["booked_slots"].append(tag)
                    save_data(data)
                    return True, "APT" + ''.join(random.choices(string.digits, k=6))
    return False, "Error"

async def has_existing_booking(db, mobile: str, date: str):
    result = await db.execute(select(Appointment).where(Appointment.mobile == mobile, Appointment.date == date))
    return result.scalar_one_or_none()

async def cancel_appointment(db, booking_id: str):
    result = await db.execute(select(Appointment).where(Appointment.booking_id == booking_id.upper()))
    appt = result.scalar_one_or_none()
    if not appt: return False
    await db.delete(appt)
    await db.commit()
    return True