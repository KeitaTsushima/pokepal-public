<script setup>
import { onErrorCaptured } from 'vue'
import Toast from './components/Toast.vue'

// Error Boundary - catch unexpected errors
onErrorCaptured(err => {
  console.error('[Error Boundary]', err)
  return false // Stop error propagation
})
</script>

<template>
  <div id="app">
    <Toast />

    <header>
      <h1>PokePal 管理画面</h1>
      <nav>
        <router-link to="/">デバイス一覧</router-link>
        <router-link to="/users">利用者管理</router-link>
      </nav>
    </header>

    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
#app {
  font-family: Arial, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 30px;
}

h1 {
  margin-bottom: 20px;
}

nav {
  display: flex;
  gap: 20px;
  border-bottom: 2px solid #ddd;
  padding-bottom: 10px;
}

nav a {
  text-decoration: none;
  color: #333;
  padding: 5px 10px;
  border-radius: 3px;
}

nav a.router-link-active {
  background: #007bff;
  color: white;
}

nav a:hover {
  background: #0056b3;
  color: white;
}
</style>
