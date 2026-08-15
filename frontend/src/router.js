import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import Login from './views/Login.vue'
import Register from './views/Register.vue'
import ResetPassword from './views/ResetPassword.vue'
import { store, loadMe } from './store'

// 需要登录才能访问的路由
const PROTECTED = ['admin', 'settings', 'network-check']

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/login', name: 'login', component: Login },
  { path: '/register', name: 'register', component: Register },
  { path: '/reset-password', name: 'reset-password', component: ResetPassword },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('./views/Admin.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/ProfileView.vue'),
  },
  {
    path: '/network-check',
    name: 'network-check',
    component: () => import('./views/NetworkCheckView.vue'),
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录访问受保护页 → 跳登录页并带上 redirect（登录后自动回跳）；
// /admin 还需管理员角色，否则回前台首页。
router.beforeEach(async (to, from, next) => {
  const loggedIn = !!store.token
  if (to.name && PROTECTED.includes(to.name) && !loggedIn) {
    return next({ name: 'login', query: { redirect: to.fullPath } })
  }
  if (to.meta && to.meta.requiresAdmin && loggedIn) {
    // 刷新后 store.user 是异步加载的，此刻可能仍为空；
    // 必须先等待 loadMe 完成再判定角色，否则会误判非管理员而跳走前台
    if (!store.user) await loadMe()
    // loadMe 失败会清除 token → 重新走登录逻辑并带上回跳
    if (!store.token) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
    const role = store.user && store.user.role
    if (role !== 'admin') return next({ name: 'home' })
  }
  next()
})

export default router
