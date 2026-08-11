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
// 点击图标区域（可编辑时）：调用默认接口自动获取/更新图标
function onIconClick() {
  if (props.editable) emit('fetch-icon', props.link)
}
</script>

<template>
  <!-- 移动端方形卡：1:1，仅图标 + 标题（对齐 square_cards 原型） -->
  <a
    class="aspect-square rounded-xl glass-card flex flex-col items-center justify-center gap-2 p-2 relative cursor-pointer active:scale-95 transition-[transform,box-shadow] duration-200 ease-spring overflow-hidden"
    :class="editable ? 'ring-1 ring-brand/40' : ''"
    @click.prevent="onCardClick"
  >
    <!-- 可编辑：编辑按钮（移动端无 hover，常驻显示） -->
    <button
      v-if="editable"
      type="button"
      class="absolute top-1.5 left-1.5 z-20 w-7 h-7 rounded-full bg-brand text-white flex items-center justify-center shadow-md active:scale-90"
      title="编辑链接"
      @click.stop="emit('edit', link)"
    >
      <span class="material-symbols-outlined text-[16px]">edit</span>
    </button>

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

    <!-- 图标（编辑模式下点击 = 调用默认接口获取/更新图标） -->
    <div
      class="relative w-9 h-9 rounded-lg flex items-center justify-center overflow-hidden"
      :class="[
        catActive ? '' : 'bg-surface-container',
        editable ? 'ring-2 ring-brand/60' : '',
      ]"
      :style="catContainerStyle"
      @click.stop="onIconClick"
    >
      <EntityIcon
        :icon="link.icon"
        :fallback="getLinkIcon(link.title)"
        :size="22"
        :alt="link.title"
        :class="catActive ? '' : iconColor"
        :style="catIconStyle"
      />
      <!-- 编辑模式下：图标刷新中显示转圈遮罩 -->
      <div
        v-if="iconBusy"
        class="absolute inset-0 bg-black/40 rounded-lg flex items-center justify-center"
      >
        <span class="material-symbols-outlined text-[16px] text-white animate-spin">progress_activity</span>
      </div>
      <!-- 可编辑（非刷新中）：右下角小角标，提示图标可点刷新（移动端无 hover，需常驻提示） -->
      <span
        v-else-if="editable"
        class="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-brand text-white flex items-center justify-center shadow ring-2 ring-surface-container-low"
      >
        <span class="material-symbols-outlined text-[10px] leading-none">refresh</span>
      </span>
    </div>

    <!-- 标题 -->
    <span class="font-label-sm text-label-sm text-on-background text-center truncate w-full px-1 leading-tight">{{ link.title }}</span>
  </a>
</template>
