<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { store, setAuth, loadMe, loadTree } from '../store'
import { api } from '../api/client'

const route = useRoute()
const router = useRouter()
const username = ref('admin')
const password = ref('admin123')
const remember = ref(false)
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const data = await api.login(username.value.trim(), password.value)
    setAuth(data.token, data.user, remember.value)
    await loadMe()
    await loadTree()
    // 登录后优先回跳到访问前被拦截的页面（带 redirect 时）；否则回前台首页
    const redirect = route.query.redirect
    router.push(typeof redirect === 'string' && redirect ? redirect : '/')
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

// 游客访问：不登录，直接进入前台首页浏览公开内容（后端按 guest 角色走权限）
function enterAsGuest() {
  setAuth('', null)
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen bg-surface-container-low flex items-center justify-center p-4 relative overflow-hidden font-body-md text-body-md text-on-surface">
    <!-- 弱紫渐变背景（对齐 p7） -->
    <div class="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none z-0">
      <div class="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] max-w-[800px] max-h-[800px] rounded-full bg-primary-fixed/30 blur-[120px] opacity-70"></div>
      <div class="absolute bottom-[-20%] right-[-10%] w-[50vw] h-[50vw] max-w-[600px] max-h-[600px] rounded-full bg-secondary-fixed/40 blur-[100px] opacity-60"></div>
    </div>

    <!-- 主卡片（玻璃拟态） -->
    <main class="w-full max-w-[420px] bg-surface/70 backdrop-blur-xl rounded-[1.25rem] shadow-[0_8px_32px_rgba(83,65,205,0.06)] border border-outline-variant/40 p-8 relative z-10 flex flex-col gap-unit-24">
      <!-- Header -->
      <div class="flex flex-col items-center text-center">
        <div class="w-16 h-16 bg-primary-container text-on-primary-container rounded-[1rem] flex items-center justify-center shadow-sm mb-4 overflow-hidden">
          <img v-if="store.siteLogo" :src="store.siteLogo" alt="logo" class="w-full h-full object-contain" />
          <span v-else class="material-symbols-outlined text-[32px]" style="font-variation-settings: 'FILL' 1;">dashboard</span>
        </div>
        <h1 class="font-headline-lg text-headline-lg text-primary tracking-tight mb-1">{{ store.siteName }}</h1>
        <p class="font-body-md text-body-md text-secondary">{{ store.siteSubtitle || '你的个人导航主页' }}</p>
      </div>

      <!-- Form -->
      <form class="flex flex-col gap-5 mt-2" @submit.prevent="submit">
        <div class="flex flex-col gap-1.5">
          <label class="font-label-sm text-label-sm text-on-surface-variant ml-1" for="username">用户名</label>
          <div class="relative">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">person</span>
            <input
              id="username"
              v-model="username"
              type="text"
              class="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-lg pl-10 pr-4 py-3 font-body-md text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all shadow-sm"
              placeholder="请输入用户名"
              @keyup.enter="submit"
            />
          </div>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="font-label-sm text-label-sm text-on-surface-variant ml-1" for="password">密码</label>
          <div class="relative">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">lock</span>
            <input
              id="password"
              v-model="password"
              type="password"
              class="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-lg pl-10 pr-4 py-3 font-body-md text-body-md text-on-surface placeholder:text-outline/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all shadow-sm"
              placeholder="••••••••"
              @keyup.enter="submit"
            />
          </div>
        </div>

        <div class="flex items-center gap-2 ml-1 mt-1">
          <input v-model="remember" type="checkbox" id="remember-me" class="w-4 h-4 rounded border-outline-variant/60 text-primary-container focus:ring-primary-container cursor-pointer transition-all" />
          <label for="remember-me" class="font-body-sm text-label-sm text-on-surface-variant cursor-pointer select-none">记住我，30天免登录</label>
        </div>

        <p v-if="error" class="text-error font-body-sm text-body-sm">{{ error }}</p>

        <button
          type="submit"
          class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm rounded-lg py-3.5 mt-2 hover:bg-surface-tint shadow-[0_4px_14px_rgba(83,65,205,0.25)] transition-all active:scale-[0.98] flex justify-center items-center gap-2 disabled:opacity-50"
          :disabled="loading"
        >
          <span>{{ loading ? '登录中…' : '登录' }}</span>
          <span class="material-symbols-outlined text-[18px]">login</span>
        </button>

        <button
          type="button"
          class="w-full mt-3 py-2.5 rounded-lg border border-outline-variant/70 text-on-surface-variant font-body-md hover:bg-surface-container transition-colors flex justify-center items-center gap-2 disabled:opacity-50"
          :disabled="loading"
          @click="enterAsGuest"
        >
          <span class="material-symbols-outlined text-[18px]">travel_explore</span>
          <span>游客访问（仅浏览公开内容）</span>
        </button>
      </form>

      <!-- Footer Action -->
      <div class="pt-6 mt-2 border-t border-outline-variant/30 flex items-center justify-center gap-4 text-center">
        <router-link to="/register" class="group font-body-md text-body-md text-secondary hover:text-primary transition-colors inline-flex items-center gap-1">
          <span>注册账号</span>
          <span class="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
        </router-link>
        <span class="text-outline-variant">|</span>
        <router-link to="/reset-password" class="group font-body-md text-body-md text-secondary hover:text-primary transition-colors inline-flex items-center gap-1">
          <span>忘记密码</span>
          <span class="material-symbols-outlined text-[18px] group-hover:translate-x-1 transition-transform">arrow_forward</span>
        </router-link>
      </div>
    </main>
  </div>
</template>
