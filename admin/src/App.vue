<script setup>
import { onMounted, onErrorCaptured } from 'vue';
import { useDevicesStore } from './stores/devices';
import { formatDeviceName, formatStatus, formatRelativeTime } from './utils/formatters';

const devicesStore = useDevicesStore();

// Error Boundary - 予期しないエラーをキャッチ
onErrorCaptured((err) => {
  console.error('[Error Boundary]', err);
  devicesStore.error = '予期しないエラーが発生しました。';
  return false; // エラー伝播を停止
});

// 画面表示時にデバイス情報を取得
onMounted(() => {
  devicesStore.loadDevices();
});
</script>

<template>
  <h1>PokePal 管理画面</h1>

  <!-- ローディング表示 -->
  <div v-if="devicesStore.loading">読み込み中...</div>

  <!-- エラー表示 + 再試行ボタン -->
  <div v-else-if="devicesStore.error" class="error-card">
    <p>{{ devicesStore.error }}</p>
    <button @click="devicesStore.loadDevices()">再試行</button>
  </div>

  <!-- デバイス一覧 -->
  <div v-else>
    <div v-for="device in devicesStore.devices" :key="device.deviceId" class="device-card">
      <p>{{ formatDeviceName(device.deviceId) }} - {{ formatStatus(device.status) }}</p>
      <p>最終更新: {{ formatRelativeTime(device.lastSeen) }}</p>
      <p v-if="device.lastConversation">
        最後の会話: 「{{ device.lastConversation.text }}」
      </p>
    </div>
  </div>
</template>

<style>
.device-card {
  border: 1px solid #ddd;
  padding: 15px;
  margin: 10px 0;
  border-radius: 5px;
  background: #f9f9f9;
}

.error-card {
  border: 1px solid #f44;
  padding: 15px;
  margin: 10px 0;
  border-radius: 5px;
  background: #fee;
}
</style>