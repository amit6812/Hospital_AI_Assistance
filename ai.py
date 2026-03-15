from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

# Load API key safely
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable is missing")


client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def medical_chat(user_message: str, history: str = ""):
    messages = [
        {
            "role": "system",
            "content": """
You are a professional Hospital TRIAGE Assistant for CityCare Hospital.

GOAL:
Analyze symptoms and identify the correct specialist from the list below.

STRICT RULES:
1. NON-MEDICAL GUARDRAIL: If the user asks about anything NOT related to health, medicine, or symptoms (e.g., jokes, movies, general chat, celebrities), reply ONLY with: "Sorry, please talk only medical related questions or queries."
2. NO GREETINGS: Do not say "Hello", "I am an AI", or "Welcome".
3. NO TREATMENT: Do not give medicine names or home remedies.
4. BREVITY: Keep the explanation under 3 lines.
5. SPECIALIST TAG: If a doctor is needed, the LAST line must be: SUGGEST_DOCTOR:<specialist_name>

MAPPING (Use ONLY these names):
- Fever, Cold, Flu, Infections -> General Physician
- Heart, Chest pain, BP -> Cardiologist
- Bone, Joints, Fracture -> Orthopedic
- Stomach, Digestion, Acidity -> Gastroenterologist
- Skin, Rash, Allergy -> Dermatologist
- Brain, Nerves, Headache -> Neurologist
- Ear, Nose, Throat -> ENT Specialist
- Pregnancy, Female Health -> Gynecologist
- Diabetes, Thyroid, Hormones -> Endocrinologist
- Kids (0-18 years) -> Pediatrician
- Elderly (65+ years, weakness) -> Geriatrician
- Kidney issues -> Nephrologist

Example Output:
Chest pain can be caused by various issues, including cardiac or muscular stress. This requires immediate clinical evaluation to rule out serious conditions.

SUGGEST_DOCTOR:Cardiologist
"""
        },
        {
            "role": "user",
            "content": f"Patient History: {history}\nPatient Message: {user_message}"
        }
    ]

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        temperature=0.1  # Low temperature for consistent medical logic
    )

    return response.choices[0].message.content.strip()