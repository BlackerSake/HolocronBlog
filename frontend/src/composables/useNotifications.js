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
let socket = null
let reconnectTimer = null

function isTokenExpired(token) {
  try {
    const payload = token.split('.')[1]
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const data = JSON.parse(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')))
    return !data.exp || data.exp * 1000 <= Date.now()
  } catch {
    return true
  }
}

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

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    reconnectTimer = null
    if (socket) {
      socket.onclose = null
      socket.close()
    }
    socket = null
  }

  function connect() {
    disconnect()
    const token = localStorage.getItem('token')
    if (!token) return
    if (isTokenExpired(token)) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
      return
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const connection = new WebSocket(`${protocol}//${window.location.host}/notifications/ws?token=${encodeURIComponent(token)}`)
    socket = connection
    connection.onopen = () => fetchUnreadCount().catch(() => {})
    connection.onmessage = event => {
      const message = JSON.parse(event.data)
      if (message.type === 'notification_created') {
        fetchUnreadCount().catch(() => {})
        fetchList({ page: state.page, per_page: state.perPage }).catch(() => {})
      } else if (message.type === 'like_changed') {
        window.dispatchEvent(new CustomEvent('holocron:like-changed', { detail: message }))
      }
    }
    connection.onclose = () => {
      if (socket !== connection) return
      socket = null
      if (localStorage.getItem('token')) reconnectTimer = setTimeout(connect, 3000)
    }
  }

  function reset() {
    state.unreadCount = 0
    state.items = []
    state.total = 0
    state.page = 1
    state.pages = 0
    state.loading = false
    disconnect()
  }

  return {
    ...toRefs(state),
    fetchUnreadCount,
    fetchList,
    markRead,
    markAllRead,
    connect,
    disconnect,
    reset,
  }
}
