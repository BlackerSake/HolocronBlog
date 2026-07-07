<template>
  <div class="profile-page container-narrow">
    <router-link to="/" class="nav-link" style="display:inline-block;margin:2rem 0 1rem;">&larr; 返回档案馆</router-link>

    <div v-if="loading" class="loading">加载中<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
    <div v-else-if="!profile" class="empty-state">未找到该用户。</div>

    <template v-else>
      <section class="profile-head animate-in">
        <img v-if="profile.avatar" class="profile-avatar-img" :src="profile.avatar" alt="" />
        <div v-else class="profile-avatar">{{ displayName[0]?.toUpperCase() || '?' }}</div>
        <div class="profile-main">
          <h1 class="page-title">{{ displayName }}</h1>
          <div class="item-meta">
            <span>@{{ profile.username }}</span>
            <span>{{ formatDate(profile.created_at) }}</span>
          </div>
          <p v-if="profile.bio" class="profile-bio">{{ profile.bio }}</p>
        </div>
      </section>

      <nav class="profile-tabs animate-in animate-in-d1">
        <button type="button" :class="{ active: activeTab === 'profile' }" @click="switchTab('profile')">资料</button>
        <button type="button" :class="{ active: activeTab === 'likes' }" @click="switchTab('likes')">点赞</button>
      </nav>

      <form v-if="activeTab === 'profile' && isMe" class="profile-form animate-in animate-in-d1" @submit.prevent="saveProfile">
        <div class="form-group">
          <label>昵称</label>
          <input v-model="form.nickname" class="input" maxlength="50" />
        </div>
        <div class="form-group">
          <label>头像 URL</label>
          <input v-model="form.avatar" class="input" placeholder="https://example.com/avatar.png" />
        </div>
        <div class="form-group">
          <label>简介</label>
          <textarea v-model="form.bio" class="textarea" maxlength="255" rows="4"></textarea>
        </div>
        <button class="btn btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存资料' }}</button>
      </form>

      <section v-else-if="activeTab === 'profile'" class="profile-form animate-in animate-in-d1">
        <p class="profile-note">公开资料已展示在上方。</p>
      </section>

      <section v-else class="like-history animate-in animate-in-d2">
        <div class="history-header">
          <h2 class="section-title">点赞</h2>
          <div class="history-tabs">
            <button type="button" class="filter-chip" :class="{ active: targetType === '' }" @click="switchType('')">全部</button>
            <button type="button" class="filter-chip" :class="{ active: targetType === 'article' }" @click="switchType('article')">文章</button>
            <button type="button" class="filter-chip" :class="{ active: targetType === 'comment' }" @click="switchType('comment')">评论</button>
          </div>
        </div>

        <div v-if="!historyLoaded && historyLoading" class="loading">加载中</div>
        <div v-else-if="historyLoaded && !displayHistory.length" class="empty-state">暂无点赞记录。</div>
        <div v-else class="history-feed">
          <article v-for="item in displayHistory" :key="`${item.target_type}-${item.target_id}-${item.liked_at}`" class="history-card">
            <div class="history-mark" :class="item.target_type">{{ item.target_type === 'article' ? '文' : '评' }}</div>
            <div class="history-card-body">
              <div class="history-card-meta">
                <span>{{ item.target_type === 'article' ? '赞了文章' : '赞了评论' }}</span>
                <span>{{ formatDate(item.liked_at) }}</span>
              </div>

              <router-link v-if="item.url" :to="item.url" class="history-title">
                {{ item.target_type === 'article' ? item.article_title || item.title : item.comment_content || item.title }}
              </router-link>
              <p v-else class="history-title dimmed">{{ item.title }}</p>

              <div v-if="item.target_type === 'comment' && item.article_url" class="history-context">
                来自 <router-link :to="item.article_url">《{{ item.article_title }}》</router-link>
              </div>

              <div class="history-author" v-if="item.author_id">
                <router-link :to="`/users/${item.author_id}/profile`" class="history-author-link">
                  <img v-if="item.author_avatar" :src="item.author_avatar" alt="" />
                  <span v-else>{{ item.author_name?.[0]?.toUpperCase() || '?' }}</span>
                  {{ item.author_name }}
                </router-link>
              </div>
            </div>
          </article>
        </div>

        <div class="history-loader" aria-hidden="true"></div>
        <div v-if="historyLoading && displayHistory.length" class="history-loading">加载中</div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { likesAPI, profileAPI } from '../api/index.js'
import { useAuth } from '../composables/useAuth.js'
import { useToast } from '../composables/useToast.js'
import { formatDate } from '../utils.js'

const route = useRoute()
const auth = useAuth()
const toast = useToast()

const profile = ref(null)
const loading = ref(true)
const saving = ref(false)
const history = ref([])
const historyLoading = ref(false)
const historyLoaded = ref(false)
const historyDone = ref(false)
const activeTab = ref('profile')
const targetType = ref('')
const page = ref(1)
const perPage = 50
let historyRequestId = 0
const form = reactive({ nickname: '', avatar: '', bio: '' })

const userId = computed(() => route.name === 'my-profile' ? auth.user.value?.id : Number(route.params.id))
const isMe = computed(() => auth.user.value?.id && Number(userId.value) === auth.user.value.id)
const displayName = computed(() => profile.value?.nickname || profile.value?.username || '')
const displayHistory = computed(() => {
  const seen = new Set()
  return history.value.filter(item => {
    const key = `${item.target_type}-${item.target_id}`
    if (seen.has(key)) return false
    seen.add(key)
    if (item.target_type === 'article') return Boolean(item.url && (item.article_title || item.title))
    if (item.target_type === 'comment') return Boolean(item.url && item.comment_content && item.article_title)
    return false
  })
})

function fillForm(data) {
  form.nickname = data.nickname || ''
  form.avatar = data.avatar || ''
  form.bio = data.bio || ''
}

async function fetchProfile() {
  if (!userId.value) {
    profile.value = null
    loading.value = false
    return
  }
  loading.value = true
  try {
    const data = await profileAPI.get(userId.value)
    profile.value = data
    fillForm(data)
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  if (!userId.value || historyLoading.value || historyDone.value) return
  const requestId = historyRequestId
  historyLoading.value = true
  try {
    const params = {
      page: page.value,
      per_page: perPage,
    }
    if (targetType.value) params.target_type = targetType.value
    const items = await likesAPI.userHistory(userId.value, params)
    if (requestId !== historyRequestId) return
    history.value = page.value === 1 ? items : [...history.value, ...items]
    historyDone.value = items.length < perPage
  } finally {
    if (requestId === historyRequestId) {
      historyLoading.value = false
      historyLoaded.value = true
    }
  }
}

async function refreshHistory() {
  historyRequestId += 1
  history.value = []
  page.value = 1
  historyLoaded.value = false
  historyDone.value = false
  historyLoading.value = false
  try {
    await fetchHistory()
  } catch {
    history.value = []
  }
}

async function saveProfile() {
  if (saving.value) return
  saving.value = true
  try {
    const data = await profileAPI.update({ ...form })
    profile.value = data
    fillForm(data)
    auth.updateUser(data)
    toast.show('资料已保存', 'success')
  } finally {
    saving.value = false
  }
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'likes' && !historyLoaded.value) await refreshHistory()
}

async function switchType(type) {
  targetType.value = type
  await refreshHistory()
}

async function loadMoreHistory() {
  if (activeTab.value !== 'likes' || historyLoading.value || historyDone.value) return
  page.value += 1
  try {
    await fetchHistory()
  } catch {
    page.value -= 1
  }
}

function onScroll() {
  const doc = document.documentElement
  if (window.innerHeight + window.scrollY < doc.scrollHeight - 360) return
  loadMoreHistory()
}

onMounted(fetchProfile)
onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
watch(() => route.fullPath, () => {
  activeTab.value = 'profile'
  targetType.value = ''
  history.value = []
  historyLoaded.value = false
  historyDone.value = false
  page.value = 1
  fetchProfile()
})
</script>

<style scoped>
.profile-page {
  padding-bottom: 3rem;
}

.profile-head {
  position: relative;
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
  padding: 1.35rem;
  border: 1px solid rgba(95, 110, 103, 0.12);
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(233, 251, 247, 0.9), rgba(241, 239, 255, 0.54)),
    rgba(255,255,255,0.72);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.profile-head::after {
  content: '';
  position: absolute;
  inset: auto 1.35rem 0;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--teal), var(--accent), var(--violet));
}

.profile-avatar,
.profile-avatar-img {
  width: 76px;
  height: 76px;
  border-radius: 10px;
  flex-shrink: 0;
}

.profile-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--teal), var(--violet));
  color: #fff;
  font-family: var(--font-mono);
  font-size: 1.6rem;
  font-weight: 600;
  box-shadow: 0 16px 32px rgba(15, 143, 134, 0.18);
}

.profile-avatar-img {
  object-fit: cover;
  border: 1px solid var(--border-light);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.12);
}

.profile-main {
  min-width: 0;
}

.profile-bio {
  margin-top: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.7;
  word-break: break-word;
}

.profile-tabs {
  position: sticky;
  top: 86px;
  z-index: 2;
  display: flex;
  gap: 0.35rem;
  margin-top: 1rem;
  padding: 0.35rem;
  border: 1px solid rgba(95, 110, 103, 0.12);
  border-radius: 999px;
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(14px);
  box-shadow: var(--shadow-sm);
}

.profile-tabs button {
  flex: 1;
  border: 0;
  border-radius: 999px;
  padding: 0.55rem 0.9rem;
  background: transparent;
  color: var(--text-muted);
  font-family: var(--font-mono);
  cursor: pointer;
  transition: background var(--transition), color var(--transition), transform var(--transition);
}

.profile-tabs button:hover {
  color: var(--teal);
  transform: translateY(-1px);
}

.profile-tabs button.active {
  background: linear-gradient(135deg, var(--teal), var(--violet));
  color: #fff;
  box-shadow: 0 10px 24px rgba(15, 143, 134, 0.18);
}

.profile-form,
.like-history {
  margin-top: 1.5rem;
  padding: 1.35rem;
  border-bottom: 1px solid var(--border-light);
  border: 1px solid rgba(95, 110, 103, 0.12);
  border-radius: var(--radius);
  background: rgba(255,255,255,0.72);
  box-shadow: var(--shadow-sm);
}

.profile-note {
  color: var(--text-muted);
  font-size: 0.88rem;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.section-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 600;
}

.history-tabs {
  display: flex;
  gap: 0.5rem;
}

.history-feed {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.history-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid rgba(95, 110, 103, 0.12);
  border-radius: var(--radius);
  background: rgba(255,255,255,0.74);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
}

.history-card:hover {
  border-color: rgba(15, 143, 134, 0.22);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.history-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 600;
}

.history-mark.article {
  background: var(--teal-bg);
  color: var(--teal);
}

.history-mark.comment {
  background: var(--violet-bg);
  color: var(--violet);
}

.history-card-body {
  min-width: 0;
}

.history-card-meta {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.68rem;
  margin-bottom: 0.25rem;
}

.history-title {
  display: block;
  color: var(--text-primary);
  font-size: 0.98rem;
  line-height: 1.6;
  text-decoration: none;
  word-break: break-word;
}

.history-title:hover {
  color: var(--teal);
}

.history-context {
  margin-top: 0.35rem;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.history-author {
  margin-top: 0.55rem;
}

.history-author-link {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.72rem;
}

.history-author-link img,
.history-author-link span {
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 999px;
  object-fit: cover;
}

.history-author-link span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--teal), var(--violet));
  color: #fff;
}

.history-loader {
  min-height: 1px;
}

.history-loading {
  min-height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.dimmed {
  color: var(--text-muted);
  font-style: italic;
}

@media (max-width: 640px) {
  .profile-head,
  .history-header {
    flex-direction: column;
  }

  .profile-tabs {
    top: 78px;
  }

  .history-card {
    grid-template-columns: 1fr;
  }
}
</style>
