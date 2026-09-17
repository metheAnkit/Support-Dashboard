/**
 * Formats an ISO date string to a human-readable format.
 * Example: '2025-12-15T10:30:00' -> '15 Dec 2025, 10:30'
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date string
 */
export function formatDate(dateString) {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;

  const day = date.getDate().toString().padStart(2, '0');
  const monthNames = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const month = monthNames[date.getMonth()];
  const year = date.getFullYear();
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');

  return `${day} ${month} ${year}, ${hours}:${minutes}`;
}

/**
 * Returns a CSS colour string based on severity level.
 * @param {string} severity - 'High', 'Medium', or 'Low'
 * @returns {string} Hex colour string
 */
export function getSeverityColor(severity) {
  switch ((severity || '').toLowerCase()) {
    case 'high':
      return '#e74c3c';
    case 'medium':
      return '#f39c12';
    case 'low':
      return '#27ae60';
    default:
      return '#95a5a6';
  }
}

/**
 * Send a message directly to a running Rasa REST webhook.
 * Example Rasa endpoint: http://localhost:5005/webhooks/rest/webhook
 * @param {string} message
 * @param {string} senderId
 */
export async function sendMessageToRasa(message, senderId = 'web_user') {
  const url =
    (window?.RASA_WEBHOOK_URL) ||
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_RASA_WEBHOOK_URL) ||
    'http://localhost:5005/webhooks/rest/webhook';
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender: senderId, message }),
    });
  } catch (err) {
    console.error('Network error contacting Rasa:', err);
    throw new Error(`Network error contacting Rasa at ${url}: ${err.message}`);
  }

  if (!res.ok) {
    let details = '';
    try {
      details = await res.text();
    } catch (e) {
      details = '';
    }
    throw new Error(`Rasa request failed: ${res.status} ${details}`);
  }

  try {
    const json = await res.json(); // array of bot messages
    // If Rasa returned an empty array, try to get more details from the /status endpoint
    if (Array.isArray(json) && json.length === 0) {
      try {
        const base = url.replace(/\/webhooks\/rest\/webhook\/?$/, '');
        const statusRes = await fetch(`${base}/status`);
        if (statusRes.ok) {
          const statusJson = await statusRes.json();
          if (statusJson && statusJson.status === 'failure' && statusJson.message) {
            throw new Error(`Rasa status: ${statusJson.message}`);
          }
        } else if (statusRes.status) {
          const text = await statusRes.text().catch(() => '');
          throw new Error(`Rasa status check failed: ${statusRes.status} ${text}`);
        }
      } catch (e) {
        // surface status errors to frontend
        throw e;
      }
    }
    return json;
  } catch (err) {
    let details = '';
    try {
      details = await res.clone().text();
    } catch (e) {
      details = '';
    }
    console.error('Invalid JSON response from Rasa:', err, details);
    throw new Error(`Invalid JSON response from Rasa: ${details}`);
  }
}

/**
 * Send a message to the project's backend proxy which forwards to Rasa.
 * Useful when you want to attach auth/session info in the backend.
 * @param {string} message
 * @param {string} senderId
 */
export async function sendMessageToBackend(message, senderId = 'web_user') {
  const url = '/api/chat';
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sender: senderId, message }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Backend chat proxy failed: ${res.status} ${errText}`);
  }
  return res.json(); // forwarded Rasa response
}
