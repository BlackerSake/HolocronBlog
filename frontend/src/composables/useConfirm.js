import { reactive } from 'vue'

const state = reactive({ visible: false, message: '', resolve: null })

export function useConfirm() {
  function confirm(msg) {
    state.message = msg
    state.visible = true
    return new Promise(resolve => { state.resolve = resolve })
  }
  function ok() { state.visible = false; if (state.resolve) state.resolve(true) }
  function cancel() { state.visible = false; if (state.resolve) state.resolve(false) }
  return { state, confirm, ok, cancel }
}
