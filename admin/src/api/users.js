import apiClient from './client';

const API_BASE_URL = 'https://pokepal-user-api.azurewebsites.net';

/**
 * Fetch all users from API
 * @param {AbortSignal} signal - Cancellation signal
 * @returns {Promise<Array>} User list
 */
export async function fetchUsers(signal) {
  try {
    const response = await apiClient.get(`${API_BASE_URL}/api/users`, { signal });

    if (response.status >= 200 && response.status < 300) {
      // API returns {users: [...]} structure
      return response.data?.users || [];
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    if (error.domainError === 'NotFound') {
      return [];
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('サービスが利用できません。しばらくしてから再試行してください。');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('リクエストがタイムアウトしました。再試行してください。');
    }

    throw new Error('利用者情報の取得に失敗しました。');
  }
}

/**
 * Fetch user by ID
 * @param {string} id - User ID
 * @param {AbortSignal} signal - Cancellation signal
 * @returns {Promise<Object>} User object
 */
export async function fetchUserById(id, signal) {
  try {
    const response = await apiClient.get(`${API_BASE_URL}/api/users/${id}`, { signal });

    if (response.status >= 200 && response.status < 300) {
      return response.data;
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    if (error.domainError === 'NotFound') {
      throw new Error('指定された利用者が見つかりません。');
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('サービスが利用できません。しばらくしてから再試行してください。');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('リクエストがタイムアウトしました。再試行してください。');
    }

    throw new Error('利用者情報の取得に失敗しました。');
  }
}

/**
 * Create new user
 * @param {Object} userData - User data (id, name, nickname, deviceId, etc.)
 * @param {AbortSignal} signal - Cancellation signal
 * @returns {Promise<Object>} Created user object
 */
export async function createUser(userData, signal) {
  try {
    const response = await apiClient.post(`${API_BASE_URL}/api/users`, userData, { signal });

    if (response.status >= 200 && response.status < 300) {
      return response.data;
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    if (error.domainError === 'Conflict') {
      throw new Error('すでに同じIDの利用者が存在します。');
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('サービスが利用できません。しばらくしてから再試行してください。');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('リクエストがタイムアウトしました。再試行してください。');
    }

    throw new Error('利用者の登録に失敗しました。');
  }
}

/**
 * Update user
 * @param {string} id - User ID
 * @param {Object} userData - Updated user data
 * @param {AbortSignal} signal - Cancellation signal
 * @returns {Promise<Object>} Updated user object
 */
export async function updateUser(id, userData, signal) {
  try {
    const response = await apiClient.put(`${API_BASE_URL}/api/users/${id}`, userData, { signal });

    if (response.status >= 200 && response.status < 300) {
      return response.data;
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    if (error.domainError === 'NotFound') {
      throw new Error('指定された利用者が見つかりません。');
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('サービスが利用できません。しばらくしてから再試行してください。');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('リクエストがタイムアウトしました。再試行してください。');
    }

    throw new Error('利用者情報の更新に失敗しました。');
  }
}

/**
 * Delete user
 * @param {string} id - User ID
 * @param {AbortSignal} signal - Cancellation signal
 * @returns {Promise<void>}
 */
export async function deleteUser(id, signal) {
  try {
    const response = await apiClient.delete(`${API_BASE_URL}/api/users/${id}`, { signal });

    if (response.status >= 200 && response.status < 300) {
      return;
    }

    throw new Error(`Unexpected status: ${response.status}`);
  } catch (error) {
    if (error.domainError === 'NotFound') {
      throw new Error('指定された利用者が見つかりません。');
    }

    if (error.domainError === 'ServiceUnavailable') {
      throw new Error('サービスが利用できません。しばらくしてから再試行してください。');
    }

    if (error.domainError === 'Timeout') {
      throw new Error('リクエストがタイムアウトしました。再試行してください。');
    }

    throw new Error('利用者の削除に失敗しました。');
  }
}
