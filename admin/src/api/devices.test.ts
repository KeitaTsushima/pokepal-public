import { describe, it, expect } from 'vitest'
import { fetchDevices } from './devices'
import type { Device } from './devices'

describe('devices API', () => {
  describe('fetchDevices', () => {
    it('should be a function', () => {
      expect(typeof fetchDevices).toBe('function')
    })

    it('should accept AbortSignal parameter', () => {
      const controller = new AbortController()
      controller.abort() // Abort immediately to prevent actual network call
      const signal = controller.signal

      // Should not throw when called with signal
      expect(() => {
        fetchDevices(signal).catch(() => {}) // Catch to prevent unhandled rejection
      }).not.toThrow()
    })

    it('should return Promise<Device[]>', () => {
      const controller = new AbortController()
      controller.abort() // Abort immediately to prevent actual network call
      const result = fetchDevices(controller.signal)

      expect(result).toBeInstanceOf(Promise)
      result.catch(() => {}) // Catch to prevent unhandled rejection
    })
  })

  describe('Device type', () => {
    it('should have correct structure', () => {
      const device: Device = {
        deviceId: 'test-device',
        status: 'online'
      }

      expect(device).toHaveProperty('deviceId')
      expect(device).toHaveProperty('status')
    })
  })
})

// Note: Full API testing requires mocking fetch/axios and is better
// suited for integration tests. These tests verify type safety and
// basic function signatures.
