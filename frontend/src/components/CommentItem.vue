<template>
  <div class="comment-item" :id="`comment-${comment.id}`">
    <div class="comment-avatar" :class="{ small: depth > 1 }">{{ comment.author?.username?.[0]?.toUpperCase() || '?' }}</div>
    <div class="comment-body">
      <div class="comment-meta">
        <span class="comment-author">{{ comment.author?.username }}</span>
        <span class="comment-time">{{ formatRelativeTime(comment.created_at) }}</span>
        <span v-if="comment.is_deleted" class="deleted-badge">已删除</span>
      </div>
      <div class="comment-content">
        <span v-if="replyToAuthor" class="reply-at">{{ replyToAuthor }}</span>{{ comment.content }}
      </div>
      <div class="comment-actions">
        <button v-if="!comment.is_deleted" class="action-btn comment-like-btn" :class="{ active: liked, pop: likePopped }" :disabled="liking" @click="toggleLike">
          <span class="comment-like-icon">{{ liked ? '♥' : '♡' }}</span>
          <span>{{ liked ? '已赞' : '点赞' }}</span>
          <span v-if="likeLoaded || likeCount" class="comment-like-count">{{ likeCount }}</span>
        </button>
        <button v-if="auth.user.value && !comment.is_deleted" class="action-btn" @click="openReply">回复</button>
        <button v-if="canDelete" class="action-btn action-danger" @click="$emit('delete', comment.id)">删除</button>
      </div>

      <form v-if="showReply" class="reply-form" @submit.prevent="submitReply">
        <textarea ref="replyInput" v-model="replyText" class="comment-input" :placeholder="'回复 @' + comment.author?.username" rows="2" maxlength="2000"
          @keydown.enter="handleReplyEnter"></textarea>
        <div class="form-actions">
          <span class="hint">Enter 发送 · Shift+Enter 换行</span>
          <div>
            <button type="submit" class="btn btn-sm btn-primary" :disabled="!replyText.trim() || submitting">{{ submitting ? '...' : '发送' }}</button>
            <button type="button" class="btn btn-sm" @click="closeReply">取消</button>
          </div>
        </div>
      </form>

      <div v-if="comment.replies?.length" class="reply-children">
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
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { commentsAPI, likesAPI } from '../api/index.js'
import { useAuth } from '../composables/useAuth.js'
import { formatRelativeTime } from '../utils.js'

const props = defineProps({
  comment: Object,
  slug: String,
  depth: { type: Number, default: 1 },
  authorMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['delete', 'refresh'])
const auth = useAuth()
const route = useRoute()
const router = useRouter()

const replyText = ref('')
const showReply = ref(false)
const submitting = ref(false)
const replyInput = ref(null)
const liked = ref(false)
const likeCount = ref(props.comment.like_count || 0)
const likeLoaded = ref(false)
const liking = ref(false)
const likePopped = ref(false)

const replyToAuthor = computed(() => {
  if (!props.comment.parent_id) return ''
  const name = props.authorMap[props.comment.parent_id]
  return name ? `回复 @${name}：` : ''
})

const canDelete = computed(() => {
  if (props.comment.is_deleted) return false
  const u = auth.user.value
  if (!u) return false
  return u.role_name === 'admin' || props.comment.author?.id === u.id
})

function openReply() {
  showReply.value = true
  replyText.value = ''
  nextTick(() => replyInput.value?.focus())
}

function closeReply() { showReply.value = false; replyText.value = '' }

async function fetchLikeStatus() {
  if (!auth.token.value || props.comment.is_deleted) return
  const status = await likesAPI.commentStatus(props.comment.id)
  liked.value = status.is_liked
  likeCount.value = status.like_count
  likeLoaded.value = true
}

async function toggleLike() {
  if (!auth.token.value) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (liking.value) return
  liking.value = true
  try {
    const status = await likesAPI.toggleComment(props.comment.id)
    liked.value = status.is_liked
    likeCount.value = status.like_count
    likeLoaded.value = true
    likePopped.value = true
    setTimeout(() => likePopped.value = false, 260)
  } finally {
    liking.value = false
  }
}

async function submitReply() {
  const text = replyText.value.trim()
  if (!text || submitting.value) return
  submitting.value = true
  try {
    await commentsAPI.create(props.slug, { content: text, parent_id: props.comment.id })
    replyText.value = ''
    showReply.value = false
    emit('refresh')
  } catch (e) { /* handled globally */ }
  finally { submitting.value = false }
}

function handleReplyEnter(event) {
  if (event.shiftKey) return
  event.preventDefault()
  submitReply()
}

onMounted(() => {
  fetchLikeStatus().catch(() => {})
})
</script>

<style>
.comment-item { display: flex; gap: 12px; padding: 16px; border-top: 1px solid var(--border-light); }
.comment-list > .comment-item:first-child { border-top: 0; }
.comment-avatar { width: 34px; height: 34px; border-radius: 7px; background: var(--green); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 0.82rem; font-weight: 700; flex-shrink: 0; }
.comment-avatar.small { width: 28px; height: 28px; font-size: 0.72rem; }
.comment-body { flex: 1; min-width: 0; }
.comment-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.comment-author { font-size: 0.86rem; font-weight: 700; color: var(--text-primary); }
.comment-time { font-size: 0.76rem; color: var(--text-muted); }
.deleted-badge { font-size: 0.72rem; color: var(--text-muted); border: 1px solid var(--border-light); padding: 0 6px; border-radius: 3px; }
.comment-content { font-size: 0.94rem; line-height: 1.7; color: var(--text-primary); word-break: break-word; }
.reply-at { color: var(--blue); font-size: 0.88rem; }
.comment-actions { margin-top: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.action-btn { background: none; border: 0; font-size: 0.78rem; color: var(--text-muted); cursor: pointer; padding: 2px 6px; border-radius: 999px; }
.action-btn:hover,
.action-btn.active { color: var(--blue); background: #edf3f8; }
.comment-like-btn { display: inline-flex; align-items: center; gap: 4px; }
.comment-like-icon { font-size: 0.92rem; line-height: 1; }
.comment-like-btn.pop .comment-like-icon { animation: pop 0.26s ease; }
.action-danger:hover { color: var(--danger); background: var(--danger-bg); }
.reply-children { margin-top: 12px; padding-left: 12px; border-left: 1px solid var(--border-light); }
.reply-form { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.comment-input { font-family: var(--font-body); font-size: 0.9rem; width: 100%; padding: 0.65rem 0.85rem; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: var(--radius); outline: none; resize: vertical; line-height: 1.6; }
.comment-input:focus { border-color: var(--blue); box-shadow: var(--shadow-glow); }
.form-actions { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.hint { font-size: 0.76rem; color: var(--text-muted); }
</style>
