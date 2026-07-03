import { reactive, toRefs } from 'vue'
import { notificationsAPI } from '../api/index.js'

const state = reactive({
  unreadCount: 0,
  items: [],
  total: 0,
  page: 1,
  perPage: 10,
  pages: 0,
  loading: false,
})

export function useNotifications() {
  async function fetchUnreadCount() {
    if (!localStorage.getItem('token')) {
      state.unreadCount = 0
      return 0
    }
    const data = await notificationsAPI.unreadCount()
    state.unreadCount = data.count || 0
    return state.unreadCount
  }

  async function fetchList(params = {}) {
    state.loading = true
    try {
      const data = await notificationsAPI.list(params)
      state.items = data.items
      state.total = data.total
      state.page = data.page
      state.perPage = data.per_page
      state.pages = data.pages
    } finally {
      state.loading = false
    }
  }

  async function markRead(id) {
    await notificationsAPI.markRead(id)
    const item = state.items.find(i => i.id === id)
    if (item && !item.is_read) {
      item.is_read = true
      state.unreadCount = Math.max(0, state.unreadCount - 1)
    } else {
      await fetchUnreadCount()
    }
  }

  async function markAllRead() {
    await notificationsAPI.markAllRead()
    state.items.forEach(item => item.is_read = true)
    state.unreadCount = 0
  }

  function reset() {
    state.unreadCount = 0
    state.items = []
    state.total = 0
    state.page = 1
    state.pages = 0
    state.loading = false
  }

  return {
    ...toRefs(state),
    fetchUnreadCount,
    fetchList,
    markRead,
    markAllRead,
    reset,
  }
}
