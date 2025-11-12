import type { Ref } from 'vue'

const DEVICE_NAME_MAPPING: Record<string, string> = {
  'PokepalDevice1': 'Device #1 (RaspberryPi)',
  'PokepalDevice2': 'Device #2 (Jetson)'
}

const STATUS_MAPPING: Record<string, string> = {
  'online': '🟢 オンライン',
  'offline': '🔴 オフライン',
  'unknown': '⚪ 不明'
}

/**
 * Convert device ID to display name
 */
export function formatDeviceName(deviceId: string): string {
  return DEVICE_NAME_MAPPING[deviceId] || deviceId
}

/**
 * Convert status to emoji with text
 */
export function formatStatus(status: string): string {
  return STATUS_MAPPING[status] || status
}

/**
 * Format timestamp to relative time
 * @param timestamp - ISO timestamp string
 * @param currentTime - Current time in ms (Vue ref or number) for auto-update
 * @returns Relative time string (e.g., "5分前", "2時間前", "たった今")
 */
export function formatRelativeTime(
  timestamp: string | null | undefined,
  currentTime?: Ref<number> | number
): string {
  if (!timestamp) return '不明'

  // Extract value from Vue ref or use number directly
  let nowMs: number
  if (!currentTime) {
    nowMs = Date.now()
  } else if (typeof currentTime === 'object' && 'value' in currentTime) {
    nowMs = currentTime.value
  } else {
    nowMs = currentTime
  }
  const now = new Date(nowMs)

  // Add 'Z' suffix if not present to treat as UTC (only if no timezone designator)
  const hasTimezone = /Z|[+-]\d{2}:\d{2}$/.test(timestamp)
  const timestampStr = hasTimezone ? timestamp : timestamp + 'Z'
  const then = new Date(timestampStr)

  // Validate parsed date
  if (isNaN(then.getTime())) {
    return '不明'
  }

  const diffMs = now.getTime() - then.getTime()
  const absDiffMs = Math.abs(diffMs)
  const diffMinutes = Math.floor(absDiffMs / 60000)

  // Near zero: "just now"
  if (diffMinutes < 1) return 'たった今'

  // Determine if past or future
  const isFuture = diffMs < 0
  const suffix = isFuture ? '後' : '前'

  // Minutes
  if (diffMinutes < 60) return `${diffMinutes}分${suffix}`

  // Hours
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}時間${suffix}`

  // Days
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}日${suffix}`
}
