import { describe, it, expect } from 'vitest'
import apiClient from './client'

describe('apiClient', () => {
  it('should be an axios instance', () => {
    expect(apiClient).toBeDefined()
    expect(typeof apiClient.get).toBe('function')
    expect(typeof apiClient.post).toBe('function')
    expect(typeof apiClient.put).toBe('function')
    expect(typeof apiClient.delete).toBe('function')
  })

  it('should have default timeout configured', () => {
    expect(apiClient.defaults.timeout).toBe(10000)
  })

  it('should have baseURL configured', () => {
    expect(apiClient.defaults.baseURL).toBeDefined()
    expect(typeof apiClient.defaults.baseURL).toBe('string')
  })

  it('should have request interceptor configured', () => {
    expect(apiClient.interceptors.request.handlers.length).toBeGreaterThan(0)
  })

  it('should have response interceptor configured', () => {
    expect(apiClient.interceptors.response.handlers.length).toBeGreaterThan(0)
  })
})

// Note: Testing interceptor behavior requires mocking axios calls
// and is better suited for integration tests. The above tests verify
// that the client is properly configured.
