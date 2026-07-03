<template>
  <div class="admin-shell">
    <div class="admin-topbar">
      <div class="topbar-left">
        <router-link to="/" class="topbar-logo">
          <span class="logo-icon">H</span>
          <span class="logo-text">管理后台</span>
        </router-link>
        <nav class="topbar-nav">
          <router-link to="/backend/articles" class="topbar-link" :class="{ active: $route.path === '/backend' || $route.path.startsWith('/backend/articles') }">文章</router-link>
          <router-link to="/notifications" class="topbar-link notification-link">
            通知
            <span v-if="unreadCount" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </router-link>
          <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/categories" class="topbar-link" :class="{ active: $route.path === '/backend/categories' }">分类</router-link>
          <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/tags" class="topbar-link" :class="{ active: $route.path === '/backend/tags' }">标签</router-link>
          <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/admin" class="topbar-link" :class="{ active: $route.path === '/backend/admin' }">用户</router-link>
        </nav>
      </div>
      <div class="topbar-right">
        <div class="topbar-user-wrap">
          <div class="topbar-avatar">{{ auth.user?.value?.username?.[0]?.toUpperCase() || '?' }}</div>
          <div class="topbar-user">
            <span class="un">{{ auth.user?.value?.username }}</span>
            <span class="rl">{{ auth.user?.value?.role_name === 'admin' ? 'admin' : 'user' }}</span>
          </div>
        </div>
        <button class="topbar-btn" @click="handleLogout">退出</button>
      </div>
    </div>
    <div class="admin-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'
import { useNotifications } from '../../composables/useNotifications.js'

const router = useRouter()
const auth = useAuth()
const notifications = useNotifications()
const unreadCount = notifications.unreadCount

function handleLogout() {
  auth.logout()
  notifications.reset()
  router.push('/')
}
</script>
