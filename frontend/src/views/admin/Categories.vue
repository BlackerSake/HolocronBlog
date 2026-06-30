<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <div>
        <h2 class="page-title" style="font-size:1.8rem;">分类管理</h2>
        <p class="page-subtitle" style="margin-bottom:0;">组织档案馆的分类结构</p>
      </div>
      <button class="btn btn-primary btn-sm" @click="showForm = true; editing = null; form = { name: '', description: '' }">新建</button>
    </div>

    <div class="card" style="margin-bottom:1.5rem;" v-if="showForm">
      <div class="card-title">{{ editing ? '编辑' : '新建' }}分类</div>
      <form @submit.prevent="handleSave" style="display:flex;gap:0.75rem;align-items:end;flex-wrap:wrap;">
        <div class="form-group" style="flex:1;min-width:200px;margin:0;">
          <label>名称</label>
          <input v-model="form.name" class="input" required />
        </div>
        <div class="form-group" style="flex:2;min-width:250px;margin:0;">
          <label>描述</label>
          <input v-model="form.description" class="input" />
        </div>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="saving">{{ saving ? '...' : '保存' }}</button>
        <button type="button" class="btn btn-sm" @click="showForm = false">取消</button>
      </form>
      <p v-if="formError" style="color:var(--danger);font-size:0.82rem;margin-top:0.5rem;">{{ formError }}</p>
    </div>

    <table class="admin-table">
      <thead>
        <tr><th>名称</th><th>描述</th><th>创建时间</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="c in categories" :key="c.id">
          <td style="color:var(--text-primary);">{{ c.name }}</td>
          <td>{{ c.description || '—' }}</td>
          <td>{{ formatDate(c.created_at) }}</td>
          <td class="actions">
            <button class="btn btn-sm" @click="startEdit(c)">编辑</button>
            <button class="btn btn-sm btn-danger" @click="handleDelete(c.id)">删除</button>
          </td>
        </tr>
        <tr v-if="!categories.length">
          <td colspan="4" style="text-align:center;color:var(--text-muted);padding:2rem;">暂无分类。</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { categoriesAPI } from '../../api/index.js'

const categories = ref([])
const showForm = ref(false)
const editing = ref(null)
const form = ref({ name: '', description: '' })
const saving = ref(false)
const formError = ref('')

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'short', day: 'numeric' })
}

function startEdit(cat) {
  editing.value = cat.id
  form.value = { name: cat.name, description: cat.description || '' }
  showForm.value = true
  formError.value = ''
}

async function handleSave() {
  formError.value = ''
  saving.value = true
  try {
    if (editing.value) {
      await categoriesAPI.update(editing.value, form.value)
    } else {
      await categoriesAPI.create(form.value)
    }
    showForm.value = false
    categories.value = await categoriesAPI.list()
  } catch (e) {
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

async function handleDelete(id) {
  if (!confirm('确定删除此分类？')) return
  try {
    await categoriesAPI.delete(id)
    categories.value = categories.value.filter(c => c.id !== id)
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  categories.value = await categoriesAPI.list().catch(() => [])
})
</script>
