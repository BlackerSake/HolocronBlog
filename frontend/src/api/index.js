import axios from 'axios'

const api = axios.create({ baseURL: '/' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// unwrap the standard Response wrapper: { code, message, data }
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

  adminList: (params = {}) =>
    api.get('/articles/admin/list', { params }).then(unwrap),

  get: slug =>
    api.get(`/articles/${slug}`).then(unwrap),

  create: data =>
    api.post('/articles', data).then(unwrap),

  update: (slug, data) =>
    api.put(`/articles/${slug}`, data).then(unwrap),

  delete: slug =>
    api.delete(`/articles/${slug}`),
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
