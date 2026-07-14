<template>
  <div class="forum-panel comment-section">
    <h3 class="comment-heading">回复</h3>
    <div v-if="!auth.user.value" class="comment-login-hint">
      <router-link to="/login">登录</router-link>后可参与讨论
    </div>
    <form v-else class="comment-form" @submit.prevent="submitTopLevel">
      <textarea v-model="newComment" class="comment-input" placeholder="写下你的回复..." rows="4" maxlength="2000"
        @keydown.enter="handleTopLevelEnter"></textarea>
      <div class="form-actions">
        <span class="hint">Enter 发送 · Shift+Enter 换行</span>
        <button type="submit" class="btn btn-sm btn-primary" :disabled="!newComment.trim() || submitting">{{ submitting ? '发送中...' : '发表回复' }}</button>
      </div>
    </form>
    <div v-if="loading" class="loading">加载中</div>
    <div v-else-if="!comments.length" class="comment-empty">暂无回复。</div>
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
import { useConfirm } from '../composables/useConfirm.js'
const dialog = useConfirm()

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
  } catch (e) { /* handled globally */ }
  finally { submitting.value = false }
}

function handleTopLevelEnter(event) {
  if (event.shiftKey) return
  event.preventDefault()
  submitTopLevel()
}

async function handleDelete(id) {
  if (!await dialog.confirm('确定删除此评论？')) return
  try { await commentsAPI.delete(id); await fetchComments() }
  catch (e) { /* handled globally */ }
}

onMounted(fetchComments)
</script>

<style scoped>
.comment-section { margin-top: 16px; padding: 0; }
.comment-heading { margin: 0; padding: 14px 16px; border-bottom: 1px solid var(--border-light); font-size: 1rem; }
.comment-login-hint { padding: 18px 16px; color: var(--text-muted); }
.comment-login-hint a { color: var(--blue); }
.comment-form { display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border-light); }
.comment-input { font-family: var(--font-body); font-size: 0.92rem; width: 100%; padding: 0.75rem 0.9rem; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: var(--radius); outline: none; resize: vertical; line-height: 1.6; }
.comment-input:focus { border-color: var(--blue); box-shadow: var(--shadow-glow); }
.form-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.hint { font-size: 0.78rem; color: var(--text-muted); }
.comment-empty { padding: 26px 16px; color: var(--text-muted); text-align: center; }
.comment-list { display: flex; flex-direction: column; }
</style>
