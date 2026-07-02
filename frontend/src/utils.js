export function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: 'short', day: 'numeric' })
}
