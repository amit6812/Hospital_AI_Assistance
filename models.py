from sqlalchemy import Column, Integer, String, Text, Boolean, JSON, DateTime
from sqlalchemy.sql import func
from db import Base


# ==============================
# CHAT SESSION TABLE
# ==============================

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)

    patient_name = Column(String, default="Guest")

    # Patient Details
    patient_age = Column(Integer, nullable=True)        # Changed to Integer
    patient_mobile = Column(String, nullable=True)
    patient_address = Column(String, nullable=True)

    # Temporary Doctor Selection
    temp_doctor_name = Column(String, nullable=True)
    temp_doctor_id = Column(Integer, nullable=True)

    # Flow Stage
    stage = Column(String, default="GREETING")

    # Conversation Memory
    history = Column(Text, default="")

    # Detected Context
    last_specialist = Column(String, nullable=True)
    last_doctor = Column(String, nullable=True)

    # Temporary Booking Memory
    temp_date = Column(String, nullable=True)
    temp_slot = Column(String, nullable=True)
    options = Column(JSON, nullable=True)

    confirmed = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ==============================
# APPOINTMENTS TABLE
# ==============================

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(String, unique=True, index=True)

    # Session Reference
    session_id = Column(String, index=True)

    # Patient Info
    patient_name = Column(String, index=True)
    age = Column(Integer, index=True)
    mobile = Column(String, index=True)
    address = Column(String)

    # Doctor Info
    doctor_name = Column(String, index=True)
    specialist = Column(String)

    # Appointment Details
    date = Column(String, index=True)
    slot = Column(String)
    
    # Status (NEW)
    status = Column(String, default="BOOKED")  
    # BOOKED / CANCELLED / COMPLETED / RESCHEDULED

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())
