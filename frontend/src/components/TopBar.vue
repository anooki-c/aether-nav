<script setup>
import { computed } from 'vue'
import { store, setNetwork, toggleSidebar } from '../store'
import WeatherWidget from './WeatherWidget.vue'
import UserMenu from './UserMenu.vue'
import SearchHero from './SearchHero.vue'

const emit = defineEmits(['add-link'])

// 当前生效网络：用户显式选过就立刻以它为准（点击即反馈，不等后端回包），
// 否则回落到后端解析出来的 effectiveNetwork。'auto' 是「站点默认」、不对应具体内外网，故只作回落分支。
const currentNet = computed(() =>
  store.network === 'internal' || store.network === 'external' ? store.network : store.effectiveNetwork
)

function pick(network) {
  setNetwork(network)
}

// 移动端单按钮：在内外网之间来回切（auto 态下按当前生效态取反）
function toggleNetwork() {
  setNetwork(currentNet.value === 'internal' ? 'external' : 'internal')
}

// Material Symbols 的 FILL 轴：1 = 实心（内网生效），null = 默认描边
function fillStyle(on) {
  return on ? { fontVariationSettings: "'FILL' 1" } : null
}

function onSearch({ engine, q }) {
  if (engine === 'local') store.searchQuery = q || ''
}
</script>

<template>
  <header
    class="site-topbar w-full px-3 md:px-5 flex items-center gap-3 md:gap-4 sticky top-0 z-30 h-16"
  >
    <!-- 左侧：折叠侧边栏图标 + 城市天气 -->
    <div class="flex items-center gap-3 min-w-0 shrink-0">
      <button
        class="topbar-control ui-icon-hover w-10 h-10 flex items-center justify-center text-on-surface-variant hover:bg-surface-variant active:scale-95 active:bg-surface-variant rounded-xl transition-[transform,background-color] duration-200 ease-spring shrink-0"
        @click="toggleSidebar"
        :title="store.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
        :aria-label="store.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
      >
        <!-- 箭头指向「点击后侧边栏的去向」：已折叠 → 向右展开；已展开 → 向左收起 -->
        <span class="material-symbols-outlined">{{ store.sidebarCollapsed ? 'chevron_right' : 'chevron_left' }}</span>
      </button>
      <WeatherWidget class="hidden sm:flex" />
    </div>

    <!-- 右侧：搜索 + 添加 + 内外网 + 头像（整体右对齐；搜索框吃掉剩余宽度） -->
    <div class="flex items-center gap-2 md:gap-4 min-w-0 flex-1 justify-end">
      <!-- 站内/外部搜索：固定在顶栏右侧，输入响应来自当前搜索引擎配置 -->
      <div class="flex-1 min-w-0 md:flex-none md:w-[clamp(140px,32vw,360px)]">
        <SearchHero compact local-only placeholder="站内搜索…" @search="onSearch" />
      </div>
      <!-- 添加链接（登录且允许主页编辑时显示） -->
      <button
        v-if="store.token && store.allowHomeEdit"
        class="topbar-add ui-btn ui-btn-primary rounded-full px-3.5 py-2 min-h-0 font-label-sm text-label-sm active:scale-95 shrink-0"
        @click="emit('add-link')"
        aria-label="添加链接"
      >
        <span class="material-symbols-outlined text-[18px]">add</span>
        <span class="hidden sm:inline">添加</span>
      </button>

      <!-- 内外网切换（对齐原型 P1：pill 按钮 Internal/External）。
           移动端顶栏太挤，收成「单个按钮 + 点击切换」：图标随状态换字形，实心=内网生效。 -->
      <div class="network-switch hidden md:flex items-center bg-surface-container-highest rounded-full p-1 gap-1">
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full font-label-sm text-label-sm transition-[transform,background-color,color] duration-200 ease-spring active:scale-95"
          :class="currentNet === 'internal' ? 'bg-brand text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
          @click="pick('internal')"
        >
          <span class="material-symbols-outlined text-[16px]">home</span>
          <span class="hidden min-[400px]:inline">内网</span>
        </button>
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full font-label-sm text-label-sm transition-[transform,background-color,color] duration-200 ease-spring active:scale-95"
          :class="currentNet === 'external' ? 'bg-brand text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
          @click="pick('external')"
        >
          <span class="material-symbols-outlined text-[16px]">public</span>
          <span class="hidden min-[400px]:inline">外网</span>
        </button>
      </div>

      <!-- 移动端：单个按钮，点击即切换（内网 = home 实心 + 主题色，外网 = public 描边 + 中性色） -->
      <button
        class="network-switch md:hidden w-10 h-10 shrink-0 flex items-center justify-center rounded-full transition-[transform,background-color,color] duration-200 ease-spring active:scale-95"
        :class="currentNet === 'internal' ? 'bg-brand/10 text-brand' : 'bg-surface-container-highest text-on-surface-variant'"
        :title="currentNet === 'internal' ? '当前：内网，点击切换到外网' : '当前：外网，点击切换到内网'"
        :aria-label="currentNet === 'internal' ? '当前内网，点击切换到外网' : '当前外网，点击切换到内网'"
        @click="toggleNetwork"
      >
        <span
          class="material-symbols-outlined text-[20px]"
          :style="fillStyle(currentNet === 'internal')"
        >{{ currentNet === 'internal' ? 'home' : 'public' }}</span>
      </button>

      <!-- 头像菜单（登录后显示，右上角） -->
      <UserMenu />
    </div>
  </header>
</template>
