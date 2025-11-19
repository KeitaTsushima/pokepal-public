<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useUsersStore } from '../stores/users'
import { useToastStore } from '../stores/toast'
import UserForm from '../components/UserForm.vue'

const usersStore = useUsersStore()
const toastStore = useToastStore()
const showModal = ref(false)
const editingUser = ref(null)
const showDeleteDialog = ref(false)
const deletingUser = ref(null)

// Load users on mount
onMounted(() => {
  usersStore.loadUsers()
})

// Cleanup SignalR on unmount
onUnmounted(() => {
  usersStore.cleanup()
})

// Open create modal
function openCreateModal() {
  editingUser.value = null
  showModal.value = true
}

// Open edit modal
function openEditModal(user) {
  editingUser.value = user
  showModal.value = true
}

// Close modal
function closeModal() {
  showModal.value = false
  editingUser.value = null
}

// Handle user creation or update
async function handleUserSubmit(userData) {
  try {
    if (editingUser.value) {
      // Update existing user
      await usersStore.modifyUser(editingUser.value.id, userData)
      toastStore.showSuccess('利用者を更新しました')
    } else {
      // Create new user
      const userId = `user_${Date.now()}`
      const newUser = { id: userId, ...userData }
      await usersStore.addUser(newUser)
      toastStore.showSuccess('利用者を登録しました')
    }
    closeModal()
  } catch (error) {
    console.error('Failed to save user:', error instanceof Error ? error.message : String(error))
    toastStore.showError('保存に失敗しました')
  }
}

// Open delete confirmation dialog
function confirmDelete(user) {
  deletingUser.value = user
  showDeleteDialog.value = true
}

// Cancel deletion
function cancelDelete() {
  showDeleteDialog.value = false
  deletingUser.value = null
}

// Execute deletion
async function executeDelete() {
  if (!deletingUser.value) return

  try {
    await usersStore.removeUser(deletingUser.value.id)
    toastStore.showSuccess('利用者を削除しました')
    showDeleteDialog.value = false
    deletingUser.value = null
  } catch (error) {
    console.error('Failed to delete user:', error instanceof Error ? error.message : String(error))
    toastStore.showError('削除に失敗しました')
  }
}
</script>

<template>
  <div>
    <div class="header">
      <h2>利用者管理</h2>
      <button @click="openCreateModal" class="btn-primary">新規登録</button>
    </div>

    <!-- Loading state -->
    <div v-if="usersStore.loading">読み込み中...</div>

    <!-- Error state with retry button -->
    <div v-else-if="usersStore.error" class="error-card">
      <p>{{ usersStore.error }}</p>
      <button @click="usersStore.loadUsers()">再試行</button>
    </div>

    <!-- User list -->
    <div v-else>
      <div v-if="usersStore.users.length === 0" class="empty-message">
        利用者が登録されていません
      </div>

      <div v-else>
        <div v-for="user in usersStore.users" :key="user.id" class="user-card">
          <div class="user-info">
            <h3>{{ user.name }}</h3>
            <p>呼び方: {{ user.nickname }}</p>
            <p v-if="user.roomNumber">部屋番号: {{ user.roomNumber }}</p>
            <p>デバイスID: {{ user.deviceId }}</p>
            <p>
              本日の予定:
              <router-link :to="`/users/${user.id}/tasks`" class="proactive-tasks-link">
                {{ user.proactiveTasks?.length || 0 }}件
              </router-link>
            </p>
            <p v-if="user.notes" class="notes">{{ user.notes }}</p>
          </div>
          <div class="user-actions">
            <button @click="openEditModal(user)" class="btn-edit">編集</button>
            <button @click="confirmDelete(user)" class="btn-delete">削除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit/Create Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingUser ? '利用者編集' : '新規利用者登録' }}</h3>
          <button @click="closeModal" class="close-button">&times;</button>
        </div>
        <UserForm :user="editingUser" @submit="handleUserSubmit" @cancel="closeModal" />
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <div v-if="showDeleteDialog" class="modal-overlay" @click="cancelDelete">
      <div class="dialog-content" @click.stop>
        <h3>利用者削除の確認</h3>
        <p>以下の利用者を削除してもよろしいですか？</p>
        <div class="delete-user-info">
          <p><strong>氏名:</strong> {{ deletingUser?.name }}</p>
          <p><strong>デバイスID:</strong> {{ deletingUser?.deviceId }}</p>
        </div>
        <p class="warning-text">※この操作は取り消せません</p>
        <div class="dialog-actions">
          <button @click="cancelDelete" class="btn-secondary">キャンセル</button>
          <button @click="executeDelete" class="btn-danger">削除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

h2 {
  margin: 0;
}

.btn-primary {
  padding: 0.5rem 1.5rem;
  background-color: #3b82f6;
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease-in-out;
}

.btn-primary:hover {
  background-color: #2563eb;
}

.user-card {
  border: 1px solid #ddd;
  padding: 15px;
  margin: 10px 0;
  border-radius: 5px;
  background: #f9f9f9;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.user-info {
  flex: 1;
}

.user-info h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.user-info p {
  margin: 5px 0;
  color: #666;
}

.proactive-tasks-link {
  color: #3b82f6;
  font-weight: 500;
  text-decoration: underline;
  cursor: pointer;
}

.user-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.btn-edit {
  padding: 0.5rem 1rem;
  background-color: #10b981;
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease-in-out;
}

.btn-edit:hover {
  background-color: #059669;
}

.btn-delete {
  padding: 0.5rem 1rem;
  background-color: #ef4444;
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease-in-out;
}

.btn-delete:hover {
  background-color: #dc2626;
}

.notes {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ddd;
  font-style: italic;
}

.error-card {
  border: 1px solid #f44;
  padding: 15px;
  margin: 10px 0;
  border-radius: 5px;
  background: #fee;
}

.empty-message {
  padding: 20px;
  text-align: center;
  color: #999;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 2rem;
  border-radius: 0.5rem;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.modal-header h3 {
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  color: #666;
}

.close-button:hover {
  color: #333;
}

/* Delete Dialog */
.dialog-content {
  background: white;
  padding: 2rem;
  border-radius: 0.5rem;
  max-width: 500px;
  width: 90%;
}

.dialog-content h3 {
  margin: 0 0 1rem 0;
  color: #333;
}

.dialog-content p {
  margin: 0.5rem 0;
  color: #666;
}

.delete-user-info {
  background: #f9fafb;
  padding: 1rem;
  border-radius: 0.375rem;
  margin: 1rem 0;
}

.delete-user-info p {
  margin: 0.5rem 0;
}

.warning-text {
  color: #ef4444;
  font-weight: 500;
  margin-top: 1rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1.5rem;
}

.btn-danger {
  padding: 0.5rem 1.5rem;
  background-color: #ef4444;
  color: white;
  border: none;
  border-radius: 0.375rem;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.15s ease-in-out;
}

.btn-danger:hover {
  background-color: #dc2626;
}
</style>
