def build_response(stage: str, data: dict | None = None):

    data = data or {}

    if stage == "ASK_SYMPTOM":
        return "Please tell me your health concern."

    if stage == "ASK_DATE":
        specialist = data.get("specialist", "doctor")
        return f"I will connect you to {specialist}. Kindly tell preferred date in DD/MM/YY format."

    if stage == "INVALID_DATE":
        return "Please tell date like 25/02/26."

    if stage == "NO_DOCTOR":
        return "No doctors are available on this date. Please choose another date."

    if stage == "SHOW_SLOTS":
        text = "Available doctors and timings: "
        for doc in data.get("options", []):
            text += f"{doc['doctor']} at {', '.join(doc['slots'])}. "
        return text

    if stage == "INVALID_TIME":
        return "That time slot is not available. Please select another time."

    if stage == "BOOKED":
        return f"Your appointment is confirmed with {data['doctor']} on {data['date']} at {data['time']}. Booking ID {data['id']}."

    if stage == "CLARIFY":
        return "I did not understand. Could you repeat please?"

    return "How may I help you?"
