import { defineStore } from 'pinia';
import { ref } from 'vue';
import { fetchDevices } from '../api/devices';

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

  return {
    devices,
    loading,
    error,
    loadDevices
  };
});
