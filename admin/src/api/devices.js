import apiClient from './client';

/**
 * Fetch device list from API
 * @param {AbortSignal} signal - Cancellation signal for timeout/user abort (P0: Quality gate)
 * @returns {Promise<Array>} Device list
 */
export async function fetchDevices(signal) {
  try {
    const response = await apiClient.get('/api/devices', { signal });

    // P0: response.ok equivalent check (axios auto-rejects non-2xx, but documented here)
    if (response.status >= 200 && response.status < 300) {
      // TODO(Phase 2): Add schema validation (zod) for robust API response checking
      // Currently using simple fallback for prototype speed
      return response.data.devices || [];
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    // P0: Error vocabulary mapping (quality-rules.md compliant)
    // TODO(Phase 2): Implement i18n for user-facing error messages
    if (error.domainError === 'NotFound') {
      return []; // 404 = empty array
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('Service is busy. Please try again later.');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('Request timed out. Please try again.');
    }

    // Other errors
    throw new Error('Failed to fetch device information.');
  }
}
