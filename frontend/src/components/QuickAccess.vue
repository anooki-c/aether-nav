<script setup>
import { computed } from 'vue'
import draggable from 'vuedraggable'
import { store } from '../store'
import EntityIcon from './EntityIcon.vue'

const props = defineProps({
  // 当前用户收藏的链接（后端已按可见性过滤 + position 排序）
  links: { type: Array, default: () => [] },
  // 登录用户可拖拽调整顺序（收藏本身按用户独立存储）
  sortable: { type: Boolean, default: false },
})
const emit = defineEmits(['open', 'reorder'])

// 三档卡片尺寸（系统设置 → 显示设置 → 快捷访问卡片大小）。
// 类名与图标像素必须写成字面量，供 Tailwind JIT 扫描生成对应样式。
const SIZES = {
  small: { tile: 'w-11 h-11 rounded-xl', icon: 20, gap: 'gap-2.5' },
  medium: { tile: 'w-14 h-14 rounded-2xl', icon: 26, gap: 'gap-3' },
  large: { tile: 'w-[72px] h-[72px] rounded-2xl', icon: 34, gap: 'gap-4' },
}
const size = computed(() => SIZES[store.quickAccessSize] || SIZES.medium)

// 无图标时的兜底：取标题首字（保留中文原样，拉丁字母转大写），避免整排相同的占位符号
function initial(title) {
  const t = (title || '').trim()
  if (!t) return '?'
  return t.slice(0, 1).toUpperCase()
}

// 拖拽结束：把当前顺序回传父组件存库
function onDragEnd(list) {
  emit('reorder', list.map((l) => l.id))
}
</script>

<template>
  <section class="mb-8" id="quick-access-section">
    <h3 class="font-headline-md text-headline-md text-on-background mb-4 flex items-center gap-2">
      <span class="w-7 h-7 rounded-lg flex items-center justify-center bg-surface-container">
        <span class="material-symbols-outlined text-[18px] text-brand" style="font-variation-settings: 'FILL' 1">star</span>
      </span>
      快捷访问
      <span v-if="sortable" class="font-label-sm text-label-sm text-on-surface-variant font-normal">拖拽可调整顺序</span>
    </h3>

    <!-- 登录用户：可拖拽排序。distance=6 让「点击打开」与「拖拽」共存——
         位移小于 6px 视为点击，不会误触发排序。 -->
    <draggable
      v-if="sortable"
      :list="links"
      item-key="id"
      :animation="180"
      :distance="6"
      :class="['flex flex-wrap items-center', size.gap]"
      @end="onDragEnd(links)"
    >
      <template #item="{ element }">
        <a
          class="glass-card flex items-center justify-center shrink-0 cursor-pointer active:scale-95"
          :class="size.tile"
          :title="element.title"
          @click.prevent="emit('open', element)"
        >
          <EntityIcon
            v-if="(element.icon || '').trim()"
            :icon="element.icon"
            fallback="link"
            :size="size.icon"
            :alt="element.title"
          />
          <span
            v-else
            class="font-headline-sm text-headline-sm text-on-surface-variant leading-none select-none"
            :style="{ fontSize: size.icon + 'px' }"
          >{{ initial(element.title) }}</span>
        </a>
      </template>
    </draggable>

    <!-- 未登录（理论上不会有收藏）／无需排序：静态排列 -->
    <div v-else class="flex flex-wrap items-center" :class="size.gap">
      <a
        v-for="l in links"
        :key="l.id"
        class="glass-card flex items-center justify-center shrink-0 cursor-pointer active:scale-95"
        :class="size.tile"
        :title="l.title"
        @click.prevent="emit('open', l)"
      >
        <EntityIcon
          v-if="(l.icon || '').trim()"
          :icon="l.icon"
          fallback="link"
          :size="size.icon"
          :alt="l.title"
        />
        <span
          v-else
          class="font-headline-sm text-headline-sm text-on-surface-variant leading-none select-none"
          :style="{ fontSize: size.icon + 'px' }"
        >{{ initial(l.title) }}</span>
      </a>
    </div>
  </section>
</template>
