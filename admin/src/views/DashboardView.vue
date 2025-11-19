<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useDevicesStore } from '../stores/devices'
import { formatDeviceName, formatStatus, formatRelativeTime } from '../utils/formatters'

const devicesStore = useDevicesStore()

// Current time updated every minute for relative time display
const currentTime = ref(Date.now())
let timeUpdateInterval = null

// Load device data on mount
onMounted(() => {
  devicesStore.loadDevices()

  // Update current time every minute to refresh relative time display
  timeUpdateInterval = setInterval(() => {
    currentTime.value = Date.now()
  }, 60000) // 60 seconds
})

// Clean up timer on unmount
onUnmounted(() => {
  if (timeUpdateInterval) {
    clearInterval(timeUpdateInterval)
  }
  devicesStore.cleanup()
})
</script>

<template>
  <h2>デバイス一覧</h2>

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
      <p>最終更新: {{ formatRelativeTime(device.lastSeen, currentTime) }}</p>
      <p v-if="device.lastConversation">最後の会話: 「{{ device.lastConversation.text }}」</p>
    </div>
  </div>
</template>

<style scoped>
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
