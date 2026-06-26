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

  async function login(username, password) {
    const data = await authAPI.login(username, password)
    save(data.access_token, { username })
    await fetchUser()
    return data
  }

  async function register(username, email, password) {
    return authAPI.register({ username, email: email || undefined, password })
  }

  async function fetchUser() {
    if (!state.token) return null
    const user = await authAPI.me()
    save(state.token, user)
    return user
  }

  function logout() {
    state.token = null
    state.user = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { ...toRefs(state), login, register, fetchUser, logout }
}
