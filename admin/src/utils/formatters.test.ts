import { describe, it, expect } from 'vitest'
import { ref } from 'vue'
import { formatDeviceName, formatStatus, formatRelativeTime } from './formatters'

describe('formatDeviceName', () => {
  it('should format known device IDs', () => {
    expect(formatDeviceName('PokepalDevice1')).toBe('Device #1 (RaspberryPi)')
    expect(formatDeviceName('PokepalDevice2')).toBe('Device #2 (Jetson)')
  })

  it('should return original ID for unknown devices', () => {
    expect(formatDeviceName('UnknownDevice')).toBe('UnknownDevice')
    expect(formatDeviceName('PokepalDevice3')).toBe('PokepalDevice3')
  })
})

describe('formatStatus', () => {
  it('should format known statuses with emoji', () => {
    expect(formatStatus('online')).toBe('🟢 オンライン')
    expect(formatStatus('offline')).toBe('🔴 オフライン')
    expect(formatStatus('unknown')).toBe('⚪ 不明')
  })

  it('should return original status for unknown values', () => {
    expect(formatStatus('pending')).toBe('pending')
    expect(formatStatus('error')).toBe('error')
  })
})

describe('formatRelativeTime', () => {
  const BASE_TIME = new Date('2024-01-01T12:00:00Z').getTime()

  it('should return "不明" for null or undefined', () => {
    expect(formatRelativeTime(null)).toBe('不明')
    expect(formatRelativeTime(undefined)).toBe('不明')
  })

  it('should return "不明" for invalid timestamp', () => {
    expect(formatRelativeTime('invalid-date', BASE_TIME)).toBe('不明')
    expect(formatRelativeTime('not a date', BASE_TIME)).toBe('不明')
  })

  it('should return "たった今" for time within 1 minute', () => {
    const timestamp = '2024-01-01T11:59:30Z' // 30 seconds ago
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('たった今')
  })

  it('should format minutes correctly (past)', () => {
    const timestamp = '2024-01-01T11:55:00Z' // 5 minutes ago
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('5分前')
  })

  it('should format hours correctly (past)', () => {
    const timestamp = '2024-01-01T10:00:00Z' // 2 hours ago
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('2時間前')
  })

  it('should format days correctly (past)', () => {
    const timestamp = '2023-12-30T12:00:00Z' // 2 days ago
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('2日前')
  })

  it('should format future times with "後" suffix', () => {
    const futureTimestamp = '2024-01-01T12:05:00Z' // 5 minutes in future
    expect(formatRelativeTime(futureTimestamp, BASE_TIME)).toBe('5分後')
  })

  it('should work with Vue Ref<number>', () => {
    const currentTime = ref(BASE_TIME)
    const timestamp = '2024-01-01T11:55:00Z' // 5 minutes ago
    expect(formatRelativeTime(timestamp, currentTime)).toBe('5分前')
  })

  it('should work with number directly', () => {
    const timestamp = '2024-01-01T11:55:00Z' // 5 minutes ago
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('5分前')
  })

  it('should add Z suffix if timezone is missing', () => {
    const timestamp = '2024-01-01T11:55:00' // No Z
    expect(formatRelativeTime(timestamp, BASE_TIME)).toBe('5分前')
  })

  it('should not add Z if timezone already present', () => {
    const timestampWithZ = '2024-01-01T11:55:00Z'
    const timestampWithOffset = '2024-01-01T11:55:00+09:00'

    expect(formatRelativeTime(timestampWithZ, BASE_TIME)).toBe('5分前')
    // +09:00 means Japan time, so 11:55+09:00 = 02:55 UTC = ~9 hours ago from 12:00 UTC
    expect(formatRelativeTime(timestampWithOffset, BASE_TIME)).toBe('9時間前')
  })

  it('should use Date.now() when no currentTime provided', () => {
    const recentTimestamp = new Date(Date.now() - 30000).toISOString() // 30 seconds ago
    expect(formatRelativeTime(recentTimestamp)).toBe('たった今')
  })
})
