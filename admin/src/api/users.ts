import apiClient from './client'

const API_BASE_URL = 'https://pokepal-user-api.azurewebsites.net'

// ==================== Type Definitions ====================

/**
 * User object structure
 */
export interface User {
  id: string
  name: string
  nickname?: string
  deviceId?: string
  // Add other fields as needed based on API response
}

/**
 * API response structure for user list
 */
interface UserListResponse {
  users: User[]
}

// ==================== Function Signatures ====================

/**
 * Fetch all users from API
 */
export async function fetchUsers(signal: AbortSignal): Promise<User[]> {
  try {
    const response = await apiClient.get<UserListResponse>(`${API_BASE_URL}/api/users`, { signal })
    return response.data?.users || []
  } catch (error: unknown) {
    // Type guard for domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      if (typeof domainError === 'string') {
        if (domainError === 'NotFound') {
          return []
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('サービスが利用できません。しばらくしてから再試行してください。')
        }

        if (domainError === 'Timeout') {
          throw new Error('リクエストがタイムアウトしました。再試行してください。')
        }
      }
    }

    throw new Error('利用者情報の取得に失敗しました。')
  }
}

/**
 * Fetch user by ID
 */
export async function fetchUserById(id: string, signal: AbortSignal): Promise<User> {
  try {
    const response = await apiClient.get<User>(`${API_BASE_URL}/api/users/${id}`, { signal })

    if (!response.data) {
      throw new Error('Empty response from server')
    }

    return response.data
  } catch (error: unknown) {
    // Type guard for domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      if (typeof domainError === 'string') {
        if (domainError === 'NotFound') {
          throw new Error('指定された利用者が見つかりません。')
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('サービスが利用できません。しばらくしてから再試行してください。')
        }

        if (domainError === 'Timeout') {
          throw new Error('リクエストがタイムアウトしました。再試行してください。')
        }
      }
    }

    throw new Error('利用者情報の取得に失敗しました。')
  }
}

/**
 * Create new user
 */
export async function createUser(userData: Omit<User, 'id'>, signal: AbortSignal): Promise<User> {
  try {
    const response = await apiClient.post<User>(`${API_BASE_URL}/api/users`, userData, { signal })

    if (!response.data) {
      throw new Error('Empty response from server')
    }

    return response.data
  } catch (error: unknown) {
    // Type guard for domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      if (typeof domainError === 'string') {
        if (domainError === 'Conflict') {
          throw new Error('すでに同じIDの利用者が存在します。')
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('サービスが利用できません。しばらくしてから再試行してください。')
        }

        if (domainError === 'Timeout') {
          throw new Error('リクエストがタイムアウトしました。再試行してください。')
        }
      }
    }

    throw new Error('利用者の登録に失敗しました。')
  }
}

/**
 * Update user
 */
export async function updateUser(id: string, userData: Partial<Omit<User, 'id'>>, signal: AbortSignal): Promise<User> {
  try {
    const response = await apiClient.put<User>(`${API_BASE_URL}/api/users/${id}`, userData, { signal })

    if (!response.data) {
      throw new Error('Empty response from server')
    }

    return response.data
  } catch (error: unknown) {
    // Type guard for domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      if (typeof domainError === 'string') {
        if (domainError === 'NotFound') {
          throw new Error('指定された利用者が見つかりません。')
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('サービスが利用できません。しばらくしてから再試行してください。')
        }

        if (domainError === 'Timeout') {
          throw new Error('リクエストがタイムアウトしました。再試行してください。')
        }
      }
    }

    throw new Error('利用者情報の更新に失敗しました。')
  }
}

/**
 * Delete user
 */
export async function deleteUser(id: string, signal: AbortSignal): Promise<void> {
  try {
    await apiClient.delete(`${API_BASE_URL}/api/users/${id}`, { signal })
  } catch (error: unknown) {
    // Type guard for domainError
    if (typeof error === 'object' && error !== null && 'domainError' in error) {
      const domainError = (error as { domainError?: string }).domainError

      if (typeof domainError === 'string') {
        if (domainError === 'NotFound') {
          throw new Error('指定された利用者が見つかりません。')
        }

        if (domainError === 'ServiceUnavailable') {
          throw new Error('サービスが利用できません。しばらくしてから再試行してください。')
        }

        if (domainError === 'Timeout') {
          throw new Error('リクエストがタイムアウトしました。再試行してください。')
        }
      }
    }

    throw new Error('利用者の削除に失敗しました。')
  }
}
