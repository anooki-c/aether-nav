<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { store, logout } from '../store'
import EntityIcon from './EntityIcon.vue'

const router = useRouter()
const open = ref(false)
const root = ref(null)

const displayName = computed(() => store.user?.display_name || store.user?.username || '访客')
const isAdmin = computed(() => store.user && store.user.role === 'admin')

// 头像菜单对所有登录用户一致：个人设置 + 管理后台 + 退出登录（不区分管理员/普通用户）
const items = computed(() => {
  return [
    { k: 'settings', icon: 'settings', label: '个人设置', to: '/settings' },
    { k: 'admin', icon: 'admin_panel_settings', label: '管理后台', to: '/admin' },
  ]
})

function toggle() {
  open.value = !open.value
}
function close() {
  open.value = false
}
function go(to) {
  close()
  router.push(to)
}
function onSignOut() {
  close()
  logout()
  router.push('/login')
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) close()
}
function onKey(e) {
  if (e.key === 'Escape') close()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div v-if="store.user" ref="root" class="relative">
    <button
      class="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center border-2 border-surface-container-highest overflow-hidden cursor-pointer hover:bg-surface-variant transition-colors"
      :title="displayName"
      @click="toggle"
    >
      <EntityIcon :icon="store.user.avatar" fallback="person" :size="28" alt="头像" />
    </button>

    <!-- 下拉菜单 -->
    <transition
      enter-active-class="transition ease-out duration-150"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-in duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-52 bg-surface rounded-xl shadow-glass border border-surface-variant/60 py-1.5 z-50"
        @click.stop
      >
        <div class="px-4 py-2 border-b border-outline-variant/40 flex items-center gap-2">
          <div class="w-8 h-8 rounded-full bg-surface-container-high flex items-center justify-center overflow-hidden shrink-0">
            <EntityIcon :icon="store.user.avatar" fallback="person" :size="22" alt="头像" />
          </div>
          <div class="min-w-0">
            <div class="text-body-sm font-semibold text-on-surface truncate">{{ displayName }}</div>
            <div class="text-label-sm text-on-surface-variant truncate">@{{ store.user.username }}</div>
          </div>
        </div>

        <button
          v-for="it in items"
          :key="it.k"
          class="w-full flex items-center gap-3 px-4 py-2.5 text-left text-body-sm text-on-surface hover:bg-surface-container transition-colors"
          @click="go(it.to)"
        >
          <span class="material-symbols-outlined text-[20px] text-on-surface-variant">{{ it.icon }}</span>
          {{ it.label }}
        </button>

        <button
          class="w-full flex items-center gap-3 px-4 py-2.5 text-left text-body-sm text-error hover:bg-error-container/30 transition-colors border-t border-outline-variant/40"
          @click="onSignOut"
        >
          <span class="material-symbols-outlined text-[20px]">logout</span>
          退出登录
        </button>
      </div>
    </transition>
  </div>
</template>
