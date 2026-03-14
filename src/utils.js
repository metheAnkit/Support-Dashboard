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
