import { HubConnection, HubConnectionBuilder, LogLevel } from '@microsoft/signalr'
import type { Device } from '../api/devices'

const NEGOTIATE_URL =
  import.meta.env.VITE_SIGNALR_NEGOTIATE_URL ||
  'https://pokepal-realtime-api.azurewebsites.net/api/negotiate'

// ===== Type Definitions =====

/** Negotiate API response structure */
interface NegotiateResponse {
  url: string
  accessToken: string
}

/** User update event payload */
export interface UserUpdate {
  id: string
  name: string
  tasks: Array<{ id: string; description: string }>
}

/** User deletion event payload */
export interface UserDelete {
  id: string
}

// ===== Module State =====

let connection: HubConnection | null = null

/**
 * Establish SignalR connection
 * @returns The established connection
 * @throws Error if negotiate or connection fails
 */
export async function connectSignalR(): Promise<HubConnection> {
  if (connection) {
    console.log('[SignalR] Already connected')
    return connection
  }

  try {
    // 1. Get connection info from negotiate endpoint (with timeout)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout

    let response: Response
    try {
      response = await fetch(NEGOTIATE_URL, { signal: controller.signal })
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('negotiate request timeout (5s)')
      }
      throw error
    } finally {
      clearTimeout(timeoutId)
    }

    if (!response.ok) {
      throw new Error(`negotiate failed: ${response.status}`)
    }
    const data = await response.json()

    // 2. Validate response structure
    if (!data || typeof data !== 'object') {
      throw new Error('negotiate response is not an object')
    }
    if (typeof data.url !== 'string' || !data.url) {
      throw new Error('negotiate response missing or invalid "url"')
    }
    if (typeof data.accessToken !== 'string' || !data.accessToken) {
      throw new Error('negotiate response missing or invalid "accessToken"')
    }

    const { url, accessToken } = data as NegotiateResponse

    // 2. Build SignalR connection
    connection = new HubConnectionBuilder()
      .withUrl(url, {
        accessTokenFactory: async () => {
          // Always fetch fresh token on reconnect
          try {
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 5000)
            try {
              const response = await fetch(NEGOTIATE_URL, { signal: controller.signal })
              clearTimeout(timeoutId)
              if (!response.ok) return accessToken // Fallback to initial token
              const data = await response.json()
              return data.accessToken || accessToken
            } finally {
              clearTimeout(timeoutId)
            }
          } catch {
            return accessToken // Fallback on error (including timeout)
          }
        },
      })
      .configureLogging(LogLevel.Information)
      .withAutomaticReconnect()
      .build()

    // 3. Start connection
    await connection.start()
    console.log('[SignalR] Connected')

    return connection
  } catch (error) {
    console.error('[SignalR] Connection failed:', error)
    connection = null
    throw error
  }
}

/**
 * Disconnect SignalR connection
 */
export async function disconnectSignalR(): Promise<void> {
  if (connection) {
    await connection.stop()
    connection = null
    console.log('[SignalR] Disconnected')
  }
}

/**
 * Listen to deviceUpdated events
 * @param callback - Function to call when devices are updated (receives array)
 * @returns Cleanup function to unsubscribe the handler
 */
export function onDeviceUpdated(callback: (data: Device[]) => void): () => void {
  if (!connection) {
    console.warn('[SignalR] Not connected')
    return () => {} // no-op cleanup function
  }

  connection.on('deviceUpdated', callback)

  // Return cleanup function
  return () => connection?.off('deviceUpdated', callback)
}

/**
 * Listen to userUpdated events
 * @param callback - Function to call when user is updated
 * @returns Cleanup function to unsubscribe the handler
 */
export function onUserUpdated(callback: (data: UserUpdate) => void): () => void {
  if (!connection) {
    console.warn('[SignalR] Not connected')
    return () => {} // no-op cleanup function
  }

  connection.on('userUpdated', callback)

  // Return cleanup function
  return () => connection?.off('userUpdated', callback)
}

/**
 * Listen to userDeleted events
 * @param callback - Function to call when user is deleted
 * @returns Cleanup function to unsubscribe the handler
 */
export function onUserDeleted(callback: (data: UserDelete) => void): () => void {
  if (!connection) {
    console.warn('[SignalR] Not connected')
    return () => {} // no-op cleanup function
  }

  connection.on('userDeleted', callback)

  // Return cleanup function
  return () => connection?.off('userDeleted', callback)
}
