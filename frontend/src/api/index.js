import axios from 'axios'
import { useToast } from '../composables/useToast.js'

const api = axios.create({ baseURL: '/' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    const detail = err.response?.data?.message || err.response?.data?.detail
    const status = err.response?.status
    if (status === 401 && !err.config.url.includes('/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    } else if (status && detail) {
      useToast().show(`[${status}] ${detail}`)
    } else if (status) {
      useToast().show(`[${status}] Request failed`)
    }
    return Promise.reject(err)
  }
)

function unwrap(res) {
  const body = res.data
  if (body.code && body.code >= 400) throw new Error(body.message || 'Request failed')
  return body.data
}

export default api

/* ── Auth ── */
export const authAPI = {
  login: (username, password) =>
    api.post('/api/v1/login', new URLSearchParams({ username, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }).then(unwrap),

  register: data =>
    api.post('/api/v1/register', data).then(unwrap),

}

/* ── Articles ── */
export const articlesAPI = {
  list: (params = {}) =>
    api.get('/articles', { params }).then(unwrap),

  backendList: (params = {}) =>
    api.get('/articles/backend/list', { params }).then(unwrap),

  backendGet: slug =>
    api.get(`/articles/backend/detail/${slug}`).then(unwrap),

  get: slug =>
    api.get(`/articles/${slug}`).then(unwrap),

  create: data =>
    api.post('/articles', data).then(unwrap),

  update: (slug, data) =>
    api.put(`/articles/${slug}`, data).then(unwrap),

  unpublish: slug =>
    api.patch(`/articles/${slug}/unpublish`).then(unwrap),

  delete: slug =>
    api.delete(`/articles/${slug}`),
}

/* ── Comments ── */
export const commentsAPI = {
  list: slug =>
    api.get(`/articles/${slug}/comments`).then(unwrap),

  create: (slug, data) =>
    api.post(`/articles/${slug}/comments`, data).then(unwrap),

  delete: id =>
    api.delete(`/comments/${id}`),
}


/* ── Notifications ── */
export const notificationsAPI = {
  list: (params = {}) =>
    api.get('/notifications', { params }).then(unwrap),

  unreadCount: () =>
    api.get('/notifications/unread_count').then(res => res.data),

  markRead: id =>
    api.patch(`/notifications/${id}/read`),

  markAllRead: () =>
    api.patch('/notifications/read-all'),
}

/* ── Admin ── */
export const adminAPI = {
  listUsers: (params = {}) =>
    api.get('/admin/users', { params }).then(unwrap),

  updateRole: (userId, data) =>
    api.put(`/admin/users/${userId}`, data).then(unwrap),
}

/* ── Categories ── */
export const categoriesAPI = {
  list: () =>
    api.get('/categories').then(unwrap),

  create: data =>
    api.post('/categories', data).then(unwrap),

  update: (id, data) =>
    api.put(`/categories/${id}`, data).then(unwrap),

  delete: id =>
    api.delete(`/categories/${id}`),
}

/* ── Tags ── */
export const tagsAPI = {
  list: () =>
    api.get('/tags').then(unwrap),

  create: data =>
    api.post('/tags', data).then(unwrap),

  update: (id, data) =>
    api.put(`/tags/${id}`, data).then(unwrap),

  delete: id =>
    api.delete(`/tags/${id}`),
}
