<template>
  <div class="home-page container">
    <header class="page-header animate-in">
      <h1 class="page-title">Holocron Blog</h1>
    </header>

    <div class="epigraph animate-in animate-in-d1">
      <p>凡修习者，必有所录。</p>
      <p>学而时习，恐其有忘；思而日省，恐其有失。</p>
      <p>故录之于此。</p>
      <p>后之览者，亦将有感于斯文。</p>
    </div>

    <div class="home-layout">
      <section class="home-main">
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

        <p class="page-subtitle">共 {{ total }} 条记录 &middot; 按时间排序</p>

        <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
        <div v-else-if="error" class="empty-state">{{ error }}</div>
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
      </section>

      <aside class="hot-panel animate-in animate-in-d2">
        <div class="hot-panel-head">
          <h2>热门</h2>
          <span>热度</span>
        </div>
        <div v-if="hotLoading" class="hot-empty">加载中</div>
        <div v-else-if="!hotArticles.length" class="hot-empty">暂无热榜</div>
        <router-link
          v-for="(article, i) in hotArticles"
          v-else
          :key="article.id"
          :to="`/articles/${article.slug}`"
          class="hot-item"
        >
          <span class="hot-rank">{{ i + 1 }}</span>
          <span class="hot-title">{{ article.title }}</span>
        </router-link>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { articlesAPI, categoriesAPI, tagsAPI } from '../api/index.js'
import { formatDate } from '../utils.js'

const route = useRoute()
const router = useRouter()
const articles = ref([])
const hotArticles = ref([])
const categories = ref([])
const tags = ref([])
const total = ref(0)
const page = ref(Math.max(1, Number(route.query.page || 1)))
const pages = ref(0)
const loading = ref(true)
const hotLoading = ref(true)
const error = ref('')
const search = ref(String(route.query.search || ''))
const selectedCategory = ref(route.query.category_id ? Number(route.query.category_id) : null)
const selectedTag = ref(route.query.tag_id ? Number(route.query.tag_id) : null)

let searchTimer = null

function syncQuery() {
  router.replace({
    query: {
      page: page.value > 1 ? page.value : undefined,
      search: search.value || undefined,
      category_id: selectedCategory.value || undefined,
      tag_id: selectedTag.value || undefined,
    },
  })
}

async function fetchArticles() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: page.value, per_page: 10 }
    if (selectedCategory.value) params.category_id = selectedCategory.value
    if (selectedTag.value) params.tag_id = selectedTag.value
    if (search.value) params.search = search.value

    syncQuery()
    const data = await articlesAPI.list(params)
    articles.value = data.items
    total.value = data.total
    page.value = data.page
    pages.value = data.pages
  } catch {
    articles.value = []
    total.value = 0
    pages.value = 0
    error.value = '文章加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

async function fetchHotArticles() {
  hotLoading.value = true
  try {
    hotArticles.value = await articlesAPI.hot()
  } catch {
    hotArticles.value = []
  } finally {
    hotLoading.value = false
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

onMounted(async () => {
  await Promise.all([
    fetchArticles(),
    fetchHotArticles(),
    categoriesAPI.list().then(d => categories.value = d),
    tagsAPI.list().then(d => tags.value = d),
  ])
})
</script>
