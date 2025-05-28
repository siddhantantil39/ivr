import os
import openai
from datetime import datetime

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

def analyze_transcript_with_llm(transcript):
    try:
        prompt = f"""
        Please analyze the following call transcript and extract:
        1. Customer Name
        2. Loan Number
        3. Consent Type (if mentioned)
        4. Consent Status (Opt-in/Opt-out)
        5. Date of Call

        Transcript:
        {transcript}

        Return the information in JSON format with these exact keys:
        customer_name, loan_number, consent_type, consent_status, call_date
        """

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant analyzing call transcripts."},
                {"role": "user", "content": prompt}
            ]
        )

        # Parse the response
        analysis = json.loads(response.choices[0].message.content)
        return analysis

    except Exception as e:
        print(f"LLM Analysis error: {e}")
        return {
            "customer_name": "Unknown",
            "loan_number": "Unknown",
            "consent_type": "Unknown",
            "consent_status": "Unknown",
            "call_date": datetime.now().isoformat()
        }