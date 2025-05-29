import os
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from datetime import datetime
import json

# Initialize Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_transcript_with_llm(transcript):
    try:
        generation_config = GenerationConfig(
            temperature=0.7,
            max_output_tokens=1000,
            top_p=1,
            top_k=1
        )
        # Configure the model
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            generation_config=generation_config
        )
        
        prompt = f"""
        Please analyze the following call transcript and extract:
        1. Customer Name
        2. Loan Number
        3. Consent Type (if mentioned as email or mobile/phone/cell)
        4. Consent Status (Opt-in/Opt-out)
        5. Today's date

        Transcript:
        {transcript}

        Return ONLY a JSON object with these exact keys:
        customer_name, loan_number, consent_type, consent_status, call_date
        """

        response = model.generate_content(prompt)
        print(f"Gemini Response: {response.text}")  # Debug logging
        
        # Extract JSON from response
        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:-3]  # Remove ```json and ``` markers
        
        analysis = json.loads(content)
        return analysis

    except Exception as e:
        print(f"LLM Analysis error: {str(e)}")
        return {
            "customer_name": "Unknown",
            "loan_number": "Unknown",
            "consent_type": "Unknown",
            "consent_status": "Unknown",
            "call_date": datetime.now().isoformat()
        }
    
#acc_number phone_number consent_flag
#transcript print on ui
#speech validation -> handle incident/ and for genuine customer
#rag
#email to back-office/and email to customer to validate
#create a request ticket
#sms for confirmation