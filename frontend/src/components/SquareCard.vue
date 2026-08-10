<script setup>
import { computed } from 'vue'
import { store } from '../store'
import { getLinkIcon, iconColorMap } from '../utils/linkIcon'
import EntityIcon from './EntityIcon.vue'

const props = defineProps({
  link: { type: Object, required: true },
})
const emit = defineEmits(['open'])

// 优先用链接自身 icon，未设置时按标题推断（不使用 emoji 占位）
const symbolName = computed(() => {
  const ic = (props.link.icon || '').trim()
  if (/^(\/|https?:\/\/)/.test(ic)) return null
  if (/^[a-z0-9_]+$/.test(ic)) return ic
  return getLinkIcon(props.link.title)
})
const iconColor = computed(() =>
  symbolName.value ? iconColorMap[symbolName.value] || 'text-on-surface-variant' : ''
)
</script>

<template>
  <!-- 移动端方形卡：1:1，仅图标 + 标题（对齐 square_cards 原型） -->
  <a
    class="aspect-square rounded-xl glass-card flex flex-col items-center justify-center gap-2 p-2 relative cursor-pointer active:scale-95 transition-[transform,box-shadow] duration-200 ease-spring overflow-hidden"
    @click.prevent="emit('open', link)"
  >
    <!-- 网络标识：右上角小圆点（外网=绿 / 内网=蓝） -->
    <span
      class="absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full"
      :class="link.network === 'external' ? 'bg-success' : 'bg-info'"
    ></span>

    <!-- 加密标识：右下角（移动端缩小至 50%） -->
    <span
      v-if="link.has_password && store.showPasswordLock"
      class="absolute bottom-1 right-1 text-[5px] bg-error-container text-error px-0.5 rounded flex items-center gap-0.5"
    >
      <span class="material-symbols-outlined text-[6px]">lock</span>
    </span>

    <!-- 图标 -->
    <div class="w-9 h-9 rounded-lg bg-surface-container flex items-center justify-center overflow-hidden">
      <EntityIcon
        :icon="link.icon"
        :fallback="getLinkIcon(link.title)"
        :size="22"
        :alt="link.title"
        :class="iconColor"
      />
    </div>

    <!-- 标题 -->
    <span class="font-label-sm text-label-sm text-on-background text-center truncate w-full px-1 leading-tight">{{ link.title }}</span>
  </a>
</template>
