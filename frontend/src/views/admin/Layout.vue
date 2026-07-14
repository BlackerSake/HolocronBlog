<template>
  <div class="admin-shell">
    <nav class="admin-subnav">
      <router-link to="/backend/articles" class="filter-chip" :class="{ active: $route.path === '/backend' || $route.path.startsWith('/backend/articles') }">文章</router-link>
      <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/categories" class="filter-chip" :class="{ active: $route.path === '/backend/categories' }">分类</router-link>
      <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/tags" class="filter-chip" :class="{ active: $route.path === '/backend/tags' }">标签</router-link>
      <router-link v-if="auth.user?.value?.role_name === 'admin'" to="/backend/admin" class="filter-chip" :class="{ active: $route.path === '/backend/admin' }">用户</router-link>
    </nav>
    <div class="admin-content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useAuth } from '../../composables/useAuth.js'

const auth = useAuth()
</script>
