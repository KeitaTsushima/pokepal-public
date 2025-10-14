import { defineStore } from 'pinia';
import { ref } from 'vue';
import { fetchUsers, createUser, updateUser, deleteUser } from '../api/users';
import { connectSignalR, disconnectSignalR, onUserUpdated, onUserDeleted } from '../utils/signalr';

export const useUsersStore = defineStore('users', () => {
  const users = ref([]);
  const loading = ref(false);
  const error = ref(null);

  // Abort controller for cancellation (Quality gate P0)
  let abortController = null;

  /**
   * Load all users from API
   */
  async function loadUsers() {
    // Cancel previous request if exists (concurrency control)
    if (abortController) {
      abortController.abort();
    }

    abortController = new AbortController();
    loading.value = true;
    error.value = null;

    try {
      users.value = await fetchUsers(abortController.signal);

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

  /**
   * Initialize SignalR connection and register event handlers
   */
  async function initializeSignalR() {
    try {
      await connectSignalR();

      // Register handler for user updates (create/update)
      onUserUpdated((updatedUser) => {
        console.log('[Store] Received user update:', updatedUser);

        const index = users.value.findIndex(u => u.id === updatedUser.id);
        if (index !== -1) {
          // Update existing user
          users.value[index] = updatedUser;
        } else {
          // Add new user
          users.value.push(updatedUser);
        }
      });

      // Register handler for user deletion
      onUserDeleted((deletedUser) => {
        console.log('[Store] Received user deletion:', deletedUser);

        users.value = users.value.filter(u => u.id !== deletedUser.id);
      });
    } catch (err) {
      console.error('[Store] SignalR initialization failed:', err);
      // Don't show error to user - initial data is already loaded
    }
  }

  /**
   * Cleanup SignalR connection
   */
  function cleanup() {
    disconnectSignalR();
  }

  /**
   * Add new user
   * @param {Object} userData - User data
   */
  async function addUser(userData) {
    loading.value = true;
    error.value = null;

    try {
      const newUser = await createUser(userData);
      // Don't add locally - let SignalR event handler do it
      // This prevents duplicate entries in the creating browser
      return newUser;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Update existing user
   * @param {string} id - User ID
   * @param {Object} userData - Updated user data
   */
  async function modifyUser(id, userData) {
    loading.value = true;
    error.value = null;

    try {
      const updatedUser = await updateUser(id, userData);
      // Don't update locally - let SignalR event handler do it
      return updatedUser;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Remove user
   * @param {string} id - User ID
   */
  async function removeUser(id) {
    loading.value = true;
    error.value = null;

    try {
      await deleteUser(id);
      // Don't remove locally - let SignalR event handler do it
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  }

  return {
    users,
    loading,
    error,
    loadUsers,
    addUser,
    modifyUser,
    removeUser,
    cleanup
  };
});
