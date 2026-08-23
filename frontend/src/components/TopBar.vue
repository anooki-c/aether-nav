<script setup>
import { store, setNetwork, toggleSidebar } from '../store'
import WeatherWidget from './WeatherWidget.vue'
import UserMenu from './UserMenu.vue'
import SearchHero from './SearchHero.vue'

const emit = defineEmits(['add-link'])

function pick(network) {
  setNetwork(network)
}

function onSearch({ engine, q }) {
  if (engine === 'local') store.searchQuery = q || ''
}
</script>

<template>
  <header
    class="site-topbar w-full px-5 flex justify-between items-center sticky top-0 z-30 h-16"
  >
    <!-- 左侧：折叠侧边栏图标 + 城市天气 -->
    <div class="flex items-center gap-3 min-w-0">
      <button
        class="topbar-control ui-icon-hover w-10 h-10 flex items-center justify-center text-on-surface-variant hover:bg-surface-variant active:scale-95 active:bg-surface-variant rounded-xl transition-[transform,background-color] duration-200 ease-spring shrink-0"
        @click="toggleSidebar"
        :title="store.sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'"
      >
        <span class="material-symbols-outlined">{{ store.sidebarCollapsed ? 'menu' : 'menu_open' }}</span>
      </button>
      <WeatherWidget class="hidden sm:flex" />
    </div>

    <div class="flex items-center gap-4">
      <!-- 站内/外部搜索：固定在顶栏右侧，输入响应来自当前搜索引擎配置 -->
      <div class="shrink min-w-0" style="width: clamp(140px, 32vw, 360px)">
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

      <!-- 内外网切换（对齐原型 P1：pill 按钮 Internal/External） -->
      <div class="network-switch flex items-center bg-surface-container-highest rounded-full p-1 gap-1">
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full font-label-sm text-label-sm transition-[transform,background-color,color] duration-200 ease-spring active:scale-95"
          :class="store.network === 'internal' ? 'bg-brand text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
          @click="pick('internal')"
        >
          <span class="material-symbols-outlined text-[16px]">home</span>
          <span class="hidden min-[400px]:inline">内网</span>
        </button>
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full font-label-sm text-label-sm transition-[transform,background-color,color] duration-200 ease-spring active:scale-95"
          :class="store.network === 'external' ? 'bg-brand text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
          @click="pick('external')"
        >
          <span class="material-symbols-outlined text-[16px]">public</span>
          <span class="hidden min-[400px]:inline">外网</span>
        </button>
      </div>

      <!-- 头像菜单（登录后显示，右上角） -->
      <UserMenu />
    </div>
  </header>
</template>
