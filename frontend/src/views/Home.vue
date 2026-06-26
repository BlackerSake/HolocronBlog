<template>
  <div class="home-page container">
    <header class="page-header animate-in">
      <h1 class="page-title">档案馆</h1>
      <p class="page-subtitle">共 {{ total }} 条记录 &middot; 按时间排序</p>
    </header>

    <!-- 筛选栏 -->
    <div class="filter-bar animate-in animate-in-d1">
      <input v-model="search" class="input search-input" placeholder="搜索档案馆..." @input="onSearch" />
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="filter-chip"
        :class="{ active: selectedCategory === cat.id }"
        @click="toggleFilter('category', cat.id)"
      >{{ cat.name }}</button>
      <button
        v-if="selectedCategory || selectedTag || search"
        class="filter-chip"
        @click="clearFilters"
      >清除</button>
    </div>

    <!-- 标签 -->
    <div class="filter-bar animate-in animate-in-d2" v-if="tags.length">
      <span class="nav-link" style="font-size:0.65rem;opacity:0.6;">标签</span>
      <button
        v-for="tag in tags"
        :key="tag.id"
        class="filter-chip"
        :class="{ active: selectedTag === tag.id }"
        @click="toggleFilter('tag', tag.id)"
      >#{{ tag.name }}</button>
    </div>

    <!-- 文章列表 -->
    <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
    <div v-else-if="!articles.length" class="empty-state">
      档案馆中暂无记录。
    </div>
    <div v-else class="article-list">
      <router-link
        v-for="(article, i) in articles"
        :key="article.id"
        :to="`/articles/${article.slug}`"
        class="article-list-item animate-in"
        :class="`animate-in-d${Math.min(i + 1, 4)}`"
      >
        <div class="item-title">{{ article.title }}</div>
        <div class="item-meta">
          <span>{{ article.author?.username }}</span>
          <span>{{ formatDate(article.created_at) }}</span>
          <span v-if="article.category">{{ article.category.name }}</span>
        </div>
        <div class="item-summary" v-if="article.summary">{{ article.summary }}</div>
        <div style="margin-top:0.5rem;display:flex;gap:0.4rem;flex-wrap:wrap;" v-if="article.tags?.length">
          <span class="tag-pill" v-for="t in article.tags" :key="t.id">#{{ t.name }}</span>
        </div>
      </router-link>
    </div>

    <!-- 分页 -->
    <div class="pagination" v-if="pages > 1">
      <button class="page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <button
        v-for="p in pages"
        :key="p"
        class="page-btn"
        :class="{ active: p === page }"
        @click="goPage(p)"
      >{{ p }}</button>
      <button class="page-btn" :disabled="page >= pages" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { articlesAPI, categoriesAPI, tagsAPI } from '../api/index.js'

const articles = ref([])
const categories = ref([])
const tags = ref([])
const total = ref(0)
const page = ref(1)
const pages = ref(0)
const loading = ref(true)
const search = ref('')
const selectedCategory = ref(null)
const selectedTag = ref(null)

let searchTimer = null

async function fetchArticles() {
  loading.value = true
  try {
    const params = { page: page.value, per_page: 10 }
    if (selectedCategory.value) params.category_id = selectedCategory.value
    if (selectedTag.value) params.tag_id = selectedTag.value
    if (search.value) params.search = search.value

    const data = await articlesAPI.list(params)
    articles.value = data.items
    total.value = data.total
    page.value = data.page
    pages.value = data.pages
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchArticles()
  }, 350)
}

function toggleFilter(type, id) {
  if (type === 'category') {
    selectedCategory.value = selectedCategory.value === id ? null : id
    selectedTag.value = null
  } else {
    selectedTag.value = selectedTag.value === id ? null : id
    selectedCategory.value = null
  }
  page.value = 1
  fetchArticles()
}

function clearFilters() {
  selectedCategory.value = null
  selectedTag.value = null
  search.value = ''
  page.value = 1
  fetchArticles()
}

function goPage(p) {
  if (p < 1 || p > pages.value) return
  page.value = p
  fetchArticles()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', {
    year: 'numeric', month: 'short', day: 'numeric'
  })
}

onMounted(async () => {
  await Promise.all([
    fetchArticles(),
    categoriesAPI.list().then(d => categories.value = d),
    tagsAPI.list().then(d => tags.value = d),
  ])
})
</script>
