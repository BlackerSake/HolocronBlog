<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <router-link to="/" class="logo" style="font-size:0.95rem;">
          <span class="logo-icon">◇</span>
          <span class="logo-text">管理后台</span>
        </router-link>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/backend/articles" class="sidebar-link" :class="{ active: $route.path === '/backend' || $route.path.startsWith('/backend/articles') }">
          <span class="sl-icon">⊞</span> 文章
        </router-link>
        <router-link v-if="auth.user?.value?.role === 'admin'" to="/backend/categories" class="sidebar-link" :class="{ active: $route.path === '/backend/categories' }">
          <span class="sl-icon">⊡</span> 分类
        </router-link>
        <router-link v-if="auth.user?.value?.role === 'admin'" to="/backend/tags" class="sidebar-link" :class="{ active: $route.path === '/backend/tags' }">
          <span class="sl-icon">#</span> 标签
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <div class="user-info">
          <span class="user-name">{{ auth.user?.value?.username }}</span>
          <span class="user-role">{{ auth.user?.value?.role }}</span>
        </div>
        <button class="nav-link logout-btn" @click="handleLogout">退出管理</button>
      </div>
    </aside>
    <div class="admin-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth.js'

const router = useRouter()
const auth = useAuth()

function handleLogout() {
  auth.logout()
  router.push('/')
}
</script>
