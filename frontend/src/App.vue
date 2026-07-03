<template>
  <div class="app-shell">
    <header class="archive-header" v-if="!isAdminRoute">
      <div class="header-inner">
        <router-link to="/" class="logo">
          <span class="logo-icon">H</span>
          <span class="logo-text">Holocron Blog</span>
        </router-link>
        <nav class="header-nav">
          <router-link to="/" class="nav-link">文章</router-link>
          <router-link v-if="auth.token.value" to="/notifications" class="nav-link notification-link">
            通知
            <span v-if="unreadCount" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </router-link>
          <router-link v-if="auth.token.value" to="/backend" class="nav-link">管理</router-link>
          <template v-if="auth.token.value">
            <div class="header-user-wrap">
              <div class="header-avatar">{{ auth.user.value?.username?.[0]?.toUpperCase() || '?' }}</div>
              <span class="header-username">{{ auth.user.value?.username }}</span>
            </div>
            <button class="nav-link" @click="handleLogout">退出</button>
          </template>
          <router-link v-else to="/login" class="nav-link login-btn">进入</router-link>
        </nav>
      </div>
    </header>

    <main class="main-content">
      <router-view />
    </main>

    <footer class="archive-footer" v-if="!isAdminRoute">
      <p>Holocron 档案馆 &mdash; 知识在此长存</p>
    </footer>

    <div v-if="toast.state.visible" class="toast" :class="toast.state.type" @click="toast.hide()">
      {{ toast.state.message }}
    </div>

    <div v-if="dialog.state.visible" class="confirm-overlay" @click="dialog.cancel()">
      <div class="confirm-dialog" @click.stop>
        <p class="confirm-msg">{{ dialog.state.message }}</p>
        <div class="confirm-actions">
          <button class="btn btn-sm" @click="dialog.cancel()">取消</button>
          <button class="btn btn-sm btn-danger" @click="dialog.ok()">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'
import { useToast } from './composables/useToast.js'
import { useConfirm } from './composables/useConfirm.js'
import { useNotifications } from './composables/useNotifications.js'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const toast = useToast()
const dialog = useConfirm()
const notifications = useNotifications()
const unreadCount = notifications.unreadCount
let notificationTimer = null

const isAdminRoute = computed(() => route.path.startsWith('/backend'))

function refreshUnreadCount() {
  if (!auth.token.value) {
    notifications.reset()
    return
  }
  notifications.fetchUnreadCount().catch(() => {})
}

function stopNotificationPolling() {
  if (notificationTimer) clearInterval(notificationTimer)
  notificationTimer = null
}

function startNotificationPolling() {
  stopNotificationPolling()
  refreshUnreadCount()
  if (auth.token.value) notificationTimer = setInterval(refreshUnreadCount, 30000)
}

onMounted(startNotificationPolling)
watch(auth.token, startNotificationPolling)
onBeforeUnmount(stopNotificationPolling)

function handleLogout() {
  auth.logout()
  notifications.reset()
  router.push('/')
}
</script>
