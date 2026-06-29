import { reactive, toRefs } from 'vue'
import { authAPI } from '../api/index.js'

const state = reactive({
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
})

function decodeToken(token) {
  try { return JSON.parse(atob(token.split('.')[1])) }
  catch { return null }
}

export function useAuth() {
  function save(token, user) {
    state.token = token
    state.user = user
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  }

  async function login(username, password) {
    const data = await authAPI.login(username, password)
    const payload = decodeToken(data.access_token)
    save(data.access_token, { username: payload?.sub || username })
    return data
  }

  async function register(username, email, password) {
    return authAPI.register({ username, email: email || undefined, password })
  }

  async function fetchUser() {
    return state.user
  }

  function logout() {
    state.token = null
    state.user = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { ...toRefs(state), login, register, fetchUser, logout }
}
