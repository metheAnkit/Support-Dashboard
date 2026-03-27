import React, { useState } from 'react';
import { formatDate, getSeverityColor } from '../../utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

const EMPTY_REGISTER_FORM = {
  customer_id: '',
  name: '',
  dob: '',
  address: '',
  mobile: '',
  email: '',
  location: '',
};

const EMPTY_INCIDENT_FORM = {
  customer_id: '',
  customer_email: '',
  summary: '',
  description: '',
  severity: 'Medium',
};

function CustomerPortal() {
  // ── Register Customer state ──────────────────────────────────────────────
  const [registerForm, setRegisterForm] = useState(EMPTY_REGISTER_FORM);
  const [registerErrors, setRegisterErrors] = useState({});
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState('');
  const [registerError, setRegisterError] = useState('');

  // ── Report Incident state ──────────────────────────────────────────────
  const [incidentForm, setIncidentForm] = useState(EMPTY_INCIDENT_FORM);
  const [incidentLoading, setIncidentLoading] = useState(false);
  const [incidentError, setIncidentError] = useState('');
  const [incidentSuccess, setIncidentSuccess] = useState('');

  // ── Track Issue state ────────────────────────────────────────────────────
  const [searchType, setSearchType] = useState('issue_id'); // 'issue_id' | 'email'
  const [searchInput, setSearchInput] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [singleIncident, setSingleIncident] = useState(null);
  const [incidentList, setIncidentList] = useState(null);

  // ── Register handlers ────────────────────────────────────────────────────
  function handleRegisterChange(e) {
    const { name, value } = e.target;
    setRegisterForm((prev) => ({ ...prev, [name]: value }));
    if (registerErrors[name]) {
      setRegisterErrors((prev) => ({ ...prev, [name]: '' }));
    }
  }

  function validateRegisterForm() {
    const errors = {};
    if (!registerForm.customer_id.trim()) {
      errors.customer_id = 'Customer ID is required.';
    }
    if (!registerForm.name.trim()) {
      errors.name = 'Full Name is required.';
    }
    if (!registerForm.mobile.trim()) {
      errors.mobile = 'Mobile Number is required.';
    }
    if (!registerForm.email.trim()) {
      errors.email = 'Email Address is required.';
    }
    if (!registerForm.location.trim()) {
      errors.location = 'Location is required.';
    }
    return errors;
  }

  function handleIncidentChange(e) {
    const { name, value } = e.target;
    setIncidentForm((prev) => ({ ...prev, [name]: value }));
    if (incidentError) setIncidentError('');
  }

  async function handleRegisterSubmit(e) {
    e.preventDefault();
    setRegisterSuccess('');
    setRegisterError('');

    const errors = validateRegisterForm();
    if (Object.keys(errors).length > 0) {
      setRegisterErrors(errors);
      return;
    }

    setRegisterLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/customers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(registerForm),
      });
      const data = await response.json();

      if (response.status === 201) {
        setRegisterSuccess(`Customer registered successfully! Customer ID: ${data.customer_id || registerForm.customer_id}`);
        setRegisterForm(EMPTY_REGISTER_FORM);
        setRegisterErrors({});
      } else {
        setRegisterError(data.message || data.error || 'Registration failed. Please try again.');
      }
    } catch {
      setRegisterError('Network error. Please check your connection and try again.');
    } finally {
      setRegisterLoading(false);
    }
  }

  async function handleIncidentSubmit(e) {
    e.preventDefault();
    setIncidentError('');
    setIncidentSuccess('');

    if (!incidentForm.customer_id.trim() || !incidentForm.summary.trim()) {
      setIncidentError('Customer ID and issue summary are required to log an incident.');
      return;
    }

    setIncidentLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: incidentForm.customer_id.trim(),
          customer_email: incidentForm.customer_email.trim(),
          summary: incidentForm.summary.trim(),
          description: incidentForm.description.trim(),
          severity: incidentForm.severity,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        setIncidentError(data.message || data.error || 'Failed to log incident.');
        return;
      }

      const createdIssueId = data.issue_id || '';
      const emailSent = data.email_sent === true;
      if (!emailSent) {
        const backendReason = data.error ? ` Reason: ${data.error}` : '';
        setIncidentError(
          `Incident was logged but issue ID email was not confirmed.${backendReason}`
        );
        return;
      }

      setIncidentSuccess(`Incident logged successfully. Issue ID ${createdIssueId} has been sent to your email.`);
      setIncidentForm(EMPTY_INCIDENT_FORM);

      if (createdIssueId) {
        setSearchType('issue_id');
        setSearchInput(createdIssueId);
      }
    } catch {
      setIncidentError('Network error. Could not log incident.');
    } finally {
      setIncidentLoading(false);
    }
  }

  // ── Track Issue handlers ─────────────────────────────────────────────────
  async function handleSearch(e) {
    e.preventDefault();
    setSingleIncident(null);
    setIncidentList(null);
    setSearchError('');

    if (!searchInput.trim()) {
      setSearchError('Please enter a search value.');
      return;
    }

    setSearchLoading(true);
    try {
      let url;
      if (searchType === 'issue_id') {
        url = `${API_BASE_URL}/api/incidents/${encodeURIComponent(searchInput.trim())}`;
      } else {
        url = `${API_BASE_URL}/api/customers/issues?email=${encodeURIComponent(searchInput.trim())}`;
      }

      const response = await fetch(url);
      const data = await response.json();

      if (!response.ok) {
        if (searchType === 'issue_id') {
          setSearchError('Issue ID is not found');
        } else {
          setSearchError('Email is not found');
        }
        return;
      }

      if (searchType === 'issue_id') {
        setSingleIncident(data);
      } else {
        const list = Array.isArray(data) ? data : data.incidents || [];
        if (list.length === 0) {
          setSearchError('Email is not found');
        } else {
          setIncidentList(list);
        }
      }
    } catch {
      setSearchError('Network error. Please check your connection and try again.');
    } finally {
      setSearchLoading(false);
    }
  }

  // ── Render helpers ───────────────────────────────────────────────────────
  function StatusBadge({ status }) {
    const statusColors = {
      new: '#3498db',
      assigned: '#9b59b6',
      'in progress': '#f39c12',
      resolved: '#27ae60',
      closed: '#95a5a6',
    };
    const color = statusColors[(status || '').toLowerCase()] || '#95a5a6';
    return (
      <span className="status-badge" style={{ backgroundColor: color }}>
        {status || 'Unknown'}
      </span>
    );
  }

  return (
    <div className="portal-container customer-portal">
      {/* ══ Section 1: Register Customer ══════════════════════════════════ */}
      <section className="portal-section">
        <h2 className="section-heading">Register Customer</h2>

        {registerSuccess && (
          <div className="message success-message">{registerSuccess}</div>
        )}
        {registerError && (
          <div className="message error-message">{registerError}</div>
        )}

        <form className="form" onSubmit={handleRegisterSubmit} noValidate>
          <div className="form-row form-row--two-col">
            <div className="form-group">
              <label htmlFor="customer_id" className="form-label">
                Customer ID <span className="required">*</span>
              </label>
              <input
                id="customer_id"
                name="customer_id"
                type="text"
                className={`form-input${registerErrors.customer_id ? ' input-error' : ''}`}
                value={registerForm.customer_id}
                onChange={handleRegisterChange}
                autoComplete="off"
              />
              {registerErrors.customer_id && (
                <span className="inline-error">{registerErrors.customer_id}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="name" className="form-label">
                Full Name <span className="required">*</span>
              </label>
              <input
                id="name"
                name="name"
                type="text"
                className={`form-input${registerErrors.name ? ' input-error' : ''}`}
                value={registerForm.name}
                onChange={handleRegisterChange}
                autoComplete="name"
              />
              {registerErrors.name && (
                <span className="inline-error">{registerErrors.name}</span>
              )}
            </div>
          </div>

          <div className="form-row form-row--two-col">
            <div className="form-group">
              <label htmlFor="dob" className="form-label">
                Date of Birth
              </label>
              <input
                id="dob"
                name="dob"
                type="date"
                className="form-input"
                value={registerForm.dob}
                onChange={handleRegisterChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="mobile" className="form-label">
                Mobile Number <span className="required">*</span>
              </label>
              <input
                id="mobile"
                name="mobile"
                type="tel"
                className={`form-input${registerErrors.mobile ? ' input-error' : ''}`}
                value={registerForm.mobile}
                onChange={handleRegisterChange}
                autoComplete="tel"
              />
              {registerErrors.mobile && (
                <span className="inline-error">{registerErrors.mobile}</span>
              )}
            </div>
          </div>

          <div className="form-row form-row--two-col">
            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email Address <span className="required">*</span>
              </label>
              <input
                id="email"
                name="email"
                type="email"
                className={`form-input${registerErrors.email ? ' input-error' : ''}`}
                value={registerForm.email}
                onChange={handleRegisterChange}
                autoComplete="email"
              />
              {registerErrors.email && (
                <span className="inline-error">{registerErrors.email}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="location" className="form-label">
                Location <span className="required">*</span>
              </label>
              <input
                id="location"
                name="location"
                type="text"
                className={`form-input${registerErrors.location ? ' input-error' : ''}`}
                value={registerForm.location}
                onChange={handleRegisterChange}
              />
              {registerErrors.location && (
                <span className="inline-error">{registerErrors.location}</span>
              )}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="address" className="form-label">
              Address
            </label>
            <textarea
              id="address"
              name="address"
              className="form-input form-textarea"
              value={registerForm.address}
              onChange={handleRegisterChange}
              rows={3}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={registerLoading}
          >
            {registerLoading ? (
              <span className="btn-loading">
                <span className="spinner-inline" />
                Registering…
              </span>
            ) : (
              'Register Customer'
            )}
          </button>
        </form>
      </section>

      {/* ══ Section 2: Log Incident ═══════════════════════════════════════ */}
      <section className="portal-section">
        <h2 className="section-heading">Log New Incident</h2>
        <p className="section-subtext">
          Submit an incident first. Tracking becomes available only after the issue ID email is sent successfully.
        </p>

        {incidentSuccess && (
          <div className="message success-message">{incidentSuccess}</div>
        )}
        {incidentError && (
          <div className="message error-message">{incidentError}</div>
        )}

        <form className="form" onSubmit={handleIncidentSubmit} noValidate>
          <div className="form-row form-row--two-col">
            <div className="form-group">
              <label htmlFor="incident_customer_id" className="form-label">
                Customer ID <span className="required">*</span>
              </label>
              <input
                id="incident_customer_id"
                name="customer_id"
                type="text"
                className="form-input"
                value={incidentForm.customer_id}
                onChange={handleIncidentChange}
                autoComplete="off"
              />
            </div>

            <div className="form-group">
              <label htmlFor="incident_customer_email" className="form-label">
                Customer Email
              </label>
              <input
                id="incident_customer_email"
                name="customer_email"
                type="email"
                className="form-input"
                value={incidentForm.customer_email}
                onChange={handleIncidentChange}
                autoComplete="email"
              />
            </div>
          </div>

          <div className="form-row form-row--two-col">
            <div className="form-group">
              <label htmlFor="incident_summary" className="form-label">
                Issue Summary <span className="required">*</span>
              </label>
              <input
                id="incident_summary"
                name="summary"
                type="text"
                className="form-input"
                value={incidentForm.summary}
                onChange={handleIncidentChange}
              />
            </div>

            <div className="form-group">
              <label htmlFor="incident_severity" className="form-label">
                Severity <span className="required">*</span>
              </label>
              <select
                id="incident_severity"
                name="severity"
                className="form-input form-select"
                value={incidentForm.severity}
                onChange={handleIncidentChange}
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="incident_description" className="form-label">
              Detailed Description
            </label>
            <textarea
              id="incident_description"
              name="description"
              className="form-input form-textarea"
              value={incidentForm.description}
              onChange={handleIncidentChange}
              rows={3}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={incidentLoading}
          >
            {incidentLoading ? (
              <span className="btn-loading">
                <span className="spinner-inline" />
                Logging…
              </span>
            ) : (
              'Log Incident'
            )}
          </button>
        </form>
      </section>

      {/* ══ Section 3: Track My Issue ══════════════════════════════════════ */}
      <section className="portal-section">
        <h2 className="section-heading">Track My Issue</h2>

        <form className="form" onSubmit={handleSearch}>
          <div className="form-group">
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  name="searchType"
                  value="issue_id"
                  checked={searchType === 'issue_id'}
                  onChange={() => {
                    setSearchType('issue_id');
                    setSearchInput('');
                    setSingleIncident(null);
                    setIncidentList(null);
                    setSearchError('');
                  }}
                />
                Search by Issue ID
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="searchType"
                  value="email"
                  checked={searchType === 'email'}
                  onChange={() => {
                    setSearchType('email');
                    setSearchInput('');
                    setSingleIncident(null);
                    setIncidentList(null);
                    setSearchError('');
                  }}
                />
                Search by Email
              </label>
            </div>
          </div>

          <div className="form-group form-row-inline">
            <input
              type={searchType === 'email' ? 'email' : 'text'}
              className="form-input"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              aria-label="Search input"
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={searchLoading}
            >
              {searchLoading ? (
                <span className="btn-loading">
                  <span className="spinner-inline" />
                  Searching…
                </span>
              ) : (
                'Search'
              )}
            </button>
          </div>
        </form>

        {/* Loading spinner */}
        {searchLoading && (
          <div className="spinner-container">
            <div className="spinner" aria-label="Loading" />
          </div>
        )}

        {/* Error / empty state */}
        {searchError && !searchLoading && (
          <div className="message error-message">{searchError}</div>
        )}

        {/* Single incident detail card */}
        {singleIncident && !searchLoading && (
          <div className="incident-card">
            <h3 className="card-title">Incident Details</h3>
            <div className="card-grid">
              <div className="card-field">
                <span className="card-label">Issue ID</span>
                <span className="card-value">{singleIncident.issue_id || singleIncident.id}</span>
              </div>
              <div className="card-field">
                <span className="card-label">Status</span>
                <span className="card-value">
                  <StatusBadge status={singleIncident.status} />
                </span>
              </div>
              <div className="card-field">
                <span className="card-label">Severity</span>
                <span
                  className="card-value severity-text"
                  style={{ color: getSeverityColor(singleIncident.severity) }}
                >
                  {singleIncident.severity || 'N/A'}
                </span>
              </div>
              <div className="card-field">
                <span className="card-label">Logged Date</span>
                <span className="card-value">{formatDate(singleIncident.logged_date || singleIncident.created_at)}</span>
              </div>
              <div className="card-field card-field--full">
                <span className="card-label">Summary</span>
                <span className="card-value">{singleIncident.summary || singleIncident.description || 'N/A'}</span>
              </div>
              <div className="card-field">
                <span className="card-label">Assigned Agent</span>
                <span className="card-value">{singleIncident.assigned_agent || singleIncident.agent_name || 'Unassigned'}</span>
              </div>
              {singleIncident.progress_notes && (
                <div className="card-field card-field--full">
                  <span className="card-label">Progress Notes</span>
                  <span className="card-value">{singleIncident.progress_notes}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Email search results table */}
        {incidentList && !searchLoading && (
          <div className="table-wrapper">
            <h3 className="table-heading">
              Found {incidentList.length} incident{incidentList.length !== 1 ? 's' : ''}
            </h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Issue ID</th>
                  <th>Summary</th>
                  <th>Status</th>
                  <th>Severity</th>
                  <th>Logged Date</th>
                  <th>Agent</th>
                </tr>
              </thead>
              <tbody>
                {incidentList.map((incident, idx) => (
                  <tr key={incident.issue_id || incident.id || idx}>
                    <td>{incident.issue_id || incident.id}</td>
                    <td>{incident.summary || incident.description}</td>
                    <td>
                      <StatusBadge status={incident.status} />
                    </td>
                    <td>
                      <span
                        style={{ color: getSeverityColor(incident.severity), fontWeight: 600 }}
                      >
                        {incident.severity || 'N/A'}
                      </span>
                    </td>
                    <td>{formatDate(incident.logged_date || incident.created_at)}</td>
                    <td>{incident.assigned_agent || incident.agent_name || 'Unassigned'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default CustomerPortal;
