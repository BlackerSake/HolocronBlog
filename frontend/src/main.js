import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { routes, beforeEach } from './router/index.js'
import './assets/main.css'

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(beforeEach)

createApp(App).use(router).mount('#app')
