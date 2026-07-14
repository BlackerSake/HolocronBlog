<template>
  <div class="article-page container-narrow" v-if="article">
    <div class="animate-in">
      <router-link to="/" class="nav-link" style="display:inline-block;margin-bottom:2rem;">&larr; 返回档案馆</router-link>

      <div class="item-meta" style="margin-bottom:0.75rem;">
        <router-link v-if="article.author" :to="`/users/${article.author.id}/profile`">{{ article.author.username }}</router-link>
        <span>{{ formatDate(article.created_at) }}</span>
        <span v-if="article.category">{{ article.category.name }}</span>
        <span>{{ article.views || 0 }} 次阅读</span>
      </div>

      <h1 class="page-title" style="margin-bottom:0.5rem;">{{ article.title }}</h1>

      <button class="like-btn" :class="{ active: liked, pop: likePopped }" :disabled="liking" @click="toggleLike">
        <span class="like-icon">{{ liked ? '♥' : '♡' }}</span>
        <span>{{ liked ? '已赞' : '点赞' }}</span>
        <span v-if="likeLoaded || likeCount" class="like-count">{{ likeCount }}</span>
      </button>

      <img v-if="article.cover_image" class="article-cover" :src="article.cover_image" :alt="article.title" />

      <div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:2.5rem;" v-if="article.tags?.length">
        <span class="tag-pill" v-for="t in article.tags" :key="t.id">#{{ t.name }}</span>
      </div>
    </div>

    <div class="markdown-body animate-in animate-in-d1" v-html="article.content_html"></div>

    <CommentSection :slug="route.params.slug" />
  </div>

  <div v-else-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
  <div v-else class="container-narrow empty-state" style="margin-top:3rem;">
    未找到该文章。
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { articlesAPI, likesAPI } from '../api/index.js'
import CommentSection from '../components/CommentSection.vue'
import { formatDate } from '../utils.js'
import { useAuth } from '../composables/useAuth.js'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const article = ref(null)
const loading = ref(true)
const liked = ref(false)
const likeCount = ref(0)
const likeLoaded = ref(false)
const liking = ref(false)
const likePopped = ref(false)

async function fetchLikeStatus() {
  if (!auth.token.value) return
  const status = await likesAPI.articleStatus(route.params.slug)
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
    const status = await likesAPI.toggleArticle(route.params.slug)
    liked.value = status.is_liked
    likeCount.value = status.like_count
    likeLoaded.value = true
    likePopped.value = true
    setTimeout(() => likePopped.value = false, 280)
  } finally {
    liking.value = false
  }
}

onMounted(async () => {
  try {
    article.value = await articlesAPI.get(route.params.slug)
    likeCount.value = article.value.like_count ?? 0
    await fetchLikeStatus().catch(() => {})
  } catch { /* 404 handled by template */ }
  finally { loading.value = false }
})
</script>

<style scoped>
.article-page {
  padding-top: 2rem;
  padding-bottom: 3rem;
}

.markdown-body {
  padding: 0.5rem 0;
}

.article-cover {
  display: block;
  width: 100%;
  max-height: 360px;
  margin: 0.5rem 0 1.5rem;
  border-radius: var(--radius);
  object-fit: cover;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
}

.like-btn {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.25rem 0 1.5rem;
  padding: 0.48rem 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background: rgba(255,255,255,0.76);
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: background var(--transition), border-color var(--transition), color var(--transition), box-shadow var(--transition), transform var(--transition);
}

.like-btn:hover {
  border-color: var(--teal);
  background: var(--teal-bg);
  color: var(--teal);
  transform: translateY(-1px);
}

.like-btn.active {
  border-color: transparent;
  background: linear-gradient(135deg, var(--teal), var(--violet));
  color: #fff;
  box-shadow: 0 12px 28px rgba(15, 143, 134, 0.22);
}

.like-icon {
  font-size: 1rem;
  line-height: 1;
}

.like-btn.pop .like-icon {
  animation: pop 0.28s ease;
}

.like-count {
  min-width: 1.4rem;
  height: 1.4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.45rem;
  border-radius: 999px;
  background: rgba(255,255,255,0.55);
}

.like-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
