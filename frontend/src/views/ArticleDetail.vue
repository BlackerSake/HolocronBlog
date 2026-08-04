<template>
  <div class="topic-detail-page" v-if="article">
    <router-link to="/" class="back-link">返回论坛</router-link>

    <article class="forum-panel topic-detail">
      <header class="topic-detail-head">
        <div class="topic-main">
          <span class="topic-avatar large">{{ avatarText(article.author) }}</span>
          <div class="topic-copy">
            <div class="topic-labels">
              <span v-if="article.category" class="tag-pill">{{ article.category.name }}</span>
              <span v-for="tag in article.tags" :key="tag.id" class="tag-pill">#{{ tag.name }}</span>
            </div>
            <h1>{{ article.title }}</h1>
            <p class="topic-meta">
              {{ article.author?.nickname || article.author?.username || '匿名' }}
              · 发布于 {{ formatRelativeTime(article.created_at) }}
              · {{ article.views || 0 }} 浏览
            </p>
          </div>
        </div>

        <button class="like-btn" :class="{ active: liked, pop: likePopped }" :disabled="liking" @click="toggleLike">
          <span>{{ liked ? '已赞' : '点赞' }}</span>
          <strong>{{ likeCount }}</strong>
        </button>
      </header>

      <img v-if="article.cover_image" class="article-cover" :src="article.cover_image" :alt="article.title" />
      <div class="markdown-body topic-content-body" v-html="article.content_html"></div>
    </article>

    <CommentSection :slug="route.params.slug" />
  </div>

  <div v-else-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
  <div v-else class="container-narrow empty-state" style="margin-top:3rem;">未找到该主题。</div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { articlesAPI, likesAPI } from '../api/index.js'
import CommentSection from '../components/CommentSection.vue'
import { formatRelativeTime } from '../utils.js'
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

function avatarText(user) {
  return (user?.nickname || user?.username || '?').slice(0, 1).toUpperCase()
}

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
    const status = await likesAPI.setArticle(route.params.slug, !liked.value)
    liked.value = status.is_liked
    likeCount.value = status.like_count
    likeLoaded.value = true
    likePopped.value = true
    setTimeout(() => likePopped.value = false, 260)
  } finally {
    liking.value = false
  }
}

onMounted(async () => {
  try {
    article.value = await articlesAPI.get(route.params.slug)
    likeCount.value = article.value.like_count || 0
    await fetchLikeStatus().catch(() => {})
  } catch {
    article.value = null
  } finally {
    loading.value = false
  }
})
</script>
