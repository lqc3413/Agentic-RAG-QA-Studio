<template>
  <header class="app-header">
    <div class="logo-area">
      <div class="glow-dot"></div>
      <span class="studio-title">Agentic RAG QA Studio</span>
      <span class="badge">v1.0.0</span>
    </div>
    <div class="status-area">
      <span class="status-indicator" :class="{ connected: isConnected }">
        <span class="pulse-ring"></span>
        服务状态: {{ isConnected ? '已连接' : '离线' }}
      </span>
      <span v-if="authStore.user" class="user-chip">{{ authStore.user.username }}</span>
      <button class="logout-btn" type="button" @click="handleLogout">退出</button>
    </div>
  </header>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const isConnected = ref(false)
let interval = null
const authStore = useAuthStore()
const router = useRouter()

const checkHealth = async () => {
  try {
    let baseURL = import.meta.env.VITE_API_BASE_URL
    if (baseURL === undefined || baseURL === '') {
      baseURL = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''
    }
    await axios.get(`${baseURL}/api/health`)
    isConnected.value = true
  } catch (err) {
    isConnected.value = false
  }
}

onMounted(() => {
  checkHealth()
  interval = setInterval(checkHealth, 10000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})

const handleLogout = async () => {
  await authStore.logout()
  await router.replace('/login')
}
</script>

<style scoped>
.app-header {
  height: 64px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: relative;
  z-index: 10;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.glow-dot {
  width: 10px;
  height: 10px;
  background-color: var(--color-primary);
  border-radius: 50%;
  box-shadow: 0 0 10px var(--color-primary);
}

.studio-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.5px;
  font-family: var(--font-family);
  background: linear-gradient(135deg, var(--text-primary) 30%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.badge {
  font-size: 11px;
  font-family: var(--font-family);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  padding: 2px 6px;
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-color);
}

.status-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-danger);
  font-weight: 500;
}

.status-indicator.connected {
  color: var(--color-success);
}

.pulse-ring {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--color-danger);
  position: relative;
}

.status-indicator.connected .pulse-ring {
  background-color: var(--color-success);
}

.user-chip {
  color: var(--text-secondary);
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: rgba(9, 13, 22, 0.5);
}

.logout-btn {
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 6px;
  height: 30px;
  padding: 0 10px;
  cursor: pointer;
}

.logout-btn:hover {
  border-color: var(--border-color-hover);
  color: var(--text-primary);
}

.status-indicator.connected .pulse-ring::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background-color: var(--color-success);
  animation: ring-pulse 1.8s infinite ease-out;
}

@keyframes ring-pulse {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(2.8); opacity: 0; }
}
</style>
