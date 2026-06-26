<template>
  <div class="app-shell">
    <header class="archive-header" v-if="!isAdminRoute">
      <div class="header-inner">
        <router-link to="/" class="logo">
          <span class="logo-icon">◇</span>
          <span class="logo-text">Holocron Blog</span>
        </router-link>
        <nav class="header-nav">
          <router-link to="/" class="nav-link">文章</router-link>
          <router-link v-if="auth.token.value" to="/backend" class="nav-link">管理</router-link>
          <router-link v-if="!auth.token.value" to="/login" class="nav-link login-btn">进入</router-link>
          <button v-else class="nav-link logout-btn" @click="handleLogout">退出</button>
        </nav>
      </div>
    </header>

    <main class="main-content">
      <router-view />
    </main>

    <footer class="archive-footer" v-if="!isAdminRoute">
      <p>Holocron 档案馆 &mdash; 知识在此长存</p>
    </footer>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from './composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

const isAdminRoute = computed(() => route.path.startsWith('/backend'))

function handleLogout() {
  auth.logout()
  router.push('/')
}
</script>
