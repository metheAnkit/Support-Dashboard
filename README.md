# Incident Engine: Support Dashboard

Support Dashboard is an incident management app with a React frontend and a Flask + MongoDB backend.

This repository contains:
- React frontend (`src/`) for customer and agent portals
- Flask + MongoDB backend (`app.py`) for customer, incident, agent, and analytics APIs

## Project Structure

- `src/` React frontend for the customer and agent portals
- `app.py` Flask backend API
- `requirements.txt` Python backend dependencies
- `package.json` frontend dependencies and scripts
- `rasa/` separate chatbot project folder, not required to run the main dashboard

## Tech Stack

- Frontend: React 19 + Vite
- Backend: Flask + Flask-CORS
- Database: MongoDB (pymongo)
- Auth/security: bcrypt
- Config: python-dotenv

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- MongoDB running locally (or a remote MongoDB URI)

## Environment Variables

Use the existing `.env` file (or create one at project root) with values like:

```env
# Frontend
VITE_API_BASE_URL=http://localhost:5000

# Backend
PORT=5000
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=support_system

# SMTP for sending issue ID emails
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASS=your-app-password
SMTP_FROM=your-email@example.com
SMTP_USE_TLS=true
```

## Quick Start

### 1) Install frontend dependencies

```bash
npm install
```

### 2) Install backend dependencies

```bash
pip install -r requirements.txt
```

### 3) Run backend

```bash
python app.py
```

Backend runs at `http://localhost:5000` by default.

### 4) Run frontend

```bash
npm run dev
```

Frontend runs at `http://localhost:3000`.

## Available Frontend Scripts

- `npm run dev` Start development server
- `npm run build` Create production build
- `npm run preview` Preview production build locally

## API Overview

### Health
- `GET /`

### Customers
- `POST /api/customers`
- `GET /api/customers`
- `GET /api/customers/<customer_id>`
- `GET /api/customers/issues?email=<email>`

### Incidents
- `POST /api/incidents`
- `GET /api/incidents`
- `GET /api/incidents/<issue_id>`
- `PUT /api/incidents/assign`
- `PUT /api/incidents/<issue_id>/status`
- `GET /api/incidents/search`

### Agents
- `POST /api/agents`
- `POST /api/agents/login`
- `GET /api/agents/<uid>`
- `PUT /api/agents/<uid>`
- `GET /api/agents/<uid>/incidents`

### Analytics
- `GET /api/analytics/stats`
- `GET /api/analytics/status`
- `GET /api/analytics/severity`
- `GET /api/analytics/trend`

## Notes

<<<<<<< HEAD
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

No additional files at this time.
=======
- Incident tracking endpoints are available only after issue ID email notification is sent.
- Backend creates MongoDB indexes automatically at startup.
- `build/` or `dist/` folders are generated artifacts and can be deleted safely.
- `node_modules/`, `.venv/`, and `rasa/.venv/` are environment folders and are not required in source control.
- If you only want the dashboard itself, the `rasa/` folder is optional.
>>>>>>> 7b8db584 (Add support dashboard)
