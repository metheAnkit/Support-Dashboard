# Incident Engine: Support Dashboard + Flask API

This repository contains:
- React frontend (`src/`) for customer and agent portals
- Flask + MongoDB backend (`app.py`) for customer, incident, agent, and analytics APIs

## Tech Stack

- Python 3.10+
- Flask
- pymongo
- flask-cors
- bcrypt
- MongoDB
- React (frontend)

## Prerequisites

- Node.js 16+ and npm
- Python 3.10+
- MongoDB server running locally

## Environment Variables

Copy `.env.example` to `.env` and update values as needed.

```env
REACT_APP_API_BASE_URL=http://localhost:5000
PORT=5000
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=support_system

# SMTP (required for incident issue ID email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASS=your-app-password
SMTP_FROM=your-email@example.com
SMTP_USE_TLS=true
```

## Database Setup

Run the MongoDB seed script:

```bash
mongosh < mongo_seed.js
```

Optional query examples are available in `mongo_queries.js`.

## Backend Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run the backend server:

```bash
python app.py
```

Backend starts on `http://localhost:5000` by default.

Health check:

```http
GET /
```

## Frontend Setup

Install frontend dependencies:

```bash
npm install
```

Run frontend app:

```bash
npm start
```

Frontend opens at `http://localhost:3000`.

## API Reference

### Customer APIs
- `POST /api/customers`
- `GET /api/customers`
- `GET /api/customers/<customer_id>`
- `GET /api/customers/issues?email=<email>`

### Incident APIs
- `POST /api/incidents`
- `GET /api/incidents`
- `GET /api/incidents/<issue_id>`
- `PUT /api/incidents/assign`
- `PUT /api/incidents/<issue_id>/status`
- `GET /api/incidents/search`

Note: Issue tracking (`GET /api/incidents/<issue_id>` and `GET /api/customers/issues?email=...`) works only after the incident issue ID email is sent successfully.

Supported search query params:
- `issue_id`
- `customer_id`
- `agent_id`
- `status`
- `severity`
- `date_from`
- `date_to`
- `keyword`

### Agent APIs
- `POST /api/agents`
- `POST /api/agents/login`
- `GET /api/agents/<uid>`
- `PUT /api/agents/<uid>`
- `GET /api/agents/<uid>/incidents`

### Analytics APIs
- `GET /api/analytics/stats`
- `GET /api/analytics/status`
- `GET /api/analytics/severity`
- `GET /api/analytics/trend`

## Notes

| Method | Endpoint | Portal |
|--------|----------|--------|
| POST | `/api/customers` | Customer - Register |
| GET | `/api/incidents/<issue_id>` | Customer - Track by ID |
| GET | `/api/customers/issues?email=...` | Customer - Track by Email |
| POST | `/api/agents/login` | Auth Context |
| GET | `/api/agents/<uid>/incidents` | Agent - Incident list |
| PUT | `/api/incidents/<issue_id>/status` | Agent - Update status |

- New agent registrations are stored with bcrypt-hashed passwords.
- Login supports one-time migration of legacy plain-text seed passwords to bcrypt hash.
- `mongo_seed.js` includes at least 10 incidents covering all required status and severity values.

## Submission Artifacts Included

- `app.py`
- `requirements.txt`
- `mongo_seed.js`
- `mongo_queries.js`
- `.env.example`

```
src/
+-- App.js                        - Root component
+-- index.js                      - ReactDOM 18 entry point
+-- context/
|   +-- AuthContext.js            - Global auth state (React Context)
+-- components/
|   +-- common/
|   |   +-- Tabs.js               - Reusable tab switcher
|   +-- customer/
|   |   +-- CustomerPortal.js     - Customer-facing UI
|   +-- agent/
|       +-- AgentPortal.js        - Agent-facing UI
+-- styles/
|   +-- App.css                   - All application styles
+-- utils.js                      - Shared helper functions
```

---

## Features

### Customer Portal
- Register a new customer (7-field form with validation)
- Track issues by Issue ID (shows detail card) or by Email (shows results table)
- Loading states, error messages, and empty-state handling

### Agent Portal
- Secure login gate (UID + password, via Auth Context)
- Agent dashboard with all assigned incidents in a sortable table
- Update incident status, progress notes, and resolution description via modal
- Logout button clears auth state

---

## Screenshots

See the `screenshots/` folder for:
1. Customer portal loaded
2. Register form - success message
3. Track issue - results card
4. Agent login form
5. Agent dashboard with incident table
6. Update modal open

## Additional Submission Files

You can add your Postman collection JSON and ER diagram file to this repository before final submission.
