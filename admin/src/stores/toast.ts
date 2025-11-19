import { defineStore } from 'pinia'
import { ref, onScopeDispose, type Ref } from 'vue'

/**
 * Toast type - success or error
 */
export type ToastType = 'success' | 'error'

/**
 * Toast message structure
 */
export interface Toast {
  id: number
  message: string
  type: ToastType
  duration: number
}

/**
 * Toast store composable return type
 */
export interface ToastStore {
  toasts: Ref<Toast[]>
  showSuccess: (message: string, duration?: number) => void
  showError: (message: string, duration?: number) => void
  dismissToast: (id: number) => void
}

/**
 * Toast store for displaying temporary notifications
 */
export const useToastStore = defineStore('toast', (): ToastStore => {
  const toasts = ref<Toast[]>([])
  let nextId = 0
  const timeoutMap = new Map<number, ReturnType<typeof setTimeout>>()

  /**
   * Helper function to create and schedule a toast
   * @param message - Toast message
   * @param type - Toast type (success or error)
   * @param duration - Display duration in milliseconds
   */
  function createToast(message: string, type: ToastType, duration: number): void {
    const id = nextId++
    toasts.value.push({
      id,
      message,
      type,
      duration,
    })

    // Auto-dismiss after duration
    const timeoutId = setTimeout(() => {
      dismissToast(id)
    }, duration)

    // Store timeout ID for cleanup
    timeoutMap.set(id, timeoutId)
  }

  /**
   * Show a success message
   * @param message - Success message to display
   * @param duration - Display duration in milliseconds (default: 3000)
   */
  function showSuccess(message: string, duration = 3000): void {
    createToast(message, 'success', duration)
  }

  /**
   * Show an error message
   * @param message - Error message to display
   * @param duration - Display duration in milliseconds (default: 5000)
   */
  function showError(message: string, duration = 5000): void {
    createToast(message, 'error', duration)
  }

  /**
   * Dismiss a specific toast
   * @param id - Toast ID to dismiss
   */
  function dismissToast(id: number): void {
    // Clear scheduled timeout if exists
    const timeoutId = timeoutMap.get(id)
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId)
      timeoutMap.delete(id)
    }

    // Remove toast from array
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  // Cleanup all timeouts when store is disposed
  onScopeDispose(() => {
    // Clear all scheduled timeouts
    timeoutMap.forEach(timeoutId => {
      clearTimeout(timeoutId)
    })
    timeoutMap.clear()

    // Clear all toasts
    toasts.value = []
  })

  return {
    toasts,
    showSuccess,
    showError,
    dismissToast,
  }
})
