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
    return data
  }

  async function fetchUser() {
    // The backend /api/v1/users/me endpoint would be needed;
    // for now use the token decode info. The token contains username in "sub".
    // We actually don't have a /users/me endpoint, so we store minimal user info on login.
    // ponytail: no dedicated user-fetch endpoint on backend, rely on login data
  }

  function logout() {
    state.token = null
    state.user = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { ...toRefs(state), login, fetchUser, logout }
}
