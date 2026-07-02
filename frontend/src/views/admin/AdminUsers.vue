<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
      <div>
        <h2 class="page-title" style="font-size:1.8rem;">用户管理</h2>
        <p class="page-subtitle" style="margin-bottom:0;">管理所有注册用户</p>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中</div>
    <table v-else class="admin-table">
      <thead>
        <tr><th>ID</th><th>用户名</th><th>邮箱</th><th>角色</th><th>状态</th><th>注册时间</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.id }}</td>
          <td style="color:var(--text-primary);">{{ u.username }}</td>
          <td>{{ u.email }}</td>
          <td><span class="status-badge" :class="u.role?.name === 'admin' ? 'status-published' : 'status-draft'">{{ u.role?.name }}</span></td>
          <td>{{ u.is_active ? '活跃' : '禁用' }}</td>
          <td>{{ formatDate(u.created_at) }}</td>
          <td class="actions">
            <button class="btn btn-sm" @click="openPanel(u)">编辑</button>
          </td>
        </tr>
        <tr v-if="!users.length">
          <td colspan="7" style="text-align:center;color:var(--text-muted);padding:2rem;">暂无用户。</td>
        </tr>
      </tbody>
    </table>

    <!-- 滑动面板 -->
    <transition name="slide">
      <div v-if="panelUser" class="panel-overlay" @click.self="closePanel">
        <div class="panel">
          <div class="panel-header">
            <h3>编辑用户</h3>
            <button class="panel-close" @click="closePanel">×</button>
          </div>
          <div class="panel-body">
            <div class="form-group">
              <label>用户名</label>
              <p style="padding:0.5rem 0;color:var(--text-primary);">{{ panelUser.username }}</p>
            </div>
            <div class="form-group">
              <label>邮箱</label>
              <p style="padding:0.5rem 0;color:var(--text-primary);">{{ panelUser.email }}</p>
            </div>
            <div class="form-group">
              <label>角色</label>
              <select v-model="editRole" class="select">
                <option value="admin">admin</option>
                <option value="author">author</option>
                <option value="user">user</option>
              </select>
            </div>
            <div class="form-group">
              <label>状态</label>
              <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer;font-family:var(--font-body);text-transform:none;letter-spacing:0;font-size:0.88rem;">
                <input type="checkbox" v-model="panelActive" style="accent-color:var(--teal);" />
                {{ panelActive ? '活跃' : '禁用' }}
              </label>
            </div>
            <p v-if="panelError" style="color:var(--danger);font-size:0.82rem;">{{ panelError }}</p>
          </div>
          <div class="panel-footer">
            <button class="btn btn-sm" @click="closePanel">取消</button>
            <button class="btn btn-sm btn-primary" :disabled="saving" @click="saveRole">{{ saving ? '保存中...' : '保存' }}</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminAPI } from '../../api/index.js'
import { formatDate } from '../../utils.js'

const users = ref([])
const loading = ref(true)
const panelUser = ref(null)
const panelActive = ref(true)
const editRole = ref('')
const saving = ref(false)
const panelError = ref('')

function openPanel(u) {
  panelUser.value = u
  editRole.value = u.role?.name || 'user'
  panelActive.value = u.is_active
  panelError.value = ''
}

function closePanel() { panelUser.value = null }

async function saveRole() {
  panelError.value = ''
  saving.value = true
  try {
    await adminAPI.updateRole(panelUser.value.id, { id: editRole.value === 'admin' ? 1 : editRole.value === 'author' ? 2 : 3, is_active: panelActive.value })
    closePanel()
    await fetchUsers()
  } catch (e) {
    panelError.value = e.response?.data?.message || e.response?.data?.detail || '保存失败'
  } finally { saving.value = false }
}

async function fetchUsers() {
  loading.value = true
  try {
    const data = await adminAPI.listUsers({ per_page: 100 })
    users.value = data.items
  } catch { users.value = [] }
  finally { loading.value = false }
}

onMounted(fetchUsers)
</script>

<style scoped>
.panel-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}
.panel {
  width: 360px;
  background: var(--bg-surface);
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 12px rgba(0,0,0,0.1);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.2rem;
  border-bottom: 1px solid var(--border-light);
}
.panel-header h3 { font-family: var(--font-display); font-size: 1.1rem; font-weight: 600; }
.panel-close { background: none; border: none; font-size: 1.4rem; cursor: pointer; color: var(--text-muted); }
.panel-body { flex: 1; padding: 1.2rem; overflow-y: auto; }
.panel-footer { display: flex; gap: 0.5rem; justify-content: flex-end; padding: 1rem 1.2rem; border-top: 1px solid var(--border-light); }

.slide-enter-active, .slide-leave-active { transition: transform 0.25s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); }
</style>
