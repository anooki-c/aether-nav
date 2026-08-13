<script setup>
import { computed } from 'vue'
import { store } from '../store'
import { getLinkIcon, iconColorMap } from '../utils/linkIcon'
import { hexToRgba } from '../utils/color'
import EntityIcon from './EntityIcon.vue'

const props = defineProps({
  link: { type: Object, required: true },
  // 可编辑：登录且站点允许主页编辑（后台「主页是否可以编辑」）时为真，
  // 显示编辑按钮 + 图标区可点击刷新；卡片点击仍打开链接
  editable: { type: Boolean, default: false },
  // 所属分类颜色（系统「分类颜色」开关开启时用于图标背景/字形着色）
  categoryColor: { type: String, default: '' },
})
const emit = defineEmits(['open', 'edit', 'fetch-icon'])

// 图标正在刷新中
const iconBusy = computed(() => store.iconBusyId === props.link.id)

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
// 分类颜色是否生效：开关开启且链接携带分类颜色
const catActive = computed(() => store.showCategoryColors && !!props.categoryColor)
const catContainerStyle = computed(() =>
  catActive.value ? { background: hexToRgba(props.categoryColor, 0.16) } : {}
)
const catIconStyle = computed(() =>
  catActive.value ? { color: props.categoryColor } : {}
)

function onCardClick() {
  emit('open', props.link)
}
</script>

<template>
  <!-- 移动端方形卡：1:1，仅图标 + 标题（对齐 square_cards 原型） -->
  <a
    class="aspect-square rounded-xl glass-card flex flex-col items-center justify-center gap-2 p-2 relative cursor-pointer active:scale-95 transition-[transform,box-shadow] duration-200 ease-spring overflow-hidden"
    :class="editable ? 'ring-1 ring-brand/40' : ''"
    @click.prevent="onCardClick"
  >
    <!-- 可编辑：编辑按钮（纯图标，移动端无 hover 常驻显示） -->
    <button
      v-if="editable"
      type="button"
      class="absolute top-1.5 left-1.5 z-20 flex items-center justify-center text-on-surface-variant hover:text-brand active:scale-90"
      title="编辑链接"
      @click.stop="emit('edit', link)"
    >
      <span class="material-symbols-outlined text-[18px]">edit</span>
    </button>

    <!-- 网络标识：右上角小圆点（外网=绿 / 内网=橙） -->
    <span
      class="absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full"
      :class="link.network === 'external' ? 'bg-success' : 'bg-warning'"
    ></span>

    <!-- 加密标识：右下角（移动端缩小至 50%） -->
    <span
      v-if="link.has_password && store.showPasswordLock"
      class="absolute bottom-1 right-1 text-[5px] bg-error-container text-error px-0.5 rounded flex items-center gap-0.5"
    >
      <span class="material-symbols-outlined text-[6px]">lock</span>
    </span>

    <!-- 图标（点击 = 打开链接；刷新图标由右上角小按钮触发） -->
    <div
      class="relative w-10 h-10 rounded-xl flex items-center justify-center"
      :class="[
        catActive ? '' : 'bg-surface-container',
        editable ? 'ring-2 ring-brand/60' : '',
      ]"
      :style="catContainerStyle"
    >
      <EntityIcon
        :icon="link.icon"
        :fallback="getLinkIcon(link.title)"
        :size="26"
        :alt="link.title"
        :class="catActive ? '' : iconColor"
        :style="catIconStyle"
      />
      <!-- 刷新中：转圈遮罩 -->
      <div
        v-if="iconBusy"
        class="absolute inset-0 bg-black/40 rounded-xl flex items-center justify-center"
      >
        <span class="material-symbols-outlined text-[16px] text-white animate-spin">progress_activity</span>
      </div>
      <!-- 可编辑：图标右上角小刷新按钮（纯图标，无背景，与编辑按钮同系列） -->
      <button
        v-if="editable"
        type="button"
        class="absolute -top-1.5 -right-1.5 z-20 flex items-center justify-center text-on-surface-variant hover:text-brand active:scale-90"
        title="刷新图标"
        @click.stop="emit('fetch-icon', link)"
      >
        <span class="material-symbols-outlined text-[18px]">refresh</span>
      </button>
    </div>

    <!-- 标题 -->
    <span class="font-label-sm text-label-sm text-on-background text-center truncate w-full px-1 leading-tight">{{ link.title }}</span>
  </a>
</template>
