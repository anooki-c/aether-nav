<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
const emit = defineEmits(['search', 'profile', 'add-link'])
</script>

<template>
  <nav
    class="bg-surface-container-highest dark:bg-inverse-surface border-t border-outline-variant/30 backdrop-blur-lg shadow-2xl shadow-primary/15 fixed bottom-0 left-0 w-full z-50 lg:hidden rounded-t-xl"
  >
    <div class="flex justify-around items-center h-16 px-4">
      <a
        class="flex flex-col items-center justify-center text-brand bg-brand/10 rounded-xl px-4 py-1 active:scale-90 transition-[transform,background-color] duration-150 ease-spring font-label-sm text-label-sm"
        @click="router.push('/')"
      >
        <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1">home</span>
        <span>首页</span>
      </a>
      <a class="flex flex-col items-center justify-center text-on-secondary-fixed-variant active:bg-surface-variant active:scale-90 transition-[transform,background-color] duration-150 ease-spring font-label-sm text-label-sm cursor-pointer" @click="emit('search')">
        <span class="material-symbols-outlined">search</span>
        <span>搜索</span>
      </a>
      <a class="flex flex-col items-center justify-center text-on-secondary-fixed-variant active:bg-surface-variant active:scale-90 transition-[transform,background-color] duration-150 ease-spring font-label-sm text-label-sm cursor-pointer" @click="emit('profile')">
        <span class="material-symbols-outlined">person</span>
        <span>我的</span>
      </a>
    </div>
  </nav>
</template>
