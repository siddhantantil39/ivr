import os
import json
import time
import sqlite3
import re
from datetime import datetime
from flask import Flask, request, jsonify
import speech_recognition as sr
from twilio.twiml.voice_response import VoiceResponse, Gather
from dotenv import load_dotenv
load_dotenv()

# Initialize Twilio client
from twilio.rest import Client
client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)

app = Flask(__name__)

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
        status TEXT DEFAULT 'new'
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# Main IVR entry point
@app.route("/incoming_call", methods=['GET', 'POST'])
def incoming_call():
    response = VoiceResponse()
    response.say("Thank you for calling customer support. This call may be recorded for quality assurance purposes.")
    
    gather = Gather(num_digits=1, action='/menu_selection', method='POST')
    gather.say("For account inquiries, press 1. For technical support, press 2. For billing questions, press 3. For all other inquiries, press 4.")
    response.append(gather)
    
    # If no input received, retry
    response.redirect('/incoming_call')
    
    return str(response)

# Process menu selection
@app.route("/menu_selection", methods=['POST'])
def menu_selection():
    selected_option = request.form.get('Digits', None)
    call_sid = request.form.get('CallSid')
    caller = request.form.get('From')
    
    response = VoiceResponse()
    
    # Store initial call information
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO calls (call_sid, caller_number, timestamp, issue_type) VALUES (?, ?, ?, ?)",
        (call_sid, caller, datetime.now().isoformat(), get_issue_type(selected_option))
    )
    conn.commit()
    conn.close()
    
    if selected_option == '1':
        gather = Gather(input='speech', action='/collect_account_info', method='POST')
        gather.say("Please say your full name followed by your account number.")
        response.append(gather)
    elif selected_option == '2':
        gather = Gather(input='speech', action='/collect_technical_issue', method='POST')
        gather.say("Please describe your technical issue in detail.")
        response.append(gather)
    elif selected_option == '3':
        gather = Gather(input='speech', action='/collect_billing_issue', method='POST')
        gather.say("Please describe your billing question or concern.")
        response.append(gather)
    else:
        gather = Gather(input='speech', action='/collect_other_issue', method='POST')
        gather.say("Please describe how we can assist you today.")
        response.append(gather)
    
    return str(response)

# Helper function to convert menu selection to issue type
def get_issue_type(digit):
    issue_types = {
        '1': 'Account Inquiry',
        '2': 'Technical Support',
        '3': 'Billing Question',
        '4': 'Other'
    }
    return issue_types.get(digit, 'Unknown')

# Process account information
@app.route("/collect_account_info", methods=['POST'])
def collect_account_info():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    response = VoiceResponse()
    
    # Extract name and account number
    extract_and_store_account_info(call_sid, speech_result)
    
    gather = Gather(input='speech', action='/collect_technical_issue', method='POST')
    gather.say("Thank you. Please describe your account-related issue.")
    response.append(gather)
    
    return str(response)

# Extract name and account number using pattern matching
def extract_and_store_account_info(call_sid, speech_text):
    # Basic pattern for a name followed by numbers
    # This is simplified and might need refinement based on your specific needs
    name_match = re.search(r'^([\w\s]+?)(?=\d)', speech_text)
    account_match = re.search(r'^[1-9][0-9]{9}$', speech_text)  # Looking for 10 digit sequences
    
    # use llm to get account name from sequence
    name = name_match.group(1).strip() if name_match else "Unknown"
    account = account_match.group(1) if account_match else "Unknown"
    
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET customer_name = ?, account_number = ? WHERE call_sid = ?",
        (name, account, call_sid)
    )
    conn.commit()
    conn.close()

# Process technical issues
@app.route("/collect_technical_issue", methods=['POST'])
def collect_technical_issue():
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult', '')
    
    # Store the issue description
    store_issue_description(call_sid, speech_result)
    
    response = VoiceResponse()
    gather = Gather(num_digits=1, action='/collect_priority', method='POST')
    gather.say("Thank you for providing that information. On a scale of 1 to 3, with 1 being urgent and 3 being non-urgent, how would you rate the priority of this issue?")
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
    call_sid = request.form.get('CallSid')
    digit = request.form.get('Digits', '3')
    
    priority_mapping = {
        '1': 'Urgent',
        '2': 'Medium',
        '3': 'Low'
    }
    
    priority = priority_mapping.get(digit, 'Low')
    
    # Store priority
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET priority = ? WHERE call_sid = ?",
        (priority, call_sid)
    )
    conn.commit()
    conn.close()
    
    response = VoiceResponse()
    response.say("Thank you for providing that information. A representative will assist you shortly.")
    response.record(max_length=300, action='/process_complete_call')
    
    return str(response)

# Process the complete call recording and transcript
@app.route("/process_complete_call", methods=['POST'])
def process_complete_call():
    call_sid = request.form.get('CallSid')
    recording_url = request.form.get('RecordingUrl')
    
    # In a real system, you would download the recording and process it
    # Here we'll simulate getting a full transcript
    full_transcript = simulate_transcription(recording_url)
    
    # Store the full transcript
    conn = sqlite3.connect('call_data.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE calls SET full_transcript = ? WHERE call_sid = ?",
        (full_transcript, call_sid)
    )
    conn.commit()
    conn.close()
    
    # Process the transcript to extract any missing information
    extract_missing_information(call_sid, full_transcript)
    
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

if __name__ == "__main__":
    app.run(debug=True, port=5000)