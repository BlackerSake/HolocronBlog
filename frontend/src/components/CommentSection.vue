<template>
  <div class="comment-section">
    <h3 class="comment-heading">评论</h3>
    <div v-if="!auth.user.value" class="comment-login-hint">
      <router-link to="/login" style="color:var(--teal);">登录</router-link>后可发表评论
    </div>
    <form v-else class="comment-form" @submit.prevent="submitTopLevel">
      <textarea v-model="newComment" class="comment-input" placeholder="写下你的评论..." rows="3" maxlength="2000"
        @keydown.enter.prevent="submitTopLevel"></textarea>
      <div class="form-actions">
        <span class="hint">Enter 发送 · Shift+Enter 换行</span>
        <button type="submit" class="btn btn-sm btn-primary" :disabled="!newComment.trim() || submitting">{{ submitting ? '发送中...' : '发表评论' }}</button>
      </div>
    </form>
    <div v-if="loading" class="loading">加载中</div>
    <div v-else-if="!comments.length" class="comment-empty">暂无评论</div>
    <div v-else class="comment-list">
      <CommentItem
        v-for="c in comments" :key="c.id"
        :comment="c" :slug="slug" :depth="1" :author-map="authorMap"
        @delete="handleDelete"
        @refresh="fetchComments" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { commentsAPI } from '../api/index.js'
import { useAuth } from '../composables/useAuth.js'
import CommentItem from './CommentItem.vue'

const props = defineProps({ slug: String })
const auth = useAuth()

const comments = ref([])
const authorMap = ref({})
const loading = ref(true)
const newComment = ref('')
const submitting = ref(false)

async function fetchComments() {
  loading.value = true
  try {
    const raw = await commentsAPI.list(props.slug)
    const map = {}
    function walk(list) {
      for (const c of list) {
        map[c.id] = c.author?.username
        if (c.replies) walk(c.replies)
      }
    }
    walk(raw)
    // 打平：所有嵌套回复铺到第二层
    for (const c of raw) {
      const flat = []
      function collect(list) {
        for (const r of list) {
          flat.push({ ...r, replies: [] })
          if (r.replies) collect(r.replies)
        }
      }
      if (c.replies) collect(c.replies)
      c.replies = flat
    }
    comments.value = raw
    authorMap.value = map
  }
  catch { comments.value = [] }
  finally { loading.value = false }
}

async function submitTopLevel() {
  const text = newComment.value.trim()
  if (!text || submitting.value) return
  submitting.value = true
  try {
    await commentsAPI.create(props.slug, { content: text })
    newComment.value = ''
    await fetchComments()
  } catch (e) { alert(e.response?.data?.detail || '评论失败') }
  finally { submitting.value = false }
}

async function handleDelete(id) {
  if (!confirm('确定删除此评论？')) return
  try { await commentsAPI.delete(id); await fetchComments() }
  catch (e) { alert(e.response?.data?.detail || '删除失败') }
}

onMounted(fetchComments)
</script>

<style scoped>
.comment-section { margin-top: 3rem; padding-top: 2rem; border-top: 1px solid var(--border-light); }
.comment-heading { font-family: var(--font-display); font-size: 1.15rem; font-weight: 600; margin-bottom: 1.5rem; }
.comment-login-hint { text-align: center; padding: 1.5rem; color: var(--text-muted); font-size: 0.88rem; border: 1px solid var(--border-light); border-radius: var(--radius); }
.comment-form { margin-bottom: 1.5rem; display: flex; flex-direction: column; gap: 0.5rem; }
.comment-input { font-family: var(--font-body); font-size: 0.9rem; width: 100%; padding: 0.65rem 0.85rem; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: var(--radius); outline: none; transition: border-color var(--transition), box-shadow var(--transition); resize: vertical; line-height: 1.6; }
.comment-input:focus { border-color: var(--teal); box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.1); }
.form-actions { display: flex; justify-content: space-between; align-items: center; }
.hint { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.comment-empty { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.88rem; }
.comment-list { display: flex; flex-direction: column; gap: 0.75rem; }
</style>
