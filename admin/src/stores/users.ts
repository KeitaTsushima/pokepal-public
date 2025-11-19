import { defineStore } from 'pinia'
import { ref, type Ref } from 'vue'
import { fetchUsers, createUser, updateUser, deleteUser, type User } from '../api/users'
import { connectSignalR, disconnectSignalR, onUserUpdated, onUserDeleted } from '../utils/signalr'

export const useUsersStore = defineStore('users', () => {
  const users: Ref<User[]> = ref([])
  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)

  let abortController: AbortController | null = null
  let signalRInitialized = false
  let signalRInitializing = false
  let unregisterUpdateHandler: (() => void) | null = null
  let unregisterDeleteHandler: (() => void) | null = null

  async function loadUsers(): Promise<void> {
    if (abortController) {
      abortController.abort()
    }

    const currentController = new AbortController()
    abortController = currentController

    loading.value = true
    error.value = null

    try {
      users.value = await fetchUsers(currentController.signal)

      if (!signalRInitialized && !signalRInitializing) {
        signalRInitializing = true
        try {
          await initializeSignalR()
        } finally {
          signalRInitializing = false
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
    } finally {
      if (abortController === currentController) {
        loading.value = false
        abortController = null
      }
    }
  }

  async function initializeSignalR(): Promise<boolean> {
    if (signalRInitialized) {
      return true
    }

    try {
      await connectSignalR()

      if (unregisterUpdateHandler) {
        unregisterUpdateHandler()
        unregisterUpdateHandler = null
      }

      if (unregisterDeleteHandler) {
        unregisterDeleteHandler()
        unregisterDeleteHandler = null
      }

      unregisterUpdateHandler = onUserUpdated(updatedUser => {
        console.log('[Store] Received user update:', updatedUser)

        const index = users.value.findIndex(u => u.id === updatedUser.id)
        if (index !== -1) {
          users.value[index] = updatedUser
        } else {
          users.value.push(updatedUser)
        }
      })

      unregisterDeleteHandler = onUserDeleted(deletedUser => {
        console.log('[Store] Received user deletion:', deletedUser)

        users.value = users.value.filter(u => u.id !== deletedUser.id)
      })

      signalRInitialized = true
      return true
    } catch (err) {
      console.error('Failed to initialize SignalR:', err)
      return false
    }
  }

  function cleanup(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    if (unregisterUpdateHandler) {
      unregisterUpdateHandler()
      unregisterUpdateHandler = null
    }

    if (unregisterDeleteHandler) {
      unregisterDeleteHandler()
      unregisterDeleteHandler = null
    }

    disconnectSignalR()
    signalRInitialized = false
    signalRInitializing = false

    users.value = []
    loading.value = false
    error.value = null
  }

  async function addUser(userData: User): Promise<User> {
    const controller = new AbortController()
    loading.value = true
    error.value = null

    try {
      const newUser = await createUser(userData, controller.signal)
      // Don't add locally - let SignalR event handler do it
      // This prevents duplicate entries in the creating browser
      return newUser
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function modifyUser(id: string, userData: Partial<User>): Promise<User> {
    const controller = new AbortController()
    loading.value = true
    error.value = null

    try {
      const updatedUser = await updateUser(id, userData, controller.signal)
      // Don't update locally - let SignalR event handler do it
      return updatedUser
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function removeUser(id: string): Promise<void> {
    const controller = new AbortController()
    loading.value = true
    error.value = null

    try {
      await deleteUser(id, controller.signal)
      // Don't remove locally - let SignalR event handler do it
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
      throw err
    } finally {
      loading.value = false
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
    cleanup,
  }
})
