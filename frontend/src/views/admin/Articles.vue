<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <div>
        <h2 class="page-title" style="font-size:1.8rem;">文章管理</h2>
        <p class="page-subtitle" style="margin-bottom:0;">管理档案馆中的所有文章</p>
      </div>
      <router-link to="/backend/articles/new" class="btn btn-primary btn-sm">写文章</router-link>
    </div>

    <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
    <template v-else>
      <div style="display:flex;gap:0.5rem;margin-bottom:1.5rem;">
        <button class="filter-chip" :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</button>
        <button class="filter-chip" :class="{ active: filter === 'published' }" @click="filter = 'published'">已发布</button>
        <button class="filter-chip" :class="{ active: filter === 'draft' }" @click="filter = 'draft'">草稿</button>
      </div>
      <table class="admin-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>作者</th>
            <th>状态</th>
            <th>分类</th>
            <th>日期</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in filtered" :key="a.id">
            <td style="color:var(--text-primary);font-weight:500;">{{ a.title }}</td>
            <td style="font-size:0.82rem;color:var(--text-muted);">#{{ a.author?.id }} {{ a.author?.username }}</td>
            <td>
              <span class="status-badge" :class="a.is_published ? 'status-published' : 'status-draft'">
                {{ a.is_published ? '已发布' : '草稿' }}
              </span>
            </td>
            <td>{{ a.category?.name || '—' }}</td>
            <td>{{ formatDate(a.created_at) }}</td>
            <td class="actions">
              <router-link v-if="a.author?.id === user?.id" :to="`/backend/articles/${a.slug}/edit`" class="btn btn-sm">编辑</router-link>
              <button v-if="a.author?.id === user?.id" class="btn btn-sm btn-danger" @click="handleDelete(a)">删除</button>
              <button v-if="a.author?.id !== user?.id && user?.role === 'admin' && a.is_published" class="btn btn-sm" @click="handleUnpublish(a)">取消发布</button>
            </td>
          </tr>
          <tr v-if="!filtered.length">
            <td colspan="6" style="text-align:center;color:var(--text-muted);padding:2rem;">{{ filter === 'draft' ? '暂无草稿。' : '暂无文章。' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { articlesAPI } from '../../api/index.js'
import { useAuth } from '../../composables/useAuth.js'

const { user } = useAuth()
const articles = ref([])
const loading = ref(true)
const filter = ref('all')

const filtered = computed(() => {
  if (filter.value === 'published') return articles.value.filter(a => a.is_published)
  if (filter.value === 'draft') return articles.value.filter(a => !a.is_published)
  return articles.value
})

function formatDate(d) {
  if (!d.endsWith("Z") && !d.includes("+")) d += "Z"
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai',
    year: 'numeric', month: 'short', day: 'numeric'
  })
}

async function handleDelete(article) {
  if (!confirm(`确定删除「${article.title}」？`)) return
  try {
    await articlesAPI.delete(article.slug)
    articles.value = articles.value.filter(a => a.id !== article.id)
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

async function handleUnpublish(article) {
  if (!confirm(`确定取消发布「${article.title}」？`)) return
  try {
    await articlesAPI.unpublish(article.slug)
    article.is_published = false
  } catch (e) {
    alert(e.response?.data?.detail || '操作失败')
  }
}

onMounted(async () => {
  try {
    const data = await articlesAPI.backendList({ per_page: 100 })
    articles.value = data.items
  } finally {
    loading.value = false
  }
})
</script>
