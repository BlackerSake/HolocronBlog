import { reactive } from 'vue'

const state = reactive({ visible: false, message: '', type: 'error' })
let timer = null

export function useToast() {
  function show(msg, type = 'error') {
    state.message = msg
    state.type = type
    state.visible = true
    clearTimeout(timer)
    timer = setTimeout(() => state.visible = false, 3000)
  }
  function hide() {
    state.visible = false
    clearTimeout(timer)
  }
  return { state, show, hide }
}
