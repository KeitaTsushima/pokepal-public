<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useUsersStore } from '../stores/users';
import UserForm from '../components/UserForm.vue';

const usersStore = useUsersStore();
const showModal = ref(false);

// Load users on mount
onMounted(() => {
  usersStore.loadUsers();
});

// Cleanup SignalR on unmount
onUnmounted(() => {
  usersStore.cleanup();
});

// Open create modal
function openCreateModal() {
  showModal.value = true;
}

// Close modal
function closeModal() {
  showModal.value = false;
}

// Handle user creation
async function handleUserSubmit(userData) {
  try {
    // Generate user ID (timestamp-based)
    const userId = `user_${Date.now()}`;
    const newUser = { id: userId, ...userData };

    await usersStore.addUser(newUser);
    closeModal();
  } catch (error) {
    console.error('Failed to create user:', error);
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
          <h3>{{ user.name }}</h3>
          <p>呼び方: {{ user.nickname }}</p>
          <p v-if="user.roomNumber">部屋番号: {{ user.roomNumber }}</p>
          <p>デバイスID: {{ user.deviceId }}</p>
          <p v-if="user.notes" class="notes">{{ user.notes }}</p>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>新規利用者登録</h3>
          <button @click="closeModal" class="close-button">&times;</button>
        </div>
        <UserForm @submit="handleUserSubmit" @cancel="closeModal" />
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
}

.user-card h3 {
  margin: 0 0 10px 0;
  color: #333;
}

.user-card p {
  margin: 5px 0;
  color: #666;
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
</style>
