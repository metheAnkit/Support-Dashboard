# Advanced Support Dashboard

A React.js frontend dashboard for the Incident Management System, featuring a **Customer Portal** and an **Agent Portal**.

---

## Prerequisites

- Node.js 16+ and npm
- The Flask backend running at `http://localhost:5000`

---

## Installation

```bash
npm install
```

---

## Running the App

```bash
npm start
```

The app opens at [http://localhost:3000](http://localhost:3000).

---

## Connecting to the Backend

All API calls use `http://localhost:5000` as the base URL. Ensure the Flask backend is running before using the portals.

If your backend runs on a different port or host, update the `REACT_APP_API_BASE_URL` value in a `.env` file (see `.env.example`).

> **Note:** The app currently hardcodes `http://localhost:5000`. To use the environment variable, replace API base URLs in the source files with `` `${process.env.REACT_APP_API_BASE_URL}/api/...` ``.

---

## API Endpoints Used

| Method | Endpoint | Portal |
|--------|----------|--------|
| POST | `/api/customers` | Customer - Register |
| GET | `/api/incidents/<issue_id>` | Customer - Track by ID |
| GET | `/api/customers/issues?email=...` | Customer - Track by Email |
| POST | `/api/agents/login` | Auth Context |
| GET | `/api/agents/<uid>/incidents` | Agent - Incident list |
| PUT | `/api/incidents/<issue_id>/status` | Agent - Update status |

---

## Project Structure

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
