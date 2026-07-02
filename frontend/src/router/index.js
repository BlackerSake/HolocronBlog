import Home from '../views/Home.vue'
import ArticleDetail from '../views/ArticleDetail.vue'
import Login from '../views/Login.vue'
import AdminArticles from '../views/admin/Articles.vue'
import ArticleEditor from '../views/admin/ArticleEditor.vue'
import AdminUsers from '../views/admin/AdminUsers.vue'
import AdminCategories from '../views/admin/Categories.vue'
import AdminTags from '../views/admin/Tags.vue'
import AdminLayout from '../views/admin/Layout.vue'
import { useAuth } from '../composables/useAuth.js'

export const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/articles/:slug', name: 'article', component: ArticleDetail },
  { path: '/login', name: 'login', component: Login },
  {
    path: '/backend',
    component: AdminLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', component: AdminArticles },
      { path: 'articles', name: 'admin-articles', component: AdminArticles },
      { path: 'articles/new', name: 'admin-article-new', component: ArticleEditor },
      { path: 'articles/:slug/edit', name: 'admin-article-edit', component: ArticleEditor },
      { path: 'categories', name: 'admin-categories', component: AdminCategories, meta: { requiresAdmin: true } },
      { path: 'tags', name: 'admin-tags', component: AdminTags, meta: { requiresAdmin: true } },
      { path: 'admin', name: 'admin-users', component: AdminUsers, meta: { requiresAdmin: true } },
    ]
  }
]

export async function beforeEach(to, from, next) {
  if (to.meta.requiresAuth) {
    const auth = useAuth()
    if (!auth.token.value) {
      next({ name: 'login', query: { redirect: to.fullPath } })
      return
    }
    if (!auth.user.value) {
      try {
        await auth.fetchUser()
      } catch {
        auth.logout()
        next({ name: 'login', query: { redirect: to.fullPath } })
        return
      }
    }
    if (to.meta.requiresAdmin && auth.user?.value?.role_name !== 'admin') {
      next({ name: 'admin-articles' })
      return
    }
  }
  next()
}
