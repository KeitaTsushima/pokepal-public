import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { onDeviceUpdated, onUserUpdated, onUserDeleted, disconnectSignalR } from './signalr'

describe('signalr event listeners', () => {
  beforeEach(() => {
    // Disconnect any existing connection before each test
    vi.clearAllMocks()
  })

  afterEach(async () => {
    // Clean up connection after each test
    await disconnectSignalR()
  })

  describe('onDeviceUpdated', () => {
    it('should return cleanup function when not connected', () => {
      const callback = vi.fn()
      const cleanup = onDeviceUpdated(callback)

      expect(typeof cleanup).toBe('function')
      cleanup() // Should not throw
    })
  })

  describe('onUserUpdated', () => {
    it('should return cleanup function when not connected', () => {
      const callback = vi.fn()
      const cleanup = onUserUpdated(callback)

      expect(typeof cleanup).toBe('function')
      cleanup() // Should not throw
    })
  })

  describe('onUserDeleted', () => {
    it('should return cleanup function when not connected', () => {
      const callback = vi.fn()
      const cleanup = onUserDeleted(callback)

      expect(typeof cleanup).toBe('function')
      cleanup() // Should not throw
    })
  })

  describe('disconnectSignalR', () => {
    it('should not throw when disconnecting without connection', async () => {
      await expect(disconnectSignalR()).resolves.toBeUndefined()
    })
  })
})

// Note: connectSignalR is not tested here because it requires:
// - External API (negotiate endpoint)
// - WebSocket connection
// - These should be tested in integration/e2e tests with proper mocks
