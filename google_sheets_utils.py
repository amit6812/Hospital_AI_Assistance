import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# CONFIGURATION
CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_ID = "1MCWqrWGWIj2fCPlbL80gTDwYF7PCC0nQ8_oyuWVpAj0"
SHEET_NAME = "Sheet1"

def get_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(SHEET_NAME)
        return sheet
    except Exception as e:
        print(f"Auth Error Detail: {e}")
        return None

def log_booking(doctor, date, time, booking_id, patient_name, age, mobile, address):
    """
    Sabhi 8 fields ko Google Sheet mein save karta hai.
    """
    sheet = get_sheet()
    if sheet:
        try:
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            new_row = [
                timestamp, booking_id, patient_name, age, 
                mobile, address, doctor, date, time
            ]
            sheet.append_row(new_row)
            print(f"SUCCESS: Booking for {patient_name} saved!")
            return True
        except Exception as e:
            print(f"Sheet Write Error: {e}")
            return False
    return False