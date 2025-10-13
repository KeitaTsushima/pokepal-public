<script setup>
import { onMounted } from 'vue';
import { useUsersStore } from '../stores/users';

const usersStore = useUsersStore();

// Load users on mount
onMounted(() => {
  usersStore.loadUsers();
});
</script>

<template>
  <div>
    <h2>利用者管理</h2>

    <!-- ローディング表示 -->
    <div v-if="usersStore.loading">読み込み中...</div>

    <!-- エラー表示 + 再試行ボタン -->
    <div v-else-if="usersStore.error" class="error-card">
      <p>{{ usersStore.error }}</p>
      <button @click="usersStore.loadUsers()">再試行</button>
    </div>

    <!-- 利用者一覧 -->
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
  </div>
</template>

<style scoped>
h2 {
  margin-bottom: 20px;
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
</style>
