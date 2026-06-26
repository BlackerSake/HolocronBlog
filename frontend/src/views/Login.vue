<template>
  <div class="login-page">
    <div class="login-card animate-in">
      <div class="login-header">
        <span class="logo-icon" style="font-size:1.5rem;">◇</span>
        <h1 class="login-title">{{ isRegister ? '注册账号' : '登录账号' }}</h1>
        <p class="login-subtitle">{{ isRegister ? '创建账号以管理内容' : '验证身份以进入管理后台' }}</p>
      </div>

      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input v-model="username" class="input" placeholder="请输入用户名" required autocomplete="username" />
        </div>
        <div class="form-group" v-if="isRegister">
          <label>邮箱</label>
          <input v-model="email" type="email" class="input" placeholder="选填" />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input v-model="password" type="password" class="input" placeholder="请输入密码" required autocomplete="current-password" />
        </div>
        <p v-if="error" style="color:var(--danger);font-size:0.82rem;margin-bottom:1rem;">{{ error }}</p>
        <button type="submit" class="btn btn-primary" style="width:100%;" :disabled="loading">
          {{ loading ? '处理中...' : (isRegister ? '注册并进入' : '进入Holocron') }}
        </button>
      </form>

      <p style="text-align:center;margin-top:1.5rem;font-size:0.82rem;color:var(--text-muted);">
        <a href="#" @click.prevent="toggleMode" style="color:var(--teal);">
          {{ isRegister ? '已有账号？登录' : '没有账号？注册' }}
        </a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuth()

const username = ref('')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)

function toggleMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(username.value, email.value, password.value)
    }
    await auth.login(username.value, password.value)
    router.push(route.query.redirect || '/backend')
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || (isRegister.value ? '注册失败' : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 120px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1.5rem;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  padding: 2.5rem;
  box-shadow: var(--shadow-md);
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 600;
  margin-top: 0.5rem;
}

.login-subtitle {
  color: var(--text-muted);
  font-size: 0.8rem;
  font-family: var(--font-mono);
  margin-top: 0.3rem;
}
</style>
