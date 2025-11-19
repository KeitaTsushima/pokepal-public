import { defineStore } from 'pinia'
import { ref, type Ref } from 'vue'
import { fetchDevices, type Device } from '../api/devices'
import { connectSignalR, disconnectSignalR, onDeviceUpdated } from '../utils/signalr'

export const useDevicesStore = defineStore('devices', () => {
  const devices: Ref<Device[]> = ref([])
  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)

  // P0: Abort controller for cancellation (Quality gate)
  let abortController: AbortController | null = null
  let signalRInitialized = false
  let unregisterDeviceHandler: (() => void) | null = null

  async function loadDevices(): Promise<void> {
    // P0: Cancel previous request if exists (concurrency control)
    if (abortController) {
      abortController.abort()
    }

    const currentController = new AbortController()
    abortController = currentController
    loading.value = true
    error.value = null

    try {
      // TODO: Merge fetched devices instead of replacing to avoid overwriting SignalR updates
      // See: CodeRabbit suggestion - compare timestamps and merge intelligently
      devices.value = await fetchDevices(currentController.signal)

      // Connect to SignalR after initial data load (only once)
      if (!signalRInitialized) {
        const success = await initializeSignalR()
        if (success) {
          signalRInitialized = true
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Cancelled by user, do nothing
        return
      }
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
    } finally {
      // Only clear if this is still the active request
      if (abortController === currentController) {
        loading.value = false
        abortController = null
      }
    }
  }

  async function initializeSignalR(): Promise<boolean> {
    try {
      await connectSignalR()

      // Register handler for device updates and store the unregister function
      unregisterDeviceHandler = onDeviceUpdated((updatedDevices: Device[]) => {
        console.log('[Store] Received device update:', updatedDevices)

        // Merge updated devices with existing devices
        updatedDevices.forEach(updated => {
          // SignalR callback nesting is unavoidable, findIndex is standard pattern
          // eslint-disable-next-line sonarjs/no-nested-functions
          const index = devices.value.findIndex(d => d.deviceId === updated.deviceId)
          if (index !== -1) {
            // Update existing device
            devices.value[index] = updated
          } else {
            // Add new device
            devices.value.push(updated)
          }
        })
      })

      return true
    } catch (err) {
      console.error('[Store] SignalR initialization failed:', err)
      // Don't show error to user - initial data is already loaded
      return false
    }
  }

  function cleanup(): void {
    // Abort any in-flight requests
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    // Unregister SignalR event handler
    if (unregisterDeviceHandler) {
      unregisterDeviceHandler()
      unregisterDeviceHandler = null
    }

    // Disconnect SignalR
    disconnectSignalR()
    signalRInitialized = false

    // Reset store state
    devices.value = []
    loading.value = false
    error.value = null
  }

  return {
    devices,
    loading,
    error,
    loadDevices,
    cleanup,
  }
})
