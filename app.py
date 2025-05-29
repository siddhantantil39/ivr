import os
import json
import time
import sqlite3
import re
import random
import string
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import speech_recognition as sr
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv
from ai_service import analyze_transcript_with_llm
from twilio.base.exceptions import TwilioRestException  
from flask import url_for
from dialer_file_processor import process_consent_data

# Initialize Twilio client
from twilio.rest import Client
import logging
client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

app = Flask(__name__)

SPEECH_CONFIDENCE_THRESHOLD = 0.6

call_transcripts = {}  # Format: {call_sid: transcript_text}

@app.errorhandler(404)
def not_found_error(error):
    print("Error: {}".format(error))
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Initialize database
def init_db():
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_sid TEXT,
        caller_number TEXT,
        timestamp TEXT,
        full_transcript TEXT,
        customer_name TEXT,
        account_number TEXT,
        issue_type TEXT,
        issue_description TEXT,
        priority TEXT,
        status TEXT DEFAULT 'new',
        consent_type TEXT,  -- Add this column
        consent_status TEXT  -- Add this column
    )
    ''')
    
    # Add OTP table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS otp_verification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT,
        otp TEXT,
        created_at TEXT,
        verified BOOLEAN DEFAULT FALSE
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# Main IVR entry point
@app.route("/incoming_call", methods=['GET', 'POST'])
def incoming_call():
    caller = request.form.get('From')
    call_sid = request.form.get('CallSid')
    
    # Initialize empty transcript for this call
    call_transcripts[call_sid] = ""

    if caller and caller.startswith("client:"):
        default_number = os.getenv('DEFAULT_CALLER_NUMBER', '+1234567890')
        print(f"Client caller detected, using default number: {default_number}")
        caller = default_number
        # Add to transcript
        call_transcripts[call_sid] += f"Client caller, using number: {default_number}\n"
    elif not caller:
        print("No caller number received")
        caller = os.getenv('DEFAULT_CALLER_NUMBER', '+1234567890')
        call_transcripts[call_sid] += f"No caller ID, using default: {caller}\n"
    
    call_sid = request.form.get('CallSid')
    call_transcripts[call_sid]+=call_sid

    response = VoiceResponse()
    caller = request.form.get('From')

    
    # Debug: Print caller number format
    print(f"Received call from: {caller}")
    
    # Handle case where caller number is not provided
    if not caller:
        print("No caller number received")
        response.say("We're unable to verify your number. Please ensure you're not blocking your caller ID.")
        response.hangup()
        return str(response)
    
    # Generate and store OTP
    otp = generate_otp()
    store_otp(caller, otp)
    
    try:
        # Debug: Print Twilio configuration
        print(f"Using Twilio number: {os.getenv('TWILIO_PHONE_NUMBER')}")
        print(f"Account SID length: {len(os.getenv('TWILIO_ACCOUNT_SID'))}")
        print(f"Auth Token length: {len(os.getenv('TWILIO_AUTH_TOKEN'))}")
        
        # Verify phone number format
        caller = f"+{caller}" if not caller.startswith('+') else caller
        
        # Send SMS
        # message = client.messages.create(
        #     to="+918130773883",
        #     from_=os.getenv('TWILIO_PHONE_NUMBER'),
        #     body=f"Your IVR authentication code is: {otp}"
        # )
        
        # # Debug: Print message SID if successful
        # print(f"Message sent successfully with SID: {message.sid}")
        
    except TwilioRestException as e:
        print(f"Twilio Error Code: {e.code}")
        print(f"Twilio Error Message: {e.msg}")
        
        error_messages = {
            21211: "Invalid 'To' phone number",
            21606: "The 'From' phone number is not a valid SMS-enabled Twilio number",
            20003: "Authentication error - check credentials",
            20404: "Resource not found - check phone numbers"
        }
        
        error_msg = error_messages.get(e.code, "Unknown error")
        print(f"Interpreted error: {error_msg}")
        
        response.say(f"We encountered a technical issue: {error_msg}. Please try again later.")
        response.hangup()
        return str(response)
    
    gather = Gather(num_digits=1, action='/menu_selection', method='POST')
    gather.say("Authentication successful. For account inquiries, press 1. For technical support, press 2. For billing questions, press 3. For all other inquiries, press 4.")
    response.append(gather)
        
    # Continue with normal flow if SMS sent successfully
    # gather = Gather(
    #     num_digits=6, 
    #     action='/verify_otp', 
    #     method='POST',
    #     timeout=200,  # Extend timeout to 30 seconds
    #     finish_on_key='#'  # Allow user to submit early with #
    # )
    # gather.say("Please enter the 6-digit code sent to your phone, then press pound.")
    # response.append(gather)

        
    return str(response)

# Verify OTP and route to menu selection
@app.route("/verify_otp", methods=['POST'])
def verify_otp_route():
    caller = request.form.get('From')
    entered_otp = request.form.get('Digits')
    
    response = VoiceResponse()
    
    if verify_otp(caller, entered_otp):
        # Continue with main menu
        gather = Gather(num_digits=1, action='/menu_selection', method='POST')
        gather.say("Authentication successful. For account inquiries, press 1. For technical support, press 2. For billing questions, press 3. For all other inquiries, press 4.")
        response.append(gather)
    else:
        # Failed verification
        response.say("Invalid or expired code. Please call again.")
        response.hangup()
    
    return str(response)

# Process menu selection
@app.route("/menu_selection", methods=['POST'])
def menu_selection():
    print("\n=== Menu Selection ===")
    selected_option = request.form.get('Digits', None)
    call_sid = request.form.get('CallSid')
    caller = request.form.get('From')
    
    print(f"Selected Option: {selected_option}")
    print(f"CallSid: {call_sid}")
    
    response = VoiceResponse()
    
    if selected_option == '1':
        print("Selected account inquiry")
        gather = Gather(
            input='speech',
            action='/collect_account_info',
            method='POST',
            language='en-IN',
            speech_model='phone_call',
            timeout=10,
            speech_timeout='auto'
        )
        gather.say(
            "Please say your full name followed by your account number.",
            voice='Polly.Raveena',
            language='en-IN'
        )
        response.append(gather)
    
    print("Sending response from menu_selection")
    return str(response)

# Update collect_account_info route for debug
@app.route("/collect_account_info", methods=['POST'])
def collect_account_info():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Append to transcript
    if call_sid in call_transcripts:
        call_transcripts[call_sid] += f"User: {speech_result}\n"
    
    print(f"Current transcript: {call_transcripts.get(call_sid, '')}")

    
    response = VoiceResponse()
    gather = create_gather(
        '/collect_technical_issue',
        "Thank you. Please describe your account-related issue.",
        input_type='speech'
    )
    response.append(gather)
    return str(response)

# Process technical issues
@app.route("/collect_technical_issue", methods=['POST'])
def collect_technical_issue():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    if call_sid in call_transcripts:
        call_transcripts[call_sid] += f"Technical issue: {speech_result}\n"
    
    print(f"Current transcript: {call_transcripts.get(call_sid, '')}")
    
    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/collect_priority', method='POST')
    gather.say("Thank you. On a scale of 1 to 3, with 1 being urgent and 3 being non-urgent, how would you rate this issue?")
    response.append(gather)
    return str(response)

# Process billing issues
@app.route("/collect_billing_issue", methods=['POST'])
def collect_billing_issue():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Store the issue description
    store_issue_description(call_sid, speech_result)
    
    response = VoiceResponse()
    gather = Gather(input='speech', action='/collect_account_for_billing', method='POST')
    gather.say("Thank you for describing your billing issue. Please provide your account number so we can locate your billing information.")
    response.append(gather)
    
    return str(response)

# Process other issues
@app.route("/collect_other_issue", methods=['POST'])
def collect_other_issue():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Store the issue description
    store_issue_description(call_sid, speech_result)
    
    response = VoiceResponse()
    gather = Gather(input='speech', action='/collect_name', method='POST')
    gather.say("Thank you for describing your issue. Please tell us your full name.")
    response.append(gather)
    
    return str(response)

# Store issue description
def store_issue_description(call_sid, description):
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET issue_description = ? WHERE call_sid = ?",
        (description, call_sid)
    )
    conn.commit()
    conn.close()

# Collect account number for billing issues
@app.route("/collect_account_for_billing", methods=['POST'])
def collect_account_for_billing():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Extract account number
    account_match = re.search(r'(\d{4,})', speech_result)
    account = account_match.group(1) if account_match else "Unknown"
    
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET account_number = ? WHERE call_sid = ?",
        (account, call_sid)
    )
    conn.commit()
    conn.close()
    
    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/collect_priority', method='POST')
    gather.say("Thank you. On a scale of 1 to 3, with 1 being urgent and 3 being non-urgent, how would you rate the priority of this billing issue?")
    response.append(gather)
    
    return str(response)

# Collect name for other issues
@app.route("/collect_name", methods=['POST'])
def collect_name():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Store the name
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET customer_name = ? WHERE call_sid = ?",
        (speech_result.strip(), call_sid)
    )
    conn.commit()
    conn.close()
    
    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/collect_priority', method='POST')
    gather.say("Thank you. On a scale of 1 to 3, with 1 being urgent and 3 being non-urgent, how would you rate the priority of your issue?")
    response.append(gather)
    
    return str(response)

# Collect priority information
@app.route("/collect_priority", methods=['POST'])
def collect_priority():
    try:
        print("\n=== Collect Priority ===")
        call_sid = request.form.get('CallSid')
        digit = request.form.get('Digits', '3')
        
        print(f"Call SID: {call_sid}")
        print(f"Priority Digit: {digit}")
        
        priority_mapping = {
            '1': 'Urgent',
            '2': 'Medium',
            '3': 'Low'
        }
        
        priority = priority_mapping.get(digit, 'Low')
        print(f"Mapped Priority: {priority}")
        
        if call_sid in call_transcripts:
            # Fix: Use dictionary access instead of calling it as a function
            call_transcripts[call_sid] += f"Priority: {priority}\n"
    
        print(f"Current transcript: {call_transcripts.get(call_sid, '')}")
        
        response = VoiceResponse()
        response.say("Thank you for providing that information. We will register the issue.")
        response.record(max_length=300, action='/process_complete_call')
        
        print("Sending response from collect_priority")
        return str(response)
        
    except Exception as e:
        print(f"Error in collect_priority: {str(e)}")
        response = VoiceResponse()
        response.say("We encountered a technical issue. Please try your call again.")
        response.hangup()
        return str(response)

# Process the complete call recording and transcript
@app.route("/process_complete_call", methods=['POST'])
def process_complete_call():
    call_sid = request.form.get('CallSid')
    caller = request.form.get('From')

    if caller and caller.startswith("client:"):
        default_number = os.getenv('DEFAULT_CALLER_NUMBER', '+1234567890')
        print(f"Client caller detected, using default number: {default_number}")
        caller = default_number
    
    if call_sid in call_transcripts:
        try:
            # Get the full transcript
            transcript = call_transcripts[call_sid]
            
            # Analyze with LLM
            analysis = analyze_transcript_with_llm(transcript)
            print("LLM Analysis:", analysis)
            
            # Store in database
            conn = sqlite3.connect('call_data.db')
            cursor = conn.cursor()
            
            # Insert or update the call record
            cursor.execute('''
                INSERT OR REPLACE INTO calls (
                    call_sid, 
                    caller_number,
                    timestamp,
                    full_transcript,
                    customer_name,
                    account_number,
                    issue_type,
                    issue_description,
                    priority,
                    status,
                    consent_type,
                    consent_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                call_sid,
                caller,
                datetime.now().isoformat(),
                transcript,
                analysis.get('customer_name', 'Unknown'),
                analysis.get('loan_number', 'Unknown'),
                'consent',
                transcript,
                'Low',
                'new',
                analysis.get('consent_type', 'Unknown'),
                analysis.get('consent_status', 'Unknown')
            ))
            
            conn.commit()
            print(f"Saved call data for SID: {call_sid}")
            
            # Process consent data and update file
            try:
                process_consent_data()
                print("Consent data processed and file updated")
            except Exception as e:
                print(f"Error processing consent data: {str(e)}")
            
            # Clean up
            conn.close()
            del call_transcripts[call_sid]
            
        except Exception as e:
            print(f"Error processing call: {str(e)}")
    
    response = VoiceResponse()
    response.say("Thank you for calling. Your information has been recorded. Goodbye.")
    response.hangup()
    return str(response)

# Simulate transcription (in production, you would use a real transcription service)
def simulate_transcription(recording_url):
    # This is a placeholder. In a real application, you would:
    # 1. Download the recording
    # 2. Use a speech-to-text service like Google's Speech-to-Text API
    return f"This is a simulated transcript of the call. In a real application, this would contain the actual transcribed content of the call recording."

# Extract any missing information from the full transcript
def extract_missing_information(call_sid, transcript):
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    
    # Get current call data
    cursor.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,))
    call_data = cursor.fetchone()
    
    # This would be more sophisticated in a real application
    # Here we're just doing some basic checks
    if call_data[4] == "Unknown" or not call_data[4]:  # customer_name
        # Try to extract name using more sophisticated patterns
        name_match = re.search(r'my name is ([\w\s]+)', transcript, re.IGNORECASE)
        if name_match:
            cursor.execute(
                "UPDATE calls SET customer_name = ? WHERE call_sid = ?",
                (name_match.group(1).strip(), call_sid)
            )
    
    if call_data[5] == "Unknown" or not call_data[5]:  # account_number
        # Try to extract account number
        account_match = re.search(r'account (?:number|#)?\s*(?:is|:)?\s*(\d{4,})', transcript, re.IGNORECASE)
        if account_match:
            cursor.execute(
                "UPDATE calls SET account_number = ? WHERE call_sid = ?",
                (account_match.group(1), call_sid)
            )
    
    conn.commit()
    conn.close()

# Admin API to get call data
@app.route("/api/calls", methods=['GET'])
def get_calls():
    conn = sqlite3.connect('call_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM calls ORDER BY timestamp DESC")
    calls = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(calls)

# Admin API to get a specific call
@app.route("/api/calls/<call_id>", methods=['GET'])
def get_call(call_id):
    conn = sqlite3.connect('call_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM calls WHERE id = ?", (call_id,))
    call = dict(cursor.fetchone())
    
    conn.close()
    return jsonify(call)

# Admin API to update call status
@app.route("/api/calls/<call_id>/status", methods=['PUT'])
def update_call_status(call_id):
    data = request.json
    new_status = data.get('status')
    
    if not new_status:
        return jsonify({"error": "No status provided"}), 400
    
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET status = ? WHERE id = ?",
        (new_status, call_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def store_otp(phone_number, otp):
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO otp_verification (phone_number, otp, created_at) VALUES (?, ?, ?)",
        (phone_number, otp, created_at)
    )
    conn.commit()
    conn.close()

def verify_otp(phone_number, otp):
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    # Check OTP within last 5 minutes
    five_mins_ago = (datetime.now() - timedelta(minutes=5)).isoformat()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Attempting OTP verification for phone: {phone_number}")
        
        cursor.execute(
            """SELECT * FROM otp_verification 
               WHERE phone_number = ? AND otp = ? AND created_at > ? 
               AND verified = FALSE""",
            (phone_number, otp, five_mins_ago)
        )
        result = cursor.fetchone()
        
        if result:
            logger.info(f"Valid OTP found for phone: {phone_number}")
            cursor.execute(
                "UPDATE otp_verification SET verified = TRUE WHERE id = ?",
                (result[0],)
            )
            conn.commit()
            conn.close()
            return True
            
        logger.warning(f"Invalid or expired OTP attempt for phone: {phone_number}")
        conn.close()
        return False
        
    except sqlite3.Error as e:
        logger.error(f"Database error during OTP verification: {str(e)}")
        if conn:
            conn.close()
        return False
    except Exception as e:
        logger.error(f"Unexpected error during OTP verification: {str(e)}")
        if conn:
            conn.close()
        return False

def create_gather(action, prompt, input_type='speech'):
    gather = Gather(
        input=input_type,
        action=action,
        method='POST',
        language='en-IN',
        speech_model='phone_call',
        timeout=10,         # Increase timeout
        speech_timeout=3,   # Add specific speech timeout
        hints=[            # Add speech hints
            'account',
            'number',
            'my name is'
        ]
    )
    
    gather.say(
        prompt,
        voice='Polly.Raveena',  
        language='en-IN'
    )
    return gather


if __name__ == "__main__":
    app.run(debug=True, port=5000)