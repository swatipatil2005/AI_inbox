import os
import json
import time
import xml.etree.ElementTree as ET
from flask import Flask, redirect, request, session, url_for, render_template_string
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import google.generativeai as genai

# --- 1. CONFIGURATION ---
app = Flask(__name__)
# This secret key is needed for 'session' to work
app.secret_key = 'some-random-secret-key-please-change-this' 
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
CLIENT_SECRETS_FILE = 'client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# --- 2. GEMINI API SETUP ---
#
# IMPORTANT: PASTE YOUR 2 VALUES HERE
#
# (1) This is the key you got from Google AI Studio
# (1) This key will be read from Render's Environment Variables
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # (2) This is the model name we found with check_models.py
    model = genai.GenerativeModel('models/gemini-2.5-flash') 
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    model = None
    

# --- 3. HTML TEMPLATES (Our "Website") ---

# This is the new, creative login page
HTML_HOME = """
<html>
<head>
    <title>Email and SMS Summarizer</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            color: #333;
        }
        .container {
            text-align: center;
            background: #ffffff;
            padding: 40px 50px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            max-width: 450px;
        }
        h1 {
            font-size: 2.2rem;
            margin-bottom: 10px;
        }
        p {
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 30px;
        }
        .button {
            display: inline-block;
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .login-btn {
            background-color: #4285F4; /* Google Blue */
            color: #fff;
        }
        .login-btn:hover {
            background-color: #357ae8;
        }
        .summaries-btn {
            background-color: #00c853; /* Green */
            color: #fff;
            margin-bottom: 20px;
        }
        .summaries-btn:hover {
            background-color: #00b04a;
        }
        .logout-link {
            color: #999;
            font-size: 0.9rem;
            text-decoration: none;
        }
        .logout-link:hover {
            text-decoration: underline;
        }

        .sms-btn {
            background-color: #00796b; /* Teal */
            color: #fff;
            margin-bottom: 20px;
        }
        .sms-btn:hover {
            background-color: #00695c;
        }
    </style>
</head>
<body>
    <div class="container">
        {% if credentials %}
            <!-- LOGGED IN STATE -->
            <h1>Welcome Back!</h1>
            <p>Ready to check your email and sms priorities?</p>
            <a href="/get-emails" class="button summaries-btn">Get your email Summaries </a>
            <br>
            <a href="/sms" class="button sms-btn">Summarize and priorities your SMS</a>
            <br>
            <a href="/logout" classs="logout-link">Log out</a>
        {% else %}
            <!-- LOGGED OUT STATE (The Login Page) -->
            <h1>Email Summarizer</h1>
            <p>Use AI to summarize and prioritize your inbox.</p>
            <a href="/login" class="button login-btn">Log in with Google</a>
        {% endif %}
    </div>
</body>
</html>
"""

# This is the new, sorted summaries page with TABS
HTML_SUMMARIES = """
<html>
<head>
    <title>Your Summaries</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background-color: #f4f7f6;
            margin: 0;
            padding: 30px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            overflow: hidden; /* Contains the tabs */
        }
        .back-link {
            display: inline-block;
            margin: 20px 30px;
            color: #555;
            text-decoration: none;
        }
        .back-link:hover {
            text-decoration: underline;
        }
        
        /* --- Tab Styles --- */
        .tab-bar {
            display: flex;
            background-color: #eee;
        }
        .tab-button {
            background-color: #eee;
            border: none;
            outline: none;
            cursor: pointer;
            padding: 14px 20px;
            transition: background-color 0.3s;
            font-size: 1rem;
            font-weight: 500;
            color: #555;
            flex-grow: 1;
            text-align: center;
        }
        .tab-button:hover {
            background-color: #ddd;
        }
        /* Active tab button style */
        .tab-button.active {
            background-color: #fff;
            color: #D32F2F;
            border-bottom: 3px solid #D32F2F;
        }
        /* Color themes for other tabs */
        .tab-button.medium.active {
            color: #F57C00;
            border-bottom-color: #F57C00;
        }
        .tab-button.low.active {
            color: #388E3C;
            border-bottom-color: #388E3C;
        }

        .tab-button.alert.active {
            color: #0288D1; /* A nice blue */
            border-bottom-color: #0288D1;
        }

        /* --- Tab Content --- */
        .tab-content {
            padding: 20px 30px;
            display: none; /* Hide all tabs by default */
            animation: fadeIn 0.5s;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .email { 
            background: #f9f9f9;
            border: 1px solid #e0e0e0; 
            padding: 15px 20px; 
            margin-bottom: 15px; 
            border-radius: 8px; 
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">&larr; Go Back</a>
        
        <!-- The Tab Bar -->
        <div class="tab-bar">
            <button class="tab-button high active" onclick="openTab(event, 'High')">🔥 High Priority</button>
            <button class="tab-button medium" onclick="openTab(event, 'Medium')">🟠 Medium Priority</button>
            <button class="tab-button low" onclick="openTab(event, 'Low')">🟢 Low Priority</button>
            <button class="tab-button alert" onclick="openTab(event, 'Alert')">🔔 Alerts</button>  </div>
        </div>

        <!-- Tab Content for High Priority -->
        <div id="High" class="tab-content" style="display: block;">
            <h2>High Priority</h2>
            {% if high_priority %}
                {% for email in high_priority %}
                    <div class="email">{{ email | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No high priority emails found.</p>
            {% endif %}
        </div>

        <!-- Tab Content for Medium Priority -->
        <div id="Medium" class="tab-content">
            <h2>Medium Priority</h2>
            {% if medium_priority %}
                {% for email in medium_priority %}
                    <div class="email">{{ email | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No medium priority emails found.</p>
            {% endif %}
        </div>

        <!-- Tab Content for Low Priority -->
        <div id="Low" class="tab-content">
            <h2>Low Priority</h2>
            {% if low_priority %}
                {% for email in low_priority %}
                    <div class="email">{{ email | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No low priority emails found.</p>
            {% endif %}
        </div>

        <div id="Alert" class="tab-content">
            <h2>Alerts &amp; Notifications</h2>
            {% if alerts %}
                {% for email in alerts %}
                    <div class="email">{{ email | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No alerts or notifications found.</p>
            {% endif %}
        </div>
    </div>

    <!-- The JavaScript to make tabs work -->
    <script>
        function openTab(evt, tabName) {
            // Get all tab content elements and hide them
            let tabContent = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabContent.length; i++) {
                tabContent[i].style.display = "none";
            }

            // Get all tab button elements and remove the "active" class
            let tabButtons = document.getElementsByClassName("tab-button");
            for (let i = 0; i < tabButtons.length; i++) {
                tabButtons[i].className = tabButtons[i].className.replace(" active", "");
            }

            // Show the current tab, and add an "active" class to the button that opened the tab
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }
    </script>
</body>
</html>
"""

# --- 4. FLASK ROUTES (The App's "Pages") ---

@app.route('/')
def index():
    if 'credentials' in session:
        return render_template_string(HTML_HOME, credentials=True)
    return render_template_string(HTML_HOME, credentials=False)

@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('callback', _external=True)
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='select_account') # <-- This forces the account chooser
    
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('callback', _external=True)
    
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    return redirect(url_for('index'))


@app.route('/get-emails')
def get_emails():
    """Fetches, summarizes, and displays emails, sorted by priority."""
    if 'credentials' not in session:
        return redirect(url_for('login'))
        
    if not model:
        return "Gemini AI model is not configured. Check your API key and model name in app.py."

    # --- 1. Create lists to hold sorted emails ---
    high_priority_emails = []
    medium_priority_emails = []
    low_priority_emails = []
    alert_emails = []

    try:
        creds = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=creds)
        
        # Get 20 most recent emails from the INBOX (read or unread)
        result = service.users().messages().list(
            userId='me', 
            labelIds=['INBOX'], 
            maxResults=20
        ).execute()
        
        messages = result.get('messages', [])
    
    except Exception as e:
        return f"An error occurred fetching emails from GMail: {e}"
    
    if not messages:
        return render_template_string(
            HTML_SUMMARIES, 
            high_priority=[], 
            medium_priority=[], 
            low_priority=["No emails found in your inbox."]
        )
        
    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            
            sender = ""
            for header in msg_data['payload']['headers']:
                if header['name'] == 'From':
                    sender = header['value']
                    break
            
            snippet = msg_data['snippet']
            
            # --- 2. Ask the AI for JSON, not plain text ---
            prompt = f"""
            Analyze the following email snippet and sender.
            First, check if it is an urgent notification (like a bank alert, 2FA code, password reset, or payment confirmation). If it is, classify it as "Alert".
            
            If it is not an Alert, then classify its priority as "High", "Medium", or "Low" based on its general importance.

            Respond ONLY with a valid JSON object in this format:
            {{"priority": "Alert" or "High" or "Medium" or "Low", "from": "Sender Name", "summary": "One-sentence summary"}}
            
            ---
            Email from: {sender}
            Snippet: {snippet}
            ---
            """
            
            response = model.generate_content(prompt)
            
            # Clean up the response to make sure it's valid JSON
            clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
            
            # Parse the JSON string into a Python dictionary
            data = json.loads(clean_json_str)
            
            # Get the data from the dictionary
            priority = data.get('priority', 'Low').lower()
            from_sender = data.get('from', sender) # Use AI's "from" or our "from"
            summary = data.get('summary', 'Could not summarize.')

            # Format the email as an HTML string
            email_html = f"<b>From:</b> {from_sender}<br><b>Summary:</b> {summary}"

            # --- 3. Sort the email into the correct list ---
            if priority == 'alert':
                alert_emails.append(email_html)
            elif priority == 'high':
                high_priority_emails.append(email_html)
            elif priority == 'medium':
                medium_priority_emails.append(email_html)
            else:
                low_priority_emails.append(email_html)

        except Exception as e:
            # If AI or JSON fails, just put it in "Low" priority
            error_html = f"<b>Error processing email:</b> {e}<br><b>Snippet:</b> {snippet}"
            low_priority_emails.append(error_html)
            time.sleep(6)

    # --- 4. Render the new HTML template with the 3 sorted lists ---
    return render_template_string(
        HTML_SUMMARIES, 
        high_priority=high_priority_emails, 
        medium_priority=medium_priority_emails, 
        low_priority=low_priority_emails,
        alerts=alert_emails
    )

# --- 5. NEW SMS FEATURE CODE ---

# This is the HTML for the SMS upload page
HTML_SMS_UPLOAD = """
<html>
<head>
    <title>SMS Summarizer</title>
    <style>
        /* (This is the same style as your other pages) */
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
            background-color: #f4f7f6;
            margin: 0;
            padding: 30px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 90vh;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            padding: 40px;
            text-align: center;
        }
        .upload-form {
            margin-top: 20px;
        }
        input[type="file"] {
            margin-bottom: 20px;
        }
        .button {
            display: inline-block;
            padding: 15px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            cursor: pointer;
            border: none;
            background-color: #00796b;
            color: white;
        }
        .button:hover {
            background-color: #00695c;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #555;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Upload Your SMS File</h1>
        <p>Please upload your <code>.xml</code> file from your SMS backup.</p>
        <form action="/process-sms" method="post" enctype="multipart/form-data" class="upload-form">
            <input type="file" name="sms_file" accept=".xml" required>
            <br>
            <button type="submit" class="button">Summarize My SMS</button>
        </form>
        <a href="/" class="back-link">&larr; Go Back Home</a>
    </div>
</body>
</html>
"""

# This is the HTML for the SMS *results* page (copied from your email one)
HTML_SMS_SUMMARIES = """
<html>
<head>
    <title>Your SMS Summaries</title>
    <style>
        /* ... (Same CSS as HTML_SUMMARIES) ... */
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 30px; }
        .container { max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); overflow: hidden; }
        .back-link { display: inline-block; margin: 20px 30px; color: #555; text-decoration: none; }
        .back-link:hover { text-decoration: underline; }
        .tab-bar { display: flex; background-color: #eee; }
        .tab-button { background-color: #eee; border: none; outline: none; cursor: pointer; padding: 14px 20px; transition: background-color 0.3s; font-size: 1rem; font-weight: 500; color: #555; flex-grow: 1; text-align: center; }
        .tab-button:hover { background-color: #ddd; }
        .tab-button.active { background-color: #fff; color: #D32F2F; border-bottom: 3px solid #D32F2F; }
        .tab-button.medium.active { color: #F57C00; border-bottom-color: #F57C00; }
        .tab-button.low.active { color: #388E3C; border-bottom-color: #388E3C; }
        .tab-content { padding: 20px 30px; display: none; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .email { background: #f9f9f9; border: 1px solid #e0e0e0; padding: 15px 20px; margin-bottom: 15px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">&larr; Go Back Home</a>
        
        <div class="tab-bar">
            <button class="tab-button high active" onclick="openTab(event, 'Urgent')">🔥 Urgent</button>
            <button class="tab-button medium" onclick="openTab(event, 'Important')">🟠 Important</button>
            <button class="tab-button low" onclick="openTab(event, 'Other')">🟢 Other</button>
        </div>

        <div id="Urgent" class="tab-content" style="display: block;">
            <h2>Urgent</h2>
            {% if urgent %}
                {% for sms in urgent %}
                    <div class="email">{{ sms | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No urgent messages found.</p>
            {% endif %}
        </div>

        <div id="Important" class="tab-content">
            <h2>Important</h2>
            {% if important %}
                {% for sms in important %}
                    <div class="email">{{ sms | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No important messages found.</p>
            {% endif %}
        </div>

        <div id="Other" class="tab-content">
            <h2>Other</h2>
            {% if other %}
                {% for sms in other %}
                    <div class="email">{{ sms | safe }}</div>
                {% endfor %}
            {% else %}
                <p>No other messages found.</p>
            {% endif %}
        </div>
    </div>

    <script>
        function openTab(evt, tabName) {
            let tabContent = document.getElementsByClassName("tab-content");
            for (let i = 0; i < tabContent.length; i++) {
                tabContent[i].style.display = "none";
            }
            let tabButtons = document.getElementsByClassName("tab-button");
            for (let i = 0; i < tabButtons.length; i++) {
                tabButtons[i].className = tabButtons[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }
    </script>
</body>
</html>
"""

# This new route shows the upload page
@app.route('/sms')
def sms_page():
    # We must be logged in to use the Gemini AI
    if 'credentials' not in session:
        return redirect(url_for('login'))
    return render_template_string(HTML_SMS_UPLOAD)


# This new route *handles* the file upload and processing
@app.route('/process-sms', methods=['POST'])
def process_sms():
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    if 'sms_file' not in request.files:
        return "No file uploaded.", 400
        
    file = request.files['sms_file']
    if file.filename == '':
        return "No file selected.", 400
        
    if not model:
        return "Gemini AI model is not configured. Check your API key."

    # Create lists to hold sorted SMS
    urgent_sms = []
    important_sms = []
    other_sms = []
    
    sms_limit = 20 # Let's only process 10 to keep it fast
    sms_count = 0

    try:
        # Read the file and parse the XML
        tree = ET.parse(file.stream)
        root = tree.getroot()
        
        # This loops through each <sms> tag in your .xml file
        # (This assumes the common "SMS Backup & Restore" format)
        for msg in root.iter('sms'):
            if sms_count >= sms_limit:
                break # Stop after we hit our limit
                
            try:
                sender = msg.get('address', 'Unknown')
                body = msg.get('body', 'No content')
                
                # --- Ask the AI to classify the SMS ---
                prompt = f"""
                Analyze the following SMS message. Classify its priority as "Urgent" (e.g., 2FA codes, bank alerts, emergency), "Important" (e.g., personal conversation, plans), or "Other" (e.g., spam, marketing, promotions).
                
                Respond ONLY with a valid JSON object in this format:
                {{"priority": "Urgent" or "Important" or "Other", "from": "Sender", "summary": "One-sentence summary"}}
                
                ---
                From: {sender}
                Message: {body}
                ---
                """
                
                response = model.generate_content(prompt)
                clean_json_str = response.text.strip().replace("```json", "").replace("```", "")
                data = json.loads(clean_json_str)
                
                priority = data.get('priority', 'Other').lower()
                from_sender = data.get('from', sender)
                summary = data.get('summary', 'Could not summarize.')

                sms_html = f"<b>From:</b> {from_sender}<br><b>Summary:</b> {summary}"

                # --- Sort the SMS into the correct list ---
                if priority == 'urgent':
                    urgent_sms.append(sms_html)
                elif priority == 'important':
                    important_sms.append(sms_html)
                else:
                    other_sms.append(sms_html)
                
                time.sleep(6) # --- RATE LIMITING ---
                sms_count += 1

            except Exception as e:
                error_html = f"<b>Error processing SMS:</b> {e}<br><b>From:</b> {sender}"
                other_sms.append(error_html)
                time.sleep(6) # --- RATE LIMITING ---
                sms_count += 1
                
    except Exception as e:
        return f"Error reading XML file. Is it a valid SMS backup? Error: {e}"

    # --- Render the new HTML template with the 3 sorted lists ---
    return render_template_string(
        HTML_SMS_SUMMARIES, 
        urgent=urgent_sms, 
        important=important_sms, 
        other=other_sms
    )

# --- 5. RUN THE APP ---
if __name__ == '__main__':
    app.run(port=5000, debug=True)
