/**
 * Convert device ID to display name
 */
export function formatDeviceName(deviceId) {
  const mapping = {
    'PokepalDevice1': 'Device #1 (RaspberryPi)',
    'PokepalDevice2': 'Device #2 (Jetson)'
  };
  return mapping[deviceId] || deviceId;
}

/**
 * Convert status to emoji with text
 */
export function formatStatus(status) {
  const mapping = {
    'online': '🟢 オンライン',
    'offline': '🔴 オフライン',
    'unknown': '⚪ 不明'
  };
  return mapping[status] || status;
}

/**
 * Format timestamp to relative time
 * @returns {string} Relative time string (e.g., "5分前", "2時間前", "たった今")
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp) return '不明';

  const now = new Date();
  // Add 'Z' suffix if not present to treat as UTC
  const timestampStr = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z';
  const then = new Date(timestampStr);
  const diffMs = now - then;
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return 'たった今';
  if (diffMinutes < 60) return `${diffMinutes}分前`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}時間前`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}日前`;
}
