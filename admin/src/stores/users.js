import { defineStore } from 'pinia';
import { ref } from 'vue';
import { fetchUsers, createUser, updateUser, deleteUser } from '../api/users';

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
   * Add new user
   * @param {Object} userData - User data
   */
  async function addUser(userData) {
    loading.value = true;
    error.value = null;

    try {
      const newUser = await createUser(userData);
      users.value.push(newUser);
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

      // Update in local state
      const index = users.value.findIndex(u => u.id === id);
      if (index !== -1) {
        users.value[index] = updatedUser;
      }

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

      // Remove from local state
      users.value = users.value.filter(u => u.id !== id);
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
    removeUser
  };
});
