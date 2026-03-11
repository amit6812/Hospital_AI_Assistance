import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

def make_voice_friendly(text):
    """
    Technical tags and symbols
    """
    if not text:
        return ""
    
    # "SUGGEST_DOCTOR:Dentist" ko "I recommend consulting a Dentist" mein badalta hai
    friendly_text = re.sub(r"SUGGEST_DOCTOR ([\w\s]+)", r"I recommend you consult a \1.", text)
    
    # Extra symbols saaf karein
    friendly_text = friendly_text.replace("_", " ")
    
    return friendly_text.strip()