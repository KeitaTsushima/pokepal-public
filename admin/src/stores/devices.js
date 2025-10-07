import { defineStore } from 'pinia';
import { ref } from 'vue';
import { fetchDevices } from '../api/devices';
import { connectSignalR, disconnectSignalR, onDeviceUpdated } from '../utils/signalr';

export const useDevicesStore = defineStore('devices', () => {
  const devices = ref([]);
  const loading = ref(false);
  const error = ref(null);

  // P0: Abort controller for cancellation (Quality gate)
  let abortController = null;

  async function loadDevices() {
    // P0: Cancel previous request if exists (concurrency control)
    if (abortController) {
      abortController.abort();
    }

    abortController = new AbortController();
    loading.value = true;
    error.value = null;

    try {
      devices.value = await fetchDevices(abortController.signal);

      // Connect to SignalR after initial data load
      await initializeSignalR();
    } catch (err) {
      if (err.name === 'AbortError') {
        // Cancelled by user, do nothing
        return;
      }
      error.value = err.message;
    } finally {
      loading.value = false;
      abortController = null;
    }
  }

  async function initializeSignalR() {
    try {
      await connectSignalR();

      // Register handler for device updates
      onDeviceUpdated((updatedDevices) => {
        console.log('[Store] Received device update:', updatedDevices);

        // Merge updated devices with existing devices
        updatedDevices.forEach(updated => {
          const index = devices.value.findIndex(d => d.deviceId === updated.deviceId);
          if (index !== -1) {
            // Update existing device
            devices.value[index] = updated;
          } else {
            // Add new device
            devices.value.push(updated);
          }
        });
      });
    } catch (err) {
      console.error('[Store] SignalR initialization failed:', err);
      // Don't show error to user - initial data is already loaded
    }
  }

  function cleanup() {
    disconnectSignalR();
  }

  return {
    devices,
    loading,
    error,
    loadDevices,
    cleanup
  };
});
