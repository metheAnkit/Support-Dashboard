import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { formatDate, getSeverityColor } from '../../utils';

const STATUS_OPTIONS = ['New', 'Assigned', 'In Progress', 'Resolved', 'Closed'];

// Initial state for the update form
const EMPTY_UPDATE_FORM = {
  status: '',
  progress_notes: '',
  resolution_description: '',
};

function AgentPortal() {
  const { agentUser, login, logout } = useAuth();

  // ── Login form state ───────────────────────────────────────────────────
  const [loginForm, setLoginForm] = useState({ uid: '', password: '' });
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');

  // ── Agent dashboard state ──────────────────────────────────────────────
  const [incidents, setIncidents] = useState([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);
  const [incidentsError, setIncidentsError] = useState('');

  // Sort state
  const [sortField, setSortField] = useState('status');
  const [sortDir, setSortDir] = useState('asc');

  // Update modal state
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [updateForm, setUpdateForm] = useState(EMPTY_UPDATE_FORM);
  const [updateLoading, setUpdateLoading] = useState(false);
  const [updateError, setUpdateError] = useState('');
  const [updateSuccess, setUpdateSuccess] = useState('');

  // ── Fetch incidents when logged in ─────────────────────────────────────
  const fetchIncidents = useCallback(async () => {
    if (!agentUser) return;
    setIncidentsLoading(true);
    setIncidentsError('');
    try {
      const uid = agentUser.uid || agentUser.agent_uid || agentUser.id;
      const response = await fetch(
        `http://localhost:5000/api/agents/${encodeURIComponent(uid)}/incidents`
      );
      const data = await response.json();
      if (!response.ok) {
        setIncidentsError(data.message || data.error || 'Failed to load incidents.');
        return;
      }
      setIncidents(Array.isArray(data) ? data : data.incidents || []);
    } catch {
      setIncidentsError('Network error. Could not load incidents.');
    } finally {
      setIncidentsLoading(false);
    }
  }, [agentUser]);

  useEffect(() => {
    if (agentUser) {
      fetchIncidents();
    }
  }, [agentUser, fetchIncidents]);

  // ── Login handlers ─────────────────────────────────────────────────────
  function handleLoginChange(e) {
    const { name, value } = e.target;
    setLoginForm((prev) => ({ ...prev, [name]: value }));
    if (loginError) setLoginError('');
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    setLoginError('');
    if (!loginForm.uid.trim() || !loginForm.password) {
      setLoginError('Agent UID and Password are required.');
      return;
    }
    setLoginLoading(true);
    try {
      await login(loginForm.uid.trim(), loginForm.password);
    } catch (err) {
      setLoginError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoginLoading(false);
    }
  }

  // ── Sort handler ───────────────────────────────────────────────────────
  function handleSort(field) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  }

  function getSortedIncidents() {
    return [...incidents].sort((a, b) => {
      const aVal = (a[sortField] || '').toString().toLowerCase();
      const bVal = (b[sortField] || '').toString().toLowerCase();
      if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }

  // ── Update modal handlers ──────────────────────────────────────────────
  function openUpdateModal(incident) {
    setSelectedIncident(incident);
    setUpdateForm({
      status: incident.status || 'New',
      progress_notes: incident.progress_notes || '',
      resolution_description: incident.resolution_description || '',
    });
    setUpdateError('');
    setUpdateSuccess('');
  }

  function closeUpdateModal() {
    setSelectedIncident(null);
    setUpdateForm(EMPTY_UPDATE_FORM);
    setUpdateError('');
    setUpdateSuccess('');
  }

  function handleUpdateChange(e) {
    const { name, value } = e.target;
    setUpdateForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleUpdateSubmit(e) {
    e.preventDefault();
    setUpdateError('');
    setUpdateSuccess('');
    setUpdateLoading(true);

    const issueId = selectedIncident.issue_id || selectedIncident.id;

    try {
      const body = {
        status: updateForm.status,
        progress_notes: updateForm.progress_notes,
      };
      if (
        updateForm.status === 'Resolved' ||
        updateForm.status === 'Closed'
      ) {
        body.resolution_description = updateForm.resolution_description;
      }

      const response = await fetch(
        `http://localhost:5000/api/incidents/${encodeURIComponent(issueId)}/status`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      );
      const data = await response.json();

      if (!response.ok) {
        setUpdateError(data.message || data.error || 'Update failed.');
        return;
      }

      setUpdateSuccess('Incident updated successfully.');
      await fetchIncidents();
      setTimeout(closeUpdateModal, 1200);
    } catch {
      setUpdateError('Network error. Could not save update.');
    } finally {
      setUpdateLoading(false);
    }
  }

  // ── Status badge helper ────────────────────────────────────────────────
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

  function SortIcon({ field }) {
    if (sortField !== field) return <span className="sort-icon">⇅</span>;
    return <span className="sort-icon">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  // ══════════════════════════════════════════════════════════════════════
  // RENDER: Login gate
  // ══════════════════════════════════════════════════════════════════════
  if (!agentUser) {
    return (
      <div className="portal-container">
        <section className="portal-section login-section">
          <h2 className="section-heading">Agent Login</h2>
          <p className="section-subtext">
            Please log in with your agent credentials to access the dashboard.
          </p>

          {loginError && (
            <div className="message error-message">{loginError}</div>
          )}

          <form className="form login-form" onSubmit={handleLoginSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="uid" className="form-label">
                Agent UID <span className="required">*</span>
              </label>
              <input
                id="uid"
                name="uid"
                type="text"
                className="form-input"
                value={loginForm.uid}
                onChange={handleLoginChange}
                placeholder="e.g. AGT001"
                autoComplete="username"
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password <span className="required">*</span>
              </label>
              <input
                id="password"
                name="password"
                type="password"
                className="form-input"
                value={loginForm.password}
                onChange={handleLoginChange}
                placeholder="Enter your password"
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loginLoading}
            >
              {loginLoading ? (
                <span className="btn-loading">
                  <span className="spinner-inline" />
                  Logging in…
                </span>
              ) : (
                'Login'
              )}
            </button>
          </form>
        </section>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════
  // RENDER: Agent dashboard
  // ══════════════════════════════════════════════════════════════════════
  const agentName = agentUser.name || agentUser.agent_name || agentUser.uid || 'Agent';
  const sortedIncidents = getSortedIncidents();

  return (
    <div className="portal-container">
      {/* ── Dashboard header ── */}
      <div className="agent-header">
        <div>
          <h2 className="agent-welcome">Welcome, {agentName}</h2>
          <p className="agent-subtitle">Your assigned incidents are listed below.</p>
        </div>
        <button className="btn btn-secondary" onClick={logout}>
          Logout
        </button>
      </div>

      {/* ── Incidents section ── */}
      <section className="portal-section">
        <h3 className="section-heading">Assigned Incidents</h3>

        {incidentsLoading && (
          <div className="spinner-container">
            <div className="spinner" aria-label="Loading incidents" />
          </div>
        )}

        {incidentsError && !incidentsLoading && (
          <div className="message error-message">{incidentsError}</div>
        )}

        {!incidentsLoading && !incidentsError && incidents.length === 0 && (
          <div className="message info-message">No incidents assigned to you.</div>
        )}

        {!incidentsLoading && sortedIncidents.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Issue ID</th>
                  <th>Summary</th>
                  <th
                    className="sortable-col"
                    onClick={() => handleSort('status')}
                    aria-sort={sortField === 'status' ? sortDir : 'none'}
                  >
                    Status <SortIcon field="status" />
                  </th>
                  <th
                    className="sortable-col"
                    onClick={() => handleSort('severity')}
                    aria-sort={sortField === 'severity' ? sortDir : 'none'}
                  >
                    Severity <SortIcon field="severity" />
                  </th>
                  <th>Customer ID</th>
                  <th>Last Modified</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedIncidents.map((incident, idx) => {
                  const issueId = incident.issue_id || incident.id;
                  return (
                    <tr key={issueId || idx}>
                      <td>{issueId}</td>
                      <td className="summary-cell">
                        {incident.summary || incident.description}
                      </td>
                      <td>
                        <StatusBadge status={incident.status} />
                      </td>
                      <td>
                        <span
                          style={{
                            color: getSeverityColor(incident.severity),
                            fontWeight: 600,
                          }}
                        >
                          {incident.severity || 'N/A'}
                        </span>
                      </td>
                      <td>{incident.customer_id}</td>
                      <td>{formatDate(incident.last_modified || incident.updated_at)}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-outline"
                          onClick={() => openUpdateModal(incident)}
                        >
                          Update
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ══ Update Modal ══════════════════════════════════════════════════ */}
      {selectedIncident && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeUpdateModal();
          }}
        >
          <div className="modal-panel">
            <div className="modal-header">
              <h3 id="modal-title" className="modal-title">
                Update Incident{' '}
                <span className="modal-issue-id">
                  #{selectedIncident.issue_id || selectedIncident.id}
                </span>
              </h3>
              <button
                className="modal-close-btn"
                onClick={closeUpdateModal}
                aria-label="Close update form"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <p className="modal-summary">
                {selectedIncident.summary || selectedIncident.description}
              </p>

              {updateSuccess && (
                <div className="message success-message">{updateSuccess}</div>
              )}
              {updateError && (
                <div className="message error-message">{updateError}</div>
              )}

              <form className="form" onSubmit={handleUpdateSubmit}>
                <div className="form-group">
                  <label htmlFor="update-status" className="form-label">
                    Status <span className="required">*</span>
                  </label>
                  <select
                    id="update-status"
                    name="status"
                    className="form-input form-select"
                    value={updateForm.status}
                    onChange={handleUpdateChange}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="progress_notes" className="form-label">
                    Progress Notes
                  </label>
                  <textarea
                    id="progress_notes"
                    name="progress_notes"
                    className="form-input form-textarea"
                    value={updateForm.progress_notes}
                    onChange={handleUpdateChange}
                    placeholder="Describe the progress made…"
                    rows={4}
                  />
                </div>

                {/* Resolution description — only for Resolved / Closed */}
                {(updateForm.status === 'Resolved' ||
                  updateForm.status === 'Closed') && (
                  <div className="form-group">
                    <label
                      htmlFor="resolution_description"
                      className="form-label"
                    >
                      Resolution Description
                    </label>
                    <textarea
                      id="resolution_description"
                      name="resolution_description"
                      className="form-input form-textarea"
                      value={updateForm.resolution_description}
                      onChange={handleUpdateChange}
                      placeholder="Describe how the issue was resolved…"
                      rows={4}
                    />
                  </div>
                )}

                <div className="modal-actions">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={updateLoading}
                  >
                    {updateLoading ? (
                      <span className="btn-loading">
                        <span className="spinner-inline" />
                        Saving…
                      </span>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={closeUpdateModal}
                    disabled={updateLoading}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentPortal;
