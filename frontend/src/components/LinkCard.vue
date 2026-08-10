<script setup>
import { computed } from 'vue'
import { store } from '../store'
import { getLinkIcon, iconColorMap } from '../utils/linkIcon'
import { hexToRgba } from '../utils/color'
import EntityIcon from './EntityIcon.vue'

const props = defineProps({
  link: { type: Object, required: true },
  draggable: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  // 所属分类颜色（系统「分类颜色」开关开启时用于图标背景/字形着色）
  categoryColor: { type: String, default: '' },
})
const emit = defineEmits(['open'])

// 实际生效的 Material Symbols 名称：优先取链接自身 icon，
// 为空/为图片时回落到按标题推断（图片场景不需要着色）
const symbolName = computed(() => {
  const ic = (props.link.icon || '').trim()
  if (/^(\/|https?:\/\/)/.test(ic)) return null
  if (/^[a-z0-9_]+$/.test(ic)) return ic
  return getLinkIcon(props.link.title)
})
const iconColor = computed(() =>
  symbolName.value ? iconColorMap[symbolName.value] || 'text-on-surface-variant' : ''
)
// 分类颜色是否生效：开关开启且链接携带分类颜色
const catActive = computed(() => store.showCategoryColors && !!props.categoryColor)
const catContainerStyle = computed(() =>
  catActive.value ? { background: hexToRgba(props.categoryColor, 0.16) } : {}
)
const catIconStyle = computed(() =>
  catActive.value ? { color: props.categoryColor } : {}
)
</script>

<template>
  <a
    class="glass-card rounded-xl flex items-center relative overflow-hidden group cursor-pointer border border-transparent transition-[transform,box-shadow,border-color] duration-300 ease-spring hover:-translate-y-0.5 hover:border-brand hover:shadow-[0_10px_23px_rgba(52,42,100,0.11)] active:scale-[0.98]"
    :class="[
      draggable ? 'cursor-grab active:cursor-grabbing' : '',
      compact ? 'p-3 h-20 gap-3' : 'p-4 h-24 gap-4',
    ]"
    @click.prevent="emit('open', link)"
  >
    <!-- 拖拽手柄 -->
    <div
      v-if="draggable"
      class="absolute top-2 left-2 opacity-0 group-hover:opacity-40 transition-opacity hidden md:block"
    >
      <span class="material-symbols-outlined text-[18px] text-on-surface-variant">drag_indicator</span>
    </div>

    <!-- 图标区域（对齐原型：Material Symbols 小图标 + 彩色，非大号 emoji） -->
    <div
      class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors overflow-hidden"
      :class="catActive ? '' : 'bg-surface-container group-hover:bg-primary-fixed'"
      :style="catContainerStyle"
    >
      <EntityIcon
        :icon="link.icon"
        :fallback="getLinkIcon(link.title)"
        :size="22"
        :alt="link.title"
        :class="catActive ? '' : iconColor"
        :style="catIconStyle"
      />
    </div>

    <!-- 文字信息 -->
    <div class="flex-1 min-w-0">
      <h4 class="font-headline-sm text-headline-sm text-on-background truncate">{{ link.title }}</h4>
      <p class="font-body-sm text-body-sm text-on-surface-variant truncate">{{ link.description }}</p>
    </div>

    <!-- 加密标识（参考目标页：右下角红色 lock 图标，无背景药丸） -->
    <span
      v-if="link.has_password && store.showPasswordLock"
      class="absolute bottom-2 right-2 text-error material-symbols-outlined text-[16px] leading-none"
    >lock</span>

    <!-- 内外网标识（桌面端：右上角小药丸，外网=绿/内网=蓝，纯文字） -->
    <span
      class="absolute top-2 right-2 text-[10px] px-[7px] py-[2px] rounded-md font-semibold hidden md:flex items-center"
      :class="link.network === 'external' ? 'bg-success/10 text-success' : 'bg-info/10 text-info'"
    >
      {{ link.network === 'internal' ? '内网' : '外网' }}
    </span>
    <!-- 移动端：右上角小圆点（外网=绿/内网=蓝） -->
    <span
      class="absolute top-2 right-2 w-2.5 h-2.5 rounded-full md:hidden"
      :class="link.network === 'external' ? 'bg-success' : 'bg-info'"
    ></span>
  </a>
</template>
