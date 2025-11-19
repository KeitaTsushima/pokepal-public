import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useToastStore } from './toast'

describe('useToastStore', () => {
  beforeEach(() => {
    // Create a fresh Pinia instance for each test
    setActivePinia(createPinia())
    // Mock timers
    vi.useFakeTimers()
  })

  afterEach(() => {
    // Restore real timers
    vi.restoreAllMocks()
  })

  it('should initialize with empty toasts', () => {
    const store = useToastStore()
    expect(store.toasts).toEqual([])
  })

  it('should add a success toast', () => {
    const store = useToastStore()
    store.showSuccess('Success message')

    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0]).toMatchObject({
      id: 0,
      message: 'Success message',
      type: 'success',
      duration: 3000,
    })
  })

  it('should add an error toast', () => {
    const store = useToastStore()
    store.showError('Error message')

    expect(store.toasts).toHaveLength(1)
    expect(store.toasts[0]).toMatchObject({
      id: 0,
      message: 'Error message',
      type: 'error',
      duration: 5000,
    })
  })

  it('should add multiple toasts', () => {
    const store = useToastStore()
    store.showSuccess('First message')
    store.showError('Second message')
    store.showSuccess('Third message')

    expect(store.toasts).toHaveLength(3)
    expect(store.toasts[0].message).toBe('First message')
    expect(store.toasts[1].message).toBe('Second message')
    expect(store.toasts[2].message).toBe('Third message')
  })

  it('should auto-dismiss success toast after 3 seconds', () => {
    const store = useToastStore()
    store.showSuccess('Auto dismiss')

    expect(store.toasts).toHaveLength(1)

    // Fast-forward time by 3 seconds
    vi.advanceTimersByTime(3000)

    expect(store.toasts).toHaveLength(0)
  })

  it('should auto-dismiss error toast after 5 seconds', () => {
    const store = useToastStore()
    store.showError('Auto dismiss error')

    expect(store.toasts).toHaveLength(1)

    // Fast-forward time by 5 seconds
    vi.advanceTimersByTime(5000)

    expect(store.toasts).toHaveLength(0)
  })

  it('should allow custom duration for success toast', () => {
    const store = useToastStore()
    store.showSuccess('Custom duration', 1000)

    expect(store.toasts).toHaveLength(1)

    // Fast-forward time by 1 second
    vi.advanceTimersByTime(1000)

    expect(store.toasts).toHaveLength(0)
  })

  it('should manually dismiss a toast', () => {
    const store = useToastStore()
    store.showSuccess('Manual dismiss')

    const toastId = store.toasts[0].id
    store.dismissToast(toastId)

    expect(store.toasts).toHaveLength(0)
  })

  it('should cancel auto-dismiss when manually dismissed', () => {
    const store = useToastStore()
    store.showSuccess('Cancel auto-dismiss')

    const toastId = store.toasts[0].id

    // Manually dismiss before timeout
    store.dismissToast(toastId)
    expect(store.toasts).toHaveLength(0)

    // Fast-forward time - should not cause errors
    vi.advanceTimersByTime(3000)
    expect(store.toasts).toHaveLength(0)
  })

  it('should handle dismissing non-existent toast gracefully', () => {
    const store = useToastStore()

    // Should not throw error
    expect(() => {
      store.dismissToast(999)
    }).not.toThrow()
  })

  it('should generate unique IDs for each toast', () => {
    const store = useToastStore()
    store.showSuccess('First')
    store.showSuccess('Second')
    store.showSuccess('Third')

    const ids = store.toasts.map(t => t.id)
    const uniqueIds = new Set(ids)

    expect(uniqueIds.size).toBe(3)
    expect(ids).toEqual([0, 1, 2])
  })
})
