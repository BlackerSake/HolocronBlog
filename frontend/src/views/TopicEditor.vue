<template>
  <div class="topic-editor-page">
    <header class="forum-head compact">
      <div>
        <h1>发布主题</h1>
        <p class="forum-subtitle">写清问题、背景和已经尝试过的方案。</p>
      </div>
    </header>

    <form class="forum-panel topic-editor" @submit.prevent="submitTopic">
      <div class="form-group">
        <label>标题</label>
        <input v-model="form.title" class="input" required maxlength="120" placeholder="一句话说明主题" />
      </div>

      <div class="editor-meta-grid">
        <div class="form-group">
          <label>板块</label>
          <select v-model="form.category_id" class="select">
            <option :value="null">不选择板块</option>
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
        </div>
        <div class="form-group">
          <label>标签</label>
          <select v-model="form.tags_id" class="select" multiple>
            <option v-for="tag in tags" :key="tag.id" :value="tag.id">{{ tag.name }}</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>正文</label>
        <textarea v-model="form.content" class="textarea topic-content" required maxlength="20000" placeholder="支持 Markdown"></textarea>
      </div>

      <p v-if="error" class="form-error">{{ error }}</p>

      <div class="editor-actions">
        <button type="submit" class="btn btn-primary" :disabled="saving || !canSubmit">
          {{ saving ? '发布中...' : '发布主题' }}
        </button>
        <router-link to="/" class="btn">取消</router-link>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { articlesAPI, categoriesAPI, tagsAPI } from '../api/index.js'

const router = useRouter()
const categories = ref([])
const tags = ref([])
const saving = ref(false)
const error = ref('')
const form = ref({
  title: '',
  content: '',
  category_id: null,
  tags_id: [],
})

const canSubmit = computed(() => form.value.title.trim() && form.value.content.trim())

function summaryOf(text) {
  return text.replace(/\s+/g, ' ').trim().slice(0, 160)
}

async function submitTopic() {
  if (!canSubmit.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const article = await articlesAPI.create({
      ...form.value,
      summary: summaryOf(form.value.content),
      cover_image: '',
      is_published: true,
    })
    router.push(`/articles/${article.slug}`)
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || '发布失败'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const [cats, tgs] = await Promise.all([
    categoriesAPI.list().catch(() => []),
    tagsAPI.list().catch(() => []),
  ])
  categories.value = cats
  tags.value = tgs
})
</script>
