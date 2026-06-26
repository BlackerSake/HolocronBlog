<template>
  <div>
    <h2 class="page-title" style="font-size:1.8rem;">{{ isEdit ? '编辑' : '新建' }}文章</h2>
    <p class="page-subtitle" style="margin-bottom:0;">{{ isEdit ? '修改档案馆中的记录' : '向档案馆添加新记录' }}</p>

    <div class="card" style="margin-top:2rem;max-width:800px;">
      <form @submit.prevent="handleSave">
        <div class="form-group">
          <label>标题</label>
          <input v-model="form.title" class="input" required />
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
          <div class="form-group">
            <label>分类</label>
            <select v-model="form.category_id" class="select">
              <option :value="null">无</option>
              <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>标签</label>
            <select v-model="form.tags_id" class="select" multiple style="min-height:80px;">
              <option v-for="t in tags" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>摘要</label>
          <input v-model="form.summary" class="input" placeholder="简短描述..." />
        </div>

        <div class="form-group">
          <label>内容（Markdown）</label>
          <textarea v-model="form.content" class="textarea" style="min-height:350px;font-family:var(--font-mono);font-size:0.85rem;" required></textarea>
        </div>

        <div class="form-group">
          <label>封面图 URL</label>
          <input v-model="form.cover_image" class="input" placeholder="https://..." />
        </div>

        <div class="form-group" style="display:flex;align-items:center;gap:0.5rem;">
          <input type="checkbox" id="published" v-model="form.is_published" style="accent-color:var(--teal);" />
          <label for="published" style="margin:0;cursor:pointer;">立即发布</label>
        </div>

        <p v-if="error" style="color:var(--danger);font-size:0.82rem;margin-bottom:1rem;">{{ error }}</p>

        <div style="display:flex;gap:0.75rem;">
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? '保存中...' : (isEdit ? '更新' : '创建') }}
          </button>
          <router-link to="/admin/articles" class="btn">取消</router-link>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { articlesAPI, categoriesAPI, tagsAPI } from '../../api/index.js'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.slug)

const categories = ref([])
const tags = ref([])
const saving = ref(false)
const error = ref('')

const form = ref({
  title: '',
  content: '',
  summary: '',
  cover_image: '',
  category_id: null,
  tags_id: [],
  is_published: false,
})

async function handleSave() {
  error.value = ''
  saving.value = true
  try {
    const payload = { ...form.value }
    if (isEdit.value) {
      await articlesAPI.update(route.params.slug, payload)
    } else {
      await articlesAPI.create(payload)
    }
    router.push('/admin/articles')
  } catch (e) {
    error.value = e.response?.data?.detail || '保存失败'
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

  if (isEdit.value) {
    try {
      const article = await articlesAPI.get(route.params.slug)
      form.value = {
        title: article.title,
        content: article.content,
        summary: article.summary || '',
        cover_image: article.cover_image || '',
        category_id: article.category?.id || null,
        tags_id: article.tags?.map(t => t.id) || [],
        is_published: article.is_published,
      }
    } catch {
      error.value = '未找到该文章'
    }
  }
})
</script>
