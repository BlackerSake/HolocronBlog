<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <div>
        <h2 class="page-title" style="font-size:1.8rem;">标签管理</h2>
        <p class="page-subtitle" style="margin-bottom:0;">为文章添加标签以便检索</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="showForm = true; editing = null; form = { name: '' }">新建</button>
    </div>

    <div class="card" style="margin-bottom:1.5rem;" v-if="showForm">
      <div class="card-title">{{ editing ? '编辑' : '新建' }}标签</div>
      <form @submit.prevent="handleSave" style="display:flex;gap:0.75rem;align-items:end;flex-wrap:wrap;">
        <div class="form-group" style="flex:1;min-width:200px;margin:0;">
          <label>名称</label>
          <input v-model="form.name" class="input" required />
        </div>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? '...' : '保存' }}</button>
        <button type="button" class="btn btn-sm" @click="showForm = false">取消</button>
      </form>
      <p v-if="formError" style="color:var(--danger);font-size:0.82rem;margin-top:0.5rem;">{{ formError }}</p>
    </div>

    <table class="admin-table">
      <thead>
        <tr><th>名称</th><th>创建时间</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="t in tags" :key="t.id">
          <td style="color:var(--text-primary);">#{{ t.name }}</td>
          <td>{{ formatDate(t.created_at) }}</td>
          <td class="actions">
            <button class="btn btn-sm" @click="startEdit(t)">编辑</button>
            <button class="btn btn-sm btn-danger" @click="handleDelete(t.id)">删除</button>
          </td>
        </tr>
        <tr v-if="!tags.length">
          <td colspan="3" style="text-align:center;color:var(--text-muted);padding:2rem;">暂无标签。</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { tagsAPI } from '../../api/index.js'

const tags = ref([])
const showForm = ref(false)
const editing = ref(null)
const form = ref({ name: '' })
const saving = ref(false)
const formError = ref('')

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function startEdit(tag) {
  editing.value = tag.id
  form.value = { name: tag.name }
  showForm.value = true
  formError.value = ''
}

async function handleSave() {
  formError.value = ''
  saving.value = true
  try {
    if (editing.value) {
      await tagsAPI.update(editing.value, form.value)
    } else {
      await tagsAPI.create(form.value)
    }
    showForm.value = false
    tags.value = await tagsAPI.list()
  } catch (e) {
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  if (!confirm('确定删除此标签？')) return
  try {
    await tagsAPI.delete(id)
    tags.value = tags.value.filter(t => t.id !== id)
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  tags.value = await tagsAPI.list().catch(() => [])
})
</script>
