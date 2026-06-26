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
        <router-link to="/admin" class="sidebar-link" :class="{ active: $route.path === '/admin' }">
          <span class="sl-icon">◇</span> 概览
        </router-link>
        <router-link to="/admin/articles" class="sidebar-link" :class="{ active: $route.path.startsWith('/admin/articles') }">
          <span class="sl-icon">⊞</span> 文章
        </router-link>
        <router-link to="/admin/categories" class="sidebar-link" :class="{ active: $route.path === '/admin/categories' }">
          <span class="sl-icon">⊡</span> 分类
        </router-link>
        <router-link to="/admin/tags" class="sidebar-link" :class="{ active: $route.path === '/admin/tags' }">
          <span class="sl-icon">#</span> 标签
        </router-link>
      </nav>
      <div class="sidebar-footer">
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
