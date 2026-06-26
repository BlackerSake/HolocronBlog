<template>
  <div>
    <h2 class="page-title" style="font-size:1.8rem;">管理概览</h2>
    <p class="page-subtitle">档案馆运行状况一览</p>

    <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
    <div v-else style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;">
      <div class="card">
        <div class="card-title">文章</div>
        <p style="font-size:2.5rem;font-family:var(--font-display);color:var(--teal);">{{ stats.articles }}</p>
      </div>
      <div class="card">
        <div class="card-title">分类</div>
        <p style="font-size:2.5rem;font-family:var(--font-display);color:var(--teal);">{{ stats.categories }}</p>
      </div>
      <div class="card">
        <div class="card-title">标签</div>
        <p style="font-size:2.5rem;font-family:var(--font-display);color:var(--teal);">{{ stats.tags }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { articlesAPI, categoriesAPI, tagsAPI } from '../../api/index.js'

const loading = ref(true)
const stats = ref({ articles: 0, categories: 0, tags: 0 })

onMounted(async () => {
  const [articles, categories, tags] = await Promise.all([
    articlesAPI.list({ per_page: 1 }).catch(() => ({ total: 0 })),
    categoriesAPI.list().catch(() => []),
    tagsAPI.list().catch(() => []),
  ])
  stats.value = {
    articles: articles.total || 0,
    categories: categories.length || 0,
    tags: tags.length || 0,
  }
  loading.value = false
})
</script>
