<template>
  <main class="login-view">
    <section class="auth-panel">
      <!-- 品牌头部区域 -->
      <div class="brand-header">
        <div class="logo-grid">
          <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
          <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
          <span class="logo-dot"></span><span class="logo-dot"></span><span class="logo-dot"></span>
        </div>
        <h1>Agentic RAG QA Studio</h1>
        <p>进入您的智能会话、记忆和知识库管理区</p>
      </div>

      <!-- 登录/注册胶囊滑块 Tab -->
      <div class="mode-switch" role="tablist" aria-label="auth mode">
        <button 
          :class="{ active: mode === 'login' }" 
          @click="mode = 'login'" 
          type="button"
        >
          登录
        </button>
        <button 
          :class="{ active: mode === 'register' }" 
          @click="mode = 'register'" 
          type="button"
        >
          注册
        </button>
      </div>

      <!-- 表单区域 -->
      <form class="auth-form" @submit.prevent="handleSubmit">
        <label>
          <span>用户名</span>
          <input 
            v-model.trim="username" 
            autocomplete="username" 
            minlength="3" 
            maxlength="64" 
            required 
            placeholder="请输入您的用户名"
          />
        </label>

        <label>
          <span>密码</span>
          <input
            v-model="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            type="password"
            minlength="8"
            maxlength="128"
            required
            placeholder="请输入您的密码"
          />
        </label>

        <p v-if="authStore.error" class="error-text">{{ authStore.error }}</p>

        <button class="submit-btn" type="submit" :disabled="authStore.loading">
          {{ authStore.loading ? '处理中...' : mode === 'login' ? '登 录' : '创建账号' }}
        </button>
      </form>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const mode = ref('login')
const username = ref('')
const password = ref('')

const handleSubmit = async () => {
  const action = mode.value === 'login' ? authStore.login : authStore.register
  await action(username.value, password.value)
  ElMessage.success(mode.value === 'login' ? '登录成功' : '注册成功')
  await router.replace(route.query.redirect || '/chat')
}
</script>

<style scoped>
.login-view {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background-color: #f8fafc;
  /* 科技感淡曜径向微光晕 background */
  background-image: 
    radial-gradient(at 0% 0%, rgba(224, 242, 254, 0.45) 0, transparent 50%), 
    radial-gradient(at 50% 0%, rgba(224, 231, 255, 0.45) 0, transparent 50%), 
    radial-gradient(at 100% 0%, rgba(253, 224, 71, 0.1) 0, transparent 40%);
}

.auth-panel {
  width: min(420px, 100%);
  padding: 40px 32px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(9, 11, 30, 0.05);
  box-shadow: 0 24px 64px -16px rgba(9, 11, 30, 0.05);
}

.brand-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: 32px;
}

.logo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  width: 20px;
  height: 20px;
  margin-bottom: 16px;
}

.logo-dot {
  width: 4px;
  height: 4px;
  background-color: #090B1E;
  border-radius: 50%;
}

.brand-header h1 {
  font-size: 19px;
  font-weight: 850;
  color: #090B1E;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.brand-header p {
  font-size: 12.5px;
  color: #5e6278;
  line-height: 1.5;
  margin: 0;
}

/* iOS 胶囊分段 Tab */
.mode-switch {
  display: flex;
  background-color: #f1f2f5;
  border-radius: 12px;
  padding: 3px;
  margin-bottom: 26px;
  border: 1px solid rgba(9, 11, 30, 0.02);
}

.mode-switch button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px 0;
  font-size: 13px;
  font-weight: 700;
  color: #5e6278;
  border-radius: 9px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.mode-switch button.active {
  background-color: #ffffff;
  color: #0085FF;
  box-shadow: 0 2px 8px rgba(9, 11, 30, 0.04);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #3f4254;
  font-size: 12px;
  font-weight: 700;
}

input {
  height: 44px;
  border-radius: 10px;
  border: 1px solid #e4e6ef;
  background-color: #ffffff;
  color: #181c32;
  padding: 0 16px;
  font-size: 13.5px;
  outline: none;
  transition: all 0.2s ease;
}

input::placeholder {
  color: #a1a5b7;
  font-size: 13px;
}

input:focus {
  border-color: #0085FF;
  box-shadow: 0 0 0 3px rgba(0, 133, 255, 0.1);
}

.error-text {
  color: #ef4444;
  font-size: 12.5px;
  margin: 0;
  line-height: 1.4;
}

.submit-btn {
  height: 44px;
  border-radius: 10px;
  border: none;
  background: #0085FF;
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(0, 133, 255, 0.15);
  margin-top: 6px;
}

.submit-btn:hover:not(:disabled) {
  background: #0076e5;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(0, 133, 255, 0.2);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0.5px);
}

.submit-btn:disabled {
  background-color: #a1a5b7;
  cursor: not-allowed;
  box-shadow: none;
  opacity: 0.6;
}
</style>
