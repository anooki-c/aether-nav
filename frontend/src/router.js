import { createRouter, createWebHistory } from 'vue-router'
import Home from './views/Home.vue'
import Login from './views/Login.vue'
import Register from './views/Register.vue'
import ResetPassword from './views/ResetPassword.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/login', name: 'login', component: Login },
  { path: '/register', name: 'register', component: Register },
  { path: '/reset-password', name: 'reset-password', component: ResetPassword },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('./views/Admin.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('./views/ProfileView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
