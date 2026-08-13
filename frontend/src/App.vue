<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { store, loadTree, loadMe, loadSettings, focusSearch, openDrawer, openAddLink, applyFavicon } from './store'
import Sidebar from './components/Sidebar.vue'
import TopBar from './components/TopBar.vue'
import MobileNav from './components/MobileNav.vue'
import AddLinkModal from './components/AddLinkModal.vue'
import QuickAddLink from './components/QuickAddLink.vue'

const route = useRoute()
const isLogin = computed(() => route.name === 'login')
// 后台管理 / 个人设置均为独立控制台（自有侧边栏+顶栏），不再套用主应用导航
const isAdmin = computed(() => route.name === 'admin')
const isSettings = computed(() => route.name === 'settings')
const showQuick = ref(false)
// 书签小工具从外部网页带来的预填（当前页 URL/标题）
const quickPrefill = ref({ url: '', title: '' })

onMounted(async () => {
  // 解析书签小工具带过来的 ?quickadd=URL&title=标题
  try {
    const params = new URLSearchParams(window.location.search)
    const q = params.get('quickadd')
    if (q) {
      quickPrefill.value = { url: decodeURIComponent(q), title: decodeURIComponent(params.get('title') || '') }
      showQuick.value = true
      // 清理地址栏，避免刷新后重复弹出
      window.history.replaceState({}, '', window.location.pathname)
    }
  } catch (e) { /* 解析失败忽略 */ }
  await loadSettings()
  await loadMe()
  await loadTree()
})

// 站点 Logo 变更（后台保存后无需刷新）→ 实时同步标签页图标
watch(() => store.siteLogo, (v) => applyFavicon(v))

// 顶栏「添加」→ 快速添加（自动识别网络/标题/图标）
function openQuick() {
  // 清空可能残留的书签小工具预填，避免带入上次外部网页地址
  quickPrefill.value = { url: '', title: '' }
  showQuick.value = true
}
// 快速添加里「切换到完整表单」→ 打开完整弹窗（新增模式）
function toFullForm() {
  showQuick.value = false
  openAddLink()
}
function backToTop() {
  const el = document.getElementById('main-scroll')
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' })
}
function onSearchNav() {
  focusSearch()
}
function onProfileNav() {
  // 移动端「我的」：已登录 → 个人设置；未登录 → 登录页（不再打开侧边栏抽屉）
  if (store.user) router.push('/settings')
  else router.push('/login')
}

const TOAST_STYLE = {
  success: { cls: 'bg-bg-card border-success/40 text-success', icon: 'check_circle' },
  warn: { cls: 'bg-bg-card border-warning/40 text-warning', icon: 'warning' },
  error: { cls: 'bg-bg-card border-error/40 text-error', icon: 'error' },
  info: { cls: 'bg-bg-card border-outline-variant text-on-surface', icon: 'info' },
}
const toastClass = computed(() => (TOAST_STYLE[store.toast.type] || TOAST_STYLE.info).cls)
const toastIcon = computed(() => (TOAST_STYLE[store.toast.type] || TOAST_STYLE.info).icon)
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-background text-on-background">
    <Sidebar v-if="!isLogin && !isAdmin && !isSettings" />
    <div
      class="flex-1 flex flex-col min-w-0 transition-[padding] duration-200 ease-spring"
      :class="!isLogin && !isAdmin && !isSettings ? (store.sidebarCollapsed ? 'lg:pl-[144px]' : 'lg:pl-[240px]') : ''"
    >
      <TopBar v-if="!isLogin && !isAdmin && !isSettings" @add-link="openQuick" />
      <div id="main-scroll" class="flex-1 min-h-0 overflow-y-auto pb-20 lg:pb-0">
        <router-view v-slot="{ Component }">
          <Transition name="route">
            <component :is="Component" />
          </Transition>
        </router-view>
      </div>
    </div>
    <MobileNav v-if="!isLogin && !isAdmin && !isSettings" @search="onSearchNav" @profile="onProfileNav" @add-link="openQuick" />

    <!-- 回到顶部 FAB（桌面端显示） -->
    <button
      v-if="!isLogin && !isAdmin && !isSettings"
      class="fixed bottom-20 lg:bottom-8 right-8 w-14 h-14 bg-[#002FA7] text-white rounded-full flex items-center justify-center shadow-[0_10px_25px_-5px_rgba(0,47,167,0.45)] hover:scale-105 hover:bg-[#00238a] transition-[transform,background-color] z-40 active:scale-95 hidden lg:flex"
      @click="backToTop"
      aria-label="回到顶部"
    >
      <span class="material-symbols-outlined text-[28px]">arrow_upward</span>
    </button>

    <AddLinkModal :open="store.linkModalOpen" :edit-link="store.linkModalEditLink" @update:open="store.linkModalOpen = $event" />
    <QuickAddLink :open="showQuick" :prefill-url="quickPrefill.url" :prefill-title="quickPrefill.title" @update:open="showQuick = $event" @full-form="toFullForm" />

    <!-- 全局轻提示 -->
    <Transition name="toast-fade">
      <div
        v-if="store.toast.text"
        class="fixed top-6 left-1/2 -translate-x-1/2 z-[100] max-w-[90vw] px-4 py-3 rounded-xl shadow-lg border flex items-center gap-2 text-sm"
        :class="toastClass"
      >
        <span class="material-symbols-outlined text-[18px]">{{ toastIcon }}</span>
        <span>{{ store.toast.text }}</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.23, 1, 0.32, 1), transform 0.2s cubic-bezier(0.23, 1, 0.32, 1);
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
/* 路由切换：整页淡入（仅 opacity，避免两页同屏重叠/跳动） */
.route-enter-active,
.route-leave-active {
  transition: opacity 220ms cubic-bezier(0.23, 1, 0.32, 1);
}
.route-enter-from,
.route-leave-to {
  opacity: 0;
}
</style>
