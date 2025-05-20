## Setup Instructions

### Prerequisites
- Python 3.x
- Visual Studio Code
- Twilio Account
- ngrok for local development

### Installation

# Create project directory
mkdir ivr
cd ivr

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Install Dependencies
pip install flask twilio python-dotenv SpeechRecognition

# Environment Configuration
# Create a .env file in project root:
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here

# Install ngrok

Download ngrok from https://ngrok.com/download
Extract to C:\Program Files\ngrok
Add to System PATH:
Open Windows Settings
Search for "Environment Variables"
Edit System Environment Variables
Add ngrok path to System Variables > Path
Set up authentication:
ngrok config add-authtoken your-auth-token-here

Run the Application
Set Flask environment variables

set FLASK_APP=app.py
set FLASK_ENV=development

# Run Flask application
flask run

# Start ngrok Tunnel:
In a new terminal:
ngrok http 5000

