import os
import re
import smtplib
import random
import uuid
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
import requests
import threading
import time


app = Flask(__name__)
CORS(app)

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DB = os.getenv('MONGODB_DB', 'support_system')

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
db = mongo_client[MONGODB_DB]
customers_collection = db['customers']
agents_collection = db['agents']
incidents_collection = db['incidents']

CHAT_SESSIONS = {}

# Ensure key uniqueness and common query performance.
try:
    customers_collection.create_index([('customer_id', ASCENDING)], unique=True)
    agents_collection.create_index([('uid', ASCENDING)], unique=True)
    incidents_collection.create_index([('issue_id', ASCENDING)], unique=True)
    incidents_collection.create_index([('customer_id', ASCENDING)])
    incidents_collection.create_index([('assigned_to', ASCENDING)])
    incidents_collection.create_index([('customer_email', ASCENDING)])
    incidents_collection.create_index([('logged_date', DESCENDING)])
except Exception:
    # Allow app startup even if MongoDB is temporarily unavailable.
    pass

STATUS_VALUES = ['New', 'Assigned', 'In Progress', 'Resolved', 'Closed']
SEVERITY_VALUES = ['Low', 'Medium', 'High']


def parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def send_issue_id_email(recipient_email: str, issue_id: str, summary: str):
    # Read configuration
    smtp_host = os.getenv('SMTP_HOST', '').strip()
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '').strip()
    smtp_pass = os.getenv('SMTP_PASS', '')
    if smtp_pass is None:
        smtp_pass = ''
    smtp_pass = smtp_pass.strip()
    # remove surrounding single/double quotes if present (common in .env files)
    if len(smtp_pass) >= 2 and ((smtp_pass[0] == smtp_pass[-1]) and smtp_pass[0] in {'"', "'"}):
        smtp_pass = smtp_pass[1:-1]
    smtp_from = os.getenv('SMTP_FROM', smtp_user).strip()
    smtp_use_tls = parse_bool(os.getenv('SMTP_USE_TLS', 'true'), default=True)
    smtp_use_ssl = parse_bool(os.getenv('SMTP_USE_SSL', 'false'), default=False)
    smtp_timeout = int(os.getenv('SMTP_TIMEOUT', '15'))

    subject = f'Incident Logged: {issue_id}'
    plain_body = (
        f"Your incident has been logged successfully.\n\n"
        f"Issue ID: {issue_id}\n"
        f"Summary: {summary}\n\n"
        "Use this Issue ID or your email to track the incident in the Support Dashboard."
    )

    html_body = f"""
    <html>
      <body>
        <p>Your incident has been logged successfully.</p>
        <h2>Issue ID: {issue_id}</h2>
        <p><strong>Summary:</strong> {summary}</p>
        <p>Use this Issue ID or your email to track the incident in the Support Dashboard.</p>
      </body>
    </html>
    """

    # For real SMTP delivery, ensure required settings exist
    if not smtp_host or not smtp_from:
        raise RuntimeError('SMTP is not configured. Set SMTP_HOST and SMTP_FROM/SMTP_USER.')

    # build email
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = smtp_from
    message['To'] = recipient_email
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype='html')

    # helper: send via sendgrid API
    def send_via_sendgrid(api_key: str) -> bool:
        if not api_key:
            return False
        sg_url = 'https://api.sendgrid.com/v3/mail/send'
        payload = {
            'personalizations': [{'to': [{'email': recipient_email}]}],
            'from': {'email': smtp_from},
            'subject': subject,
            'content': [
                {'type': 'text/plain', 'value': plain_body},
                {'type': 'text/html', 'value': html_body},
            ],
        }
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        resp = requests.post(sg_url, json=payload, headers=headers, timeout=15)
        return resp.status_code in (200, 202)

    # helper: send via mailgun API
    def send_via_mailgun(api_key: str, domain: str) -> bool:
        if not api_key or not domain:
            return False
        mg_url = f'https://api.mailgun.net/v3/{domain}/messages'
        auth = ('api', api_key)
        data = {
            'from': smtp_from,
            'to': recipient_email,
            'subject': subject,
            'text': plain_body,
            'html': html_body,
        }
        resp = requests.post(mg_url, auth=auth, data=data, timeout=15)
        return resp.status_code in (200, 202)

    # First, try SMTP (SSL or STARTTLS). If it fails due to auth, attempt provider fallbacks.
    try:
        if smtp_use_ssl or smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=smtp_timeout) as server:
                if smtp_use_tls:
                    server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.send_message(message)
        return True
    except smtplib.SMTPAuthenticationError as auth_err:
        # Try API provider fallbacks if configured
        sendgrid_key = os.getenv('SENDGRID_API_KEY', '').strip()
        if sendgrid_key:
            try:
                if send_via_sendgrid(sendgrid_key):
                    return True
            except Exception:
                pass

        mailgun_key = os.getenv('MAILGUN_API_KEY', '').strip()
        mailgun_domain = os.getenv('MAILGUN_DOMAIN', '').strip()
        if mailgun_key and mailgun_domain:
            try:
                if send_via_mailgun(mailgun_key, mailgun_domain):
                    return True
            except Exception:
                pass

        # If fallbacks not available or also failed, raise the original auth error
        raise auth_err
    except Exception:
        # For any other SMTP exception, try fallbacks too
        sendgrid_key = os.getenv('SENDGRID_API_KEY', '').strip()
        if sendgrid_key:
            try:
                if send_via_sendgrid(sendgrid_key):
                    return True
            except Exception:
                pass

        mailgun_key = os.getenv('MAILGUN_API_KEY', '').strip()
        mailgun_domain = os.getenv('MAILGUN_DOMAIN', '').strip()
        if mailgun_key and mailgun_domain:
            try:
                if send_via_mailgun(mailgun_key, mailgun_domain):
                    return True
            except Exception:
                pass

        # Re-raise to let caller record the error
        raise


def now_string() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def now_datetime() -> datetime:
    return datetime.utcnow()


def serialize_value(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    return value


def serialize_row(row: dict) -> dict:
    return {k: serialize_value(v) for k, v in row.items()}


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return {}
    output = dict(doc)
    output.pop('_id', None)
    return serialize_row(output)


def normalize_severity(value: str) -> str:
    if not value:
        return ''
    value_map = {
        'low': 'Low',
        'medium': 'Medium',
        'high': 'High',
    }
    return value_map.get(value.strip().lower(), value.strip())


def normalize_status(value: str) -> str:
    if not value:
        return ''
    value_map = {
        'new': 'New',
        'assigned': 'Assigned',
        'in progress': 'In Progress',
        'resolved': 'Resolved',
        'closed': 'Closed',
    }
    return value_map.get(value.strip().lower(), value.strip())


def make_issue_id() -> str:
    while True:
        issue_id = uuid.uuid4().hex[:8].upper()
        if not incidents_collection.find_one({'issue_id': issue_id}, {'_id': 1}):
            return issue_id


def parse_date_only(value: str):
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return None


def agent_projection():
    return {'_id': 0, 'uid': 1, 'name': 1, 'email': 1, 'phone': 1, 'department': 1, 'created_date': 1}


def resolve_agent_for_assignment(assigned_value: str):
    assigned_value = (assigned_value or '').strip()
    if not assigned_value:
        return None

    projection = {'_id': 0, 'uid': 1, 'name': 1, 'department': 1}

    exact_matches = [
        agents_collection.find_one({'uid': assigned_value}, projection),
        agents_collection.find_one({'name': assigned_value}, projection),
        agents_collection.find_one({'department': assigned_value}, projection),
    ]
    for agent in exact_matches:
        if agent:
            return agent

    assigned_lower = assigned_value.lower()
    best_agent = None
    best_score = 0

    for agent in agents_collection.find({}, projection):
        for field in ('uid', 'name', 'department'):
            field_value = (agent.get(field) or '').strip()
            if not field_value:
                continue

            field_lower = field_value.lower()
            if assigned_lower == field_lower:
                return agent

            if assigned_lower in field_lower or field_lower in assigned_lower:
                score = len(field_lower)
                if score > best_score:
                    best_score = score
                    best_agent = agent

    return best_agent


def get_random_agent_uid() -> str | None:
    agents = list(agents_collection.find({}, {'_id': 0, 'uid': 1}).sort([('name', ASCENDING), ('uid', ASCENDING)]))
    if not agents:
        return None
    return random.choice(agents).get('uid')


def migrate_incident_assignments_to_uid() -> None:
    try:
        agents = list(agents_collection.find({}, {'_id': 0, 'uid': 1}).sort([('name', ASCENDING), ('uid', ASCENDING)]))
        agent_uids = [agent.get('uid') for agent in agents if agent.get('uid')]
        if not agent_uids:
            return

        for incident in incidents_collection.find({}, {'_id': 0, 'issue_id': 1, 'assigned_to': 1}):
            assigned_value = (incident.get('assigned_to') or '').strip()
            if assigned_value in agent_uids:
                continue

            new_agent_uid = random.choice(agent_uids)
            incidents_collection.update_one(
                {'issue_id': incident.get('issue_id')},
                {'$set': {'assigned_to': new_agent_uid, 'modified_date': now_datetime()}},
            )
    except Exception:
        # Keep startup resilient even if the backfill cannot run.
        pass


def assignment_allows_agent(assigned_value: str, agent_uid: str) -> bool:
    assigned_value = (assigned_value or '').strip()
    agent_uid = (agent_uid or '').strip()
    if not assigned_value or not agent_uid:
        return False

    agent = agents_collection.find_one({'uid': agent_uid}, {'_id': 0, 'uid': 1, 'name': 1, 'department': 1})
    if not agent:
        return False

    agent_fields = [
        (agent.get('uid') or '').strip(),
        (agent.get('name') or '').strip(),
        (agent.get('department') or '').strip(),
    ]
    assigned_lower = assigned_value.lower()

    for field_value in agent_fields:
        if not field_value:
            continue

        field_lower = field_value.lower()
        if assigned_lower == field_lower:
            return True

        if assigned_lower in field_lower or field_lower in assigned_lower:
            return True

    assigned_tokens = {token for token in re.split(r'[^a-z0-9]+', assigned_lower) if token}
    agent_tokens = set()
    for field_value in agent_fields:
        agent_tokens.update(token for token in re.split(r'[^a-z0-9]+', field_value.lower()) if token)

    return bool(assigned_tokens & agent_tokens)


def get_chat_session(sender: str) -> dict:
    session = CHAT_SESSIONS.get(sender)
    if session is None:
        session = {'mode': None, 'step': None, 'data': {}}
        CHAT_SESSIONS[sender] = session
    return session


def reset_chat_session(sender: str) -> None:
    CHAT_SESSIONS[sender] = {'mode': None, 'step': None, 'data': {}}


def extract_issue_id(message: str) -> str:
    match = re.search(r'\b[A-Z][A-Z0-9-]{5,11}\b', message or '', re.IGNORECASE)
    return match.group(0).upper() if match else ''


def normalize_chat_message(message: str) -> str:
    text = (message or '').strip().lower()
    if text.startswith('/'):
        text = text[1:]
    text = text.replace('_', ' ')
    return ' '.join(text.split())


def format_incident_for_chat(incident: dict) -> str:
    incident_doc = serialize_doc(incident)
    logged_date = incident_doc.get('start_date') or incident_doc.get('logged_date') or 'N/A'
    modified_date = incident_doc.get('modified_date') or 'N/A'

    message = f"📋 Issue: {incident_doc.get('issue_id', 'N/A')}\n"
    message += f"📝 Summary: {incident_doc.get('summary', 'N/A')}\n"
    message += f"🔴 Status: {incident_doc.get('status', 'N/A')}\n"
    message += f"⚠️ Severity: {incident_doc.get('severity', 'N/A')}\n"
    message += f"📅 Logged on: {logged_date}\n"
    message += f"🕒 Modified on: {modified_date}\n"
    if incident_doc.get('assigned_to'):
        message += f"👤 Assigned to: {incident_doc.get('assigned_to')}\n"
    if incident_doc.get('progress_notes'):
        message += f"\n📝 Progress Notes:\n{incident_doc.get('progress_notes')}\n"
    if incident_doc.get('resolution_description'):
        message += f"\n✅ Resolution:\n{incident_doc.get('resolution_description')}\n"
    return message


def create_incident_record(payload: dict):
    customer_id = (payload.get('customer_id') or '').strip()
    summary = (payload.get('summary') or '').strip()
    severity = normalize_severity(payload.get('severity', ''))

    if not customer_id or not summary or not severity:
        return {'message': 'customer_id, summary, and severity are required'}, 400

    if severity not in SEVERITY_VALUES:
        return {'message': f'severity must be one of {SEVERITY_VALUES}'}, 400

    try:
        customer_email = (payload.get('customer_email') or '').strip()
        customer = customers_collection.find_one({'customer_id': customer_id}, {'_id': 0, 'email': 1, 'name': 1})

        if not customer:
            return {
                'message': "Your Customer ID doesn't Exist"
            }, 400

        stored_email = (customer.get('email') or '').strip()
        if not customer_email:
            customer_email = stored_email
        elif stored_email and stored_email.lower() != customer_email.lower():
            return {
                'message': 'Customer email does not match the registered Customer ID.'
            }, 400

        if not customer_email:
            return {'message': 'Registered customer email is required to send the issue ID'}, 400

        issue_id = make_issue_id()
        current_time = now_datetime()

        assigned_to = get_random_agent_uid()

        if not assigned_to:
            return {'message': 'No agents are available for assignment'}, 400

        incident_doc = {
            'issue_id': issue_id,
            'customer_id': customer_id,
            'customer_email': customer_email,
            'summary': summary,
            'description': payload.get('description') or summary,
            'severity': severity,
            'status': 'New',
            'assigned_to': assigned_to,
            'start_date': current_time,
            'logged_date': current_time,
            'modified_date': current_time,
            'progress_notes': payload.get('progress_notes'),
            'resolution_description': payload.get('resolution_description'),
            'resolution_date': None,
            'notification_sent': False,
            'notification_sent_at': None,
        }

        incidents_collection.insert_one(incident_doc)

        # Send email asynchronously with retries so transient failures do not block user flow.
        def _bg_send(recipient, iid, summ):
            max_attempts = 3
            delay = 2
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    send_issue_id_email(recipient, iid, summ)
                    incidents_collection.update_one(
                        {'issue_id': iid},
                        {'$set': {'notification_sent': True, 'notification_sent_at': now_datetime(), 'notification_error': None}},
                    )
                    return
                except Exception as e:
                    last_err = e
                    incidents_collection.update_one(
                        {'issue_id': iid},
                        {'$set': {'notification_error': str(e), 'modified_date': now_datetime()}},
                    )
                    time.sleep(delay)
                    delay *= 2

            # If we exhausted retries, leave notification_error set for diagnostics.
            try:
                incidents_collection.update_one(
                    {'issue_id': iid},
                    {'$set': {'notification_error': str(last_err), 'modified_date': now_datetime()}},
                )
            except Exception:
                pass

        # Try immediate send first so users get an instant success when delivery works.
        try:
            send_issue_id_email(customer_email, issue_id, summary)
            incidents_collection.update_one(
                {'issue_id': issue_id},
                {'$set': {'notification_sent': True, 'notification_sent_at': now_datetime(), 'notification_error': None}},
            )
            return {
                'message': 'Incident created and issue ID sent to email',
                'issue_id': issue_id,
                'email_sent': True,
            }, 201
        except Exception as immediate_err:
            # Record the immediate failure and continue with background retries.
            incidents_collection.update_one(
                {'issue_id': issue_id},
                {'$set': {'notification_error': str(immediate_err), 'modified_date': now_datetime()}},
            )

            try:
                t = threading.Thread(target=_bg_send, args=(customer_email, issue_id, summary), daemon=True)
                t.start()
            except Exception as schedule_err:
                incidents_collection.update_one(
                    {'issue_id': issue_id},
                    {'$set': {'notification_error': str(schedule_err), 'modified_date': now_datetime()}},
                )

            return {
                'message': 'Incident created; issue ID will be emailed when available',
                'issue_id': issue_id,
                'email_sent': False,
            }, 201
    except Exception as err:
        return {'message': 'Failed to create incident', 'error': str(err)}, 500


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'incident-engine-backend'})


@app.route('/api/customers', methods=['POST'])
def create_customer():
    payload = request.get_json(silent=True) or {}
    customer_id = (payload.get('customer_id') or '').strip()
    name = (payload.get('name') or '').strip()
    mobile = (payload.get('mobile') or '').strip()
    email = (payload.get('email') or '').strip()
    location = (payload.get('location') or '').strip()

    if not customer_id or not name or not mobile or not email or not location:
        return jsonify({'message': 'customer_id, name, mobile, email, and location are required'}), 400

    try:
        if customers_collection.find_one({'customer_id': customer_id}, {'_id': 1}):
            return jsonify({'message': 'Customer already exists'}), 400

        customers_collection.insert_one(
            {
                'customer_id': customer_id,
                'name': name,
                'dob': payload.get('dob'),
                'address': payload.get('address'),
                'mobile': mobile,
                'email': email,
                'location': location,
                'created_date': now_datetime(),
            }
        )
        return jsonify({'message': 'Customer created', 'customer_id': customer_id}), 201
    except Exception as err:
        return jsonify({'message': 'Failed to create customer', 'error': str(err)}), 500


@app.route('/api/customers', methods=['GET'])
def list_customers():
    try:
        rows = [
            serialize_doc(row)
            for row in customers_collection.find({}, {'_id': 0}).sort(
                [('created_date', DESCENDING), ('customer_id', ASCENDING)]
            )
        ]
        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to fetch customers', 'error': str(err)}), 500


@app.route('/api/customers/<customer_id>', methods=['GET'])
def get_customer(customer_id):
    try:
        row = customers_collection.find_one({'customer_id': customer_id}, {'_id': 0})
        if not row:
            return jsonify({'message': 'Customer not found'}), 404
        return jsonify(serialize_doc(row))
    except Exception as err:
        return jsonify({'message': 'Failed to fetch customer', 'error': str(err)}), 500


@app.route('/api/chat', methods=['POST'])
def chat_proxy():
    payload = request.get_json(silent=True) or {}
    sender = (payload.get('sender') or 'web_user').strip() or 'web_user'
    message = (payload.get('message') or '').strip()

    if not message:
        return jsonify({'message': 'message is required'}), 400

    lower_message = normalize_chat_message(message)
    session = get_chat_session(sender)

    if lower_message in {'restart'}:
        reset_chat_session(sender)
        return jsonify([{'text': 'Conversation reset. How can I help you next?'}])

    if session.get('mode') == 'create_incident':
        field_order = ['customer_id', 'customer_email', 'summary', 'severity']
        current_step = session.get('step') or 0
        data = session.get('data') or {}

        def next_prompt(index: int) -> str:
            prompts = {
                0: 'Please provide your Customer ID.',
                1: 'Please provide the email address where the issue ID should be sent.',
                2: 'Please briefly describe the incident.',
                3: 'Please choose a severity: Low, Medium, or High.',
            }
            return prompts.get(index, 'Please provide the incident details.')

        if current_step == 0:
            if not data.get('customer_id'):
                customer_id = message.strip()
                customer = customers_collection.find_one({'customer_id': customer_id}, {'_id': 1})
                if not customer:
                    reset_chat_session(sender)
                    return jsonify([{'text': "Your Customer ID doesn't Exist"}])
                data['customer_id'] = customer_id
                session['data'] = data
                session['step'] = 1
                return jsonify([{'text': next_prompt(1)}])

        if current_step == 1:
            email_match = re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', message)
            if not email_match:
                return jsonify([{'text': 'Please provide a valid email address.'}])
            data['customer_email'] = email_match.group(0).strip()
            session['data'] = data
            session['step'] = 2
            return jsonify([{'text': next_prompt(2)}])

        if current_step == 2:
            data['summary'] = message.strip()
            session['data'] = data
            session['step'] = 3
            return jsonify([{'text': next_prompt(3)}])

        if current_step == 3:
            severity = normalize_severity(message)
            if severity not in SEVERITY_VALUES:
                return jsonify([{'text': 'Severity must be Low, Medium, or High. Please try again.'}])
            data['severity'] = severity
            body, status_code = create_incident_record(data)
            reset_chat_session(sender)
            return jsonify([{'text': body.get('message', 'Incident created successfully.') + (f" Issue ID: {body.get('issue_id')}" if body.get('issue_id') else '')}]), status_code

    if lower_message in {'create incident', 'create a new incident', 'log incident', 'log a new incident', 'report incident', 'report an issue', 'open a ticket', 'raise a ticket'}:
        session['mode'] = 'create_incident'
        session['step'] = 0
        session['data'] = {}
        return jsonify([{'text': 'I will create a new incident. Please provide your Customer ID.'}])

    if lower_message in {'incident status', 'check incident status', 'track my incident'}:
        session['mode'] = 'lookup_incident'
        session['step'] = None
        session['data'] = {}
        return jsonify([{'text': 'Please provide the Issue ID you want to check.'}])

    if lower_message in {'login help', 'i cannot log in', 'i am unable to sign in', 'help me with login', 'password reset help', 'my login is failing', 'sign in problem', 'unable to access my account', 'login issue', 'i forgot my password', 'i need help signing in', 'account access help'}:
        return jsonify([{'text': 'For login help, reset your password, verify your username, and confirm the account is active.'}])

    issue_id = extract_issue_id(message)
    if session.get('mode') != 'create_incident' and issue_id:
        incident = incidents_collection.find_one({'issue_id': issue_id}, {'_id': 0})
        if not incident:
            return jsonify([{'text': f'Incident {issue_id} was not found in the database.'}])
        return jsonify([{'text': format_incident_for_chat(incident)}])

    if session.get('mode') == 'lookup_incident' and not issue_id:
        return jsonify([{'text': 'Please provide the Issue ID you want to check.'}])

    rasa_webhook_url = os.getenv('RASA_WEBHOOK_URL', 'http://localhost:5005/webhooks/rest/webhook').strip()

    try:
        rasa_response = requests.post(
            rasa_webhook_url,
            json={'sender': sender, 'message': message},
            timeout=30,
        )
    except Exception as err:
        return jsonify({'message': 'Failed to reach Rasa server', 'error': str(err)}), 502

    if not rasa_response.ok:
        try:
            details = rasa_response.text
        except Exception:
            details = ''
        return jsonify({'message': 'Rasa request failed', 'status_code': rasa_response.status_code, 'error': details}), 502

    try:
        bot_messages = rasa_response.json()
    except Exception as err:
        return jsonify({'message': 'Invalid JSON response from Rasa', 'error': str(err)}), 502

    return jsonify(bot_messages)


@app.route('/api/incidents', methods=['POST'])
def create_incident():
    payload = request.get_json(silent=True) or {}
    body, status_code = create_incident_record(payload)
    return jsonify(body), status_code


@app.route('/api/incidents', methods=['GET'])
def list_incidents():
    try:
        rows = [
            serialize_doc(row)
            for row in incidents_collection.find({}, {'_id': 0}).sort(
                [('logged_date', DESCENDING), ('issue_id', DESCENDING)]
            )
        ]
        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to fetch incidents', 'error': str(err)}), 500


@app.route('/api/incidents/<issue_id>', methods=['GET'])
def get_incident(issue_id):
    try:
        row = incidents_collection.find_one({'issue_id': issue_id}, {'_id': 0})
        if not row:
            return jsonify({'message': 'Incident not found'}), 404

        assigned_value = row.get('assigned_to')
        if assigned_value:
            agent = resolve_agent_for_assignment(assigned_value)
            if agent:
                row['agent_uid'] = agent.get('uid')
                row['agent_name'] = agent.get('name')
                row['agent_email'] = agent.get('email')
                row['agent_phone'] = agent.get('phone')
                row['agent_department'] = agent.get('department')

        return jsonify(serialize_doc(row))
    except Exception as err:
        return jsonify({'message': 'Failed to fetch incident', 'error': str(err)}), 500


@app.route('/api/incidents/assign', methods=['PUT'])
def assign_incident():
    payload = request.get_json(silent=True) or {}
    issue_id = (payload.get('issue_id') or '').strip()
    agent_uid = (payload.get('agent_uid') or '').strip()

    if not issue_id or not agent_uid:
        return jsonify({'message': 'issue_id and agent_uid are required'}), 400

    try:
        incident = incidents_collection.find_one(
            {'issue_id': issue_id},
            {'_id': 0, 'issue_id': 1, 'status': 1, 'progress_notes': 1},
        )
        if not incident:
            return jsonify({'message': 'Incident not found'}), 404

        if not agents_collection.find_one({'uid': agent_uid}, {'_id': 1}):
            return jsonify({'message': 'Agent not found'}), 404

        timestamp = now_string()
        old_status = incident.get('status') or 'New'
        assignment_note = f'[{timestamp}] Status changed from {old_status} to Assigned: Assigned to agent {agent_uid}'
        notes = incident.get('progress_notes')
        progress_notes = f'{notes}\n{assignment_note}' if notes else assignment_note

        incidents_collection.update_one(
            {'issue_id': issue_id},
            {
                '$set': {
                    'assigned_to': agent_uid,
                    'status': 'Assigned',
                    'modified_date': now_datetime(),
                    'progress_notes': progress_notes,
                }
            },
        )
        return jsonify({'message': 'Incident assigned successfully'})
    except Exception as err:
        return jsonify({'message': 'Failed to assign incident', 'error': str(err)}), 500


@app.route('/api/incidents/<issue_id>/status', methods=['PUT'])
def update_incident_status(issue_id):
    payload = request.get_json(silent=True) or {}
    new_status = normalize_status(payload.get('status', ''))
    new_note = (payload.get('progress_notes') or '').strip()
    resolution_description = (payload.get('resolution_description') or '').strip()
    agent_uid = (payload.get('agent_uid') or '').strip()

    if not new_status:
        return jsonify({'message': 'status is required'}), 400

    if not agent_uid:
        return jsonify({'message': 'agent_uid is required'}), 400

    if new_status not in STATUS_VALUES:
        return jsonify({'message': f'status must be one of {STATUS_VALUES}'}), 400

    try:
        incident = incidents_collection.find_one(
            {'issue_id': issue_id},
            {'_id': 0, 'issue_id': 1, 'status': 1, 'progress_notes': 1, 'assigned_to': 1},
        )
        if not incident:
            return jsonify({'message': 'Incident not found'}), 404

        if incident.get('assigned_to') != agent_uid:
            return jsonify({'message': 'Only the assigned logged-in agent can update this incident'}), 403

        old_status = incident.get('status') or 'New'
        timestamp = now_string()
        note_text = new_note if new_note else 'Status updated'
        history_line = f'[{timestamp}] Status changed from {old_status} to {new_status}: {note_text}'
        notes = incident.get('progress_notes')
        combined_notes = f'{notes}\n{history_line}' if notes else history_line

        update_fields = {
            'status': new_status,
            'progress_notes': combined_notes,
            'modified_date': now_datetime(),
            'resolution_description': resolution_description if new_status in ('Resolved', 'Closed') else None,
            'resolution_date': now_datetime() if new_status in ('Resolved', 'Closed') else None,
        }
        incidents_collection.update_one({'issue_id': issue_id}, {'$set': update_fields})
        return jsonify({'message': 'Incident status updated successfully'})
    except Exception as err:
        return jsonify({'message': 'Failed to update status', 'error': str(err)}), 500


@app.route('/api/incidents/search', methods=['GET'])
def search_incidents():
    mongo_filter = {}
    and_filters = []

    issue_id = (request.args.get('issue_id') or '').strip()
    customer_id = (request.args.get('customer_id') or '').strip()
    agent_id = (request.args.get('agent_id') or '').strip()
    status = normalize_status(request.args.get('status', ''))
    severity = normalize_severity(request.args.get('severity', ''))
    date_from = (request.args.get('date_from') or '').strip()
    date_to = (request.args.get('date_to') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()

    if issue_id:
        and_filters.append({'issue_id': {'$regex': re.escape(issue_id), '$options': 'i'}})
    if customer_id:
        and_filters.append({'customer_id': {'$regex': re.escape(customer_id), '$options': 'i'}})
    if agent_id:
        and_filters.append({'assigned_to': {'$regex': re.escape(agent_id), '$options': 'i'}})
    if status:
        and_filters.append({'status': status})
    if severity:
        and_filters.append({'severity': severity})
    if date_from:
        start_date = parse_date_only(date_from)
        if not start_date:
            return jsonify({'message': 'date_from must be YYYY-MM-DD'}), 400
        and_filters.append(
            {
                '$or': [
                    {'logged_date': {'$gte': start_date}},
                    {'start_date': {'$gte': start_date}},
                ]
            }
        )
    if date_to:
        end_date = parse_date_only(date_to)
        if not end_date:
            return jsonify({'message': 'date_to must be YYYY-MM-DD'}), 400
        end_of_day = end_date + timedelta(days=1) - timedelta(microseconds=1)
        and_filters.append(
            {
                '$or': [
                    {'logged_date': {'$lte': end_of_day}},
                    {'start_date': {'$lte': end_of_day}},
                ]
            }
        )
    if keyword:
        and_filters.append(
            {
                '$or': [
                    {'summary': {'$regex': re.escape(keyword), '$options': 'i'}},
                    {'description': {'$regex': re.escape(keyword), '$options': 'i'}},
                ]
            }
        )

    if and_filters:
        mongo_filter['$and'] = and_filters

    try:
        rows = [
            serialize_doc(row)
            for row in incidents_collection.find(mongo_filter, {'_id': 0}).sort(
                [('logged_date', DESCENDING), ('issue_id', DESCENDING)]
            )
        ]

        assigned_ids = sorted({row.get('assigned_to') for row in rows if row.get('assigned_to')})
        if assigned_ids:
            agent_map = {
                a['uid']: a['name']
                for a in agents_collection.find({'uid': {'$in': assigned_ids}}, {'_id': 0, 'uid': 1, 'name': 1})
            }
            for row in rows:
                if row.get('assigned_to'):
                    row['agent_name'] = agent_map.get(row.get('assigned_to'))

        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to search incidents', 'error': str(err)}), 500


@app.route('/api/customers/issues', methods=['GET'])
def get_incidents_by_customer_email():
    email = (request.args.get('email') or '').strip()
    if not email:
        return jsonify({'message': 'email query parameter is required'}), 400

    try:
        rows = [
            serialize_doc(row)
            for row in incidents_collection.find({'customer_email': email, 'notification_sent': True}, {'_id': 0}).sort(
                [('logged_date', DESCENDING), ('issue_id', DESCENDING)]
            )
        ]

        assigned_ids = sorted({row.get('assigned_to') for row in rows if row.get('assigned_to')})
        if assigned_ids:
            agent_map = {
                a['uid']: a['name']
                for a in agents_collection.find({'uid': {'$in': assigned_ids}}, {'_id': 0, 'uid': 1, 'name': 1})
            }
            for row in rows:
                if row.get('assigned_to'):
                    row['agent_name'] = agent_map.get(row.get('assigned_to'))

        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to fetch customer incidents', 'error': str(err)}), 500


@app.route('/api/agents', methods=['POST'])
def create_agent():
    return jsonify({'message': 'Agent self-registration is disabled. Use pre-created agent credentials.'}), 403


@app.route('/api/agents', methods=['GET'])
def list_agents():
    try:
        rows = []
        for agent in agents_collection.find({}, agent_projection()).sort([('name', ASCENDING), ('uid', ASCENDING)]):
            agent_doc = serialize_doc(agent)
            open_issue_count = 0
            for incident in incidents_collection.find({'assigned_to': {'$exists': True, '$nin': [None, '']}}, {'_id': 0, 'assigned_to': 1, 'status': 1}):
                if (incident.get('status') or '') in {'Resolved', 'Closed'}:
                    continue
                if incident.get('assigned_to') == agent_doc.get('uid'):
                    open_issue_count += 1
            agent_doc['open_issue_count'] = int(open_issue_count)
            agent_doc['available'] = open_issue_count == 0
            rows.append(agent_doc)
        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to fetch agents', 'error': str(err)}), 500


@app.route('/api/agents/<uid>', methods=['GET'])
def get_agent(uid):
    try:
        row = agents_collection.find_one({'uid': uid}, agent_projection())
        if not row:
            return jsonify({'message': 'Agent not found'}), 404
        return jsonify(serialize_doc(row))
    except Exception as err:
        return jsonify({'message': 'Failed to fetch agent', 'error': str(err)}), 500


@app.route('/api/agents/login', methods=['POST'])
def agent_login():
    payload = request.get_json(silent=True) or {}
    uid = (payload.get('uid') or '').strip()
    email = (payload.get('email') or '').strip()
    password = payload.get('password') or ''

    if not uid or not email or not password:
        return jsonify({'message': 'Agent UID, Agent email, and password are required'}), 400

    try:
        agent = agents_collection.find_one({'uid': uid, 'email': email})
        if not agent:
            return jsonify({'message': 'Invalid credentials'}), 401

        stored_password = agent.get('password') or ''

        authenticated = False
        # Legacy plain-text compatibility: if old data exists, migrate on successful login.
        if stored_password.startswith('$2a$') or stored_password.startswith('$2b$') or stored_password.startswith('$2y$'):
            authenticated = checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
        else:
            authenticated = stored_password == password
            if authenticated:
                new_hash = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
                agents_collection.update_one({'uid': agent.get('uid')}, {'$set': {'password': new_hash}})

        if not authenticated:
            return jsonify({'message': 'Invalid credentials'}), 401

        response = {
            'uid': agent.get('uid'),
            'name': agent.get('name'),
            'email': agent.get('email'),
            'phone': agent.get('phone'),
            'department': agent.get('department'),
        }
        return jsonify(response)
    except Exception as err:
        return jsonify({'message': 'Login failed', 'error': str(err)}), 500


@app.route('/api/agents/<uid>', methods=['PUT'])
def update_agent(uid):
    payload = request.get_json(silent=True) or {}
    email = payload.get('email')
    phone = payload.get('phone')
    department = payload.get('department')

    try:
        if not agents_collection.find_one({'uid': uid}, {'_id': 1}):
            return jsonify({'message': 'Agent not found'}), 404

        update_fields = {}
        if 'email' in payload:
            update_fields['email'] = email
        if 'phone' in payload:
            update_fields['phone'] = phone
        if 'department' in payload:
            update_fields['department'] = department

        if not update_fields:
            return jsonify({'message': 'No updatable fields provided'}), 400

        agents_collection.update_one({'uid': uid}, {'$set': update_fields})
        return jsonify({'message': 'Agent updated successfully'})
    except Exception as err:
        return jsonify({'message': 'Failed to update agent', 'error': str(err)}), 500


@app.route('/api/agents/<uid>/incidents', methods=['GET'])
def get_agent_incidents(uid):
    try:
        if not agents_collection.find_one({'uid': uid}, {'_id': 1}):
            return jsonify({'message': 'Agent not found'}), 404

        rows = []
        for row in incidents_collection.find({'assigned_to': {'$exists': True, '$nin': [None, '']}}, {'_id': 0}).sort(
            [('modified_date', DESCENDING), ('issue_id', DESCENDING)]
        ):
            if row.get('assigned_to') != uid:
                continue
            rows.append(serialize_doc(row))

        for row in rows:
            agent = agents_collection.find_one({'uid': row.get('assigned_to')}, {'_id': 0, 'uid': 1, 'name': 1, 'department': 1})
            if agent:
                row['agent_uid'] = agent.get('uid')
                row['agent_name'] = agent.get('name')
                row['agent_department'] = agent.get('department')
            elif row.get('assigned_to'):
                row['agent_name'] = row.get('assigned_to')
                row['agent_department'] = 'N/A'

        return jsonify(rows)
    except Exception as err:
        return jsonify({'message': 'Failed to fetch agent incidents', 'error': str(err)}), 500


@app.route('/api/analytics/stats', methods=['GET'])
def analytics_stats():
    try:
        today_start = datetime.combine(date.today(), datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)

        total_incidents = incidents_collection.count_documents({})
        open_incidents = incidents_collection.count_documents({'status': {'$nin': ['Resolved', 'Closed']}})
        resolved_today = incidents_collection.count_documents(
            {'resolution_date': {'$gte': today_start, '$lt': tomorrow_start}}
        )
        high_severity_incidents = incidents_collection.count_documents({'severity': 'High'})

        avg_pipeline = [
            {
                '$match': {
                    'resolution_date': {'$ne': None},
                    'logged_date': {'$ne': None},
                }
            },
            {
                '$project': {
                    'hours': {
                        '$divide': [
                            {'$subtract': ['$resolution_date', '$logged_date']},
                            3600000,
                        ]
                    }
                }
            },
            {'$group': {'_id': None, 'avg_hours': {'$avg': '$hours'}}},
        ]
        avg_row = next(incidents_collection.aggregate(avg_pipeline), None)
        avg_hours = round(float(avg_row.get('avg_hours', 0)), 2) if avg_row else 0.0

        return jsonify(
            {
                'total_incidents': int(total_incidents),
                'total_issues': int(total_incidents),
                'open_incidents': int(open_incidents),
                'open_issues': int(open_incidents),
                'resolved_today': int(resolved_today),
                'avg_resolution_hours': float(avg_hours),
                'avg_resolution_time': f'{avg_hours:.2f} hours',
                'high_severity_incidents': int(high_severity_incidents),
                'high_severity': int(high_severity_incidents),
            }
        )
    except Exception as err:
        return jsonify({'message': 'Failed to fetch analytics stats', 'error': str(err)}), 500


@app.route('/api/incidents/<issue_id>/severity', methods=['PUT'])
def update_incident_severity(issue_id):
    payload = request.get_json(silent=True) or {}
    new_severity = normalize_severity(payload.get('severity', ''))
    note = (payload.get('progress_notes') or '').strip()

    if not new_severity:
        return jsonify({'message': 'severity is required'}), 400

    if new_severity not in SEVERITY_VALUES:
        return jsonify({'message': f'severity must be one of {SEVERITY_VALUES}'}), 400

    try:
        incident = incidents_collection.find_one({'issue_id': issue_id}, {'_id': 0, 'issue_id': 1, 'severity': 1, 'progress_notes': 1})
        if not incident:
            return jsonify({'message': 'Incident not found'}), 404

        old_severity = incident.get('severity') or 'Low'
        timestamp = now_string()
        note_text = note if note else f'Severity changed from {old_severity} to {new_severity}'
        history_line = f'[{timestamp}] {note_text}'
        notes = incident.get('progress_notes')
        combined_notes = f'{notes}\n{history_line}' if notes else history_line

        incidents_collection.update_one(
            {'issue_id': issue_id},
            {
                '$set': {
                    'severity': new_severity,
                    'progress_notes': combined_notes,
                    'modified_date': now_datetime(),
                }
            },
        )
        return jsonify({'message': 'Incident severity updated successfully'})
    except Exception as err:
        return jsonify({'message': 'Failed to update severity', 'error': str(err)}), 500


@app.route('/api/analytics/status', methods=['GET'])
def analytics_status():
    try:
        pipeline = [{'$group': {'_id': '$status', 'total': {'$sum': 1}}}]
        rows = list(incidents_collection.aggregate(pipeline))
        count_map = {row['_id']: int(row['total']) for row in rows if row.get('_id')}
        labels = [status for status in STATUS_VALUES if status in count_map]
        values = [count_map[status] for status in labels]
        return jsonify({'labels': labels, 'values': values})
    except Exception as err:
        return jsonify({'message': 'Failed to fetch status analytics', 'error': str(err)}), 500


@app.route('/api/analytics/severity', methods=['GET'])
def analytics_severity():
    try:
        pipeline = [{'$group': {'_id': '$severity', 'total': {'$sum': 1}}}]
        rows = list(incidents_collection.aggregate(pipeline))
        count_map = {row['_id']: int(row['total']) for row in rows if row.get('_id')}
        labels = [severity for severity in SEVERITY_VALUES if severity in count_map]
        values = [count_map[severity] for severity in labels]
        return jsonify({'labels': labels, 'values': values})
    except Exception as err:
        return jsonify({'message': 'Failed to fetch severity analytics', 'error': str(err)}), 500


@app.route('/api/analytics/trend', methods=['GET'])
def analytics_trend():
    try:
        start_date = datetime.combine(date.today() - timedelta(days=6), datetime.min.time())

        new_pipeline = [
            {'$match': {'logged_date': {'$gte': start_date}}},
            {
                '$group': {
                    '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$logged_date'}},
                    'total': {'$sum': 1},
                }
            },
            {'$sort': {'_id': 1}},
        ]
        resolved_pipeline = [
            {
                '$match': {
                    'resolution_date': {'$ne': None, '$gte': start_date},
                }
            },
            {
                '$group': {
                    '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$resolution_date'}},
                    'total': {'$sum': 1},
                }
            },
            {'$sort': {'_id': 1}},
        ]

        new_rows = list(incidents_collection.aggregate(new_pipeline))
        resolved_rows = list(incidents_collection.aggregate(resolved_pipeline))

        new_map = {row['_id']: int(row['total']) for row in new_rows}
        resolved_map = {row['_id']: int(row['total']) for row in resolved_rows}

        labels = []
        new_values = []
        resolved_values = []
        today = date.today()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            key = str(d)
            labels.append(key)
            new_values.append(new_map.get(key, 0))
            resolved_values.append(resolved_map.get(key, 0))

        return jsonify(
            {
                'labels': labels,
                'new_incidents': new_values,
                'resolved_incidents': resolved_values,
            }
        )
    except Exception as err:
        return jsonify({'message': 'Failed to fetch trend analytics', 'error': str(err)}), 500


migrate_incident_assignments_to_uid()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)
