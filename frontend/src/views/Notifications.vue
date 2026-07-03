<template>
  <div class="notifications-page container">
    <header class="notification-header animate-in">
      <div>
        <h1 class="page-title">通知</h1>
        <p class="page-subtitle">共 {{ total }} 条消息 · {{ unreadCount }} 条未读</p>
      </div>
      <button class="btn btn-sm" :disabled="!unreadCount || loading" @click="handleMarkAllRead">
        全部已读
      </button>
    </header>

    <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
    <div v-else-if="!items.length" class="empty-state">暂无通知。</div>
    <div v-else class="notification-list animate-in animate-in-d1">
      <article
        v-for="item in items"
        :key="item.id"
        class="notification-item"
        :class="{ unread: !item.is_read, clickable: item.article_slug }"
        :tabindex="item.article_slug ? 0 : -1"
        :role="item.article_slug ? 'link' : undefined"
        @click="openNotification(item)"
        @keydown.enter="openNotification(item)"
      >
        <span class="notification-dot" aria-hidden="true"></span>
        <div class="notification-body">
          <div class="notification-line">
            <span class="notification-type">{{ typeLabel(item.type) }}</span>
            <span class="notification-time">{{ formatDate(item.created_at) }}</span>
          </div>
          <p class="notification-content">{{ item.content }}</p>
          <p v-if="item.preview" class="notification-preview">{{ item.preview }}</p>
          <div class="notification-meta">
            <span v-if="item.initiator">来自 {{ item.initiator.username }}</span>
            <span v-if="item.article_id">文章 #{{ item.article_id }}</span>
            <span v-if="item.comment_id">评论 #{{ item.comment_id }}</span>
          </div>
        </div>
        <button v-if="!item.is_read" class="btn btn-sm" @click.stop="handleMarkRead(item)" @keydown.enter.stop>已读</button>
      </article>
    </div>

    <div class="pagination" v-if="pages > 1">
      <button class="page-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <button
        v-for="p in pages"
        :key="p"
        class="page-btn"
        :class="{ active: p === page }"
        @click="goPage(p)"
      >{{ p }}</button>
      <button class="page-btn" :disabled="page >= pages" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotifications } from '../composables/useNotifications.js'
import { formatDate } from '../utils.js'

const router = useRouter()

const {
  items,
  total,
  page,
  perPage,
  pages,
  loading,
  unreadCount,
  fetchList,
  fetchUnreadCount,
  markRead,
  markAllRead,
} = useNotifications()

const typeLabels = {
  comment_on_article: '文章评论',
  reply_to_comment: '评论回复',
  someone_comment_on_my_article: '文章评论',
  someone_reply_to_me: '评论回复',
}

function typeLabel(type) {
  return typeLabels[type] || type
}

async function load(p = page.value) {
  await fetchList({ page: p, per_page: perPage.value })
  await fetchUnreadCount()
}

async function handleMarkRead(item) {
  if (!item.is_read) await markRead(item.id)
}

async function openNotification(item) {
  if (!item.article_slug) return
  if (!item.is_read) await markRead(item.id)
  router.push(`/articles/${item.article_slug}`)
}

async function handleMarkAllRead() {
  if (unreadCount.value) await markAllRead()
}

async function goPage(p) {
  if (p < 1 || p > pages.value) return
  await load(p)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => load(1))
</script>
