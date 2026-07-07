import { reactive, toRefs } from 'vue'
import { authAPI } from '../api/index.js'

const state = reactive({
  token: localStorage.getItem('token') || null,
  user: JSON.parse(localStorage.getItem('user') || 'null'),
})

export function useAuth() {
  function save(token, user) {
    state.token = token
    state.user = user
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
  }

  function updateUser(patch) {
    state.user = { ...(state.user || {}), ...patch }
    localStorage.setItem('user', JSON.stringify(state.user))
  }

  async function login(username, password) {
    const data = await authAPI.login(username, password)
    save(data.access_token, data.user || { username })
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

  return { ...toRefs(state), login, register, fetchUser, logout, updateUser }
}
