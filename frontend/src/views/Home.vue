<template>
  <div class="forum-page">
    <header class="forum-head">
      <div>
        <h1>Holocron 论坛</h1>
        <div class="forum-subtitle">
          <p>凡修习者，必有所录。学而时习，恐其有忘；思而日省，恐其有失。故录之于此。</p>
          <p> 后之览者，亦将有感于斯文。</p>
        </div>
      </div>
      <div class="forum-stats">
        <div><strong>{{ total }}</strong><span>主题</span></div>
        <div><strong>{{ categories.length }}</strong><span>板块</span></div>
        <div><strong>{{ tags.length }}</strong><span>标签</span></div>
      </div>
    </header>

    <div class="forum-layout">
      <aside class="forum-panel">
        <div class="panel-title">板块</div>
        <button
          class="board-link"
          :class="{ active: !selectedCategory && !selectedTag }"
          @click="clearFilters"
        >
          <span class="board-name">全部主题</span>
          <span class="board-desc">按最新发布排序</span>
        </button>
        <button
          v-for="cat in categories"
          :key="cat.id"
          class="board-link"
          :class="{ active: selectedCategory === cat.id }"
          @click="toggleFilter('category', cat.id)"
        >
          <span class="board-name">{{ cat.name }}</span>
          <span class="board-desc">{{ cat.description || '查看该板块主题' }}</span>
        </button>
      </aside>

      <section class="forum-panel topic-panel">
        <div class="topic-toolbar">
          <div class="topic-tabs">
            <button :class="{ active: !selectedTag }" @click="clearTag">最新</button>
            <button
              v-for="tag in tags.slice(0, 4)"
              :key="tag.id"
              :class="{ active: selectedTag === tag.id }"
              @click="toggleFilter('tag', tag.id)"
            >
              #{{ tag.name }}
            </button>
          </div>
          <input v-model="search" class="forum-search" type="search" placeholder="搜索主题" @input="onSearch" />
        </div>

        <div class="topic-row topic-header">
          <span>主题</span>
          <span>回复</span>
          <span>浏览</span>
          <span>活动</span>
        </div>

        <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
        <div v-else-if="error" class="empty-state">{{ error }}</div>
        <div v-else-if="!articles.length" class="empty-state">暂无主题。</div>
        <template v-else>
          <router-link
            v-for="article in articles"
            :key="article.id"
            :to="`/articles/${article.slug}`"
            class="topic-row topic-link"
          >
            <div class="topic-main">
              <span class="topic-avatar">{{ avatarText(article.author) }}</span>
              <div class="topic-copy">
                <strong>{{ article.title }}</strong>
                <span class="topic-meta">
                  {{ article.author?.nickname || article.author?.username || '匿名' }}
                  <template v-if="article.category"> · {{ article.category.name }}</template>
                  · {{ formatRelativeTime(article.created_at) }}
                </span>
                <span v-if="article.tags?.length" class="topic-tags">
                  <span v-for="tag in article.tags" :key="tag.id" class="tag-pill">#{{ tag.name }}</span>
                </span>
              </div>
            </div>
            <span class="topic-num"><strong>{{ article.reply_count || 0 }}</strong><small>回复</small></span>
            <span class="topic-num"><strong>{{ article.views || 0 }}</strong><small>浏览</small></span>
            <span class="topic-activity">{{ formatRelativeTime(article.updated_at || article.created_at) }}</span>
          </router-link>
        </template>

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

      <aside class="forum-panel">
        <div class="panel-title">社区动态</div>
        <div v-if="hotLoading" class="side-empty">加载中</div>
        <template v-else>
          <router-link
            v-for="(article, i) in hotArticles"
            :key="article.id"
            :to="`/articles/${article.slug}`"
            class="hot-link"
          >
            <span class="hot-rank">{{ i + 1 }}</span>
            <span>
              <strong>{{ article.title }}</strong>
              <small>{{ article.views || 0 }} 浏览 · {{ article.like_count || 0 }} 赞</small>
            </span>
          </router-link>
        </template>
        <router-link class="new-topic-card" to="/topics/new">
          <strong>发起新主题</strong>
          <span>分享问题、方案或改版建议</span>
        </router-link>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { articlesAPI, categoriesAPI, tagsAPI } from '../api/index.js'
import { formatRelativeTime } from '../utils.js'

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

function avatarText(user) {
  return (user?.nickname || user?.username || '?').slice(0, 1).toUpperCase()
}

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
    const params = { page: page.value, per_page: 15 }
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
    error.value = '主题加载失败，请稍后重试。'
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
  }, 300)
}

function toggleFilter(type, id) {
  if (type === 'category') {
    selectedCategory.value = selectedCategory.value === id ? null : id
    selectedTag.value = null
  } else {
    selectedTag.value = selectedTag.value === id ? null : id
  }
  page.value = 1
  fetchArticles()
}

function clearTag() {
  selectedTag.value = null
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
    categoriesAPI.list().then(data => categories.value = data).catch(() => {}),
    tagsAPI.list().then(data => tags.value = data).catch(() => {}),
  ])
})
</script>
