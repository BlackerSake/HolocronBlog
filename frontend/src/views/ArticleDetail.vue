<template>
  <div class="article-page container-narrow" v-if="article">
    <div class="animate-in">
      <router-link to="/" class="nav-link" style="display:inline-block;margin-bottom:2rem;">&larr; 返回档案馆</router-link>

      <div class="item-meta" style="margin-bottom:0.75rem;">
        <span v-if="article.author">{{ article.author.username }}</span>
        <span>{{ formatDate(article.created_at) }}</span>
        <span v-if="article.category">{{ article.category.name }}</span>
      </div>

      <h1 class="page-title" style="margin-bottom:0.5rem;">{{ article.title }}</h1>

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
import { useRoute } from 'vue-router'
import { articlesAPI } from '../api/index.js'
import CommentSection from '../components/CommentSection.vue'
import { formatDate } from '../utils.js'

const route = useRoute()
const article = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    article.value = await articlesAPI.get(route.params.slug)
  } catch { /* 404 handled by template */ }
  finally { loading.value = false }
})
</script>
