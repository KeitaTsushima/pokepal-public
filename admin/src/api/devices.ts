import apiClient from './client'

/**
 * Device status values
 */
export type DeviceStatus = 'online' | 'offline' | 'unknown'

/**
 * Device type returned from API
 */
export interface Device {
  deviceId: string
  status: DeviceStatus
  lastSeen: string
}

/**
 * API response structure for device list
 */
interface DeviceListResponse {
  devices: Device[]
}

/**
 * Fetch device list from API
 * @param signal - Cancellation signal for timeout/user abort (P0: Quality gate)
 * @returns Device list
 */
export async function fetchDevices(signal: AbortSignal): Promise<Device[]> {
  try {
    const response = await apiClient.get<DeviceListResponse>('/api/devices', { signal })

    // axios auto-rejects non-2xx responses, so we only handle success here
    // TODO(Phase 2): Add schema validation (zod) for robust API response checking
    // Currently using simple fallback for prototype speed
    return response.data.devices || []
  } catch (error: unknown) {
    // P0: Error vocabulary mapping (quality-rules.md compliant)
    // TODO(Phase 2): Implement i18n for user-facing error messages

    // Type guard for axios error with domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      // Ensure domainError is actually a string before comparison
      if (typeof domainError === 'string') {
        if (domainError === 'NotFound') {
          return [] // 404 = empty array
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('Service is busy. Please try again later.')
        }

        if (domainError === 'Timeout') {
          throw new Error('Request timed out. Please try again.')
        }
      }
    }

    // Other errors
    throw new Error('Failed to fetch device information.')
  }
}
