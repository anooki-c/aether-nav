<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { store } from '../store'
import PasswordField from '../components/PasswordField.vue'

const router = useRouter()
const username = ref('')
const newPassword = ref('')
const confirm = ref('')
const error = ref('')
const done = ref(false)
const loading = ref(false)

async function submit() {
  error.value = ''
  if (newPassword.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  if (newPassword.value !== confirm.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await api.resetPassword({ username: username.value.trim(), new_password: newPassword.value })
    done.value = true
  } catch (e) {
    error.value = e.message || '重置失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-bg-page min-h-screen flex items-center justify-center font-body-md text-on-surface relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
      <div class="absolute top-[-10%] right-[-5%] w-96 h-96 bg-primary-container rounded-full mix-blend-multiply filter blur-[100px] opacity-20"></div>
      <div class="absolute bottom-[-10%] left-[-10%] w-80 h-80 bg-info rounded-full mix-blend-multiply filter blur-[100px] opacity-20"></div>
    </div>

    <div class="w-full max-w-[440px] px-unit-16 relative z-10">
      <div class="bg-bg-card rounded-[16px] shadow-sm p-8 sm:p-10 relative overflow-hidden glass-card">
        <!-- Logo & Header -->
        <div class="flex flex-col items-center mb-8">
          <div class="w-12 h-12 bg-primary-container rounded-xl flex items-center justify-center mb-4 shadow-sm">
            <span class="material-symbols-outlined text-on-primary-container" style="font-size: 24px;">ac_unit</span>
          </div>
          <h1 class="font-headline-lg text-headline-lg text-text-primary text-center">{{ store.siteName }}</h1>
          <p class="font-body-md text-body-md text-text-secondary mt-2 text-center">请在下方输入你的新密码</p>
        </div>

        <!-- Form -->
        <form v-if="!done" class="space-y-5" @submit.prevent="submit">
          <div>
            <label class="block font-label-sm text-label-sm text-on-surface-variant mb-1" for="username">用户名</label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <span class="material-symbols-outlined text-outline" style="font-size: 18px;">person</span>
              </div>
              <input id="username" v-model="username" type="text" class="block w-full pl-10 pr-3 py-2 border border-outline-variant/50 rounded-lg bg-surface-container-lowest font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-colors shadow-sm placeholder:text-outline/50" placeholder="请输入用户名" />
            </div>
          </div>
          <div>
            <label class="block font-label-sm text-label-sm text-on-surface-variant mb-1" for="new-password">新密码</label>
            <PasswordField id="new-password" v-model="newPassword" icon="lock" placeholder="••••••••" autocomplete="new-password" input-class="block w-full py-2 border border-outline-variant/50 rounded-lg bg-surface-container-lowest font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-colors shadow-sm placeholder:text-outline/50" />
          </div>
          <div>
            <label class="block font-label-sm text-label-sm text-on-surface-variant mb-1" for="confirm-password">确认新密码</label>
            <PasswordField id="confirm-password" v-model="confirm" icon="swipe_left_alt" placeholder="••••••••" autocomplete="new-password" input-class="block w-full py-2 border border-outline-variant/50 rounded-lg bg-surface-container-lowest font-body-md text-body-md text-on-surface focus:outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container transition-colors shadow-sm placeholder:text-outline/50" />
          </div>
          <p v-if="error" class="text-error font-body-sm text-body-sm">{{ error }}</p>
          <button type="submit" :disabled="loading" class="w-full bg-primary-container hover:bg-primary text-on-primary-container font-headline-sm text-headline-sm py-2.5 px-4 rounded-lg shadow-sm transition-all duration-200 active:scale-[0.98] mt-6 flex items-center justify-center gap-2 group disabled:opacity-50">
            <span>{{ loading ? '重置中…' : '重置密码' }}</span>
            <span class="material-symbols-outlined text-on-primary-container group-hover:translate-x-1 transition-transform" style="font-size: 18px;">arrow_forward</span>
          </button>
        </form>

        <!-- 成功态 -->
        <div v-else class="text-center space-y-4">
          <div class="w-14 h-14 mx-auto rounded-full bg-success/15 flex items-center justify-center text-success">
            <span class="material-symbols-outlined" style="font-size: 32px;" data-weight="fill">check_circle</span>
          </div>
          <p class="font-headline-sm text-headline-sm text-text-primary">密码已重置</p>
        </div>

        <!-- Footer Link -->
        <div class="mt-8 text-center">
          <router-link to="/login" class="inline-flex items-center gap-1 font-body-sm text-body-sm text-primary hover:text-primary-container transition-colors">
            <span class="material-symbols-outlined" style="font-size: 16px;">arrow_back</span>
            返回登录
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
}
</style>
