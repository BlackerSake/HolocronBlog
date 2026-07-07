<template>
  <div class="comment-item" :id="`comment-${comment.id}`">
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
          @keydown.enter.prevent="submitReply"></textarea>
        <div class="form-actions">
          <span class="hint">Enter 发送</span>
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

onMounted(() => {
  fetchLikeStatus().catch(() => {})
})
</script>

<style>
.comment-item { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; padding: 0.7rem; border: 1px solid transparent; border-radius: var(--radius); transition: background var(--transition), border-color var(--transition), box-shadow var(--transition), transform var(--transition); animation: fadeUp 0.32s ease both; }
.comment-item:hover { background: rgba(255,255,255,0.72); border-color: rgba(15, 143, 134, 0.12); box-shadow: var(--shadow-sm); transform: translateY(-1px); }
.comment-avatar { width: 34px; height: 34px; border-radius: 50%; background: linear-gradient(135deg, var(--teal), var(--violet)); color: #fff; display: flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 0.8rem; font-weight: 600; flex-shrink: 0; box-shadow: 0 8px 18px rgba(15, 143, 134, 0.16); }
.comment-avatar.small { width: 28px; height: 28px; font-size: 0.7rem; }
.comment-body { flex: 1; min-width: 0; }
.comment-meta { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.2rem; flex-wrap: wrap; }
.comment-author { font-family: var(--font-mono); font-size: 0.78rem; font-weight: 600; color: var(--text-primary); }
.comment-time { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.deleted-badge { font-size: 0.65rem; color: var(--text-muted); font-family: var(--font-mono); border: 1px solid var(--border-light); padding: 0 0.35rem; border-radius: 3px; }
.comment-content { font-size: 0.92rem; line-height: 1.65; color: var(--text-primary); word-break: break-word; }
.reply-at { color: var(--teal); font-size: 0.85rem; }
.comment-actions { margin-top: 0.5rem; display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }
.action-btn { background: none; border: none; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); cursor: pointer; padding: 0.2rem 0.35rem; border-radius: 999px; transition: background var(--transition), color var(--transition), transform var(--transition); }
.action-btn:hover { color: var(--teal); background: var(--teal-bg); transform: translateY(-1px); }
.action-btn.active { color: var(--teal); background: var(--teal-bg); }
.comment-like-btn { display: inline-flex; align-items: center; gap: 0.25rem; }
.comment-like-icon { font-size: 0.92rem; line-height: 1; }
.comment-like-btn.pop .comment-like-icon { animation: pop 0.26s ease; }
.comment-like-count { color: inherit; }
.action-danger:hover { color: var(--danger); }
.reply-children { margin-top: 0.75rem; padding-left: 0.75rem; border-left: 1px solid var(--border-light); }
.reply-form { margin-top: 0.65rem; display: flex; flex-direction: column; gap: 0.4rem; animation: fadeUp 0.2s ease both; }
.comment-input { font-family: var(--font-body); font-size: 0.9rem; width: 100%; padding: 0.65rem 0.85rem; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-primary); border-radius: var(--radius); outline: none; transition: border-color var(--transition), box-shadow var(--transition); resize: vertical; line-height: 1.6; }
.comment-input:focus { border-color: var(--teal); box-shadow: var(--shadow-glow); }
.form-actions { display: flex; justify-content: space-between; align-items: center; }
.hint { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
</style>
