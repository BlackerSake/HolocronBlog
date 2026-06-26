<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <div>
        <h2 class="page-title" style="font-size:1.8rem;">文章管理</h2>
        <p class="page-subtitle" style="margin-bottom:0;">管理档案馆中的所有文章</p>
      </div>
      <router-link to="/admin/articles/new" class="btn btn-primary btn-sm">写文章</router-link>
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
            <th>状态</th>
            <th>分类</th>
            <th>日期</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in filtered" :key="a.id">
            <td style="color:var(--text-primary);font-weight:500;">{{ a.title }}</td>
            <td>
              <span class="status-badge" :class="a.is_published ? 'status-published' : 'status-draft'">
                {{ a.is_published ? '已发布' : '草稿' }}
              </span>
            </td>
            <td>{{ a.category?.name || '—' }}</td>
            <td>{{ formatDate(a.created_at) }}</td>
            <td class="actions">
              <router-link :to="`/admin/articles/${a.slug}/edit`" class="btn btn-sm">编辑</router-link>
              <button class="btn btn-sm btn-danger" @click="handleDelete(a)">删除</button>
            </td>
          </tr>
          <tr v-if="!filtered.length">
            <td colspan="5" style="text-align:center;color:var(--text-muted);padding:2rem;">{{ filter === 'draft' ? '暂无草稿。' : '暂无文章。' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { articlesAPI } from '../../api/index.js'

const articles = ref([])
const loading = ref(true)
const filter = ref('all')

const filtered = computed(() => {
  if (filter.value === 'published') return articles.value.filter(a => a.is_published)
  if (filter.value === 'draft') return articles.value.filter(a => !a.is_published)
  return articles.value
})

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', {
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

onMounted(async () => {
  try {
    const data = await articlesAPI.adminList({ per_page: 100 })
    articles.value = data.items
  } finally {
    loading.value = false
  }
})
</script>
