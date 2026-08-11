<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setAuth, loadMe, loadTree, store } from '../store'
import { api } from '../api/client'

const router = useRouter()
const fullName = ref('')
const username = ref('')
const email = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  if (password.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const data = await api.register({
      username: username.value.trim(),
      password: password.value,
      display_name: fullName.value.trim(),
    })
    setAuth(data.token, data.user)
    await loadMe()
    await loadTree()
    router.push('/')
  } catch (e) {
    error.value = e.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-surface-container min-h-screen flex items-center justify-center p-unit-24 font-body-md text-on-surface">
    <main class="w-full max-w-[440px]">
      <div class="bg-surface-container-lowest rounded-xl shadow-sm p-card-padding flex flex-col gap-[2rem] border border-outline-variant/30">
        <!-- Brand Header -->
        <div class="flex flex-col items-center text-center gap-unit-8">
          <div class="w-12 h-12 rounded-lg bg-primary-container/20 flex items-center justify-center text-primary mb-2">
            <span class="material-symbols-outlined" style="font-size: 28px;">explore</span>
          </div>
          <h1 class="font-headline-lg text-headline-lg text-on-surface">{{ store.siteName }}</h1>
          <p class="font-body-sm text-body-sm text-on-surface-variant">创建你的个人导航主页</p>
        </div>

        <!-- Form -->
        <form class="flex flex-col gap-unit-16" @submit.prevent="submit">
          <div class="flex flex-col gap-unit-4">
            <label class="font-label-sm text-label-sm text-on-surface-variant" for="fullName">姓名</label>
            <input id="fullName" v-model="fullName" type="text" class="w-full bg-surface rounded-lg border border-outline-variant px-unit-16 py-[10px] text-on-surface font-body-md focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all shadow-sm" placeholder="张三" />
          </div>
          <div class="flex flex-col gap-unit-4">
            <label class="font-label-sm text-label-sm text-on-surface-variant" for="username">用户名</label>
            <input id="username" v-model="username" type="text" class="w-full bg-surface rounded-lg border border-outline-variant px-unit-16 py-[10px] text-on-surface font-body-md focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all shadow-sm" placeholder="zhangsan" />
          </div>
          <div class="flex flex-col gap-unit-4">
            <label class="font-label-sm text-label-sm text-on-surface-variant" for="email">邮箱</label>
            <input id="email" v-model="email" type="email" class="w-full bg-surface rounded-lg border border-outline-variant px-unit-16 py-[10px] text-on-surface font-body-md focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all shadow-sm" placeholder="zhangsan@example.com" />
          </div>
          <div class="flex flex-col gap-unit-4">
            <label class="font-label-sm text-label-sm text-on-surface-variant" for="password">密码</label>
            <input id="password" v-model="password" type="password" class="w-full bg-surface rounded-lg border border-outline-variant px-unit-16 py-[10px] text-on-surface font-body-md focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all shadow-sm" placeholder="••••••••" />
          </div>
          <div class="flex flex-col gap-unit-4">
            <label class="font-label-sm text-label-sm text-on-surface-variant" for="confirmPassword">确认密码</label>
            <input id="confirmPassword" v-model="confirm" type="password" class="w-full bg-surface rounded-lg border border-outline-variant px-unit-16 py-[10px] text-on-surface font-body-md focus:border-primary focus:ring-1 focus:ring-primary/50 outline-none transition-all shadow-sm" placeholder="••••••••" />
          </div>
          <p v-if="error" class="text-error font-body-sm text-body-sm">{{ error }}</p>
          <div class="pt-unit-8">
            <button type="submit" :disabled="loading" class="w-full bg-primary text-on-primary font-headline-sm text-headline-sm rounded-lg py-3 px-6 shadow-sm hover:shadow-md hover:-translate-y-[1px] hover:bg-surface-tint transition-all duration-200 disabled:opacity-50">
              {{ loading ? '创建中…' : '创建账号' }}
            </button>
          </div>
        </form>

        <!-- Footer Links -->
        <div class="text-center pt-unit-8 border-t border-outline-variant/30">
          <router-link to="/login" class="font-body-sm text-body-sm text-on-surface-variant hover:text-primary transition-colors">
            已有账号？<span class="font-headline-sm text-headline-sm text-primary">登录</span>
          </router-link>
        </div>
      </div>
    </main>
  </div>
</template>
