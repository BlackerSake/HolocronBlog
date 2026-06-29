<template>
  <div class="comment-item">
    <div class="comment-avatar" :class="{ small: depth > 1 }">{{ comment.author?.username?.[0]?.toUpperCase() || '?' }}</div>
    <div class="comment-body">
      <div class="comment-meta">
        <span class="comment-author">{{ comment.author?.username }}</span>
        <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
        <span v-if="comment.is_deleted" class="deleted-badge">已删除</span>
      </div>
      <div class="comment-content">
        <span v-if="replyToAuthor" class="reply-at">{{ replyToAuthor }}</span>{{ comment.content }}
      </div>
      <div class="comment-actions">
        <button v-if="auth.user.value && !comment.is_deleted" class="action-btn" @click="openReply">回复</button>
        <button v-if="canDelete" class="action-btn action-danger" @click="$emit('delete', comment.id)">删除</button>
      </div>

      <form v-if="showReply" class="reply-form" @submit.prevent="submitReply">
        <textarea v-model="replyText" class="comment-input" :placeholder="'回复 @' + comment.author?.username" rows="2" maxlength="2000"
          @keydown.enter.prevent="submitReply"></textarea>
        <div class="form-actions">
          <span class="hint">Enter 发送</span>
          <div>
            <button type="submit" class="btn btn-sm btn-primary" :disabled="!replyText.trim() || submitting">{{ submitting ? '...' : '发送' }}</button>
            <button type="button" class="btn btn-sm" @click="closeReply">取消</button>
          </div>
        </div>
      </form>

      <div v-if="comment.replies?.length" class="reply-list">
        <CommentItem
          v-for="reply in comment.replies" :key="reply.id"
          :comment="reply" :slug="slug" :depth="depth + 1"
          :author-map="authorMap"
          @delete="id => $emit('delete', id)"
          @refresh="$emit('refresh')" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { commentsAPI } from '../api/index.js'
import { useAuth } from '../composables/useAuth.js'

const props = defineProps({
  comment: Object,
  slug: String,
  depth: { type: Number, default: 1 },
  authorMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['delete', 'refresh'])
const auth = useAuth()

const replyText = ref('')
const showReply = ref(false)
const submitting = ref(false)

const replyToAuthor = computed(() => {
  if (!props.comment.parent_id) return ''
  const name = props.authorMap[props.comment.parent_id]
  return name ? `回复 @${name}：` : ''
})

const canDelete = computed(() => {
  if (props.comment.is_deleted) return false
  const u = auth.user.value
  if (!u) return false
  return u.role === 'admin' || props.comment.author?.id === u.id
})

function formatTime(d) {
  if (!d) return ''
  const date = new Date(d)
  const now = new Date()
  const diff = now - date
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return date.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', month: 'short', day: 'numeric' })
}

function openReply() {
  showReply.value = true
  replyText.value = ''
}

function closeReply() { showReply.value = false; replyText.value = '' }

async function submitReply() {
  const text = replyText.value.trim()
  if (!text || submitting.value) return
  submitting.value = true
  try {
    await commentsAPI.create(props.slug, { content: text, parent_id: props.comment.id })
    replyText.value = ''
    showReply.value = false
    emit('refresh')
  } catch (e) { alert(e.response?.data?.detail || '回复失败') }
  finally { submitting.value = false }
}
</script>

<style>
.comment-item { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }
.comment-avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--teal); color: #fff; display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; flex-shrink: 0; }
.comment-avatar.small { width: 28px; height: 28px; font-size: 0.7rem; }
.comment-body { flex: 1; min-width: 0; }
.comment-meta { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.2rem; flex-wrap: wrap; }
.comment-author { font-family: var(--font-mono); font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.comment-time { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.deleted-badge { font-size: 0.65rem; color: var(--text-muted); font-family: var(--font-mono); border: 1px solid var(--border-light); padding: 0 0.35rem; border-radius: 3px; }
.comment-content { font-size: 0.92rem; line-height: 1.65; color: var(--text-primary); word-break: break-word; }
.reply-at { color: var(--teal); font-size: 0.85rem; }
.comment-actions { margin-top: 0.35rem; display: flex; gap: 0.75rem; }
.action-btn { background: none; border: none; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); cursor: pointer; padding: 0; transition: color var(--transition); }
.action-btn:hover { color: var(--teal); }
.action-danger:hover { color: var(--danger); }
.reply-list { margin-top: 0.6rem; padding-left: 0.5rem; border-left: 2px solid var(--border-light); }
.reply-form { margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem; }
.comment-input { font-family: var(--font-body); font-size: 0.9rem; width: 100%; padding: 0.65rem 0.85rem; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: var(--radius); outline: none; transition: border-color var(--transition), box-shadow var(--transition); resize: vertical; line-height: 1.6; }
.comment-input:focus { border-color: var(--teal); box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.1); }
.form-actions { display: flex; justify-content: space-between; align-items: center; }
.hint { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
</style>
