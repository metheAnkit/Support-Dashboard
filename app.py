import os
import re
import uuid
from datetime import date, datetime, timedelta

from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient


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


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'incident-engine-backend'})


@app.route('/api/customers', methods=['POST'])
def create_customer():
    payload = request.get_json(silent=True) or {}
    customer_id = (payload.get('customer_id') or '').strip()
    name = (payload.get('name') or '').strip()

    if not customer_id or not name:
        return jsonify({'message': 'customer_id and name are required'}), 400

    try:
        if customers_collection.find_one({'customer_id': customer_id}, {'_id': 1}):
            return jsonify({'message': 'Customer already exists'}), 400

        customers_collection.insert_one(
            {
                'customer_id': customer_id,
                'name': name,
                'dob': payload.get('dob'),
                'address': payload.get('address'),
                'mobile': payload.get('mobile'),
                'email': payload.get('email'),
                'location': payload.get('location'),
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


@app.route('/api/incidents', methods=['POST'])
def create_incident():
    payload = request.get_json(silent=True) or {}
    customer_id = (payload.get('customer_id') or '').strip()
    summary = (payload.get('summary') or '').strip()
    severity = normalize_severity(payload.get('severity', ''))

    if not customer_id or not summary or not severity:
        return jsonify({'message': 'customer_id, summary, and severity are required'}), 400

    if severity not in SEVERITY_VALUES:
        return jsonify({'message': f'severity must be one of {SEVERITY_VALUES}'}), 400

    try:
        customer = customers_collection.find_one({'customer_id': customer_id}, {'_id': 0, 'email': 1})
        if not customer:
            return jsonify({'message': 'Customer does not exist'}), 400

        issue_id = make_issue_id()
        current_time = now_datetime()

        incidents_collection.insert_one(
            {
                'issue_id': issue_id,
                'customer_id': customer_id,
                'customer_email': payload.get('customer_email') or customer.get('email'),
                'summary': summary,
                'description': payload.get('description'),
                'severity': severity,
                'status': 'New',
                'assigned_to': payload.get('assigned_to'),
                'logged_date': current_time,
                'modified_date': current_time,
                'progress_notes': payload.get('progress_notes'),
                'resolution_description': payload.get('resolution_description'),
                'resolution_date': None,
            }
        )
        return jsonify({'message': 'Incident created', 'issue_id': issue_id}), 201
    except Exception as err:
        return jsonify({'message': 'Failed to create incident', 'error': str(err)}), 500


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

        assigned_uid = row.get('assigned_to')
        if assigned_uid:
            agent = agents_collection.find_one({'uid': assigned_uid}, {'_id': 0})
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

    if not new_status:
        return jsonify({'message': 'status is required'}), 400

    if new_status not in STATUS_VALUES:
        return jsonify({'message': f'status must be one of {STATUS_VALUES}'}), 400

    try:
        incident = incidents_collection.find_one(
            {'issue_id': issue_id},
            {'_id': 0, 'issue_id': 1, 'status': 1, 'progress_notes': 1},
        )
        if not incident:
            return jsonify({'message': 'Incident not found'}), 404

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
        mongo_filter.setdefault('logged_date', {})['$gte'] = start_date
    if date_to:
        end_date = parse_date_only(date_to)
        if not end_date:
            return jsonify({'message': 'date_to must be YYYY-MM-DD'}), 400
        end_of_day = end_date + timedelta(days=1) - timedelta(microseconds=1)
        mongo_filter.setdefault('logged_date', {})['$lte'] = end_of_day
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
            for row in incidents_collection.find({'customer_email': email}, {'_id': 0}).sort(
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
    payload = request.get_json(silent=True) or {}
    uid = (payload.get('uid') or '').strip()
    name = (payload.get('name') or '').strip()
    password = payload.get('password') or ''

    if not uid or not name or not password:
        return jsonify({'message': 'uid, name, and password are required'}), 400

    try:
        if agents_collection.find_one({'uid': uid}, {'_id': 1}):
            return jsonify({'message': 'Agent already exists'}), 400

        password_hash = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

        agents_collection.insert_one(
            {
                'uid': uid,
                'password': password_hash,
                'name': name,
                'email': payload.get('email'),
                'phone': payload.get('phone'),
                'department': payload.get('department'),
                'created_date': now_datetime(),
            }
        )
        return jsonify({'message': 'Agent created', 'uid': uid}), 201
    except Exception as err:
        return jsonify({'message': 'Failed to create agent', 'error': str(err)}), 500


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
    password = payload.get('password') or ''

    if not uid or not password:
        return jsonify({'message': 'uid and password are required'}), 400

    try:
        agent = agents_collection.find_one({'uid': uid})
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
                agents_collection.update_one({'uid': uid}, {'$set': {'password': new_hash}})

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

        rows = [
            serialize_doc(row)
            for row in incidents_collection.find({'assigned_to': uid}, {'_id': 0}).sort(
                [('modified_date', DESCENDING), ('issue_id', DESCENDING)]
            )
        ]
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
                'open_incidents': int(open_incidents),
                'resolved_today': int(resolved_today),
                'avg_resolution_hours': float(avg_hours),
                'high_severity_incidents': int(high_severity_incidents),
            }
        )
    except Exception as err:
        return jsonify({'message': 'Failed to fetch analytics stats', 'error': str(err)}), 500


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)
