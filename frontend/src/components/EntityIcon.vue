<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  // 实体自带的图标值：本地/远程图片路径、Material Symbols 名称，或用户自定义 emoji
  icon: { type: String, default: '' },
  // 取不到图标时兜底的 Material Symbols 名称（不使用无关 emoji 占位）
  fallback: { type: String, default: 'link' },
  size: { type: [Number, String], default: 20 },
  alt: { type: String, default: '' },
})

const value = computed(() => (props.icon || '').trim())
const px = computed(() => `${props.size}px`)

// 远程图标地址可能加载不到（无外网 / 内网不可达），失败后回退到 fallback 符号，避免破图
const imgError = ref(false)
watch(value, () => { imgError.value = false })

// 本地磁盘路径（如 D:\icons\a.png）：浏览器无法直接渲染，用占位图标代替，避免显示成乱码文本
const isLocalFsPath = computed(() => /^([A-Za-z]:[\\/]|\\\\|file:\/\/)/.test(value.value))
// 图片路径：本地上传路径(/uploads/...)或远程 http(s)
const isImagePath = computed(
  () => !isLocalFsPath.value && /^(\/|https?:\/\/)/.test(value.value)
)
// 实际以 <img> 渲染：图片路径且未加载失败
const isImage = computed(() => isImagePath.value && !imgError.value)
// Material Symbols：仅小写字母/数字/下划线，如 folder、play_circle
const isSymbol = computed(() => /^[a-z0-9_]+$/.test(value.value))
// 其余非空值视为用户自定义 emoji / 文本图标，原样渲染
const isEmoji = computed(
  () => !!value.value && !isImagePath.value && !isSymbol.value && !isLocalFsPath.value
)
// 非法或空值时回退到 fallback，避免把图片路径塞进图标字体渲染成乱码
const symbolName = computed(() => (isSymbol.value ? value.value : props.fallback))
</script>

<template>
  <img
    v-if="isImage"
    :src="value"
    :alt="alt"
    class="object-contain shrink-0"
    :style="{ width: px, height: px }"
    @error="imgError = true"
  />
  <span v-else-if="isEmoji" class="shrink-0 leading-none" :style="{ fontSize: px }">{{ value }}</span>
  <span
    v-else
    class="material-symbols-outlined shrink-0 leading-none"
    :style="{ fontSize: px }"
  >{{ symbolName }}</span>
</template>
