<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUsersStore } from '../stores/users'
import { useToastStore } from '../stores/toast'
import TaskForm from '../components/TaskForm.vue'

const route = useRoute()
const router = useRouter()
const usersStore = useUsersStore()
const toastStore = useToastStore()

// Get user ID from URL parameter
const userId = route.params.id

// User data - computed to react to store changes (SignalR updates)
const user = computed(() => {
  return usersStore.users.find(u => u.id === userId)
})

const loading = ref(true)

// Modal state
const showModal = ref(false)
const editingTask = ref(null)

// Load user data on mount
onMounted(async () => {
  await loadUsers()
})

/**
 * Load users data from store
 */
async function loadUsers() {
  loading.value = true

  try {
    // Ensure users are loaded
    if (usersStore.users.length === 0) {
      await usersStore.loadUsers()
    }

    if (!user.value) {
      toastStore.showError('利用者が見つかりません')
      router.push('/users')
    }
  } catch (error) {
    console.error('Failed to load users:', error)
    toastStore.showError('利用者情報の取得に失敗しました')
  } finally {
    loading.value = false
  }
}

/**
 * Navigate back to users list
 */
function goBack() {
  router.push('/users')
}

/**
 * Add new task
 */
function addTask() {
  editingTask.value = null
  showModal.value = true
}

/**
 * Edit task
 */
function editTask(task) {
  editingTask.value = JSON.parse(JSON.stringify(task))
  showModal.value = true
}

/**
 * Close modal
 */
function closeModal() {
  showModal.value = false
  editingTask.value = null
}

/**
 * Handle task submission (add or update)
 */
async function handleTaskSubmit(taskData) {
  try {
    const tasks = JSON.parse(JSON.stringify(user.value.proactiveTasks || []))

    if (editingTask.value) {
      // Update existing task
      const index = tasks.findIndex(t => t.id === editingTask.value.id)
      if (index !== -1) {
        tasks[index] = { ...editingTask.value, ...taskData }
      }
    } else {
      // Add new task
      const newTask = {
        id: `task_${Date.now()}`,
        ...taskData,
      }
      tasks.push(newTask)
    }

    // Update user via API
    await usersStore.modifyUser(userId, {
      proactiveTasks: tasks,
    })

    toastStore.showSuccess(editingTask.value ? 'タスクを更新しました' : 'タスクを追加しました')
    closeModal()

    // No need to reload - computed property will auto-update via SignalR
  } catch (error) {
    console.error('Failed to save task:', error)
    toastStore.showError('タスクの保存に失敗しました')
  }
}

/**
 * Delete task
 */
async function deleteTask(task) {
  // Show confirmation dialog
  const confirmed = confirm(`「${task.title}」を削除しますか？`)
  if (!confirmed) {
    return
  }

  try {
    // Remove task from array (deep copy to avoid mutation)
    const tasks = JSON.parse(JSON.stringify(user.value.proactiveTasks || []))
    const updatedTasks = tasks.filter(t => t.id !== task.id)

    // Update user via API
    await usersStore.modifyUser(userId, {
      proactiveTasks: updatedTasks,
    })

    toastStore.showSuccess('タスクを削除しました')
  } catch (error) {
    console.error('Failed to delete task:', error)
    toastStore.showError('タスクの削除に失敗しました')
  }
}
</script>

<template>
  <div>
    <!-- Loading state -->
    <div v-if="loading">読み込み中...</div>

    <!-- User not found -->
    <div v-else-if="!user">
      <p>利用者が見つかりません</p>
      <button @click="goBack">戻る</button>
    </div>

    <!-- Task management view -->
    <div v-else>
      <!-- Header -->
      <div class="header">
        <div>
          <button @click="goBack" class="btn-back">← 戻る</button>
          <h2>{{ user.name }}さんのタスク管理</h2>
        </div>
        <button @click="addTask" class="btn-primary">新規タスク追加</button>
      </div>

      <!-- Task list -->
      <div class="tasks-container">
        <div v-if="!user.proactiveTasks || user.proactiveTasks.length === 0" class="empty-message">
          タスクが登録されていません
        </div>

        <div v-else>
          <div v-for="task in user.proactiveTasks" :key="task.id" class="task-card">
            <div class="task-info">
              <h3>{{ task.title }}</h3>
              <p class="task-time">{{ task.time }}</p>
              <p
                class="task-status"
                :class="{ 'status-enabled': task.enabled, 'status-disabled': !task.enabled }"
              >
                {{ task.enabled ? '有効' : '無効' }}
              </p>
            </div>
            <div class="task-actions">
              <button @click="editTask(task)" class="btn-edit">編集</button>
              <button @click="deleteTask(task)" class="btn-delete">削除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Task Add/Edit Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingTask ? 'タスク編集' : '新規タスク追加' }}</h3>
          <button @click="closeModal" class="close-button">&times;</button>
        </div>
        <TaskForm :task="editingTask" @submit="handleTaskSubmit" @cancel="closeModal" />
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

.btn-back {
  background: none;
  border: none;
  color: #3b82f6;
  font-size: 1rem;
  cursor: pointer;
  padding: 0.5rem;
  margin-bottom: 0.5rem;
}

.btn-back:hover {
  text-decoration: underline;
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

.tasks-container {
  margin-top: 20px;
}

.empty-message {
  padding: 20px;
  text-align: center;
  color: #999;
}

.task-card {
  border: 1px solid #ddd;
  padding: 15px;
  margin: 10px 0;
  border-radius: 5px;
  background: #f9f9f9;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.task-info {
  flex: 1;
}

.task-info h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.task-time {
  margin: 5px 0;
  color: #666;
  font-size: 1.1rem;
  font-weight: 500;
}

.task-status {
  margin: 5px 0;
  font-size: 0.875rem;
  font-weight: 500;
}

.status-enabled {
  color: #10b981;
}

.status-disabled {
  color: #6b7280;
}

.task-actions {
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
</style>
